"""Ranking-signal probe (V4_PLAN §9.6): where does the answer-key item rank when
the query carries a real signal, and how much of the gap is lexical vs semantic?

`eval_absolute_recall.py` drives every query with ONLY the taxonomy concept label
(e.g. "경업금지"), which every sibling in the node also matches — so it measures
population size, not ranking. Its "recall@10 ≈ 1.5% / median 462" is the arithmetic
consequence of returning a whole node (RW.CONTRACTS 2,894 .. DEF.CONTRACT_TERM
18,404) with no discriminating query signal, NOT a defect a ranker can tune away.
T4/embeddings do NOT fix that benchmark either: one word is near-equidistant to all
siblings. What T4 is supposed to win is *paraphrase* matching — a user who describes
a clause in their own words instead of quoting it.

This probe measures two honest counterparts, both read-only:

  --mode verbatim    (default) query = a distinctive leading slice of the item's own
                     verbatim (a remembered quote). Measures ranking when the words
                     are literally in the clause text. This is the metric the
                     text-path relevance ordering (v4_search) moves.

  --mode paraphrase  query = the item's distinctive PROPOSITION tokens (a normalized
                     restatement whose wording differs from the verbatim). Measures
                     the LEXICAL gap between how a clause is described and how it is
                     written — the space embeddings claim to close. Its shortfall
                     vs. the verbatim mode is the pre-registered T4-ablation baseline:
                     V4-7 must beat this lexical number to justify adoption.

Measured 2026-07-30, 220 stored full_read answer-key items (seed 17):
  concept-label path (eval_absolute_recall):        recall@10 1.5%   median 462
  verbatim mode, file_key order (pre-ordering):     recall@10 0.905  median 1
  verbatim mode, relevance order + token AND:       (see current run)
  paraphrase mode (lexical gap / T4 baseline):      (see current run)

Run from repo root:
  python eval_ranking_signal.py [n] [--mode verbatim|paraphrase] [--dump-misses N]
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

from lib.console import configure_utf8_stdio
from eval_absolute_recall import (
    DEFAULT_SOURCES,
    MIN_CONTAINMENT,
    load_ground_truth,
    match_item,
    normalize_text,
)
from v4_search import search_clause_items

OUT = Path("cs_index")
K_GRID = (1, 3, 5, 10, 25, 50, 100)
DEPTH = 200
_WORD = re.compile(r"[0-9A-Za-z가-힣%]+")


def verbatim_needle(item: dict) -> str | None:
    """A ≤40-char leading slice of the verbatim — a plausible remembered quote."""
    text = " ".join(str(item.get("verbatim") or "").split())[:40].strip()
    return text if len(normalize_text(text)) >= MIN_CONTAINMENT else None


def paraphrase_needle(item: dict) -> str | None:
    """The proposition's most distinctive content tokens (up to 4, longest first) —
    a keyword-style description in the restatement's vocabulary, not the verbatim's."""
    tokens = [t for t in _WORD.findall(str(item.get("proposition") or "")) if len(t) >= 2]
    # longest distinct tokens carry the most signal; keep original casing for the query
    seen, picked = set(), []
    for tok in sorted(tokens, key=len, reverse=True):
        low = tok.lower()
        if low not in seen:
            seen.add(low)
            picked.append(tok)
        if len(picked) >= 4:
            break
    query = " ".join(picked)
    return query if len(normalize_text(query)) >= MIN_CONTAINMENT else None


def _verbatim_token_coverage(item: dict, query: str) -> float:
    """Fraction of the query tokens that literally appear in the item's verbatim —
    the direct lexical-gap indicator (1.0 = fully lexical, low = paraphrased away)."""
    toks = [t.lower() for t in query.split() if t]
    if not toks:
        return 0.0
    v = str(item.get("verbatim") or "").lower()
    return sum(1 for t in toks if t in v) / len(toks)


def rank_of(item: dict, query: str, depth: int = DEPTH) -> int | None:
    try:
        page = search_clause_items(OUT, item["family"], text=query,
                                   show_duplicates=True, limit=depth)
    except Exception:
        return None
    for rank, row in enumerate(page["results"], start=1):
        if match_item(item, row):
            return rank
    return None


def _median(values):
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def evaluate(n_sample=300, seed=17, mode="verbatim", dump_misses=0) -> dict:
    make_needle = verbatim_needle if mode == "verbatim" else paraphrase_needle
    items = [it for doc in load_ground_truth(OUT, DEFAULT_SOURCES) for it in doc["items"]]
    random.Random(seed).shuffle(items)
    records, coverages = [], []
    for it in items:
        query = make_needle(it)
        if not query:
            continue
        if len(records) >= n_sample:
            break
        rank = rank_of(it, query)
        coverages.append(_verbatim_token_coverage(it, query))
        records.append({"item": it, "query": query, "rank": rank})
    found = [r["rank"] for r in records if r["rank"] is not None]
    n = len(records)
    misses = [r for r in records if r["rank"] is None or r["rank"] > 10]
    report = {
        "probe": f"ranking-signal ({mode}) — V4_PLAN §9.6",
        "mode": mode,
        "probed": n,
        f"found_within_{DEPTH}": len(found),
        f"recall_within_{DEPTH}": round(len(found) / n, 4) if n else None,
        "recall_at": {f"@{k}": round(sum(1 for r in found if r <= k) / n, 4)
                      for k in K_GRID} if n else {},
        "median_rank_of_found": _median(found),
        "mean_verbatim_token_coverage": round(sum(coverages) / n, 4) if n else None,
        "misses_or_below_top10": len(misses),
    }
    if dump_misses:
        report["miss_sample"] = [
            {
                "family": r["item"]["family"],
                "taxonomy_id": r["item"]["taxonomy_id"],
                "rank": r["rank"],
                "query": r["query"],
                "verbatim_token_coverage": round(_verbatim_token_coverage(r["item"], r["query"]), 3),
                "verbatim_head": " ".join(str(r["item"].get("verbatim") or "").split())[:90],
            }
            for r in misses[:dump_misses]
        ]
    return report


def main(argv=None) -> int:
    configure_utf8_stdio()
    ap = argparse.ArgumentParser(description="Ranking-signal probe (§9.6).")
    ap.add_argument("n", nargs="?", type=int, default=300)
    ap.add_argument("--mode", choices=("verbatim", "paraphrase"), default="verbatim")
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--dump-misses", type=int, default=0)
    args = ap.parse_args(argv)
    print(json.dumps(evaluate(args.n, args.seed, args.mode, args.dump_misses),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
