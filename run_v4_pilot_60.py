"""Build and context-review the formal V4-3 sixty-document pilot.

The ten approved representative documents are retained as the pilot anchor.
Fifty documents are selected proportionally from the 59 documents that only
have bounded positive-evidence V4 rows.  New inputs are rebuilt from current
doc_meta and txt caches; no paid API is used.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from finalize_v4_remaining_nine import (
    defined_term,
    finalize_result,
    prepare_reviewed_source,
)
from plan_v4_batch import (
    build_atomic_unit_hints,
    build_input,
    build_source_inventory,
    load_taxonomy_catalog,
)
from propose_v4_remaining_nine import build_result, load_nodes
from v4_schema import initialize_v4_schema, taxonomy_ids, validate_v4_result


REPRESENTATIVE_KEYS = (
    "0ba3a1b8246c5dd5",
    "a51842fc51010f69",
    "3c86175c4821fa83",
    "b324cb8bdf00015a",
    "660fc9d64566ba0e",
    "a5da55951cfdabfb",
    "0df5e9d7e1e7c893",
    "5853fe0540a72d6c",
    "b6fd6ff14e51e05f",
    "973d43e89040fb57",
)

FAMILIES = ("RW", "CP", "COV", "DEF", "PAY", "REM")
FAMILY_TITLE_PATTERNS = {
    "RW": (
        r"^\s*(?:[0-9IVXLC.() -]+\s*)?representations?\s+and\s+"
        r"warrant(?:y|ies)(?:\s+of\s+.{1,60})?\s*$",
        r"^\s*(?:[0-9IVXLC.() -]+\s*)?warrant(?:y|ies)\s+of\s+"
        r"(?:the\s+)?(?:seller|sellers|buyer|purchaser)\s*$",
        r"^\s*(?:제?\s*\d+\s*조\s*)?(?:.{0,30}의\s+)?"
        r"진술\s*(?:및|과)?\s*보장\s*[.;:]?\s*$",
    ),
    "CP": (
        r"^\s*(?:[0-9IVXLC.() -]+\s*)?conditions\s+"
        r"(?:precedent|to\s+(?:closing|completion))(?:\s+.{1,40})?\s*$",
        r"^\s*(?:제?\s*\d+\s*조\s*)?(?:.{0,35}의\s+)?선행조건\s*[.;:]?\s*$",
    ),
    "COV": (
        r"^\s*(?:[0-9IVXLC.() -]+\s*)?(?:covenants?|undertakings?)\s*$",
        r"^\s*(?:제?\s*\d+\s*조\s*)?(?:확약|확약사항|약정|약정사항)\s*$",
    ),
    "DEF": (
        r"^\s*(?:[0-9IVXLC.() -]+\s*)?(?:definitions?|interpretation)\s*$",
        r"^\s*(?:제?\s*\d+\s*조\s*)?(?:용어의\s*정의|정의|해석)\s*$",
    ),
    "PAY": (
        r"^\s*(?:[0-9IVXLC.() -]+\s*)?(?:purchase\s+price|consideration)\s*$",
        r"^\s*(?:제?\s*\d+\s*조\s*)?(?:매매대금|양수도대금|인수대금|대금)\s*$",
    ),
    "REM": (
        r"^\s*(?:[0-9IVXLC.() -]+\s*)?(?:indemnification|indemnity|"
        r"limitations?\s+on\s+claims?(?:\s+against\s+the\s+sellers?)?|"
        r"warranty\s+and\s+indemnity\s+insurance|tax\s+indemnity)\s*$",
        r"^\s*(?:제?\s*\d+\s*조\s*)?(?:손해배상|손해배상책임|"
        r"손해배상\s*및\s*존속기간(?:\s*등)?|배상)\s*[.;:]?\s*$",
        r"^\s*(?:제?\s*\d+\s*조\s*)?손해배상.*(?:위약벌|존속기간).*$",
    ),
}
TOC_LEADER_RE = re.compile(r"\.{4,}")
ANNEX_TITLE_RE = re.compile(
    r"^\s*(?:schedule|annex|exhibit|별지|별첨|부속서)\s*"
    r"(?:[0-9A-Z가-힣]+(?:[.-][0-9A-Z가-힣]+)*)?\s*$",
    re.IGNORECASE,
)
TARGET_ADDITIONS = 50


def read_paragraphs(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"^\[¶(\d+)\]\s*(.*)$", line)
        if match:
            rows.append({"para": int(match.group(1)), "text": match.group(2)})
    return rows


def normalize_title(value: str) -> str:
    value = TOC_LEADER_RE.sub(" ", value)
    value = re.sub(r"\s+\d+\s*$", "", value)
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", value).casefold()


def title_family(value: str) -> str | None:
    text = " ".join(value.split()).strip()
    if not text or len(text) > 180 or TOC_LEADER_RE.search(text):
        return None
    for family, patterns in FAMILY_TITLE_PATTERNS.items():
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns):
            # Broad RW/CP expressions must still look like a title, not an
            # operative condition or remedy sentence referring to the topic.
            if family in {"RW", "CP"} and len(text) > 90:
                continue
            if family in {"RW", "CP"} and re.search(
                r"(?:shall|must|will|is|are|has|have|한다|하여야|일\s*것|경우)",
                text,
                re.IGNORECASE,
            ):
                continue
            return family
    return None


def toc_titles(paragraphs: list[dict]) -> set[str]:
    titles: set[str] = set()
    recognized_family_titles = 0
    for row in paragraphs:
        text = " ".join(str(row.get("text") or "").split()).strip()
        if not TOC_LEADER_RE.search(text):
            continue
        title = TOC_LEADER_RE.split(text, maxsplit=1)[0].strip(" .\t")
        normalized = normalize_title(title)
        if len(normalized) >= 4:
            titles.add(normalized)
            if title_family(title) or major_heading_family(title):
                recognized_family_titles += 1
    return titles if recognized_family_titles >= 2 else set()


def generic_major_heading(value: str, known_toc_titles: set[str]) -> bool:
    text = " ".join(value.split()).strip()
    if not text or len(text) > 100 or TOC_LEADER_RE.search(text):
        return False
    if normalize_title(text) in known_toc_titles:
        return True
    if ANNEX_TITLE_RE.fullmatch(text):
        return True
    # Korean contracts commonly omit article numbers in the extracted cache.
    if re.search(r"[가-힣]", text):
        return (
            len(text) <= 55
            and not re.search(r"[.。;:]$", text)
            and not re.search(r"(?:한다|된다|있다|없다|이다|것이다)$", text)
        )
    if known_toc_titles:
        return False
    return bool(
        re.match(
            r"^(?:(?:ARTICLE\s+[IVXLC0-9]+|\d+(?:\.\d+)*)\.?\s+)?"
            r"[A-Z][A-Za-z0-9 &'(),/.-]+$",
            text,
            re.IGNORECASE,
        )
        and len(text.split()) <= 12
    )


def major_heading_family(value: str) -> str | None:
    """Infer the family of a verified major heading, including subarticles."""

    text = " ".join(value.split()).strip()
    lowered = text.casefold()
    if (
        ("warrant" in lowered or "진술" in text and "보장" in text)
        and "indemnity insurance" not in lowered
        and "claim" not in lowered
    ):
        return "RW"
    if re.search(r"\bconditions?\s+precedent\b", lowered) or "선행조건" in text:
        return "CP"
    if re.search(r"\b(?:covenants?|undertakings?)\b", lowered) or re.fullmatch(
        r"(?:제?\s*\d+\s*조\s*)?(?:확약|확약사항|약정|약정사항)",
        text,
    ):
        return "COV"
    if re.search(r"\b(?:definitions?|interpretation)\b", lowered) or re.fullmatch(
        r"(?:제?\s*\d+\s*조\s*)?(?:용어의\s*정의|정의|해석)",
        text,
    ):
        return "DEF"
    if re.search(r"\b(?:purchase price|consideration)\b", lowered) or re.fullmatch(
        r"(?:제?\s*\d+\s*조\s*)?(?:매매대금|양수도대금|인수대금|대금)",
        text,
    ):
        return "PAY"
    if (
        re.search(r"\b(?:indemnification|indemnity)\b", lowered)
        or "limitation" in lowered and "claim" in lowered
        or "손해배상" in text
    ):
        return "REM"
    return None


def locate_family_ranges(paragraphs: list[dict]) -> dict[str, list[tuple[int, int]]]:
    """Locate actual articles and reject table-of-contents coordinates."""

    paragraph_by_number = {
        int(row["para"]): str(row.get("text") or "") for row in paragraphs
    }
    if not paragraph_by_number:
        return {family: [] for family in FAMILIES}
    toc = toc_titles(paragraphs)
    article_heading_count = sum(
        bool(
            re.match(
                r"^\s*ARTICLE\s+(?:[IVXLC]+|\d+)\.?\s+\S",
                str(text),
                re.IGNORECASE,
            )
        )
        for text in paragraph_by_number.values()
    )
    article_mode = not toc and article_heading_count >= 3
    family_at: dict[int, str] = {}
    boundaries: set[int] = set()
    for number, text in paragraph_by_number.items():
        family = title_family(text)
        is_major = generic_major_heading(text, toc)
        if article_mode:
            is_article = bool(
                re.match(
                    r"^\s*ARTICLE\s+(?:[IVXLC]+|\d+)\.?\s+\S",
                    text,
                    re.IGNORECASE,
                )
            )
            is_major = is_article or bool(ANNEX_TITLE_RE.fullmatch(text.strip()))
            if not is_article:
                family = None
        is_latin_toc_match = (
            not re.search(r"[가-힣]", text)
            and normalize_title(text) in toc
            and not ANNEX_TITLE_RE.fullmatch(" ".join(text.split()).strip())
        )
        if is_major and is_latin_toc_match and family is None:
            previous = " ".join(
                paragraph_by_number.get(number - 1, "").split()
            ).strip()
            is_major = bool(
                re.fullmatch(r"(?:ARTICLE\s+)?(?:[IVXLC]+|\d+)\.", previous, re.IGNORECASE)
            )
        if family or is_major:
            inferred = family or major_heading_family(text)
            if inferred:
                family_at[number] = inferred
        if family or is_major:
            boundaries.add(number)
    boundaries.add(max(paragraph_by_number) + 1)
    ordered_boundaries = sorted(boundaries)
    ranges: dict[str, list[tuple[int, int]]] = {family: [] for family in FAMILIES}
    for start in sorted(family_at):
        family = family_at[start]
        end = max(paragraph_by_number)
        for boundary in (number for number in ordered_boundaries if number > start):
            # Consecutive headings/subheadings for the same legal family form
            # one article. A different or generic major heading closes it.
            if family_at.get(boundary) == family:
                continue
            end = boundary - 1
            break
        if end >= start:
            ranges[family].append((start, end))
    for family, rows in ranges.items():
        merged: list[tuple[int, int]] = []
        for start, end in rows:
            if merged and start <= merged[-1][1] + 1:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        ranges[family] = merged
    return ranges


def repair_family_sections(payload: dict, source: dict) -> dict:
    """Replace noisy T3/TOC ranges with locally detected article ranges."""

    paragraphs = source["paragraphs"]
    paragraph_by_number = {
        int(row["para"]): str(row.get("text") or "") for row in paragraphs
    }
    ranges = locate_family_ranges(paragraphs)
    sections = payload["family_sections"]
    for family in FAMILIES:
        family_ranges = ranges[family]
        if not family_ranges:
            existing = sections.get(family, {})
            existing_rows = list(existing.get("paragraphs") or [])
            if (
                family in {"DEF", "PAY"}
                and existing_rows
                and len(existing_rows) <= 250
                and not TOC_LEADER_RE.search(
                    str(existing_rows[0].get("text") or "")
                )
            ):
                existing["range_repair"] = "bounded_doc_meta_fallback"
                continue
            sections[family] = {
                **existing,
                "loc_start": None,
                "loc_end": None,
                "ranges": [],
                "paragraphs": [],
                "atomic_unit_hints": [],
                "range_expanded": False,
                "range_repair": "no_reliable_article_heading",
            }
            continue
        rows = [
            {"para": number, "text": paragraph_by_number[number]}
            for start, end in family_ranges
            for number in range(start, end + 1)
            if number in paragraph_by_number
        ]
        if family == "DEF":
            hints = [
                {
                    "unit_id": f"u-{row['para']}",
                    "loc_start": row["para"],
                    "loc_end": row["para"],
                    "heading": row["text"],
                }
                for row in rows
                if defined_term(str(row["text"]))
            ]
        else:
            hints = build_atomic_unit_hints(rows)
        sections[family] = {
            **sections.get(family, {}),
            "loc_start": min(row["para"] for row in rows),
            "loc_end": max(row["para"] for row in rows),
            "ranges": [[start, end] for start, end in family_ranges],
            "paragraphs": rows,
            "atomic_unit_hints": hints,
            "range_expanded": True,
            "range_repair": "actual_heading_and_major_boundary",
        }
    payload["source_inventory"] = build_source_inventory(source, sections)
    for family, section in sections.items():
        section["source_ids"] = [
            row["source_id"]
            for row in payload["source_inventory"]
            if row["family"] == family
        ]
    return payload


def allocate_quotas(
    counts: dict[tuple[str, str], int],
    *,
    target: int,
) -> dict[tuple[str, str], int]:
    total = sum(counts.values())
    if target > total:
        raise ValueError(f"target {target} exceeds eligible population {total}")
    exact = {key: target * count / total for key, count in counts.items()}
    quotas = {key: int(value) for key, value in exact.items()}
    remaining = target - sum(quotas.values())
    ranked = sorted(
        counts,
        key=lambda key: (-(exact[key] - quotas[key]), key),
    )
    for key in ranked[:remaining]:
        quotas[key] += 1
    return quotas


def select_additions(conn: sqlite3.Connection) -> tuple[list[dict], dict]:
    placeholders = ",".join("?" for _ in REPRESENTATIVE_KEYS)
    rows = [
        dict(row)
        for row in conn.execute(
            f"""
            SELECT DISTINCT f.file_key,f.path,f.ctype,f.lang,f.content_hash,
                   f.txt_path,d.txt_hash
            FROM v4_document_coverage c
            JOIN files f USING(file_key)
            JOIN doc_meta d USING(file_key)
            WHERE f.status='ok'
              AND f.file_key NOT IN ({placeholders})
            ORDER BY f.ctype,f.lang,f.file_key
            """,
            REPRESENTATIVE_KEYS,
        )
    ]
    eligible = [
        row
        for row in rows
        if row["txt_hash"] == row["content_hash"]
        and row.get("txt_path")
    ]
    if len(eligible) < TARGET_ADDITIONS:
        raise RuntimeError(
            f"only {len(eligible)} current doc_meta/txt documents are eligible"
        )
    strata: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in eligible:
        strata[(str(row["ctype"]), str(row["lang"]))].append(row)
    counts = {key: len(value) for key, value in strata.items()}
    quotas = allocate_quotas(counts, target=TARGET_ADDITIONS)
    selected = [
        row
        for key in sorted(strata)
        for row in strata[key][: quotas[key]]
    ]
    return selected, {
        "population": len(rows),
        "eligible": len(eligible),
        "stale_or_missing": len(rows) - len(eligible),
        "strata_population": {
            f"{key[0]}|{key[1]}": counts[key] for key in sorted(counts)
        },
        "strata_selected": {
            f"{key[0]}|{key[1]}": quotas[key] for key in sorted(quotas)
        },
    }


def load_v3_like_payload(
    conn: sqlite3.Connection,
    out: Path,
    row: dict,
) -> tuple[dict, dict]:
    txt_path = Path(str(row["txt_path"]))
    if not txt_path.is_absolute():
        txt_path = out / txt_path
    paragraphs = read_paragraphs(txt_path)
    if not paragraphs:
        raise RuntimeError(f"{row['file_key']}: no cached paragraphs")
    meta = conn.execute(
        """
        SELECT deal_type_detail,consideration_json,clause_map_json,
               definitions_json,confidence
        FROM doc_meta WHERE file_key=?
        """,
        (row["file_key"],),
    ).fetchone()
    source = {
        "file_key": row["file_key"],
        "path": row["path"],
        "ctype": row["ctype"],
        "lang": row["lang"],
        "content_hash": row["content_hash"],
        "paragraphs": paragraphs,
    }
    result = {
        "document_status": "contract",
        "confidence": str(meta["confidence"] or "med"),
        "deal_type_detail": str(meta["deal_type_detail"] or row["ctype"] or ""),
        "consideration_json": json.loads(meta["consideration_json"] or "{}"),
        "clause_map_json": json.loads(meta["clause_map_json"] or "{}"),
        "definitions_json": json.loads(meta["definitions_json"] or "{}"),
    }
    return source, result


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--raw-input-dir", type=Path)
    parser.add_argument("--pre-result-dir", type=Path)
    parser.add_argument("--final-input-dir", type=Path)
    parser.add_argument("--final-result-dir", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--cohort-manifest", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    raw_input_dir = args.raw_input_dir or args.out / "enrich_inputs_v4_pilot60_raw"
    pre_result_dir = (
        args.pre_result_dir or args.out / "enrich_results_v4_pilot60_pre"
    )
    final_input_dir = (
        args.final_input_dir or args.out / "enrich_inputs_v4_pilot60_final"
    )
    final_result_dir = (
        args.final_result_dir or args.out / "enrich_results_v4_pilot60_final"
    )
    manifest_path = args.manifest or args.out / "v4_pilot60_final_manifest.json"
    cohort_path = (
        args.cohort_manifest or args.out / "v4_pilot60_cohort_manifest.json"
    )
    for directory in (
        raw_input_dir,
        pre_result_dir,
        final_input_dir,
        final_result_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(args.out / "catalog.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        initialize_v4_schema(conn)
        taxonomy_version = int(
            conn.execute(
                "SELECT value FROM v4_meta WHERE key='taxonomy_version'"
            ).fetchone()[0]
        )
        catalog = load_taxonomy_catalog(conn)
        nodes, _index = load_nodes(conn)
        known = taxonomy_ids(conn)
        selected, selection = select_additions(conn)
        conn.commit()

        manifest_rows = []
        total_pre_candidates = 0
        total_final_candidates = 0
        total_items = 0
        docs_with_candidates = 0
        for row in selected:
            source, v3_result = load_v3_like_payload(conn, args.out, row)
            raw = build_input(
                source,
                v3_result,
                taxonomy_version=taxonomy_version,
                taxonomy_catalog=catalog,
            )
            raw = repair_family_sections(raw, source)
            raw_path = raw_input_dir / f"{row['file_key']}.json"
            write_json(raw_path, raw)

            pre = build_result(raw, nodes)
            pre_path = pre_result_dir / f"{row['file_key']}.json"
            write_json(pre_path, pre)
            pre_count = len(pre["taxonomy_candidates"])
            total_pre_candidates += pre_count

            final, unresolved = finalize_result(pre, known, source=raw)
            reviewed_source = prepare_reviewed_source(raw, final)
            final_input_path = final_input_dir / f"{row['file_key']}.json"
            final_result_path = final_result_dir / f"{row['file_key']}.json"
            write_json(final_input_path, reviewed_source)
            write_json(final_result_path, final)
            if not unresolved:
                validate_v4_result(
                    final,
                    file_key=str(row["file_key"]),
                    known_taxonomy=known,
                )
            final_count = len(unresolved)
            total_final_candidates += final_count
            docs_with_candidates += int(final_count > 0)
            total_items += len(final["items"])
            manifest_rows.append(
                {
                    "file_key": row["file_key"],
                    "ctype": row["ctype"],
                    "lang": row["lang"],
                    "path": row["path"],
                    "item_count": len(final["items"]),
                    "pre_candidate_count": pre_count,
                    "candidate_count": final_count,
                    "input_path": str(final_input_path),
                    "result_path": str(final_result_path),
                }
            )

    manifest = {
        "meta_schema_version": 4,
        "taxonomy_version": taxonomy_version,
        "schema_revision": "1R2",
        "batch": "V4-3 formal pilot additions (50 documents)",
        "count": len(manifest_rows),
        "selection": selection,
        "pre_candidate_count": total_pre_candidates,
        "candidate_count": total_final_candidates,
        "candidate_document_count": docs_with_candidates,
        "item_count": total_items,
        "items": manifest_rows,
    }
    write_json(manifest_path, manifest)
    cohort = {
        "meta_schema_version": 4,
        "taxonomy_version": taxonomy_version,
        "batch": "V4-3 formal sixty-document pilot",
        "count": 60,
        "representative_count": len(REPRESENTATIVE_KEYS),
        "addition_count": len(manifest_rows),
        "representative_keys": list(REPRESENTATIVE_KEYS),
        "addition_keys": [row["file_key"] for row in manifest_rows],
        "selection": selection,
    }
    write_json(cohort_path, cohort)
    print(
        json.dumps(
            {
                "pilot_count": 60,
                "addition_count": len(manifest_rows),
                "item_count": total_items,
                "pre_candidate_count": total_pre_candidates,
                "candidate_count": total_final_candidates,
                "candidate_document_count": docs_with_candidates,
                "manifest": str(manifest_path),
                "cohort_manifest": str(cohort_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
