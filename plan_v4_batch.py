"""Prepare the V4-2 representative batch from approved V3 clause ranges."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path


REPRESENTATIVE_KEYS = (
    "0ddde0e62bd84e41",  # SPA low draft
    "a51842fc51010f69",  # SPA high executed
    "3c86175c4821fa83",  # SPA high executed, Korean
    "b324cb8bdf00015a",  # SSA high
    "660fc9d64566ba0e",  # SSA med draft
    "a5da55951cfdabfb",  # SHA low draft, referenced agreements
    "0df5e9d7e1e7c893",  # SHA high executed
    "5853fe0540a72d6c",  # SHA med execution-form
    "b6fd6ff14e51e05f",  # ATA/BTA high executed
    "973d43e89040fb57",  # ATA/BTA low form
)
FAMILY_TAG = {"RW": "진술보장", "CP": "선행조건", "COV": "확약"}
SUPPLEMENTAL_FAMILY_TAGS = {
    "PAY": ("대금조정", "earn-out", "에스크로"),
    "REM": ("손해배상", "조세배상", "해제"),
}
ALL_FAMILIES = ("RW", "CP", "COV", "DEF", "PAY", "REM")
SOURCE_REF_RE = re.compile(
    r"((?i:Seller\s+Disclosure\s+Schedule|Buyer\s+Disclosure\s+Schedule)|"
    r"(?i:Schedule|Annex|Exhibit)\s+(?:[0-9]+(?:\.[0-9]+)*|[A-Z](?:-[0-9]+)?)|"
    r"매도인\s*공개사항|매수인\s*공개사항|"
    r"별지\s*(?:제\s*)?[0-9]+(?:\s*[-의]\s*[0-9]+)?|"
    r"별첨\s*(?:제\s*)?[0-9]+|부속서\s*(?:제\s*)?[0-9]+|첨부\s*(?:제\s*)?[0-9]+)",
)
SOURCE_HEADER_RE = re.compile(
    r"^\s*((?i:Seller\s+Disclosure\s+Schedule|Buyer\s+Disclosure\s+Schedule)|"
    r"(?i:Schedule|Annex|Exhibit)\s+(?:[0-9]+(?:\.[0-9]+)*|[A-Z](?:-[0-9]+)?)|"
    r"매도인\s*공개사항|매수인\s*공개사항|별지|별첨|부속서|첨부)",
)
GENERIC_HEADINGS = {
    "매도인의진술및보장",
    "대상회사에관한진술및보장",
    "매수인의진술및보장",
    "선행조건",
    "확약",
    "representationsandwarrantiesofsellers",
    "representationsandwarrantiesofbuyer",
    "conditionsprecedent",
    "covenants",
}
MAJOR_HEADING_RE = re.compile(
    r"^\s*(?:ARTICLE\s+[IVXLC0-9]+|제\s*[0-9일이삼사오육칠팔구십]+\s*조|Á¦\s*[0-9]+)\s*$",
    re.IGNORECASE,
)


def _compact(value: str) -> str:
    return re.sub(r"[\s·:：()\[\].,_\-]+", "", value).casefold()


def _source_kind(name: str) -> str:
    compact = _compact(name)
    if "disclosureschedule" in compact or "공개사항" in compact:
        return "disclosure_schedule"
    if compact.startswith("schedule"):
        return "schedule"
    if compact.startswith("exhibit"):
        return "exhibit"
    return "annex"


def _source_headers(paragraphs: list[dict]) -> list[dict]:
    headers = []
    for row in paragraphs:
        text = str(row.get("text") or "").strip()
        compact = _compact(text)
        english_header_count = len(
            re.findall(r"(?i)\b(?:schedule|annex|exhibit)\b", text)
        )
        looks_like_reference_sentence = any(
            marker in compact
            for marker in (
                "따라",
                "기재",
                "첨부",
                "참조",
                "의하면",
                "포함",
                "assetforth",
                "describedin",
                "pursuantto",
            )
        )
        if (
            len(text) <= 240
            and SOURCE_HEADER_RE.search(text)
            and not looks_like_reference_sentence
            and english_header_count <= 1
        ):
            headers.append({"para": int(row["para"]), "text": text})
    return headers


def _matching_header(reference: str, headers: list[dict]) -> dict | None:
    needle = _compact(reference)
    exact = [header for header in headers if needle and needle in _compact(header["text"])]
    if exact:
        return exact[0]
    # Disclosure schedules are often titled more fully than the body reference.
    if "공개사항" in needle or "disclosureschedule" in needle:
        broad = [
            header
            for header in headers
            if "공개사항" in _compact(header["text"])
            or "disclosureschedule" in _compact(header["text"])
        ]
        if broad:
            return broad[0]
    return None


def build_source_inventory(source: dict, family_sections: dict) -> list[dict]:
    paragraphs = source["paragraphs"]
    paragraph_by_number = {int(row["para"]): row["text"] for row in paragraphs}
    headers = _source_headers(paragraphs)
    header_numbers = sorted({int(row["para"]) for row in headers})
    found: dict[tuple[str, str], dict] = {}

    for family, section in family_sections.items():
        for row in section["paragraphs"]:
            for match in SOURCE_REF_RE.finditer(str(row["text"])):
                name = " ".join(match.group(0).split()).rstrip(").,;:")
                kind = _source_kind(name)
                header = _matching_header(name, headers)
                if header is None and kind == "disclosure_schedule":
                    section_match = re.search(
                        r"(?i)\bSection\s+([0-9]+(?:\.[0-9]+)*)",
                        str(row["text"]),
                    )
                    if section_match:
                        header = _matching_header(
                            f"Schedule {section_match.group(1)}",
                            headers,
                        )
                key = (
                    family,
                    f"header:{header['para']}" if header is not None else _compact(name),
                )
                if key in found:
                    found[key]["reference_paras"].append(int(row["para"]))
                    if name not in found[key]["source_aliases"]:
                        found[key]["source_aliases"].append(name)
                    continue
                source_paragraphs: list[dict] = []
                status_hint = "missing"
                source_ref = f"¶{row['para']}"
                if header is not None:
                    start = int(header["para"])
                    following = [number for number in header_numbers if number > start]
                    end = (following[0] - 1) if following else max(paragraph_by_number)
                    end = min(end, start + 250)
                    source_paragraphs = [
                        {"para": number, "text": paragraph_by_number[number]}
                        for number in range(start, end + 1)
                        if number in paragraph_by_number
                    ]
                    status_hint = "available"
                    source_ref = f"¶{start}-¶{end}"
                source_id = hashlib.sha1(
                    f"{family}|{kind}|{_compact(name)}".encode("utf-8")
                ).hexdigest()[:16]
                found[key] = {
                    "source_id": source_id,
                    "family": family,
                    "source_kind": kind,
                    "source_name": name,
                    "source_aliases": [name],
                    "source_ref": source_ref,
                    "storage_file_key": source["file_key"] if header is not None else None,
                    "status_hint": status_hint,
                    "reference_paras": [int(row["para"])],
                    "paragraphs": source_paragraphs,
                }
    rows = list(found.values())
    for family in FAMILY_TAG:
        available = [
            row
            for row in rows
            if row["family"] == family
            and row["source_kind"] == "disclosure_schedule"
            and row["status_hint"] == "available"
        ]
        missing = [
            row
            for row in rows
            if row["family"] == family
            and row["source_kind"] == "disclosure_schedule"
            and row["status_hint"] == "missing"
        ]
        if len(available) == 1:
            target = available[0]
            for row in missing:
                target["reference_paras"].extend(row["reference_paras"])
                for alias in row["source_aliases"]:
                    if alias not in target["source_aliases"]:
                        target["source_aliases"].append(alias)
                rows.remove(row)
    return sorted(
        rows,
        key=lambda row: (row["family"], row["source_kind"], row["source_name"], row["source_id"]),
    )


def build_atomic_unit_hints(paragraphs: list[dict]) -> list[dict]:
    headings: list[tuple[int, str]] = []
    for row in paragraphs:
        text = " ".join(str(row.get("text") or "").split()).strip()
        compact = _compact(text)
        if not text or compact in GENERIC_HEADINGS or len(text) > 140:
            continue
        if (
            "sellerdraft" in compact
            or "purchasercomments" in compact
            or "noteto" in compact
            or re.match(r"^\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.", text)
        ):
            continue
        looks_numbered = bool(
            re.match(r"^\(?[0-9A-Za-z가-힣]+\)?[.)]\s*\S{2,}", text)
        )
        looks_titled = (
            len(text) >= 3
            and text.endswith(".")
            and not re.fullmatch(r"\(?(?:[0-9]+|[A-Za-z가-힣])\)?[.]?", text)
        )
        if looks_numbered or looks_titled:
            headings.append((int(row["para"]), text))
    hints = []
    final_para = int(paragraphs[-1]["para"]) if paragraphs else 0
    for index, (start, heading) in enumerate(headings):
        end = headings[index + 1][0] - 1 if index + 1 < len(headings) else final_para
        hints.append(
            {
                "unit_id": f"u-{start}",
                "loc_start": start,
                "loc_end": max(start, end),
                "heading": heading,
            }
        )
    return hints


def expand_title_only_range(
    paragraph_by_number: dict[int, str],
    start: int,
    end: int,
    *,
    max_paragraphs: int = 200,
) -> tuple[int, int]:
    """Expand a V3 heading-only range to the next major article boundary."""

    if end > start:
        return start, end
    numbers = sorted(number for number in paragraph_by_number if number > end)
    expanded_end = end
    for number in numbers:
        if number > start + max_paragraphs:
            break
        text = " ".join(str(paragraph_by_number[number]).split())
        if number > end and MAJOR_HEADING_RE.fullmatch(text):
            break
        expanded_end = number
    return start, expanded_end


def expand_family_range(
    paragraph_by_number: dict[int, str],
    result: dict,
    family: str,
    start: int,
    end: int,
) -> tuple[int, int]:
    """Use V3 as a start coordinate and include the whole family article."""

    if family == "CP":
        for number in sorted(number for number in paragraph_by_number if number > end):
            compact = _compact(str(paragraph_by_number[number]))
            if number > start + 300:
                break
            if any(
                marker in compact
                for marker in (
                    "면책및손해배상",
                    "indemnification",
                    "limitationofliability",
                )
            ):
                return start, number - 1

    next_family_starts = []
    for other_family, other_tag in FAMILY_TAG.items():
        if other_family == family:
            continue
        other = result["clause_map_json"].get(other_tag) or {}
        other_start = other.get("loc_start") if other.get("present") else None
        if isinstance(other_start, int) and other_start > start:
            next_family_starts.append(other_start)
    if next_family_starts:
        boundary = min(next_family_starts)
        return start, max(end, boundary - 1)

    later_clause_starts = []
    for clause in result["clause_map_json"].values():
        if not isinstance(clause, dict) or not clause.get("present"):
            continue
        clause_start = clause.get("loc_start")
        if isinstance(clause_start, int) and clause_start > end:
            later_clause_starts.append(clause_start)
    if later_clause_starts:
        return start, max(end, min(later_clause_starts) - 1)
    return expand_title_only_range(paragraph_by_number, start, end)


def load_taxonomy_catalog(conn: sqlite3.Connection) -> list[dict]:
    aliases: dict[str, list[str]] = {}
    for taxonomy_id, alias in conn.execute(
        """
        SELECT a.taxonomy_id,a.alias
        FROM v4_taxonomy_alias a
        JOIN v4_taxonomy_node n USING(taxonomy_id)
        WHERE n.status='active'
        ORDER BY a.taxonomy_id,a.alias
        """
    ):
        aliases.setdefault(str(taxonomy_id), []).append(str(alias))
    return [
        {
            "taxonomy_id": str(row[0]),
            "parent_id": str(row[1]) if row[1] is not None else None,
            "family": str(row[2]),
            "canonical_ko": str(row[3]),
            "canonical_en": str(row[4]),
            "definition": str(row[5]),
            "include_criteria": row[6],
            "exclude_criteria": row[7],
            "aliases": aliases.get(str(row[0]), []),
        }
        for row in conn.execute(
            """
            SELECT taxonomy_id,parent_id,family,canonical_ko,canonical_en,
                   definition,include_criteria,exclude_criteria
            FROM v4_taxonomy_node
            WHERE status='active'
            ORDER BY taxonomy_id
            """
        )
    ]


def _paragraph_rows(
    paragraph_by_number: dict[int, str],
    ranges: list[tuple[int, int]],
) -> list[dict]:
    numbers = sorted(
        {
            number
            for start, end in ranges
            for number in range(start, end + 1)
            if number in paragraph_by_number
        }
    )
    return [
        {"para": number, "text": paragraph_by_number[number]} for number in numbers
    ]


def _heading_range_near(
    paragraph_by_number: dict[int, str],
    anchor: int,
    heading_terms: tuple[str, ...],
    *,
    lookback: int = 100,
    lookahead: int = 0,
    max_paragraphs: int = 250,
) -> tuple[int, int] | None:
    candidates = []
    for number, text in paragraph_by_number.items():
        if not (max(1, anchor - lookback) <= number <= anchor + lookahead):
            continue
        compact = _compact(str(text))
        if len(str(text)) <= 180 and any(term in compact for term in heading_terms):
            candidates.append(number)
    if not candidates:
        return None
    start = max(candidates)
    end = start
    for number in sorted(number for number in paragraph_by_number if number > start):
        if number > start + max_paragraphs:
            break
        text = " ".join(str(paragraph_by_number[number]).split())
        if number > anchor and (
            MAJOR_HEADING_RE.match(text)
            or re.match(r"(?i)^\s*ARTICLE\s+[IVXLC0-9]+\b", text)
        ):
            break
        end = number
    return start, max(anchor, end)


def _definition_ranges(
    paragraph_by_number: dict[int, str],
    result: dict,
) -> list[tuple[int, int]]:
    items = (result.get("definitions_json") or {}).get("items") or []
    ranges = [
        (int(item["loc_start"]), int(item["loc_end"]))
        for item in items
        if isinstance(item, dict)
        and isinstance(item.get("loc_start"), int)
        and isinstance(item.get("loc_end"), int)
    ]
    if not ranges:
        return []
    anchor = min(start for start, _ in ranges)
    article = _heading_range_near(
        paragraph_by_number,
        anchor,
        ("용어의정의", "definitions", "definition"),
        lookahead=30,
        max_paragraphs=400,
    )
    return [article] if article else ranges


def _pay_ranges(
    paragraph_by_number: dict[int, str],
    result: dict,
) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    consideration = result.get("consideration_json") or {}
    if isinstance(consideration.get("loc_start"), int) and isinstance(
        consideration.get("loc_end"), int
    ):
        anchor = int(consideration["loc_start"])
        article = _heading_range_near(
            paragraph_by_number,
            anchor,
            ("매매대금", "인수대금", "양수대금", "purchaseprice", "consideration"),
            lookback=40,
            max_paragraphs=180,
        )
        ranges.append(
            article
            or (int(consideration["loc_start"]), int(consideration["loc_end"]))
        )
    for tag in SUPPLEMENTAL_FAMILY_TAGS["PAY"]:
        clause = (result.get("clause_map_json") or {}).get(tag) or {}
        if clause.get("present") and isinstance(clause.get("loc_start"), int):
            ranges.append((int(clause["loc_start"]), int(clause["loc_end"])))
    return ranges


def _remedy_ranges(
    paragraph_by_number: dict[int, str],
    result: dict,
) -> list[tuple[int, int]]:
    ranges = []
    for tag in SUPPLEMENTAL_FAMILY_TAGS["REM"]:
        clause = (result.get("clause_map_json") or {}).get(tag) or {}
        if clause.get("present") and isinstance(clause.get("loc_start"), int):
            ranges.append((int(clause["loc_start"]), int(clause["loc_end"])))
    ranges.sort()
    expanded = [
        (
            start,
            max(end, ranges[index + 1][0] - 1)
            if index + 1 < len(ranges)
            else end,
        )
        for index, (start, end) in enumerate(ranges)
    ]
    if expanded:
        start, end = expanded[-1]
        for number in sorted(
            number for number in paragraph_by_number if number > end
        ):
            if number > start + 300:
                break
            if MAJOR_HEADING_RE.match(
                " ".join(str(paragraph_by_number[number]).split())
            ):
                end = number - 1
                break
        expanded[-1] = (start, end)
    return expanded


def _supplemental_section(
    family: str,
    paragraph_by_number: dict[int, str],
    result: dict,
) -> dict:
    if family == "DEF":
        ranges = _definition_ranges(paragraph_by_number, result)
        source_tag: object = "definitions_json"
    elif family == "PAY":
        ranges = _pay_ranges(paragraph_by_number, result)
        source_tag = ["consideration_json", *SUPPLEMENTAL_FAMILY_TAGS["PAY"]]
    else:
        ranges = _remedy_ranges(paragraph_by_number, result)
        source_tag = list(SUPPLEMENTAL_FAMILY_TAGS["REM"])
    paragraphs = _paragraph_rows(paragraph_by_number, ranges)
    return {
        "source_tag": source_tag,
        "v3_present": bool(paragraphs),
        "v3_summary": None,
        "loc_start": min((row["para"] for row in paragraphs), default=None),
        "loc_end": max((row["para"] for row in paragraphs), default=None),
        "v3_loc_start": min((start for start, _ in ranges), default=None),
        "v3_loc_end": max((end for _, end in ranges), default=None),
        "ranges": [[start, end] for start, end in ranges],
        "range_expanded": any(end - start > 0 for start, end in ranges),
        "paragraphs": paragraphs,
        "atomic_unit_hints": build_atomic_unit_hints(paragraphs),
        "annex_status_hint": "not_evaluated",
    }


def build_input(
    source: dict,
    result: dict,
    *,
    taxonomy_version: int = 3,
    taxonomy_catalog: list[dict] | None = None,
) -> dict:
    paragraph_by_number = {row["para"]: row["text"] for row in source["paragraphs"]}
    sections = {}
    for family, tag in FAMILY_TAG.items():
        clause = result["clause_map_json"].get(tag) or {"present": False}
        paragraphs = []
        if clause.get("present"):
            start, end = clause["loc_start"], clause["loc_end"]
            start, end = expand_family_range(
                paragraph_by_number,
                result,
                family,
                int(start),
                int(end),
            )
            paragraphs = [
                {"para": number, "text": paragraph_by_number[number]}
                for number in range(start, end + 1)
                if number in paragraph_by_number
            ]
        sections[family] = {
            "source_tag": tag,
            "v3_present": bool(clause.get("present")),
            "v3_summary": clause.get("summary"),
            "loc_start": clause.get("loc_start"),
            "loc_end": end if clause.get("present") else clause.get("loc_end"),
            "v3_loc_start": clause.get("loc_start"),
            "v3_loc_end": clause.get("loc_end"),
            "range_expanded": bool(
                clause.get("present") and end != clause.get("loc_end")
            ),
            "paragraphs": paragraphs,
            "atomic_unit_hints": build_atomic_unit_hints(paragraphs),
            "annex_status_hint": "not_evaluated",
        }
    for family in ("DEF", "PAY", "REM"):
        sections[family] = _supplemental_section(
            family, paragraph_by_number, result
        )
    source_inventory = build_source_inventory(source, sections)
    for family, section in sections.items():
        section["source_ids"] = [
            row["source_id"] for row in source_inventory if row["family"] == family
        ]
    return {
        "file_key": source["file_key"],
        "content_hash": source["content_hash"],
        "ctype": source["ctype"],
        "lang": source["lang"],
        "path": source["path"],
        "meta_schema_version": 4,
        "taxonomy_version": taxonomy_version,
        "taxonomy_catalog": taxonomy_catalog or [],
        "prompt": ".docs/extract_prompt_v4.md",
        "approved_v3_context": {
            "deal_type_detail": result["deal_type_detail"],
            "document_status": result["document_status"],
            "confidence": result["confidence"],
        },
        "family_sections": sections,
        "source_inventory": source_inventory,
        "instructions": {
            "task": "extract_atomic_clause_items",
            "families": list(ALL_FAMILIES),
            "do_not_read_full_document": True,
            "require_atomic_items_for_all_units": True,
            "require_source_coverage_for_all_inventory": True,
            "no_paid_api": True,
            "output_file": f"{source['file_key']}.json",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--result-dir", type=Path)
    parser.add_argument("--v4-input-dir", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    v3_inputs = args.input_dir or args.out / "enrich_inputs_v3"
    v3_results = args.result_dir or args.out / "enrich_results_v3"
    v4_inputs = args.v4_input_dir or args.out / "enrich_inputs_v4"
    manifest_path = args.manifest or args.out / "v4_batch_01_manifest.json"
    v4_inputs.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(args.out / "catalog.sqlite") as conn:
        row = conn.execute(
            "SELECT value FROM v4_meta WHERE key='taxonomy_version'"
        ).fetchone()
        taxonomy_catalog = load_taxonomy_catalog(conn)
    taxonomy_version = int(row[0]) if row else 3

    items = []
    for key in REPRESENTATIVE_KEYS:
        source = json.loads((v3_inputs / f"{key}.json").read_text(encoding="utf-8"))
        result = json.loads((v3_results / f"{key}.json").read_text(encoding="utf-8"))
        if result["document_status"] != "contract":
            raise SystemExit(f"representative is not a contract: {key}")
        payload = build_input(
            source,
            result,
            taxonomy_version=taxonomy_version,
            taxonomy_catalog=taxonomy_catalog,
        )
        (v4_inputs / f"{key}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        items.append(
            {
                "file_key": key,
                "ctype": source["ctype"],
                "lang": source["lang"],
                "path": source["path"],
                "v3_confidence": result["confidence"],
                "family_ranges": {
                    family: [section["loc_start"], section["loc_end"]] if section["v3_present"] else None
                    for family, section in payload["family_sections"].items()
                },
            }
        )
    manifest = {
        "meta_schema_version": 4,
        "taxonomy_version": taxonomy_version,
        "schema_revision": "1R2",
        "batch": "V4-2 representative 10 (taxonomy v4)",
        "count": len(items),
        "items": items,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"count": len(items), "input_dir": str(v4_inputs), "manifest": str(manifest_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
