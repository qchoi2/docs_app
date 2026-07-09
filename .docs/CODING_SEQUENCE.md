# CODING_SEQUENCE — GPT-5.5/Claude Code/Codex 단계별 구현 명령
_2026-07-08 · IMPLEMENTATION_BRIEF.md를 단일 기준으로 삼고, 이 문서는 구현 순서를 강제하는 실행 지침이다._

## 원칙
- `CODING_AGENT_RULES.md`를 모든 Step의 상위 코딩 행동 원칙으로 적용한다.
- 작업 시작 전 Claude Code 설치·로그인 상태를 확인하고, 문제가 있으면 `AGENT_SETUP_AND_MODEL_OPTIONS.md` 절차를 따른다. Codex를 쓸 경우에도 동일한 Step 단위 지침을 적용하되, Codex는 ChatGPT 구독계정 로그인 기반으로 사용하고 OpenAI API key를 가져오지 않는다.
- 전체를 한 번에 구현하지 않는다. 색인 → 검색 → 운영도구 → 평가 → API 보조 순서로 나눈다.
- 각 Step 종료 시 반드시 `pytest` 또는 해당 스모크 테스트를 실행하고, 실행 예시 1개를 남긴다.
- 각 Step 완료 후 테스트가 통과하면 즉시 git commit을 만든다. commit message는 `step-N: <short description>` 또는 `ui-N: <short description>` 형식을 사용한다.
- 테스트 실패 상태에서는 commit하지 않는다. 여러 Step을 하나의 commit에 섞지 않는다.
- DDL·CLI·JSON 스키마는 `IMPLEMENTATION_BRIEF.md`를 따른다. 충돌 시 Brief가 우선한다.
- 유료 API는 호출하지 않는다. Phase 1B는 mock으로만 테스트한다.
- 개선 아이디어는 코드에 임의 반영하지 말고 `NOTES_FOR_OWNER.md`에 남긴다.

## 모든 Step의 공통 진행 루프

각 Step은 아래 순서로 진행한다.

```text
1. git status로 시작 상태 확인
2. 이번 Step의 목표, 수정할 파일, 실행할 테스트를 먼저 적기
3. 해당 Step 범위만 구현
4. py_compile / pytest / 스모크 테스트 실행
5. 실패 시 수정 후 재실행, 그래도 실패하면 commit하지 않고 보고
6. 통과 시 git add로 관련 파일만 stage
7. git diff --cached로 불필요한 변경이 없는지 확인
8. git commit -m "step-N: <short description>"
9. 보고서에 commit hash 또는 commit하지 않은 이유 포함
```

UI 단계는 `ui-N: <short description>` 형식으로 commit한다.



## Preflight — 에이전트 설치·로그인 확인

Step 1에 들어가기 전에 아래를 확인한다.

```text
1. claude --version으로 Claude Code 설치 여부를 확인한다.
2. 미설치이면 AGENT_SETUP_AND_MODEL_OPTIONS.md §2 절차에 따라 설치한다.
3. claude 실행 또는 세션 내 /login으로 로그인 상태를 확인한다.
4. Claude Code가 불가하거나 한도에 도달한 경우, Codex 구독요금제를 선택적으로 사용하되 현재 Step 하나만 맡긴다.
5. Codex 사용 시 OpenAI API key를 입력·저장·요구하지 않는다. VS Code 확장 또는 CLI의 ChatGPT 로그인 흐름을 사용한다.
6. Haiku/Sonnet/Opus API 경로는 Codex/Claude Code 로그인과 별개이며, 실제 런타임 호출에는 사용자의 ANTHROPIC_API_KEY와 api_budget.yaml 상한이 필요함을 확인한다.
6. 어느 에이전트를 쓰든 IMPLEMENTATION_BRIEF.md / CODING_SEQUENCE.md / CODING_AGENT_RULES.md를 먼저 읽고 진행한다.
```

완료 기준:
- Claude Code 또는 Codex 중 실제 작업자가 명확히 정해짐
- 프로젝트 루트에서 `git status` 확인 가능
- 유료 API 실호출 금지 원칙 재확인

## Step 1 — 저장소 골격 만들기
코딩 모델에게 줄 명령:

```text
IMPLEMENTATION_BRIEF.md와 CODING_SEQUENCE.md를 읽고, 저장소 골격만 만들어라.
requirements.txt, lib/ 패키지, data/ 파일 배치, tests/ 디렉토리, README.md 초안을 만든다.
CLAUDE_v2.md는 저장소 루트의 CLAUDE.md로 복사한다. 아직 핵심 로직은 구현하지 마라.
```

완료 기준:
- `python -m py_compile` 대상 파일이 있으면 통과
- `requirements.txt`에 허용 의존성만 있음
- `data/`에 yaml 파일들이 배치됨

## Step 2 — normalize.py
명령:

```text
lib/normalize.py를 구현하고 단위 테스트를 작성하라.
NFC, 전각→반각, 하이픈/따옴표 표준화, 소프트하이픈/제로폭 제거, 공백 정규화를 검증한다.
색인과 검색이 반드시 같은 normalize()를 import하도록 설계하라.
```

완료 기준:
- `pytest tests/test_normalize.py` 통과
- 한글/영문/전각/하이픈 샘플 테스트 포함

## Step 3 — catalog.py와 DDL
명령:

```text
lib/catalog.py를 구현하라.
IMPLEMENTATION_BRIEF.md §2.4 DDL을 그대로 생성하고, SQLite FTS5 trigram 가용성 점검을 구현하라.
trigram 미지원 시 명확한 오류와 pysqlite3-binary 안내를 출력하고 중단하라.
```

완료 기준:
- 임시 DB 생성 테스트 통과
- `files`, `fts`, `doc_meta`, `clause_index` 테이블 존재 확인

## Step 4 — index_contracts.py 1차
명령:

```text
index_contracts.py의 기본 색인을 구현하라.
파일 스캔, file_key/content_hash, docx/pdf 텍스트 추출, ¶ txt 캐시, files/fts 기록까지 구현한다.
DOCX는 문서 등장 순서대로 문단과 표를 처리하고, 각주·머리글·바닥글은 best-effort로 처리한다.
```

완료 기준:
- 합성 docx fixture 3~4개와 텍스트 pdf 1개 색인 성공
- txt 캐시에 `[¶N]\t` 형식이 유지됨
- FTS para와 txt ¶번호가 일치

## Step 5 — index_contracts.py 2차: 증분·파일럿·리포트
명령:

```text
index_contracts.py에 증분 갱신, --full, --include-misc, --batch-label, --file-list, --sample, --sample-seed, --dry-run을 구현하라.
report_YYYYMMDD.md에는 Brief §2.5의 9개 섹션을 모두 출력하라.
--file-list와 --sample이 동시에 주어지면 오류 처리하라.
```

완료 기준:
- 같은 root/out에서 파일 추가 시 신규만 처리
- 이동/삭제(missing)/복원/내용변경 테스트 통과
- `--file-list` 파일럿 후 전체 증분 확장 테스트 통과
- `--sample N --sample-seed`가 결정적 결과를 냄

## Step 6 — search_contracts.py
명령:

```text
search_contracts.py를 구현하라.
FTS5 trigram 검색, term_dict 확장, --expand strict|normal|broad, --no-expand, RRF, dedup 대표 선택, --show-duplicates, --exclude-drafts, JSON 출력, query_log.jsonl 기록을 구현한다.
```

완료 기준:
- `--kw` 반복은 AND로 동작
- 정확질의 랭크가 확장질의보다 우선됨
- JSON에 `why`, `score_breakdown`, `snippet_paras` 포함
- 검색 결과 없음은 exit code 1, 오류는 2

## Step 7 — stats_contracts.py
명령:

```text
stats_contracts.py를 구현하라.
--by ctype, --by ctype,lang, --status, --errors, --batches, --dedup 옵션을 지원한다.
```

완료 기준:
- status=ok 기준 집계와 전체 status 집계가 구분됨
- `--dedup` 시 dup_group 대표 기준으로 집계됨

## Step 8 — 운영 디버깅 도구
명령:

```text
inspect_file.py와 open_text.py를 구현하라.
inspect_file.py는 파일 1건의 분류, 중복, 실패사유, batch_label, source_signals, doc_meta stale 여부를 출력한다.
open_text.py는 --para와 --search 두 모드를 지원하고, 원문 전체 출력 대신 주변 문단만 보여준다.
```

완료 기준:
- 실제 file_key 기준 조회 가능
- `--show-dup-group` 출력 가능
- `open_text.py --search TERM --context C` 동작

## Step 9 — eval_search.py
명령:

```text
eval_search.py를 구현하라.
golden_queries.yaml의 T1/T2 문항만 실행하고, expected_filter/expected_files/expected_count를 부분채점 방식으로 처리한다.
eval_history.jsonl에 결과를 추가 기록한다.
```

완료 기준:
- 실코퍼스가 없어도 fixture 기준 부분채점으로 완주
- count 성격 문항은 stats_contracts.py 또는 검색 결과를 사용

## Step 10 — README.md 완성
명령:

```text
README.md를 완성하라.
Claude Code 미설치/미로그인 절차, Codex 선택 활용, Codex는 API key를 가져오지 않는다는 원칙, 최초 파일럿 색인, --file-list 파일럿, --sample 파일럿, 검색 예시, 결과 해석, 전체 코퍼스 확장, 평가, manual_overrides.yaml, 백업/복구, 오류 FAQ를 포함한다.
```

완료 기준:
- 사용자가 파일럿 subset → 전체 확장까지 따라 할 수 있음
- cs_index를 PC 로컬 디스크에 두라는 경고 포함
- SQLite WAL 백업 주의 포함

## Step 11 — Phase 1B: budget.py와 answer_quick.py
명령:

```text
검색 품질 확인 후 Phase 1B를 구현하라.
lib/budget.py는 api_budget.yaml을 읽고 예산 상한, 캐시, ledger를 처리한다.
answer_quick.py는 search_contracts.py --json 상위 후보만 사용해 짧은 답변을 생성한다.
실 API 호출 테스트는 금지하고 mock으로만 검증한다. 최종 답변 로그는 agent_log.jsonl에 남긴다.
```

완료 기준:
- per_call/per_run null이면 API 실행 거부
- 상한 초과 시 호출 차단
- cache hit 시 무호출
- `api_ledger.jsonl`과 `agent_log.jsonl` 기록

## Step 12 — plan_extract.py
명령:

```text
plan_extract.py를 구현하라.
Phase 2 추출 후보를 SPA/SHA/SSA, final/signed, dedup 대표, query_log 빈도 기준으로 추천한다.
API 호출이나 doc_meta 기록은 하지 않는다.
```

완료 기준:
- 추천 목록과 추천 사유 출력
- limit 옵션 동작



## UI-0 — 디자인 인수(getdesign.md)
명령:

```text
CLI 검색 MVP가 안정화된 뒤 UI 구현을 시작하라.
먼저 getdesign.md를 읽고 DESIGN_INTEGRATION.md 절차에 따라 DESIGN_AUDIT.md를 작성하라.
아직 UI 코드는 만들지 말고, 사용할 디자인 자산과 부족한 항목만 정리하라.
```

완료 기준:
- DESIGN_AUDIT.md 작성
- STACK_DECISION.md 작성: 서버 렌더링+경량 JS(htmx/vanilla)와 SPA(React+Vite 등)를 비교하고 선택 사유 기록
- 사용 가능한 색상/폰트/간격/컴포넌트 목록 정리
- UI_PRODUCT_SPEC.md와의 충돌 또는 부족한 항목 기록


## UI-0.4 — PC Backend Foundation
명령:

```text
BACKEND_REVIEW_PC.md를 읽고 Windows PC 로컬 실행 기준의 백엔드 기반을 먼저 확정하라.
기본 바인딩은 127.0.0.1로 제한하고, 관리자 보호가 필요한 엔드포인트를 분리한다.
cs_index가 PC 로컬 디스크인지 검증하고, 네트워크 드라이브의 SQLite 사용은 거부한다.
색인/평가/API 호출용 단일 worker job queue와 job status API를 설계하라.
MVP 진행률 갱신은 GET /api/jobs/{job_id} 1~2초 폴링으로 처리하고 SSE/WebSocket은 v2로 미뤄라.
Runtime API Settings의 secret 저장소는 프론트엔드 저장소가 아니라 PC 로컬 사용자 전용 저장소를 사용한다.
원본 계약서 루트 설정은 POST /api/settings/root-path/validate로 존재 여부·읽기 권한·대략 파일 수를 검증하라.
필터 옵션을 위한 GET /api/catalog/facets를 제공해 ctype/lang/batch_label을 catalog에서 동적으로 내려줘라.
파일 열기는 file_key 기반 catalog 조회로만 처리하고, 임의 경로 입력을 허용하지 마라.
```

완료 기준:
- BACKEND_REVIEW_PC.md의 DoD가 구현 계획 또는 코드에 반영됨
- 임의 shell 실행 기능 없음
- raw exception이 사용자 화면으로 전달되지 않음
- SQLite writer 단일화 원칙이 반영됨

## UI-0.5 — Agent Setup Wizard
명령:

```text
UI_PRODUCT_SPEC.md의 Agent Setup Wizard 섹션과 AGENT_SETUP_AND_MODEL_OPTIONS.md §7을 읽어라.
관리자용 `설정 > AI 코딩 에이전트` 화면을 구현하라.
Claude Code, Codex CLI, Node.js/npm, Git, 프로젝트 경로 쓰기 권한, 샌드박스/파일시스템 상태를 진단해 표시한다.
미설치/로그인 필요/오류 상태별로 Windows PowerShell/VS Code 터미널용 복사 가능한 명령과 수동 절차를 보여주고, [다시 검사] 버튼을 제공한다.
초기 버전에서는 설치 명령을 서버에서 직접 실행하지 마라.
웹앱의 Agent Setup Wizard는 Claude/ChatGPT 비밀번호, OAuth 토큰, 세션 토큰, 로그인 코드를 입력받거나 저장하지 마라.
Codex는 API key를 가져오지 않는 구조로 유지하고, ChatGPT 구독계정 로그인 기반의 VS Code 확장/CLI 절차만 안내하라.
단, G1.5 Haiku/A9/A10/G2는 백엔드가 Anthropic API를 직접 호출하는 기능이므로, 별도 Runtime API Settings 화면에 `ANTHROPIC_API_KEY` 입력창과 api_budget 상한 입력을 두는 구조를 분리 설계하라. `.env` 직접 설정은 고급/수동 백업 경로로만 둔다.
```

완료 기준:
- 각 도구 상태가 installed / missing / needs_login / ready / error 중 하나로 표시됨
- OS/환경별 복사 가능한 설치·로그인 명령 표시
- [다시 검사] 버튼으로 상태 갱신 가능
- Agent Setup Wizard에는 API key 입력란 없음
- 로그인 토큰/코드 저장 없음
- Runtime API Settings는 별도 화면/섹션으로 분리되어 ANTHROPIC_API_KEY 입력창, 저장/연결 테스트/삭제 기능, 예산 상한 상태를 표시
- 임의 shell 명령 실행 기능 없음

## UI-1 — 읽기 전용 검색 UI
명령:

```text
UI_PRODUCT_SPEC.md의 UI MVP 범위만 구현하라.
검색창, catalog facets 기반 고급 필터, 필터 칩, 코퍼스 상태 배너, 결과 카드, 문단 주변 보기, 중복본 보기, 최근 검색, URL 상태 복원, Markdown/CSV 내보내기를 구현한다.
검색 결과 카드에는 why, matched_terms, score_breakdown, ¶번호, draft 여부, 중복 수를 표시하라.
한글 IME composition 중 Enter는 검색을 실행하지 않게 하고, 검색창 포커스 중 j/k 단축키는 비활성화하라.
CSV 다운로드는 utf-8-sig로 생성하라.
검색 결과 warnings(short_term_fallback, unsearchable_docs 등)는 결과 요약줄 배지로 표시하라.
매칭어 하이라이트가 전각/하이픈/따옴표 변이 때문에 실패하면 하이라이트 없이 원문 스니펫을 표시하라.
```

완료 기준:
- 필터 옵션이 catalog facets에서 동적으로 로드됨
- 검색 상태(query/filters/expand_mode)가 URL query parameter로 복원 가능
- 최근 검색이 UI에 표시되고 다시 실행 가능
- 파일럿 코퍼스 배너가 항상 표시됨
- 결과 카드에서 문단 주변 보기로 이동 가능
- CSV가 utf-8-sig로 생성됨
- 한글 IME Enter·검색창 포커스 단축키 충돌 방지
- search warnings 배지와 하이라이트 폴백 동작

## UI-2 — 운영 UI
명령:

```text
색인 상태 대시보드와 실패 파일 목록을 구현하라.
saved searches, result feedback, manual_overrides 후보 export를 구현한다.
```

완료 기준:
- status/error/batch 통계 표시
- 실패 파일별 error_reason과 권장 조치 표시
- 저장된 검색을 생성/실행/삭제 가능
- 결과 피드백이 result_feedback에 기록됨

## UI-3 — 리서치 UI
명령:

```text
비교 목록, 북마크/메모, 리서치 세션을 구현하라.
비교 목록은 메모리 상태만 쓰지 말고 ui_state.sqlite의 이름 없는 기본 비교 목록에 영속 저장하라.
MVP 비교 목록은 메모리 상태만 쓰지 말고 ui_state.sqlite의 이름 없는 기본 비교 목록에 영속 저장하라.
선택한 문단을 Markdown/CSV로 내보낼 수 있게 하라.
```

완료 기준:
- 검색 결과를 비교 목록에 추가/삭제 가능
- session_items에 선택 문단이 저장됨
- user_marks에 즐겨찾기/메모가 저장됨

## UI-4 — AI 보조 UI
명령:

```text
선택한 결과만 근거로 AI 요약/비교표를 생성하는 화면을 구현하라.
file_key와 ¶번호를 반드시 인용하고, 파일럿 코퍼스인 경우 주의 문구를 답변 상단에 표시하라.
```

완료 기준:
- 검색 결과에 없는 일반론 생성 금지
- API 예산 상태 표시
- agent_log.jsonl 기록
- 사용자가 선택하지 않은 문서를 근거로 쓰지 않음

## 최종 보고 형식
마지막 보고는 아래 형식으로 한다.

```text
1. 구현한 파일 목록
2. 실행한 테스트와 결과
3. 생성한 git commit 목록(hash + message)
4. Brief §6 DoD 체크리스트
5. 적용한 기본값
6. 남은 제한사항/질문
7. 파일럿 실행 권장 명령
```
