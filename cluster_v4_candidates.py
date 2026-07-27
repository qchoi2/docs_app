"""Build a deterministic review queue for pending V4 taxonomy candidates.

The report groups exact normalized propositions while preserving candidate
ids, document coordinates, contract types, and nearest taxonomy nodes.  It is
read-only and does not call an external API.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from lib.console import configure_utf8_stdio


def normalize_candidate_text(value: str) -> str:
    return re.sub(r"[\W_]+", " ", value.casefold(), flags=re.UNICODE).strip()


def cluster_rows(rows: list[dict], *, min_count: int = 2) -> list[dict]:
    grouped: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        key = (
            str(row["family"]),
            str(row.get("nearest_taxonomy_id") or ""),
            normalize_candidate_text(str(row["verbatim"])),
        )
        grouped[key].append(row)

    clusters = []
    for (family, nearest, normalized), members in grouped.items():
        if len(members) < min_count:
            continue
        document_keys = {
            str(row["evidence_file_key"])
            for row in members
        }
        ctypes = Counter(str(row.get("ctype") or "미분류") for row in members)
        languages = Counter(str(row.get("lang") or "미분류") for row in members)
        clusters.append(
            {
                "family": family,
                "nearest_taxonomy_id": nearest or None,
                "normalized_text": normalized,
                "verbatim": str(members[0]["verbatim"]),
                "candidate_count": len(members),
                "document_count": len(document_keys),
                "contract_type_count": len(ctypes),
                "contract_types": dict(ctypes.most_common()),
                "languages": dict(languages.most_common()),
                "candidate_ids": [
                    int(row["candidate_id"])
                    for row in members
                ],
                "evidence": [
                    {
                        "candidate_id": int(row["candidate_id"]),
                        "file_key": str(row["evidence_file_key"]),
                        "path": str(row.get("path") or ""),
                        "loc_start": int(row["loc_start"]),
                        "loc_end": int(row["loc_end"]),
                    }
                    for row in members[:5]
                ],
            }
        )
    clusters.sort(
        key=lambda row: (
            -int(row["document_count"]),
            -int(row["candidate_count"]),
            -int(row["contract_type_count"]),
            str(row["family"]),
            str(row["normalized_text"]),
        )
    )
    return clusters


def build_report(
    out: Path,
    *,
    min_count: int = 2,
    limit: int = 500,
) -> dict:
    with sqlite3.connect(out / "catalog.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT c.candidate_id,c.family,c.nearest_taxonomy_id,
                       c.verbatim,c.evidence_file_key,c.loc_start,c.loc_end,
                       f.ctype,f.lang,f.path
                FROM v4_taxonomy_candidate c
                JOIN files f ON f.file_key=c.evidence_file_key
                WHERE c.status='pending'
                ORDER BY c.candidate_id
                """
            )
        ]
    clusters = cluster_rows(rows, min_count=min_count)
    family_counts = Counter(str(row["family"]) for row in rows)
    repeated_candidates = sum(
        int(cluster["candidate_count"]) for cluster in clusters
    )
    return {
        "mode": "read_only",
        "pending_candidate_count": len(rows),
        "family_counts": dict(sorted(family_counts.items())),
        "minimum_cluster_count": min_count,
        "repeated_cluster_count": len(clusters),
        "repeated_candidate_count": repeated_candidates,
        "reported_cluster_count": min(limit, len(clusters)),
        "clusters": clusters[:limit],
    }


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--min-count", type=int, default=2)
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args(argv)
    if args.min_count < 2:
        raise SystemExit("--min-count must be at least 2")
    if not 1 <= args.limit <= 5000:
        raise SystemExit("--limit must be between 1 and 5000")
    payload = build_report(
        args.out,
        min_count=args.min_count,
        limit=args.limit,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                key: value
                for key, value in payload.items()
                if key != "clusters"
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
