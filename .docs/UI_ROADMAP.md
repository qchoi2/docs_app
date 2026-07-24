# UI_ROADMAP — 웹 UI 단계별 구현 순서
_2026-07-08 · CLI 검색 MVP 이후 UI를 붙일 때의 단계별 로드맵._

## UI-0 — 디자인 인수

목표: getdesign.md 기반 디자인 자산 확인.

산출물:

```text
- DESIGN_AUDIT.md
- STACK_DECISION.md
- UI 구현에 사용할 색상/폰트/간격/컴포넌트 목록
```

`STACK_DECISION.md`에는 서버 렌더링+경량 JS(htmx/vanilla)와 SPA(React+Vite 등)를 비교하고, 개인 Windows PC 로컬 단일 사용자 앱이라는 배포 조건에서 어떤 스택을 선택했는지 명시한다. getdesign.md 자산이 컴포넌트 코드인지, 토큰/스크린샷인지에 따라 판단하되 코딩 에이전트가 임의로 무거운 SPA를 선택하지 못하게 한다.

명령 예:

```text
getdesign.md를 읽고 DESIGN_INTEGRATION.md 절차에 따라 DESIGN_AUDIT.md를 작성하라.
아직 UI 코드는 만들지 말고, 사용 가능한 디자인 자산과 부족한 항목만 정리하라.
```


## UI-0.2 — PC 로컬 첫 실행 온보딩

목표: 사용자가 원본 폴더, 인덱스 저장 위치, 최초 색인, 선택 기능 설정을 한 번에 이해하게 한다.

필수 기능:

```text
- 원본 계약서 루트 경로 텍스트 입력 + 백엔드 검증(`POST /api/settings/root-path/validate`)
- 인덱스/캐시/로그 저장 위치 표시
- 최초 색인 시작
- API key/예산은 선택 설정으로 안내
- Claude Code/Codex는 개발·배치 보조용임을 표시
```

금지:

```text
- 첫 실행에서 API key 입력을 필수로 만들기
- 원본 폴더를 수정하는 것처럼 보이는 문구
- NAS/서버 배포를 기본 경로로 안내
```

## UI-0.3 — 작업 진행률/상태 UX

목표: 색인·재색인·AI 답변 생성 같은 장시간 작업을 안전하게 표시한다.

필수 기능:

```text
- job 상태: idle/running/failed/completed
- 진행률과 현재 파일
- MVP 갱신 방식: `GET /api/jobs/{id}` 1~2초 폴링
- 취소/실패 파일만 재시도
- raw traceback 대신 표준 오류 메시지
- 진행률/완료/실패 알림은 aria-live에 반영
```

## UI-1 — 읽기 전용 검색 UI

목표: CLI 검색 기능을 웹에서 사용할 수 있게 한다.

필수 기능:

```text
- 자연어 검색창
- catalog facets 기반 고급 필터(ctype/lang 하드코딩 금지)
- 필터 칩
- URL query parameter로 query/filters/expand_mode 복원
- 한글 IME composition 중 Enter 검색 방지
- 코퍼스 상태 배너
- 결과 카드
- 문단 주변 보기
- 중복본 보기
- 최근 검색
- Markdown/CSV 내보내기(CSV는 utf-8-sig)
- search warnings 배지(`short_term_fallback`, `unsearchable_docs` 등)
- 매칭어 하이라이트 실패 시 원문 표시 폴백
```

금지:

```text
- AI 요약 자동 생성
- 원본 파일 수정
- 색인 자동 실행
```

## UI-2 — 운영 UI

목표: 파일럿/전체 운영 상태를 사용자가 이해하고 보정할 수 있게 한다.

필수 기능:

```text
- 색인 상태 대시보드
- 실패 파일 목록
- batch별 통계
- saved searches
- result feedback
- manual_overrides 후보 export
```

## UI-3 — 리서치 UI

목표: 검색 결과를 실무 리서치 자료로 모으고 재사용하게 한다.

필수 기능:

```text
- ui_state.sqlite에 영속 저장되는 기본 비교 목록
- 북마크/메모
- 리서치 세션
- 선택 문단 Markdown/CSV export
```

## UI-4 — AI 보조

목표: 선택한 검색 결과만 근거로 짧은 요약/비교표를 생성한다.

필수 기능:

```text
- 선택 결과 기반 요약
- 선택 문단 비교표
- file_key/¶번호 인용
- API 예산 표시
- agent_log 기록
```

금지:

```text
- 검색 결과에 없는 일반론 생성
- 파일럿 결과를 전체 경향처럼 표현
- 근거 없는 조항 비교
```

## UI-5 — V4 taxonomy 관리 화면

목표: v4 세부 분류(진술보장·선행조건·확약 원자 항목)의 신규 분류 후보를 소유자가
**버튼 클릭만으로** 승격·병합·반려할 수 있게 한다. 소유자가 이후 개발을 이어가지
않아도 taxonomy 운영이 가능해야 한다. 상세 계약은 `V4_PLAN.md` §5를 따른다.

필수 기능:

```text
- 후보 목록: 제안 이름, 추천 상위 노드, 원문 근거(verbatim + file_key/¶), 발견 문서 수
- 행 단위 버튼: [정식 분류로 승격] / [기존 분류의 alias로 병합] / [반려]
- 승격/병합 확정 전 영향받는 item·문서 수 미리보기
- 승격 시 taxonomy_version 자동 증가, 관련 item 자동 재지정
- 분류체계 트리 보기 + deprecated 처리(삭제 금지) + yaml 내보내기
- [회귀 확인 실행] — 골든 질의 eval을 기존 job queue로 실행, 악화 시 배너 경고
```

금지:

```text
- yaml 손편집이나 SQL 실행을 전제로 하는 흐름
- 후보를 자동으로 정식 분류에 편입
- 승격/병합 이력 미기록
```

시점: V4-3(60건 파일럿) 후보 축적과 병행 개발 가능. V4-6 전량 확장 전 완성 필수.

## MCP 병행 트랙 — UI와 독립

MCP는 UI-4의 대체 단계가 아니라 웹앱과 같은 검색 코어를 공유하는 별도 인터페이스다.

### T4 검색 UX·성능 계약

T4가 연결된 뒤에도 UI-0~UI-3의 기본 검색은 로컬 임베딩 모델 준비 여부와 무관하게
즉시 동작해야 한다.

- 기본 검색(T1/T2/T3/V4)을 먼저 표시하고 T4·rerank 결과는 후속 갱신한다.
  후속 갱신 구현이 복잡하면 `[빠른 검색]`과 `[정밀 의미검색]`을 명시적으로 분리한다.
- 정확한 메타·수치·taxonomy 질의에는 T4를 자동 실행하지 않는다. 의미 유사성 질의,
  결과 희소 또는 낮은 신뢰도일 때만 실행하고 사용자가 수동으로 켤 수 있게 한다.
- 모델은 서버 시작 시 1회 로드해 상주시킨다. 준비 중·사용 가능·fallback 상태와
  cold start를 UI 및 health API에 표시한다.
- reranker는 시간 예산을 넘으면 생략하고 기본/RRF 결과를 유지한다. T4 오류나
  timeout 때문에 이미 나온 검색 결과를 숨기거나 실패 처리하지 않는다.
- 검색 상태에 base/vector/rerank 경로, 처리 시간, fallback 여부를 간결한 배지로 표시한다.
- warm 상태 목표는 기본 검색 p95 0.5초 이하, 벡터 포함 p95 2초 이하,
  rerank 포함 p95 5초 이하이며 8초에서 hard timeout한다. 실제 대상 PC 측정으로 확정한다.
- 외부 API나 MCP AI는 최종 후보의 설명·답변 생성 경로이며, 로컬 벡터 검색의
  질문 임베딩 모델을 대체하지 않는다.
상세 계약은 `MCP_INTEGRATION.md`를 따른다.

```text
MCP-1  로컬 stdio read-only 7개 도구                         ✅ 구현
MCP-2  실제 AI 클라이언트 연결·검색·조항 정독·인용 스모크      다음
MCP-3  선택적 Sampling(capability+사용자 승인)                 보류
MCP-4  원격 MCP/OAuth/조직 배포                                범위 밖
```

- MCP-1은 UI-1 검색 코어가 안정되면 병행 가능하다.
- MCP가 없어도 UI-0~UI-4는 동작해야 한다.
- UI-4 웹앱 내부 답변은 직접 API 경로, MCP 답변은 AI 클라이언트 경로로 구분한다.
- 웹앱 도움말은 설치·`--check`·클라이언트 설정 복사 안내만 제공하며 토큰을 받지 않는다.

## 구현 우선순위

1. UI-0
2. UI-0.2
3. UI-0.3
4. UI-1
5. UI-2
6. UI-3
7. UI-4
8. UI-5 (V4 진행 시 — V4-3와 병행 가능, V4-6 전 완성 필수)

병행: UI-1 안정화 후 MCP-1 → MCP-2. MCP-3은 실제 클라이언트 지원 확인 후에만 진행한다.

CLI 검색 품질이 안정되기 전에는 UI-4로 가지 않는다.


## 2026-07-09 UI Hardening 반영사항

```text
- 필터 옵션은 catalog DISTINCT ctype/lang/batch에서 동적으로 생성한다.
- 브라우저 폴더 피커 절대경로 취득에 의존하지 않고, 경로 입력 + 백엔드 검증을 사용한다.
- 검색창은 한글 IME composition Enter를 무시한다.
- CSV export는 utf-8-sig로 생성한다.
- normalize() 기준 검색과 원문 표면형 하이라이트 불일치 시 하이라이트 없이 표시한다.
- job 진행률은 MVP에서 폴링으로 구현하고 SSE/WebSocket은 v2로 미룬다.
- warnings는 결과 요약줄 배지로 표시한다.
- AI disabled 상태는 원인별 문구와 설정 링크를 제공한다.
- 비교 목록은 MVP에서도 새로고침에 보존한다.
- 검색 상태는 URL에 반영한다.
- UI-0 산출물에 STACK_DECISION.md를 포함한다.
- 접근성: aria-live, split view 포커스 이동, 검색창 포커스 중 j/k 비활성화.
```
