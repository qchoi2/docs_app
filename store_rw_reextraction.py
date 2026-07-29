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

from lib.catalog import require_catalog
from lib.console import configure_utf8_stdio
from prune_backups import DEFAULT_KEEP_DAYS, DEFAULT_KEEP_LATEST, prune

POLARITY = {"affirmative", "negative", "none_exist", "not_applicable"}
CONFIDENCE = {"low", "med", "high"}
# A result carrying one of these in review_method was produced by reading the
# document's reps article start-to-end (proofread), so it reconstructs the whole
# RW family and is authoritative — it overrides the regression guard for that one
# document. Auto-extraction results (no marker) keep the guard.
_FULL_READ_MARKERS = {"full_read", "full-read", "fullread", "proofread", "정독"}

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


def _normalize_tid(tid, known_rw: set):
    """Map an unknown leaf (e.g. a GPT-invented RW.IP.NO_ENCUMBRANCE) to the
    nearest known RW ancestor (RW.IP). Coverage/absence work at the sub-domain
    level, so this preserves meaning. Returns None only if nothing resolves."""
    parts = str(tid or "").split(".")
    while parts:
        cand = ".".join(parts)
        if cand in known_rw:
            return cand
        parts.pop()
    return None


def store_one(conn: sqlite3.Connection, out: Path, data: dict, known_rw: set,
              mode: str = "replace", allow_regress: bool = False) -> dict:
    file_key = str(data["file_key"])
    # A proofread result reconstructs the ENTIRE RW family from a full reading of
    # the reps article, so a sub-domain it omits is a deliberate correction (a
    # mis-classified or genuinely absent rep), not an incomplete extraction. Such
    # a result overrides the regression guard for THIS document only.
    full_read = str(data.get("review_method", "")).strip().lower() in _FULL_READ_MARKERS
    effective_allow_regress = allow_regress or full_read
    items = data.get("items") or []
    if not items:
        return {"file_key": file_key, "status": "skipped_no_items"}
    normalized_count = 0
    for it in items:
        tid = it.get("taxonomy_id")
        if tid not in known_rw:
            norm = _normalize_tid(tid, known_rw)
            if norm is None:
                raise ValueError(f"{file_key}: taxonomy_id not resolvable to RW: {tid}")
            if norm != tid:
                normalized_count += 1
            it["taxonomy_id"] = norm
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

    def _dom(t):
        p = str(t).split(".")
        return "RW." + p[1] if len(p) >= 2 else str(t)

    # replace: re-extract the whole RW family (preserving resolved-candidate items).
    # add: append the supplied items (targeted fix for missed sub-domains); existing
    #      items and coverage are left as-is.
    prefix = "RWRX" if mode == "replace" else "RWADD"
    prev_domains = set()
    if mode == "replace":
        # Re-extraction now covers the COMPLETE RW set — seller/target AND buyer
        # (RW.BUYER) reps. So RW.BUYER is part of the regression check too: if the
        # new result drops a sub-domain the doc already has (including RW.BUYER),
        # skip it. This protects docs whose buyer reps came from the original V4
        # extraction when an older buyer-less result is (re-)stored against them.
        prev_domains = {
            _dom(r[0]) for r in conn.execute(
                "SELECT taxonomy_id FROM v4_clause_item WHERE file_key=? "
                "AND family='RW'",
                (file_key,),
            )
        }
        new_domains = {_dom(it["taxonomy_id"]) for it in items}
        dropped = prev_domains - new_domains
        if dropped and not effective_allow_regress:
            return {"file_key": file_key, "status": "skipped_regression",
                    "lost_domains": sorted(dropped)}
    if mode == "replace":
        # Full RW replace including RW.BUYER — the agent supplies the complete set.
        # Only resolved-candidate/-TC items are preserved (materialized elsewhere).
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
                "DELETE FROM v4_clause_item WHERE file_key=? AND family='RW'",
                (file_key,),
            )
    else:  # add: avoid duplicate refs from a prior add run
        conn.execute(
            "DELETE FROM v4_clause_item WHERE file_key=? AND family='RW' AND item_ref LIKE 'RWADD-%'",
            (file_key,),
        )
    now = datetime.now(timezone.utc).isoformat()
    for i, it in enumerate(items, 1):
        rec = {
            "file_key": file_key, "item_ref": f"{prefix}-{i:03d}", "family": "RW",
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
    if mode == "replace":
        conn.execute(
            "UPDATE v4_document_coverage SET body_status='complete', reason=? "
            "WHERE file_key=? AND family='RW'",
            (data.get("reason", "RW 하위영역 전수 재추출 (2026-07-28)"), file_key),
        )
    n = conn.execute(
        "SELECT COUNT(*) FROM v4_clause_item WHERE file_key=? AND family='RW'", (file_key,)
    ).fetchone()[0]
    lost = []
    if mode == "replace":
        new_domains = {_dom(t) for t in (it["taxonomy_id"] for it in items)}
        lost = sorted(prev_domains - new_domains)  # substantive domains dropped
    res = {"file_key": file_key, "status": "stored", "mode": mode,
           "rw_items": n, "added": len(items)}
    if full_read:
        res["review_method"] = "full_read"
    if lost:
        res["lost_domains"] = lost  # potential regression: fewer reps than before
        if full_read:
            # proofread deliberately dropped these domains — surface for owner review
            res["regress_overridden"] = True
    return res


def main(argv=None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("cs_index"))
    parser.add_argument("--result-dir", type=Path, default=Path("cs_index/rw_reextract_results"))
    parser.add_argument("--file-key", help="store only this file_key")
    parser.add_argument("--mode", choices=["replace", "add"], default="replace",
                        help="replace = full RW re-extraction; add = append supplied items only")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate every result and roll back — no DB change, no backup")
    parser.add_argument("--allow-regress", action="store_true",
                        help="store even results that drop sub-domains the doc already has "
                        "(default: skip such docs to protect existing reps)")
    parser.add_argument("--prune-backups", action="store_true",
                        help="after a successful snapshot, apply the retention policy "
                        "(prune_backups.py) so old snapshots stop accumulating")
    parser.add_argument("--prune-keep-latest", type=int, default=DEFAULT_KEEP_LATEST)
    parser.add_argument("--prune-keep-days", type=float, default=DEFAULT_KEEP_DAYS)
    args = parser.parse_args(argv)

    db = args.out / "catalog.sqlite"
    files = sorted(args.result_dir.glob("*.json"))
    if args.file_key:
        files = [args.result_dir / f"{args.file_key}.json"]
    files = [f for f in files if f.exists()]
    if not files:
        print(json.dumps({"stored": 0, "note": "no result files"}, ensure_ascii=False))
        return 0

    backup_name = None
    pruned = None
    if not args.dry_run:
        require_catalog(db)  # never snapshot (or write to) a catalog we just created
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        backup = args.out / f".backups/catalog.pre_rw_reextract_{stamp}.sqlite"
        backup.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(db)) as s, closing(sqlite3.connect(backup)) as d:
            s.backup(d)
        backup_name = backup.name
        if args.prune_backups:
            # Only after the fresh snapshot exists, so it is always the newest kept one.
            report = prune(out=args.out, keep_latest=args.prune_keep_latest,
                           keep_days=args.prune_keep_days, delete=True)
            pruned = {"removed": report["counts"]["prune"],
                      "reclaimed": report["reclaimable_h"]}

    results = []
    with closing(sqlite3.connect(db)) as conn:
        known_rw = {
            r[0] for r in conn.execute("SELECT taxonomy_id FROM v4_taxonomy_node WHERE family='RW'")
        }
        for f in files:
            fk = f.stem
            sp = conn.execute("SAVEPOINT one")
            try:
                data = json.loads(f.read_text(encoding="utf-8-sig"))  # tolerate BOM
                res = store_one(conn, args.out, data, known_rw, mode=args.mode,
                                allow_regress=args.allow_regress)
            except Exception as exc:  # isolate a bad result — never abort the batch
                conn.execute("ROLLBACK TO one")
                res = {"file_key": fk, "status": "error", "error": str(exc)[:200]}
            conn.execute("RELEASE one")
            results.append(res)
        if args.dry_run:
            conn.rollback()
            integrity = "n/a (dry-run)"
        else:
            conn.commit()
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    from collections import Counter
    by_status = Counter(r["status"] for r in results)
    errors = [r for r in results if r["status"] == "error"]
    regressions = [
        {"file_key": r["file_key"], "lost_domains": r["lost_domains"]}
        for r in results if r.get("status") == "skipped_regression"
    ]
    full_read_stored = sum(1 for r in results if r.get("review_method") == "full_read")
    regress_overridden = [
        {"file_key": r["file_key"], "lost_domains": r["lost_domains"]}
        for r in results if r.get("regress_overridden")
    ]
    print(json.dumps(
        {"dry_run": args.dry_run, "backup": backup_name, "pruned": pruned,
         "files": len(files),
         "by_status": dict(by_status), "integrity": integrity,
         "full_read_stored": full_read_stored,
         "regress_overridden_count": len(regress_overridden),
         "regress_overridden": regress_overridden[:40],
         "regression_count": len(regressions), "regressions": regressions[:40],
         "errors": errors[:40]},
        ensure_ascii=False, indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
