"""Audit V4 atomic clause item result files before database storage."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Dict, List, Mapping, Optional

from audit_t3_v3 import _compact, _normalized_number_is_supported
from finalize_v4_remaining_nine import source_needs_candidate
from lib.console import configure_utf8_stdio
from v4_schema import (
    V4SchemaError,
    normalize_alias,
    taxonomy_aliases,
    taxonomy_ids,
    taxonomy_parents,
    validate_v4_result,
)


def paragraph_map(payload: Mapping[str, object]) -> Dict[int, str]:
    result: Dict[int, str] = {}
    for row in payload.get("paragraphs") or []:
        if isinstance(row, dict) and isinstance(row.get("para"), int):
            result[int(row["para"])] = str(row.get("text") or "")
    # V4-2 inputs keep evidence ranges under family_sections to avoid
    # accidentally passing the full document. Preserve support for the
    # legacy top-level paragraphs shape as well.
    for section in (payload.get("family_sections") or {}).values():
        if not isinstance(section, dict):
            continue
        for row in section.get("paragraphs") or []:
            if isinstance(row, dict) and isinstance(row.get("para"), int):
                result[int(row["para"])] = str(row.get("text") or "")
    for row in payload.get("unscoped_body_paragraphs") or []:
        if isinstance(row, dict) and isinstance(row.get("para"), int):
            result[int(row["para"])] = str(row.get("text") or "")
    for source in payload.get("source_inventory") or []:
        if not isinstance(source, dict):
            continue
        for row in source.get("paragraphs") or []:
            if isinstance(row, dict) and isinstance(row.get("para"), int):
                result[int(row["para"])] = str(row.get("text") or "")
    return result


def source_paragraph_maps(payload: Mapping[str, object]) -> Dict[str, Dict[int, str]]:
    result: Dict[str, Dict[int, str]] = {}
    for source in payload.get("source_inventory") or []:
        if not isinstance(source, dict) or not source.get("source_id"):
            continue
        rows: Dict[int, str] = {}
        for row in source.get("paragraphs") or []:
            if isinstance(row, dict) and isinstance(row.get("para"), int):
                rows[int(row["para"])] = str(row.get("text") or "")
        result[str(source["source_id"])] = rows
    return result


def evidence_issues(
    data: Mapping[str, object],
    paragraphs: Mapping[int, str],
    source_maps: Optional[Mapping[str, Mapping[int, str]]] = None,
) -> List[dict]:
    issues: List[dict] = []
    for index, item in enumerate(data.get("items") or []):
        item_paragraphs = paragraphs
        if item.get("source_kind") != "body" and item.get("source_id"):
            item_paragraphs = (source_maps or {}).get(str(item["source_id"]), {})
        start, end = item["loc_start"], item["loc_end"]
        missing = [
            number for number in range(start, end + 1) if number not in item_paragraphs
        ]
        if missing:
            issues.append({"item": index, "code": "location_missing", "detail": missing[:10]})
            continue
        source = " ".join(
            item_paragraphs[number] for number in range(start, end + 1)
        )
        verbatim = item["verbatim"]
        if _compact(verbatim) not in _compact(source):
            issues.append({"item": index, "code": "verbatim_not_in_range", "detail": verbatim[:120]})
        for field, value in item["normalized"].items():
            if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            if not _normalized_number_is_supported(field, value, f"{verbatim} {source}"):
                issues.append({"item": index, "code": "normalized_number_not_in_evidence", "detail": f"{field}={value}"})
    return issues


def candidate_issues(
    data: Mapping[str, object],
    paragraphs: Mapping[int, str],
    known: Mapping[str, str],
    aliases: Mapping[str, str],
) -> List[dict]:
    issues: List[dict] = []
    candidates = data.get("taxonomy_candidates") or []
    if not isinstance(candidates, list):
        return [{"code": "taxonomy_candidates_not_array"}]
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            issues.append({"candidate": index, "code": "candidate_not_object"})
            continue
        required = ("proposed_ko", "family", "recommended_parent_id", "distinction_reason", "loc_start", "loc_end", "verbatim", "nearest_taxonomy_id")
        missing_fields = [field for field in required if field not in candidate]
        if missing_fields:
            issues.append({"candidate": index, "code": "candidate_missing_fields", "detail": missing_fields})
            continue
        parent = candidate["recommended_parent_id"]
        nearest = candidate["nearest_taxonomy_id"]
        if parent not in known or nearest not in known:
            issues.append({"candidate": index, "code": "candidate_unknown_taxonomy"})
            continue
        if known[parent] != candidate["family"] or known[nearest] != candidate["family"]:
            issues.append({"candidate": index, "code": "candidate_family_mismatch"})
        proposed_names = [
            str(candidate.get("proposed_ko") or ""),
            str(candidate.get("proposed_en") or ""),
        ]
        duplicate = next(
            (
                aliases[normalize_alias(name)]
                for name in proposed_names
                if name and normalize_alias(name) in aliases
            ),
            None,
        )
        if duplicate:
            issues.append(
                {
                    "candidate": index,
                    "code": "candidate_duplicates_existing_alias",
                    "detail": duplicate,
                }
            )
        start, end = candidate["loc_start"], candidate["loc_end"]
        if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start:
            issues.append({"candidate": index, "code": "candidate_location_invalid"})
            continue
        if any(number not in paragraphs for number in range(start, end + 1)):
            issues.append({"candidate": index, "code": "candidate_location_missing"})
            continue
        source = " ".join(paragraphs[number] for number in range(start, end + 1))
        if _compact(str(candidate["verbatim"])) not in _compact(source):
            issues.append({"candidate": index, "code": "candidate_verbatim_not_in_range"})
    return issues


def source_coverage_issues(
    data: Mapping[str, object],
    source: Mapping[str, object],
) -> List[dict]:
    issues: List[dict] = []
    inventory = source.get("source_inventory") or []
    if not isinstance(inventory, list):
        return [{"code": "source_inventory_not_array"}]
    result_rows = data.get("source_coverage") or []
    result_map = {
        (str(row.get("family")), str(row.get("source_id"))): row
        for row in result_rows
        if isinstance(row, dict)
    }
    inventory_keys = set()
    for row in inventory:
        if not isinstance(row, dict):
            issues.append({"code": "source_inventory_item_invalid"})
            continue
        key = (str(row.get("family")), str(row.get("source_id")))
        inventory_keys.add(key)
        result = result_map.get(key)
        if result is None:
            issues.append(
                {
                    "code": "source_coverage_missing",
                    "detail": {"family": key[0], "source_id": key[1]},
                }
            )
            continue
        hint = row.get("status_hint")
        status = result.get("status")
        if hint == "available" and status != "complete":
            issues.append(
                {
                    "code": "available_source_not_complete",
                    "detail": {"source_id": key[1], "status": status},
                }
            )
        if hint == "missing" and status not in ("missing", "not_evaluated"):
            issues.append(
                {
                    "code": "missing_source_marked_evaluated",
                    "detail": {"source_id": key[1], "status": status},
                }
            )
    for key in sorted(set(result_map) - inventory_keys):
        issues.append(
            {
                "code": "source_coverage_not_in_inventory",
                "detail": {"family": key[0], "source_id": key[1]},
            }
        )
    return issues


def document_coverage_issues(data: Mapping[str, object]) -> List[dict]:
    """Reject a nominal pass when no body family was actually evaluated."""

    coverage = data.get("coverage") or {}
    if not isinstance(coverage, dict) or not coverage:
        return [{"code": "document_coverage_missing"}]
    statuses = [
        str(row.get("body_status") or "not_evaluated")
        for row in coverage.values()
        if isinstance(row, dict)
    ]
    if statuses and all(status == "not_evaluated" for status in statuses):
        return [
            {
                "code": "document_body_not_evaluated",
                "detail": "all clause families have body_status=not_evaluated",
            }
        ]
    return []


def atomicity_issues(
    data: Mapping[str, object],
    source: Mapping[str, object],
    parents: Mapping[str, Optional[str]],
) -> List[dict]:
    issues: List[dict] = []
    children = {parent for parent in parents.values() if parent}
    candidates = data.get("taxonomy_candidates") or []
    candidate_parents = {
        str(row.get("recommended_parent_id"))
        for row in candidates
        if isinstance(row, dict)
    }
    items = data.get("items") or []
    body_evidence = {
        (int(row.get("loc_start") or 0), str(row.get("verbatim") or "").strip())
        for row in [*items, *(data.get("taxonomy_candidates") or [])]
        if isinstance(row, dict)
        and row.get("source_kind", "body") == "body"
    }
    for index, item in enumerate(items):
        taxonomy_id = str(item.get("taxonomy_id") or "")
        if taxonomy_id in children and taxonomy_id not in candidate_parents:
            issues.append(
                {
                    "item": index,
                    "code": "non_leaf_taxonomy_without_candidate",
                    "detail": taxonomy_id,
                }
            )

    sections = source.get("family_sections") or {}
    for family, section in sections.items():
        if not isinstance(section, dict):
            continue
        coverage = (data.get("coverage") or {}).get(family) or {}
        if coverage.get("body_status") != "complete":
            continue
        family_items = [
            item
            for item in items
            if item.get("family") == family and item.get("source_kind") == "body"
        ]
        for hint in section.get("atomic_unit_hints") or []:
            if not isinstance(hint, dict):
                continue
            start, end = hint.get("loc_start"), hint.get("loc_end")
            covered = any(
                int(item["loc_start"]) <= int(end)
                and int(item["loc_end"]) >= int(start)
                for item in family_items
            )
            if not covered:
                issues.append(
                    {
                        "code": "atomic_unit_uncovered",
                        "detail": {
                            "family": family,
                            "unit_id": hint.get("unit_id"),
                            "heading": hint.get("heading"),
                            "loc_start": start,
                            "loc_end": end,
                        },
                    }
                )
        for paragraph in section.get("paragraphs") or []:
            if not isinstance(paragraph, dict):
                continue
            para = int(paragraph.get("para") or 0)
            text = str(paragraph.get("text") or "").strip()
            if (
                source_needs_candidate(text)
                and (para, text) not in body_evidence
            ):
                issues.append(
                    {
                        "code": "body_paragraph_unrepresented",
                        "detail": {
                            "family": family,
                            "loc_start": para,
                            "text": text[:160],
                        },
                    }
                )
    for paragraph in source.get("unscoped_body_paragraphs") or []:
        if not isinstance(paragraph, dict):
            continue
        para = int(paragraph.get("para") or 0)
        text = str(paragraph.get("text") or "").strip()
        if (
            source_needs_candidate(text)
            and (para, text) not in body_evidence
        ):
            issues.append(
                {
                    "code": "body_paragraph_unrepresented",
                    "detail": {
                        "family": "UNSCOPED",
                        "loc_start": para,
                        "text": text[:160],
                    },
                }
            )
    return issues


def audit_v4(manifest_path: Path, *, out: Path, input_dir: Path, result_dir: Path, report_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("items"), list):
        raise ValueError("manifest must contain an items array")
    with sqlite3.connect(out / "catalog.sqlite") as conn:
        known = taxonomy_ids(conn)
        parents = taxonomy_parents(conn)
        aliases = taxonomy_aliases(conn)
    if not known:
        raise ValueError("v4 taxonomy is not initialized")

    rows = []
    counts = Counter()
    for manifest_item in manifest["items"]:
        key = str(manifest_item["file_key"])
        input_path = input_dir / f"{key}.json"
        result_path = result_dir / f"{key}.json"
        if not input_path.exists():
            rows.append({"file_key": key, "status": "error", "issues": [{"code": "input_missing"}]})
            counts["error"] += 1
            continue
        if not result_path.exists():
            rows.append({"file_key": key, "status": "pending", "issues": []})
            counts["pending"] += 1
            continue
        try:
            source = json.loads(input_path.read_text(encoding="utf-8"))
            data = json.loads(result_path.read_text(encoding="utf-8"))
            validate_v4_result(data, file_key=key, known_taxonomy=known)
            paragraphs = paragraph_map(source)
            source_maps = source_paragraph_maps(source)
            issues = (
                evidence_issues(data, paragraphs, source_maps)
                + candidate_issues(data, paragraphs, known, aliases)
                + source_coverage_issues(data, source)
                + document_coverage_issues(data)
                + atomicity_issues(data, source, parents)
            )
            needs_review = bool(issues) or any(item.get("confidence") == "low" or item.get("review_status") == "needs_review" for item in data["items"]) or bool(data.get("taxonomy_candidates"))
            status = "review" if needs_review else "pass"
            rows.append({"file_key": key, "status": status, "item_count": len(data["items"]), "issues": issues})
            counts[status] += 1
        except (OSError, ValueError, V4SchemaError, json.JSONDecodeError) as exc:
            rows.append({"file_key": key, "status": "error", "issues": [{"code": "invalid_result", "detail": str(exc)}]})
            counts["error"] += 1
    payload = {
        "meta_schema_version": 4,
        "taxonomy_count": len(known),
        "summary": {"total": len(rows), "pass": counts["pass"], "review": counts["review"], "pending": counts["pending"], "error": counts["error"]},
        "items": rows,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Audit V4 clause item result files")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = audit_v4(args.manifest, out=args.out, input_dir=args.input_dir, result_dir=args.result_dir, report_path=args.report)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["summary"]["error"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
