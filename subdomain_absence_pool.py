#!/usr/bin/env python3
"""subdomain_absence_pool.py -- generalized READ-ONLY recall net for absence claims.

The corpus-wide standing audit half of net-then-confirm (V4_PLAN §9.3), generalizing
env_absence_pool.py to ANY (family, sub-domain). For a sub-domain blanket-stamped
body_status='complete', it lists the documents that would become confirmed_absent if
un-gated and splits them by an automated grounding scan of the txt cache:

  clean_absent : none of the sub-domain's vocabulary appears -> supports genuine absence.
  suspect      : vocabulary IS present yet extraction produced ZERO items in the subtree
                 -> a likely MISSED extraction (false absence); feed only these to a
                 confirm/정독 pass.

The scan costs zero API tokens, so it sweeps the whole corpus; only the `suspect` set
is worth a confirm pass. Two modes:

  --subdomain RW.LABOR   detailed pool listing + snippets for one sub-domain.
  --all [--family RW]    aggregate sweep over every sub-domain (one text read per doc),
                         ranked by suspect count; flags sub-domains whose vocabulary is
                         too broad to discriminate (implausibly high suspect rate).

Vocabulary derivation, scanning, and the per-doc suspect check live in lib.absence_net
(shared with the store-time guard). Strictly read-only, mode=ro, no APIs.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Optional

from lib.absence_net import (  # noqa: F401  (derive_terms re-exported for tests)
    build_vocab_for,
    covered_subdomains,
    derive_terms,
    doc_absence_suspects,
    doc_folded,
    family_subdomains,
    family_vocab,
    resolve_txt,
    text_hits,
)

REPO_ROOT = Path(__file__).resolve().parent
CS_INDEX = REPO_ROOT / "cs_index"
DB_URI = "file:cs_index/catalog.sqlite?mode=ro"
SCRATCH = REPO_ROOT / "scratchpad" / "subdomain_absence"
SUSPECT_RATE_BROAD = 0.85  # above this, the vocabulary can't discriminate -> flag, don't trust

ALL_FAMILIES = ("RW", "PAY", "DEF", "COV", "REM", "CP")


def _family_complete_docs(conn: sqlite3.Connection, family: str) -> List[sqlite3.Row]:
    """Docs with this family's coverage complete, status ok, non-empty txt."""
    return list(conn.execute(
        """
        SELECT f.file_key, f.filename, f.txt_path, f.dup_group, f.char_count
        FROM v4_document_coverage c JOIN files f ON f.file_key = c.file_key
        WHERE c.family = ? AND c.body_status = 'complete'
          AND f.status = 'ok' AND COALESCE(f.char_count, 0) > 0
        ORDER BY f.file_key
        """,
        (family,),
    ))


def _dedup(rows: List[sqlite3.Row]) -> List[sqlite3.Row]:
    seen, out = set(), []
    for r in rows:
        g = r["dup_group"] or r["file_key"]
        if g in seen:
            continue
        seen.add(g)
        out.append(r)
    return out


def run_subdomain(subdomain: str, snippet_cap: int = 5) -> dict:
    """Detailed single-sub-domain pool: every zero-item doc classified clean/suspect."""
    family = subdomain.split(".")[0]
    conn = sqlite3.connect(DB_URI, uri=True)
    conn.row_factory = sqlite3.Row
    ko, en_pat, canon = build_vocab_for(conn, subdomain)
    if not ko and not en_pat:
        raise SystemExit(f"no vocabulary derivable for {subdomain}")

    subs = [subdomain]
    pool = [r for r in _family_complete_docs(conn, family)
            if not covered_subdomains(conn, r["file_key"], family, subs)]
    deduped = _dedup(pool)

    records = []
    for r in pool:
        fk = r["file_key"]
        folded = doc_folded(conn, CS_INDEX, fk)
        if folded is None:
            records.append({"file_key": fk, "filename": r["filename"],
                            "dup_group": r["dup_group"] or fk, "cls": "no_txt", "hits": []})
            continue
        hits = text_hits(folded, ko, en_pat)
        records.append({"file_key": fk, "filename": r["filename"],
                        "dup_group": r["dup_group"] or fk,
                        "cls": "suspect" if hits else "clean_absent", "hits": hits})
    conn.close()

    by_key = {x["file_key"]: x for x in records}
    dd = [by_key[r["file_key"]] for r in deduped]
    def _c(cls): return [x for x in dd if x["cls"] == cls]
    clean, suspect, notxt = _c("clean_absent"), _c("suspect"), _c("no_txt")

    report = {
        "subdomain": subdomain, "family": family, "read_only": True,
        "vocabulary": {"source_canonicals": canon, "ko": ko,
                       "en": [t for t, _ in en_pat], "size": len(ko) + len(en_pat)},
        "pool_size_raw": len(pool), "pool_size_deduped": len(deduped),
        "counts_deduped": {"clean_absent": len(clean), "suspect": len(suspect),
                           "no_txt": len(notxt)},
        "suspect_rate_deduped": round(len(suspect) / len(deduped), 4) if deduped else None,
        "suspects": [{"file_key": x["file_key"], "filename": x["filename"],
                      "dup_group": x["dup_group"], "matched_terms": x["hits"][:snippet_cap]}
                     for x in suspect],
    }
    SCRATCH.mkdir(parents=True, exist_ok=True)
    slug = subdomain.replace(".", "_")
    (SCRATCH / f"{slug}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with (SCRATCH / f"{slug}.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["file_key", "filename", "dup_group", "classification", "matched_terms"])
        for rec in records:
            w.writerow([rec["file_key"], rec["filename"], rec["dup_group"], rec["cls"],
                        "; ".join(rec["hits"])])
    return report


def sweep(families: List[str]) -> dict:
    """Aggregate sweep: for every family-complete doc, one text read, test each of its
    UNCOVERED sub-domains. Ranks sub-domains by suspect-doc count.

    Speed: a single combined regex per sub-domain gates each doc (C-level) before the
    detailed term-attributing scan runs only on a hit; folded document text is cached
    across families so a doc complete in several families is read once."""
    from lib.absence_net import compile_any
    conn = sqlite3.connect(DB_URI, uri=True)
    conn.row_factory = sqlite3.Row
    per_subdomain: Dict[str, dict] = {}
    folded_cache: Dict[str, Optional[str]] = {}
    for family in families:
        vocab = family_vocab(conn, family)
        any_pat = {sd: compile_any(ko, [t for t, _ in en_pat])
                   for sd, (ko, en_pat, _c) in vocab.items()}
        docs = _dedup(_family_complete_docs(conn, family))
        for sd in vocab:
            ko, en_pat, canon = vocab[sd]
            per_subdomain[sd] = {
                "family": family, "vocab_size": len(ko) + len(en_pat),
                "source_canonicals": canon, "auditable": bool(ko or en_pat),
                "pool": 0, "suspect": 0, "suspect_keys": [],
            }
        for i, r in enumerate(docs, 1):
            fk = r["file_key"]
            covered = covered_subdomains(conn, fk, family, list(vocab))
            uncovered = [sd for sd in vocab if sd not in covered]
            if not uncovered:
                continue
            if fk not in folded_cache:
                folded_cache[fk] = doc_folded(conn, CS_INDEX, fk)
            folded = folded_cache[fk]
            for sd in uncovered:
                per_subdomain[sd]["pool"] += 1
                pat = any_pat[sd]
                if folded and pat and pat.search(folded):
                    per_subdomain[sd]["suspect"] += 1
                    if len(per_subdomain[sd]["suspect_keys"]) < 50:
                        ko, en_pat, _c = vocab[sd]
                        per_subdomain[sd]["suspect_keys"].append(
                            {"file_key": fk, "terms": text_hits(folded, ko, en_pat)[:8]})
            if i % 100 == 0:
                print(f"  [{family}] {i}/{len(docs)} docs", file=sys.stderr, flush=True)
    conn.close()

    for sd, d in per_subdomain.items():
        d["suspect_rate"] = round(d["suspect"] / d["pool"], 4) if d["pool"] else None
        d["vocab_too_broad"] = (d["suspect_rate"] is not None
                                and d["suspect_rate"] >= SUSPECT_RATE_BROAD)
    ranked = sorted(per_subdomain.items(),
                    key=lambda kv: (-(kv[1]["suspect"] or 0), kv[0]))
    summary = {
        "families": families, "read_only": True,
        "suspect_rate_broad_threshold": SUSPECT_RATE_BROAD,
        "subdomains_total": len(per_subdomain),
        "subdomains_with_suspects": sum(1 for _, d in ranked if d["suspect"]),
        "not_auditable": [sd for sd, d in ranked if not d["auditable"]],
        "vocab_too_broad": [sd for sd, d in ranked if d["vocab_too_broad"]],
        "ranking": [
            {"subdomain": sd, "family": d["family"], "pool": d["pool"],
             "suspect": d["suspect"], "suspect_rate": d["suspect_rate"],
             "vocab_size": d["vocab_size"], "vocab_too_broad": d["vocab_too_broad"],
             "source_canonicals": d["source_canonicals"]}
            for sd, d in ranked
        ],
        "suspect_keys": {sd: d["suspect_keys"] for sd, d in ranked if d["suspect_keys"]},
    }
    SCRATCH.mkdir(parents=True, exist_ok=True)
    (SCRATCH / "sweep_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subdomain", help="detailed audit of one node, e.g. RW.LABOR")
    ap.add_argument("--all", action="store_true", help="aggregate sweep over all sub-domains")
    ap.add_argument("--family", help="restrict --all to one family (default: all families)")
    ap.add_argument("--build-df", action="store_true",
                    help="compute the needle document-frequency cache (precision filter) and exit")
    args = ap.parse_args(argv)

    if args.build_df:
        from lib.absence_net import build_needle_df
        conn = sqlite3.connect(DB_URI, uri=True)
        payload = build_needle_df(conn, CS_INDEX)
        conn.close()
        df = payload["df"]
        broad = sorted(((v, k) for k, v in df.items() if v > payload["df_max"]), reverse=True)
        print(json.dumps({"docs": payload["docs"], "df_max": payload["df_max"],
                          "needles": len(df), "dropped_as_broad": len(broad),
                          "top_broad": [{"needle": k, "df": v} for v, k in broad[:25]]},
                         ensure_ascii=False, indent=2))
        return 0
    if args.all:
        fams = [args.family] if args.family else list(ALL_FAMILIES)
        summary = sweep(fams)
        top = summary["ranking"][:20]
        print(json.dumps({
            "families": fams,
            "subdomains_total": summary["subdomains_total"],
            "subdomains_with_suspects": summary["subdomains_with_suspects"],
            "not_auditable": summary["not_auditable"],
            "vocab_too_broad": summary["vocab_too_broad"],
            "top20": [{k: r[k] for k in ("subdomain", "pool", "suspect",
                                         "suspect_rate", "vocab_too_broad")} for r in top],
        }, ensure_ascii=False, indent=2))
        return 0
    if args.subdomain:
        report = run_subdomain(args.subdomain)
        print(json.dumps({k: report[k] for k in
                          ("subdomain", "pool_size_raw", "pool_size_deduped",
                           "counts_deduped", "suspect_rate_deduped")},
                         ensure_ascii=False, indent=2))
        print("vocab:", report["vocabulary"]["size"],
              "from", report["vocabulary"]["source_canonicals"])
        return 0
    ap.error("pass --subdomain NODE or --all")


if __name__ == "__main__":
    sys.exit(main())
