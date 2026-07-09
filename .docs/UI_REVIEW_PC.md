# UI_REVIEW_PC — PC 로컬 실행 기준 UI 개선 검토 및 반영사항
_2026-07-09 · Frontend hardening 2차 반영._

## 1. 검토 범위

`UI_PRODUCT_SPEC.md`, `UI_ROADMAP.md`, `DESIGN_INTEGRATION.md`, `BACKEND_REVIEW_PC.md`, `IMPLEMENTATION_BRIEF.md`의 UI 구현 단계에서 실제로 부딪힐 수 있는 데이터 계약 불일치, Windows/한국어 환경 함정, 백엔드-UI 접점, 상태 보존, 접근성 요구를 정리한다.

기본 전제:

```text
- Windows PC 로컬 단일 사용자 웹앱
- 검색 우선, AI 후순위
- 원본 계약서 읽기 전용
- cs_index와 ui_state.sqlite는 PC 로컬 디스크
- Claude Code/Codex는 개발·배치 보조자, 런타임 Haiku/Sonnet/Opus는 Anthropic API 경로
```

## 2. 데이터 계약 불일치 — 우선 수정

### 2.1 고급 필터 ctype/lang 옵션

기존 UI 예시의 계약 유형 목록(`SPA / SHA / SSA / IA / APA / Escrow / 미분류`)은 실제 `type_rules.yaml`의 `ctype` 체계와 일치하지 않는다. `IA`, `Escrow`는 ctype에 없고, `APA`는 `ATA/BTA`에 흡수되어 있으며, `CB인수`, `BW인수`, `EB인수`, `분할합병`, `주식교환`, `JVA`, `MOU` 등은 누락될 수 있다. 언어도 UI 전용 `bilingual` 대신 데이터 값 `국영문`을 써야 한다.

수정 원칙:

```text
- UI는 ctype/lang 옵션을 하드코딩하지 않는다.
- GET /api/catalog/facets 또는 catalog의 DISTINCT ctype/lang에서 동적으로 생성한다.
- type_rules.yaml 또는 manual_overrides.yaml 보강 후에도 UI 코드를 수정하지 않아야 한다.
- 서버가 label/value를 제공하지 않는 한 catalog 값을 그대로 표시한다.
```

### 2.2 원본 계약서 폴더 선택

브라우저는 보안상 로컬 폴더의 절대경로를 JavaScript에 안정적으로 넘겨주지 않는다. `webkitdirectory`는 파일 업로드용이지 PC 로컬 앱의 원본 루트 경로 설정 수단이 아니다.

수정 원칙:

```text
- 온보딩 1단계는 경로 텍스트 입력 방식으로 구현한다.
- POST /api/settings/root-path/validate가 존재 여부, 읽기 권한, 대략 파일 수, 허용 확장자 수, 네트워크 드라이브 여부를 반환한다.
- 검증 전에는 색인 시작 버튼을 활성화하지 않는다.
- 원본 폴더는 읽기 전용으로만 접근한다고 표시한다.
```

## 3. 한국어·Windows 환경 특유 함정

### 3.1 한글 IME composition 처리

검색창에서 Enter로 검색을 실행할 때 한글 조합 중 Enter가 검색으로 처리되면 마지막 글자가 미완성인 채 검색되거나 검색이 두 번 실행될 수 있다.

필수 구현:

```text
- keydown Enter 처리 시 event.isComposing === true이면 return
- keyCode === 229이면 return
- form submit과 keydown에서 중복 검색이 발생하지 않도록 검색 실행 경로를 하나로 수렴
- 검색창 포커스 중 j/k 전역 단축키 비활성화
```

### 3.2 CSV 내보내기 인코딩

한국어 Windows Excel은 BOM 없는 UTF-8 CSV를 cp949로 오인할 수 있다.

필수 구현:

```text
- CSV 다운로드는 utf-8-sig(BOM 포함)로 생성
- 서버 생성 CSV와 클라이언트 생성 CSV 모두 같은 원칙 적용
- 파일명에는 검색어를 그대로 넣지 말고 안전한 timestamp 기반 이름 사용
```

### 3.3 매칭어 하이라이트 정규화 불일치

색인·검색은 normalize()가 적용된 텍스트 기준이지만, 화면 스니펫은 원문 표면형을 보여준다. 전각/반각, 하이픈류, 따옴표류 변이 때문에 단순 문자열 치환 하이라이트는 실패할 수 있다.

필수 구현:

```text
- matched_terms의 term/canonical/variant 후보를 기준으로 원문 표면형을 찾는다.
- 표면형 매칭 실패는 오류가 아니다.
- 실패 시 하이라이트 없이 원문 스니펫과 ¶번호를 표시한다.
- 하이라이트를 위해 원문을 normalize한 문자열로 바꿔 표시하지 않는다.
```

## 4. 백엔드 계약과 UI 접점

### 4.1 진행률 갱신 방식

색인 진행률 화면은 MVP에서 폴링으로 충분하다.

```text
- GET /api/jobs/{job_id}를 1~2초 간격으로 호출
- 표시 필드: status, progress_done, progress_total, current_item, started_at, finished_at, error_code
- 예: 423 / 1,204 files · 현재 파일: 05_SHA/example.docx
- SSE/WebSocket은 v2 이후 최적화
```

### 4.2 warnings UI 표기

백엔드가 반환하는 warnings는 검색 품질 이해에 중요하므로 숨기지 않는다.

```text
short_term_fallback:<term>
→ “2글자/3자 미만 검색어는 폴백 검색으로 처리됨(동의어 확장 또는 랭킹이 일부 달라질 수 있음): <term>”

unsearchable_docs:N
→ “추출 실패/빈 문서 N건은 검색 대상에서 제외됨”
```

표시 위치는 결과 요약줄의 “추출 실패 제외 N건”과 같은 영역으로 둔다.

### 4.3 AI disabled 상태 원인 구분

enabled/disabled 이진 표시만으로는 사용자가 무엇을 해야 하는지 알기 어렵다.

```text
missing_key
→ Anthropic API key 필요 · 설정 > API 예산 및 키 링크

budget_not_set
→ 예산 상한 필요 · 설정 > API 예산 및 키 링크

missing_key_and_budget
→ API key와 예산 상한 필요

no_selection
→ 요약할 문단을 먼저 선택
```

AI 실행 버튼 옆에 원인별 배지를 표시한다.

## 5. 상태 보존

### 5.1 비교 목록 영속성

비교 목록은 실무 리서치 중 새로고침 한 번에 사라지면 치명적이다.

```text
- MVP에서도 ui_state.sqlite에 이름 없는 기본 비교 목록을 저장한다.
- compare_lists / compare_items 테이블을 사용한다.
- 새로고침 후에도 선택 문단이 유지되어야 한다.
- 구현을 미루는 경우 최소한 이탈 경고를 표시한다. 권장안은 영속 저장이다.
```

### 5.2 검색 상태 URL 반영

뒤로가기, 새로고침, 최근 검색의 필터 복원을 가장 싸게 충족하는 방법은 URL query parameter다.

```text
- URL에 query, filters, expand_mode, corpus_scope, page/offset을 반영
- 새로고침 후 같은 결과 상태 복원
- 저장 금지: API key, 로컬 절대경로, 원문 전문, 사용자 메모 전문
```

## 6. 구조적 결정

### 6.1 프론트엔드 스택 결정

UI 문서만으로 프레임워크가 정해지지 않으면 코딩 에이전트가 임의로 무거운 SPA를 선택할 수 있다.

필수 산출물:

```text
- DESIGN_AUDIT.md
- STACK_DECISION.md
```

`STACK_DECISION.md`에는 서버 렌더링 + 경량 JS(htmx/vanilla)와 SPA(React+Vite 등)를 비교하고, getdesign.md 자산 형태와 Windows PC 로컬 단일 사용자 앱의 유지보수성을 기준으로 선택 사유를 적는다. 기본 권장은 서버 렌더링 + 경량 JS다. 다만 getdesign.md가 특정 SPA 컴포넌트 코드를 제공하면 그 근거를 명시하고 SPA를 선택할 수 있다.

## 7. 접근성 보강

필수 구현:

```text
- 진행률, 검색 완료, 오류 메시지는 aria-live 영역으로 알린다.
- split view에서 결과 목록 ↔ 문단 패널 사이의 키보드 포커스 이동 규칙을 둔다.
- 검색창 포커스 중에는 j/k 등 전역 단축키를 비활성화한다.
- 색상만으로 상태를 구분하지 않고 텍스트 배지를 함께 표시한다.
- 버튼 disabled 상태는 이유 문구와 설정 링크를 함께 제공한다.
```

## 8. MVP 반영 우선순위

1. catalog facets 기반 필터
2. 경로 입력 + root-path validate 온보딩
3. IME Enter 방어
4. CSV utf-8-sig
5. job polling 진행률
6. warnings 배지
7. AI disabled reason
8. URL 상태 복원
9. 비교 목록 영속화
10. 하이라이트 폴백
11. STACK_DECISION.md
12. 접근성 세부 규칙
