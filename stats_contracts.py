from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from lib.console import configure_utf8_stdio


STATUSES = ("ok", "empty", "error", "unsupported", "excluded", "missing")


def parse_by(value: Optional[str]) -> List[str]:
    if not value:
        return []
    columns = [item.strip() for item in value.split(",") if item.strip()]
    allowed = {"ctype", "lang"}
    invalid = [column for column in columns if column not in allowed]
    if invalid:
        raise ValueError(f"unsupported --by column(s): {', '.join(invalid)}")
    if not columns:
        raise ValueError("--by requires at least one column")
    return columns


def connect(out: Path) -> sqlite3.Connection:
    db_path = out / "catalog.sqlite"
    if not db_path.exists():
        raise FileNotFoundError(f"catalog.sqlite not found: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def representative_filter(dedup: bool) -> str:
    if not dedup:
        return "1 = 1"
    return """
    file_key = (
      SELECT f2.file_key
      FROM files f2
      WHERE COALESCE(f2.dup_group, f2.file_key) = COALESCE(files.dup_group, files.file_key)
        AND f2.status = files.status
      ORDER BY
        CASE WHEN f2.is_draft = 1 THEN 1 ELSE 0 END,
        CASE
          WHEN lower(COALESCE(f2.version_hint, '') || ' ' || COALESCE(f2.path, '')) LIKE '%final%' THEN 0
          WHEN lower(COALESCE(f2.version_hint, '') || ' ' || COALESCE(f2.path, '')) LIKE '%signed%' THEN 0
          WHEN lower(COALESCE(f2.version_hint, '') || ' ' || COALESCE(f2.path, '')) LIKE '%clean%' THEN 0
          ELSE 1
        END,
        length(COALESCE(f2.path, '')),
        COALESCE(f2.filename, ''),
        f2.file_key
      LIMIT 1
    )
    """


def grouped_counts(conn: sqlite3.Connection, columns: Sequence[str], dedup: bool, ok_only: bool) -> List[Dict[str, object]]:
    where = [representative_filter(dedup)]
    params: List[object] = []
    if ok_only:
        where.append("status = 'ok'")
    else:
        where.append("status != 'missing'")

    select_columns = ", ".join(columns)
    group_columns = ", ".join(columns)
    rows = conn.execute(
        f"""
        SELECT {select_columns}, COUNT(*) AS count
        FROM files
        WHERE {' AND '.join(where)}
        GROUP BY {group_columns}
        ORDER BY count DESC, {group_columns}
        """,
        params,
    ).fetchall()
    return [{column: row[column] for column in columns} | {"count": row["count"]} for row in rows]


def simple_counts(
    conn: sqlite3.Connection,
    column: str,
    dedup: bool,
    *,
    ok_only: Optional[bool] = None,
    where_extra: str = "",
) -> List[Dict[str, object]]:
    where = [representative_filter(dedup)]
    if ok_only is True:
        where.append("status = 'ok'")
    elif ok_only is False:
        where.append("status != 'missing'")
    if where_extra:
        where.append(where_extra)
    rows = conn.execute(
        f"""
        SELECT COALESCE({column}, '') AS value, COUNT(*) AS count
        FROM files
        WHERE {' AND '.join(where)}
        GROUP BY COALESCE({column}, '')
        ORDER BY count DESC, value
        """
    ).fetchall()
    return [{"value": row["value"], "count": row["count"]} for row in rows]


def status_counts(conn: sqlite3.Connection, dedup: bool) -> Dict[str, int]:
    rows = simple_counts(conn, "status", dedup)
    counts = {row["value"]: row["count"] for row in rows}
    return {status: counts.get(status, 0) for status in STATUSES}


def dedup_summary(conn: sqlite3.Connection) -> Dict[str, object]:
    total_files = conn.execute("SELECT COUNT(*) FROM files WHERE status != 'missing'").fetchone()[0]
    ok_files = conn.execute("SELECT COUNT(*) FROM files WHERE status = 'ok'").fetchone()[0]
    total_groups = conn.execute(
        "SELECT COUNT(DISTINCT COALESCE(dup_group, file_key)) FROM files WHERE status != 'missing'"
    ).fetchone()[0]
    ok_groups = conn.execute(
        "SELECT COUNT(DISTINCT COALESCE(dup_group, file_key)) FROM files WHERE status = 'ok'"
    ).fetchone()[0]
    groups = conn.execute(
        """
        SELECT COALESCE(dup_group, file_key) AS dup_group,
               COUNT(*) AS count,
               SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) AS ok_count
        FROM files
        WHERE status != 'missing'
        GROUP BY COALESCE(dup_group, file_key)
        HAVING COUNT(*) >= 2
        ORDER BY count DESC, dup_group
        """
    ).fetchall()
    return {
        "total_files": total_files,
        "total_groups": total_groups,
        "ok_files": ok_files,
        "ok_groups": ok_groups,
        "duplicate_groups": [
            {"dup_group": row["dup_group"], "count": row["count"], "ok_count": row["ok_count"]}
            for row in groups
        ],
    }


def build_stats(
    out: Path,
    by: Optional[str] = None,
    include_status: bool = False,
    include_errors: bool = False,
    include_batches: bool = False,
    include_dedup: bool = False,
    dedup: bool = False,
) -> Dict[str, object]:
    columns = parse_by(by)
    with closing(connect(out)) as conn:
        result: Dict[str, object] = {"out": str(out), "dedup": dedup}
        if columns:
            key = ",".join(columns)
            result["by"] = {
                "columns": columns,
                "ok": grouped_counts(conn, columns, dedup, ok_only=True),
                "all": grouped_counts(conn, columns, dedup, ok_only=False),
            }
            result[key] = result["by"]
        if include_status:
            result["status"] = status_counts(conn, dedup)
        if include_errors:
            result["errors"] = simple_counts(
                conn,
                "error_reason",
                dedup,
                ok_only=False,
                where_extra="error_reason IS NOT NULL",
            )
        if include_batches:
            result["batches"] = simple_counts(conn, "batch_label", dedup, ok_only=False)
        if include_dedup:
            result["dedup_summary"] = dedup_summary(conn)
    return result


def print_table(title: str, rows: List[Dict[str, object]]) -> None:
    print(title)
    if not rows:
        print("(none)")
        return
    keys = [key for key in rows[0].keys() if key != "count"] + ["count"]
    print("\t".join(keys))
    for row in rows:
        print("\t".join(str(row.get(key, "")) for key in keys))


def print_text(result: Dict[str, object]) -> None:
    if "by" in result:
        columns = ",".join(result["by"]["columns"])
        print_table(f"by {columns} (status=ok)", result["by"]["ok"])
        print_table(f"by {columns} (all non-missing)", result["by"]["all"])
    if "status" in result:
        print_table("status", [{"value": key, "count": value} for key, value in result["status"].items()])
    if "errors" in result:
        print_table("errors", result["errors"])
    if "batches" in result:
        print_table("batches", result["batches"])
    if "dedup_summary" in result:
        print(json.dumps(result["dedup_summary"], ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize indexed contract catalog.")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--by", choices=["ctype", "ctype,lang"])
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--errors", action="store_true")
    parser.add_argument("--batches", action="store_true")
    parser.add_argument("--dedup", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = build_stats(
            args.out,
            by=args.by,
            include_status=args.status,
            include_errors=args.errors,
            include_batches=args.batches,
            include_dedup=args.dedup,
            dedup=args.dedup,
        )
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
