"""Plan the RW re-extraction batch (root fix ②, extraction half).

Emits a prioritized manifest of the RW under-extracted documents (those the
coverage audit demoted to partial with reason 'rw_subdomain_audit_pending'),
annotated with which core representation sub-domains are missing vs present.
An AI-client extraction session consumes this manifest to re-extract each
document's seller-representation article per .docs/extract_prompt_v4_rw_addendum.md
(every sub-domain either extracted as items or explicitly present=false), then
stores via replace_v4_result and re-audits. Read-only; writes only the manifest.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from lib.console import configure_utf8_stdio
from audit_rw_coverage import CORE_RW_SUBDOMAINS, _domain

# Type processing order (V4_PLAN §6 priority, incl. approved CB/BW/EB scope).
CTYPE_ORDER = [
    "SPA", "SSA", "SHA", "ATA/BTA",
    "CB인수계약", "CB매수계약", "BW인수계약", "W매수계약", "EB인수계약",
]


def plan(out: Path) -> list:
    db = out / "catalog.sqlite"
    with closing(sqlite3.connect(f"file:{db}?mode=ro", uri=True)) as conn:
        targets = [
            str(r[0])
            for r in conn.execute(
                "SELECT file_key FROM v4_document_coverage "
                "WHERE family='RW' AND reason LIKE '%rw_subdomain_audit_pending%'"
            )
        ]
        meta = {
            str(r[0]): {"ctype": r[1], "lang": r[2], "path": r[3]}
            for r in conn.execute("SELECT file_key,ctype,lang,path FROM files")
        }
        present: dict[str, set] = {}
        for fk, tid in conn.execute(
            "SELECT file_key,taxonomy_id FROM v4_clause_item WHERE family='RW'"
        ):
            present.setdefault(str(fk), set()).add(_domain(str(tid)))
    core = set(CORE_RW_SUBDOMAINS)
    rows = []
    for fk in targets:
        m = meta.get(fk, {})
        have = present.get(fk, set()) & core
        rows.append(
            {
                "file_key": fk,
                "ctype": m.get("ctype"),
                "lang": m.get("lang"),
                "present_subdomains": sorted(have),
                "missing_subdomains": [d for d in CORE_RW_SUBDOMAINS if d not in have],
            }
        )
    rank = {c: i for i, c in enumerate(CTYPE_ORDER)}
    rows.sort(key=lambda r: (rank.get(r["ctype"], len(CTYPE_ORDER)), r["file_key"]))
    return rows


def main(argv=None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("cs_index"))
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("cs_index/rw_reextraction_manifest.json"),
    )
    parser.add_argument("--limit", type=int, help="only the first N targets")
    parser.add_argument(
        "--shard",
        help="k/N — emit only shard k of N (1-indexed), for parallel agents. "
        "Disjoint, priority-balanced (every Nth doc).",
    )
    parser.add_argument(
        "--skip-existing",
        type=Path,
        help="drop targets that already have a result JSON in this directory "
        "(avoid re-doing docs other agents finished).",
    )
    args = parser.parse_args(argv)
    rows = plan(args.out)
    if args.skip_existing:
        done = {p.stem for p in args.skip_existing.glob("*.json")}
        rows = [r for r in rows if r["file_key"] not in done]
    if args.shard:
        k, n = (int(x) for x in args.shard.split("/"))
        if not (1 <= k <= n):
            parser.error("--shard k/N requires 1 <= k <= N")
        rows = rows[k - 1 :: n]
    if args.limit:
        rows = rows[: args.limit]
    args.manifest.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    from collections import Counter

    by_ct = Counter(r["ctype"] for r in rows)
    print(
        json.dumps(
            {
                "targets": len(rows),
                "manifest": str(args.manifest),
                "by_ctype": dict(by_ct),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
