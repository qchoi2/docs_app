"""Build a conservative V4-2 pre-review bundle for the remaining nine documents.

This is a local proposal pass, not a production extractor.  It uses the
approved taxonomy aliases to find high-signal propositions, preserves exact
paragraph evidence, and deliberately marks every proposed item and coverage
row for review.  It never writes to the operational V4 tables.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from lib.console import configure_utf8_stdio
from lib.normalize import normalize


REMAINING_KEYS = (
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
GENERIC_TERMS = {
    "계약",
    "의무",
    "권리",
    "손해",
    "조세",
    "세금",
    "주식",
    "자산",
    "부채",
    "동의",
    "승인",
    "통지",
    "agreement",
    "contract",
    "obligation",
    "right",
    "rights",
    "loss",
    "losses",
    "tax",
    "taxes",
    "asset",
    "assets",
    "liability",
    "liabilities",
    "consent",
    "approval",
    "notice",
    "no",
    "not",
    "none",
    "any",
    "all",
    "each",
    "shall",
    "may",
    "must",
    "company",
    "target",
    "seller",
    "sellers",
    "buyer",
    "purchaser",
    "party",
    "parties",
    "business",
    "material",
    "materially",
    "relevant",
    "applicable",
    "transaction",
    "대상회사",
    "회사",
    "매도인",
    "매수인",
    "당사자",
    "모든",
    "중요한",
    "중대한",
    "관련",
    "해당",
    "본건",
    "거래",
    "사항",
    "경우",
}
HEADING_ONLY = re.compile(
    r"^(article|section|schedule|annex|exhibit|별지|부록|제\s*\d+\s*[조장절])"
    r"[\s\d.\-–—()가-힣a-z]*$",
    re.IGNORECASE,
)
NEGATIVE_ABSENCE = re.compile(
    r"(없(?:다|으며|고|는|음)|존재하지|발생하지|해당하지|부담하지|"
    r"\bno\b|\bnone\b|\bwithout\b|\bdoes not exist\b|\bhas not\b)",
    re.IGNORECASE,
)
NEGATIVE_PROHIBITION = re.compile(
    r"(하여서는 아니|해서는 아니|금지|제한한다|않아야|\bshall not\b|\bmay not\b|\bmust not\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Node:
    taxonomy_id: str
    parent_id: str | None
    family: str
    canonical_ko: str
    canonical_en: str
    terms: tuple[str, ...]


def compact(value: object) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", normalize(str(value or "")).casefold())


def words(value: object) -> set[str]:
    return {
        token
        for token in re.findall(r"[0-9a-z가-힣]+", normalize(str(value or "")).casefold())
        if len(token) >= 2 and token not in GENERIC_TERMS
    }


def useful_term(value: str) -> bool:
    cleaned = compact(value)
    if not cleaned or cleaned in {compact(row) for row in GENERIC_TERMS}:
        return False
    latin_tokens = re.findall(r"[a-z0-9]+", normalize(value).casefold())
    if latin_tokens and not re.search(r"[가-힣]", value):
        return len(cleaned) >= 7 or len(latin_tokens) >= 2 or cleaned in {
            "ebitda",
            "firpta",
            "rwi",
            "rofr",
            "rofo",
        }
    return len(cleaned) >= 4


def load_nodes(conn: sqlite3.Connection) -> tuple[dict[str, Node], dict[str, list[tuple[str, int]]]]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT n.taxonomy_id,n.parent_id,n.family,n.canonical_ko,n.canonical_en,
               n.definition,n.include_criteria,
               CASE WHEN c.taxonomy_id IS NULL THEN 1 ELSE 0 END AS is_leaf
        FROM v4_taxonomy_node n
        LEFT JOIN v4_taxonomy_node c
          ON c.parent_id=n.taxonomy_id AND c.status='active'
        WHERE n.status='active'
        GROUP BY n.taxonomy_id
        ORDER BY n.taxonomy_id
        """
    ).fetchall()
    aliases: dict[str, list[str]] = defaultdict(list)
    for row in conn.execute(
        "SELECT taxonomy_id,alias FROM v4_taxonomy_alias ORDER BY taxonomy_id,alias"
    ):
        aliases[str(row["taxonomy_id"])].append(str(row["alias"]))

    nodes: dict[str, Node] = {}
    index: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for row in rows:
        if not int(row["is_leaf"]):
            continue
        taxonomy_id = str(row["taxonomy_id"])
        raw_terms = [
            str(row["canonical_ko"] or ""),
            str(row["canonical_en"] or ""),
            *aliases.get(taxonomy_id, []),
        ]
        terms = tuple(dict.fromkeys(term.strip() for term in raw_terms if useful_term(term.strip())))
        node = Node(
            taxonomy_id=taxonomy_id,
            parent_id=str(row["parent_id"]) if row["parent_id"] else None,
            family=str(row["family"]),
            canonical_ko=str(row["canonical_ko"]),
            canonical_en=str(row["canonical_en"]),
            terms=terms,
        )
        nodes[taxonomy_id] = node
        for term in terms:
            index[node.family].append((taxonomy_id, len(compact(term))))
    return nodes, index


def paragraph_matches(text: str, family: str, nodes: dict[str, Node]) -> list[tuple[str, int, str]]:
    normalized_text = normalize(text).casefold()
    compact_text = compact(text)
    matches: dict[str, tuple[int, str]] = {}
    for node in nodes.values():
        if node.family != family:
            continue
        for term in node.terms:
            normalized_term = normalize(term).casefold()
            compact_term = compact(term)
            if not compact_term:
                continue
            direct = normalized_term in normalized_text or compact_term in compact_text
            if direct:
                score = len(compact_term)
                prior = matches.get(node.taxonomy_id)
                if prior is None or score > prior[0]:
                    matches[node.taxonomy_id] = (score, term)
    ranked = sorted(
        ((taxonomy_id, score, term) for taxonomy_id, (score, term) in matches.items()),
        key=lambda row: (-row[1], row[0]),
    )
    if not ranked:
        return []
    best = ranked[0][1]
    # Preserve multiple genuinely independent explicit matches while suppressing
    # very short incidental terms in long schedules.
    return [row for row in ranked if row[1] >= max(4, min(best, 8))][:6]


def nearest_node(text: str, family: str, nodes: dict[str, Node]) -> Node:
    text_words = words(text)
    best: tuple[float, str] | None = None
    for node in nodes.values():
        if node.family != family:
            continue
        node_words = words(" ".join((node.canonical_ko, node.canonical_en, *node.terms)))
        overlap = len(text_words & node_words)
        union = len(text_words | node_words) or 1
        score = overlap / union
        candidate = (score, node.taxonomy_id)
        if best is None or candidate > best:
            best = candidate
    if best is None:
        raise RuntimeError(f"no leaf taxonomy node for family {family}")
    return nodes[best[1]]


def substantive(text: str) -> bool:
    cleaned = normalize(text).strip()
    if len(compact(cleaned)) < 12:
        return False
    if HEADING_ONLY.fullmatch(cleaned):
        return False
    latin_words = re.findall(r"[A-Za-z]+", cleaned)
    if (
        latin_words
        and len(latin_words) <= 10
        and not re.search(
            r"\b(shall|must|may|will|is|are|has|have|means|agrees|undertakes)\b",
            cleaned,
            re.IGNORECASE,
        )
    ):
        return False
    if (
        re.search(r"[가-힣]", cleaned)
        and len(compact(cleaned)) < 30
        and not re.search(r"(한다|있다|없다|된다|의미|말한다|하여야|아니)", cleaned)
    ):
        return False
    return True


def polarity(text: str) -> str:
    if NEGATIVE_ABSENCE.search(text):
        return "none_exist"
    if NEGATIVE_PROHIBITION.search(text):
        return "negative"
    return "affirmative"


def item(
    *,
    item_ref: str,
    family: str,
    node: Node,
    paragraph: dict,
    source_kind: str,
    source_id: str | None,
    source_name: str | None,
    parent_clause_ref: str | None,
    matched_term: str,
) -> dict:
    text = str(paragraph["text"]).strip()
    para = int(paragraph["para"])
    return {
        "item_ref": item_ref,
        "family": family,
        "taxonomy_id": node.taxonomy_id,
        "proposition": f"{node.canonical_ko}: {text}",
        "statement_polarity": polarity(text),
        "subject_role": None,
        "counterparty_role": None,
        "action": None,
        "object_type": None,
        "effective_time": None,
        "source_kind": source_kind,
        "source_id": source_id,
        "source_name": source_name,
        "source_ref": f"¶{para}",
        "parent_clause_ref": parent_clause_ref,
        "related_item_ref": None,
        "qualifier": {"matched_alias": matched_term, "proposal_pass": True},
        "verbatim": text,
        "loc_start": para,
        "loc_end": para,
        "normalized": {},
        "confidence": "low",
        "review_status": "needs_review",
    }


def source_status(status_hint: object) -> str:
    hint = str(status_hint or "").casefold()
    if hint == "missing":
        return "missing"
    if hint == "unreadable":
        return "unreadable"
    if hint in {"available", "partial"}:
        return "partial"
    return "not_evaluated"


def build_result(payload: dict, nodes: dict[str, Node]) -> dict:
    counters: Counter[str] = Counter()
    items: list[dict] = []
    candidates: list[dict] = []
    covered_body: dict[str, set[int]] = defaultdict(set)
    seen_items: set[tuple[str, str, int, str | None]] = set()

    def add_paragraph(
        family: str,
        paragraph: dict,
        *,
        source_kind: str,
        source_id: str | None,
        source_name: str | None,
        parent_clause_ref: str | None,
    ) -> None:
        text = str(paragraph.get("text") or "").strip()
        if not substantive(text):
            return
        if family != "DEF" and re.search(
            r'(^|[\s"(])[^"]{0,80}("?\s+shall mean\b|"?\s+means\b|이란|이라 함은|의미한다)',
            text,
            re.IGNORECASE,
        ):
            return
        para = int(paragraph["para"])
        for taxonomy_id, _score, matched_term in paragraph_matches(text, family, nodes):
            dedupe = (family, taxonomy_id, para, source_id)
            if dedupe in seen_items:
                continue
            seen_items.add(dedupe)
            counters[family] += 1
            items.append(
                item(
                    item_ref=f"{family}-{counters[family]:04d}",
                    family=family,
                    node=nodes[taxonomy_id],
                    paragraph=paragraph,
                    source_kind=source_kind,
                    source_id=source_id,
                    source_name=source_name,
                    parent_clause_ref=parent_clause_ref,
                    matched_term=matched_term,
                )
            )
            if source_kind == "body":
                covered_body[family].add(para)

    sections = payload.get("family_sections") or {}
    for family in FAMILIES:
        section = sections.get(family) or {}
        hints = section.get("atomic_unit_hints") or []
        hint_by_para: dict[int, str] = {}
        for hint in hints:
            heading = str(hint.get("heading") or hint.get("unit_id") or "")
            for para in range(int(hint["loc_start"]), int(hint["loc_end"]) + 1):
                hint_by_para.setdefault(para, heading)
        for paragraph in section.get("paragraphs") or []:
            add_paragraph(
                family,
                paragraph,
                source_kind="body",
                source_id=None,
                source_name=None,
                parent_clause_ref=hint_by_para.get(int(paragraph["para"])),
            )

    source_coverage: list[dict] = []
    for source in payload.get("source_inventory") or []:
        family = str(source["family"])
        source_id = str(source["source_id"])
        source_name = str(source["source_name"])
        status = source_status(source.get("status_hint"))
        source_coverage.append(
            {
                "family": family,
                "source_id": source_id,
                "source_kind": str(source["source_kind"]),
                "source_name": source_name,
                "source_ref": source.get("source_ref"),
                "storage_file_key": source.get("storage_file_key"),
                "status": status,
                "reason": "alias 기반 사전분류 완료; 사람 전수검토 전이므로 partial"
                if status == "partial"
                else "입력 inventory 상태를 보존함",
            }
        )
        if status not in {"partial", "complete"}:
            continue
        for paragraph in source.get("paragraphs") or []:
            add_paragraph(
                family,
                paragraph,
                source_kind=str(source["source_kind"]),
                source_id=source_id,
                source_name=source_name,
                parent_clause_ref=source_name,
            )

    # Every body atomic-unit hint with no proposed item becomes an explicit
    # taxonomy/review candidate rather than silently disappearing.
    for family in FAMILIES:
        section = sections.get(family) or {}
        paragraph_map = {
            int(row["para"]): str(row["text"])
            for row in section.get("paragraphs") or []
        }
        for hint in section.get("atomic_unit_hints") or []:
            start, end = int(hint["loc_start"]), int(hint["loc_end"])
            if any(start <= para <= end for para in covered_body[family]):
                continue
            evidence_row = next(
                (
                    (number, paragraph_map[number].strip())
                    for number in range(start, end + 1)
                    if number in paragraph_map and substantive(paragraph_map[number])
                ),
                None,
            )
            if not evidence_row:
                continue
            evidence_para, evidence = evidence_row
            nearest = nearest_node(f"{hint.get('heading') or ''} {evidence}", family, nodes)
            proposed = str(hint.get("heading") or evidence[:70]).strip()
            candidates.append(
                {
                    "proposed_ko": f"검토후보: {proposed}",
                    "proposed_en": None,
                    "family": family,
                    "recommended_parent_id": nearest.parent_id or family,
                    "distinction_reason": "기존 canonical·alias의 고신뢰 직접 일치가 없어 문맥 검토가 필요함",
                    "loc_start": evidence_para,
                    "loc_end": evidence_para,
                    "verbatim": evidence,
                    "nearest_taxonomy_id": nearest.taxonomy_id,
                    "source_kind": "body",
                    "source_id": None,
                    "source_name": "계약서 본문",
                    "source_ref": f"¶{evidence_para}",
                    "parent_clause_ref": proposed or None,
                    "qualifier": {"proposal_pass": True},
                }
            )

    inventory_by_family: dict[str, list[dict]] = defaultdict(list)
    for row in source_coverage:
        inventory_by_family[str(row["family"])].append(row)
    coverage = {}
    for family in FAMILIES:
        body_has_text = bool((sections.get(family) or {}).get("paragraphs"))
        source_rows = inventory_by_family[family]
        if not source_rows:
            annex_status = "no_annex"
        elif any(row["status"] in {"missing", "unreadable", "not_evaluated"} for row in source_rows):
            annex_status = "not_evaluated"
        else:
            annex_status = "partial"
        coverage[family] = {
            "body_status": "partial" if body_has_text else "not_evaluated",
            "annex_status": annex_status,
            "reason": "taxonomy v8 alias 기반 사전분류; 사람 검수 및 원자성 확정 전",
        }

    return {
        "file_key": payload["file_key"],
        "meta_schema_version": 4,
        "taxonomy_version": int(payload["taxonomy_version"]),
        "extractor_version": "local-alias-proposal-1",
        "prompt_version": "v4-prompt-8-pre-review",
        "items": items,
        "coverage": coverage,
        "source_coverage": source_coverage,
        "taxonomy_candidates": candidates,
    }


def render_report(rows: Iterable[dict], *, taxonomy_version: int) -> str:
    rows = list(rows)
    total_items = sum(int(row["item_count"]) for row in rows)
    total_candidates = sum(int(row["candidate_count"]) for row in rows)
    lines = [
        "# V4-2 나머지 9건 사전분류 보고서",
        "",
        f"- taxonomy version: {taxonomy_version}",
        f"- 문서: {len(rows)}건",
        f"- 사람 검수 대기 item: {total_items}개",
        f"- taxonomy·문맥 검토 후보: {total_candidates}개",
        "- 운영 DB 적재: 하지 않음",
        "",
        "이 결과는 canonical·alias 직접 일치에 기반한 보수적 사전분류다. 모든 item은",
        "`needs_review`, 모든 평가범위는 `partial`로 유지한다. 사람 검수와 원자성 확인 전에는",
        "V4 완료 또는 조항 부재의 근거로 사용할 수 없다.",
        "",
        "| file_key | 유형 | 언어 | item | 후보 | 별지 source |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['file_key']}` | {row['ctype']} | {row['lang']} | "
            f"{row['item_count']} | {row['candidate_count']} | {row['source_count']} |"
        )
    lines.extend(
        [
            "",
            "## 다음 검수 순서",
            "",
            "1. 후보가 많은 문서부터 문단 문맥으로 기존 노드 병합·alias 추가·신규 leaf 여부를 판정한다.",
            "2. 각 atomic unit의 독립 명제 누락과 복수 명제 뭉침을 수정한다.",
            "3. 별지·Disclosure Schedule별 coverage를 complete/missing/unreadable로 확정한다.",
            "4. 감사 pass 및 소유자 승인 결과만 운영 DB에 적재한다.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--result-dir", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--report", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    input_dir = args.input_dir or args.out / "enrich_inputs_v4"
    result_dir = args.result_dir or args.out / "enrich_results_v4_batch_02_pre_review"
    manifest_path = args.manifest or args.out / "v4_batch_02_pre_review_manifest.json"
    report_path = args.report or Path(".docs/V4_BATCH_02_PRE_REVIEW_20260723.md")
    result_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(args.out / "catalog.sqlite") as conn:
        nodes, _index = load_nodes(conn)
        version_row = conn.execute(
            "SELECT value FROM v4_meta WHERE key='taxonomy_version'"
        ).fetchone()
    taxonomy_version = int(version_row[0]) if version_row else 1

    rows = []
    for file_key in REMAINING_KEYS:
        payload = json.loads((input_dir / f"{file_key}.json").read_text(encoding="utf-8"))
        if int(payload["taxonomy_version"]) != taxonomy_version:
            raise RuntimeError(
                f"{file_key}: input taxonomy {payload['taxonomy_version']} != DB {taxonomy_version}"
            )
        result = build_result(payload, nodes)
        result_path = result_dir / f"{file_key}.json"
        result_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        rows.append(
            {
                "file_key": file_key,
                "ctype": payload["ctype"],
                "lang": payload["lang"],
                "path": payload["path"],
                "item_count": len(result["items"]),
                "candidate_count": len(result["taxonomy_candidates"]),
                "source_count": len(result["source_coverage"]),
                "result_path": str(result_path),
            }
        )

    manifest = {
        "meta_schema_version": 4,
        "taxonomy_version": taxonomy_version,
        "schema_revision": "1R2",
        "batch": "V4-2 remaining nine pre-review",
        "count": len(rows),
        "items": rows,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report_path.write_text(
        render_report(rows, taxonomy_version=taxonomy_version),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "count": len(rows),
                "item_count": sum(row["item_count"] for row in rows),
                "candidate_count": sum(row["candidate_count"] for row in rows),
                "result_dir": str(result_dir),
                "manifest": str(manifest_path),
                "report": str(report_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
