# Progress

## 2026-07-09

- Created the initial repository scaffold for the contract search project.
- Added base directories: `lib/`, `data/`, `tests/`.
- Added initial project files: `requirements.txt`, `README.md`, `CLAUDE.md`.
- Added a minimal smoke test to verify the scaffold structure.
- Verified the scaffold with `pytest -q tests/test_scaffold.py` and got `1 passed`.
- Implemented `lib/normalize.py` with NFC normalization, fullwidth-to-halfwidth conversion, hyphen/quote normalization, zero-width character removal, and whitespace cleanup.
- Added `tests/test_normalize.py` and verified it with `python -m pytest -q tests/test_normalize.py`.
- Completed Step 3: implemented `lib/catalog.py` for catalog SQLite schema initialization.
- Added creation of the `files`, `fts`, `doc_meta`, and `clause_index` tables, plus `idx_meta` and `idx_dup` indexes.
- Added FTS5 trigram availability checks using both `sqlite3.sqlite_version_info >= 3.34.0` and an in-memory `fts5(... tokenize='trigram')` probe.
- Added explicit failure behavior for missing trigram support, including a clear error message and `pysqlite3-binary` installation guidance; no silent fallback is used.
- Added catalog helpers: `initialize_catalog(db_path)`, `connect_catalog(db_path)`, `CatalogError`, and a small CLI entrypoint for schema initialization.
- Adjusted the FTS column declaration from the brief's `para INTEGER UNINDEXED` to SQLite FTS5-compatible `para UNINDEXED`; the rest of the catalog DDL follows the implementation brief.
- Verified temporary DB creation successfully: SQLite `3.50.4`, `journal_mode=wal`, all required tables present, and trigram search returned `('K1', 1)`.
- Ran the full test suite with `python -m pytest`; result: `4 passed` with one existing pytest cache warning.
- Confirmed `index_contracts.py` was not implemented in this step.
- Completed Step 4: implemented the first pass of `index_contracts.py`.
- Added root folder scanning for supported `.docx` and `.pdf` files only.
- Added `file_key` generation from the first 16 hex characters of the file byte SHA-256 digest.
- Added `content_hash` generation from the first 16 hex characters of the normalized extracted text SHA-256 digest, excluding paragraph markers.
- Added txt cache writing at `cs_index/txt/<file_key>.txt` with `[¶N]\t` prefixes and continuous numbering for non-empty paragraphs.
- Added catalog writes to the `files` table and paragraph writes to the `fts` table for `status='ok'` documents.
- Implemented DOCX extraction using document body order traversal instead of separate `document.paragraphs` and `document.tables` passes; table rows are emitted as row-level paragraphs with cells joined by ` | `.
- Added best-effort DOCX header/footer extraction and a non-fatal footnote skipped warning.
- Implemented PDF text extraction with `pdfminer.six`; blank extracted text is recorded as `status='empty'` with `error_reason='pdf_text_empty'`.
- Added fixtures/tests for synthetic DOCX paragraphs, DOCX table ordering, text PDF indexing, and blank PDF empty handling.
- Kept Step 4 scope narrow: did not implement incremental indexing, `--sample`, `--file-list`, or `--dry-run`.
- Updated `requirements.txt` to Python 3.14-compatible `python-docx` and `pdfminer.six` ranges after the previous pinned range failed to install in this environment.
- Verified CLI shape with `python index_contracts.py --help`; only `--root` and `--out` are present.
- Ran the full test suite with `python -m pytest`; result: `8 passed` with one existing pytest cache warning.
- Completed Step 5: added operational indexing options to `index_contracts.py`.
- Added `--full`, `--include-misc`, `--batch-label`, `--file-list`, `--sample`, `--sample-seed`, and `--dry-run`.
- Added incremental handling for unchanged skip, newly added files, moved files, deleted files marked `missing`, restored files, and same-path content changes with old file keys marked `missing`.
- Added validation that `--file-list` and `--sample` cannot be used together.
- Added deterministic sampling with `--sample-seed`.
- Added partial-run behavior for `--file-list` and `--sample`: unlisted/unselected existing files are not marked `missing`.
- Added `--full` behavior to rebuild only the generated `files` and `fts` index data.
- Added `report_YYYYMMDD.md` generation with change counts/lists and database summary sections.
- Added tests for rerun skip, add-only incremental indexing, deletion-to-missing, file-list pilot followed by full expansion, deterministic sampling, file-list/sample conflict, move, restore, content change, dry-run, full batch-label recording, and include-misc filtering.
- Verified CLI shape with `python index_contracts.py --help`; all Step 5 options are present.
- Ran the full test suite with `python -m pytest`; result: `20 passed` with one existing pytest cache warning.
- Completed implementation brief hardening pass after reviewing `.docs/IMPLEMENTATION_BRIEF.md` against the code.
- Removed Python 3.10-only union type syntax from `index_contracts.py` and `lib/catalog.py`; verified both files parse with Python 3.9 syntax rules.
- Replaced hardcoded misc-folder filtering with `type_rules.yaml`-based `exclude_by_default` pattern handling, preferring `data/type_rules.yaml` and falling back to `.docs/type_rules.yaml`.
- Added type/language/draft/version classification signals to `files` table writes using the available type rules and text heuristics.
- Expanded root scanning to account for unsupported legacy extensions and zip files while excluding symlinks.
- Added DB recording for unsupported files with `status='unsupported'` and `error_reason='unsupported_ext'`; zip files are reported as excluded without DB rows.
- Added file-level OS error handling for stat/read failures, mapping permission failures to `permission_denied` and other OS failures to `unknown_error` where possible.
- Expanded `report_YYYYMMDD.md` with type-language distribution, unclassified folders, unsupported/excluded/error lists, and existing DB summary sections.
- Changed `requirements.txt` dependency ranges to exact pins for deterministic extraction behavior.
- Added tests for unsupported-file recording, zip report exclusion, type-rule classification, and unclassified folder reporting.
- Added `.gitignore` entries for Python cache and pytest cache artifacts, and removed previously tracked `.pyc` cache files from the working tree.
- Verified `python index_contracts.py --help`; Step 5 options remain present.
- Ran the full test suite with `python -m pytest`; result: `22 passed` with one existing pytest cache warning.
- Completed second implementation-brief alignment pass.
- Placed runtime YAML files in `data/`: `term_dict.yaml`, `type_rules.yaml`, `golden_queries.yaml`, `api_budget.yaml`, and `manual_overrides.yaml`.
- Replaced the partial custom `type_rules.yaml` parser with `PyYAML` loading.
- Changed unsupported-file scanning so arbitrary non-supported, non-zip files are recorded as `status='unsupported'` instead of being silently ignored.
- Added `report_YYYYMMDD-2.md`, `-3.md`, etc. collision handling.
- Added `PRAGMA wal_checkpoint(TRUNCATE)` after successful write runs.
- Expanded README with Windows local setup, local `cs_index` disk warning, pilot/full indexing commands, dry-run note, and runtime data guidance.
- Added tests for runtime YAML placement, arbitrary unsupported extension recording, and report filename collision handling.
- Verified `python index_contracts.py --help`; Step 5 options remain present.
- Verified Python 3.9 syntax compatibility with `ast.parse(..., feature_version=(3, 9))`.
- Ran the full test suite with `python -m pytest`; result: `25 passed` with one existing pytest cache warning.
- Added a local test convenience extension: `index_contracts.py --root` now defaults to the repository-local `root/` folder when omitted, while explicit `--root` remains supported for real corpus runs.
- Added `root/` and `cs_index/` to `.gitignore` so local sample contracts and generated indexes are not committed.
- Fixed ctype classification to use path/file-name signals only; body text is still used for language heuristics. This avoids SPA contracts being over-classified as BW/CB due to boilerplate terms in the extracted text.
- Added regression tests for the default root parser behavior and path-only ctype classification.
- Ran a 200-file pilot index against local `root/` using `python index_contracts.py --out .\cs_index --sample 200 --sample-seed 42 --batch-label pilot_001`.
- Re-ran the same pilot with `--full` after fixing ctype classification. Final pilot result: 200 indexed, 195 ok, 5 empty PDFs, 0 errors, 0 unsupported, 1 duplicate group of size 5, and 2 unclassified investment agreement files.
- Verified `python -m pytest`; result: `27 passed` with one existing pytest cache warning.
- Completed Step 6: implemented `search_contracts.py`.
- Added FTS5 trigram search with phrase escaping for hyphen, quotes, and boolean-looking terms.
- Added runtime loading of `data/term_dict.yaml` through `PyYAML`; no term dictionary content is hardcoded.
- Added `--expand strict|normal|broad`, `--no-expand`, repeated `--kw` AND semantics, `--exclude-drafts`/`--exclude-draft`, and `--show-duplicates`.
- Added file-level RRF ranking with exact-match weight 2.0 over expansion matches.
- Added default dedup representative selection by `dup_group`, with duplicate counts and representative reason in JSON.
- Added JSON output including `why`, `score_breakdown`, `matched_terms`, `snippet`, and `snippet_paras`.
- Added `query_log.jsonl` append logging with timestamp, query, filters, expand mode, result count, and warnings.
- Added 3-character-short term LIKE fallback with `short_term_fallback:<term>` warnings.
- Implemented no-result searches as normal non-error responses per user instruction.
- Added tests for exact-vs-expanded ranking, two-character Korean fallback, special FTS escaping, dedup on/off, repeated keyword AND, draft exclusion, strict expansion behavior, JSON schema, query logging, and no-result behavior.
- Verified `python search_contracts.py --help`; Step 6 options are present.
- Ran a smoke search against local pilot `cs_index`: `python search_contracts.py --out .\cs_index --kw 손해배상 --limit 3 --json`.
- Verified Python 3.9 syntax compatibility with `ast.parse(..., feature_version=(3, 9))`.
- Ran the full test suite with `python -m pytest`; result: `36 passed` with one existing pytest cache warning.
- Completed a critical `.docs` alignment pass after Step 6.
- Updated `search_contracts.py` so exact terms also carry term_dict canonical tags, snippet generation honors `--context`, and RRF scoring uses the best file rank per exact/expanded source rather than accumulating score for every synonym variant.
- Reworked `index_contracts.py` reports into the nine Brief §2.5 sections, including explicit status, duplicate, unsupported/excluded, error, batch, and stale doc_meta sections.
- Refreshed README current scope and added a minimal search CLI example.
- Kept no-result searches as exit code 0 per the user's Step 6 instruction, despite the older `.docs` exit-code note.
- Completed Step 7: implemented `stats_contracts.py`.
- Added `--by ctype`, `--by ctype,lang`, `--status`, `--errors`, `--batches`, `--dedup`, and `--json`.
- Added grouped statistics that distinguish `status='ok'` counts from all non-missing catalog counts.
- Added dedup representative-based counting for grouped/status/error/batch statistics and a `dedup_summary` with file-vs-group totals.
- Added tests for ok-vs-all grouped counts, dedup group counting, and CLI JSON output for status/error/batch/dedup sections.
- Verified `python stats_contracts.py --help`.
- Verified Python 3.9 syntax compatibility for `stats_contracts.py` and `tests/test_stats_contracts.py`.
- Ran the full test suite with `python -m pytest -q`; result: `41 passed` with one existing pytest cache warning.
- Completed Step 8: implemented `inspect_file.py` and `open_text.py`.
- Added `inspect_file.py --out ... --file-key K [--show-dup-group] [--json]` with ctype/lang/status/error_reason/source_signals, duplicate group details, and a doc_meta stale status slot.
- Added `open_text.py --out ... --file-key K --para N --context C` and `--search TERM --context C`, reading paragraph windows from txt cache only.
- Added tests for file_key inspection lookup, surrounding paragraph output, search-term paragraph output, and JSON CLI output.
- Verified `python inspect_file.py --help` and `python open_text.py --help`.
- Verified Python 3.9 syntax compatibility for the new Step 8 files.
- Ran the full test suite with `python -m pytest -q`; result: `45 passed` with one existing pytest cache warning.

## 2026-07-10

- Completed Step 9: implemented `eval_search.py` with T1/T2 golden-query execution, partial (filter-only) scoring, unscored-query reporting, and `eval_history.jsonl` regression logging.
- Recovered a corrupt `.git/index` (zeroed by an interrupted git process) and added `.gitattributes` for line-ending normalization.
- Completed Step 10: rewrote `README.md` in Korean covering Windows-local setup, venv, pilot indexing, full-corpus expansion, search/eval usage, manual overrides, backup/restore with WAL files, Claude Code install/login, optional Codex usage without OpenAI API keys, the ANTHROPIC_API_KEY runtime path, an error FAQ, and web UI as a follow-up phase.
- Completed Step 11: `index_contracts.py` now loads `data/manual_overrides.yaml` with path-glob and file_key overrides, applied as auto classification -> path override -> file_key override; only ctype/lang/is_draft/version_hint can be corrected and applied overrides are recorded in source_signals. Added three tests covering path override, file_key override (including ignoring file_key/content_hash keys), and precedence.
- Fixed a real dedup bug found in the pilot index: documents without extracted text (empty scanned PDFs) all share the empty-string content hash and were grouped into one spurious dup_group of size 5. `rebuild_dup_groups` now groups only status='ok' documents; others keep their own file_key as dup_group. Added a regression test.
- Fixed silent cwd dependence of runtime data loading: `term_dict.yaml`, `type_rules.yaml`, `manual_overrides.yaml`, and `golden_queries.yaml` are now resolved from the current directory first and the script directory as a fallback, and searches emit a `term_dict_not_found` warning instead of silently disabling expansion. Verified the same query previously returned 2 vs 5 results depending on launch directory.
- Added `lib/console.py` and wired `configure_utf8_stdio()` into every CLI entrypoint to prevent cp949 UnicodeEncodeError on piped output (brief §4), and NFC-normalized both sides of path/pattern matching for macOS-origin NFD filenames.
- Polished CLI tools per brief defaults: `index_contracts.py --quiet`, 240-character total snippet budget centered on the matched paragraph, `meta_filter_match` null when no meta filter was requested, `inspect_file.py` now reports char_count and matched term_dict entries, and `eval_search.py` uses an optional `kw:` field from golden queries when present.
- Wrote `NOTES_FOR_OWNER.md` recording applied defaults, intentional deviations (no-result exit code 0, dry-run report file), unimplemented risks (per-file extraction timeout, long-path handling), remaining Phase 1B/UI work, and the golden-query `kw:` suggestion.
- Ran the full test suite with `python -m pytest -q`; result: `58 passed`.
- Ran the pilot workflow on the local sample corpus (`--sample 200 --sample-seed 42 --batch-label pilot_001`, chunked via `--file-list` for sandbox time limits): 271 files total, 265 ok, 6 empty scanned PDFs, 0 errors, no duplicate groups.
- Pilot checklist found a real lang misclassification: all 43 documents labeled 영문 were Korean contracts (hangul ratio 0.88-0.99) because lang rules matched body text containing language clauses ("...국문과 영문...", "English"). Fixed `classify_path` to use path signals only for lang (same principle as the earlier ctype fix), added a regression test, and reclassified the existing catalog (45 rows updated; final: 263 국문, 2 영문 both genuinely English, 6 미상 empty scans).
- Verified the remaining checklist items: 미분류 2/271, draft exclusion correct (262→92, no drafts remaining, 21 판별불가 included and marked), no over-merged duplicates, 20 practical search terms return results with synonym expansion (0.4-1.4s per query on local disk), and 2-character terms (합병/해제/CP/DD) all return results with `short_term_fallback` warnings.
- Recorded findings and follow-ups in `PILOT_REPORT_20260710.md`.
- Merged owner-approved term variants into `data/term_dict.yaml` (dict v2.2): 배상상한 gains 손해배상 상한/손해배상상한/배상한도/손해배상액의 한도/limitation of liability, 해제 gains 계약해제/계약 해제/계약의 해지. Measured effect: "손해배상 상한" 1→92 results, "계약해제" 9→264 results.
- Added `term_dict_tools.py` implementing the maintenance pipeline documented in the dictionary header: `--validate` (schema, duplicate variants, cross-entry conflicts — found 3 informational shared-variant warnings), `--suggest` (mines query_log.jsonl for unlisted search terms and writes `pending_terms.yaml` candidates with evidence for human approval), and `--zero-hits` (variants with no FTS matches in the current corpus). No paid API calls anywhere. Added three tests.
- Documented the extension loop in README §6.5 and, per owner instruction, added a "term_dict 확장 제안" section to CLAUDE.md/AGENTS.md so search agents proactively propose dictionary candidates (never merging directly; human approval and eval regression check required). Recorded the CLAUDE.md modification authorization in NOTES_FOR_OWNER.md.
- Ran the full test suite: 62 passed.
- Completed Web Backend Step 1: added `webapp.py`, a standard-library WSGI server wrapping the CLI search MVP as a read-only API bound to 127.0.0.1 by default. Endpoints: GET /api/health, GET /api/corpus/status, POST /api/search (limit/offset pagination from the start), GET /api/files/{file_key}/context, GET /api/files/{file_key}/duplicates, POST /api/export/markdown, POST /api/export/csv (utf-8-sig), GET /api/search/facets (+ /api/catalog/facets alias). Errors use standard codes (VALIDATION_ERROR, FILE_NOT_FOUND_IN_CATALOG, SQLITE_BUSY, INTERNAL_ERROR...) and raw exceptions never reach the client. File access is file_key-only with format validation; UNC cs_index paths are rejected.
- Added `connect_search_db(read_only=...)` so web searches use short-lived mode=ro SQLite connections with busy_timeout, per BACKEND_REVIEW_PC §2.4.
- Added five webapp tests (smoke incl. 404/405/validation, search JSON schema + pagination, context/duplicates by file_key, CSV BOM + parseability, markdown citations) and live-smoked all endpoints against the pilot index. Job queue, Runtime API Settings, Agent Setup Wizard, and AI answers remain out of scope for this step.
- Completed UI-0 (design intake): audited `getdesign.md` (Vercel Geist token spec — full color/typography/spacing/radius/component tokens, no framework code, one data defect in typography.label-sm noted for the owner) into `DESIGN_AUDIT.md`, including derived-component rules for missing data-UI pieces (badges, tables, sidebar), Korean font fallback and tracking exceptions, and per-screen application plans for UI_PRODUCT_SPEC. Wrote `STACK_DECISION.md` choosing static HTML + vanilla JS + CSS custom properties served by webapp.py, with React/Vite, Tailwind/Bootstrap, and htmx explicitly excluded per DESIGN_INTEGRATION §7. No UI code written in this step.
- Completed UI-1 (read-only search screen): webapp.py now serves a bundled static UI (GET / and /static/<name> with single-segment name validation — no traversal, no server-source exposure). Built `static/index.html`, `app.css` (getdesign.md tokens as CSS custom properties, Korean font fallback stack, app-chrome 6px buttons per DESIGN_AUDIT), and `app.js` (vanilla): search box with IME-composition Enter guard, dynamic ctype/lang facets from /api/search/facets (no hardcoded options), filter chips with removal, result cards showing why/score_breakdown/snippet_paras plus exact/synonym/broad/draft/dup-representative badges, warnings badges (short_term_fallback, unsearchable_docs, term_dict_not_found), paragraph-context and duplicates panels per card, Markdown/CSV export via the existing endpoints, URL query-parameter state (kw/type/lang/expand/drafts/dups) with popstate restore, aria-live search-completion announcements, and j/k card navigation disabled while inputs have focus. No AI generation, no indexing triggers, no source-file modification.
- Added four UI tests (static serving, traversal/unknown-file blocking, offline no-external-resources rule, no hardcoded facet options); suite now 71 passed. Verified live serving of /, app.css, app.js against the pilot index.
- Completed UI-3 recent searches: added `lib/ui_state.py` creating `cs_index/ui_state.sqlite` with the Brief §2.11 user-state tables (search_history active; saved_searches/user_marks/result_feedback reserved). POST /api/search now records query, filters_json (kw/type/lang/exclude_drafts/show_duplicates), expand_mode, result_count, top_file_keys, and duration_ms into search_history — empty searches and export re-runs are not recorded, and a failed history write never blocks the search. New GET /api/history/recent returns the latest searches deduped by identical conditions. The search screen shows them as clickable chips that restore the full search state, inputs, and URL query parameters. Boundary kept: query_log.jsonl remains the operational log written by search_contracts; user state lives only in ui_state.sqlite; catalog.sqlite holds no user tables (asserted by test).
- Added three tests (history persistence + catalog boundary, recent-endpoint dedupe/ordering/empty-search skip, exports not recording); suite now 74 passed. Live-smoked recording and retrieval against the pilot index.

## 2026-07-11

Note: the UI-0 / UI-1 / UI-3 entries above were completed in the early hours of 2026-07-11 (same working session as 2026-07-10).

### Session summary (2026-07-10 -> 2026-07-11, 17 commits)

Review and hardening of the CLI MVP, the real-sample pilot, and the first web layer. Full test suite: **74 passed**.

- Recovery/hygiene: recovered a corrupt `.git/index`, added `.gitattributes` (`61084df`).
- Step 10-11: completed Korean README for the CLI MVP (`cba1e6f`); manual_overrides.yaml loading with path-glob/file_key priority (`b8886dd`).
- Fixes from the review pass: non-ok documents no longer share dup groups (`e02f2bd`); runtime YAML files resolve from the script directory as fallback with a `term_dict_not_found` warning (`b4d39ed`); UTF-8 console output + NFC path matching for Windows (`de91809`); CLI polish — --quiet, 240-char snippet budget, honest meta_filter_match, inspect char_count/term_matches, eval `kw:` support (`bf949ea`); owner notes (`6679e3b`).
- Pilot on the local sample corpus (271 docs): found and fixed lang misclassification — all 43 "영문" documents were Korean contracts matched via body-text language clauses; lang now classifies from path signals only and the catalog was reclassified (`ad2ed4e`); findings in PILOT_REPORT_20260710.md (`a7805ce`).
- term_dict loop: owner-approved variants merged (dict v2.2 — "손해배상 상한" 1->92, "계약해제" 9->264) (`5bd9054`); `term_dict_tools.py` --validate/--suggest/--zero-hits writing pending_terms.yaml for human approval (`e8586f0`); CLAUDE.md/AGENTS.md now direct agents to propose term_dict candidates without paid API calls (`5c6433a`).
- Web layer: read-only API (8 endpoints, stdlib WSGI, 127.0.0.1, standard error codes, utf-8-sig CSV) (`0767f85`); UI-0 design audit + stack decision (`e5f3d4e`); UI-1 read-only search screen (`0ff3c6b`); UI-3 recent searches persisted in ui_state.sqlite (`072801a`).

Current state: Phase 1A CLI MVP complete and pilot-validated; web read-only search (UI-1) and recent searches (UI-3 subset) shipped.
Remaining (in roadmap order): real-corpus pilot on D:\Contracts re-run by the owner, UI-0.4 job queue / backend foundation, UI-2 operations dashboard, rest of UI-3 (bookmarks/sessions/compare), Phase 1B (budget.py, answer_quick.py) after search-quality sign-off, then UI-4 AI answers.

### 웹앱 실행 방법 (재확인)

`webapp.py`는 프로젝트 폴더(`docs_app`) 안에서 실행해야 하고, `--out`은 실제 색인 폴더를
가리켜야 한다. README의 `C:\cs_index`는 예시 경로이며, 현재 리포지토리에 포함된 파일럿 색인은
`docs_app\cs_index`에 있다.

```
cd C:\Users\qchoi\Desktop\cowork\docs_app
python webapp.py --out cs_index
# 또는 (경로/폴더 자동 처리):
run_webapp.bat
```

`run_webapp.bat`는 어느 폴더에서 실행해도 프로젝트 폴더로 이동한 뒤 로컬 `cs_index`를
대상으로 웹앱을 띄운다. 다른 색인은 `run_webapp.bat C:\my_index`.

### UI-0.2/0.3 백엔드 착수 — job/indexing write 계층 (steps 1-3)

문서상 "현재 단계=UI-3"과 실제 구현(UI-1 + 최근검색 slice) 사이의 격차를 `UI_GAP_ANALYSIS.md`에
정리했다. UI-0.2(온보딩)·UI-0.3(진행률)은 색인 실행이라는 write 작업을 전제로 하므로,
화면보다 **job/indexing write 백엔드**를 먼저 구현했다. 검색 read 경로에는 영향이 없다.

- **`lib/jobs.py`** — `jobs.sqlite` 영속 job 큐. 표준 `queue.Queue` + worker thread 1개(one-writer),
  상태 전이 queued→running→completed|failed|cancelled, 파일 단위 협조적 취소, 앱 시작 시
  running/queued 잔여 job을 `failed(error_code=interrupted)`로 정리(크래시 복구),
  progress write throttle(0.3s), `job_logs` 테이블 + `GET /api/jobs/{id}/log` lifecycle 로그.
  jobs는 사용자 상태(ui_state)도 색인 산출물(catalog)도 아니므로 별도 DB에 둔다.
- **`index_contracts.py`** — `IndexOptions`에 선택 훅 `progress_callback(done,total,current_item)`,
  `cancel_check()`를 추가. 메인 루프가 파일마다 진행률을 보고하고 취소를 확인한다. 취소 시
  이미 커밋된 파일은 유지하고, 스캔되지 않은 파일을 missing으로 표기하지 않는다(부분 증분).
  결과 dict에 `cancelled` 추가. CLI 경로는 훅이 None이라 동작 불변.
- **`webapp.py`** — write 엔드포인트 추가: `POST /api/settings/root-path/validate`(존재·읽기권한·
  예상 파일 수·지원 확장자 수·네트워크 드라이브 여부, 스캔 상한 20000),
  `POST /api/jobs/index`(202+job_id), `GET /api/jobs`, `GET /api/jobs/{id}`,
  `POST /api/jobs/{id}/cancel`, `GET /api/jobs/{id}/log`(job 로그). `App`이 `JobQueue`를 생성·기동하고 index 핸들러를 등록한다.
  표준 오류 코드 유지, raw 예외 비노출.
- 테스트: `tests/test_jobs.py`(성공/진행률/협조적 취소/표준 error_code/미등록 타입/크래시 복구 6건),
  `tests/test_webapp_jobs.py`(root-path 검증·색인 job end-to-end 진행률·ROOT_NOT_FOUND·job 검증/404·
  jobs가 catalog에 없음·job 로그 lifecycle 6건). 전체 **86 passed**.

미완료(다음 순서): UI-0.2 온보딩 화면 + UI-0.3 진행률 폴링 UI(step 4) → UI-2 운영 대시보드(step 5)
→ UI-3 리서치 UI(compare_lists/compare_items/research_sessions, 북마크/메모, 선택 문단 export)(step 6).


### 커밋 기록

- `9bba691 web-2: add persistent job queue` — 6 files(+872/-8): lib/jobs.py, webapp.py,
  index_contracts.py, tests/test_jobs.py, tests/test_webapp_jobs.py, progress.md.
- **git 상태 주의**: 리포의 `.git/index`가 이전부터 손상돼 있어(HEAD에 존재하는 webapp.py·static/·
  lib/ui_state.py 등이 "삭제됨"으로 표시) HEAD로부터 깨끗한 임시 인덱스를 만들어 의도한 6개
  파일만 스테이징해 커밋했고, `.git/index`를 그 트리로 복구했다. 샌드박스가 잠금 파일을 unlink할 수
  없어 0바이트 `.git/index.lock`, `.git/HEAD.lock`가 남아 있으니 PC에서 두 파일을 삭제해야 다음
  커밋이 가능하다. `UI_GAP_ANALYSIS.md`, `run_webapp.bat`은 job queue 범위가 아니라 untracked로 남김.

### 2026-07-11 세션 2 — 리뷰 반영 + 온보딩/진행률 UI + Runtime API Settings (7 commits)

Web Backend Step 1과 UI-0/UI-1/UI-3 구현을 계획 문서(BACKEND_REVIEW_PC, UI_PRODUCT_SPEC,
UI_ROADMAP, 2026-07-09 hardening checklist)와 대조 검증했다. 핵심 계약(127.0.0.1 기본 바인딩,
file_key 전용 파일 접근, 표준 오류 코드, utf-8-sig CSV, limit/offset+total/total_files,
facets 동적 로드, IME Enter 가드, URL 상태 복원, ui_state 분리, one-writer job 큐)은 모두
계획대로 구현돼 있음을 확인했고, 아래 편차를 수정했다. 전체 테스트: **96 passed**.

- 리뷰 수정 (`f03c1f4`): CSV export에 스펙 §13 필수 컬럼(query, filters, export_created_at,
  filename, para, why) 추가; Markdown export에 검색 사유(why) 병기; UI-1 필수였던
  매칭어 하이라이트를 구현 — matched_terms+검색어를 원문 표면형에서 찾아 <mark> 처리하고,
  전각/하이픈 차이로 실패하면 하이라이트 없이 원문 그대로 표시(스펙 §5 안전 규칙).
- 문서 커밋 (`99a0417`): 이전 세션의 progress/UI_GAP_ANALYSIS/run_webapp.bat 추적 시작.
- UI-0.2/0.3 화면 (`7130c43`, 커밋명 ui-4): `/setup` 온보딩+진행률 페이지.
  경로 텍스트 입력 + POST /api/settings/root-path/validate(폴더 피커 미사용),
  cs_index 로컬 디스크 경고, 색인 시작 버튼, GET /api/jobs/{id} 1.5초 폴링
  (progress bar·현재 파일·취소·로그 보기·최근 작업 목록), 표준 오류 코드→한국어 메시지
  매핑(raw traceback 비노출), aria-live는 상태 전이 시에만 알림. 테스트 2건 추가.
- Runtime API Settings (`c0ce2b9`): `/settings` 화면 + lib/settings_store.py.
  ANTHROPIC_API_KEY 저장/삭제/교체 — Windows DPAPI(ctypes) 암호화, 비 Windows 폴백은
  0600 사용자 전용 권한; 저장 위치는 %APPDATA%/contract-search/secrets.json
  (CONTRACT_SEARCH_CONFIG_DIR로 재지정 가능). 저장 후 마지막 4자리만 표시, 키 전문은
  응답·로그에 비노출, 프론트엔드 저장소 사용 금지(테스트로 강제). 예산은
  data/api_budget.yaml의 per_call/per_run 두 줄만 주석 보존 갱신. disabled_reason:
  missing_api_key / missing_budget / missing_api_key_and_budget. 연결 테스트는
  format_only mock — 실제 API 호출 없음. OpenAI key 입력란 없음. 테스트 5건 추가.
- 백엔드 하드닝 (`edd7a10`): 색인 job 동시 실행 금지(409 INDEX_JOB_ALREADY_RUNNING),
  요청 본문 1MB 상한(413), `backup_index.py` — SQLite 3종을 Connection.backup()으로
  WAL-safe 온라인 백업하고 txt/·jsonl을 복사(README §7 갱신). 테스트 3건 추가.
- 프론트엔드 개선 (`435059d`): 오류 코드→한국어 메시지 매핑을 검색 화면에도 적용,
  색인 0건이면 배너에서 /setup 안내, 문단 주변 보기에 앞뒤 더 보기(context 최대 10)·
  ¶번호 복사·원본 경로 복사 추가(스펙 §5), 빈 결과 화면에 스펙 §12 제안 목록,
  settings 키 입력창 Enter 저장(IME 가드).
- git 정비: 이전 세션의 0바이트 `.git/index.lock`·`HEAD.lock`을 삭제 권한 승인 후 제거 —
  PC에서 수동 삭제 불필요해짐. repo-local user.name/email 설정.

남은 것(로드맵 순): 실제 코퍼스(D:\Contracts) 파일럿 재실행(소유자), UI-2 운영 대시보드
(색인 상태/실패 파일/batch 통계/saved searches/피드백/보정 후보 export), UI-3 나머지
(비교 목록·북마크·리서치 세션·선택 문단 export), Phase 1B(lib/budget.py, answer_quick.py —
검색 품질 사인오프 후), UI-4 AI 답변 화면.

### 2026-07-11 세션 3 — A-1 enrich_contracts.py 하네스

NEXT_STEPS.md 부록 A의 A-1 범위를 구현했다. `enrich_contracts.py`는 실제 AI/API 호출 없이 T3 보강 배치의 하네스만 담당한다: `status='ok'` 문서 중 dup 대표만 고르고, 기본 우선순위(SPA → SHA → SSA → MOU → ATA/BTA → JVA → CB/BW/EB → 주식교환 → 분할합병 → 기타) 또는 `--priority` 순서로 정렬하며, `--file-key`, `--limit`, `--dry-run`을 지원한다. 입력 JSON은 `cs_index/enrich_inputs/<file_key>.json`, 에이전트 결과 JSON은 `cs_index/enrich_results/<file_key>.json`, 진행/재개 상태는 `cs_index/enrich_progress.json`에 둔다.

`doc_meta`는 기존 통합 `json` 컬럼을 유지하면서 A-1 요구 필드(`parties_json`, `deal_type_detail`, `consideration_json`, `clause_map_json`, `special_notes`, `definitions_json`)를 분리 컬럼으로도 저장하도록 확장했다. 기존 카탈로그는 `enrich_contracts.py` 실행 시 누락 컬럼을 `ALTER TABLE`로 보강한다. 결과 JSON은 필수 키, `meta_schema_version`, `confidence`, `clause_map_json`의 `present`/문단 범위 타입을 검증하고, 실패 시 `doc_meta`에 커밋하지 않는다.

README에 파일 기반 에이전트-스크립트 인터페이스와 재개/증분 동작을 문서화했다. 테스트는 `tests/test_enrich_contracts.py`에 추가했으며 재개, 증분 skip, 우선순위 정렬, dup 대표 처리, 스키마 검증 실패를 mock 결과 JSON으로 검증한다.

검증:
- `python -m pytest -q tests/test_enrich_contracts.py tests/test_scaffold.py` → 6 passed
- Python 3.9 `ast.parse(..., feature_version=(3, 9))` → ok
- `python -m pytest -q` → 100 passed

### 2026-07-11 세션 4 — A-2 샘플 10건 품질 루프

A-1 하네스 인터페이스로 파일럿 `cs_index`의 SPA 10건을 처리했다. 기본 우선순위로
선택된 `2a08ef8b2699dca5`, `e6db8b55a58a1a3a`, `cae8ff1986f4f37e`,
`706b9ca10fa4d2e5`, `9598d3b7fa1e51d7`, `c97356967ef00c57`,
`9800d93256e48009`, `5446bb6dc64f36ba`, `e79f1f0ef05f43ec`,
`a450dcf36d92fa75`에 대해 Codex 세션이 txt 캐시 원문을 읽고
`cs_index/enrich_results/<file_key>.json`을 작성했다. 실제 AI/API 호출은 없었다.

품질 루프 중 A-1 하네스의 txt 캐시 문단 파서가 깨진 `¶` 리터럴에 의존해 입력 JSON
문단이 0개가 되는 결함을 발견했다. 파서를 `[숫자]\t본문` 구조 기반으로 수정하고,
기본 우선순위의 `주식교환`, `분할합병` 문자열도 유니코드 이스케이프로 복원했다.
테스트는 실제 `[¶n]` 캐시 마커를 읽는 케이스를 추가했다.

10건 모두 `doc_meta`에 저장했고, clause_map 위치·confidence·오탐 위험 및
프롬프트 개선 제안은 `A2_SAMPLE_QUALITY_20260711.md`에 정리했다. `extract_prompt_v1.md`와
`term_dict.yaml`은 수정하지 않고 제안만 남겼다.

검증:
- `python enrich_contracts.py --out cs_index --limit 10` → 10 processed, 0 errors
- `python -m pytest -q tests/test_enrich_contracts.py` → 5 passed

### 2026-07-12 세션 5 — A-3 read_contract.py

`read_contract.py`를 구현했다. CLI는 `--out cs_index --file-key K --section 손해배상
[--context N] [--json]`을 지원하며, `doc_meta.clause_map_json`의 `loc_start`/`loc_end`
문단 좌표를 사용해 txt 캐시에서 해당 조항 범위만 출력한다. `--section`은
`data/term_dict.yaml`의 canonical 태그와 동의어로 정규화하므로 `indemnity`도
`손해배상`으로 매칭된다.

상태는 세 가지로 구분한다. `doc_meta`에 해당 canonical 태그가 없으면 `미평가`,
태그가 있지만 `present=false`이면 `평가 후 부재`, `present=true`와 유효 문단 범위가
있으면 조항 본문을 출력한다. `doc_meta.txt_hash`가 현재 `files.content_hash`와 다르면
`재추출 전`을 표시한다. README에 사용법과 상태 의미를 추가했다.

테스트는 `tests/test_read_contract.py`에 추가했다. 조항 범위 정확 출력, 미평가/부재 구분,
stale 표기를 결정적으로 검증한다.

검증:
- `python read_contract.py --out cs_index --file-key c97356967ef00c57 --section 손해배상 --context 0 --json` → 손해배상 ¶151-177만 출력
- `python read_contract.py --out cs_index --file-key e6db8b55a58a1a3a --section 경업금지 --json` → `평가 후 부재`
- `python -m pytest -q tests/test_read_contract.py` → 3 passed

### 2026-07-12 세션 6 — A-4 search_contracts.py T3 clause 필터 활성화

`search_contracts.py`에 예약돼 있던 T3 clause_map 필터를 활성화했다. 새 CLI는
`--clause 태그 [--present | --absent]`이며, 태그는 `data/term_dict.yaml` canonical/동의어로
정규화한다. `--present` 또는 기본 모드는 `doc_meta.clause_map_json`에서 해당 태그의
`present=true` 문서만 후보로 좁히고, `--absent`는 `present=false` 문서만 반환한다.

clause_map에서 해당 태그가 생략된 문서는 `미평가`로 `query.clause.needs_review`에 분리하고,
`present=false`와 혼동하지 않도록 했다. `--absent`에서 `confidence=low` 문서도 결과에서
제외하고 확인 필요로 분리한다. `--json` 결과의 각 문서에는 `clause` 근거(`tag`, `present`,
`loc_start`, `loc_end`, `summary`, `confidence`)를 포함한다. 기존 T1/T2 후보 생성, FTS5,
용어사전 확장, RRF 랭킹, dedup 함수는 유지했다.

테스트는 `tests/test_search_contracts.py`에 추가했다. `--clause` present/absent 필터,
미평가와 부재 구분, keyword 검색과 clause 필터 합성을 검증한다.

검증:
- `python search_contracts.py --out cs_index --clause 손해배상 --present --limit 3 --json` → A-2 샘플 손해배상 present 문서와 clause 근거 출력
- `python search_contracts.py --out cs_index --clause 경업금지 --absent --limit 3 --json` → 평가 후 부재 문서만 결과, 미평가 문서는 needs_review
- `python -m pytest -q tests/test_search_contracts.py` → 16 passed

### 2026-07-12 세션 7 — A-5 T3 골든 문항 + eval 연결

`eval_search.py`가 `--tiers T1,T2,T3`로 실행될 수 있도록 T3 채점 경로를 연결했다.
T1/T2 평가는 기존 메타 필터·키워드·부분채점 흐름을 유지한다. T3 문항은
`expected_filter.clause`가 있을 때 `search_contracts.py`의 `--clause` 경로로 실행하고,
`present`, `clause_present`, `absent` 필드로 존재/부재 채점을 지원한다. clause 조건이 없는
T3 placeholder는 실패가 아니라 `skipped`로 기록한다.

수치 조건용 자리로 `cap_lte`, `cap_gte`, `cap_eq`, `cap_percent_lte`,
`cap_percent_gte`, `survival_months_lte`, `survival_months_gte` 필드를 예약했다.
현재 구조화 수치 필드가 채워지기 전에는 해당 필드를 `unscored_filter_keys`에 남겨
임의 판정하지 않는다. `data/golden_queries.yaml` 데이터는 수정하지 않았다.

`eval_history.jsonl` 누적 로깅은 그대로 유지했고, summary에 `skipped` 카운트를 추가했다.
README에 `--tiers T1,T2,T3` 사용법과 T3 skipped 동작을 문서화했다.

검증:
- `python -m pytest -q tests/test_eval_search.py` → 11 passed
- `python eval_search.py --out cs_index --tiers T1,T2,T3` → 오류 없이 실행, 문항별 pass/fail/skipped 출력 및 `eval_history.jsonl` 누적
