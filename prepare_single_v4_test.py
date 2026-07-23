"""Prepare one existing doc_meta contract as a V4 representative input."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path

from plan_v4_batch import (
    build_atomic_unit_hints,
    build_input,
    build_source_inventory,
    load_taxonomy_catalog,
)


def read_paragraphs(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"^\[¶(\d+)\]\s*(.*)$", line)
        if match:
            rows.append({"para": int(match.group(1)), "text": match.group(2)})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--file-key", required=True)
    parser.add_argument("--v4-input-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--range",
        action="append",
        default=[],
        metavar="FAMILY=START-END",
        help="Reviewed family range override for older doc_meta coordinates",
    )
    parser.add_argument(
        "--focus-family",
        action="append",
        choices=("RW", "CP", "COV", "DEF", "PAY", "REM"),
        default=[],
        help="Keep only these families in source_inventory for a bounded trial",
    )
    parser.add_argument(
        "--extra-source",
        action="append",
        default=[],
        metavar="FAMILY=START-END|KIND|NAME",
        help="Add a reviewed local annex/disclosure range to source_inventory",
    )
    args = parser.parse_args()

    with sqlite3.connect(args.out / "catalog.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT f.file_key,f.path,f.ctype,f.lang,f.content_hash,f.txt_path,
                   dm.json,dm.confidence
            FROM files f JOIN doc_meta dm USING(file_key)
            WHERE f.file_key=? AND f.status='ok'
            """,
            (args.file_key,),
        ).fetchone()
        if row is None:
            raise SystemExit(f"searchable doc_meta contract not found: {args.file_key}")
        taxonomy_version = int(
            conn.execute(
                "SELECT value FROM v4_meta WHERE key='taxonomy_version'"
            ).fetchone()[0]
        )
        taxonomy_catalog = load_taxonomy_catalog(conn)

    txt_path = Path(row["txt_path"])
    if not txt_path.is_absolute():
        txt_path = args.out / txt_path
    source = {
        "file_key": row["file_key"],
        "content_hash": row["content_hash"],
        "ctype": row["ctype"],
        "lang": row["lang"],
        "path": row["path"],
        "paragraphs": read_paragraphs(txt_path),
    }
    result = json.loads(row["json"])
    result["meta_schema_version"] = 3
    result.setdefault("document_status", "contract")
    result.setdefault("confidence_reason", "existing local doc_meta")
    # Older local doc_meta rows store bounded candidates rather than the v3
    # loc_start/loc_end fields consumed by the V4 planner. Promote only direct
    # candidate coordinates so DEF/PAY are not silently skipped.
    definitions = result.get("definitions_json") or {}
    if not definitions.get("items"):
        candidates = [
            item
            for item in definitions.get("candidates") or []
            if isinstance(item, dict) and isinstance(item.get("para"), int)
        ]
        if candidates:
            anchor = min(int(item["para"]) for item in candidates)
            definitions["items"] = [
                {"loc_start": anchor, "loc_end": anchor + 1}
            ]
            result["definitions_json"] = definitions
    consideration = result.get("consideration_json") or {}
    if not isinstance(consideration.get("loc_start"), int):
        candidates = [
            item
            for item in consideration.get("candidates") or []
            if isinstance(item, dict) and isinstance(item.get("para"), int)
        ]
        if candidates:
            paras = [int(item["para"]) for item in candidates]
            consideration["loc_start"] = min(paras)
            consideration["loc_end"] = max(paras)
            result["consideration_json"] = consideration
    payload = build_input(
        source,
        result,
        taxonomy_version=taxonomy_version,
        taxonomy_catalog=taxonomy_catalog,
    )
    reviewed_ranges: dict[str, tuple[int, int]] = {}
    for raw in args.range:
        family, value = raw.split("=", 1)
        start_text, end_text = value.split("-", 1)
        reviewed_ranges[family] = (int(start_text), int(end_text))
    if reviewed_ranges:
        by_number = {row["para"]: row["text"] for row in source["paragraphs"]}
        for family, (start, end) in reviewed_ranges.items():
            section = payload["family_sections"][family]
            paragraphs = [
                {"para": number, "text": by_number[number]}
                for number in sorted(by_number)
                if start <= number <= end
            ]
            section.update(
                {
                    "v3_present": True,
                    "loc_start": start,
                    "loc_end": end,
                    "v3_loc_start": start,
                    "v3_loc_end": end,
                    "ranges": [[start, end]],
                    "range_expanded": True,
                    "paragraphs": paragraphs,
                    "atomic_unit_hints": build_atomic_unit_hints(paragraphs),
                }
            )
        payload["source_inventory"] = build_source_inventory(
            source,
            payload["family_sections"],
        )
    if args.focus_family:
        focus = set(args.focus_family)
        payload["source_inventory"] = [
            row
            for row in payload["source_inventory"]
            if row["family"] in focus
        ]
    if args.extra_source:
        by_number = {row["para"]: row["text"] for row in source["paragraphs"]}
        for raw in args.extra_source:
            family, spec = raw.split("=", 1)
            range_text, kind, name = spec.split("|", 2)
            start_text, end_text = range_text.split("-", 1)
            start, end = int(start_text), int(end_text)
            if family not in payload["family_sections"]:
                raise SystemExit(f"unknown source family: {family}")
            if kind not in ("schedule", "disclosure_schedule", "annex", "exhibit"):
                raise SystemExit(f"unsupported source kind: {kind}")
            rows = [
                {"para": number, "text": by_number[number]}
                for number in range(start, end + 1)
                if number in by_number
            ]
            if not rows:
                raise SystemExit(f"extra source range has no paragraphs: {raw}")
            source_id = hashlib.sha1(
                f"{family}|{kind}|{name}|{start}|{end}".encode("utf-8")
            ).hexdigest()[:16]
            payload["source_inventory"].append(
                {
                    "source_id": source_id,
                    "family": family,
                    "source_kind": kind,
                    "source_name": name,
                    "source_aliases": [name],
                    "source_ref": f"¶{start}-¶{end}",
                    "storage_file_key": source["file_key"],
                    "status_hint": "available",
                    "reference_paras": [],
                    "paragraphs": rows,
                }
            )
        payload["source_inventory"] = sorted(
            payload["source_inventory"],
            key=lambda row: (
                row["family"],
                row["source_kind"],
                row["source_name"],
                row["source_id"],
            ),
        )
    args.v4_input_dir.mkdir(parents=True, exist_ok=True)
    input_path = args.v4_input_dir / f"{args.file_key}.json"
    input_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    manifest = {
        "meta_schema_version": 4,
        "taxonomy_version": taxonomy_version,
        "schema_revision": "1R2",
        "batch": "V4-2 single Korean representative taxonomy refinement test",
        "count": 1,
        "items": [
            {
                "file_key": row["file_key"],
                "ctype": row["ctype"],
                "lang": row["lang"],
                "path": row["path"],
                "v3_confidence": row["confidence"],
                "family_ranges": {
                    family: (
                        [section["loc_start"], section["loc_end"]]
                        if section["v3_present"]
                        else None
                    )
                    for family, section in payload["family_sections"].items()
                },
            }
        ],
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "file_key": args.file_key,
                "taxonomy_version": taxonomy_version,
                "input": str(input_path),
                "manifest": str(args.manifest),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
