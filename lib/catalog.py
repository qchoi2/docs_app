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
  version_role TEXT,             -- classify_version.py: execution/buyer_draft/... (검색 버전 필터)
  version_basis TEXT,            -- version_role 분류 근거 JSON (source_signals와 같은 형식)
  version_confidence TEXT,       -- high/med/low. NULL=아직 백필 안 됨(확신으로 읽지 말 것)
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


class CatalogNotFoundError(CatalogError, FileNotFoundError):
    """Raised when a read path points at a catalog that does not exist.

    Also a ``FileNotFoundError`` so the existing ``except FileNotFoundError``
    handlers in webapp.py / mcp_server.py keep working unchanged.

    ``sqlite3.connect()`` silently CREATEs a missing file, so a tool run with
    the wrong ``--out`` used to produce an empty second database (observed
    2026-07-29: a bare ``sqlite3.connect('catalog.sqlite')`` from the repo root
    left a 0-byte ``catalog.sqlite`` beside the real ``cs_index/catalog.sqlite``)
    and then report an empty corpus. Read paths must fail loudly instead.
    """


def catalog_path(out: Union[str, Path]) -> Path:
    """Return the catalog file inside an ``--out`` directory."""

    return Path(out) / "catalog.sqlite"


def require_catalog(db_path: Union[str, Path]) -> Path:
    """Return ``db_path`` only if it is an existing, non-empty catalog file.

    Never creates anything. Raises :class:`CatalogNotFoundError` with an
    actionable message otherwise.
    """

    path = Path(db_path)
    if not path.exists():
        raise CatalogNotFoundError(
            f"색인 DB가 없습니다: {path} — --out 경로를 확인하세요 "
            "(색인은 보통 cs_index/catalog.sqlite 입니다). "
            "새 색인을 만들려면 index_contracts.py를 사용하세요."
        )
    if path.is_dir():
        raise CatalogNotFoundError(
            f"색인 DB가 없습니다: {path} — 디렉터리입니다. --out 경로를 확인하세요."
        )
    if path.stat().st_size == 0:
        raise CatalogNotFoundError(
            f"색인 DB가 없습니다: {path} — 0바이트 빈 파일입니다. "
            "--out 경로를 확인하세요 (잘못된 경로로 실행해 생긴 껍데기 파일일 수 "
            "있습니다; 지운 뒤 올바른 --out으로 다시 실행하세요)."
        )
    return path


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


def connect_catalog(
    db_path: Union[str, Path],
    *,
    read_only: bool = False,
    create: bool = False,
    timeout: Optional[float] = None,
    verify_trigram: bool = False,
) -> sqlite3.Connection:
    """Open the catalog, refusing to conjure a missing database.

    ``create=True`` is the only way to get the old creating behaviour and is
    reserved for the deliberate build paths (index_contracts.py); every read
    path leaves it at False so a wrong ``--out`` raises
    :class:`CatalogNotFoundError` instead of leaving an empty database behind.
    """

    if verify_trigram:
        ensure_trigram_available()
    if not create:
        db_path = require_catalog(db_path)
    kwargs = {} if timeout is None else {"timeout": timeout}
    if read_only:
        uri = f"file:{Path(db_path).as_posix()}?mode=ro"
        return sqlite3.connect(uri, uri=True, **kwargs)
    return sqlite3.connect(db_path, **kwargs)


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
