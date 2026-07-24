"""Deterministic V4-6 expansion over previously unevaluated core contracts."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

from finalize_v4_remaining_nine import (
    finalize_result,
    prepare_reviewed_source,
)
from plan_v4_batch import build_input, load_taxonomy_catalog
from propose_v4_remaining_nine import build_result
from propose_v4_remaining_nine import load_nodes
from run_v4_pilot_60 import (
    allocate_quotas,
    load_v3_like_payload,
    repair_family_sections,
    write_json,
)
from v4_schema import initialize_v4_schema, taxonomy_ids, validate_v4_result


TYPE_PRIORITY = ("SPA", "SSA", "SHA", "ATA/BTA")


def select_expansion(
    conn: sqlite3.Connection,
    *,
    target: int,
    type_priority: tuple[str, ...] = TYPE_PRIORITY,
) -> tuple[list[dict], dict]:
    conn.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in type_priority)
    rows = [
        dict(row)
        for row in conn.execute(
            f"""
            SELECT f.file_key,f.path,f.ctype,f.lang,f.content_hash,f.txt_path,
                   f.dup_group,d.txt_hash
            FROM files f
            JOIN doc_meta d USING(file_key)
            LEFT JOIN (
              SELECT DISTINCT file_key FROM v4_document_coverage
            ) v USING(file_key)
            WHERE f.status='ok'
              AND f.ctype IN ({placeholders})
              AND d.txt_hash=f.content_hash
              AND f.txt_path IS NOT NULL
              AND v.file_key IS NULL
            ORDER BY f.ctype,f.lang,f.file_key
            """,
            type_priority,
        )
    ]
    unique = []
    seen_groups: set[str] = set()
    for row in rows:
        group = str(row.get("dup_group") or row["file_key"])
        if group in seen_groups:
            continue
        seen_groups.add(group)
        unique.append(row)
    if target > len(unique):
        raise ValueError(f"target {target} exceeds eligible unique population {len(unique)}")

    by_type: dict[str, list[dict]] = defaultdict(list)
    for row in unique:
        by_type[str(row["ctype"])].append(row)
    selected: list[dict] = []
    per_type: dict[str, int] = {}
    per_stratum: dict[str, int] = {}
    remaining = target
    for ctype in type_priority:
        population = by_type.get(ctype, [])
        if not population or remaining <= 0:
            continue
        take = min(remaining, len(population))
        strata: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for row in population:
            strata[(ctype, str(row["lang"]))].append(row)
        quotas = allocate_quotas(
            {key: len(value) for key, value in strata.items()},
            target=take,
        )
        chosen = [
            row
            for key in sorted(strata)
            for row in strata[key][: quotas[key]]
        ]
        selected.extend(chosen)
        per_type[ctype] = len(chosen)
        per_stratum.update(
            {f"{key[0]}|{key[1]}": quotas[key] for key in sorted(quotas)}
        )
        remaining -= len(chosen)
    return selected, {
        "eligible_unique": len(unique),
        "type_priority": list(type_priority),
        "selected_by_type": per_type,
        "selected_by_type_lang": per_stratum,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=300)
    parser.add_argument("--batch-id", default="v4_expansion_01_spa300")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 1 <= args.batch_size <= 300:
        raise SystemExit("--batch-size must be between 1 and 300")
    base = args.out
    raw_dir = base / f"enrich_inputs_{args.batch_id}_raw"
    pre_dir = base / f"enrich_results_{args.batch_id}_pre"
    input_dir = base / f"enrich_inputs_{args.batch_id}_final"
    result_dir = base / f"enrich_results_{args.batch_id}_final"
    manifest_path = base / f"{args.batch_id}_manifest.json"
    for directory in (raw_dir, pre_dir, input_dir, result_dir):
        directory.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(base / "catalog.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        initialize_v4_schema(conn)
        version = int(
            conn.execute(
                "SELECT value FROM v4_meta WHERE key='taxonomy_version'"
            ).fetchone()[0]
        )
        catalog = load_taxonomy_catalog(conn)
        nodes, _ = load_nodes(conn)
        known = taxonomy_ids(conn)
        selected, selection = select_expansion(conn, target=args.batch_size)
        conn.commit()
        rows = []
        totals = {"items": 0, "pre_candidates": 0, "candidates": 0, "candidate_docs": 0}
        for row in selected:
            source, v3_result = load_v3_like_payload(conn, base, row)
            raw = build_input(
                source,
                v3_result,
                taxonomy_version=version,
                taxonomy_catalog=catalog,
            )
            raw = repair_family_sections(raw, source)
            write_json(raw_dir / f"{row['file_key']}.json", raw)
            pre = build_result(raw, nodes)
            write_json(pre_dir / f"{row['file_key']}.json", pre)
            final, unresolved = finalize_result(pre, known, source=raw)
            reviewed_source = prepare_reviewed_source(raw, final)
            write_json(input_dir / f"{row['file_key']}.json", reviewed_source)
            write_json(result_dir / f"{row['file_key']}.json", final)
            if not unresolved:
                validate_v4_result(
                    final, file_key=str(row["file_key"]), known_taxonomy=known
                )
            item_count = len(final["items"])
            pre_count = len(pre["taxonomy_candidates"])
            candidate_count = len(unresolved)
            totals["items"] += item_count
            totals["pre_candidates"] += pre_count
            totals["candidates"] += candidate_count
            totals["candidate_docs"] += int(candidate_count > 0)
            rows.append(
                {
                    "file_key": row["file_key"],
                    "ctype": row["ctype"],
                    "lang": row["lang"],
                    "path": row["path"],
                    "item_count": item_count,
                    "pre_candidate_count": pre_count,
                    "candidate_count": candidate_count,
                    "input_path": str(input_dir / f"{row['file_key']}.json"),
                    "result_path": str(result_dir / f"{row['file_key']}.json"),
                }
            )
    manifest = {
        "meta_schema_version": 4,
        "taxonomy_version": version,
        "schema_revision": "1R2",
        "batch": args.batch_id,
        "count": len(rows),
        "selection": selection,
        "item_count": totals["items"],
        "pre_candidate_count": totals["pre_candidates"],
        "candidate_count": totals["candidates"],
        "candidate_document_count": totals["candidate_docs"],
        "items": rows,
    }
    write_json(manifest_path, manifest)
    print(
        json.dumps(
            {**totals, "count": len(rows), "selection": selection,
             "manifest": str(manifest_path)},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
