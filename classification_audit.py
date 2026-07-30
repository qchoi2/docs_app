#!/usr/bin/env python3
"""Audit / fix cross-node misclassification for a known-confusion taxonomy node.

Dry-run by default: prints the bucket counts and sample items. With ``--apply`` it
reclassifies ONLY the airtight ``reclassify`` bucket to the confusion rule's target node
(updating taxonomy_id AND family), after a WAL-safe backup, and logs every change to
scratchpad/ for reversibility. ``keep`` / ``noise`` / ``review`` are never modified.

Seeded confusion: COV.NON_COMPETE -> RW.CONTRACTS (disclosure reps mistagged as
covenants). See lib/classification_audit.py for the structural rules.

Usage:
  python classification_audit.py --node COV.NON_COMPETE            # dry-run
  python classification_audit.py --node COV.NON_COMPETE --apply    # reclassify
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from lib.catalog import require_catalog
from lib.console import configure_utf8_stdio
from lib.classification_audit import CONFUSION_RULES, audit_node, summarize

REPO = Path(__file__).resolve().parent
SCRATCH = REPO / "scratchpad"


def apply_reclassify(db: Path, node: str, target: str, items: list) -> dict:
    fam = target.split(".")[0]
    to_move = [it for it in items if it["bucket"] == "reclassify"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    backup = db.parent / f".backups/catalog.pre_reclassify_{stamp}.sqlite"
    backup.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db)) as s, closing(sqlite3.connect(backup)) as d:
        s.backup(d)
    now = datetime.now(timezone.utc).isoformat()
    log = []
    with closing(sqlite3.connect(db, timeout=30)) as conn:
        conn.execute("PRAGMA busy_timeout=30000")
        for it in to_move:
            conn.execute(
                "UPDATE v4_clause_item SET taxonomy_id=?, family=?, updated_at=? WHERE item_id=?",
                (target, fam, now, it["item_id"]),
            )
            log.append({"item_id": it["item_id"], "file_key": it["file_key"],
                        "item_ref": it["item_ref"], "from": node, "to": target})
        conn.commit()
        integrity = conn.execute("PRAGMA quick_check").fetchone()[0]
    SCRATCH.mkdir(exist_ok=True)
    logpath = SCRATCH / f"reclassify_{node.replace('.', '_')}_{stamp}.jsonl"
    logpath.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in log), encoding="utf-8")
    return {"moved": len(log), "backup": backup.name, "integrity": integrity, "log": str(logpath)}


def main(argv=None) -> int:
    configure_utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("cs_index"))
    ap.add_argument("--node", required=True, help="taxonomy node to audit (e.g. COV.NON_COMPETE)")
    ap.add_argument("--apply", action="store_true", help="reclassify the airtight bucket (DB write)")
    ap.add_argument("--samples", type=int, default=4)
    args = ap.parse_args(argv)

    if args.node not in CONFUSION_RULES:
        print(f"no confusion rule for {args.node}; known: {list(CONFUSION_RULES)}", file=sys.stderr)
        return 2
    rule = CONFUSION_RULES[args.node]
    db = args.out / "catalog.sqlite"
    with closing(sqlite3.connect(f"file:{db}?mode=ro", uri=True)) as conn:
        items = audit_node(conn, args.node)
    counts = summarize(items)

    report = {"node": args.node, "target": rule["target"], "total": len(items), "buckets": counts}
    by_bucket = {b: [it for it in items if it["bucket"] == b] for b in
                 ("reclassify", "keep", "noise", "review")}
    report["samples"] = {b: [(it["verbatim"] or "")[:130] for it in by_bucket[b][:args.samples]]
                         for b in by_bucket}

    if args.apply:
        require_catalog(db)
        result = apply_reclassify(db, args.node, rule["target"], items)
        report["applied"] = result
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
