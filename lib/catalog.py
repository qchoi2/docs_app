"""SQLite catalog schema utilities for the contract search index."""

from __future__ import annotations

import argparse
from contextlib import closing
import sqlite3
import sys
from pathlib import Path
from typing import List, Optional, Union


MIN_TRIGRAM_SQLITE_VERSION = (3, 34, 0)


CATALOG_DDL = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS files (
  file_key    TEXT PRIMARY KEY,
  path        TEXT NOT NULL,
  folder      TEXT, filename TEXT,
  ctype       TEXT NOT NULL DEFAULT '미분류',
  lang        TEXT NOT NULL DEFAULT '미상',
  ext         TEXT, size INTEGER, mtime REAL,
  txt_path    TEXT, char_count INTEGER,
  status      TEXT NOT NULL CHECK(status IN
              ('ok','empty','error','unsupported','excluded','missing')),
  error_reason TEXT,             -- §2.4.1의 enum 값
  source_signals TEXT,           -- 파일명/폴더명 기반 추정 단서 JSON
  batch_label TEXT,              -- pilot_001, full_001 등 색인 실행 배치 식별자
  content_hash TEXT, dup_group TEXT,
  is_draft    INTEGER,           -- 1/0/NULL(판별불가)
  version_hint TEXT,
  indexed_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_meta ON files(ctype, lang, status);
CREATE INDEX IF NOT EXISTS idx_dup  ON files(dup_group);
-- FTS: 문단 단위 1행 (matched_terms의 ¶ 좌표와 스니펫 품질의 근거)
CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(
  content, file_key UNINDEXED, para UNINDEXED,
  tokenize='trigram'
);
-- Phase 2 예약 (지금은 생성만, 기록 안 함)
CREATE TABLE IF NOT EXISTS doc_meta (
  file_key TEXT PRIMARY KEY REFERENCES files(file_key),
  meta_schema_version INTEGER, txt_hash TEXT,   -- 추출 당시 content_hash
  extracted_at TEXT,
  parties_json TEXT,
  deal_type_detail TEXT,
  consideration_json TEXT,
  clause_map_json TEXT,
  special_notes TEXT,
  definitions_json TEXT,
  json TEXT,
  confidence TEXT
);
CREATE TABLE IF NOT EXISTS clause_index (
  file_key TEXT, tag TEXT, present INTEGER,
  loc_start INTEGER, loc_end INTEGER,
  PRIMARY KEY (file_key, tag)
);
"""


class CatalogError(RuntimeError):
    """Raised when the catalog database cannot be initialized."""


def _trigram_error(detail: str) -> CatalogError:
    version = sqlite3.sqlite_version
    return CatalogError(
        "SQLite FTS5 trigram tokenizer is required for catalog.sqlite. "
        f"Current sqlite3.sqlite_version={version}. {detail} "
        "Install or use a Python runtime with SQLite >= 3.34 and FTS5 trigram "
        "support, for example by installing pysqlite3-binary."
    )


def ensure_trigram_available() -> None:
    """Fail loudly unless SQLite can create an FTS5 trigram table."""

    if sqlite3.sqlite_version_info < MIN_TRIGRAM_SQLITE_VERSION:
        raise _trigram_error("SQLite is older than 3.34.")

    try:
        with closing(sqlite3.connect(":memory:")) as conn:
            conn.execute(
                "CREATE VIRTUAL TABLE trigram_probe "
                "USING fts5(content, tokenize='trigram')"
            )
    except sqlite3.Error as exc:
        raise _trigram_error(f"Probe failed: {exc}") from exc


def initialize_catalog(db_path: Union[str, Path]) -> Path:
    """Create catalog.sqlite schema at db_path and return the resolved path."""

    ensure_trigram_available()

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript(CATALOG_DDL)
    return path.resolve()


def connect_catalog(db_path: Union[str, Path]) -> sqlite3.Connection:
    """Open a catalog connection after validating trigram support."""

    ensure_trigram_available()
    return sqlite3.connect(db_path)


def _main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Initialize catalog.sqlite schema.")
    parser.add_argument("db_path", help="Path to catalog.sqlite")
    args = parser.parse_args(argv)

    try:
        path = initialize_catalog(args.db_path)
    except CatalogError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
