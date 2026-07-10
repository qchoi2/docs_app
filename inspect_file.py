from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from typing import Dict, List, Optional

from lib.console import configure_utf8_stdio


def connect(out: Path) -> sqlite3.Connection:
    db_path = out / "catalog.sqlite"
    if not db_path.exists():
        raise FileNotFoundError(f"catalog.sqlite not found: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def parse_source_signals(value: Optional[str]) -> object:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def fetch_dup_members(conn: sqlite3.Connection, dup_group: Optional[str]) -> List[Dict[str, object]]:
    if not dup_group:
        return []
    rows = conn.execute(
        """
        SELECT file_key, path, status, is_draft, version_hint
        FROM files
        WHERE dup_group = ?
        ORDER BY path, file_key
        """,
        (dup_group,),
    ).fetchall()
    return [
        {
            "file_key": row["file_key"],
            "path": row["path"],
            "status": row["status"],
            "is_draft": row["is_draft"],
            "version_hint": row["version_hint"],
        }
        for row in rows
    ]


def doc_meta_state(conn: sqlite3.Connection, file_key: str, content_hash: Optional[str]) -> Dict[str, object]:
    row = conn.execute(
        "SELECT txt_hash, confidence FROM doc_meta WHERE file_key = ?",
        (file_key,),
    ).fetchone()
    if row is None:
        return {"present": False, "stale": None, "confidence": None}
    stale = None
    if row["txt_hash"] and content_hash:
        stale = row["txt_hash"] != content_hash
    return {"present": True, "stale": stale, "confidence": row["confidence"]}


def inspect_file(out: Path, file_key: str, show_dup_group: bool = False) -> Dict[str, object]:
    with closing(connect(out)) as conn:
        row = conn.execute(
            """
            SELECT file_key, path, ctype, lang, status, error_reason,
                   source_signals, batch_label, content_hash, dup_group,
                   is_draft, version_hint, txt_path
            FROM files
            WHERE file_key = ?
            """,
            (file_key,),
        ).fetchone()
        if row is None:
            raise KeyError(f"file_key not found: {file_key}")

        dup_group = row["dup_group"]
        dup_count = conn.execute(
            "SELECT COUNT(*) FROM files WHERE dup_group = ?",
            (dup_group,),
        ).fetchone()[0] if dup_group else 1

        result: Dict[str, object] = {
            "file_key": row["file_key"],
            "path": row["path"],
            "ctype": row["ctype"],
            "lang": row["lang"],
            "status": row["status"],
            "error_reason": row["error_reason"],
            "source_signals": parse_source_signals(row["source_signals"]),
            "batch_label": row["batch_label"],
            "txt_path": row["txt_path"],
            "dup_group": {
                "id": dup_group,
                "count": dup_count,
                "is_duplicate": dup_count >= 2,
            },
            "is_draft": row["is_draft"],
            "version_hint": row["version_hint"],
            "doc_meta": doc_meta_state(conn, file_key, row["content_hash"]),
        }
        if show_dup_group:
            result["dup_group"]["members"] = fetch_dup_members(conn, dup_group)
        return result


def print_text(result: Dict[str, object]) -> None:
    print(f"file_key: {result['file_key']}")
    print(f"path: {result['path']}")
    print(f"ctype: {result['ctype']}")
    print(f"lang: {result['lang']}")
    print(f"status: {result['status']}")
    print(f"error_reason: {result['error_reason'] or ''}")
    print(f"source_signals: {json.dumps(result['source_signals'], ensure_ascii=False, sort_keys=True)}")
    print(f"batch_label: {result['batch_label'] or ''}")
    print(f"txt_path: {result['txt_path'] or ''}")
    dup_group = result["dup_group"]
    print(f"dup_group: {dup_group['id'] or ''}")
    print(f"dup_count: {dup_group['count']}")
    print(f"is_duplicate: {dup_group['is_duplicate']}")
    print(f"is_draft: {result['is_draft']}")
    print(f"version_hint: {result['version_hint'] or ''}")
    print(f"doc_meta_present: {result['doc_meta']['present']}")
    print(f"doc_meta_stale: {result['doc_meta']['stale']}")
    for member in dup_group.get("members", []):
        print(f"dup_member: {member['file_key']}\t{member['status']}\t{member['path']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect one indexed contract file record.")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--file-key", required=True)
    parser.add_argument("--show-dup-group", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = inspect_file(args.out, args.file_key, args.show_dup_group)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_text(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
