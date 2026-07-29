"""Absolute (not pooled/relative) item-level recall over the full_read answer key.

Why this exists
---------------
`eval_v4_gate.py --pooled` measures *relative* recall: the pool is the union of
what the two arms return, so an item **neither** arm surfaces is structurally
invisible. The re-extraction batches left behind a genuine absolute answer key
for free: every `cs_index/{rw,pay}_reextract_results/<file_key>.json` carrying
`review_method: full_read` was produced by reading that document's family
article start to end, so per `store_rw_reextraction.py` it "reconstructs the
whole family and is authoritative". That is a complete item list for one
(document, family) pair — an absolute recall answer key.

Scope discipline
----------------
A document full-read for RW is authoritative **for RW only**. Its CP/COV/DEF/
PAY/REM items were never proofread, so scoring those families against it would
manufacture false misses. Every measurement here is keyed on (file_key, family)
and never leaves that boundary.

What "찾아내나" (a hit) means — stated in the report, because a sloppy
definition makes the number meaningless
---------------------------------------------------------------------------
Recall is measured **per answer-key item**, not per document. A search that
returns the right contract for the wrong reason has not found the item: the
user still has to read the contract, which is the cost V4 exists to remove.

An answer-key item G is *retrieved by path P at cutoff k* when P, driven only
by the item's **concept** (the taxonomy node's canonical label / aliases — what
a user actually types, never the row's own primary key), returns within its
first k results an object identified as G's clause by one of:

  ``verbatim_exact``       normalized verbatim equal
  ``verbatim_containment`` one normalized verbatim contains the other, and the
                           shorter side is distinctive (>=MIN_CONTAINMENT chars)
  ``loc_subdomain``        ¶ ranges overlap and the sub-domain matches

The rule that fired is counted, so the number is auditable.

Paths exercised — real entry points only, never a re-query of the tables
(measuring the DB against itself is the self-referential Gate B failure that
.docs/PLAN_REVIEW_20260727.md §① diagnosed):

  ``structured``  ``v4_search.search_clause_items(label)``            rank unit: item
  ``item_text``   ``v4_search.search_clause_items(family, text=...)`` rank unit: item
                  (the item-text filter exposed on the MCP tool)
  ``paragraph``   ``search_contracts.search_contracts(keywords=...)`` rank unit: document
  ``hybrid``      union of the three (V4_PLAN §8)

Rank sensitivity: recall is reported at several k, because a hit at rank 400 is
not a hit in practice. `structured`/`item_text` k counts items; `paragraph`
counts documents (that path is document-granular by construction), and its
paragraph-localized figure is a floor because `search_contracts` caps
`matched_terms` at 20 entries per document.

Read-only. Opens the catalog through the search modules' own `mode=ro` paths and
never writes to it.

Usage:
  python eval_absolute_recall.py --out cs_index [--report out.json]
                                 [--max-depth 2000] [--doc-depth 50]
                                 [--paragraph-terms 1] [--paths structured,item_text]
                                 [--diagnose 25] [--miss-sample 40]
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
import unicodedata
from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path

from lib.console import configure_utf8_stdio
from search_contracts import search_contracts
from v4_search import V4SearchError, connect_v4_ro, resolve_taxonomy, search_clause_items

# Mirrors store_rw_reextraction._FULL_READ_MARKERS / store_pay_reextraction.
# Kept as a literal (not an import) so a mid-edit store module cannot break the
# evaluator; tests/test_eval_absolute_recall.py asserts the two stay identical.
FULL_READ_MARKERS = {"full_read", "full-read", "fullread", "proofread", "정독"}

# (result directory, family it is authoritative for)
DEFAULT_SOURCES = (("rw_reextract_results", "RW"), ("pay_reextract_results", "PAY"))

PAGE = 500  # v4_search.MAX_LIMIT
ITEM_K = (10, 25, 50, 100, 250, 500, 1000)
DOC_K = (5, 10, 25, 50, 100, 200)
# Minimum normalized length for containment to identify a clause. Counted after
# punctuation/whitespace are stripped, so this is CJK syllables for Korean text:
# 8 syllables is a distinctive phrase, while "없음"(2) or "해당 없음"(4) are not.
MIN_CONTAINMENT = 8
MAX_TERMS = 3

_PUNCT = re.compile(r"[\s·.,;:!?()\[\]{}<>\"'`~\-–—_/\\|＂＇“”‘’]+")


# --------------------------------------------------------------------------
# ground truth
# --------------------------------------------------------------------------

def load_ground_truth(out: Path, sources=DEFAULT_SOURCES) -> list[dict]:
    """Answer-key documents: one entry per (file_key, family) full_read result."""
    docs: list[dict] = []
    for dirname, family in sources:
        directory = out / dirname
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
            except (ValueError, OSError):
                continue
            marker = str(data.get("review_method", "")).strip().lower()
            if marker not in FULL_READ_MARKERS:
                continue  # auto-extraction result: not an authoritative set
            raw_items = data.get("items") or []
            if not raw_items:
                continue  # store skips these ("skipped_no_items") — nothing to score
            file_key = str(data.get("file_key") or path.stem)
            items = []
            for index, item in enumerate(raw_items):
                items.append(
                    {
                        "gt_id": f"{file_key}:{family}:{index}",
                        "file_key": file_key,
                        "family": family,
                        "taxonomy_id": str(item.get("taxonomy_id") or ""),
                        "proposition": str(item.get("proposition") or ""),
                        "verbatim": str(item.get("verbatim") or ""),
                        "loc_start": _int(item.get("loc_start")),
                        "loc_end": _int(item.get("loc_end", item.get("loc_start"))),
                        "polarity": str(item.get("statement_polarity") or ""),
                    }
                )
            docs.append(
                {
                    "file_key": file_key,
                    "family": family,
                    "source": str(path),
                    "review_method": marker,
                    "items": items,
                }
            )
    return docs


def _int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


# item_ref prefix written by each store's `replace` mode — presence proves the
# answer key reached the index. INVENTORY ONLY: never used to score retrieval.
_STORE_PREFIX = {"RW": "RWRX", "PAY": "PAYRX"}


def annotate_docs(conn: sqlite3.Connection, docs: list[dict]) -> None:
    """Catalog metadata + whether the answer key was ever stored.

    The `stored` flag exists because re-extraction is in flight: a full_read
    result whose store has not run yet is a real miss for a user today, but it
    is a pipeline backlog, not a search defect. Reported separately so the two
    are never conflated.
    """
    for doc in docs:
        row = conn.execute(
            "SELECT ctype,lang,status FROM files WHERE file_key=?", (doc["file_key"],)
        ).fetchone()
        doc["ctype"] = str(row["ctype"]) if row else None
        doc["lang"] = str(row["lang"]) if row else None
        doc["status"] = str(row["status"]) if row else "not_in_catalog"
        prefix = _STORE_PREFIX.get(doc["family"], doc["family"])
        doc["stored_items"] = int(
            conn.execute(
                "SELECT COUNT(*) FROM v4_clause_item "
                "WHERE file_key=? AND family=? AND item_ref LIKE ?",
                (doc["file_key"], doc["family"], f"{prefix}-%"),
            ).fetchone()[0]
        )
        doc["answer_key_stored"] = doc["stored_items"] > 0


def inventory(docs: list[dict]) -> dict:
    by_family = Counter(doc["family"] for doc in docs)
    items_by_family = Counter()
    by_family_ctype = Counter()
    for doc in docs:
        items_by_family[doc["family"]] += len(doc["items"])
        by_family_ctype[(doc["family"], doc.get("ctype"))] += 1
    return {
        "documents": len(docs),
        "items": sum(len(doc["items"]) for doc in docs),
        "documents_by_family": dict(by_family),
        "items_by_family": dict(items_by_family),
        "documents_by_family_ctype": {
            f"{fam}/{ctype}": n for (fam, ctype), n in sorted(by_family_ctype.items())
        },
        "distinct_file_keys": len({doc["file_key"] for doc in docs}),
        "answer_keys_stored": sum(1 for doc in docs if doc.get("answer_key_stored")),
        "answer_keys_not_yet_stored": sum(
            1 for doc in docs if not doc.get("answer_key_stored")
        ),
        "items_in_unstored_answer_keys": sum(
            len(doc["items"]) for doc in docs if not doc.get("answer_key_stored")
        ),
        "note": "a document full-read for one family is an answer key for that family only",
    }


# --------------------------------------------------------------------------
# hit definition
# --------------------------------------------------------------------------

def normalize_text(value: str) -> str:
    """Fold width/case, drop whitespace and punctuation — verbatim survives
    re-quoting and the 2000-char store truncation, but not a real text change."""
    folded = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return _PUNCT.sub("", folded)


def subdomain(taxonomy_id: str) -> str:
    parts = str(taxonomy_id or "").split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else str(taxonomy_id or "")


def match_item(gt: dict, row: dict) -> str | None:
    """Return the rule that identifies `row` as the answer-key item, else None."""
    if str(row.get("file_key")) != gt["file_key"]:
        return None
    a = normalize_text(gt["verbatim"])
    b = normalize_text(row.get("verbatim"))
    if a and b:
        if a == b:
            return "verbatim_exact"
        if len(a) >= MIN_CONTAINMENT and len(b) >= MIN_CONTAINMENT and (a in b or b in a):
            return "verbatim_containment"
    ls, le = gt["loc_start"], gt["loc_end"]
    rs, re_ = _int(row.get("loc_start")), _int(row.get("loc_end"))
    if ls >= 0 and rs >= 0 and ls <= max(re_, rs) and rs <= max(le, ls):
        if subdomain(gt["taxonomy_id"]) == subdomain(str(row.get("taxonomy_id") or "")):
            return "loc_subdomain"
    return None


def paragraph_hit(gt: dict, paras: set[int]) -> bool:
    if gt["loc_start"] < 0:
        return False
    lo, hi = gt["loc_start"], max(gt["loc_end"], gt["loc_start"])
    return any(lo <= p <= hi for p in paras)


# --------------------------------------------------------------------------
# queries — concept in, real entry point out
# --------------------------------------------------------------------------

def concept_terms(conn: sqlite3.Connection, taxonomy_id: str, limit: int = MAX_TERMS) -> list[str]:
    """What a user types for this concept: canonical labels then aliases.

    Same convention as eval_v4_gate.aliases — very short terms make unusably
    broad keyword queries, so they are dropped.
    """
    row = conn.execute(
        "SELECT canonical_ko,canonical_en FROM v4_taxonomy_node WHERE taxonomy_id=?",
        (taxonomy_id,),
    ).fetchone()
    values = [str(row[0]), str(row[1])] if row else []
    values.extend(
        str(r[0])
        for r in conn.execute(
            "SELECT alias FROM v4_taxonomy_alias WHERE taxonomy_id=? ORDER BY alias_id",
            (taxonomy_id,),
        )
    )
    seen = list(dict.fromkeys(v.strip() for v in values if len(v.strip()) >= 3))
    return seen[:limit]


def _scan_items(pages, gt_items: list[dict], ranks: dict, rules: dict, path_name: str) -> bool:
    """Fold a page of results into first-hit ranks. True once everything is found."""
    wanted = {gt["gt_id"] for gt in gt_items} - set(ranks)
    if not wanted:
        return True
    by_file: dict[str, list[dict]] = defaultdict(list)
    for gt in gt_items:
        if gt["gt_id"] in wanted:
            by_file[gt["file_key"]].append(gt)
    for rank, row in pages:
        candidates = by_file.get(str(row.get("file_key")))
        if not candidates:
            continue
        for gt in candidates:
            if gt["gt_id"] in ranks:
                continue
            rule = match_item(gt, row)
            if rule:
                ranks[gt["gt_id"]] = rank
                rules[gt["gt_id"]] = f"{path_name}:{rule}"
        if len(ranks) >= len(gt_items):
            return True
    return False


def structured_ranks(out: Path, label: str, gt_items: list[dict], max_depth: int) -> dict:
    """search_clause_items driven by the concept label, paged to max_depth."""
    ranks: dict[str, int] = {}
    rules: dict[str, str] = {}
    offset = 0
    total = None
    exhausted = False
    error = None
    while offset < max_depth:
        try:
            page = search_clause_items(
                out, label, show_duplicates=True, limit=min(PAGE, max_depth - offset),
                offset=offset,
            )
        except V4SearchError as exc:
            error = str(exc)
            break
        total = int(page["total_items"])
        rows = page["results"]
        if _scan_items(((offset + i + 1, r) for i, r in enumerate(rows)), gt_items, ranks, rules,
                       "structured"):
            offset += len(rows)
            exhausted = offset >= total
            break
        offset += len(rows)
        if not page["has_more"] or not rows:
            exhausted = True
            break
    return {"ranks": ranks, "rules": rules, "total": total, "scanned": offset,
            "exhausted": exhausted, "error": error}


def item_text_ranks(out: Path, family: str, terms: list[str], gt_items: list[dict],
                    max_depth: int) -> dict:
    """search_clause_items' item-text filter over the family root, one query per
    term; a GT item takes its best (lowest) rank across terms."""
    ranks: dict[str, int] = {}
    rules: dict[str, str] = {}
    scanned = 0
    error = None
    for term in terms:
        term_ranks: dict[str, int] = {}
        term_rules: dict[str, str] = {}
        offset = 0
        while offset < max_depth:
            try:
                page = search_clause_items(
                    out, family, text=term, show_duplicates=True,
                    limit=min(PAGE, max_depth - offset), offset=offset,
                )
            except V4SearchError as exc:
                error = str(exc)
                break
            rows = page["results"]
            done = _scan_items(((offset + i + 1, r) for i, r in enumerate(rows)),
                               gt_items, term_ranks, term_rules, "item_text")
            offset += len(rows)
            scanned += len(rows)
            if done or not page["has_more"] or not rows:
                break
        for gt_id, rank in term_ranks.items():
            if rank < ranks.get(gt_id, 1 << 30):
                ranks[gt_id] = rank
                rules[gt_id] = term_rules[gt_id]
    return {"ranks": ranks, "rules": rules, "scanned": scanned, "error": error}


def paragraph_ranks(out: Path, terms: list[str], gt_items: list[dict], doc_depth: int) -> dict:
    """Legacy paragraph FTS (search_contracts) — document-granular.

    doc_ranks:  the contract came back at document rank r.
    para_ranks: additionally, a matched paragraph falls inside the item's ¶ range.
                A floor only: search_contracts caps matched_terms at 20 per doc.
    """
    wanted_files = {gt["file_key"] for gt in gt_items}
    doc_ranks: dict[str, int] = {}
    para_ranks: dict[str, int] = {}
    error = None
    for term in terms:
        try:
            result, _count = search_contracts(
                out, keywords=[term], limit=doc_depth, show_duplicates=True, read_only=True
            )
        except Exception as exc:  # a term can be invalid for the FTS tokenizer
            error = str(exc)[:200]
            continue
        for rank, row in enumerate(result.get("results", []), start=1):
            file_key = str(row.get("file_key"))
            if file_key not in wanted_files:
                continue
            paras = {
                _int(m.get("para")) for m in (row.get("matched_terms") or [])
            } | {_int(p) for p in (row.get("snippet_paras") or [])}
            for gt in gt_items:
                if gt["file_key"] != file_key:
                    continue
                if rank < doc_ranks.get(gt["gt_id"], 1 << 30):
                    doc_ranks[gt["gt_id"]] = rank
                if paragraph_hit(gt, paras) and rank < para_ranks.get(gt["gt_id"], 1 << 30):
                    para_ranks[gt["gt_id"]] = rank
    return {"doc_ranks": doc_ranks, "para_ranks": para_ranks, "error": error}


# --------------------------------------------------------------------------
# diagnosis of misses
# --------------------------------------------------------------------------

def diagnose(out: Path, gt: dict, limit: int = 25) -> dict:
    """Why did every path miss this item? Uses the same real entry point
    (item-text filter over the family) with a distinctive slice of the item's own
    verbatim — a diagnostic probe, deliberately not part of the measurement."""
    needle = " ".join(str(gt["verbatim"]).split())[:40]
    if len(needle) < MIN_CONTAINMENT:
        return {"diagnosis": "verbatim_too_short_to_probe"}
    try:
        page = search_clause_items(
            out, gt["family"], text=needle, show_duplicates=True, limit=limit
        )
    except V4SearchError as exc:
        return {"diagnosis": "probe_failed", "error": str(exc)}
    same_doc = [r for r in page["results"] if str(r.get("file_key")) == gt["file_key"]]
    if not same_doc:
        return {
            "diagnosis": "text_not_in_index",
            "detail": "no item in this family carries this verbatim for this document "
                      "— never stored, or the wording was rewritten on re-extraction",
            "probe_hits": page["total_items"],
        }
    stored = sorted({str(r.get("taxonomy_id")) for r in same_doc})
    if gt["taxonomy_id"] in stored:
        return {
            "diagnosis": "ranking_or_scope",
            "detail": "the item is indexed under the answer key's own taxonomy_id, so "
                      "the concept query did not reach it within max_depth",
            "stored_taxonomy_ids": stored,
        }
    return {
        "diagnosis": "taxonomy_mismatch",
        "detail": "stored under a different node than the proofread answer key asserts",
        "answer_key_taxonomy_id": gt["taxonomy_id"],
        "stored_taxonomy_ids": stored,
    }


# --------------------------------------------------------------------------
# evaluation
# --------------------------------------------------------------------------

def _recall_at(ranks: dict, total: int, grid) -> dict:
    return {f"@{k}": round(sum(1 for r in ranks.values() if r <= k) / total, 4)
            for k in grid} if total else {}


def _bucket(rows: list[dict], key) -> dict:
    grouped = defaultdict(list)
    for row in rows:
        grouped[key(row)].append(row)
    return grouped


def evaluate(out: Path, *, max_depth: int = 2000, doc_depth: int = 50,
             sources=DEFAULT_SOURCES, paths=("structured", "item_text", "paragraph"),
             diagnose_n: int = 25, miss_sample: int = 40,
             paragraph_terms: int = 1) -> dict:
    started = time.perf_counter()
    docs = load_ground_truth(out, sources)
    with closing(connect_v4_ro(out)) as conn:
        annotate_docs(conn, docs)
        gt_items: list[dict] = []
        for doc in docs:
            for item in doc["items"]:
                item["ctype"] = doc.get("ctype")
                item["lang"] = doc.get("lang")
                item["answer_key_stored"] = doc.get("answer_key_stored")
                gt_items.append(item)
        concepts: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for item in gt_items:
            concepts[(item["family"], item["taxonomy_id"])].append(item)
        term_cache = {
            key: concept_terms(conn, key[1]) for key in concepts
        }
        label_cache = {}
        for (family, taxonomy_id) in concepts:
            label = taxonomy_id
            try:
                node = resolve_taxonomy(conn, taxonomy_id)
                canonical = str(node["canonical_ko"] or "")
                # prefer the human label, but only when it resolves unambiguously
                if canonical:
                    resolve_taxonomy(conn, canonical)
                    label = canonical
            except V4SearchError:
                pass
            label_cache[(family, taxonomy_id)] = label

    ranks: dict[str, dict[str, int]] = {p: {} for p in paths}
    ranks["paragraph_doc"] = {}
    rules: dict[str, str] = {}
    concept_rows = []
    for (family, taxonomy_id), items in sorted(concepts.items()):
        terms = term_cache[(family, taxonomy_id)]
        label = label_cache[(family, taxonomy_id)]
        row = {"family": family, "taxonomy_id": taxonomy_id, "query_label": label,
               "query_terms": terms, "gt_items": len(items)}
        if "structured" in paths:
            res = structured_ranks(out, label, items, max_depth)
            ranks["structured"].update(res["ranks"])
            rules.update(res["rules"])
            row["structured"] = {"found": len(res["ranks"]), "population": res["total"],
                                 "scanned": res["scanned"], "exhausted": res["exhausted"],
                                 "error": res["error"]}
        if "item_text" in paths:
            res = item_text_ranks(out, family, terms, items, max_depth)
            for gt_id, rank in res["ranks"].items():
                ranks["item_text"][gt_id] = rank
            for gt_id, rule in res["rules"].items():
                rules.setdefault(gt_id, rule)
            row["item_text"] = {"found": len(res["ranks"]), "scanned": res["scanned"],
                                "error": res["error"]}
        if "paragraph" in paths:
            # the legacy FTS scan is the slowest arm by an order of magnitude,
            # so it runs on a capped term list (reported in query_terms).
            res = paragraph_ranks(out, terms[:paragraph_terms], items, doc_depth)
            ranks["paragraph"].update(res["para_ranks"])
            ranks["paragraph_doc"].update(res["doc_ranks"])
            row["paragraph"] = {"para_localized": len(res["para_ranks"]),
                                "document_level": len(res["doc_ranks"]),
                                "error": res["error"]}
        concept_rows.append(row)

    total = len(gt_items)
    item_paths = [p for p in ("structured", "item_text") if p in paths]
    hybrid: dict[str, int] = {}
    for path in item_paths:
        for gt_id, rank in ranks[path].items():
            hybrid[gt_id] = min(rank, hybrid.get(gt_id, 1 << 30))

    def _summary(rank_map, grid, unit):
        return {
            "rank_unit": unit,
            "retrieved": len(rank_map),
            "recall_within_max_depth": round(len(rank_map) / total, 4) if total else None,
            "recall_at": _recall_at(rank_map, total, grid),
            "median_rank": _median([r for r in rank_map.values()]),
        }

    by_path = {}
    for path in item_paths:
        by_path[path] = _summary(ranks[path], ITEM_K, "item")
    if "paragraph" in paths:
        by_path["paragraph_document_level"] = _summary(ranks["paragraph_doc"], DOC_K, "document")
        by_path["paragraph_localized"] = _summary(ranks["paragraph"], DOC_K, "document")
    if item_paths:
        by_path["hybrid_item_paths"] = _summary(hybrid, ITEM_K, "item")

    # every path missed it (item paths unbounded within max_depth, paragraph at doc level)
    found_anywhere = set(hybrid) | set(ranks["paragraph_doc"])
    missed = [g for g in gt_items if g["gt_id"] not in found_anywhere]
    missed_item_paths = [g for g in gt_items if g["gt_id"] not in hybrid]

    def _breakdown(key):
        rows = {}
        for value, group in sorted(_bucket(gt_items, key).items(), key=lambda kv: str(kv[0])):
            ids = {g["gt_id"] for g in group}
            entry = {"gt_items": len(group)}
            for path in item_paths:
                sub = {gid: r for gid, r in ranks[path].items() if gid in ids}
                entry[path] = {
                    "recall_within_max_depth": round(len(sub) / len(group), 4),
                    "recall_at": _recall_at(sub, len(group), (25, 100, 1000)),
                }
            if "paragraph" in paths:
                sub = {gid: r for gid, r in ranks["paragraph_doc"].items() if gid in ids}
                entry["paragraph_document_level"] = {
                    "recall_within_doc_depth": round(len(sub) / len(group), 4),
                }
            sub = {gid: r for gid, r in hybrid.items() if gid in ids}
            entry["hybrid_item_paths"] = {
                "recall_within_max_depth": round(len(sub) / len(group), 4),
            }
            rows[str(value)] = entry
        return rows

    sample = []
    for gt in missed_item_paths[: max(miss_sample, 0)]:
        sample.append(
            {
                "gt_id": gt["gt_id"], "file_key": gt["file_key"], "family": gt["family"],
                "ctype": gt.get("ctype"), "taxonomy_id": gt["taxonomy_id"],
                "polarity": gt["polarity"], "loc": [gt["loc_start"], gt["loc_end"]],
                "proposition": gt["proposition"][:180],
                "verbatim": gt["verbatim"][:240],
                "found_by_paragraph_path": gt["gt_id"] in ranks["paragraph_doc"],
            }
        )
    for entry in sample[: max(diagnose_n, 0)]:
        gt = next(g for g in gt_items if g["gt_id"] == entry["gt_id"])
        entry.update(diagnose(out, gt))

    return {
        "benchmark": "V4 absolute item-level recall (full_read answer key)",
        "hit_definition": {
            "granularity": "answer-key item, not document",
            "query_source": "taxonomy canonical label / aliases — the concept, never the row id",
            "identity_rules": [
                "verbatim_exact",
                f"verbatim_containment(>={MIN_CONTAINMENT} normalized chars)",
                "loc_overlap + same sub-domain",
            ],
            "paragraph_path": "document rank; 'localized' additionally requires a matched "
                              "paragraph inside the item's ¶ range (floor: matched_terms is "
                              "capped at 20 per document)",
            "scope": "(file_key, family) — a full_read for one family scores that family only",
        },
        "limits": [
            "ground truth is RW/PAY only and SPA-skewed — not a corpus-wide claim",
            "answer keys were produced by an AI reading the article start-to-end, "
            "not by an independent human labeller",
            "items beyond max_depth are reported as not retrieved, which is the "
            "practical truth for a user but not proof of absence from the index",
            "re-extraction is in flight: answer keys not yet stored are broken out "
            "under by_answer_key_stored — that shortfall is pipeline backlog, not "
            "a search defect",
        ],
        "parameters": {"max_depth": max_depth, "doc_depth": doc_depth,
                       "paragraph_terms": paragraph_terms,
                       "paths": list(paths), "item_k": list(ITEM_K), "doc_k": list(DOC_K)},
        "ground_truth": inventory(docs),
        "total_gt_items": total,
        "by_path": by_path,
        "by_family": _breakdown(lambda g: g["family"]),
        "by_ctype": _breakdown(lambda g: g.get("ctype")),
        "by_answer_key_stored": _breakdown(
            lambda g: "stored" if g.get("answer_key_stored") else "not_yet_stored"
        ),
        "match_rules": dict(Counter(rules.values())),
        "missed_by_all_paths": len(missed),
        "missed_by_item_paths": len(missed_item_paths),
        "miss_sample": sample,
        "concepts": sorted(concept_rows, key=lambda r: -r["gt_items"]),
        "elapsed_s": round(time.perf_counter() - started, 2),
    }


def _median(values: list[int]):
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def main(argv=None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Absolute item-level recall over full_read docs.")
    parser.add_argument("--out", type=Path, default=Path("cs_index"))
    parser.add_argument("--report", type=Path, help="write the full JSON report here")
    parser.add_argument("--max-depth", type=int, default=2000,
                        help="deepest item rank scanned per concept query (default 2000)")
    parser.add_argument("--doc-depth", type=int, default=50,
                        help="deepest document rank scanned on the paragraph path")
    parser.add_argument("--paragraph-terms", type=int, default=1,
                        help="alias terms tried on the (slow) legacy paragraph path")
    parser.add_argument("--paths", default="structured,item_text,paragraph")
    parser.add_argument("--diagnose", type=int, default=25,
                        help="diagnose this many sampled misses (0 disables)")
    parser.add_argument("--miss-sample", type=int, default=40)
    parser.add_argument("--summary-only", action="store_true",
                        help="print the report without per-concept rows")
    args = parser.parse_args(argv)

    report = evaluate(
        args.out,
        max_depth=args.max_depth,
        doc_depth=args.doc_depth,
        paths=tuple(p.strip() for p in args.paths.split(",") if p.strip()),
        diagnose_n=args.diagnose,
        miss_sample=args.miss_sample,
        paragraph_terms=args.paragraph_terms,
    )
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                               encoding="utf-8")
    printable = dict(report)
    if args.summary_only:
        printable.pop("concepts", None)
    print(json.dumps(printable, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
