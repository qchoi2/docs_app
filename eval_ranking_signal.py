"""Ranking-signal probe (V4_PLAN §9.6).

The absolute-recall benchmark (`eval_absolute_recall.py`) drives every query with
ONLY the taxonomy concept label (e.g. "경업금지"), which *every* sibling item in the
node also matches — so it measures population size, not ranking. Its headline
"recall@10 ≈ 1.5% / median rank ≈ 462" is the arithmetic consequence of returning
a whole node (RW.CONTRACTS 2,894 items, DEF.CONTRACT_TERM 18,404) with no
discriminating query signal, NOT a defect a ranker can tune away.

This probe measures the honest counterpart: when the query carries a *discriminating*
signal (a distinctive slice of the item's own verbatim — what a user typing a
remembered phrase gives), where does the answer-key item land? High recall here next
to low recall on the concept path proves the bottleneck is query signal, not ranking.
It is also the metric that moves when `search_clause_items`' text-path relevance
ordering (v4_search, ORDER BY relevance when `text` is present) improves.

Measured 2026-07-30, 220 stored full_read answer-key items (seed 17):
  concept-label path (eval_absolute_recall):  recall@1 ~0    recall@10 1.5%   median 462
  discriminating path, file_key order (old):  recall@1 0.536  recall@10 0.905  median 1
  discriminating path, relevance order (new): recall@1 0.623  recall@10 0.923  median 1

Read-only. Run from repo root:  python eval_ranking_signal.py [n_sample]
"""
from __future__ import annotations

import json
import random
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


def distinctive_needle(verbatim: str) -> str | None:
    """A ≤40-char leading slice of the item's verbatim: long enough to be
    distinctive, short enough to be a plausible user query (mirrors
    eval_absolute_recall.diagnose's probe)."""
    text = " ".join(str(verbatim or "").split())[:40].strip()
    return text if len(normalize_text(text)) >= MIN_CONTAINMENT else None


def rank_of(gt: dict, needle: str, depth: int = DEPTH) -> int | None:
    """First rank at which the answer-key item is identified on the item-text path."""
    try:
        page = search_clause_items(OUT, gt["family"], text=needle,
                                   show_duplicates=True, limit=depth)
    except Exception:
        return None
    for rank, row in enumerate(page["results"], start=1):
        if match_item(gt, row):
            return rank
    return None


def _median(values):
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def evaluate(n_sample: int = 300, seed: int = 17) -> dict:
    items = [it for doc in load_ground_truth(OUT, DEFAULT_SOURCES) for it in doc["items"]]
    random.Random(seed).shuffle(items)
    ranks: list[int | None] = []
    for it in items:
        needle = distinctive_needle(it["verbatim"])
        if not needle:
            continue
        if len(ranks) >= n_sample:
            break
        ranks.append(rank_of(it, needle))
    found = [r for r in ranks if r is not None]
    n = len(ranks)
    return {
        "probe": "discriminating-query item recall (V4_PLAN §9.6)",
        "probed": n,
        f"found_within_{DEPTH}": len(found),
        f"recall_within_{DEPTH}": round(len(found) / n, 4) if n else None,
        "recall_at": {f"@{k}": round(sum(1 for r in found if r <= k) / n, 4)
                      for k in K_GRID} if n else {},
        "median_rank_of_found": _median(found),
    }


def main(argv=None) -> int:
    configure_utf8_stdio()
    n = int(argv[0]) if argv else (int(sys.argv[1]) if len(sys.argv) > 1 else 300)
    print(json.dumps(evaluate(n), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
