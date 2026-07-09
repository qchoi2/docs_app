# UI_PRODUCT_SPEC — 계약서 검색 웹앱 제품/화면 스펙
_2026-07-08 · CLI 검색 엔진 구현 후 웹 UI로 확장할 때의 기준 문서다._

## 1. UI 원칙

1. **검색 결과가 먼저, AI 답변은 나중**이다. 사용자는 원문 근거를 먼저 확인하고, 필요한 경우 선택한 결과만으로 요약을 생성한다.
2. **파일럿/전체 코퍼스 범위를 항상 노출**한다. 파일럿 단계의 결과를 전체 샘플의 경향처럼 오해하게 만들지 않는다.
3. **왜 검색됐는지 보여준다.** 결과 카드에는 `why`, `matched_terms`, `score_breakdown`, `¶번호`, `draft 여부`, `중복 수`를 표시한다.
4. **전체 원문 열람보다 문단 주변 보기 우선**이다. 기본 뷰어는 `open_text.py --para/--search --context`에 대응한다.
5. **사용자 작업 흐름을 보존**한다. 최근 검색, 저장된 검색, 비교 목록, 북마크/메모, 내보내기를 별도 기능으로 둔다.
6. **AI는 선택된 근거 안에서만 답한다.** 검색 결과에 없는 내용은 일반화하지 않는다.
7. **필터 데이터는 catalog가 기준이다.** 계약 유형·언어 필터는 코드에 하드코딩하지 않고 `catalog.sqlite`의 `DISTINCT ctype/lang` 또는 이에 대응하는 facets API에서 동적으로 생성한다.
8. **브라우저 보안 제약을 우회하려 하지 않는다.** 원본 계약서 폴더는 브라우저 폴더 피커로 절대경로를 얻는 방식이 아니라, 사용자가 입력한 경로를 백엔드 검증 엔드포인트로 확인한다.
9. **한국어 Windows 사용성을 기본값으로 둔다.** 한글 IME 입력, Excel CSV 인코딩, 정규화된 검색어와 원문 표면형의 하이라이트 불일치, 키보드 접근성을 명시적으로 처리한다.

## 2. 주요 사용자 흐름

### 2.1 기본 검색 흐름

```text
검색어 입력 → 필터 조정 → 결과 카드 확인 → 문단 주변 보기 → 필요한 결과를 비교 목록에 추가 → Markdown/CSV 내보내기
```

### 2.2 AI 보조 흐름

```text
검색 결과 확인 → 사용자가 문서/문단 선택 → [선택 결과로 요약 생성] → 인용 포함 답변 → agent_log 기록
```

AI 답변은 검색 결과 전체가 아니라 **사용자가 선택한 결과 또는 상위 N개 결과**만 근거로 한다.

### 2.3 파일럿 운영 흐름

```text
pilot_001 배치 색인 → 상단 배너에 파일럿 표시 → 결과 품질 확인 → type/term 보정 → full_001 확장 → 동일 검색 재실행
```

파일럿 상태에서는 모든 검색/답변 화면에 다음 문구를 표시한다.

```text
현재 결과는 pilot_001에 포함된 일부 계약서 기준입니다. 전체 코퍼스의 일반적 경향으로 보기는 어렵습니다.
```

### 2.4 첫 실행 온보딩 흐름

브라우저는 보안상 로컬 폴더의 절대경로를 JavaScript에 안정적으로 넘겨주지 않는다. 따라서 온보딩 1단계는 브라우저 폴더 피커가 아니라 **경로 텍스트 입력 + 백엔드 검증**으로 설계한다.

```text
1. 원본 계약서 루트 경로 입력
   예: D:\Contracts\M&A Samples
2. [경로 확인] → POST /api/settings/root-path/validate
3. 백엔드 응답 표시:
   - 존재 여부
   - 읽기 권한
   - 예상 파일 수(.docx/.pdf, zip 제외)
   - 네트워크 드라이브 여부
   - 원본 폴더는 읽기 전용으로만 접근한다는 안내
4. 인덱스 저장 위치 확인
   - cs_index는 PC 로컬 디스크만 허용
5. 최초 색인 시작
6. 선택 설정:
   - Runtime API Settings는 선택 사항
   - Agent Setup Wizard는 개발·배치 보조용 안내
```

금지:

```text
- `webkitdirectory`로 원본 폴더 절대경로를 얻을 수 있다고 가정하기
- 사용자가 선택한 파일 업로드를 원본 루트 설정으로 오해하게 만들기
- 첫 실행에서 API key 입력을 필수로 만들기
```

## 3. 메인 검색 화면

구성:

```text
[상단 상태 배너]
현재 코퍼스: pilot_001 · 237개 문서 · 마지막 색인 2026-07-08 19:40

[자연어 검색창]
예: earnout 조항이 있는 SPA 10개 보여줘

[검색 버튼] [고급 필터]

[필터 칩]
[SPA x] [영문 x] [Draft 제외 x] [중복 대표본만 x] [확장: 보통 x]
```

고급 필터:

```text
- 계약 유형: 전체 + catalog의 DISTINCT ctype 값
  예: SPA / SHA / SSA / ATA/BTA / CB인수 / BW인수 / EB인수 / 분할합병 / 분할계획서 / 주식교환 / JVA / 공동투자 / MOU / 기타샘플 / 미분류
- 언어: 전체 + catalog의 DISTINCT lang 값
  예: 국문 / 영문 / 국영문 / 미상
- Draft: 포함 / 제외
- 중복본: 대표본만 / 중복본 펼치기
- 검색 범위: 정확하게 / 보통 / 넓게
- 코퍼스: 전체 / 특정 batch / 파일럿만
```

필터 옵션 생성 원칙:

```text
- ctype/lang 옵션은 UI 코드에 하드코딩하지 않는다.
- 백엔드는 GET /api/catalog/facets 또는 동등한 read-only API로 현재 catalog의 ctype/lang/batch 후보와 건수를 반환한다.
- type_rules.yaml이 보강되거나 manual_overrides.yaml이 적용되어도 UI 코드를 수정하지 않아야 한다.
- 화면 표시명은 catalog 값 그대로를 기본으로 하며, 별도 alias가 필요하면 서버가 label/value를 함께 내려준다.
- `bilingual` 같은 UI 전용 값은 만들지 않고 데이터 값 `국영문`을 사용한다.
```

UI 문구와 CLI 매핑:

```text
정확하게 → --expand strict
보통 → --expand normal
넓게 → --expand broad
Draft 제외 → --exclude-drafts
중복본 펼치기 → --show-duplicates
```

기본값은 `보통`, `Draft 포함`, `중복 대표본만`이다. 단, 사용자가 Draft 제외를 켜면 이후 세션에서 기억해도 된다.

검색 상태 URL 반영:

```text
- query, filters, expand_mode, corpus_scope, selected_para, page/offset은 URL query parameter에 반영한다.
- 새로고침·뒤로가기·공유 URL·최근 검색의 [필터까지 복원]이 같은 상태를 복원해야 한다.
- URL에 저장하면 안 되는 값: API key, 로컬 절대경로, 원문 내용, 사용자 메모 전문.
```

검색창 입력 처리:

```text
- Enter 검색 실행 시 `event.isComposing === true` 또는 `event.keyCode === 229`이면 검색을 실행하지 않는다.
- 검색창에 포커스가 있을 때는 j/k 같은 전역 단축키를 비활성화한다.
- 동일 Enter 이벤트에서 검색이 두 번 실행되지 않도록 keydown/submit 처리 경로를 하나로 수렴한다.
```

## 4. 검색 결과 카드

각 결과 카드는 최소 다음 정보를 보여준다.

```text
[SPA] Share Purchase Agreement_Final_2021.docx
영문 · Final · Draft 아님 · 중복 3건 중 대표본

왜 검색됐나
- 원질의 "earnout" 직접 매칭
- 변이 "earn-out" 확장 매칭
- SPA 유형 필터 일치

매칭 위치
[¶42] Seller shall pay an earnout amount...
[¶43] The earnout shall be calculated...

[문단 주변 보기] [중복본 보기] [비교 목록에 추가] [즐겨찾기] [파일 정보]
```

결과 카드 배지:

```text
정확 매칭 / 동의어 매칭 / 넓은 확장 매칭 / Draft / 중복 대표본 / 파일럿 코퍼스
```

`broad` 확장 결과는 오탐 가능성이 있으므로 “넓은 확장 매칭” 배지를 반드시 표시한다.

결과 요약줄과 warnings:

```text
결과 37건 · 대표본 21건 · 전체 파일 48건 · Draft 8건 · 추출 실패 제외 3건
[주의] 2글자 검색어는 폴백 검색으로 처리됨: 합병
```

- search JSON의 `warnings`를 숨기지 않는다.
- `short_term_fallback:<term>`은 “2글자/3자 미만 검색어는 폴백 검색으로 처리됨(동의어 확장 또는 랭킹이 일부 달라질 수 있음)” 배지로 표시한다.
- `unsearchable_docs:N`은 “추출 실패/빈 문서 N건은 검색 대상에서 제외됨”으로 표시한다.
- 경고는 오류가 아니라 결과 해석을 돕는 정보로 표시한다.

## 5. 문단 주변 보기

기본 원문 뷰어는 전체 문서가 아니라 매칭 문단 주변을 보여준다.

```text
[¶39] ...
[¶40] ...
[¶41] ...
[¶42] Seller shall pay an [[earnout]] amount...
[¶43] ...
[¶44] ...

[앞 문단 더 보기] [뒤 문단 더 보기] [전체 txt 보기] [원본 파일 경로 복사]
```

요구사항:

- 매칭어 하이라이트
- 직접 매칭과 동의어 매칭 구분
- 문단번호 복사 가능
- 원본 파일 전체 열람은 후순위

하이라이트 안전 규칙:

```text
- 검색·색인은 normalize() 적용 텍스트 기준이지만 화면 스니펫은 원문 표면형이다.
- UI는 matched_terms의 term/canonical/variant 후보를 기준으로 원문 표면형에서 가능한 문자열을 찾는다.
- 전각/반각, 하이픈류, 따옴표류 차이로 표면형 매칭이 실패할 수 있다.
- 하이라이트 실패는 검색 오류가 아니다. 이 경우 하이라이트 없이 원문 스니펫과 ¶번호를 정상 표시한다.
- 하이라이트를 위해 원문 문자열을 변형하거나 ¶번호를 바꾸지 않는다.
```

## 6. 검색 히스토리와 저장된 검색

현재 `query_log.jsonl`은 운영 로그다. UI에는 별도 검색 히스토리를 제공한다.

### 6.1 최근 검색

사이드바 또는 드롭다운:

```text
최근 검색
- earnout 있는 SPA 10개
- drag/tag 조항 있는 SHA
- indemnity cap 10% 이하
```

각 항목 기능:

```text
[다시 검색] [필터까지 복원] [저장된 검색으로 등록] [삭제] [메모]
```

### 6.2 저장된 검색

```text
저장된 검색
- SPA 핵심 조항
- SHA 권리 조항
- 투자계약 선행조건
```

저장된 검색은 이름, query, filters, expand_mode, created_at, last_run_at을 가진다.

## 7. 리서치 세션

MVP 필수는 아니지만 실무 효용이 큰 기능이다.

```text
리서치 세션: Earnout 조항 샘플 리서치
- 검색 내역
- 선택한 문서/문단
- 메모
- 비교 목록
- 내보낸 결과
```

사용자는 한 세션 안에서 여러 검색을 반복하고, 후보 문단을 모아 비교할 수 있어야 한다.

## 8. 비교 목록

검색 결과 카드의 `[비교 목록에 추가]` 버튼으로 문단을 모은다.

```text
선택한 문서 4개
[비교 보기] [Markdown 복사] [CSV 내보내기] [비우기]
```

비교 화면:

```text
| 문서 | 유형 | 언어 | 위치 | Draft | 중복 | 스니펫 |
|---|---|---|---|---|---|---|
| SPA A | SPA | 영문 | ¶42 | 아니오 | 대표 | ... |
```

초기 MVP에서는 AI 비교 요약 없이도, 선택 문단을 나란히 모아보는 기능만 구현한다.

비교 목록 영속성:

```text
- MVP에서도 비교 목록은 메모리 상태만으로 두지 않는다.
- `ui_state.sqlite`에 이름 없는 기본 비교 목록(default compare list)을 저장한다.
- 새로고침 후에도 선택 문단이 유지되어야 한다.
- 저장 구현을 미루는 경우 최소한 페이지 이탈/새로고침 전에 “비교 목록이 사라질 수 있음” 경고를 표시한다. 단, 권장안은 영속 저장이다.
```

## 9. 북마크·메모·피드백

검색 품질 개선과 재사용을 위해 다음 기능을 둔다.

```text
[즐겨찾기]
[메모 추가]
[유용함]
[관련 없음]
[조항은 맞지만 유형이 틀림]
[Draft라 제외하고 싶음]
```

피드백은 `term_dict.yaml`, `type_rules.yaml`, golden query 보강에 사용한다.

## 10. 색인 상태/오류 대시보드

관리 화면에는 다음 정보를 표시한다.

```text
색인 상태
- 전체 파일 수
- status=ok
- empty
- error
- unsupported
- encrypted_pdf
- pdf_text_empty
- 미분류
- 중복 그룹 수
- batch별 문서 수
```

진행률 갱신 방식:

```text
- MVP는 SSE/WebSocket을 쓰지 않고 1~2초 간격 폴링을 사용한다.
- 폴링 대상: GET /api/jobs/{job_id}
- 표시 필드: status, progress_done, progress_total, current_item, started_at, finished_at, error_code
- 예: 423 / 1,204 files · 현재 파일: 05_SHA/example.docx
- SSE/WebSocket은 v2 이후 최적화로 둔다.
```

실패 파일 목록:

```text
| 파일 | 원인 | 조치 |
|---|---|---|
| sample.pdf | pdf_text_empty | 스캔 PDF일 수 있음. OCR 필요 |
| old.doc | unsupported_ext | docx로 변환 필요 |
| locked.pdf | encrypted_pdf | 암호 해제 필요 |
```

## 11. 수동 보정 UI

초기에는 `manual_overrides.yaml`을 직접 수정한다. UI v2에서는 다음 버튼을 제공한다.

```text
[유형 수정]
[언어 수정]
[Draft 아님으로 표시]
[이 파일 제외]
```

UI에서 바로 YAML을 수정하지 못하는 경우에도, 최소한 “수동 보정 후보”를 export한다.

## 12. 빈 결과 화면

검색 결과가 0건일 때 제안한다.

```text
검색 결과가 없습니다.

시도해볼 수 있는 방법:
- Draft 포함하기
- 검색 범위를 “넓게”로 변경
- 계약 유형 필터 해제
- 동의어로 검색: earnout / earn-out / contingent consideration
- 본문 추출 실패 문서가 있는지 확인
```

## 13. 내보내기

지원 포맷:

```text
[Markdown 복사]
[CSV 다운로드]
[리서치 메모 형식]
[계약서 샘플 목록 형식]
```

CSV 인코딩:

```text
- CSV 다운로드는 반드시 UTF-8 with BOM(`utf-8-sig`)으로 생성한다.
- 한국어 Windows Excel에서 BOM 없는 UTF-8 CSV가 cp949로 오인되어 깨지는 것을 방지한다.
- CSV에는 query, filters, export_created_at, file_key, filename, ctype, lang, para, snippet, why를 포함한다.
```

Markdown 예:

```text
## Earnout 조항 샘플

1. Share Purchase Agreement_Final_2021.docx
- 유형: SPA
- 언어: 영문
- 위치: ¶42
- 검색 사유: earnout 직접 매칭
- 스니펫: ...
```

## 14. AI 답변 화면

AI 답변은 검색 결과 탭보다 후순위다.

탭 구조:

```text
탭 1: 검색 결과
탭 2: 후보 문단 모아보기
탭 3: AI 요약 / 답변
```

버튼:

```text
[선택한 결과로 답변 생성]
[선택한 문단 비교 요약]
[선택한 조항을 표로 정리]
```

AI 답변 금지 원칙:

- 검색 결과에 없는 내용은 답하지 않는다.
- “일반적으로”라고 단정하지 않는다.
- 반드시 file_key와 ¶번호를 인용한다.
- 파일럿 코퍼스 기준이면 이를 답변 상단에 표시한다.

AI 버튼 disabled 원인 구분:

```text
- key 없음: “Anthropic API key 필요” + 설정 > API 예산 및 키 링크
- 예산 미설정: “예산 상한 필요” + 설정 > API 예산 및 키 링크
- key와 예산 모두 없음: “API key와 예산 상한 필요”
- 선택 문단 없음: “요약할 문단을 먼저 선택”
- 파일럿 코퍼스: disabled 사유는 아니지만 “파일럿 기준” 경고 표시
```

enabled/disabled 이진 상태만 표시하지 말고, 사용자가 바로 조치할 수 있는 원인 문구를 버튼 옆 배지로 표시한다.


## 15. Agent Setup Wizard

웹앱에는 `설정 > AI 코딩 에이전트` 화면을 둔다. 이 화면은 Claude Code/Codex를 대신 로그인시키는 기능이 아니라, **설치·로그인 상태를 진단하고 사용자가 직접 실행할 절차를 안내하는 관리자용 도우미**다.

화면 구성:

```text
[AI 코딩 에이전트 상태]
Claude Code    설치됨/미설치/로그인 필요/사용 가능/오류
Codex CLI      설치됨/미설치/로그인 필요/사용 가능/오류
Node.js/npm    설치됨/미설치/버전 불충분
Git            설치됨/미설치
Project path   쓰기 가능/쓰기 불가
Sandbox        정상/의심/오류

[권장 조치]
1. Claude Code가 미설치이면 OS별 설치 명령을 표시한다.
2. Claude Code 로그인이 필요하면 터미널에서 `claude` 실행 및 `/login` 절차를 안내한다.
3. Codex가 미설치이면 VS Code 확장 또는 CLI 설치 절차를 표시한다.
4. Codex 로그인은 ChatGPT 구독계정 기반 CLI/VS Code 로그인으로 처리한다.
5. 설치·로그인 후 [다시 검사] 버튼으로 상태를 갱신한다.
```

보안 원칙:

```text
- Agent Setup Wizard는 Claude/ChatGPT 비밀번호, OAuth 토큰, 세션 토큰, 로그인 코드를 받지 않는다.
- Codex 사용을 위해 OpenAI API key 입력란을 만들지 않는다. Codex는 API key를 가져오지 않는 구조다.
- API key가 필요한 Phase 1B/G2 기능은 별도 Runtime API Settings 화면으로 분리하고, Agent Setup Wizard와 결합하지 않는다.
- 초기 MVP에서는 설치 명령 자동 실행을 제공하지 않고, 복사 가능한 명령어와 다시 검사 버튼만 제공한다.
```

### 15.1 Runtime API Settings

Haiku가 소환되는 경로는 Claude Code/Codex 로그인과 별개다. `answer_quick.py`(G1.5), A10 분류 폴백, A9 교차검증, G2 답변은 웹앱 백엔드 또는 CLI가 Anthropic API를 직접 호출하므로, API 기능을 켜려면 사용자가 Anthropic API key를 제공해야 한다.

화면 구성:

```text
설정 > API 예산 및 키

[Anthropic API]
상태: 미설정 / 설정됨 / 검증 실패 / 오류
Key 입력창: ANTHROPIC_API_KEY
- input type=password
- placeholder: sk-ant-...
- 저장 후에는 전체 키를 다시 표시하지 않고 마지막 4자리만 표시
- [저장] [연결 테스트] [삭제/교체] 버튼 제공
저장 방식: 서버 로컬 secret 또는 서버 .env 갱신. 프론트엔드 localStorage/sessionStorage에는 저장 금지

[예산]
per_call_limit_usd 입력창
per_run_limit_usd 입력창
- 둘 중 하나라도 비어 있거나 null이면 API 호출 disabled

[사용 가능 기능]
G1.5 Haiku 즉답: enabled/disabled
A10 Haiku 분류 폴백: enabled/disabled
A9 Sonnet 교차검증: enabled/disabled
G2 답변: enabled/disabled
```

원칙:

```text
- Runtime API Settings에는 `ANTHROPIC_API_KEY` 입력창을 만든다. 사용자는 이 UI에서 키를 입력·저장·삭제·교체할 수 있어야 한다.
- API key가 없으면 G1.5/A9/A10/G2는 `disabled: missing_key`로 표시한다.
- api_budget.yaml 상한이 null이면 API key가 있어도 `disabled: budget_not_set`으로 표시하고 호출하지 않는다.
- 둘 다 없으면 `disabled: missing_key_and_budget`으로 표시한다.
- 모든 호출은 lib/budget.py를 통과한다.
- 호출 전 예상 비용과 대상 건수를 표시하고 사용자 확인 후 실행한다.
- API key는 서버 측 secret으로만 저장하고, 로그·응답·프론트엔드 저장소에 노출하지 않는다.
- Codex 사용을 위해 OpenAI API key를 받지 않는다.
```

설치 명령 자동 실행은 v2 이후 선택 기능으로만 검토한다. 구현 시 관리자 인증, 명령 allowlist, 실행 전 확인, 실행 로그, 임의 shell 입력 금지를 필수로 한다.

### 15.2 PC Backend Foundation

웹앱의 기본 실행 환경은 Windows PC 로컬이다. 백엔드는 다음 조건을 만족해야 한다.

```text
- 기본 바인딩: 127.0.0.1
- cs_index: PC 로컬 디스크만 허용
- 원본 폴더: PC 로컬 또는 읽기 전용 네트워크 드라이브 가능
- 색인/평가/API 답변: job queue로 실행
- SQLite writer: 단일 worker만 허용
- 파일 열기: file_key 기반 catalog 조회만 허용
- API key: 프론트엔드 저장소 저장 금지
- Agent 진단: subprocess allowlist + shell=False + timeout
- raw exception: 사용자 화면 노출 금지
```

설정/시크릿/로그 저장 위치, 오류 코드, 백엔드 API 경계는 `BACKEND_REVIEW_PC.md`를 따른다.

## 16. UI MVP / v2 / v3 범위

### UI MVP

```text
- 검색창
- 고급 필터
- 필터 칩
- 결과 카드
- 문단 주변 보기
- 중복본 보기
- 코퍼스 상태 배너
- 최근 검색
- Markdown/CSV 내보내기
- URL 기반 검색 상태 복원
- 관리자용 Agent Setup Wizard 상태 진단/절차 안내
- Runtime API Settings disabled 사유 배지
- 진행률 aria-live 알림과 검색창 IME 보호
```

### UI v2

```text
- 저장된 검색
- 비교 목록
- 즐겨찾기/메모
- 결과 피드백
- 색인 상태/오류 대시보드
- 수동 보정 후보 export
- Agent Setup Wizard 자동 설치 옵션 검토(관리자 인증/allowlist 전제)
```

### UI v3

```text
- 리서치 세션
- 선택 결과 기반 AI 요약
- 조항 비교표 생성
- 자연어 질의 라우팅
- 통계형 질의
- API 예산 표시
```

## 17. 후순위

- 모바일 최적화는 후순위. 데스크톱 넓은 화면을 우선한다.
- 벡터DB, 파일 감시, OCR, full-text 원본 렌더링은 Phase 2 이후다.
- AI가 자동으로 모든 검색 결과를 요약하는 기능은 UI v3 이후다.

## 18. PC 로컬 앱 UI 보강 사항

상세 검토는 `UI_REVIEW_PC.md`를 따른다. 기본 환경은 Windows PC 로컬 실행이며, NAS/서버형 운영 UI를 기본값으로 두지 않는다.

MVP에서 추가로 반영할 사항:

```text
- 첫 실행 온보딩: 원본 폴더 선택 → 인덱스 저장 위치 확인 → 최초 색인 → 선택 기능 설정
- 검색 결과 상단 요약: 총 결과, 대표본 수, Draft 수, 추출 실패로 제외된 문서 수
- split view 문단 주변 보기: 결과 목록과 문단 내용을 나란히 표시
- 색인 작업 진행률: running/failed/completed, 현재 파일, 실패 파일 재시도, 취소
- Runtime API Settings: ANTHROPIC_API_KEY 입력, 마지막 4자리 표시, 연결 테스트, 삭제/교체, 예산 null이면 disabled
- Agent Setup Wizard: Runtime API Settings와 분리, Codex는 OpenAI API key 입력 없이 구독 로그인 기반으로만 안내
- 로컬 데이터 관리: 인덱스/캐시/로그 위치 표시 및 삭제 버튼
- 고급 필터: catalog facets에서 동적 생성하고 UI 하드코딩 금지
- CSV 다운로드: utf-8-sig(BOM)로 생성
- 매칭어 하이라이트 실패 시 하이라이트 없이 원문 표시
- 비교 목록: ui_state.sqlite 기본 비교 목록에 영속 저장
- 접근성: 진행률/검색 완료 aria-live, split view 포커스 이동, 검색창 포커스 중 j/k 비활성화
```

PC 로컬 앱 보안 UX:

```text
- 기본 접속 주소는 127.0.0.1로 표시한다.
- 원본 계약서 폴더는 읽기 전용으로 다룬다고 표시한다.
- API key 저장 위치와 삭제 방법을 설정 화면에 표시한다.
- LAN 공개/0.0.0.0 바인딩은 고급 설정으로 숨기고 경고를 붙인다.
```

검색 화면 권장 레이아웃:

```text
[코퍼스 상태 배너] [API 상태 배지] [색인 최신성 배지]
[자연어 검색창.............................................] [검색]
[고급 필터] [최근 검색] [저장된 검색]
[필터 칩 영역]
[결과 요약: 37건 · 대표본 21건 · Draft 8건 · 추출 실패 제외 3건]
[결과 카드 목록]        [오른쪽: 선택 문단/비교 목록 패널]
```

빈 상태/부분 성공 상태도 별도 화면으로 구현한다. 검색 결과가 없을 때는 필터 해제, 검색 범위 확장, 추출 실패 문서 확인을 제안한다. 색인이 일부 실패한 상태에서는 검색은 가능하되 실패 파일의 내용은 결과에 포함되지 않는다고 명확히 표시한다.



## 19. 2026-07-09 Frontend Hardening Checklist

아래 항목은 UI 구현 착수 전에 테스트 또는 스모크 확인 항목으로 둔다.

```text
- 필터 옵션은 catalog facets에서 동적으로 로드된다.
- 원본 폴더는 경로 텍스트 입력 + POST /api/settings/root-path/validate로 검증된다.
- 한글 IME 조합 중 Enter는 검색을 실행하지 않는다.
- CSV 다운로드는 utf-8-sig(BOM)로 생성된다.
- normalize() 기준 매칭과 원문 표면형 불일치 시 하이라이트 없이 정상 표시된다.
- job 진행률은 GET /api/jobs/{job_id} 1~2초 폴링으로 갱신된다.
- search warnings는 결과 요약줄 배지로 표시된다.
- AI disabled 상태는 missing_key / budget_not_set / missing_key_and_budget / no_selection으로 구분된다.
- 비교 목록은 ui_state.sqlite의 기본 비교 목록에 저장된다.
- query, filters, expand_mode는 URL query parameter로 복원된다.
- UI-0에서 DESIGN_AUDIT.md와 함께 STACK_DECISION.md를 작성한다.
- 진행률·검색 완료는 aria-live로 알리고, split view 포커스 이동 규칙을 구현한다.
```
