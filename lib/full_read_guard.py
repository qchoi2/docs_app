"""Strong omission guard for purported full-read RW extractions.

The broad absence net is intentionally recall-oriented and therefore noisy.  This
module supplies a narrower signal: an explicit representation-section heading in
the contract text whose RW sub-domain has zero stored items.  A hit does not prove
that a representation exists (the extracted body can itself be incomplete), but it
does prove that ``body_status='complete'`` is unsafe.  Callers therefore downgrade
coverage to partial rather than inventing an item or an absence.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

from lib.normalize import normalize
from open_text import read_paragraphs


FULL_READ_MARKERS = {"full_read", "full-read", "fullread", "proofread", "정독"}

# Deliberately high-precision phrases.  They are matched only in short,
# heading-shaped paragraphs, not arbitrary prose.
RW_HEADING_PHRASES: Dict[str, tuple[str, ...]] = {
    "RW.TAX": (
        "tax matters", "taxes", "tax representations", "조세", "세금",
        "조세 관련 진술", "조세사항", "세무",
    ),
    "RW.ENVIRONMENT": (
        "environmental matters", "environment, safety and health",
        "environmental and health and safety matters",
        "compliance with environmental requirements", "environmental exposures",
        "environmental representations", "환경", "환경 관련 사항",
        "환경·안전", "환경 및 안전", "환경보건안전",
    ),
    "RW.LABOR": (
        "labor and employment matters", "employees; employee benefit matters",
        "employee matters", "employment matters", "labor matters",
        "노무", "근로관계", "임직원", "고용",
    ),
    "RW.IP": (
        "intellectual property", "intellectual property matters",
        "지식재산권", "지적재산권", "무체재산권",
    ),
    "RW.INSURANCE": ("insurance", "보험"),
    "RW.LITIGATION": (
        "litigation", "litigation; governmental orders", "legal proceedings",
        "소송", "분쟁", "소송 및 분쟁",
    ),
    "RW.CONTRACTS": ("material contracts", "contracts", "중요계약", "계약"),
    "RW.FINANCIAL": (
        "financial statements", "financial matters", "재무제표", "재무",
    ),
    "RW.ASSETS": ("assets", "title to assets", "자산", "자산의 소유권"),
    "RW.REAL_ESTATE": (
        "real property", "real estate", "부동산", "부동산 및 임대차",
    ),
    "RW.PERMITS": (
        "permits", "licenses and permits", "government approvals", "인허가",
    ),
    "RW.COMPLIANCE": (
        "compliance with laws", "compliance with applicable laws",
        "법률 준수", "법규 준수", "관련 법령 준수",
    ),
}

_PREFIX = re.compile(
    r"^\s*(?:(?:article|section|schedule|annex|exhibit)\s+[\w.\-()]+\s*[:.\-]?\s*"
    r"|(?:제\s*)?\d+(?:\.\d+)*(?:\s*조)?\s*[:.\-]?\s*)?",
    re.IGNORECASE,
)
_TRAILING_PAGE = re.compile(r"(?:[.\s·…]+\d+|\s+\d+)\s*$")


def _heading_body(text: str) -> Optional[str]:
    value = normalize(text).strip()
    if not value or len(value) > 180 or len(value.split()) > 22:
        return None
    value = _PREFIX.sub("", value).strip()
    value = _TRAILING_PAGE.sub("", value).strip().rstrip(".:;-").strip()
    return value.casefold() or None


def _structural_heading(text: str) -> bool:
    value = normalize(text).strip()
    return bool(
        re.match(
            r"^\s*(?:article|section|schedule|annex|exhibit)\s+[\w.\-()]+",
            value,
            re.IGNORECASE,
        )
        or re.match(r"^\s*(?:제\s*)?\d+(?:\.\d+)*(?:\s*조)\b", value)
        or _TRAILING_PAGE.search(value)
    )


def _representation_like(text: str) -> bool:
    value = normalize(text).strip().casefold()
    if not value or value in {".", "-", "—"}:
        return False
    if re.search(r"(?:^|[\"'])[\w\s-]+[\"']?\s+means\b|(?:이라|라)\s*함은|의미한다", value):
        return False
    if value.startswith(("no ", "there is no ", "there are no ", "neither ")):
        return True
    subjects = (
        "the company", "company has", "company is", "seller", "vendor",
        "target", "purchaser", "buyer", "대상회사", "매도인", "매수인",
        "양도인", "발행회사",
    )
    assertions = (
        " has ", " is ", " are ", " does ", " did ", " will ", " no ",
        "없", "아니", "준수", "보유", "납부", "제출", "취득", "위반",
    )
    return any(token in value for token in subjects) and any(
        token in value for token in assertions
    )


def explicit_rw_headings(
    out: Path, file_key: str, txt_path: Optional[str] = None
) -> Dict[str, List[dict]]:
    """Return explicit heading evidence grouped by two-segment RW sub-domain."""
    candidates: List[Path] = []
    if txt_path:
        p = Path(txt_path)
        candidates.append(p if p.is_absolute() else out / p)
    candidates.append(out / "txt" / f"{file_key}.txt")
    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        return {}

    paragraphs = read_paragraphs(path)
    found: Dict[str, List[dict]] = {}
    for index, (para, raw) in enumerate(paragraphs):
        body = _heading_body(raw)
        if body is None:
            continue
        for subdomain, phrases in RW_HEADING_PHRASES.items():
            if any(body == phrase or body.startswith(phrase + " ") for phrase in phrases):
                # A numbered/TOC heading is self-authenticating.  A bare heading
                # ("Taxes", "Insurance") must be followed by representation-like
                # prose; this excludes standalone definition labels.
                supported = _structural_heading(raw)
                if not supported:
                    for _next_para, next_raw in paragraphs[index + 1:index + 5]:
                        if normalize(next_raw).strip() in {"", ".", "-", "—"}:
                            continue
                        supported = _representation_like(next_raw)
                        break
                if not supported:
                    continue
                found.setdefault(subdomain, []).append(
                    {"para": int(para), "text": normalize(raw)[:180]}
                )
    return found


def stored_rw_subdomains(conn: sqlite3.Connection, file_key: str) -> set[str]:
    result = set()
    for (taxonomy_id,) in conn.execute(
        "SELECT taxonomy_id FROM v4_clause_item WHERE file_key=? AND family='RW'",
        (file_key,),
    ):
        parts = str(taxonomy_id).split(".")
        if len(parts) >= 2:
            result.add(".".join(parts[:2]))
    return result


def owner_not_rw_subdomains(out: Path, file_key: str) -> set[str]:
    """Return heading hits an owner verified are outside representations."""
    path = out.parent / "data" / "full_read_heading_owner_verdicts.json"
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    decisions = data.get(file_key, {})
    return {
        str(domain)
        for domain, decision in decisions.items()
        if isinstance(decision, dict) and decision.get("verdict") == "not_rw"
    }


def full_read_heading_omissions(
    conn: sqlite3.Connection, out: Path, file_key: str
) -> Dict[str, List[dict]]:
    """Explicit RW section headings whose sub-domain has no stored RW item."""
    row = conn.execute(
        "SELECT txt_path FROM files WHERE file_key=?", (file_key,)
    ).fetchone()
    headings = explicit_rw_headings(
        out, file_key, row[0] if row is not None else None
    )
    present = stored_rw_subdomains(conn, file_key)
    reviewed_not_rw = owner_not_rw_subdomains(out, file_key)
    return {
        domain: evidence
        for domain, evidence in headings.items()
        if domain not in present and domain not in reviewed_not_rw
    }
