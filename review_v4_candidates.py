"""Deterministically review and optionally resolve pending V4 taxonomy candidates.

Dry-run is the default.  ``--apply`` uses taxonomy_admin's transactional
resolution path, so every merge also creates coordinate-backed searchable
clause items.  No external or paid API is used.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from finalize_v4_remaining_nine import classify_text, reject_as_non_atomic
from lib.console import configure_utf8_stdio
from taxonomy_admin import MAX_BATCH, resolve_candidates
from v4_schema import SEED_TAXONOMY, initialize_v4_schema


def _chunks(values: list[int], size: int = MAX_BATCH):
    for start in range(0, len(values), size):
        yield values[start : start + size]


def analyze_candidates(out: Path) -> dict:
    db = Path(out) / "catalog.sqlite"
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = list(
            conn.execute(
                """
                SELECT candidate_id,family,verbatim
                FROM v4_taxonomy_candidate
                WHERE status='pending'
                ORDER BY candidate_id
                """
            )
        )
        active_ids = {
            str(row[0])
            for row in conn.execute(
                "SELECT taxonomy_id FROM v4_taxonomy_node WHERE status='active'"
            )
        }
    seeded_ids = {seed.taxonomy_id for seed in SEED_TAXONOMY}
    known_ids = active_ids | seeded_ids
    merges: dict[tuple[str, tuple[str, ...]], list[int]] = defaultdict(list)
    rejects: dict[str, list[int]] = defaultdict(list)
    unresolved: list[int] = []
    unknown_targets: Counter[str] = Counter()
    target_counts: Counter[str] = Counter()
    item_count = 0

    for row in rows:
        family = str(row["family"])
        taxonomy_ids = tuple(
            taxonomy_id
            for taxonomy_id in classify_text(str(row["verbatim"]))
            if taxonomy_id.split(".", 1)[0] == family
        )
        if taxonomy_ids:
            missing = [value for value in taxonomy_ids if value not in known_ids]
            if missing:
                unknown_targets.update(missing)
                unresolved.append(int(row["candidate_id"]))
                continue
            merges[(family, taxonomy_ids)].append(int(row["candidate_id"]))
            target_counts.update(taxonomy_ids)
            item_count += len(taxonomy_ids)
        elif reject_as_non_atomic(str(row["verbatim"])):
            rejects[family].append(int(row["candidate_id"]))
        else:
            unresolved.append(int(row["candidate_id"]))

    return {
        "pending_before": len(rows),
        "merge_candidate_count": sum(len(value) for value in merges.values()),
        "materialized_item_count": item_count,
        "reject_candidate_count": sum(len(value) for value in rejects.values()),
        "unresolved_candidate_count": len(unresolved),
        "target_counts": dict(target_counts.most_common()),
        "unknown_targets": dict(unknown_targets),
        "merge_groups": [
            {
                "family": family,
                "taxonomy_ids": list(taxonomy_ids),
                "candidate_ids": candidate_ids,
            }
            for (family, taxonomy_ids), candidate_ids in sorted(merges.items())
        ],
        "reject_groups": [
            {"family": family, "candidate_ids": candidate_ids}
            for family, candidate_ids in sorted(rejects.items())
        ],
        "unresolved_candidate_ids": unresolved,
    }


def apply_analysis(out: Path, analysis: dict) -> dict:
    if analysis["unknown_targets"]:
        raise RuntimeError(
            "candidate analysis contains unknown taxonomy targets: "
            + ", ".join(analysis["unknown_targets"])
        )
    with sqlite3.connect(Path(out) / "catalog.sqlite") as conn:
        initialize_v4_schema(conn)
        conn.commit()

    actions = []
    for group in analysis["merge_groups"]:
        for candidate_ids in _chunks(group["candidate_ids"]):
            actions.append(
                resolve_candidates(
                    out,
                    {
                        "action": "merge",
                        "candidate_ids": candidate_ids,
                        "taxonomy_ids": group["taxonomy_ids"],
                        "reason": (
                            "현재 taxonomy의 기존 leaf와 일치하는 반복 문구를 "
                            "검증된 결정 규칙으로 원자 분류"
                        ),
                    },
                )
            )
    for group in analysis["reject_groups"]:
        for candidate_ids in _chunks(group["candidate_ids"]):
            actions.append(
                resolve_candidates(
                    out,
                    {
                        "action": "reject",
                        "candidate_ids": candidate_ids,
                        "reason": "제목·리드인·편집주석 등 독립된 법적 명제가 아닌 문구",
                    },
                )
            )
    with sqlite3.connect(Path(out) / "catalog.sqlite") as conn:
        pending_after = int(
            conn.execute(
                "SELECT COUNT(*) FROM v4_taxonomy_candidate WHERE status='pending'"
            ).fetchone()[0]
        )
    return {
        "action_count": len(actions),
        "resolved_candidate_count": sum(
            int(action["resolved_count"]) for action in actions
        ),
        "materialized_item_count": sum(
            int(action["materialized_count"]) for action in actions
        ),
        "pending_after": pending_after,
        "actions": actions,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dry-run or apply deterministic V4 taxonomy-candidate review."
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--apply", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    analysis = analyze_candidates(args.out)
    payload = {"mode": "apply" if args.apply else "dry_run", "analysis": analysis}
    if args.apply:
        payload["result"] = apply_analysis(args.out, analysis)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
