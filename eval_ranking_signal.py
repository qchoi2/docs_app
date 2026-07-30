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

verbatim mode scores multi-answer: any item bearing the SAME full verbatim (an
identical-clause sibling in any document) counts, not only the source file_key. The
earlier single-item keying made @1 a needle-provenance metric — an identical-quote
sibling ranked first read as a miss — which is what depressed verbatim @1 to ~0.48
and was mis-attributed to sample variance in an earlier round (Fable §9.6 review).

Measured 2026-07-30, 220 stored full_read answer-key items (seed 17), post
noise-cleanup corpus (55 COV headings deleted, 3 reclassified):
  concept-label path (eval_absolute_recall):        recall@10 1.5%   median 462
  verbatim, single-item keying (old):               @1 0.482  recall@10 0.859
  verbatim, multi-answer (identical-sibling) keying: @1 0.700  recall@10 0.927
  paraphrase mode (lexical gap / T4 baseline):      @1 0.396  recall@10 0.609

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


# Trailing Korean particles (조사). The proposition's longest token is often a
# josa-attached form ("손해배상액의") that fails a substring match against the bare
# stem in the verbatim ("손해배상액") — a morphological artifact, not a real gap.
_JOSA = re.compile(
    r"(으로서|으로써|이라도|으로|로서|로써|에게서|에게|에서|께서|한테|부터|까지|마다|조차|처럼|"
    r"보다|이나|나마|든지|이라|라도|란|은|는|이|가|을|를|의|에|와|과|도|만|랑|이랑|께|더러|보고)$"
)


def strip_josa(tok: str) -> str:
    if re.search(r"[가-힣]$", tok):
        m = _JOSA.search(tok)
        if m and m.start() >= 2:  # keep a stem of >=2 syllables
            return tok[: m.start()]
    return tok


def paraphrase_tokens(item: dict, n: int = 6) -> list[str]:
    """Distinctive proposition content tokens, josa-stripped — the vocabulary a user
    would type to describe the clause, normalized past inflection."""
    raw = [t for t in _WORD.findall(str(item.get("proposition") or "")) if len(t) >= 2]
    seen, picked = set(), []
    for tok in sorted(raw, key=len, reverse=True):
        stem = strip_josa(tok)
        low = stem.lower()
        if len(stem) >= 2 and low not in seen:
            seen.add(low)
            picked.append(stem)
        if len(picked) >= n:
            break
    return picked


def _verbatim_token_coverage(item: dict, tokens) -> float:
    """Fraction of the query tokens that literally appear in the item's verbatim —
    the direct lexical-gap indicator (1.0 = fully lexical, low = paraphrased away)."""
    toks = [t.lower() for t in (tokens.split() if isinstance(tokens, str) else tokens) if t]
    if not toks:
        return 0.0
    v = str(item.get("verbatim") or "").lower()
    return sum(1 for t in toks if t in v) / len(toks)


def _same_verbatim(item: dict, row: dict) -> bool:
    """Multi-answer verbatim match: does this row carry the SAME full verbatim as the
    source item (an identical-clause sibling), in any document? The 2000-char store
    truncation is why containment — not just equality — counts. This is match_item's
    verbatim rule with the file_key gate removed: an identical clause pasted into a
    second contract is a correct answer to 'find this quote', so crediting it keeps @1
    a ranking-skill metric instead of a needle-provenance one (Fable §9.6 review).
    It stays STRICTER than 'row contains the 40-char needle' — a different clause that
    merely shares a boilerplate head is NOT credited, so @1 is not made tautological."""
    a = normalize_text(item.get("verbatim"))
    b = normalize_text(row.get("verbatim"))
    if not a or not b:
        return False
    if a == b:
        return True
    return len(a) >= MIN_CONTAINMENT and len(b) >= MIN_CONTAINMENT and (a in b or b in a)


def rank_of(item: dict, query: str, depth: int = DEPTH, *, multi_answer=False) -> int | None:
    """AND retrieval (the product's current text path): every token must co-occur.
    verbatim mode sets multi_answer=True to credit any identical-verbatim sibling;
    paraphrase mode scores the specific answer item (file_key-scoped) via match_item."""
    try:
        page = search_clause_items(OUT, item["family"], text=query,
                                   show_duplicates=True, limit=depth)
    except Exception:
        return None
    for rank, row in enumerate(page["results"], start=1):
        if multi_answer:
            if _same_verbatim(item, row):
                return rank
        elif match_item(item, row):
            return rank
    return None




def _median(values):
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def evaluate(n_sample=300, seed=17, mode="verbatim", dump_misses=0) -> dict:
    items = [it for doc in load_ground_truth(OUT, DEFAULT_SOURCES) for it in doc["items"]]
    random.Random(seed).shuffle(items)
    records, coverages = [], []
    for it in items:
        if mode == "paraphrase":
            # josa-stripped proposition tokens through the product path (now FTS AND +
            # bm25): the fair lexical baseline — normalized past inflection, IDF-ranked.
            toks = paraphrase_tokens(it, n=4)
            query = " ".join(toks)
            if len(normalize_text(query)) < MIN_CONTAINMENT:
                continue
            cov = _verbatim_token_coverage(it, toks)
        else:
            query = verbatim_needle(it)
            if not query:
                continue
            cov = _verbatim_token_coverage(it, query)
        if len(records) >= n_sample:
            break
        rank = rank_of(it, query, multi_answer=(mode == "verbatim"))
        coverages.append(cov)
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
