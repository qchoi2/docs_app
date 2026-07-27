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
                SELECT candidate_id,family,verbatim,source_kind
                FROM v4_taxonomy_candidate
                WHERE status='pending'
                ORDER BY candidate_id
                """
            )
        )
        active_families = {
            str(row[0]): str(row[1])
            for row in conn.execute(
                """
                SELECT taxonomy_id,family
                FROM v4_taxonomy_node WHERE status='active'
                """
            )
        }
    seeded_families = {
        seed.taxonomy_id: seed.family for seed in SEED_TAXONOMY
    }
    known_families = {**seeded_families, **active_families}
    known_ids = set(known_families)
    merges: dict[
        tuple[str, str, tuple[str, ...]], list[int]
    ] = defaultdict(list)
    rejects: dict[str, list[int]] = defaultdict(list)
    unresolved: list[int] = []
    unknown_targets: Counter[str] = Counter()
    target_counts: Counter[str] = Counter()
    item_count = 0
    classification_cache: dict[str, tuple[str, ...]] = {}
    rejection_cache: dict[str, bool] = {}

    for row in rows:
        family = str(row["family"])
        verbatim = str(row["verbatim"])
        taxonomy_ids = classification_cache.get(verbatim)
        if taxonomy_ids is None:
            taxonomy_ids = tuple(classify_text(verbatim))
            classification_cache[verbatim] = taxonomy_ids
        rejected = False
        if taxonomy_ids:
            missing = [value for value in taxonomy_ids if value not in known_ids]
            if missing:
                unknown_targets.update(missing)
                unresolved.append(int(row["candidate_id"]))
                continue
            target_families = {
                known_families[taxonomy_id]
                for taxonomy_id in taxonomy_ids
            }
            if len(target_families) != 1:
                unresolved.append(int(row["candidate_id"]))
                continue
            target_family = next(iter(target_families))
            if (
                target_family != family
                and str(row["source_kind"] or "body") != "body"
            ):
                unresolved.append(int(row["candidate_id"]))
                continue
            merges[
                (family, target_family, taxonomy_ids)
            ].append(int(row["candidate_id"]))
            target_counts.update(taxonomy_ids)
            item_count += len(taxonomy_ids)
        else:
            cached_rejection = rejection_cache.get(verbatim)
            if cached_rejection is None:
                cached_rejection = reject_as_non_atomic(verbatim)
                rejection_cache[verbatim] = cached_rejection
            rejected = cached_rejection
        if not taxonomy_ids and rejected:
            rejects[family].append(int(row["candidate_id"]))
        elif not taxonomy_ids:
            unresolved.append(int(row["candidate_id"]))

    return {
        "pending_before": len(rows),
        "merge_candidate_count": sum(len(value) for value in merges.values()),
        "materialized_item_count": item_count,
        "reject_candidate_count": sum(len(value) for value in rejects.values()),
        "unresolved_candidate_count": len(unresolved),
        "target_counts": dict(target_counts.most_common()),
        "unknown_targets": dict(unknown_targets),
        "family_reassignment_candidate_count": sum(
            len(candidate_ids)
            for (
                source_family,
                target_family,
                _taxonomy_ids,
            ), candidate_ids in merges.items()
            if source_family != target_family
        ),
        "merge_groups": [
            {
                "family": target_family,
                "source_family": source_family,
                "taxonomy_ids": list(taxonomy_ids),
                "candidate_ids": candidate_ids,
                "family_reassignment": source_family != target_family,
            }
            for (
                source_family,
                target_family,
                taxonomy_ids,
            ), candidate_ids in sorted(merges.items())
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
                        "allow_family_reassignment": bool(
                            group.get("family_reassignment")
                        ),
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
    parser.add_argument(
        "--analysis-file",
        type=Path,
        help="reuse a reviewed dry-run JSON analysis instead of recomputing it",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="write the report without echoing the full JSON payload",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    if args.analysis_file:
        loaded = json.loads(args.analysis_file.read_text(encoding="utf-8"))
        analysis = loaded.get("analysis", loaded)
        if not isinstance(analysis, dict):
            raise ValueError("analysis file must contain an analysis object")
        with sqlite3.connect(args.out / "catalog.sqlite") as conn:
            current_pending = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM v4_taxonomy_candidate
                    WHERE status='pending'
                    """
                ).fetchone()[0]
            )
        if current_pending != int(analysis.get("pending_before", -1)):
            raise RuntimeError(
                "analysis file is stale: pending candidate count changed "
                f"from {analysis.get('pending_before')} to {current_pending}"
            )
    else:
        analysis = analyze_candidates(args.out)
    payload = {"mode": "apply" if args.apply else "dry_run", "analysis": analysis}
    if args.apply:
        payload["result"] = apply_analysis(args.out, analysis)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    if not args.quiet:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
