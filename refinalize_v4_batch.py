"""Re-run the deterministic final review for an existing V4 batch.

This is used when review logic improves after a batch was selected.  It keeps
the original cohort and pre-review artifacts, rewrites only final input/result
artifacts, and updates aggregate manifest counts.  No external API is used.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from finalize_v4_remaining_nine import finalize_result, prepare_reviewed_source
from plan_v4_batch import build_input, load_taxonomy_catalog
from propose_v4_remaining_nine import build_result, load_nodes
from run_v4_pilot_60 import (
    load_v3_like_payload,
    repair_family_sections,
    write_json,
)
from v4_schema import (
    V4_SCHEMA_REVISION,
    initialize_v4_schema,
    taxonomy_ids,
    validate_v4_result,
)


def refinalize_batch(
    out: Path,
    batch_id: str,
    *,
    rebuild_input: bool = False,
    rebuild_unscoped_only: bool = False,
) -> dict:
    manifest_path = out / f"{batch_id}_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_dir = out / f"enrich_inputs_{batch_id}_raw"
    pre_dir = out / f"enrich_results_{batch_id}_pre"
    input_dir = out / f"enrich_inputs_{batch_id}_final"
    result_dir = out / f"enrich_results_{batch_id}_final"
    input_dir.mkdir(parents=True, exist_ok=True)
    result_dir.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(out / "catalog.sqlite") as conn:
        initialize_v4_schema(conn)
        known = taxonomy_ids(conn)
        taxonomy_version = int(
            conn.execute(
                "SELECT value FROM v4_meta WHERE key='taxonomy_version'"
            ).fetchone()[0]
        )
        conn.commit()

    if rebuild_input or rebuild_unscoped_only:
        with sqlite3.connect(out / "catalog.sqlite") as conn:
            conn.row_factory = sqlite3.Row
            catalog = load_taxonomy_catalog(conn)
            nodes, _ = load_nodes(conn)
            for row in manifest["items"]:
                file_key = str(row["file_key"])
                if rebuild_unscoped_only:
                    existing_raw = json.loads(
                        (raw_dir / f"{file_key}.json").read_text(
                            encoding="utf-8"
                        )
                    )
                    if any(
                        section.get("paragraphs")
                        for section in (
                            existing_raw.get("family_sections") or {}
                        ).values()
                        if isinstance(section, dict)
                    ):
                        continue
                file_row = conn.execute(
                    """
                    SELECT file_key,path,ctype,lang,content_hash,txt_path
                    FROM files
                    WHERE file_key=? AND status='ok'
                    """,
                    (file_key,),
                ).fetchone()
                if file_row is None:
                    raise RuntimeError(f"{file_key}: current source file unavailable")
                source, v3_result = load_v3_like_payload(
                    conn, out, dict(file_row)
                )
                raw = build_input(
                    source,
                    v3_result,
                    taxonomy_version=taxonomy_version,
                    taxonomy_catalog=catalog,
                )
                raw = repair_family_sections(raw, source)
                pre = build_result(raw, nodes)
                write_json(raw_dir / f"{file_key}.json", raw)
                write_json(pre_dir / f"{file_key}.json", pre)

    totals = {
        "items": 0,
        "candidates": 0,
        "candidate_docs": 0,
        "source_items": 0,
        "source_candidates": 0,
        "partial_sources": 0,
    }
    updated_rows = []
    for row in manifest["items"]:
        file_key = str(row["file_key"])
        source = json.loads((raw_dir / f"{file_key}.json").read_text(encoding="utf-8"))
        pre = json.loads((pre_dir / f"{file_key}.json").read_text(encoding="utf-8"))
        pre["taxonomy_version"] = taxonomy_version
        final, unresolved = finalize_result(pre, known, source=source)
        final["taxonomy_version"] = taxonomy_version
        reviewed_source = prepare_reviewed_source(source, final)
        validate_v4_result(final, file_key=file_key, known_taxonomy=known)
        write_json(input_dir / f"{file_key}.json", reviewed_source)
        write_json(result_dir / f"{file_key}.json", final)

        item_count = len(final["items"])
        candidate_count = len(unresolved)
        source_items = sum(
            item.get("source_kind") != "body" for item in final["items"]
        )
        source_candidates = sum(
            candidate.get("source_kind") not in (None, "body")
            for candidate in unresolved
            if isinstance(candidate, dict)
        )
        partial_sources = sum(
            source_row["status"] == "partial"
            for source_row in final["source_coverage"]
        )
        totals["items"] += item_count
        totals["candidates"] += candidate_count
        totals["candidate_docs"] += int(candidate_count > 0)
        totals["source_items"] += source_items
        totals["source_candidates"] += source_candidates
        totals["partial_sources"] += partial_sources
        updated_rows.append(
            {
                **row,
                "item_count": item_count,
                "candidate_count": candidate_count,
                "source_item_count": source_items,
                "source_candidate_count": source_candidates,
                "partial_source_count": partial_sources,
            }
        )

    manifest.update(
        {
            "taxonomy_version": taxonomy_version,
            "schema_revision": V4_SCHEMA_REVISION,
            "item_count": totals["items"],
            "candidate_count": totals["candidates"],
            "candidate_document_count": totals["candidate_docs"],
            "source_item_count": totals["source_items"],
            "source_candidate_count": totals["source_candidates"],
            "partial_source_count": totals["partial_sources"],
            "annex_review_mode": "physical-paragraph-complete-v1",
            "body_range_rebuilt": bool(
                rebuild_input
                or rebuild_unscoped_only
                or manifest.get("body_range_rebuilt")
            ),
            "unscoped_body_rebuilt": bool(
                rebuild_unscoped_only
                or manifest.get("unscoped_body_rebuilt")
            ),
            "refinalized_at": datetime.now(timezone.utc).isoformat(),
            "items": updated_rows,
        }
    )
    write_json(manifest_path, manifest)
    return {"batch": batch_id, "count": len(updated_rows), **totals}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument(
        "--rebuild-input",
        action="store_true",
        help="Rebuild family ranges and proposal artifacts from current txt.",
    )
    parser.add_argument(
        "--rebuild-unscoped-only",
        action="store_true",
        help=(
            "Rebuild only documents whose current input has no recognized "
            "family body range, then refinalize the batch."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(
        json.dumps(
            refinalize_batch(
                args.out,
                args.batch_id,
                rebuild_input=args.rebuild_input,
                rebuild_unscoped_only=args.rebuild_unscoped_only,
            ),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
