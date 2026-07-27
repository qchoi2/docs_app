"""Apply a reviewed UTF-8 V4 taxonomy-promotion plan.

The plan is validated against pending candidates before any promotion action.
Each action is then applied through taxonomy_admin's transactional path and is
recorded in v4_taxonomy_action_log.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from lib.console import configure_utf8_stdio
from taxonomy_admin import resolve_candidates
from v4_schema import normalize_alias


def apply_plan(out: Path, plan_path: Path) -> dict:
    actions = json.loads(plan_path.read_text(encoding="utf-8"))
    if not isinstance(actions, list) or not actions:
        raise ValueError("promotion plan must be a non-empty JSON array")

    planned_aliases: set[str] = set()
    planned_ids: set[str] = set()
    with sqlite3.connect(out / "catalog.sqlite") as conn:
        for body in actions:
            if body.get("action") != "promote":
                raise ValueError("promotion plan may contain only promote actions")
            taxonomy_id = str(body.get("taxonomy_id") or "")
            parent_id = str(body.get("parent_id") or "")
            if not taxonomy_id or taxonomy_id in planned_ids:
                raise ValueError(f"duplicate or empty taxonomy id: {taxonomy_id}")
            planned_ids.add(taxonomy_id)
            if conn.execute(
                "SELECT 1 FROM v4_taxonomy_node WHERE taxonomy_id=?",
                (taxonomy_id,),
            ).fetchone():
                raise ValueError(f"{taxonomy_id}: taxonomy node already exists")
            if not conn.execute(
                """
                SELECT 1 FROM v4_taxonomy_node
                WHERE taxonomy_id=? AND status='active'
                """,
                (parent_id,),
            ).fetchone():
                raise ValueError(f"{taxonomy_id}: active parent not found")
            aliases = [
                str(body.get("canonical_ko") or ""),
                str(body.get("canonical_en") or ""),
                *(str(value) for value in body.get("aliases", [])),
            ]
            normalized = [normalize_alias(value) for value in aliases]
            if any(not value for value in normalized):
                raise ValueError(f"{taxonomy_id}: empty canonical alias")
            if len(normalized) != len(set(normalized)):
                raise ValueError(f"{taxonomy_id}: duplicate aliases in action")
            if planned_aliases.intersection(normalized):
                raise ValueError(f"{taxonomy_id}: alias reused across plan actions")
            planned_aliases.update(normalized)
            placeholders = ",".join("?" for _ in normalized)
            if conn.execute(
                f"""
                SELECT 1 FROM v4_taxonomy_alias
                WHERE normalized_alias IN ({placeholders})
                LIMIT 1
                """,
                normalized,
            ).fetchone():
                raise ValueError(f"{taxonomy_id}: alias collides with taxonomy")
            candidate_ids = body.get("candidate_ids")
            if not isinstance(candidate_ids, list) or not candidate_ids:
                raise ValueError("each promotion requires candidate_ids")
            placeholders = ",".join("?" for _ in candidate_ids)
            rows = conn.execute(
                f"""
                SELECT candidate_id,status,family
                FROM v4_taxonomy_candidate
                WHERE candidate_id IN ({placeholders})
                """,
                candidate_ids,
            ).fetchall()
            if len(rows) != len(candidate_ids):
                raise ValueError(
                    f"{body.get('taxonomy_id')}: candidate count mismatch"
                )
            if any(row[1] != "pending" for row in rows):
                raise ValueError(
                    f"{body.get('taxonomy_id')}: non-pending candidate"
                )

    results = [resolve_candidates(out, body) for body in actions]
    return {
        "plan": str(plan_path),
        "action_count": len(results),
        "resolved_candidate_count": sum(
            int(result["resolved_count"]) for result in results
        ),
        "materialized_item_count": sum(
            int(result["materialized_count"]) for result in results
        ),
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    result = apply_plan(args.out, args.plan)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
