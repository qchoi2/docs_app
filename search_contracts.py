from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import yaml

from classify_version import resolve_version_filter, version_label
from lib.console import configure_utf8_stdio
from lib.normalize import normalize


TERM_DICT_PATHS = (Path("data/term_dict.yaml"), Path(".docs/term_dict.yaml"))
SCRIPT_DIR = Path(__file__).resolve().parent
RRF_K = 60


@dataclass
class TermEntry:
    canonical: str
    variants: List[Tuple[str, str]]
    strength: str = "normal"
    avoid: List[str] = None


def find_term_dict(start: Optional[Path] = None) -> Optional[Path]:
    """Look for term_dict.yaml under cwd first, then next to this script."""
    bases = []
    if start is not None:
        bases.append(start)
    bases.extend([Path.cwd(), SCRIPT_DIR])
    for base in bases:
        for candidate in TERM_DICT_PATHS:
            path = base / candidate
            if path.exists():
                return path
    return None


def load_term_dict(start: Optional[Path] = None) -> Optional[List[TermEntry]]:
    """Return term entries, or None when no term_dict.yaml could be found."""
    selected = find_term_dict(start)
    if selected is None:
        return None

    data = yaml.safe_load(selected.read_text(encoding="utf-8")) or {}
    entries = []
    for item in data.get("terms", []):
        variants = []
        canonical = str(item.get("canonical", ""))
        if canonical:
            variants.append((canonical, "strict"))
        for value in item.get("ko", []) or []:
            variants.append((str(value), "normal"))
        for value in item.get("en", []) or []:
            variants.append((str(value), "normal"))
        entries.append(
            TermEntry(
                canonical=canonical,
                variants=variants,
                strength=str(item.get("expansion_strength", "normal")),
                avoid=[str(value) for value in item.get("avoid_expanding_to", []) or []],
            )
        )
    return entries


def strength_allowed(term_strength: str, mode: str) -> bool:
    order = {"strict": 0, "normal": 1, "broad": 2}
    return order.get(term_strength, 1) <= order.get(mode, 1)


def find_term_entry(keyword: str, entries: Sequence[TermEntry]) -> Optional[TermEntry]:
    lowered = normalize(keyword).lower()
    for entry in entries:
        if any(lowered == normalize(variant).lower() for variant, _ in entry.variants):
            return entry
    return None


def resolve_clause_tag(tag: str, entries: Sequence[TermEntry]) -> str:
    lowered = normalize(tag).casefold()
    for entry in entries:
        if any(lowered == normalize(variant).casefold() for variant, _ in entry.variants):
            return entry.canonical
    return normalize(tag)


def expand_keyword(keyword: str, entries: Sequence[TermEntry], mode: str, no_expand: bool) -> List[Dict[str, str]]:
    original = normalize(keyword)
    matched_entry = find_term_entry(original, entries)
    exact_canonical = matched_entry.canonical if matched_entry else ""
    terms = [{"term": original, "canonical": exact_canonical, "source": "exact"}]
    if no_expand:
        return terms

    lowered = original.lower()
    seen = {lowered}
    for entry in entries:
        if not strength_allowed(entry.strength, mode):
            continue
        if entry is not matched_entry and not any(lowered == normalize(variant).lower() for variant, _ in entry.variants):
            continue
        avoid = {normalize(value).lower() for value in entry.avoid}
        for variant, variant_strength in entry.variants:
            normalized = normalize(variant)
            key = normalized.lower()
            if not normalized or key in seen or key in avoid:
                continue
            if mode == "strict" and variant_strength != "strict":
                continue
            terms.append({"term": normalized, "canonical": entry.canonical, "source": "expanded"})
            seen.add(key)
    return terms


def escape_fts_phrase(term: str) -> str:
    return '"' + term.replace('"', '""') + '"'


def is_short_term(term: str) -> bool:
    return len(term) < 3


def like_pattern(term: str) -> str:
    escaped = term.replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def run_term_search(conn: sqlite3.Connection, term: str) -> Tuple[List[Tuple[str, int, str]], bool]:
    if is_short_term(term):
        rows = conn.execute(
            """
            SELECT file_key, para, content
            FROM fts
            WHERE content LIKE ? ESCAPE '\\'
            ORDER BY rank
            """,
            (like_pattern(term),),
        ).fetchall()
        return rows, True

    rows = conn.execute(
        """
        SELECT file_key, para, content
        FROM fts
        WHERE fts MATCH ?
        ORDER BY rank
        """,
        (escape_fts_phrase(term),),
    ).fetchall()
    return rows, False


def reciprocal_rank(rank: int, weight: float = 1.0) -> float:
    return weight / (RRF_K + rank)


def connect_search_db(db_path: Path, read_only: bool = False) -> sqlite3.Connection:
    """Open the catalog. read_only=True uses a short-lived mode=ro connection
    (BACKEND_REVIEW_PC §2.4: searches must not take a writer slot)."""
    if read_only:
        conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def search_contracts(
    out: Path,
    ctype: Optional[str] = None,
    lang: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    limit: int = 20,
    context: int = 1,
    expand: str = "normal",
    no_expand: bool = False,
    exclude_drafts: bool = False,
    show_duplicates: bool = False,
    read_only: bool = False,
    version: Optional[object] = None,
    clause: Optional[str] = None,
    clause_present: bool = False,
    clause_absent: bool = False,
    party_name: Optional[str] = None,
    party_role: Optional[str] = None,
    payment_method: Optional[str] = None,
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    cap_pct_min: Optional[float] = None,
    cap_pct_max: Optional[float] = None,
    survival_months_min: Optional[int] = None,
    survival_months_max: Optional[int] = None,
    governing_law: Optional[str] = None,
    forum: Optional[str] = None,
) -> Tuple[Dict[str, object], int]:
    keywords = keywords or []
    version_roles = resolve_version_filter(version)
    db_path = out / "catalog.sqlite"
    if not db_path.exists():
        raise FileNotFoundError(f"catalog.sqlite not found: {db_path}")

    entries = load_term_dict()
    warnings: List[str] = []
    if entries is None:
        # Silent no-expansion would degrade recall without any signal (see brief §3.7).
        entries = []
        warnings.append("term_dict_not_found")
    if clause_present and clause_absent:
        raise ValueError("--present and --absent cannot be used together")
    expanded_query: Dict[str, List[str]] = {}
    clause_tag = resolve_clause_tag(clause, entries) if clause else None
    clause_mode = "absent" if clause_tag and clause_absent else "present" if clause_tag else None
    clause_filter_info: Optional[Dict[str, object]] = None
    structured_filters = {
        "party_name": party_name,
        "party_role": party_role,
        "payment_method": payment_method,
        "amount_min": amount_min,
        "amount_max": amount_max,
        "cap_pct_min": cap_pct_min,
        "cap_pct_max": cap_pct_max,
        "survival_months_min": survival_months_min,
        "survival_months_max": survival_months_max,
        "governing_law": governing_law,
        "forum": forum,
    }
    structured_filters = {key: value for key, value in structured_filters.items() if value is not None and value != ""}
    validate_structured_filter_ranges(structured_filters)
    structured_filter_info: Optional[Dict[str, object]] = None

    with closing(connect_search_db(db_path, read_only)) as conn:
        conn.row_factory = sqlite3.Row
        per_kw_scores = []
        per_file_details: Dict[str, Dict[str, object]] = {}
        all_exact_ranks: Dict[str, int] = {}
        all_expanded_ranks: Dict[str, int] = {}

        for keyword in keywords:
            terms = expand_keyword(keyword, entries, expand, no_expand)
            expanded_query[keyword] = [term["term"] for term in terms if term["source"] == "expanded"]
            kw_scores: Dict[str, float] = {}
            source_best_ranks: Dict[str, Dict[str, int]] = {"exact": {}, "expanded": {}}

            for term_info in terms:
                term = term_info["term"]
                if not term:
                    continue
                rows, used_like = run_term_search(conn, term)
                if used_like:
                    warning = f"short_term_fallback:{term}"
                    if warning not in warnings:
                        warnings.append(warning)
                file_rank_seen = set()
                for rank, row in enumerate(rows, start=1):
                    file_key = row["file_key"]
                    if file_key not in file_rank_seen:
                        source = term_info["source"]
                        best_ranks = source_best_ranks[source]
                        best_ranks[file_key] = min(best_ranks.get(file_key, rank), rank)
                        file_rank_seen.add(file_key)
                        if term_info["source"] == "exact":
                            all_exact_ranks[file_key] = min(all_exact_ranks.get(file_key, rank), rank)
                        else:
                            all_expanded_ranks[file_key] = min(all_expanded_ranks.get(file_key, rank), rank)

                    details = per_file_details.setdefault(
                        file_key,
                        {"matched_terms": [], "snippet_candidates": []},
                    )
                    details["matched_terms"].append(
                        {
                            "term": term,
                            "canonical": term_info.get("canonical") or "",
                            "para": row["para"],
                        }
                    )
                    details["snippet_candidates"].append((row["para"], row["content"]))
            for source, best_ranks in source_best_ranks.items():
                weight = 2.0 if source == "exact" else 1.0
                for file_key, rank in best_ranks.items():
                    kw_scores[file_key] = kw_scores.get(file_key, 0.0) + reciprocal_rank(rank, weight)
            per_kw_scores.append(kw_scores)

        if keywords:
            candidate_keys = set(per_kw_scores[0].keys()) if per_kw_scores else set()
            for kw_scores in per_kw_scores[1:]:
                candidate_keys &= set(kw_scores.keys())
        else:
            rows = conn.execute("SELECT file_key FROM files WHERE status = 'ok'").fetchall()
            candidate_keys = {row["file_key"] for row in rows}

        clause_filter_info = build_clause_filter_info(conn, candidate_keys, clause_tag, clause_mode)
        if clause_filter_info is not None:
            candidate_keys &= set(clause_filter_info["matched_file_keys"])
        structured_filter_info = build_structured_filter_info(conn, candidate_keys, structured_filters)
        if structured_filter_info is not None:
            candidate_keys &= set(structured_filter_info["matched_file_keys"])

        if not candidate_keys:
            unsearchable = count_unsearchable(conn, ctype, lang, exclude_drafts)
            if unsearchable:
                warnings.append(f"unsearchable_docs:{unsearchable}")
            result = build_result(
                ctype,
                lang,
                keywords,
                expanded_query,
                clause_filter_info,
                structured_filter_info,
                [],
                0,
                0,
                warnings,
            )
            log_query(out, result, expand, warnings)
            return result, 0

        placeholders = ",".join("?" for _ in candidate_keys)
        params: List[object] = list(candidate_keys)
        filters = [f"file_key IN ({placeholders})", "status = 'ok'"]
        if ctype:
            filters.append("ctype = ?")
            params.append(ctype)
        if lang:
            filters.append("lang = ?")
            params.append(lang)
        if exclude_drafts:
            filters.append("(is_draft IS NULL OR is_draft != 1)")
        if version_roles:
            filters.append(
                "version_role IN (%s)" % ",".join("?" for _ in version_roles)
            )
            params.extend(version_roles)
        sql = f"SELECT * FROM files WHERE {' AND '.join(filters)}"
        file_rows = conn.execute(sql, params).fetchall()

        scored_rows = []
        for row in file_rows:
            file_key = row["file_key"]
            score = sum(scores.get(file_key, 0.0) for scores in per_kw_scores) if keywords else 0.0
            scored_rows.append((score, row))

        scored_rows.sort(key=lambda item: (-item[0], representative_sort_key(item[1])))
        total_files = len(scored_rows)
        selected_rows = apply_dedup(scored_rows, show_duplicates)
        total = len(selected_rows)
        selected_rows = selected_rows[:limit]

        dup_counts = duplicate_counts(conn)
        clause_evidence = load_clause_evidence(conn, [row["file_key"] for _score, row in selected_rows], clause_tag)
        structured_evidence = load_structured_evidence(
            structured_filter_info,
            [row["file_key"] for _score, row in selected_rows],
        )
        results = []
        for score, row in selected_rows:
            details = per_file_details.get(row["file_key"], {"matched_terms": [], "snippet_candidates": []})
            snippet, snippet_paras = build_snippet(conn, row["file_key"], details["snippet_candidates"], context)
            why = []
            if all_exact_ranks.get(row["file_key"]) is not None:
                why.append("원질의 직접 매칭")
            if all_expanded_ranks.get(row["file_key"]) is not None:
                why.append("동의어 확장 매칭")
            if ctype and row["ctype"] == ctype:
                why.append(f"{ctype} 유형 필터 일치")
            if lang and row["lang"] == lang:
                why.append(f"{lang} 언어 필터 일치")
            if version_roles and row["version_role"] in version_roles:
                why.append(f"{version_label(row['version_role'])} 버전 필터 일치")
            if clause_tag:
                why.append(f"{clause_tag} 조항 {clause_mode}")
            if structured_filters:
                why.append("T3 v3 구조화 조건 일치")

            result_item = {
                "file_key": row["file_key"],
                "path": row["path"],
                "ctype": row["ctype"],
                "lang": row["lang"],
                "is_draft": row["is_draft"],
                "version_hint": row["version_hint"],
                "version_role": row["version_role"],
                "version_label": version_label(row["version_role"]),
                "dup_group": row["dup_group"],
                "dup_count": dup_counts.get(row["dup_group"], 1),
                "dup_representative_reason": representative_reason(row),
                "matched_terms": unique_matched_terms(details["matched_terms"]),
                "score_breakdown": {
                    "exact_rank": all_exact_ranks.get(row["file_key"]),
                    "expanded_rank": all_expanded_ranks.get(row["file_key"]),
                    "rrf_score": round(score, 6),
                    "meta_filter_match": True if (ctype or lang) else None,
                },
                "why": why,
                "snippet": snippet,
                "snippet_paras": snippet_paras,
            }
            if clause_tag:
                result_item["clause"] = clause_evidence.get(row["file_key"], {})
            if structured_filters:
                result_item["structured"] = structured_evidence.get(row["file_key"], {})
            results.append(result_item)

        unsearchable = count_unsearchable(conn, ctype, lang, exclude_drafts)
        if unsearchable:
            warnings.append(f"unsearchable_docs:{unsearchable}")

    result = build_result(
        ctype,
        lang,
        keywords,
        expanded_query,
        clause_filter_info,
        structured_filter_info,
        results,
        total,
        total_files,
        warnings,
    )
    log_query(out, result, expand, warnings)
    return result, len(results)


def representative_sort_key(row: sqlite3.Row) -> Tuple[int, int, int, str, str]:
    is_draft = row["is_draft"]
    version = (row["version_hint"] or "").lower()
    finalish = any(token in version or token in row["path"].lower() for token in ["final", "signed", "clean", "체결", "서명"])
    return (
        1 if is_draft == 1 else 0,
        0 if finalish else 1,
        len(row["path"] or ""),
        row["filename"] or "",
        row["file_key"],
    )


def representative_reason(row: sqlite3.Row) -> str:
    if row["is_draft"] == 1:
        return "draft included"
    if row["version_hint"]:
        return f"version hint: {row['version_hint']}"
    return "final version preferred"


def apply_dedup(scored_rows: List[Tuple[float, sqlite3.Row]], show_duplicates: bool) -> List[Tuple[float, sqlite3.Row]]:
    if show_duplicates:
        return scored_rows
    grouped: Dict[str, List[Tuple[float, sqlite3.Row]]] = {}
    for item in scored_rows:
        dup_group = item[1]["dup_group"] or item[1]["file_key"]
        grouped.setdefault(dup_group, []).append(item)
    representatives = []
    for items in grouped.values():
        representatives.append(sorted(items, key=lambda item: (-item[0], representative_sort_key(item[1])))[0])
    return sorted(representatives, key=lambda item: (-item[0], representative_sort_key(item[1])))


def rows_for_clause(
    conn: sqlite3.Connection,
    candidate_keys: Sequence[str],
    clause_tag: str,
    present: Optional[bool] = None,
) -> List[sqlite3.Row]:
    if not candidate_keys:
        return []
    placeholders = ",".join("?" for _ in candidate_keys)
    params: List[object] = list(candidate_keys)
    filters = [
        "dm.file_key IN (%s)" % placeholders,
        "je.key = ?",
    ]
    params.append(clause_tag)
    if present is not None:
        filters.append("json_extract(je.value, '$.present') = ?")
        params.append(1 if present else 0)
    return conn.execute(
        """
        SELECT dm.file_key, dm.confidence, je.key AS tag, je.value AS clause_json
        FROM doc_meta dm, json_each(dm.clause_map_json) AS je
        WHERE %s
        """ % " AND ".join(filters),
        params,
    ).fetchall()


def _clause_evidence_from_row(row: sqlite3.Row, status: str) -> Dict[str, object]:
    value = json.loads(row["clause_json"])
    if not isinstance(value, dict):
        value = {}
    return {
        "tag": row["tag"],
        "status": status,
        "present": value.get("present"),
        "loc_start": value.get("loc_start"),
        "loc_end": value.get("loc_end"),
        "summary": value.get("summary"),
        "confidence": row["confidence"],
    }


def build_clause_filter_info(
    conn: sqlite3.Connection,
    candidate_keys: Sequence[str],
    clause_tag: Optional[str],
    clause_mode: Optional[str],
) -> Optional[Dict[str, object]]:
    if not clause_tag or not clause_mode:
        return None

    candidate_set = set(candidate_keys)
    evaluated_rows = rows_for_clause(conn, sorted(candidate_set), clause_tag, None)
    evaluated_keys = {row["file_key"] for row in evaluated_rows}
    unevaluated = sorted(candidate_set - evaluated_keys)

    if clause_mode == "present":
        present_rows = rows_for_clause(conn, sorted(candidate_set), clause_tag, True)
        matched = sorted({row["file_key"] for row in present_rows})
        return {
            "tag": clause_tag,
            "mode": clause_mode,
            "matched_file_keys": matched,
            "needs_review": [
                {"file_key": key, "reason": "미평가"}
                for key in unevaluated
            ],
        }

    absent_rows = rows_for_clause(conn, sorted(candidate_set), clause_tag, False)
    matched = sorted({row["file_key"] for row in absent_rows if row["confidence"] != "low"})
    needs_review = [
        {"file_key": row["file_key"], "reason": "confidence=low"}
        for row in absent_rows
        if row["confidence"] == "low"
    ]
    needs_review.extend({"file_key": key, "reason": "미평가"} for key in unevaluated)
    needs_review.sort(key=lambda item: (str(item["reason"]), str(item["file_key"])))
    return {
        "tag": clause_tag,
        "mode": clause_mode,
        "matched_file_keys": matched,
        "needs_review": needs_review,
    }


def load_clause_evidence(
    conn: sqlite3.Connection,
    file_keys: Sequence[str],
    clause_tag: Optional[str],
) -> Dict[str, Dict[str, object]]:
    if not clause_tag or not file_keys:
        return {}
    rows = rows_for_clause(conn, file_keys, clause_tag, None)
    evidence = {}
    for row in rows:
        value = json.loads(row["clause_json"])
        if not isinstance(value, dict):
            value = {}
        status = "present" if value.get("present") is True else "absent" if value.get("present") is False else "unknown"
        evidence[row["file_key"]] = _clause_evidence_from_row(row, status)
    return evidence


def validate_structured_filter_ranges(filters: Dict[str, object]) -> None:
    for low_key, high_key in (
        ("amount_min", "amount_max"),
        ("cap_pct_min", "cap_pct_max"),
        ("survival_months_min", "survival_months_max"),
    ):
        low = filters.get(low_key)
        high = filters.get(high_key)
        for key, value in ((low_key, low), (high_key, high)):
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
                raise ValueError("%s must be numeric" % key)
            if value is not None and value < 0:
                raise ValueError("%s must not be negative" % key)
        if low is not None and high is not None and low > high:
            raise ValueError("%s must not exceed %s" % (low_key, high_key))


def _json_object(raw: object) -> Dict[str, object]:
    if not raw:
        return {}
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _contains_text(value: object, query: str) -> bool:
    if value is None:
        return False
    return normalize(query).casefold() in normalize(str(value)).casefold()


def _number_in_range(value: object, low: Optional[float], high: Optional[float]) -> Optional[bool]:
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if low is not None and value < low:
        return False
    if high is not None and value > high:
        return False
    return True


def _match_structured_row(row: sqlite3.Row, filters: Dict[str, object]) -> Tuple[Optional[bool], Dict[str, object]]:
    if int(row["meta_schema_version"] or 0) < 3:
        return None, {}
    parties = _json_object(row["parties_json"])
    consideration = _json_object(row["consideration_json"])
    clause_map = _json_object(row["clause_map_json"])
    evidence: Dict[str, object] = {"meta_schema_version": int(row["meta_schema_version"]), "confidence": row["confidence"]}

    party_name = filters.get("party_name")
    party_role = filters.get("party_role")
    if party_name is not None or party_role is not None:
        if parties.get("evaluated") is not True or not isinstance(parties.get("items"), list):
            return None, evidence
        matching_parties = []
        for item in parties["items"]:
            if not isinstance(item, dict):
                continue
            if party_name is not None and not _contains_text(item.get("name"), str(party_name)):
                continue
            if party_role is not None and not _contains_text(item.get("role"), str(party_role)):
                continue
            matching_parties.append(item)
        if not matching_parties:
            return False, evidence
        evidence["parties"] = matching_parties[:5]

    if any(key in filters for key in ("payment_method", "amount_min", "amount_max")):
        if consideration.get("evaluated") is not True:
            return None, evidence
        method = filters.get("payment_method")
        if method is not None:
            methods = consideration.get("payment_methods")
            if not isinstance(methods, list):
                return None, evidence
            if not any(_contains_text(item, str(method)) for item in methods):
                return False, evidence
        amount_match = _number_in_range(
            consideration.get("amount_value"),
            filters.get("amount_min"),
            filters.get("amount_max"),
        )
        if any(key in filters for key in ("amount_min", "amount_max")):
            if amount_match is None:
                return None, evidence
            if amount_match is False:
                return False, evidence
        evidence["consideration"] = consideration

    if any(key in filters for key in ("cap_pct_min", "cap_pct_max")):
        indemnity = clause_map.get("손해배상")
        if not isinstance(indemnity, dict) or indemnity.get("present") is not True:
            return None, evidence
        normalized_values = indemnity.get("normalized")
        if not isinstance(normalized_values, dict):
            return None, evidence
        matched = _number_in_range(
            normalized_values.get("cap_pct_of_price"),
            filters.get("cap_pct_min"),
            filters.get("cap_pct_max"),
        )
        if matched is None:
            return None, evidence
        if matched is False:
            return False, evidence
        evidence["손해배상"] = indemnity

    if any(key in filters for key in ("survival_months_min", "survival_months_max")):
        source = None
        months = None
        for tag in ("진술보장", "손해배상"):
            clause = clause_map.get(tag)
            normalized_values = clause.get("normalized") if isinstance(clause, dict) else None
            if isinstance(normalized_values, dict) and normalized_values.get("survival_months") is not None:
                source = clause
                months = normalized_values.get("survival_months")
                break
        matched = _number_in_range(
            months,
            filters.get("survival_months_min"),
            filters.get("survival_months_max"),
        )
        if matched is None:
            return None, evidence
        if matched is False:
            return False, evidence
        evidence["존속기간"] = source

    law = filters.get("governing_law")
    if law is not None:
        clause = clause_map.get("준거법")
        normalized_values = clause.get("normalized") if isinstance(clause, dict) else None
        if not isinstance(normalized_values, dict) or normalized_values.get("law") is None:
            return None, evidence
        if not _contains_text(normalized_values.get("law"), str(law)):
            return False, evidence
        evidence["준거법"] = clause

    forum = filters.get("forum")
    if forum is not None:
        clause = clause_map.get("분쟁해결")
        normalized_values = clause.get("normalized") if isinstance(clause, dict) else None
        if not isinstance(normalized_values, dict):
            return None, evidence
        values = [normalized_values.get("forum"), normalized_values.get("institution_or_court")]
        if not any(_contains_text(value, str(forum)) for value in values if value is not None):
            if not any(value is not None for value in values):
                return None, evidence
            return False, evidence
        evidence["분쟁해결"] = clause

    return True, evidence


def build_structured_filter_info(
    conn: sqlite3.Connection,
    candidate_keys: Sequence[str],
    filters: Dict[str, object],
) -> Optional[Dict[str, object]]:
    if not filters:
        return None
    if not candidate_keys:
        return {
            "filters": filters,
            "matched_file_keys": [],
            "needs_review": [],
            "needs_review_count": 0,
            "evidence": {},
        }
    placeholders = ",".join("?" for _ in candidate_keys)
    rows = conn.execute(
        """
        SELECT f.file_key, dm.meta_schema_version, dm.parties_json,
               dm.consideration_json, dm.clause_map_json, dm.confidence
        FROM files f
        LEFT JOIN doc_meta dm ON dm.file_key=f.file_key
        WHERE f.file_key IN (%s)
        """ % placeholders,
        list(candidate_keys),
    ).fetchall()
    matched: List[str] = []
    needs_review: List[Dict[str, str]] = []
    evidence: Dict[str, Dict[str, object]] = {}
    for row in rows:
        status, row_evidence = _match_structured_row(row, filters)
        if status is True:
            matched.append(row["file_key"])
            evidence[row["file_key"]] = row_evidence
        elif status is None:
            needs_review.append({"file_key": row["file_key"], "reason": "T3 v3 구조화 값 미평가"})
    matched.sort()
    needs_review.sort(key=lambda item: item["file_key"])
    return {
        "filters": filters,
        "matched_file_keys": matched,
        "needs_review": needs_review[:100],
        "needs_review_count": len(needs_review),
        "needs_review_truncated": len(needs_review) > 100,
        "evidence": evidence,
    }


def load_structured_evidence(
    structured_filter_info: Optional[Dict[str, object]],
    file_keys: Sequence[str],
) -> Dict[str, Dict[str, object]]:
    if structured_filter_info is None:
        return {}
    evidence = structured_filter_info.get("evidence")
    if not isinstance(evidence, dict):
        return {}
    return {key: evidence.get(key, {}) for key in file_keys}


def duplicate_counts(conn: sqlite3.Connection) -> Dict[str, int]:
    rows = conn.execute(
        """
        SELECT dup_group, COUNT(*)
        FROM files
        WHERE status != 'missing'
        GROUP BY dup_group
        """
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def unique_matched_terms(items: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    seen = set()
    unique = []
    for item in items:
        key = (item["term"], item["canonical"], item["para"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[:20]


def build_snippet(
    conn: sqlite3.Connection,
    file_key: str,
    candidates: List[Tuple[int, str]],
    context: int,
) -> Tuple[str, List[int]]:
    if not candidates:
        return "", []
    para, _content = sorted(candidates, key=lambda item: item[0])[0]
    context = max(context, 0)
    start = max(1, para - context)
    end = para + context
    rows = conn.execute(
        """
        SELECT para, content
        FROM fts
        WHERE file_key = ? AND para BETWEEN ? AND ?
        ORDER BY para
        """,
        (file_key, start, end),
    ).fetchall()
    if not rows:
        return "", []
    # Brief §9 default: about 240 chars in total, centered on the matched paragraph.
    budget = 240
    ordered = sorted(rows, key=lambda row: (abs(row["para"] - para), row["para"]))
    included = []
    for row in ordered:
        if budget <= 0:
            break
        text = row["content"][:budget]
        included.append((row["para"], text))
        budget -= len(text)
    included.sort(key=lambda item: item[0])
    parts = [f"[¶{number}] {text}" for number, text in included]
    return "\n".join(parts), [number for number, _ in included]


def count_unsearchable(conn: sqlite3.Connection, ctype: Optional[str], lang: Optional[str], exclude_drafts: bool) -> int:
    filters = ["status IN ('empty', 'error')"]
    params: List[object] = []
    if ctype:
        filters.append("ctype = ?")
        params.append(ctype)
    if lang:
        filters.append("lang = ?")
        params.append(lang)
    if exclude_drafts:
        filters.append("(is_draft IS NULL OR is_draft != 1)")
    return conn.execute(f"SELECT COUNT(*) FROM files WHERE {' AND '.join(filters)}", params).fetchone()[0]


def build_result(
    ctype: Optional[str],
    lang: Optional[str],
    keywords: List[str],
    expanded_query: Dict[str, List[str]],
    clause_filter: Optional[Dict[str, object]],
    structured_filter: Optional[Dict[str, object]],
    results: List[Dict[str, object]],
    total: int,
    total_files: int,
    warnings: List[str],
) -> Dict[str, object]:
    public_structured = None
    if structured_filter is not None:
        public_structured = {
            key: value
            for key, value in structured_filter.items()
            if key != "evidence" and key != "matched_file_keys"
        }
    return {
        "query": {
            "type": ctype,
            "lang": lang,
            "kw": keywords,
            "expanded": expanded_query,
            "clause": clause_filter,
            "structured": public_structured,
        },
        "total": total,
        "total_files": total_files,
        "results": results,
        "warnings": warnings,
    }


def log_query(out: Path, result: Dict[str, object], expand_mode: str, warnings: List[str]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "query": result["query"],
        "filters": {"type": result["query"]["type"], "lang": result["query"]["lang"]},
        "expand_mode": expand_mode,
        "result_count": result["total"],
        "warnings": warnings,
    }
    with (out / "query_log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search indexed contracts.")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--type", dest="ctype")
    parser.add_argument("--lang")
    parser.add_argument("--kw", action="append", default=[])
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--context", type=int, default=1)
    parser.add_argument("--expand", choices=["strict", "normal", "broad"], default="normal")
    parser.add_argument("--no-expand", action="store_true")
    parser.add_argument("--exclude-drafts", action="store_true")
    parser.add_argument("--exclude-draft", action="store_true")
    parser.add_argument("--show-duplicates", action="store_true")
    parser.add_argument("--version",
                        help="버전 필터: role key(execution/buyer_draft/...) 또는 "
                             "한글 라벨(체결본/매수인 초안/...). 콤마로 다중 지정.")
    parser.add_argument("--clause")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--present", action="store_true")
    group.add_argument("--absent", action="store_true")
    parser.add_argument("--party-name")
    parser.add_argument("--party-role")
    parser.add_argument("--payment-method")
    parser.add_argument("--amount-min", type=float)
    parser.add_argument("--amount-max", type=float)
    parser.add_argument("--cap-pct-min", type=float)
    parser.add_argument("--cap-pct-max", type=float)
    parser.add_argument("--survival-months-min", type=int)
    parser.add_argument("--survival-months-max", type=int)
    parser.add_argument("--governing-law")
    parser.add_argument("--forum")
    parser.add_argument("--item", help="V4 atomic taxonomy ID or canonical label")
    parser.add_argument("--item-absent", action="store_true",
                        help="Return only coverage-proved V4 absence; separate needs_review")
    parser.add_argument("--polarity",
                        choices=["affirmative", "negative", "none_exist", "not_applicable"])
    parser.add_argument("--subject", help="V4 atomic subject role")
    parser.add_argument("--time", dest="effective_time", help="V4 effective-time label")
    parser.add_argument("--exact-item", action="store_true",
                        help="Do not include descendants of the selected V4 node")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.item:
            from v4_search import search_clause_absence, search_clause_items

            item_common = {
                "polarity": args.polarity,
                "ctype": args.ctype,
                "lang": args.lang,
                "version": args.version,
                "include_descendants": not args.exact_item,
                "show_duplicates": args.show_duplicates,
                "limit": args.limit,
            }
            if args.item_absent:
                result = search_clause_absence(args.out, args.item, **item_common)
                result_count = result["confirmed_absent_count"]
            else:
                result = search_clause_items(
                    args.out,
                    args.item,
                    subject=args.subject,
                    effective_time=args.effective_time,
                    **item_common,
                )
                result_count = result["total_items"]
        else:
            result, result_count = search_contracts(
                args.out,
                ctype=args.ctype,
                lang=args.lang,
                keywords=args.kw,
                limit=args.limit,
                context=args.context,
                expand=args.expand,
                no_expand=args.no_expand,
                exclude_drafts=args.exclude_drafts or args.exclude_draft,
                show_duplicates=args.show_duplicates,
                version=args.version,
                clause=args.clause,
                clause_present=args.present,
                clause_absent=args.absent,
                party_name=args.party_name,
                party_role=args.party_role,
                payment_method=args.payment_method,
                amount_min=args.amount_min,
                amount_max=args.amount_max,
                cap_pct_min=args.cap_pct_min,
                cap_pct_max=args.cap_pct_max,
                survival_months_min=args.survival_months_min,
                survival_months_max=args.survival_months_max,
                governing_law=args.governing_law,
                forum=args.forum,
            )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    elif args.item and args.item_absent:
        print(
            f"{result['query']['taxonomy_id']}: "
            f"confirmed_absent={result['confirmed_absent_count']} "
            f"needs_review={result['needs_review_count']}"
        )
        for item in result["confirmed_absent"]:
            print(f"{item['file_key']} confirmed_absent {item['path']}")
    elif args.item:
        for item in result["results"]:
            print(
                f"{item['file_key']} {item['item_ref']} {item['taxonomy_id']} "
                f"para {item['loc_start']}-{item['loc_end']} {item['proposition']}"
            )
        if not result["results"]:
            print("No results")
    else:
        for item in result["results"]:
            version = item.get("version_label") or item.get("version_role") or "-"
            print(f"{item['file_key']} [{version}] {item['path']} {item['snippet']}")
        if not result["results"]:
            print("No results")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
