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

### 2026-07-12 세션 8 — 부록 A 완료 검증 + A-2 반영(v2) 정리 (Claude, 파일 도구만)

- **부록 A(A-1~A-5) 완료 검증**: 코드·테스트·progress 로그를 대조해 0단계 전 T3 개발이 전부
  반영됐음을 확인. A-1 enrich_contracts.py 하네스(세션3), A-2 샘플 게이트(세션4),
  A-3 read_contract.py(세션5), A-4 search_contracts T3 clause 필터(세션6),
  A-5 eval `--tiers T1,T2,T3`(세션7). 각 항목 테스트 포함, 부록 A 자체에는 미반영 없음.
- **0단계 전 남은 항목 식별(부록 C)**: A-2 게이트에서 소유자가 전량 수용한 프롬프트 개선
  #1~#7이 하네스/데이터에 아직 활성화되지 않음. 프롬프트는 `.docs/extract_prompt_v2.md`
  (meta_schema_version 2)로 작성돼 있으나, `enrich_contracts.py`는 `META_SCHEMA_VERSION=1`이고
  손해배상 하위필드 강제·`present` 필수 검증이 없음. 이 반영은 `NEXT_STEPS.md` 부록 C
  (C-0 데이터 무결성 확인, C-1 하네스 v2 강화, C-2 샘플 재추출)에 Codex 프롬프트로 스테이징함.
  코드 변경+테스트 실행이 필요해 이 세션(파일 도구만 가용, 샌드박스 시작 실패)에서는 직접
  구현하지 않고 프롬프트로 남김.
- **문서 반영**: `NOTES_FOR_OWNER.md`에 A-2 전량 수용 결정과 v2 상태·미반영 항목 기록.
  `NEXT_STEPS.md`에 초보자용 "지금부터 할 일"(부록 D) 추가.
- **git**: 이 세션은 커밋 실행 불가(샌드박스 시작 실패). 아래 커밋 명령을 소유자 실행용으로 남김.
  - `git add .docs/extract_prompt_v2.md NEXT_STEPS.md NOTES_FOR_OWNER.md progress.md`
  - `git commit -m "docs: verify Appendix A complete; stage A-2 v2 reflection (prompt v2 + Appendix C/D)"`

### 2026-07-12 세션 9 — NEXT_STEPS 부록 D 실행: enrich 하네스 v2 강화 (Codex)

- **C-0/D-1 데이터 무결성 확인**: `cs_index/catalog.sqlite`의 `doc_meta.clause_map_json`을 직접
  확인해 `손해배상`, `진술보장` 등 조항 키가 정상 한글 태그로 보존되어 있음을 확인했다.
- **C-1/D-2 하네스 v2 반영**: `enrich_contracts.py`의 `META_SCHEMA_VERSION`을 2로 올리고,
  v1 `doc_meta`가 재추출 대상으로 잡히는지 테스트했다. `clause_map_json`에 들어온 평가 태그는
  `present`가 반드시 boolean이어야 하며, `present=null` 또는 누락은 `EnrichError`로 거부한다.
  `손해배상.present=true`인 경우 `cap_verbatim`, `basket_verbatim`, `de_minimis_verbatim`,
  `survival_verbatim` 4개 필드를 필수로 검증하고, 미확인 값은 `"not confirmed"` 문자열만 허용한다.
- **C-2/D-3 샘플 10건 v2 재검증**: A-2와 동일한 SPA 10건을 v2 결과 JSON으로 정규화해
  `python enrich_contracts.py --out cs_index --limit 10`으로 재적재했다. 결과는 10 processed,
  0 errors. 재실행 skip도 `--file-key 2a08ef8b2699dca5 --dry-run`에서 candidate 0으로 확인했다.
  비교 보고서는 `A2_SAMPLE_QUALITY_v2_20260712.md`에 기록했다.
- **문서 반영**: README의 T3 enrich 하네스 설명을 v2 기준으로 갱신했다.

검증:
- `python -m pytest -q tests/test_enrich_contracts.py` → 10 passed
- `python -m pytest -q tests/test_read_contract.py tests/test_search_contracts.py tests/test_eval_search.py` → 30 passed
- `python -m pytest -q` → 116 passed (pytest cache warning 1건, 테스트 실패 아님)

### 2026-07-12 세션 10 — contract_docs 전체 full 재색인 + T1/T2/T3 eval (Codex)

- **전체 재색인 실행**: `contract_docs`를 `cs_index`로 full 재색인했다.
  실행 명령은 `python index_contracts.py --root contract_docs --out cs_index --full --batch-label full_001`.
  첫 2회는 제한시간(2분, 15분)에 걸려 중단됐고, 동일 명령을 재실행해 완료했다.
- **색인 결과**: 실행 로그 기준 2,244개 파일을 스캔했고, 현재 `catalog.sqlite` 기준 레코드는
  2,106건이다. 상태별 현재 레코드는 `ok=1,519`, `empty=48`, `error=1`, `unsupported=538`.
  언어별로는 `국문=1,345`, `영문=742`, `국영문=19`.
- **검색 불가/제외 유형**:
  - `unsupported=538`: `.doc` 502건, `.jpg` 34건, `.xlsx` 1건, `.eml` 1건
  - `empty=48`: 모두 PDF이며 `pdf_text_empty`(스캔 PDF 등 본문 텍스트 없음)
  - `error=1`: DOCX 추출 실패 1건(`docx_extract_failed`), MOU 파일 1건
- **평가 실행**: `python eval_search.py --out cs_index --tiers T1,T2,T3` 실행 완료.
  결과는 `total=33`, `pass=6`, `fail=2`, `unscored=16`, `skipped=9`, `partial=25`.
  T1/T2 일부 필터 문항은 통과했으나, full 재색인으로 `doc_meta`가 비어 T3 조항 문항은 대부분
  미평가/skipped 상태이며 기대 파일이 있는 T3 문항 2개는 현재 0건 반환으로 fail 처리됐다.
- **다음 의미**: 전체 색인은 끝났고, 다음 단계는 `enrich_contracts.py` v2로 전체 `doc_meta`
  조항맵을 채우는 배치다. 그 후 T3 eval을 다시 실행해야 조항 검색 품질이 실제로 측정된다.

검증/산출물:
- 색인 리포트: `cs_index/report_20260712.md`
- 평가 로그: `cs_index/eval_history.jsonl`에 누적

### 2026-07-12 세션 12 - T3 enrich 배치 20건 처리 (Codex)

- `python enrich_contracts.py --out cs_index --limit 20`로 다음 SPA 우선순위 20건의 입력 JSON을 생성했다.
- 각 입력 JSON의 txt 캐시 문단을 로컬로 읽어 `.docs/extract_prompt_v1.md`의 조항 범위 기준으로 결과 JSON을 작성했다. 현재 하네스는 schema v2 기준이므로 `present` 필드와 손해배상 하위 근거(`cap_verbatim`, `basket_verbatim`, `de_minimis_verbatim`, `survival_verbatim`)도 함께 채웠다.
- 결과 JSON을 다시 `enrich_contracts.py`로 검증 및 저장해 `doc_meta`에 반영했다.
- 처리 결과: 성공 20건, 실패 0건, 보류 0건. `doc_meta`의 schema v2 레코드는 누적 30건이 되었다.
- 낮은 신뢰도 문서 2건은 긴 PDF/대형 DOCX라 조항 위치는 저장했지만 후속 샘플 점검 때 우선 확인이 필요하다: `0ddde0e62bd84e41`, `ac3103e193f693ed`.

검증:
- `python enrich_contracts.py --out cs_index --limit 20` -> `processed_count=20`, `error_count=0`, `pending_count=0`
- `python enrich_contracts.py --out cs_index --file-key 156c3a81342d4697 --dry-run` -> `candidate_count=0` (증분 skip 확인)
- SQLite 확인 -> 이번 배치 20건 조회 성공, `doc_meta` schema v2 누적 30건

### 2026-07-12 세션 13 - 부록 B convert_doc.py 구현 (Codex)

구현 계획:
- 원본 `.doc`는 읽기 전용으로만 다루고, 변환본과 매니페스트는 `cs_index/converted/` 아래에 둔다.
- `convert_doc.py`는 표준 라이브러리 `subprocess`로 PowerShell worker를 호출하고, 새 파이썬 패키지는 추가하지 않는다.
- 변환본 파일명은 원본 바이트 sha256 기반으로 만들어 충돌을 피하고, `manifest.json`으로 증분 skip과 재개를 관리한다.
- `index_contracts.py`는 변환본이 있는 `.doc`만 `.docx`로 추출하되, 카탈로그에는 원본 `.doc` 경로와 원본 파일명을 기준으로 기록한다.
- Word가 없거나 샘플 `.doc`가 없는 환경에서도 단위 테스트는 mock으로 결정적으로 통과하고, 실제 Word 통합 테스트는 환경변수가 있을 때만 실행한다.

완료:
- `convert_doc.py`와 `convert_doc_worker.ps1` 구현.
- `index_contracts.py`에 변환 매니페스트 연동 추가.
- 테스트 추가: 증분 skip, mock 변환 성공, RTF/zip 오인 `.doc` 기록, 청크 실패 격리 후 재개, Word 미설치 중단, dry-run 비기록, 변환본 색인 연동.

검증:
- `python -m pytest -q tests/test_convert_doc.py tests/test_index_contracts.py` -> 35 passed, 1 skipped
- `python -m pytest -q` -> 124 passed, 1 skipped

### 2026-07-12 세션 14 - 웹 UI-2 운영 대시보드 + UI-3 리서치 UI 완료 (Codex)

- UI-2 운영 대시보드 구현: `/operations` 화면과 `/api/ops/dashboard`, `/api/ops/failures`, `/api/ops/manual-overrides/export`를 추가했다. 색인 상태, 실패/본문 없음 문서, batch 통계, 미분류 폴더, 최근 job, 저장 검색/피드백 요약을 확인할 수 있다.
- UI-2 저장 검색/피드백 구현: `/api/saved-searches`, `/api/feedback`를 추가하고 검색 화면에서 현재 검색 저장 및 결과 피드백을 남길 수 있게 했다.
- UI-3 리서치 UI 구현: `/research` 화면과 북마크/메모(`/api/marks`), 기본 비교 목록(`/api/compare/default`), 리서치 세션(`/api/research/sessions`), 선택 문단 Markdown export(`/api/export/paragraphs`)를 추가했다.
- 사용자 상태는 계속 `cs_index/ui_state.sqlite`에 저장하고, `catalog.sqlite`에는 사용자 테이블을 만들지 않는 경계를 테스트로 확인했다.
- 검색 화면 상단에 운영/리서치 링크를 추가하고, 결과 카드에 비교 추가/북마크/피드백 버튼을 추가했다.

검증:
- `python -m pytest -q tests/test_webapp.py tests/test_webapp_jobs.py` -> 23 passed
- `python -m pytest -q` -> 127 passed, 1 skipped

### 2026-07-12 세션 15 - .doc 변환 배치 완료 + full 재색인 (Codex)

- `convert_doc.py --root contract_docs --out cs_index --chunk-size 1 --timeout 180`로 남은 Word 변환 실패 16건을 재시도했다.
- PowerShell Word COM 환경에서 긴 `Documents.Open(...)` 선택 인자 호출이 실패하는 경우가 있어, 안전 옵션 우선 시도 후 기존 읽기전용 3인자 호출로 fallback하도록 `convert_doc_worker.ps1`를 보강했다.
- 변환 매니페스트 결과: `ok=557`, `unsupported=5`. 남은 5건은 확장자만 `.doc`이고 실제 내용은 RTF(`not_ole2_rtf`)라 변환 대상에서 제외했다.
- `python index_contracts.py --root contract_docs --out cs_index --full --batch-label full_doc_converted`로 변환본을 포함해 전체 재색인했다.
- 카탈로그 상태: `ok=2016`, `empty=48`, `error=1`, `unsupported=41`. 이 중 `.doc`은 `ok=497`, `unsupported=5`로 기록되었고, `source_format=doc_converted` 문서 497건이 검색 가능 상태다.
- `python eval_search.py --out cs_index --tiers T1,T2,T3` 결과: `total=33`, `pass=16`, `fail=1`, `unscored=8`, `skipped=8`, `partial=25`.

검증:
- `python -m pytest -q tests/test_convert_doc.py tests/test_index_contracts.py` -> 35 passed, 1 skipped
- `python convert_doc.py --root contract_docs --out cs_index --dry-run` -> `candidate_count=0`, `failure_count=5`(모두 `not_ole2_rtf`)

### 2026-07-12 세션 16 - T3 전량 초벌 보강 + SHA/MOU/ATA-BTA 품질 표본 (Codex)

- 사람이 직접 채워야 하는 `data/golden_queries.yaml` 정답 입력은 제외하고, 로컬 txt 캐시로 가능한 작업을 진행했다.
- `doc_meta` v2가 없는 ok 대표 문서 1,969건의 결과 JSON을 결정적 로컬 추출 방식으로 생성하고, `python enrich_contracts.py --out cs_index --limit 2500`로 하네스 검증 후 저장했다.
- 결과: `candidate_count=1969`, `processed_count=1969`, `error_count=0`, `pending_count=0`.
- 전량 확인: ok 대표 문서 1,999건과 `doc_meta` v2 1,999건이 일치하며, remaining/stale 모두 0이다.
- 유형별 v2 메타 누적: SPA 672, SHA 367, MOU 104, ATA/BTA 211, SSA 373, JVA 53.
- SHA/MOU/ATA-BTA 각 5건 품질 표본을 `T3_QUALITY_SHA_MOU_ATA_BTA_20260712.md`에 정리했다. 자동 키워드-문단 대조 기준 4개 항목은 수동 재확인 대상으로 표시했고, `extract_prompt_v1.md`와 `term_dict.yaml`은 수정하지 않았다.
- `python eval_search.py --out cs_index --tiers T1,T2,T3` 결과: `total=33`, `pass=17`, `fail=1`, `unscored=7`, `skipped=8`, `partial=25`.

검증:
- `python enrich_contracts.py --out cs_index --limit 5 --dry-run` -> `candidate_count=0`
- `python -m pytest -q tests/test_enrich_contracts.py tests/test_read_contract.py tests/test_search_contracts.py tests/test_eval_search.py` -> 40 passed

### 2026-07-16 세션 17 - 웹앱 병행 읽기 전용 MCP 어댑터 추가 (Codex)

- 기존 웹앱과 CLI를 유지하면서 `mcp_server.py` 로컬 stdio 어댑터를 추가했다. 검색·조항 정독·문단 읽기·파일 점검·중복 확인·코퍼스 상태·필터 조회의 7개 도구를 제공한다.
- MCP는 기존 `search_contracts.py`, `read_contract.py`, `open_text.py`, `inspect_file.py` 코어를 직접 재사용하며 색인·설정·사용자 상태를 변경하지 않는다. 쓰기 작업은 계속 웹앱의 단일 job queue가 담당한다.
- 서버 instructions에 file_key 인용, 부재 판정, 미평가 구분, 중복 제거, 5건 이내 부분 정독 등 검색 에이전트 원칙을 포함했다.
- MCP 응답에서는 로컬 txt 캐시 절대경로를 제거하고 필요한 검색 스니펫과 조항 문단만 반환한다.
- 공식 MCP Python SDK는 선택 의존성 `requirements-mcp.txt`로 분리하고 안정판 `mcp==1.28.1`을 고정했다. 기본 `requirements.txt` 설치만으로 웹앱과 CLI는 계속 동작한다.
- README에 설치, `--check`, AI 클라이언트 stdio command/args 등록 예시를 추가했다.

검증:
- `python -m pytest -q tests/test_mcp_server.py` -> 4 passed
- 검색·조항·웹앱 관련 회귀 테스트 -> 52 passed
- `python -m pytest -q` -> 139 passed, 1 skipped
- `python mcp_server.py --out cs_index --check` -> 정상, searchable 2,016건·unsearchable 49건 확인

### 2026-07-16 세션 18 - T3 v3 정밀 보강 파일럿 준비 (Codex)

- 기존 `doc_meta` v2 1,999건을 보존하면서 v3를 별도 입출력 폴더에서 검증하는 경로를 추가했다.
- `t3_schema.py`에 당사자·대금·정의의 평가 상태, 유형별 필수 조항, present 조항의 위치·원문,
  정규화 수치와 항목별 confidence 검증을 구현했다.
- `plan_t3_v3_pilot.py`로 유형·언어·Draft·기존 신뢰도를 층화한 60건을 선정하고
  `cs_index/enrich_inputs_v3`, manifest, 사람 검수표를 생성했다.
- `audit_t3_v3.py`로 DB 저장 전 스키마·문단 위치·verbatim·정규화 수치 근거를 자동 점검하도록 했다.
- `search_contracts.py`, 웹앱 API, MCP 검색에 당사자명/역할, 지급 방식·대금 범위,
  손해배상 상한 비율, 존속기간, 준거법, 법원·중재기관 조건을 추가했다.
- 구조화 조건에서 v2 문서를 불일치·부재로 오판하지 않고 `needs_review` 미평가로 분리한다.
- `.docs/extract_prompt_v3.md`, `.docs/T3_V3_PILOT.md`와 README 운용 절차를 추가했다.

실데이터 파일럿:
- 60건: SPA 8, SHA 8, SSA 6, MOU 6, ATA/BTA 5, 기타 27.
- 언어: 국문 39, 영문 18, 국영문 3.
- Draft 상태: Draft 18, 비Draft 21, 미상 21.
- 기존 신뢰도: low 47, med 9, high 4.
- v3 입력 60건 생성 완료, 결과 JSON은 60건 모두 대기. 기존 catalog.sqlite에는 v3를 기록하지 않았다.

검증:
- `python -m pytest -q tests/test_mcp_server.py tests/test_webapp.py tests/test_search_contracts.py tests/test_t3_v3.py tests/test_enrich_contracts.py` -> 57 passed
- `python audit_t3_v3.py --manifest cs_index/t3_v3_pilot_manifest.json` -> total=60, pending=60, error=0

### 2026-07-16 세션 19 - T3 v3 대표 10건 결과 생성 + 사람 검증표 (Codex)

- 60건 층화 파일럿 중 유형·언어·Draft·문서 성격을 대표하는 10건을 선정해
  `cs_index/enrich_results_v3/<file_key>.json` 결과를 생성했다. 유료 API는 호출하지 않았으며,
  로컬 txt 캐시의 관련 조항만 부분 정독해 당사자·대금·정의·필수 조항·정규화 수치와 원문 위치를 채웠다.
- 문서 자체가 계약서인지 먼저 판정하도록 v3에 `document_status=contract|not_contract|insufficient_text`를
  추가했다. 비계약 문서는 당사자·대금·정의·조항을 추측하지 않고 명시적으로 미평가 처리한다.
  `t3_schema.py`, `enrich_contracts.py`, `.docs/extract_prompt_v3.md` 및 관련 테스트를 함께 보강했다.
- 대표 10건 판정은 계약 8건, 비계약 2건이다. 비계약 2건은 각각 법률자문 킥오프 자료와
  주식교환 관련 법률의견서였다. 별도로 색인상 `주식교환`이지만 실제 내용은 CJ-네이버
  사업제휴 합의서인 분류 불일치 1건도 확인해 `deal_type_detail`과 검토 메모에 기록했다.
- 사용자가 JSON을 직접 읽지 않아도 검증할 수 있도록
  `cs_index/t3_v3_human_review_10.md`를 생성했다. 문서 판정, 실제 거래유형, 당사자·역할,
  거래대금, 존재 조항의 AI 요약·원문 인용·문단 위치·정규화 값과 체크 칸을 문서별로 제공한다.
- `audit_t3_v3.py`가 `3년→36개월`, `[1]년→12개월` 같은 정규화 단위 환산을 원문 근거로
  인정하도록 보강하고 회귀 테스트를 추가했다.
- 대표 결과는 사람 승인 전 검토용으로만 두었으며 `catalog.sqlite`에는 v3를 저장하지 않았다.
  기존 `doc_meta` v2 1,999건은 그대로 유지된다.

검증:
- `python audit_t3_v3.py --manifest cs_index/t3_v3_pilot_manifest.json` -> `pass=10`, `review=0`, `error=0`, `pending=50`
- v3 결과 JSON 10건, 사람 검증표 1건 생성 확인
- `python -m pytest -q tests/test_t3_v3.py` -> 7 passed
- `python -m pytest -q` -> 150 passed, 1 skipped
- `git diff --check` -> 오류 없음(기존 Windows LF/CRLF 경고만 출력)

### V4 다음 단계 - 세부 조항 원자 항목 분류(계획 확정, 미구현)

- v3 결과가 정확하다는 전제 아래, v4는 v3를 덮어쓰지 않고 `진술보장`·`선행조건`·`확약`
  아래의 세부 의미를 검색 가능한 원자 항목으로 저장하는 계층으로 설계한다.
- 단순히 긴 세부 태그를 계속 추가하지 않고, `조항 유형 + 분야 + 세부주제 + 행위/쟁점 + 대상 +
  시점 + 주체 + 원자적 명제`를 분리한다. 예: `진술보장/노무/임금/미지급임금 없음`,
  `선행조건/종결서류/이사 사임서 제출`, `확약/정부신고/기업결합신고서 제출`.
- 조항의 부재와 부정형 진술을 구분한다. 예를 들어 “미지급임금이 없음”은 미지급임금 관련
  진술보장이 존재하는 것이며, 해당 세부 조항이 없는 것으로 저장하지 않는다.
- 예정 저장 구조는 통제 분류체계 `v4_taxonomy_node`, 표현 변이 `v4_taxonomy_alias`,
  문서별 원자 항목 `v4_clause_item`, 평가완료·부분평가·미평가를 구분하는
  `v4_document_coverage`, 신규 분류 검토 큐 `v4_taxonomy_candidate`이다.
- 신규 표현은 즉시 정식 태그로 만들지 않는다. 기존 분류와 의미가 같으면 alias, 대상만 다르면
  object/qualifier로 저장하고, 독립적인 검색 의도와 법적 의미가 있는 경우에만 후보→검토→승인 후
  정식 taxonomy로 승격한다.
- 구현 순서는 v4 스키마·초기 taxonomy·추출 프롬프트와 감사기 구축 → 현재 대표 10건 재추출 →
  기존 60건 파일럿으로 taxonomy 발견·안정화 → CLI·웹·MCP 세부 검색/비교 기능 → 골든 질의 평가 →
  전체 계약 순차 확장으로 정했다.
- 전체 확장에서도 프로젝트가 유료 API를 자동 호출하지 않는 원칙을 유지한다. AI 클라이언트가
  MCP 또는 파일 기반 작업으로 문서별 필요한 조항만 읽고 결과를 제출하며, 서버는 검증·저장만 담당한다.

### 2026-07-16 세션 20 — V4 계획 검토·확정: `.docs/V4_PLAN.md` (Claude)

- 위 V4 초안을 검토해 `.docs/V4_PLAN.md`로 확정했다. 초안 대비 변경·추가 사항:
  - **적용 범위**: 전 항목 추출 대상을 SPA·SSA·ATA/BTA에 **SHA 추가**(소유자 지시).
    나머지 유형은 v3 유지, agent_log 수요 확인 시 유형 단위 편입.
  - **taxonomy 거버넌스 UI(UI-5)**: 신규 분류 후보의 승격·alias 병합·반려를 웹앱
    `/taxonomy` 화면에서 **버튼 클릭만으로** 처리(소유자 지시 — 이후 개발 없이 운영 가능
    해야 함). 초기 seed는 family/domain 2단계까지만, 3단계는 후보 큐에서 UI로만 승격.
    DB 테이블이 taxonomy 단일 원천, yaml은 내보내기 산출물. `UI_ROADMAP.md`에 UI-5 추가.
  - **하이브리드 검색**: taxonomy 필터 ∪ 항목 텍스트 FTS(`v4_item_fts`) ∪ 문단 FTS
    합집합 — 분류 오류를 recall 손실이 아닌 순위 하락으로 강등(누락 방지의 핵심).
  - **coverage 본문/별지 분리**: 부재 판정은 body+annex 평가 완료 시에만 허용,
    스캔 별지 미평가 건수 상시 고지.
  - **term_dict 통합**: 진술보장 하위 주제 항목을 v4 노드에 1:1 매핑/alias 흡수,
    `term_dict_tools.py --validate`에 매핑 검증 추가.
  - **추출 경로 단순화**: 신규 MCP 추출 도구 대신 검증된 enrich 파일 하네스 재사용
    (`enrich_inputs_v4`/`enrich_results_v4` + `audit_t3_v4.py`). MCP는 질의 쪽
    `search_clause_items`·`compare_clause_items` 2개만 추가. 결정적 로컬 추출로
    대체 금지(v2 초벌의 한계가 v4를 하는 이유).
  - **이중 게이트**: 자체 품질 게이트 A에 더해, 세부 골든 질의 30~50개로
    (a) v3+MCP 에이전트 정독 vs (b) v4 하이브리드를 비교하는 **게이트 B**를 전량 확장
    조건으로 추가. (b)가 recall 우위가 아니면 부재 판정·비교 기능만 남기는 축소판 전환.
  - **선행 게이트**: V4-0 = v3 파일럿 60건 사람 승인. 승인 전 V4 착수 금지.
- 관련 문서 갱신: `.docs/UI_ROADMAP.md`(UI-5 + 우선순위), `.docs/T3_V3_PILOT.md`(다음
  단계 포인터), `.docs/MANIFEST.txt`. 코드 변경 없음.

### 2026-07-16 세션 21 — T3 v3 대표 10건 QA + 소유자 지시 정정 (Claude)

- 대표 10건을 원문과 독립 대조(`cs_index/qa_v3_10.py`)해 QA 리포트
  `cs_index/t3_v3_qa_10.md`를 생성했다. verbatim↔문단 위치는 10건 전부 100% 일치,
  비계약 2건도 정상 처리. present 조항 정규화 수치 1건이 원문 미근거로 확인됐다.
- 소유자 지시 반영: 753aeef4 진술보장 present=true(¶109 원용 근거, med),
  37c9a8 선행조건은 부재 유지, dc3b4d MAC 부재판정 유지 + 근거 메모.
- 37c9a8 손해배상액 예정은 제11조(주식양도제한) 위반 시 1억원 지급으로,
  거래무산 위약금이 아님을 원문(¶104) 확인 → `break_fee_amount` 매핑 제거.
- 753aeef4 풋옵션의 근거없는 `closing_days:60/interest_rate_pct:10` 제거,
  loc를 소제목→운영문단(108–111)으로 확장, verbatim 교체.
- `.docs/extract_prompt_v3.md`에 지침 11–15 추가(정규화 숫자 근거 강제, verbatim 소제목 금지,
  다문단 loc, 부재 근거메모, break_fee 오용 금지).
- `audit_t3_v3.py` 숫자-근거 검사를 3필드→전체 숫자형 필드로 확장, 콤마·억/만·대괄호 표기 인정.

검증:
- `python audit_t3_v3.py --manifest cs_index/t3_v3_pilot_manifest.json` -> pass=10, review=0, error=0
- 감사기 음성테스트: 근거없는 60/10 탐지, 콤마 5억·[1]년→12개월 정상 통과
- `python -m pytest -q tests/test_t3_v3.py tests/test_enrich_contracts.py` -> 17 passed

### 2026-07-16 세션 22 — T3 v3 국문 우선 배치 01 추출·감사·QA (Codex)

- V4-0 게이트의 남은 50건 중 국문 우선 10건을 부분 정독했다: SPA 4건, SHA 3건,
  SSA 2건, MOU 1건. `cs_index/enrich_results_v3/<file_key>.json` 10건과
  `cs_index/t3_v3_human_review_batch_01.md`를 생성했다. 유료 API와 DB 쓰기는 사용하지 않았다.
- 부속합의서·Joinder가 원 SPA/SHA를 포괄 원용해도 현재 파일에 조문이 재현되지 않으면
  해당 조항을 추측하지 않았다. MOU의 향후 본계약 진술보장, SSA의 조세 진술보장 존속기간,
  매도인 명의 계약금 계좌도 각각 현재 진술보장·독립 조세배상·에스크로로 오분류하지 않았다.
- 최초 감사에서 인용 위치·문구 불일치 4건을 원문에 맞게 정정했다. 감사기가 `0.5억원` 같은
  소수 억 단위 금액을 인식하도록 보강하고 회귀 테스트를 추가했다.
- 배치 종합 QA 리포트 `cs_index/t3_v3_qa_batch_01.md`를 생성했다. 원문 근거가 있는
  present 조항 81개는 모두 지정 문단과 일치하고 정규화 숫자도 근거 검사를 통과했다.
- 배치 결과는 pass 7, review 3이다. review 3건(`0ddde0e62bd84e41`,
  `2a08ef8b2699dca5`, `a5da55951cfdabfb`)은 오류가 아니라 당사자·대금·책임제한 등이
  공란인 초안이므로 사람 확인 대상으로 유지했다.
- V4-0 누적 상태는 결과 생성 20/60, pass 17, review 3, error 0, pending 40이다.
  사람 승인 전이므로 `catalog.sqlite`에는 v3 결과를 기록하지 않았다.

검증:
- `python audit_t3_v3.py --manifest cs_index/t3_v3_pilot_manifest.json` -> `pass=17`, `review=3`, `error=0`, `pending=40`
- `python -m pytest -q tests/test_t3_v3.py tests/test_enrich_contracts.py` -> 18 passed

### 2026-07-16 세션 23 — v3 공란 처리 기준 소유자 확인 (Codex)

- 소유자가 당사자명·매매대금·배상상한 등 원문 입력값이 공란이면 값 없음으로 반영하도록
  확인했다. 공란 당사자는 임의 생성하지 않고, 공란 금액·비율은 `null` 또는 정규화 필드
  미생성으로 유지한다.
- 배치 01 결과 JSON은 이미 이 원칙대로 작성되어 있어 수정이 필요하지 않았다.
  `cs_index/t3_v3_qa_batch_01.md`에 소유자 확인 기록을 추가하고 관련 공란 체크 항목을 승인 처리했다.
- `review` 3건은 자동감사 오류가 아니라 초안 문서의 `low` 신뢰도 표시이므로 그대로 유지한다.
  남은 사람 확인은 원문에 실제 기재된 수치·조항의 법률적 의미 판정뿐이다.

### 2026-07-16 세션 24 — 배치 01 전건 사람 승인 + SHA 참조금액 구분 (Codex)

- 소유자가 배치 01의 남은 법률적 의미 판정을 모두 승인했다. 원문 재대조 결과
  `a5da55951cfdabfb`의 300억원은 현재 SHA 자체 대금이 아니라 별도 신주인수계약의
  RCPS 투자금액이고, Drag-along은 투자대상회사 별도 SHA상 권리이며, IRR 15% 초과분의
  10% 지급은 거래대금 earn-out이 아닌 주주간 초과이익 배분이라는 판정을 확정했다.
- `a5da55951cfdabfb`의 현재 SHA 대금은 `amount_value=null`로 바꾸고, 300억원은
  `definitions_json`의 `관련 신주인수계약 투자금액`으로 보존했다. 따라서 SHA 자체 대금
  범위 검색에서 300억원으로 오인되지 않는다.
- `동반매도요구권.present=false`, `earn-out.present=false`, `has_earnout=false`는 유지했다.
  다만 별도 Drag-along의 행사 효과와 초과이익 배분 내용은 원문 위치·검토 메모에 남겼다.
- `cs_index/t3_v3_human_review_batch_01.md`의 문서별·조항별 확인란과 배치 승인란을 모두
  승인 완료로 기록했다. `cs_index/t3_v3_qa_batch_01.md`에도 사람 승인 10/10을 반영했다.
- 자동감사 결과의 `review=3`은 공란이 있는 초안의 `low` 신뢰도 표시로 유지되며,
  미승인 상태를 뜻하지 않는다. V4-0 사람 승인 누계는 배치 01의 10/60건이다.
  결과 생성 누계는 20/60건이며, 나머지 40건 추출·감사·사람 승인이 남았다.
- 전체 60건 승인 전이므로 `catalog.sqlite`에는 v3 결과를 기록하지 않았다.

검증:
- `python audit_t3_v3.py --manifest cs_index/t3_v3_pilot_manifest.json` -> `pass=17`, `review=3`, `error=0`, `pending=40`
- `python -m pytest -q tests/test_t3_v3.py tests/test_enrich_contracts.py` -> 18 passed

### 2026-07-16 세션 25 — T3 v3 국문 중심 혼합유형 배치 02 추출·감사·QA (Codex)

- V4-0 게이트에서 결과가 없던 40건 중 국문 중심 혼합유형 10건을 부분 정독했다:
  SSA 1건, ATA/BTA 2건, JVA 1건, 공동투자 1건, BW 1건, EB 2건,
  주식교환 1건, MOU 1건. `cs_index/enrich_results_v3/<file_key>.json` 10건과
  `cs_index/t3_v3_human_review_batch_02.md`를 생성했다. 유료 API와 DB 쓰기는 사용하지 않았다.
- 당사자명·대금·교환비율 등 원문 입력값이 없으면 `null` 또는 정규화 필드 미생성으로
  처리했다. 실사 후 합의할 MOU 대금, 총액 없는 공동출자, 공란인 주식교환비율을 임의 보충하지 않았다.
- `d52f0cbc2a9171bb`의 800억원은 현재 변경계약의 신규 대금이 아니라 원 교환사채인수계약의
  전자등록총액이므로 현재 대금은 `null`로 두고 정의·메모에만 참조금액으로 보존했다.
- 비구속 MOU의 별첨·거래범위 제안은 현재 확정 의무와 구분했다. `30fae2c6d27a9f8c`의
  500억원, 선행조건과 경업금지는 비구속 별첨 조건으로 표시했고, `b0a1cc03cb0baa69`의
  임직원·자산·부채 승계도 비구속 거래범위 제안으로 신뢰도를 낮췄다.
- `584a623ee466906c`와 `c06cdd8feff8b75b`는 각각 손상된 JVA 중간 조각과 BW 비교본 조각이라
  당사자·대금·조항을 추측하지 않고 `document_status=insufficient_text`로 분리했다.
- 배치 QA 리포트 `cs_index/t3_v3_qa_batch_02.md`를 생성했다. present 조항 64개는 모두
  지정 문단과 일치하고 정규화 숫자도 원문 근거 검사를 통과했다.
- 이번 배치 결과는 pass 5, review 5, error 0이다. review 5건은 초안·공란 또는 본문 추출
  불충분에 따른 낮은 문서 신뢰도이며 자동감사 오류는 없다.
- V4-0 누적 상태는 결과 생성 30/60, pass 22, review 8, error 0, pending 30이다.
  배치 02는 사람 검토 대기이며, 사람 승인 누계는 10/60건이다. 전체 승인 전이므로
  `catalog.sqlite`에는 v3 결과를 기록하지 않았다.

검증:
- `python audit_t3_v3.py --manifest cs_index/t3_v3_pilot_manifest.json --input-dir cs_index/enrich_inputs_v3 --result-dir cs_index/enrich_results_v3 --report cs_index/t3_v3_audit_report.json` -> `pass=22`, `review=8`, `error=0`, `pending=30`
- `python -m pytest -q tests/test_t3_v3.py` -> 8 passed

### 2026-07-16 세션 26 — T3 v3 최종 30건 추출·전건 승인·V4-0 통과 (Codex)

- 배치 03~05 각 10건을 원문 부분 정독해 `enrich_results_v3` 60건을 완성했다. 공란 당사자·대금·배상상한은 값 없음으로 두고, 별도 계약의 금액·권리와 비구속 제안은 현재 계약의 확정값으로 승격하지 않았다.
- `c28dbecbb5bac628` 초안은 가액·비율 공란, `7084be8d0c8a3f68` 체결본은 현물출자가액 129,605,780,224원과 분할·분할합병대금 590,426,332,130원을 서로 다른 구성가치로 보존하고 임의 총액을 만들지 않았다.
- `dbccf24bc86783f4`는 매수인명·기초가격·에스크로가 미확정인 Buyer First Markup, `a51842fc51010f69`은 1,130억원 기초대금과 5억6500만원 basket이 명시된 체결본으로 구분했다.
- Kurly·Danggeun SHA의 별도 SSA 투자금은 현재 SHA 대금으로 넣지 않았고, FnStars Term Sheet의 USD 11.1m·USD 5m는 비구속 제안값으로 표시했다. 영문 BTA 양식의 당사자·대금 공란은 `null`로 유지했다.
- 자동 감사 결과는 총 60건, pass 42, review 18, error 0, pending 0이다. review 18건에는 근거 이슈가 없으며 초안·공란·양식에 따른 low 신뢰도 표시다.
- 소유자의 원문검토 위임·나머지 승인 지시에 따라 `t3_v3_human_approval_60.json`과 `t3_v3_v4_0_gate.md`에 60/60 승인을 기록했다.
- 승인 범위를 정확히 저장하는 `store_t3_v3_manifest.py`를 추가해 manifest 60건만 `doc_meta` v3로 저장했다. 결과는 processed=60, stored=60, error=0이다.

검증:
- `python audit_t3_v3.py ...` -> pass=42, review=18, error=0, pending=0
- `python eval_search.py --out cs_index --tiers T1,T2,T3` -> pass=17, fail=1, unscored=7, skipped=8 (기존 Q28 1건 실패 유지, 신규 회귀 없음)
- T3·검색·MCP 관련 테스트 -> 41 passed

### 2026-07-16 세션 27 — V4-1 원자항목 기반·coverage·감사기 구현 (Codex)

- 기존 v3를 변경하지 않는 additive V4 스키마를 `v4_schema.py`에 구현하고 `catalog.sqlite`에 초기화했다: taxonomy node 43, alias 168, clause item 0, coverage 0.
- `v4_clause_item`과 trigram FTS, `v4_document_coverage`의 body/annex 분리 상태, `v4_taxonomy_candidate` 후보 큐와 taxonomy 버전 메타를 추가했다.
- 초기 taxonomy는 계획대로 family/domain 2단계까지만 seed하고 topic은 만들지 않았다. 신규 topic은 후보 큐와 향후 UI 승격 절차를 거친다.
- `statement_polarity=none_exist`를 지원해 “미지급임금이 없음”을 진술보장 존재로 저장하며, 부재 판정은 body complete + annex complete/no_annex일 때만 허용한다.
- `.docs/extract_prompt_v4.md`와 `audit_t3_v4.py`를 추가했다. 감사기는 taxonomy ID·family·문단 위치·verbatim·정규화 숫자 근거·coverage·후보 근거를 검사한다.
- `data/v4_term_mapping.yaml`에 term_dict의 진술보장 하위 7개 검색축을 V4 RW domain에 연결하고 `term_dict_tools.py --validate`가 누락·잘못된 taxonomy ID를 검증하도록 보강했다. `data/term_dict.yaml` 자체는 수정하지 않았다.

검증:
- `python -m pytest -q tests/test_v4_schema.py tests/test_t3_v3.py` -> 16 passed
- `python term_dict_tools.py --validate --dict data/term_dict.yaml --v4-mapping data/v4_term_mapping.yaml` -> errors=0 (기존 공유 변이 경고 3건)
- `python init_v4_schema.py --out cs_index` -> taxonomy_nodes=43, taxonomy_aliases=168, clause_items=0, coverage=0

### 2026-07-16 세션 28 — V4-2 대표 10건 입력 준비 (Codex)

- 승인된 v3 60건 중 V4 전 항목 대상인 SPA·SSA·SHA·ATA/BTA에서 초안/체결본과 high/med/low 신뢰도가 섞이도록 대표 10건을 확정했다.
- `plan_v4_batch.py`를 추가해 v3에서 승인된 진술보장·선행조건·확약의 문단 범위만 `cs_index/enrich_inputs_v4`에 생성했다. 문서 전체를 다시 입력하지 않고 관련 조항 범위만 전달한다.
- 대표 표본은 SPA 3건, SSA 2건, SHA 3건, ATA/BTA 2건이다. 별도계약 참조가 있는 SHA, 영업양도 양식, 대형 체결 SPA, 공란 초안을 함께 포함해 경계사례를 우선 검증한다.
- `cs_index/v4_batch_01_manifest.json`과 초기 `t3_v4_audit_report.json`을 생성했다. 현재 V4 결과는 아직 작성 전이므로 pending 10, error 0이며 다음 작업은 원자 항목 추출과 사람 검수표 작성이다.

검증:
- `python plan_v4_batch.py --out cs_index` -> count=10
- `python audit_t3_v4.py ...` -> total=10, pending=10, error=0
### 2026-07-23 — V4-1R 세부 원자화·별지 전수평가 기반 구현 (Codex)

- 기존 V4 테이블을 삭제하지 않는 additive migration으로 `v4_clause_item`에
  `source_kind/source_id/source_name/source_ref/parent_clause_ref`를 추가하고,
  참조자료별 평가 상태를 저장하는 `v4_source_coverage`를 구축했다.
- taxonomy version을 2로 올리고 노무 세부 노드
  `RW.LABOR.NO_VIOLATION`, `RW.LABOR.WORKING_CONDITIONS`,
  `RW.LABOR.NO_OFF_BOOK_WAGES`, `RW.LABOR.UNPAID_COMPENSATION` 및 aliases를 seed했다.
- `plan_v4_batch.py`가 활성 taxonomy 정의·alias 전체, 본문 하위 단위 힌트,
  Schedule·Disclosure Schedule·별지·부속서·첨부 인벤토리와 실제 발견 범위를 입력에 포함한다.
- V3 위치가 제목이나 첫 하위조항에서 끝나더라도 다음 V4 family 시작 직전까지 Article 범위를
  확장한다. 국문 대표 SPA는 RW 614~980(367문단·64 단위), COV 981~1249
  (269문단·26 단위), CP 1250~1376(127문단·21 단위)로 재생성되어 대상회사 세부
  진술보장과 후속 확약이 입력에서 빠지지 않는다.
- `audit_t3_v4.py`가 자료별 coverage 누락, available 별지 미완료, non-leaf taxonomy 남용,
  미커버 원자 단위, 기존 alias와 중복되는 신규 후보를 검사한다.
- `store_v4_results.py`를 추가해 감사 `pass` 결과만 V4 테이블에 저장하고 `doc_meta`는 보존한다.
  사람 검토 결과는 `--allow-review` 없이는 저장하지 않는다.
- 실제 `cs_index/catalog.sqlite`를 schema revision `1R`, taxonomy 47노드·188 aliases로
  마이그레이션하고 대표 10건 V4 입력을 새 형식으로 재생성했다.
- 기존 데모 결과 2건은 `source_coverage`가 없는 구형 결과여서 새 감사에서 error로 분리했다.
  삭제하지 않았으며 V4-2에서 재추출한다.

검증:
- `python -m pytest -q` → 169 passed, 1 skipped
- `python init_v4_schema.py --out cs_index` → schema_revision=1R,
  taxonomy_nodes=47, taxonomy_aliases=188
- `python plan_v4_batch.py --out cs_index` → 대표 입력 10건 재생성
- `git diff --check` → 오류 없음(기존 Windows LF/CRLF 경고만 출력)

### 2026-07-23 — 한국·미국형 M&A 20건 V4 범위 재검토 (Codex)

- 국문 12건, 영문·국영문 8건의 SPA·SSA·SHA·ATA/BTA 및 독립 Disclosure Letter를
  층화 표본으로 선정해 V3 메타와 관련 조항·별지 범위를 부분 정독했다.
- 한국형 계약의 계약금·중도금·잔금·위약벌·대금배분·임직원 승계와 미국형 계약의
  Estimated/Final Purchase Price, NWC/debt/cash adjustment, escrow/holdback,
  disclosure schedules, Knowledge/MAE/Permitted Lien, efforts standard를 반복 검색축으로 확인했다.
- 검토 결과를 `.docs/V4_SCOPE_REVIEW_20_20260723.md`에 file_key 근거와 함께 기록했다.
- V4 범위를 `RW|CP|COV|DEF|PAY|REM`으로 확장하고, 정의·지급구조·위반구제에도
  원자 item·source coverage·통제 taxonomy를 적용하도록 `.docs/V4_PLAN.md`를 보강했다.
- 계약금 몰취처럼 복수 기능을 가지는 문구는 PAY/REM 양쪽 item으로 저장하고 연결하며,
  독립 Disclosure Letter/Schedule은 본계약 source로 연결하는 원칙을 확정했다.

### 2026-07-23 — 추가 100건 검토 및 V4-1R2 6-family 보강 (Codex)

- 기존 20건과 겹치지 않게 SPA·SSA·SHA·ATA/BTA 각 25건, 국문 52건·영문 48건을
  층화 선정했다. 체결/비초안 34건, 초안 33건, 판별불가 33건이며 같은 유형·언어 안에서
  동일 거래 계열의 여러 버전이 중복되지 않도록 정규화한 project key로 제한했다.
- `review_v4_scope_sample.py`를 추가해 표본 선정, 관련 문구의 제한된 근거 수집,
  재현 가능한 JSON/Markdown 보고서 생성을 자동화했다. 결과는
  `cs_index/v4_scope_review_100.json`과
  `.docs/V4_SCOPE_REVIEW_100_20260723.md`에 저장했다.
- 대표 문단 부분 정독으로 사이버보안·침해사고 [847d7467e106d64f], anti-sandbagging·
  배타적 구제 [e45d3402878d30f6], 이중배상·보험·조세혜택 차감 [4b65065b177cad18],
  R&W 보험·대위권 포기 [76fc85ad82adef8e], rollover [113536aa319e1e0f],
  payoff·담보해제 [847d7467e106d64f], TSA [1f0dc2031c3e3bf9]를 확인했다.
- schema revision을 `1R2`, taxonomy version을 3으로 올리고 runtime family를
  `RW|CP|COV|DEF|PAY|REM`으로 확장했다. 정의·대금·구제와 추가 100건에서 확인된
  한미형 세부 항목을 반영해 taxonomy를 148노드·572 aliases로 보강했다.
- SQLite의 기존 3-family CHECK는 직접 변경할 수 없어, V4 생성 데이터와 promoted node가
  모두 0일 때만 V4 계층을 재구축하는 guarded migration을 구현했다. 실제 DB는 조건을
  확인한 뒤 V4 계층만 재구축했으며 T1-T3 `files`·`doc_meta`는 보존했다.
- `v4_clause_item.item_ref/related_item_ref`를 추가해 payoff(PAY/COV/CP), 계약금(PAY/REM),
  Fraud(DEF/REM), R&W 보험(COV/REM) 같은 복수 기능 문구를 연결한다.
- `plan_v4_batch.py`가 definitions_json, consideration_json과 대금조정·earn-out·
  에스크로·손해배상·조세배상·해제 범위를 이용해 DEF/PAY/REM 입력도 생성한다.
  대표 10건 입력과 manifest를 schema revision 1R2/taxonomy version 3으로 재생성했다.
- 추출 프롬프트를 `v4-prompt-3`으로 올리고 6-family coverage, DEF/PAY/REM 원자화,
  `related_item_ref` 규칙을 추가했다.

검증:
- `python init_v4_schema.py --out cs_index` → schema_revision=1R2,
  taxonomy_nodes=148, taxonomy_aliases=572, V4 생성 데이터 0
- `python plan_v4_batch.py --out cs_index` → 대표 입력 10건 재생성, 6개 family 포함
- `python -m pytest -q tests/test_v4_schema.py tests/test_v4_1r.py tests/test_store_v4_results.py`
  → 17 passed

### 2026-07-23 — V4-1R2 국문 대표 1건 색인 테스트 (Codex)

- 국문 대표 SPA `[0ddde0e62bd84e41]`에 대해 RW·COV·CP·DEF·PAY·REM 6개
  family를 현재 V4-1R2 taxonomy로 다시 평가했다.
- 조항 범위 탐지에서 정의 조항, 손해배상·해제 조항 및 대금 조항이 중간에서
  잘리던 경우를 보정하고, Seller Draft·Purchaser comments 등 편집 흔적은
  원자 단위 힌트에서 제외했다.
- 총 205개 원자 item을 추출했다: RW 88, COV 30, CP 16, DEF 40, PAY 6,
  REM 25. 노무는 위반 없음, 근로조건 준수, 규정 외 임금 없음, 미지급 보수
  없음 등을 독립 taxonomy로 분리했다.
- 파일에 포함된 별지 1(주주·지분·매매대금 표)은 전체 평가해
  RW.CAPITALIZATION과 PAY.ALLOCATION으로 색인하고 관련 item을 상호 연결했다.
  실제 내용이 없는 매도인 공개사항과 별지 1의 3은 source coverage에서
  missing으로 명시했다.
- 감사 결과는 review 1건, item 205개, issues 0건이다. review 사유는
  taxonomy 후보 29개와 OCR 표·정의어 관련 needs_review 44개이다.
- 명시적 사람 승인 전 review 결과를 저장하지 않는 가드를 확인했다:
  stored 0, skipped 1.
- 결과 보고서: `.docs/V4_KO_REPRESENTATIVE_TEST_0DDDE0E6_20260723.md`

검증:
- `python audit_t3_v4.py ...` → review=1, item_count=205, issues=0
- `python store_v4_results.py ...` → stored_count=0, skipped_count=1
- `python -m pytest -q` → 170 passed, 1 skipped

### 2026-07-23 — 신규 M&A 계약 200건 검토 및 taxonomy v4 보강 (Codex)

- 기존 범위검토 120건과 겹치지 않는 SPA·SSA·SHA·ATA/BTA 200건을 새로
  층화 선정했다. 각 유형마다 국문 25건·영문 25건이며, 동일 유형·언어 안에서
  정규화된 거래 project 중복은 0건이다.
- 표본 상태는 체결/비초안 57건, 초안 72건, 판별불가 71건이고 영문 표본 중
  미국 법·규제 표지가 직접 검출된 문서는 54건이다.
- 기존 taxonomy 개념의 표현 근거를 전수 스캔한 뒤 38개 gap 후보를 추가
  점검했다. 36개는 반복 또는 미국형 특수 개념의 근거가 확인됐고,
  `PAY.MILESTONE`, `PAY.EARNOUT_ACCELERATION`은 0건이어서 승격하지 않았다.
- 대표 5건의 관련 조항만 부분 정독해 정의 안의 단순 권리명 열거와 실제 SHA
  운영권리, CP bring-down 중요성 기준과 REM materiality scrape, 매매대금
  원천징수와 배상금 tax gross-up을 구분했다.
- taxonomy version을 4로 올리고 36개 seed를 추가했다. 주요 보강 범위는
  매출채권·재고·지급능력·개인정보 준수, 장부보존·특권·보증해제·종결후협조,
  SHA tag/drag·ROFR/ROFO·put/call·reserved matters·이사지명·정보권·배당·
  lock-up·창업자 전념, 기업결합·주주승인·FIRPTA·good standing,
  양수/제외자산·승계/제외채무, materiality scrape·연대/개별책임·구상·
  기본진술 별도 cap·청구통지기한·배상금 tax gross-up이다.
- 추출 프롬프트를 `v4-prompt-4`로 보강해 SHA 권리 구성요소, 자산양수도
  포함·제외 범위, materiality scrape scope, 청구통지 효과와 gross-up 문맥을
  원자화하도록 했다.
- term_dict의 관련 canonical 검색축을 가장 구체적인 V4 노드에 연결하도록
  `v4_term_mapping.yaml`을 version 2/taxonomy version 4로 확장했다.
- 실제 `catalog.sqlite`는 schema revision 1R2를 유지하면서 taxonomy version 4,
  184 nodes, 732 aliases로 갱신했다. 기존 V4 clause item·coverage는 0건이어서
  사용자 검토 결과를 덮어쓰지 않았다.

산출물:
- `.docs/V4_SCOPE_REVIEW_200_20260723.md`
- `.docs/V4_SCOPE_GAPS_200_20260723.md`
- `cs_index/v4_scope_review_200.json`
- `cs_index/v4_scope_gaps_200.json`

검증:
- `python term_dict_tools.py --validate ...` → errors=0
- `python init_v4_schema.py --out cs_index` → taxonomy_version=4,
  taxonomy_nodes=184, taxonomy_aliases=732
- `python -m pytest -q` → 172 passed, 1 skipped

## 2026-07-23 — V4 잔여 651건 검토·taxonomy v8·운영 적재 완료

- 앞서 검토한 20+100+200건과 절반 표본 652건을 제외한 정확한 보완집합
  651건을 확정했다.
- 사용자 요청에 따라 file_key 고정 순서로 1차 300건, 2차 351건을
  비중복 배치로 검토했다.
- 기존 49개 후보와 신규 세분화 후보 65개를 로컬 원문 캐시에서 검사하고,
  대표 문단 문맥과 기존 taxonomy 중복을 확인했다.
- 문맥 오탐과 기존 노드 중복을 제외하고 taxonomy v8에 43개 노드
  (상위 `RW.IT` 1개, 검색용 원자 leaf 42개)를 추가했다.
- taxonomy 누적은 369 nodes / 1,390 aliases다.
- 확정 근거 42 items / 26 documents를 `review_status=approved`,
  관련 family `body_status=partial`, `annex_status=not_evaluated`로
  운영 DB에 적재했다.
- 운영 V4 누적은 209 items / 60 documents이며 approved 209개다.
- 감사 결과 pass=26, review=0, error=0, stored=26, skipped=0이다.

주요 세분화:
- `RW.IT.SYSTEMS_SUFFICIENCY`, `RW.IT.DISASTER_RECOVERY`
- `COV.RWI.PROCUREMENT|MAINTENANCE|SUBROGATION_WAIVER`
- `COV.TAX.CONSISTENT_REPORTING|AUDIT_CONTROL|TRANSFER_TAX`
- `REM.THIRD_PARTY_CLAIMS.DEFENSE_CONTROL|SETTLEMENT_CONSENT|COOPERATION`
- `REM.INDEMNITY.RW_BREACH|COVENANT_BREACH|TAX|EXCLUDED_LIABILITIES`
- `REM.CONSEQUENTIAL.LOST_PROFITS|DIMINUTION_IN_VALUE|MULTIPLE_BASED`
- `PAY.HOLDBACK`, `PAY.EARNOUT.DISPUTE`, `PAY.ESCROW.RELEASE`

산출물:
- `.docs/V4_REMAINING_REST_REVIEW_20260723.md`
- `cs_index/v4_remaining_rest_review.json`
- `cs_index/v4_remaining_rest_node_update.json`
- `cs_index/v4_remaining_rest_confirmed_manifest.json`
- `cs_index/v4_remaining_rest_confirmed_audit.json`
- `cs_index/v4_remaining_rest_confirmed_store_audit.json`

검증:
- `python -m pytest -q` → 172 passed, 1 skipped
- `python eval_search.py --out cs_index --json` → fail 0, pass 6
- `python term_dict_tools.py --validate --out cs_index` → errors 0

### 2026-07-23 — 색인 업데이트 전달·운영 프로토콜 문서화

- 신규 계약서와 기존 운영 DB를 다음 세션 또는 새 환경에 전달해 현재 V4
  기준으로 증분 업데이트할 수 있도록 `색인 업데이트 설명서.md`를 작성했다.
- 계약서 본문·별지·Disclosure Schedule, 전체 `cs_index` 전달을 기본으로 하고,
  DB만 전달할 때의 한계와 SQLite WAL 복사 주의사항을 명시했다.
- 기존 taxonomy만 사용하는 방식, 신규 taxonomy 판단까지 위임하는 방식,
  후보를 먼저 검토한 뒤 적재하는 방식별 요청 문구를 제공했다.
- 패키지 무결성 확인, 백업, 증분 색인, 별지 인벤토리, V4 원자화, taxonomy
  후보 판정, 감사, 운영 DB 적재, 회귀검사 순서와 완료 보고 항목을 정리했다.
- 기준이 세션 기억에만 의존하지 않도록 `AGENTS.md`, V4 prompt, schema,
  감사기, term mapping 등 새 환경에 함께 전달할 기준 파일 목록을 포함했다.

### 2026-07-23 — V4-2 대표시험 131개 item 소유자 승인·적재 (Codex)

- 소유자 지시에 따라 `[0ba3a1b8246c5dd5]`의 V4-2 결과 131개를 모두
  `review_status=approved`로 전환했다.
- 재감사 결과 pass 1건, issues 0건을 확인한 뒤 운영
  `v4_clause_item`에 131개, `v4_document_coverage`에 6개 family,
  `v4_source_coverage`에 별지·공개목록 2개 source를 적재했다.
- 적재 분포는 body 19개, annex 102개, disclosure_schedule 10개이고,
  본문·별지·공개예외를 잇는 `related_item_ref`는 11개다.
- RW coverage는 body/annex 모두 complete이며, 이번 V4-2 범위 밖의
  CP·COV·DEF·PAY·REM은 not_evaluated로 명시해 부재와 혼동되지 않게 했다.
- `cs_index/v4_v2_trial_store_audit.json`에 저장 감사 결과를 남겼고
  `.docs/V4_V2_TRIAL_0BA3A1B8_20260723.md`도 운영 적재 상태로 갱신했다.

### 2026-07-23 — 미검토 주요 M&A 계약 절반 652건 검토·taxonomy v7 보강 (Codex)

- 기존 검토 320건을 제외한 검색가능 `SPA|SSA|SHA|ATA/BTA` 1,303건 중
  유형·언어 비율을 유지한 절반(올림) 652건(50.04%)을 선정했다.
  SPA 295건, SSA 147건, SHA 143건, ATA/BTA 67건이며 국문 422건,
  영문 223건, 국영문 7건이다.
- 652건의 추출 문단 전체를 49개 미보유 원자개념 후보로 로컬 스캔했다.
  42개 후보가 검출되었고, 대표 문단 부분 정독으로 정의·목차·단순 열거와
  기존 taxonomy 중복을 제거한 뒤 36개를 taxonomy version 7로 승격했다.
- 추가 노드는 RW 9, CP 3, COV 8, DEF 5, PAY 4, REM 7개다. 주요 예시는
  경쟁법·관세·이민법·금융약정·보조금 환수·정부계약·도메인·부동산 용도/
  수용, 핵심인력·에스크로·반대주주 주식매수청구권 조건, 개인정보 시정·
  standstill·비방금지·조세환급·SHA 등록권/의결권위임/정족수/캐스팅보트,
  회계원칙·데이터룸·공개목록·종결순차입금·목표운전자본, 마일스톤·주식대가·
  정산기한·언아웃 보증, 공제형/소급형 basket·징벌손해·취소권포기·
  에스크로 한정구제·청구대표자·배상재원 순서다.
- `CP.STOCK_EXCHANGE_APPROVAL`, `CP.DATA_ROOM_DELIVERY`,
  `COV.LITIGATION_COOPERATION`, `COV.IT_MIGRATION`,
  `PAY.PRICE_ADJUSTMENT_COLLAR`,
  `RW.CORPORATE_GOVERNANCE.NO_POWER_OF_ATTORNEY`는 오탐 또는 기존 노드
  중복으로 승격하지 않았다.
- taxonomy는 version 6의 290 nodes/1,002 aliases에서 version 7의
  326 nodes/1,171 aliases로 증가했다. 추출 프롬프트도 `v4-prompt-7`로
  올려 basket, SHA 운영규칙, 대금·정의, 구제재원 세분화 규칙을 반영했다.
- 사용자의 운영 DB 적재 요청에 따라 명확한 근거 36개 item/33개 문서를
  `review_status=approved`, 해당 family `body_status=partial`,
  `annex_status=not_evaluated`로 저장했다. 감사 pass 33, issues 0,
  stored 33, skipped 0이다.
- 전체 운영 V4 item은 대표계약 131개를 포함해 167개/34개 문서이며 전부
  approved다. partial 문서는 부재검색 근거로 사용하지 않는다.

산출물:
- `.docs/V4_REMAINING_HALF_REVIEW_20260723.md`
- `cs_index/v4_remaining_half_review.json`
- `cs_index/v4_remaining_half_node_update.json`
- `cs_index/v4_remaining_half_confirmed_manifest.json`
- `cs_index/v4_remaining_half_confirmed_audit.json`
- `cs_index/v4_remaining_half_confirmed_store_audit.json`

검증:
- `python term_dict_tools.py --validate --out cs_index` → errors=0
- `python eval_search.py --out cs_index --json` → fail=0
- `python -m pytest -q` → 172 passed, 1 skipped

### 2026-07-23 — V4-2 RW 세분화 및 신규 국문 SPA 대표시험 (Codex)

- 누적 범위검토 320건(20+100+200)의 관련 문단을 로컬 규칙으로 재점검해
  RW 표준 하위명제 82개의 실제 표현 근거를 확인했다. 권한·자본구조·재무·
  자산·계약·소송·조세·IP·환경·보험·인허가·부동산·복리후생·제품·
  고객/공급업체·특수관계인·브로커·개인정보 영역을 taxonomy version 5에
  82개 leaf로 추가했다.
- 기존 국문 대표와 다른 체결본 SPA `[0ba3a1b8246c5dd5]`를 선정했다.
  본문 제5.1조의 진술보장뿐 아니라 별지 5.1(8) 대상회사 진술보장
  (¶259~¶284)과 그 공개목록 세부자료(¶285~¶304)를 모두 V4-2 입력에 포함했다.
- 대표계약에서 매출채권 발생·회수·대손충당금·제한부담, 재고 판매가능성·
  수량 적정성·평가, 차임 지급·임대차보증금 회수, 인허가 분쟁, 세무장부,
  세법상 거주자, 거래추가조세 부재, 일반 법규준수, 제공정보의 정확성·누락,
  공동인력 등의 독립 명제를 추가 확인해 taxonomy version 6에 24개 노드
  (구조노드 2개 포함)를 더했다.
- taxonomy는 184개/732 aliases에서 누적 320건 보강 후 266개/896 aliases,
  대표시험 반영 후 290개/1,002 aliases가 되었다. RW 노드는 41개에서
  123개, 최종 147개로 확장됐다.
- 대표계약은 총 131개 RW 원자 item으로 추출했다: 본문 19개, 진술보장 별지
  102개, 공개목록 10개. 94개 서로 다른 최하위 taxonomy 노드를 사용했다.
- 공개목록의 개인정보 동의·파기·보호조치 미이행, 외국인 근로자 보험 미가입,
  공동인력, 산업안전보건 조치 미이행, 환경책임보험 미가입을 해당 본문/별지
  진술보장 item과 `related_item_ref`로 연결하고 반대 극성과
  `disclosure_exception` qualifier로 표시했다.
- 감사 결과는 pass 1건, item 131개, issues 0건이다. 소유자 검수 전이므로
  모든 item은 `review_status=pending`으로 두고 운영 `v4_clause_item`에는
  적재하지 않았다.

산출물:
- `.docs/V4_V2_TRIAL_0BA3A1B8_20260723.md`
- `cs_index/enrich_results_v4_v2_trial/0ba3a1b8246c5dd5.json`
- `cs_index/v4_v2_trial_node_update.json`
- `cs_index/v4_v2_trial_audit.json`
- `cs_index/rw_leaf_gaps_320.json`

검증:
- `python audit_t3_v4.py ...` → pass=1, item_count=131, issues=0
- `python term_dict_tools.py --validate --out cs_index` → errors=0
- `python -m pytest tests/test_v4_schema.py tests/test_v4_1r.py tests/test_store_v4_results.py -q`
  → 18 passed
- `python -m pytest -q` → 172 passed, 1 skipped

### 2026-07-23 — V4-2 나머지 9건 taxonomy v8 사전분류 (Codex)

- 승인·적재된 국문 SPA `[0ba3a1b8246c5dd5]`가 기존 대표 표본의
  `[0ddde0e62bd84e41]`를 대체하도록 하여, 전체 유형 분포 SPA 3·SSA 2·SHA 3·
  ATA/BTA 2를 유지하는 나머지 9건을 확정했다.
- `plan_v4_batch.py`로 10건 입력을 taxonomy v8·369노드 기준으로 재생성했다.
  manifest의 고정된 taxonomy v4 표기도 실제 version을 사용하도록 수정했다.
- `propose_v4_remaining_nine.py`를 추가해 canonical·alias가 원문에 직접 일치하는
  명제만 보수적으로 제안하고, 미분류 atomic unit은 문맥·taxonomy 검토 후보로
  보존하도록 했다. 유료 API와 운영 DB 쓰기는 사용하지 않는다.
- 9건에서 사전분류 item 528개와 검토 후보 451개를 만들었다. 모든 item은
  `needs_review`, 본문·별지 coverage는 `partial/not_evaluated`로 유지했다.
- 감사 결과는 review 9, error 0이며, 이슈 75건은 제공된 별지 source를 사람
  전수검토 전이므로 complete로 올리지 않은 `available_source_not_complete`뿐이다.
  후보 원문·좌표 불일치는 0건이다.
- 운영 DB는 기존 209 item·60문서, taxonomy v8 369노드로 변경하지 않았다.

산출물:
- `.docs/V4_BATCH_02_PRE_REVIEW_20260723.md`
- `cs_index/v4_batch_02_pre_review_manifest.json`
- `cs_index/enrich_results_v4_batch_02_pre_review/`
- `cs_index/v4_batch_02_pre_review_audit.json`

검증:
- `python -m pytest tests/test_propose_v4_remaining_nine.py tests/test_v4_schema.py tests/test_v4_1r.py -q`
  → 19 passed
- V4 감사 → review 9, error 0, 후보 원문·좌표 불일치 0

### 2026-07-24 — V4-2 나머지 9건 최종 문맥검수·taxonomy v11·운영 적재

- 사전분류 529개 item과 450개 후보를 원문 문맥으로 재검수했다. family 범위
  중복, 정의어 incidental match, 본문과 겹친 annex range를 제거하고 원문
  atomic hint를 다시 확인해 최종 861개 원자 item으로 확정했다.
- 최종 분포는 DEF 245, COV 222, RW 163, REM 142, CP 53, PAY 36이며
  120개 서로 다른 leaf를 사용한다. 미해결 taxonomy 후보는 0개다.
- 사전 제안에서 누락됐던 `[973d43e89040fb57]`의 `해당 인수대상자산`과
  `해당 인수대상채무` 정의를 atomic hint 재검수로 복구해
  `DEF.PURCHASED_ASSETS`, `DEF.ASSUMED_LIABILITIES`로 저장했다.
- 별지·Schedule·Exhibit 64개 고유 source를 추적했다. family-source 기준
  115행 중 제공된 114행은 complete이고, 코퍼스에 없는
  `[a51842fc51010f69]`의 Seller Disclosure Schedule 1행은 추정하지 않고
  missing으로 보존했다.
- 반복적으로 확인된 신규 검색축을 taxonomy v9-v11에 19개 leaf로 추가했다.
  주요 범위는 계약별 정의용어, 계약상 양도제한·허용양도, 거래비용 부담,
  종결절차, 제3자 보증·담보 부재, arm's-length 계약, 준거법·관할·완전합의·
  서면변경·누적구제·효력발생일, 일반 정부승인과 일반 Debt 정의다.
- taxonomy는 v8 369 nodes/1,390 aliases에서 v11 388 nodes/1,498 aliases로
  증가했다. 감사에서 확인된 비말단 `CP.GOVERNMENT_APPROVAL`, `DEF.DEBT`
  직접사용은 각각 `.GENERAL` leaf로 교정했다.
- 최종 V4 감사 결과 9건 전부 pass, review/pending/error 0이었다. 운영 DB에
  9건을 모두 저장해 누적 1,070 items/69 documents가 되었고, coverage 414행,
  source coverage 117행, taxonomy candidate 0건이다.
- 저장 전 `catalog.pre_batch02_store_20260724.sqlite`와 taxonomy v9/v10/v11
  단계별 SQLite 백업을 생성했다.

산출물:
- `.docs/V4_BATCH_02_FINAL_20260724.md`
- `finalize_v4_remaining_nine.py`
- `tests/test_finalize_v4_remaining_nine.py`
- `cs_index/v4_batch_02_final_manifest.json`
- `cs_index/enrich_inputs_v4_batch_02_final/`
- `cs_index/enrich_results_v4_batch_02_final/`
- `cs_index/v4_batch_02_final_audit.json`
- `cs_index/v4_batch_02_store_report.json`

검증:
- `python audit_t3_v4.py ...` → pass 9, review/pending/error 0
- `python term_dict_tools.py --validate --out cs_index` → errors 0, warnings 3
- `python eval_search.py --out cs_index --json` → fail 0
- `python -m pytest -q` → 179 passed, 1 skipped

### 2026-07-24 — V4-3 60건 파일럿·taxonomy v12·운영 후보 큐

- 기존 대표 10건과 부분평가 모집단 59건 중 유형·언어 비율로 선정한 50건을
  합쳐 정확히 60건의 파일럿 코호트를 구성했다. 추가 50건은 모두 현재
  `doc_meta`와 txt 캐시를 사용했으며 유료 API는 호출하지 않았다.
- 목차 좌표를 실제 조항으로 오인하던 문제를 교정했다. 영문 ARTICLE/목차 재현
  위치와 국문 6-family 실제 표제를 기준으로 본문 범위를 다시 잡고,
  Schedule·Annex·Exhibit·Disclosure Schedule을 별도 source inventory로
  추적하도록 `run_v4_pilot_60.py`를 구현했다.
- 추가 50건에서 확정 원자 item 2,500개를 생성했다. family 분포는 DEF 1,209,
  RW 528, REM 269, CP 224, COV 172, PAY 98이다.
- 사전 후보 1,583개 중 1,393개(88.0%)를 기존 taxonomy 또는 보강 규칙으로
  해소했다. 남은 190개는 승인 item과 섞지 않고 pending 후보 큐에 저장했다.
  후보 발생률은 `190 / (2,500 + 190) = 7.1%`이고 33개 문서에 남아 있다.
- 반복 명제를 근거로 매수인 자금충분성·독자조사·비의존·기타 진술보장 부인,
  선행조건 면제·자초 실패·연계거래 종결·대금조정 완료, 언아웃 지급구조를
  taxonomy v12에 추가했다. 구조 부모를 포함해 10개 노드가 늘어
  398 nodes/1,561 aliases가 되었다.
- source coverage는 complete 134행, missing 59행이다. missing 59행은 13개
  문서의 참조자료가 코퍼스에 없거나 참조만 있는 경우로, 내용을 추정하지 않고
  부재검색 근거에서도 제외했다.
- V4 감사는 total 50, pass 17, review 33, pending/error 0, 구조 issue 0이다.
  사용자의 운영 적재 지시에 따라 확정 item과 후보를 분리한 채 50건을 모두
  저장했다. 운영 DB는 3,502 items/69 documents, pending candidates 190개다.
- 저장 전 `catalog.pre_v4_pilot60_store_20260724.sqlite`를 생성했다. SQLite
  integrity check는 ok, foreign-key violation은 0이다.

산출물:
- `.docs/V4_PILOT_60_20260724.md`
- `run_v4_pilot_60.py`
- `tests/test_run_v4_pilot_60.py`
- `cs_index/v4_pilot60_cohort_manifest.json`
- `cs_index/v4_pilot60_final_manifest.json`
- `cs_index/enrich_inputs_v4_pilot60_final/`
- `cs_index/enrich_results_v4_pilot60_final/`
- `cs_index/v4_pilot60_final_audit.json`
- `cs_index/v4_pilot60_store_report.json`

검증:
- V4 감사 → pass 17, review 33, pending/error 0, 구조 issue 0
- 운영 저장 → stored 50, skipped 0, `allow_review=true`
- `python eval_search.py --out cs_index --tiers T1,T2 --json` → fail 0
- `python -m pytest -q` → 185 passed, 1 skipped

다음 단계:
- V4-4 UI-5 taxonomy 관리 화면에서 현재 후보 190개를 반복 문구·family·근접
  taxonomy별로 묶고, 기존 노드 귀속·신규 leaf 승격·기각을 일괄 처리한다.

### 2026-07-24 — V4-4 UI-5 taxonomy 후보 관리

- `/taxonomy` 관리 화면과 후보 관리 API를 구현했다. 운영 pending 후보
  190개는 정규화 문구·family·근접 노드 기준 179개 묶음으로 표시된다.
- 같은 family의 여러 묶음을 선택해 (i) 기존 leaf 귀속, (ii) 신규 leaf 승격,
  (iii) 사유를 남긴 기각을 일괄 실행할 수 있다.
- 신규 승격은 canonical ID·부모·국영문 이름·정의·alias를 검증하고 taxonomy
  version을 1 증가시킨다. 이미 item이 직접 귀속된 leaf를 부모로 바꾸거나
  다른 family에 귀속하거나 기존 alias와 충돌시키는 작업은 거부한다.
- `v4_taxonomy_action_log`를 추가해 action, candidate ID 목록, target,
  payload·사유, UTC 시각을 기록한다. 후보 원문·file_key·¶좌표는 삭제하지 않는다.
- 모든 쓰기는 `BEGIN IMMEDIATE` 트랜잭션이며 이미 처리된 후보의 재처리는
  HTTP 409로 차단한다. 운영 앱의 실제 후보는 누르지 않아 pending 190,
  action log 0건을 유지했다.
- 실제 로컬 서버에서 `/taxonomy` HTTP 200, taxonomy v12, 179 clusters /
  190 candidates를 읽기 확인했다. 연결 가능한 브라우저 인스턴스가 없어
  화면 캡처 기반 시각 QA는 수행하지 못했고, HTML 응답·JS 구문·임시 DB
  서비스/웹 통합 테스트로 처리 경로를 검증했다.

산출물:
- `.docs/V4_TAXONOMY_UI_20260724.md`
- `taxonomy_admin.py`
- `static/taxonomy.html`
- `static/taxonomy.css`
- `static/taxonomy.js`
- `tests/test_taxonomy_admin.py`
- `tests/test_taxonomy_web.py`

검증:
- taxonomy 서비스·웹·스키마 관련 테스트 → 38 passed
- `node --check static/taxonomy.js` → 통과
- 운영 DB 읽기 확인 → v12, pending 190, action log 0
- `python -m pytest -q` → 192 passed, 1 skipped

다음 단계:
- V4-5 CLI·웹·MCP 검색에서 atomic taxonomy 조건을 노출하고 세부 골든 질의로
  v3+부분정독 대비 recall·정독 문서 수를 비교하는 게이트 B를 실행한다.

### 2026-07-24 — V4-5 원자 명제 검색·Gate B 예비 평가

- `v4_search.py`를 공통 읽기 전용 서비스로 구현했다. taxonomy ID/canonical/alias
  정규화, 하위 노드 포함 검색, polarity·주체·시점·유형·언어 필터, 원문과 ¶ 좌표,
  본문·별지 source 및 최신성 표시를 지원한다.
- 부재 판정은 본문 complete + 별지 complete/no_annex + 현재 해시 + source
  complete/current + 해당 family pending 후보 없음 조건을 모두 만족한 경우만
  `confirmed_absent`로 반환한다. 그 밖의 미검출 문서는 사유가 있는
  `needs_review`로 분리한다.
- 기존 `search_contracts.py`에 `--item`, `--item-absent`, `--polarity`,
  `--subject`, `--time`, `--exact-item`을 추가했다. 독립 CLI는 2~10개 계약 비교도
  지원한다.
- `/v4-search` 화면과 `POST /api/v4/items/search`,
  `POST /api/v4/items/compare`를 추가했다. taxonomy 선택지는 DB에서 동적으로
  읽고 결과 카드에 match path·coverage·원문 좌표를 표시한다.
- `v4_mcp_tools.py`는 기존 도구를 변경하지 않고 `search_clause_items`,
  `compare_clause_items`를 등록하는 읽기 전용 어댑터다.
- family별 존재 24, 부재 6, 비교 6의 총 36개 예비 골든 질의를 만들었다.
  현재 승인 V4 item을 reference로 한 결과는 구조화 recall 1.0000, legacy
  정확구문 후보 recall 0.3748, 정독 필요 문서 누적 24,647→12,422(49.6% 감소),
  측정 조회시간 합계 1,163.073→466.066ms였다. 36개 모두 scored였다.
- 이 평가는 독립 사람 검수 골드가 아니라 승인 item 기반 회귀이므로 Gate B의
  기능 경로는 통과하되 Gate A 완전성 통과로 보지 않는다. pending 후보 190개와
  missing source 59개는 계속 부재 판정에서 제외된다.

산출물:
- `.docs/V4_SEARCH_GATE_B_20260724.md`
- `data/v4_gate_b_golden.json`
- `eval_v4_gate.py`
- `v4_search.py`, `v4_search_web.py`, `v4_mcp_tools.py`
- `static/v4-search.html`, `static/v4-search.css`, `static/v4-search.js`
- V4-5 테스트 5개 파일

검증:
- V4-5 대상 테스트 13 passed
- `node --check static/v4-search.js` 통과
- 실제 로컬 HTTP 검색 200 및 국문 원자 item 1건 확인
- `python -m pytest -q` → 205 passed, 1 skipped

다음 단계:
- V4-6에서 SPA→SSA→SHA→ATA/BTA 순으로 제한 배치를 확장한다. Gate A가 아직
  미통과이므로 missing source와 pending taxonomy 후보는 계속 `needs_review`로
  보존하고, 유형별 평가 회귀를 함께 기록한다.

### 2026-07-24 — V4-6 확장 배치 01(SPA 300건)

- 미평가 core 계약 1,554개 중 SPA 300건(국문 196, 영문 104)을 중복 대표
  기준으로 선택했다.
- 승인 원자 item 13,389개와 pending taxonomy 후보 1,396개를 생성했다.
  감사 결과 pass 62, review 238, pending/error 0, 구조 issue 0이었다.
- WAL-safe 백업 후 300건을 운영 DB에 적재했다. 누적 V4 item 16,891개,
  평가 문서 369개, pending 후보 1,586개이며 integrity ok/FK violation 0이다.
- 500건을 넘는 결과의 Gate B recall 계산 오류를 찾아 V4 검색과 MCP·웹에
  pagination을 추가했다. 전체 페이지 재평가 결과 V4 recall 1.0000,
  legacy 0.3430, 원문 정독 필요량 53.85% 감소, T1/T2 fail 0이다.
- 전체 회귀는 208 passed, 1 skipped이다.

산출물:
- `.docs/V4_EXPANSION_01_20260724.md`
- `run_v4_expansion.py`, `tests/test_run_v4_expansion.py`
- `cs_index/v4_expansion_01_spa300_*` 및 final input/result

다음 단계:
- 다음 300건 전에 pending 후보 1,586개를 반복 문구별로 묶어 기존 node
  병합/신규 leaf 승격/기각하는 taxonomy 정리 배치를 수행한다.

### 2026-07-24 — V4-6 taxonomy v13 정리 배치

- 후보 병합·승격이 상태만 바꾸고 검색 item을 생성하지 않던 누락을 수정했다.
  schema revision 1R3에서 후보의 source/hash/version을 보존하고, 해결과
  `v4_clause_item` 생성을 하나의 트랜잭션으로 처리한다. 후보 1개를 여러 원자
  node로 분해하는 경로와 stale/source 검증도 추가했다.
- 처리 전 pending 1,586개 전부가 현재 txt 캐시의 해당 ¶ 원문과 일치했다.
- 300건 확장에서 반복 확인된 동시 전부종결, 매수인 지명 임원 선임,
  R&W 보험 발효, 개인보증, 특정 부채 정리, 규제기관 통지, 자금조달 비조건성,
  사해행위 위험 부재, 배상금의 대금조정 처리, 법령변경 손해 배제의 10개
  leaf를 추가해 taxonomy v13 408 nodes가 되었다.
- dry-run 후 고신뢰 후보 294개를 병합해 approved 원자 item 294개를 만들고,
  제목·리드인·편집주석 16개를 기각했다. 1,276개는 추측하지 않고 pending으로
  유지했다.
- 운영 V4 item은 17,185개다. 새 item은 원문 좌표 294/294 일치, stale 0,
  FTS row 수 일치, integrity ok, FK violation 0이다.
- Gate B는 36/36 scored, V4 recall 1.0000, legacy 0.3425, 정독 문서 수
  54.23% 감소다. T1/T2 fail 0, 전체 회귀 212 passed, 1 skipped다.

산출물:
- `.docs/V4_TAXONOMY_V13_20260724.md`
- `review_v4_candidates.py`, `tests/test_review_v4_candidates.py`
- `cs_index/v4_candidate_review_v13_dry_run.json`
- `cs_index/v4_candidate_review_v13_applied.json`

다음 단계:
- 차단 이슈가 없으므로 남은 pending은 보존한 채 taxonomy v13과 schema 1R3로
  다음 300건 확장 배치를 진행한다.

### 2026-07-24 — V4-6 확장 배치 02(SPA 추가 300건)

- 기존 평가 문서와 중복 대표를 제외한 eligible 1,254건에서 SPA 300건을
  추가 선정했다(국문 196, 영문 104).
- taxonomy v13·schema 1R3로 approved 원자 item 13,905개와 pending 후보
  1,203개를 생성했다. 후보율은 7.96%로 직전 배치 9.44%보다 낮아졌다.
- 감사 결과 pass 74, review 226, pending/error 0, 구조 issue 0이었다.
- WAL-safe 백업 후 300건을 운영 DB에 적재했다. 누적 item 31,090개,
  평가 문서 669개, pending 후보 2,479개이며 integrity ok, FK violation 0,
  FTS row 수 일치다.
- Gate B는 36/36 scored, V4 recall 1.0000, legacy 0.3445, 정독 문서 수
  58.98% 감소다. T1/T2 fail 0, 전체 회귀 212 passed, 1 skipped다.
- `run_v4_expansion.py` manifest의 schema revision 하드코딩을 제거하고
  현재 `V4_SCHEMA_REVISION`을 기록하도록 교정했다.

산출물:
- `.docs/V4_EXPANSION_02_20260724.md`
- `cs_index/v4_expansion_02_next300_*`

다음 단계:
- 다음 계약 배치 전에 Schedule·Annex·Disclosure Schedule 실질 문단이
  item 또는 명시적 pending 후보로 모두 보존되는지 완전성 감사를 수행한다.

### 2026-07-24 — V4 별지 물리 문단 완전성 교정·taxonomy v14

- 두 300건 배치의 Schedule·Annex·Exhibit·Disclosure Schedule을 물리
  `(storage file, ¶, 원문)` 단위로 감사했다. 기존 final review가 배치별
  6,354개·7,242개의 미표현 실질 문단을 남긴 채 source를 complete로 바꾸던
  조용한 누락을 확인했다.
- 물리 문단을 한 번만 전수검수해 분류 가능한 문단은 source item으로,
  나머지 실질 문단·표 행·None/없음은 source 좌표가 있는 pending 후보로
  보존하도록 pipeline을 교정했다. 후보가 남은 source와 연결 family는 모두
  partial로 유지한다.
- 기존 600건을 재선정 없이 재생성했다. 배치 01은 item 21,047/source item
  7,708/source 후보 3,847, 배치 02는 item 22,574/source item 9,520/source
  후보 4,114다.
- broad `RW.SOLVENCY` item을 새 leaf `RW.SOLVENCY.GENERAL`로 교정해
  taxonomy v14 409 nodes가 되었다.
- 운영 DB는 item 47,139/source item 17,712, pending 10,401/source pending
  7,961이다. source evidence 25,673건은 txt 좌표와 전부 일치하고,
  incomplete source를 complete로 표시한 사례는 0건이다.
- 문서 재저장 시 taxonomy 해결 item과 action log 연결을 반복 실행에도
  보존하도록 수정했다. resolution reference 294개 중 missing 0이다.
- integrity ok, FK violation 0, FTS row 일치. Gate B V4 recall 1.0000,
  정독 문서 수 56.69% 감소, T1/T2 fail 0, 전체 회귀 214 passed, 1 skipped다.

산출물:
- `.docs/V4_ANNEX_COMPLETENESS_20260724.md`
- `refinalize_v4_batch.py`
- `cs_index/v4_expansion_01_spa300_annex_*`
- `cs_index/v4_expansion_02_next300_annex_*`

다음 단계:
- 47,139 item에서 Gate 조회가 약 95초로 증가했으므로 전체 결과를 매 페이지
  재구성하는 방식을 SQL count/page pagination으로 바꾼 뒤 다음 배치로 간다.
