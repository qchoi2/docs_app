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

