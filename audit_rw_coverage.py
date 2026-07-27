"""RW representation coverage audit (root fix ②, honesty half).

Per .docs/V4_RW_COVERAGE_DEFECT_20260727.md, RW body_status='complete' was
blanket-stamped while substantive representation sub-domains were never
extracted. This tool checks each RW-complete document against a checklist of
core seller-representation sub-domains and:

  * report  (default): lists per-domain coverage and flags under-extracted docs
             (re-extraction targets). Read-only.
  * --apply: reclassifies flagged docs' RW body_status 'complete' -> 'partial'
             with reason 'rw_subdomain_audit_pending' (WAL-safe backup first),
             so coverage stops over-claiming and re-extraction can be tracked.

The absence query gate (ABSENCE_UNVERIFIED_FAMILIES) already protects users at
query time; this makes the stored coverage honest and enumerates the re-extract
backlog. Full re-extraction of the missing reps is a separate AI-client batch.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from lib.console import configure_utf8_stdio

# Core substantive seller-representation sub-domains expected in a typical full
# acquisition rep article. A RW-complete doc missing many of these is almost
# certainly under-extracted (not a contract that genuinely lacks them).
CORE_RW_SUBDOMAINS = [
    "RW.TAX", "RW.LITIGATION", "RW.COMPLIANCE", "RW.CONTRACTS", "RW.LABOR",
    "RW.IP", "RW.ENVIRONMENT", "RW.PERMITS", "RW.FINANCIAL", "RW.ASSETS",
    "RW.REAL_ESTATE", "RW.INSURANCE",
]


def _domain(taxonomy_id: str) -> str:
    parts = taxonomy_id.split(".")
    return "RW." + parts[1] if len(parts) >= 2 else taxonomy_id


def audit(out: Path, min_core: int) -> dict:
    db = out / "catalog.sqlite"
    with closing(sqlite3.connect(f"file:{db}?mode=ro", uri=True)) as conn:
        complete = [
            str(r[0])
            for r in conn.execute(
                "SELECT file_key FROM v4_document_coverage "
                "WHERE family='RW' AND body_status='complete'"
            )
        ]
        present: dict[str, set] = {}
        for fk, tid in conn.execute(
            "SELECT file_key,taxonomy_id FROM v4_clause_item WHERE family='RW'"
        ):
            present.setdefault(str(fk), set()).add(_domain(str(tid)))
    core = set(CORE_RW_SUBDOMAINS)
    per_domain = {d: 0 for d in CORE_RW_SUBDOMAINS}
    flagged = []
    core_hits = []
    for fk in complete:
        have = present.get(fk, set())
        hits = have & core
        core_hits.append(len(hits))
        for d in hits:
            per_domain[d] += 1
        if len(hits) < min_core:
            flagged.append(fk)
    n = len(complete) or 1
    return {
        "rw_complete_docs": len(complete),
        "min_core_threshold": min_core,
        "flagged_underextracted": flagged,
        "flagged_count": len(flagged),
        "core_domain_doc_coverage": {
            d: {"docs": per_domain[d], "pct": round(100 * per_domain[d] / n, 1)}
            for d in CORE_RW_SUBDOMAINS
        },
        "core_hits_distribution": {
            str(k): core_hits.count(k) for k in range(0, len(CORE_RW_SUBDOMAINS) + 1) if core_hits.count(k)
        },
    }


def apply_reclassify(out: Path, flagged: list) -> int:
    """Set RW body_status 'complete' -> 'partial' for flagged docs (backup first)."""
    db = out / "catalog.sqlite"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    backup = out / f".backups/catalog.pre_rw_audit_{stamp}.sqlite"
    backup.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db)) as src, closing(sqlite3.connect(backup)) as dst:
        src.backup(dst)  # WAL-safe online backup
    changed = 0
    with closing(sqlite3.connect(db)) as conn:
        for fk in flagged:
            cur = conn.execute(
                "UPDATE v4_document_coverage SET body_status='partial', "
                "reason=COALESCE(reason,'')||' | rw_subdomain_audit_pending' "
                "WHERE family='RW' AND file_key=? AND body_status='complete'",
                (fk,),
            )
            changed += cur.rowcount
        conn.commit()
    return changed


def main(argv=None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("cs_index"))
    parser.add_argument(
        "--min-core",
        type=int,
        default=6,
        help="A RW-complete doc with fewer than this many core sub-domains is "
        "flagged as under-extracted (default 6 of %d)." % len(CORE_RW_SUBDOMAINS),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Reclassify flagged docs' RW coverage complete->partial (backup first).",
    )
    args = parser.parse_args(argv)
    report = audit(args.out, args.min_core)
    if args.apply:
        report["reclassified_rows"] = apply_reclassify(
            args.out, report["flagged_underextracted"]
        )
    # keep the flagged list out of stdout summary (can be large)
    summary = {k: v for k, v in report.items() if k != "flagged_underextracted"}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
