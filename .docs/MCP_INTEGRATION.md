# MCP_INTEGRATION — 웹앱 병행 MCP 사용 기획

_2026-07-16 · 현재 웹앱을 유지하면서 동일한 계약 검색 코어를 AI 클라이언트에서도 사용하는 확정 방향._

## 1. 결정 요약

- 웹앱을 대체하지 않는다. 웹앱과 MCP는 같은 `catalog.sqlite`, `term_dict`, 검색·부분 읽기 코어를 공유하는 두 개의 어댑터다.
- 웹앱은 색인, 설정, 작업 진행률, 저장 검색, 비교 목록, 리서치 세션, 내보내기 등 운영·수동 검수 UX를 담당한다.
- MCP는 AI 클라이언트가 계약 검색, 조항 부분 정독, 비교 답변을 수행하도록 하는 로컬 읽기 전용 인터페이스다.
- 1차 전송 방식은 PC 로컬 `stdio`만 사용한다. 원격 Streamable HTTP와 OAuth는 범위 밖이다.
- MCP 사용 시 최종 답변은 연결된 AI 클라이언트가 작성하는 것이 기본이다. 이 경로에는 프로그램의 별도 답변 API key가 필요하지 않다.
- 직접 Anthropic API 경로는 웹앱 단독 AI 답변, 무인 배치, 고정 모델 평가를 위한 선택적 폴백으로 유지한다.
- MCP Sampling은 클라이언트가 해당 capability를 선언한 경우에만 쓰는 후속 선택 기능이다. 1차 어댑터의 필수 조건이 아니다.

## 2. 아키텍처 경계

```text
계약 검색 코어
├─ index_contracts.py
├─ search_contracts.py
├─ read_contract.py / open_text.py
├─ inspect_file.py
├─ term_dict / catalog.sqlite / doc_meta
│
├─ webapp.py
│  ├─ 검색·수동 탐색
│  ├─ 색인 job queue와 진행률
│  ├─ 설정·시크릿
│  └─ 저장 검색·비교·리서치 상태
│
└─ mcp_server.py
   ├─ 로컬 stdio
   ├─ 코퍼스 읽기 전용 도구
   ├─ file_key·근거 문단 반환
   └─ 최종 답변은 AI 클라이언트가 생성
```

어댑터가 서로를 호출하지 않는다. `mcp_server.py`가 `webapp.py`의 HTTP API를 호출하거나,
웹앱이 MCP 프로토콜을 내부 API처럼 사용하지 않는다. 양쪽 모두 공통 Python 코어를 직접 호출한다.

## 3. MCP 1차 도구 계약

| 도구 | 역할 | 코퍼스 변경 |
|---|---|---|
| `search_contracts` | 키워드 AND, term_dict 확장, 유형·언어·조항 필터, 중복 제거 검색 | 없음(운영 query log 제외) |
| `read_contract_clause` | doc_meta 좌표 기반 조항 부분 정독 | 없음 |
| `open_contract_context` | ¶번호 또는 용어 기준 작은 문단 창 읽기 | 없음 |
| `inspect_contract` | 분류·상태·Draft·중복·doc_meta freshness 점검 | 없음 |
| `list_contract_duplicates` | 같은 dup_group의 버전·중복 문서 확인 | 없음 |
| `get_corpus_status` | 검색 가능/불가 건수, batch, 마지막 색인 상태 | 없음 |
| `get_corpus_facets` | ctype/lang/batch 필터 값과 건수 | 없음 |

1차 MCP에는 다음 도구를 넣지 않는다.

- 색인 시작·취소
- API key 또는 예산 설정
- manual override 수정
- 저장 검색·북마크·비교 목록·리서치 세션 쓰기
- 원본 파일 열기 또는 임의 로컬 경로 읽기
- 계약서 전체 원문 반환

쓰기 기능이 필요해지면 MCP 프로세스에 두 번째 `JobQueue`를 만들지 않는다. 웹앱의 단일 writer
작업 계층을 중앙화하거나 프로세스 간 원자적 lease를 먼저 설계한 뒤 별도 승인을 받아 추가한다.

## 4. 답변·비용 라우팅

### 4.1 MCP 대화 기본 경로 — 별도 답변 API 없음

```text
사용자 질문
→ AI 클라이언트가 MCP 검색 도구 호출
→ 필요한 후보만 조항/문단 부분 읽기
→ AI 클라이언트의 현재 대화 모델이 답변·표·인용 작성
```

이 경로는 `answer_quick.py`와 G2의 답변 생성 역할을 상당 부분 대체한다. 프로그램은 모델 API를
직접 호출하지 않지만 AI 클라이언트의 구독 사용량, 조직 한도, 속도 제한은 적용된다.

### 4.2 웹앱 단독 경로 — 직접 API 선택 기능

웹앱만 열어 사용하는 경우 AI 클라이언트 세션을 자동으로 빌려 쓸 수 있다고 가정하지 않는다.
웹앱 안에서 AI 답변이 필요하면 기존 `ANTHROPIC_API_KEY` + `api_budget.yaml` 경로를 사용한다.
직접 API 기능은 기본 검색의 필수 조건이 아니며 사용자가 명시적으로 활성화해야 한다.

### 4.3 MCP Sampling — 후속 선택 기능

Sampling은 MCP 서버가 연결된 클라이언트에 별도 모델 생성을 요청하는 기능이다. 적용 조건:

- 초기 capability negotiation에서 클라이언트가 `sampling`을 선언한 경우만 요청한다.
- 미지원 클라이언트에서는 기능을 숨기거나 `unsupported_client_capability`로 종료한다.
- 사용자가 프롬프트와 반환 결과를 검토·거부할 수 있는 흐름을 유지한다.
- 모델 힌트는 강제가 아니다. 재현 평가나 독립 교차검증에서 특정 모델이 필요하면 직접 API를 사용한다.
- 대량 무인 배치의 기본 경로로 사용하지 않는다.
- Sampling 실패 시 자동으로 유료 API로 전환하지 않는다. 직접 API 전환은 별도 사용자 승인 대상이다.

### 4.4 기능별 기본 경로

| 기능 | MCP AI 클라이언트 | 직접 API | 기본 결정 |
|---|---|---|---|
| 검색·부분 정독 | 도구 호출 | 불필요 | 로컬 결정적 코어 |
| 즉답·일반 비교(G1.5/G2) | 현재 대화 모델이 작성 | 웹앱 단독 폴백 | MCP 우선 |
| T3 구조화 추출 | 대화형·소량 가능 | 무인 배치 가능 | 기존 worker-agnostic 파일 흐름 유지 |
| A10 분류 폴백 | Sampling 지원 시 가능 | 고정 배치 가능 | 소량 MCP, 무인은 직접 API/에이전트 배치 |
| A9 독립 교차검증 | 동일 모델이면 독립성 부족 | 모델 고정 가능 | 직접 API 또는 명시적 다른 모델 |
| 골든 평가 | 모델 변동으로 부적합 | 모델 버전 고정 가능 | 결정적 검색 평가 우선, 생성 평가는 별도 |

T3 v3 파일럿부터 MCP 검색은 검증된 v3 데이터에 한해 당사자·역할, 대금·지급 방식,
손해배상 상한, 존속기간, 준거법, 법원·중재기관 구조화 조건을 받을 수 있다.
v2 문서는 조건 불일치로 간주하지 않고 미평가로 분리한다. MCP는 v3 결과를 작성하거나
DB에 저장하지 않으며, 결과 저장은 계속 웹앱/CLI의 단일 enrich 경로가 담당한다.

## 5. 검색 에이전트 불변식

MCP server instructions와 도구 출력은 다음을 강제하거나 명시한다.

1. 모든 사실·수치·조항 내용에 `[file_key]` 인용.
2. `why`, `score_breakdown`, `snippet_paras`, clause evidence 우선 사용.
3. 키워드 미검출은 부재 증명이 아님. `clause_absent=true`의 평가 후 부재만 부재로 사용.
4. 미평가, `present=false`, confidence=low, stale 구분.
5. 중복 제거 기본. 요청 개수가 부족하면 확인된 수만 보고.
6. 후보 30건 초과 시 좁힌 뒤 읽기. 한 답변의 조항 정독은 기본 5건 이하.
7. empty/error 문서 건수 고지.
8. 파일럿이면 현재 색인된 파일럿 코퍼스 기준임을 표시.
9. 법률 자문이 아니라 샘플 검색·요약·비교임을 유지.

프롬프트만으로 보장하지 않는다. 입력 상한, file_key 형식, context 범위, 결과 수 상한,
로컬 경로 제거는 서버 코드에서 검증한다.

## 6. 데이터·보안 원칙

- `cs_index`는 PC 로컬 디스크만 허용한다. UNC/NAS의 SQLite를 열지 않는다.
- 기본 MCP transport는 `stdio`; 포트를 열지 않는다.
- AI 클라이언트 설정에는 Python 실행 파일, `mcp_server.py`, `--out` 절대경로만 넣는다.
- 계약서 원본 경로를 도구 입력으로 받지 않는다. 모든 문서 접근은 16자 hex `file_key`로 catalog를 조회한다.
- MCP 결과에서는 `txt_path` 등 로컬 캐시 절대경로를 제거한다.
- 전체 원문 resource를 목록화하지 않는다. 검색 스니펫과 필요한 조항·문단 창만 반환한다.
- API key, 로그인 토큰, AI 클라이언트 세션 토큰을 MCP 서버가 수집·저장하지 않는다.
- stdio stdout에는 MCP 메시지 외 내용을 출력하지 않는다. 진단 로그는 stderr만 사용한다.
- 원격 MCP가 필요해질 경우 Streamable HTTP, OAuth 2.1, 사용자별 권한, 감사 로그를 별도 설계한다. 로컬 stdio 설정을 그대로 외부에 공개하지 않는다.

## 7. 의존성·호환성

- 기본 웹앱/CLI 설치는 기존 `requirements.txt`만 사용한다.
- MCP는 Python 3.10+ 선택 설치인 `requirements-mcp.txt`로 분리한다.
- 현재 안정화 기준은 `mcp==1.28.1`로 pin한다. 2.x 마이그레이션은 별도 호환성 테스트 후 수행한다.
- `mcp`가 설치되지 않아도 기존 모듈 import, 웹앱, CLI, 기본 테스트는 실패하지 않아야 한다.
- 정상 실행 전 `python mcp_server.py --out <cs_index> --check`로 catalog와 도구 목록을 확인한다.

## 8. 상태·로드맵

### MCP-1 — 읽기 전용 어댑터: 완료

- 7개 read-only 도구
- stdio 실행
- 선택 의존성 분리
- 서버 instructions와 입력 상한
- 로컬 캐시 경로 제거
- 단위·SDK 도구 목록·회귀 테스트

### MCP-2 — 실제 AI 클라이언트 스모크: 다음

- 목표 AI 클라이언트별 등록 절차 검증
- `tools/list`, 검색, 조항 정독, 한국어 인용 답변 확인
- 클라이언트가 server instructions와 structured output을 보존하는지 확인
- 동일 질의를 웹앱과 MCP에서 실행해 file_key·순위·warnings 일치 확인

### MCP-3 — 선택적 Sampling: 보류

- capability detection
- 사용자 승인 UX
- 결과 JSON 스키마 검증
- T3 단건/A10 소량 실험
- 미지원·거부·timeout·취소 처리
- 직접 API 자동 폴백 금지 테스트

### MCP-4 — 원격/조직 배포: 범위 밖

- 사용자가 명시적으로 요구할 때만 별도 기획
- 인증·권한·기밀 데이터 정책·감사·배포 운영을 먼저 확정

## 9. 완료 정의

- [x] 기존 웹앱·CLI가 MCP 미설치 상태에서도 동작한다.
- [x] MCP SDK가 선택 requirements로 분리·pin되어 있다.
- [x] 제공 도구가 모두 read-only annotation을 가진다.
- [x] 검색 결과가 file_key, why, score_breakdown, snippet_paras, warnings를 보존한다.
- [x] 조항 부재와 미평가가 구분된다.
- [x] txt 캐시 절대경로가 MCP 응답에 포함되지 않는다.
- [x] 실제 로컬 `cs_index`의 `--check`가 통과한다.
- [ ] 최소 1개 실제 AI 클라이언트에서 stdio 연결 스모크가 통과한다.
- [ ] MCP 사용 시 직접 API가 호출되지 않았음을 로그/테스트로 확인한다.
- [ ] Sampling을 추가할 경우 지원 capability, 사용자 승인, 미지원 폴백 테스트가 통과한다.
