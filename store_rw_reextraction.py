"""Store RW re-extraction results per document (root fix ②, batch executor).

For each `cs_index/rw_reextract_results/<file_key>.json` (produced by an AI
client reading the document's seller-representation article per
.docs/extract_prompt_v4_rw_addendum.md), this surgically re-extracts ONLY the
RW family: preserves RW items linked to resolved taxonomy candidates (and -TC
items), replaces the rest with the result's items, and marks RW coverage
genuinely complete (clearing the rw_subdomain_audit_pending flag). Non-RW
families are untouched.

Result JSON shape:
  { "file_key": "<key>",
    "reason": "optional coverage reason",
    "items": [ { "taxonomy_id": "RW.LABOR", "proposition": "...",
                 "verbatim": "...", "loc_start": 109, "loc_end": 109,
                 "statement_polarity": "affirmative|none_exist|negative|not_applicable",
                 "subject_role": "대상회사", "confidence": "high" }, ... ] }

WAL-safe backup once per run. Idempotent (clears prior RWRX-* rows per doc).
Read-only validation of taxonomy_ids before any write.

Usage:  python store_rw_reextraction.py [--out cs_index] [--result-dir DIR] [--file-key K]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from lib.console import configure_utf8_stdio

POLARITY = {"affirmative", "negative", "none_exist", "not_applicable"}
CONFIDENCE = {"low", "med", "high"}

COLS = [
    "file_key", "item_ref", "family", "taxonomy_id", "proposition", "statement_polarity",
    "subject_role", "counterparty_role", "action", "object_type", "effective_time",
    "source_kind", "source_id", "source_name", "source_ref", "parent_clause_ref",
    "related_item_ref", "qualifier_json", "verbatim", "loc_start", "loc_end",
    "normalized_json", "confidence", "txt_hash", "taxonomy_version",
    "extractor_version", "prompt_version", "review_status", "created_at", "updated_at",
]


def _preserved_rw_item_ids(conn: sqlite3.Connection, file_key: str) -> set:
    """RW items linked to resolved candidates or carrying -TC refs — keep these."""
    resolved: set = set()
    for (raw,) in conn.execute(
        "SELECT resolution_json FROM v4_taxonomy_candidate "
        "WHERE evidence_file_key=? AND status IN ('merged','approved')",
        (file_key,),
    ):
        try:
            res = json.loads(str(raw or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        ids = res.get("materialized_item_ids")
        if not isinstance(ids, list):
            one = res.get("materialized_item_id")
            ids = [one] if isinstance(one, int) else []
        resolved.update(int(x) for x in ids if isinstance(x, int))
    keep: set = set()
    for item_id, item_ref in conn.execute(
        "SELECT item_id,item_ref FROM v4_clause_item WHERE file_key=? AND family='RW'",
        (file_key,),
    ):
        if "-TC" in str(item_ref) or int(item_id) in resolved:
            keep.add(int(item_id))
    return keep


def store_one(conn: sqlite3.Connection, out: Path, data: dict, known_rw: set) -> dict:
    file_key = str(data["file_key"])
    items = data.get("items") or []
    if not items:
        return {"file_key": file_key, "status": "skipped_no_items"}
    for it in items:
        tid = it.get("taxonomy_id")
        if tid not in known_rw:
            raise ValueError(f"{file_key}: taxonomy_id not a known RW node: {tid}")
        if it.get("statement_polarity") not in POLARITY:
            raise ValueError(f"{file_key}: bad statement_polarity: {it.get('statement_polarity')}")
    row = conn.execute(
        "SELECT COALESCE(content_hash,'') FROM files WHERE file_key=?", (file_key,)
    ).fetchone()
    if row is None:
        return {"file_key": file_key, "status": "not_in_catalog"}
    txt_hash = str(row[0])
    tax_version = conn.execute(
        "SELECT MAX(taxonomy_version) FROM v4_clause_item"
    ).fetchone()[0] or 19

    keep = _preserved_rw_item_ids(conn, file_key)
    if keep:
        placeholders = ",".join("?" for _ in keep)
        conn.execute(
            f"DELETE FROM v4_clause_item WHERE file_key=? AND family='RW' "
            f"AND item_id NOT IN ({placeholders})",
            (file_key, *keep),
        )
    else:
        conn.execute(
            "DELETE FROM v4_clause_item WHERE file_key=? AND family='RW'", (file_key,)
        )
    now = datetime.now(timezone.utc).isoformat()
    for i, it in enumerate(items, 1):
        rec = {
            "file_key": file_key, "item_ref": f"RWRX-{i:03d}", "family": "RW",
            "taxonomy_id": it["taxonomy_id"], "proposition": it["proposition"],
            "statement_polarity": it["statement_polarity"],
            "subject_role": it.get("subject_role"), "counterparty_role": it.get("counterparty_role", "매수인"),
            "action": it.get("action", "진술 및 보장"), "object_type": it.get("object_type"),
            "effective_time": it.get("effective_time"), "source_kind": "body",
            "source_id": None, "source_name": None, "source_ref": None,
            "parent_clause_ref": it.get("parent_clause_ref"), "related_item_ref": None,
            "qualifier_json": json.dumps(it.get("qualifier", {}), ensure_ascii=False),
            "verbatim": str(it["verbatim"])[:2000], "loc_start": int(it["loc_start"]),
            "loc_end": int(it.get("loc_end", it["loc_start"])), "normalized_json": "{}",
            "confidence": it.get("confidence", "high") if it.get("confidence", "high") in CONFIDENCE else "high",
            "txt_hash": txt_hash, "taxonomy_version": tax_version,
            "extractor_version": "claude-rw-reextract-20260728",
            "prompt_version": "extract_prompt_v4_rw_addendum",
            "review_status": "approved", "created_at": now, "updated_at": now,
        }
        conn.execute(
            f"INSERT INTO v4_clause_item({','.join(COLS)}) "
            f"VALUES ({','.join('?' for _ in COLS)})",
            [rec[c] for c in COLS],
        )
    conn.execute(
        "UPDATE v4_document_coverage SET body_status='complete', reason=? "
        "WHERE file_key=? AND family='RW'",
        (data.get("reason", "RW 하위영역 전수 재추출 (2026-07-28)"), file_key),
    )
    n = conn.execute(
        "SELECT COUNT(*) FROM v4_clause_item WHERE file_key=? AND family='RW'", (file_key,)
    ).fetchone()[0]
    return {"file_key": file_key, "status": "stored", "rw_items": n, "added": len(items)}


def main(argv=None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("cs_index"))
    parser.add_argument("--result-dir", type=Path, default=Path("cs_index/rw_reextract_results"))
    parser.add_argument("--file-key", help="store only this file_key")
    args = parser.parse_args(argv)

    db = args.out / "catalog.sqlite"
    files = sorted(args.result_dir.glob("*.json"))
    if args.file_key:
        files = [args.result_dir / f"{args.file_key}.json"]
    files = [f for f in files if f.exists()]
    if not files:
        print(json.dumps({"stored": 0, "note": "no result files"}, ensure_ascii=False))
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    backup = args.out / f".backups/catalog.pre_rw_reextract_{stamp}.sqlite"
    backup.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db)) as s, closing(sqlite3.connect(backup)) as d:
        s.backup(d)

    results = []
    with closing(sqlite3.connect(db)) as conn:
        known_rw = {
            r[0] for r in conn.execute("SELECT taxonomy_id FROM v4_taxonomy_node WHERE family='RW'")
        }
        for f in files:
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append(store_one(conn, args.out, data, known_rw))
        conn.commit()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    stored = [r for r in results if r["status"] == "stored"]
    print(json.dumps(
        {"backup": backup.name, "stored_count": len(stored), "integrity": integrity,
         "results": results},
        ensure_ascii=False, indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
