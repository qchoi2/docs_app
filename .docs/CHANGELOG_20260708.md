# CHANGELOG_20260708 — 이번 세션 반영 사항

## 충돌 정리
- `--include-drafts`를 제거하고 `--exclude-drafts`를 표준 옵션으로 통일했다.
- `--exclude-draft`는 하위호환 alias로만 허용한다.
- `golden_queries.yaml` 설명을 실제 33문항 기준으로 맞췄다.
- 본 패키지는 실행 코드가 아니라 Phase 0~1 구현 지시서임을 `docs_progress_v2.md`에 명확히 했다.
- `doc_meta`는 IMPLEMENTATION_BRIEF.md §2.4의 JSON 통합 저장 DDL을 최종 기준으로 하며, `docs_progress_v2.md`의 컬럼 분리형 설명은 구버전 메모로 표시했다.

## 구현계획 보강
- 파일럿 subset → 전체 코퍼스 확장 절차를 `PILOT_ROLLOUT.md`로 추가했다.
- `index_contracts.py`에 `--batch-label`, `--dry-run`을 추가하도록 지시했다.
- `files` DDL에 `error_reason`, `source_signals`, `batch_label`을 추가했다.
- 검색 결과 JSON에 `why`, `score_breakdown`, `snippet_paras`, `dup_representative_reason`을 추가했다.
- `query_log.jsonl` 운영 로그를 추가했다.
- `inspect_file.py`, `open_text.py`, `plan_extract.py`를 Phase 1 구현 대상에 추가했다.
- `manual_overrides.yaml` 템플릿을 추가했다.
- 실패 원인 분류, dedup 대표 선정 기준, `--show-duplicates` 옵션을 추가했다.
- 파일럿 완료 기준과 성능 기록 항목을 DoD에 추가했다.

## 파일럿 운용 핵심 원칙
- 가장 안전한 방식은 최종 운영 루트와 같은 폴더 구조에서 일부 파일만 먼저 넣고, 나중에 같은 루트에 나머지 파일을 추가하는 것이다.
- 임시 복사 폴더로 파일럿을 수행한 경우 전체 운영용 `cs_index`는 새로 만드는 것이 안전하다.
- 파일럿 단계 답변에는 “현재 색인된 파일럿 코퍼스 기준”이라고 표시한다.

## 2026-07-08 추가 반영 — 구현 순서 및 파일럿 보강
- `CODING_SEQUENCE.md`를 추가해 GPT-5.5/Claude Code에게 시킬 단계별 구현 명령을 분리했다.
- Phase 1을 `Phase 1A 검색 MVP 필수`와 `Phase 1B API 보조`로 나누었다.
- `index_contracts.py`에 `--file-list`, `--sample`, `--sample-seed` 요구사항을 추가했다.
- `search_contracts.py`에 `--expand strict|normal|broad` 옵션을 추가했다.
- `stats_contracts.py`를 Phase 1A 산출물로 추가했다.
- `query_log.jsonl`과 `agent_log.jsonl`을 분리했다.
- `error_reason` enum을 확정했다.
- DOCX 각주·머리글·바닥글 처리는 best-effort로 완화했다.
- `open_text.py --search TERM` 모드를 추가했다.
- DoD의 리포트 섹션 수를 6개에서 9개로 수정했다.


## 2026-07-08 추가 반영 — UI/디자인/코딩 원칙
- `UI_PRODUCT_SPEC.md`를 추가해 검색 화면, 결과 카드, 문단 주변 보기, 검색 히스토리, 저장된 검색, 비교 목록, 북마크/메모, 결과 피드백, 색인 상태 대시보드, 내보내기, AI 답변 화면을 정의했다.
- `search_history`, `saved_searches`, `research_sessions`, `session_items`, `user_marks`, `result_feedback` 테이블 설계를 `IMPLEMENTATION_BRIEF.md`에 추가했다.
- 기존 `query_log.jsonl`은 운영 로그이고, 사용자가 보는 검색 히스토리는 별도 UI 상태로 관리하도록 명확히 했다.
- `DESIGN_INTEGRATION.md`를 추가해 UI 구현 전 `getdesign.md`를 읽고 `DESIGN_AUDIT.md`를 작성하도록 했다.
- `CODING_AGENT_RULES.md`를 추가해 GPT-5.5/Claude Code가 따를 Karpathy식 코딩 원칙(think before coding, simplicity first, surgical changes, verify every step, no hidden magic)을 명시했다.
- `UI_ROADMAP.md`를 추가해 UI-0~UI-4 구현 순서를 정의했다.
- `CODING_SEQUENCE.md`에 UI 구현 단계와 디자인 인수 절차를 추가했다.
- AI 답변은 검색 결과 확인 이후, 선택된 문서/문단을 근거로만 생성하도록 UI 원칙을 명시했다.

## 2026-07-08 final hardening — Step별 git commit discipline

- `CODING_AGENT_RULES.md`에 `Git commit discipline` 섹션 추가.
- 각 Step 완료 후 테스트/스모크 테스트 통과 상태에서만 commit하도록 명시.
- commit message 형식을 `step-N: <short description>` / `ui-N: <short description>`로 고정.
- 테스트 실패 상태 commit, 여러 Step 혼합 commit, unrelated refactor 포함 commit을 금지.
- `CODING_SEQUENCE.md`에 모든 Step의 공통 진행 루프를 추가.
- 최종 보고 형식에 생성한 git commit 목록 또는 commit하지 않은 이유를 포함하도록 수정.

## 2026-07-09 추가 반영

- `AGENT_SETUP_AND_MODEL_OPTIONS.md`를 추가해 최초 환경에서 Claude Code가 설치·로그인되어 있지 않은 경우의 진행 절차를 명시했다.
- Codex 구독요금제를 선택적으로 활용할 수 있도록 작업자 선택 기준을 추가했다.
- `IMPLEMENTATION_BRIEF.md`, `docs_progress_v2.md`, `CODING_SEQUENCE.md`, `CODING_AGENT_RULES.md`에 Claude Code/Codex 병행 사용 시의 우선순위, Step 단위 작업, git commit 규칙, 유료 API 실호출 금지 원칙을 반영했다.

## 2026-07-09 추가 반영 — Agent Setup Wizard

- 웹앱에 관리자용 `설정 > AI 코딩 에이전트` 화면을 두는 원칙을 추가했다.
- Claude Code/Codex 설치·로그인 상태는 웹앱에서 진단하되, 실제 로그인은 각 CLI/VS Code 확장의 공식 흐름으로 사용자가 직접 진행하도록 정리했다.
- 초기 UI에서는 설치 명령 자동 실행이 아니라 복사 가능한 명령어와 [다시 검사] 버튼을 제공하도록 했다.
- Agent Setup Wizard가 계정 비밀번호, OAuth/세션 토큰, 로그인 코드, OpenAI API key를 수집·저장하지 않는다는 보안 원칙을 명시했다. Haiku/Sonnet/Opus용 Anthropic API key는 별도 Runtime API Settings로 분리한다.
- Codex는 API key를 가져오지 않고 ChatGPT 구독계정 로그인 기반으로 사용하는 구조임을 `AGENT_SETUP_AND_MODEL_OPTIONS.md`, `UI_PRODUCT_SPEC.md`, `IMPLEMENTATION_BRIEF.md`, `CODING_SEQUENCE.md`, `CODING_AGENT_RULES.md`, `docs_progress_v2.md`에 반영했다.

## 2026-07-09 추가 반영 — Haiku 런타임 API 구조 재정리

- `docs_progress_v2.md`의 원래 의도에 맞게 Claude Code/Codex와 Haiku API 경로의 역할을 재분리했다.
- Claude Code/Codex는 개발·배치 작업자이고, G1.5 Haiku/A9/A10/G2는 웹앱 또는 CLI 백엔드가 Anthropic API를 직접 호출하는 런타임 기능임을 명시했다.
- Codex는 계속 API key를 가져오지 않는 구조로 유지한다. OpenAI API key 입력란을 만들지 않는다.
- Haiku/Sonnet/Opus API 경로를 실제로 사용하려면 사용자가 `ANTHROPIC_API_KEY`를 제공해야 하며, 이는 Agent Setup Wizard가 아니라 별도 Runtime API Settings 또는 서버 `.env`에서 처리하도록 수정했다.
- `AGENT_SETUP_AND_MODEL_OPTIONS.md`, `UI_PRODUCT_SPEC.md`, `IMPLEMENTATION_BRIEF.md`, `CODING_SEQUENCE.md`, `CODING_AGENT_RULES.md`, `docs_progress_v2.md`에 Runtime API Settings와 예산 가드레일을 반영했다.


## 2026-07-09 추가 반영 — Anthropic API Key UI 입력 방식 명확화

- `ANTHROPIC_API_KEY`는 관리자용 `설정 > API 예산 및 키` 화면의 입력창에서 받는 것을 기본 경로로 명시했다.
- 서버 `.env` 직접 설정은 고급/수동 백업 경로로만 남겼다.
- Runtime API Settings에 [저장] [연결 테스트] [삭제/교체] 버튼, password 입력, 저장 후 마지막 4자리 표시, 프론트엔드 저장소 저장 금지, 로그 노출 금지 원칙을 추가했다.
- Codex는 계속 OpenAI API key를 받지 않는 구조로 유지한다.

## 2026-07-09 추가 반영 — PC 로컬 백엔드 기준

- 기본 실행 환경을 NAS/서버가 아니라 Windows PC 로컬 실행으로 재정의했다.
- `BACKEND_REVIEW_PC.md`를 추가해 설정/시크릿 저장소, 관리자 보호, job queue, SQLite one-writer, file_key 기반 파일 접근, API budget/ledger/cache, Agent Setup Wizard subprocess allowlist, 표준 오류 코드를 정리했다.
- `IMPLEMENTATION_BRIEF.md`, `docs_progress_v2.md`, `UI_PRODUCT_SPEC.md`, `CODING_SEQUENCE.md`, `AGENT_SETUP_AND_MODEL_OPTIONS.md`, `PILOT_ROLLOUT.md`에서 NAS/DSM/tmux/Docker 기본 전제를 제거하거나 고급/선택 사항으로 내렸다.
- `ANTHROPIC_API_KEY`는 UI 입력을 기본 경로로 유지하되 PC 로컬 사용자 전용 secret 저장소에 보관하도록 명시했다. Codex는 계속 OpenAI API key를 받지 않는다.

## 2026-07-09 — PC 로컬 UI 개선 검토 반영

- `UI_REVIEW_PC.md` 신규 추가.
- NAS가 아니라 Windows PC 로컬 실행을 전제로 첫 실행 온보딩, 검색 split view, 작업 진행률, 빈/부분 성공 상태, Runtime API Settings 문구, Agent Setup Wizard 분리, 로컬 데이터 관리 UI를 정리했다.
- `UI_PRODUCT_SPEC.md`, `UI_ROADMAP.md`, `IMPLEMENTATION_BRIEF.md`, `docs_progress_v2.md`, `MANIFEST.txt`에 UI 개선사항을 반영했다.


## 2026-07-09 — 백엔드 정밀 리뷰 반영 (2차)

기능 정확성:

- **3글자 미만 질의어 폴백**: FTS5 trigram이 3자 미만 질의(2음절 국문 용어, term_dict의 CP/DD/IP/RW)를 매치하지 못하는 문제에 대해, txt 캐시 대상 LIKE 폴백 + `short_term_fallback` warning을 IMPLEMENTATION_BRIEF §2.6에 계약으로 추가했다.
- **FTS 질의어 이스케이프 규칙**을 추가했다. 하이픈·`&`·따옴표·AND/OR/NOT을 포함한 키워드는 반드시 구문 문자열로 감싼다.
- **`--full` 의미론과 FTS 정리 정책**을 확정했다: missing 전환 시 fts 행 삭제(txt 캐시·레코드 보존), `--full`은 files/fts만 재구축하고 ledger/cache/query_log/eval_history/ui_state는 보존.
- **API 캐시 키를 문서 간 통일**했다: `sha256(model_id + prompt_version + 프롬프트 + 입력 + budget_version)` (Brief §2.7 = BACKEND_REVIEW §2.6 = api_budget.yaml). 모델 변경 시 옛 캐시가 적중하는 버그를 차단한다.
- `--exclude-drafts`에서 is_draft=NULL은 포함+판별불가 표기, dedup ON의 `total`=그룹 수 + `total_files` 병기를 §2.6/§9/JSON 스키마에 명시했다.

Windows PC 특유 함정 (Brief §4에 추가):

- 콘솔 인코딩 cp949 리다이렉트 시 UnicodeEncodeError → `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` + `PYTHONUTF8=1`.
- 260자 MAX_PATH 초과 → `\\?\` 확장 경로 처리, permission_denied 오분류 방지.
- 파일당 추출 타임아웃은 SIGALRM 부재로 subprocess/watchdog 스레드 방식 필요.
- CLI 예시 `python3` → Windows에서는 `python`/`py`로 표기.
- 대량 색인 후 `PRAGMA wal_checkpoint(TRUNCATE)` 실행.
- jsonl 한 줄 4KB 미만 + 웹앱 경로 단일 writer 수렴.

구조/운영 (BACKEND_REVIEW_PC 보강):

- API key는 Windows DPAPI(ctypes, 추가 의존성 없음) 암호화 저장 기본, 불가 시 ACL 제한.
- job 상태 SQLite 영속화(jobs 테이블), 진행률 필드 계약, 협조적 취소.
- `/api/search`에 limit/offset 페이지네이션과 total/total_files를 초기 계약으로 포함.
- UI 상태 테이블은 `ui_state.sqlite`로 분리(기본값) — Brief의 중복 섹션 번호도 §2.8→§2.11로 수정.
- requirements.txt 버전 고정(pin) 요구 추가 — 추출 라이브러리 버전 변경으로 인한 ¶번호 결정성 파괴 방지.
- DoD에 디스크 사용량 측정, 이스케이프/폴백/missing-FTS 테스트, `--full` 보존성 검증을 추가했다.
- 문서 관계 명확화: BACKEND_REVIEW_PC.md는 Brief §2.0의 하위 상세화이며 충돌로 보지 않는다.


## 2026-07-09 추가 반영 — Frontend hardening 2차

- `UI_PRODUCT_SPEC.md`의 고급 필터를 SPA/SHA 등 하드코딩 목록에서 catalog facets 기반 동적 생성으로 변경했다.
- 첫 실행 원본 계약서 폴더 설정을 브라우저 폴더 피커가 아니라 경로 텍스트 입력 + `POST /api/settings/root-path/validate` 방식으로 명시했다.
- 한글 IME composition Enter 방어, 검색창 포커스 중 j/k 비활성화, URL 기반 검색 상태 복원을 UI 계약에 추가했다.
- CSV 다운로드는 한국어 Windows Excel 호환을 위해 `utf-8-sig`로 생성하도록 명시했다.
- normalize() 기준 검색과 원문 표면형 불일치 시 매칭어 하이라이트 없이 표시하는 폴백 규칙을 추가했다.
- job 진행률은 MVP에서 `GET /api/jobs/{job_id}` 1~2초 폴링으로 처리하고 SSE/WebSocket은 v2로 미뤘다.
- search warnings, 특히 `short_term_fallback:<term>`, `unsearchable_docs:N`를 결과 요약줄 배지로 표시하도록 했다.
- AI disabled 상태를 `missing_key`, `budget_not_set`, `missing_key_and_budget`, `no_selection` 등 원인별 문구로 구분하도록 했다.
- 비교 목록은 MVP에서도 `ui_state.sqlite`의 이름 없는 기본 비교 목록으로 영속 저장하도록 했다.
- UI-0 산출물에 `STACK_DECISION.md`를 추가해 코딩 에이전트가 임의로 무거운 프론트엔드 스택을 선택하지 않도록 했다.
- 접근성 보강: aria-live 진행률/검색 완료 알림, split view 포커스 이동, 검색창 포커스 중 전역 단축키 비활성화.
