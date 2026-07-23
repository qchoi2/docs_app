"""Audit and store V4-1R result files without modifying doc_meta."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from audit_t3_v4 import audit_v4
from lib.console import configure_utf8_stdio
from v4_schema import initialize_v4_schema, replace_v4_result


def store_results(
    *,
    out: Path,
    manifest: Path,
    input_dir: Path,
    result_dir: Path,
    report: Path,
    allow_review: bool = False,
) -> dict:
    db_path = out / "catalog.sqlite"
    if not db_path.exists():
        raise ValueError(f"catalog.sqlite not found: {db_path}")
    audit = audit_v4(
        manifest,
        out=out,
        input_dir=input_dir,
        result_dir=result_dir,
        report_path=report,
    )
    stored: list[str] = []
    skipped: list[dict] = []
    with sqlite3.connect(db_path) as conn:
        initialize_v4_schema(conn)
        for row in audit["items"]:
            status = row["status"]
            file_key = str(row["file_key"])
            if status != "pass" and not (allow_review and status == "review"):
                skipped.append({"file_key": file_key, "status": status})
                continue
            result_path = result_dir / f"{file_key}.json"
            if not result_path.exists():
                skipped.append({"file_key": file_key, "status": "result_missing"})
                continue
            data = json.loads(result_path.read_text(encoding="utf-8"))
            file_row = conn.execute(
                "SELECT COALESCE(content_hash,'') FROM files WHERE file_key=?",
                (file_key,),
            ).fetchone()
            if file_row is None:
                skipped.append({"file_key": file_key, "status": "catalog_missing"})
                continue
            replace_v4_result(
                conn,
                file_key=file_key,
                txt_hash=str(file_row[0]),
                data=data,
            )
            stored.append(file_key)
        conn.commit()
    return {
        "stored_count": len(stored),
        "stored": stored,
        "skipped_count": len(skipped),
        "skipped": skipped,
        "audit_summary": audit["summary"],
        "allow_review": allow_review,
    }


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Audit and store V4-1R result files")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--allow-review",
        action="store_true",
        help="Store review rows only after explicit human approval.",
    )
    args = parser.parse_args()
    try:
        payload = store_results(
            out=args.out,
            manifest=args.manifest,
            input_dir=args.input_dir,
            result_dir=args.result_dir,
            report=args.report,
            allow_review=args.allow_review,
        )
    except (OSError, ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
