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
) -> Tuple[Dict[str, object], int]:
    keywords = keywords or []
    db_path = out / "catalog.sqlite"
    if not db_path.exists():
        raise FileNotFoundError(f"catalog.sqlite not found: {db_path}")

    entries = load_term_dict()
    warnings: List[str] = []
    if entries is None:
        # Silent no-expansion would degrade recall without any signal (see brief §3.7).
        entries = []
        warnings.append("term_dict_not_found")
    expanded_query: Dict[str, List[str]] = {}

    with closing(sqlite3.connect(db_path)) as conn:
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

        if not candidate_keys:
            unsearchable = count_unsearchable(conn, ctype, lang, exclude_drafts)
            if unsearchable:
                warnings.append(f"unsearchable_docs:{unsearchable}")
            result = build_result(
                ctype,
                lang,
                keywords,
                expanded_query,
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

            results.append(
                {
                    "file_key": row["file_key"],
                    "path": row["path"],
                    "ctype": row["ctype"],
                    "lang": row["lang"],
                    "is_draft": row["is_draft"],
                    "version_hint": row["version_hint"],
                    "dup_group": row["dup_group"],
                    "dup_count": dup_counts.get(row["dup_group"], 1),
                    "dup_representative_reason": representative_reason(row),
                    "matched_terms": unique_matched_terms(details["matched_terms"]),
                    "score_breakdown": {
                        "exact_rank": all_exact_ranks.get(row["file_key"]),
                        "expanded_rank": all_expanded_ranks.get(row["file_key"]),
                        "rrf_score": round(score, 6),
                        "meta_filter_match": True,
                    },
                    "why": why,
                    "snippet": snippet,
                    "snippet_paras": snippet_paras,
                }
            )

        unsearchable = count_unsearchable(conn, ctype, lang, exclude_drafts)
        if unsearchable:
            warnings.append(f"unsearchable_docs:{unsearchable}")

    result = build_result(ctype, lang, keywords, expanded_query, results, total, total_files, warnings)
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
    parts = [f"[¶{row['para']}] {row['content'][:240]}" for row in rows]
    return "\n".join(parts), [row["para"] for row in rows]


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
    results: List[Dict[str, object]],
    total: int,
    total_files: int,
    warnings: List[str],
) -> Dict[str, object]:
    return {
        "query": {"type": ctype, "lang": lang, "kw": keywords, "expanded": expanded_query},
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
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
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
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for item in result["results"]:
            print(f"{item['file_key']} {item['path']} {item['snippet']}")
        if not result["results"]:
            print("No results")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
