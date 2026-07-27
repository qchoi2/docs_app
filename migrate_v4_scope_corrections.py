"""Apply deterministic V4 scope/taxonomy corrections to an existing index.

Dry-run is the default. ``--apply`` updates only:

* folder-backed CB purchase and warrant purchase contract types; and
* legacy broad ``RW.SOLVENCY`` items after the v14 leaf split.

No external or paid API is used.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from lib.console import configure_utf8_stdio
from run_v4_expansion import expansion_contract_type, is_primary_contract_path


def analyze(out: Path) -> dict:
    with sqlite3.connect(out / "catalog.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        type_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT file_key,path,ctype,source_signals
                FROM files
                WHERE status!='missing'
                ORDER BY file_key
                """
            )
            if expansion_contract_type(str(row["ctype"]), str(row["path"]))
            != str(row["ctype"])
        ]
        nonleaf = [
            dict(row)
            for row in conn.execute(
                """
                SELECT item_id,file_key,taxonomy_id,loc_start
                FROM v4_clause_item
                WHERE taxonomy_id='RW.SOLVENCY'
                ORDER BY item_id
                """
            )
        ]
        ancillary_empty = [
            dict(row)
            for row in conn.execute(
                """
                SELECT f.file_key,f.path,f.ctype,
                       (SELECT COUNT(*) FROM v4_clause_item i
                        WHERE i.file_key=f.file_key) AS item_count,
                       (SELECT COUNT(*) FROM v4_taxonomy_candidate c
                        WHERE c.evidence_file_key=f.file_key) AS candidate_count
                FROM files f
                JOIN (
                  SELECT file_key
                  FROM v4_document_coverage
                  GROUP BY file_key
                  HAVING SUM(body_status!='not_evaluated')=0
                ) v USING(file_key)
                ORDER BY f.file_key
                """
            )
            if not is_primary_contract_path(str(row["path"]))
            and int(row["item_count"]) == 0
            and int(row["candidate_count"]) == 0
        ]
    return {
        "contract_type_update_count": len(type_rows),
        "contract_type_updates": [
            {
                "file_key": row["file_key"],
                "path": row["path"],
                "from": row["ctype"],
                "to": expansion_contract_type(row["ctype"], row["path"]),
            }
            for row in type_rows
        ],
        "solvency_item_update_count": len(nonleaf),
        "solvency_items": nonleaf,
        "ancillary_empty_v4_document_count": len(ancillary_empty),
        "ancillary_empty_v4_documents": ancillary_empty,
    }


def apply(out: Path, analysis: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(out / "catalog.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        for row in analysis["contract_type_updates"]:
            current = conn.execute(
                "SELECT ctype,source_signals FROM files WHERE file_key=?",
                (row["file_key"],),
            ).fetchone()
            if current is None or str(current["ctype"]) != str(row["from"]):
                raise RuntimeError(
                    f"{row['file_key']}: contract type changed after dry-run"
                )
            try:
                signals = json.loads(current["source_signals"] or "{}")
            except json.JSONDecodeError:
                signals = {}
            if not isinstance(signals, dict):
                signals = {}
            signals["v4_scope_correction"] = {
                "from": row["from"],
                "to": row["to"],
                "reason": "folder-backed V4 debt/warrant contract scope",
                "updated_at": now,
            }
            conn.execute(
                """
                UPDATE files
                SET ctype=?,source_signals=?
                WHERE file_key=?
                """,
                (
                    row["to"],
                    json.dumps(signals, ensure_ascii=False, sort_keys=True),
                    row["file_key"],
                ),
            )
        taxonomy_version = int(
            conn.execute(
                "SELECT value FROM v4_meta WHERE key='taxonomy_version'"
            ).fetchone()[0]
        )
        item_ids = [int(row["item_id"]) for row in analysis["solvency_items"]]
        if item_ids:
            placeholders = ",".join("?" for _ in item_ids)
            updated = conn.execute(
                f"""
                UPDATE v4_clause_item
                SET taxonomy_id='RW.SOLVENCY.GENERAL',
                    taxonomy_version=?,
                    updated_at=?
                WHERE item_id IN ({placeholders})
                  AND taxonomy_id='RW.SOLVENCY'
                """,
                (taxonomy_version, now, *item_ids),
            ).rowcount
            if updated != len(item_ids):
                raise RuntimeError("solvency item set changed after dry-run")
        for row in analysis["ancillary_empty_v4_documents"]:
            file_key = str(row["file_key"])
            counts = conn.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM v4_clause_item WHERE file_key=?),
                  (SELECT COUNT(*) FROM v4_taxonomy_candidate
                   WHERE evidence_file_key=?)
                """,
                (file_key, file_key),
            ).fetchone()
            if counts is None or tuple(map(int, counts)) != (0, 0):
                raise RuntimeError(
                    f"{file_key}: ancillary V4 document is no longer empty"
                )
            conn.execute(
                "DELETE FROM v4_source_coverage WHERE file_key=?",
                (file_key,),
            )
            conn.execute(
                "DELETE FROM v4_document_coverage WHERE file_key=?",
                (file_key,),
            )
        conn.commit()
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        fk_count = len(conn.execute("PRAGMA foreign_key_check").fetchall())
        fts_count = int(conn.execute("SELECT COUNT(*) FROM v4_item_fts").fetchone()[0])
        item_count = int(conn.execute("SELECT COUNT(*) FROM v4_clause_item").fetchone()[0])
    return {
        "contract_type_updated": len(analysis["contract_type_updates"]),
        "solvency_items_updated": len(analysis["solvency_items"]),
        "ancillary_empty_v4_documents_removed": len(
            analysis["ancillary_empty_v4_documents"]
        ),
        "integrity": integrity,
        "foreign_key_violations": fk_count,
        "item_count": item_count,
        "fts_count": fts_count,
    }


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    analysis = analyze(args.out)
    payload = {"mode": "apply" if args.apply else "dry_run", "analysis": analysis}
    if args.apply:
        payload["result"] = apply(args.out, analysis)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
