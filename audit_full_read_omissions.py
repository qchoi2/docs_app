#!/usr/bin/env python3
"""Backfill the strong heading-vs-domain omission guard over stored full reads.

Read-only by default.  ``--apply`` downgrades only affected RW coverage rows from
complete to partial after a WAL-safe backup.  It never fabricates clause items and
never opens an absence gate.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from lib.console import configure_utf8_stdio
from lib.full_read_guard import FULL_READ_MARKERS, full_read_heading_omissions


def _full_read_files(result_dir: Path) -> list[tuple[str, Path]]:
    rows = []
    for path in sorted(result_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        marker = str(data.get("review_method") or "").strip().casefold()
        if marker in FULL_READ_MARKERS:
            rows.append((str(data.get("file_key") or path.stem), path))
    return rows


def audit(out: Path, result_dir: Path) -> dict:
    db = out / "catalog.sqlite"
    findings = []
    with closing(sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)) as conn:
        for file_key, result_path in _full_read_files(result_dir):
            coverage = conn.execute(
                "SELECT body_status,reason FROM v4_document_coverage "
                "WHERE file_key=? AND family='RW'",
                (file_key,),
            ).fetchone()
            if coverage is None:
                continue
            omissions = full_read_heading_omissions(conn, out, file_key)
            if omissions:
                findings.append(
                    {
                        "file_key": file_key,
                        "result_file": str(result_path),
                        "body_status": coverage[0],
                        "omissions": omissions,
                    }
                )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "full_read_results": len(_full_read_files(result_dir)),
        "finding_count": len(findings),
        "complete_rows_at_risk": sum(x["body_status"] == "complete" for x in findings),
        "findings": findings,
    }


def apply_partial(out: Path, findings: list[dict]) -> dict:
    targets = [x for x in findings if x["body_status"] == "complete"]
    if not targets:
        return {"changed": 0, "backup": None}
    db = out / "catalog.sqlite"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    backup = out / ".backups" / f"catalog.pre_full_read_omission_{stamp}.sqlite"
    backup.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db)) as src, closing(sqlite3.connect(backup)) as dst:
        src.backup(dst)
    changed = 0
    with closing(sqlite3.connect(db)) as conn:
        for finding in targets:
            domains = ",".join(sorted(finding["omissions"]))
            cur = conn.execute(
                "UPDATE v4_document_coverage SET body_status='partial', "
                "reason=COALESCE(reason,'')||? "
                "WHERE file_key=? AND family='RW' AND body_status='complete'",
                (f" | full_read_heading_omission:{domains}", finding["file_key"]),
            )
            changed += cur.rowcount
        conn.commit()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    return {"changed": changed, "backup": str(backup), "integrity": integrity}


def main(argv=None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("cs_index"))
    parser.add_argument(
        "--result-dir", type=Path, default=Path("cs_index/rw_reextract_results")
    )
    parser.add_argument(
        "--report", type=Path, default=Path(".docs/full_read_omission_backfill.json")
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    report = audit(args.out, args.result_dir)
    if args.apply:
        report["apply"] = apply_partial(args.out, report["findings"])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "full_read_results": report["full_read_results"],
                "finding_count": report["finding_count"],
                "complete_rows_at_risk": report["complete_rows_at_risk"],
                "apply": report.get("apply"),
                "report": str(args.report),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
