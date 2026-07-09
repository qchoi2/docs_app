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
