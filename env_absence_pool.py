#!/usr/bin/env python3
"""env_absence_pool.py -- READ-ONLY grounding check for pre-releasing (선해제)
RW.ENVIRONMENT absence queries.

Builds the pool of documents that WOULD become confirmed_absent if the
RW.ENVIRONMENT sub-domain were un-gated, then runs an automated first-pass
grounding check against each document's txt cache to separate:

  clean_absent : no environment-representation language anywhere -> supports
                 a genuine confirmed_absent claim.
  suspect      : environment language IS present in the text even though the
                 extraction produced zero RW.ENVIRONMENT items -> a likely
                 MISSED extraction (false absence). Must NOT be auto-confirmed.

Strictly read-only. Opens catalog.sqlite with mode=ro. No writes, no APIs.
"""
from __future__ import annotations

import csv
import json
import random
import re
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Reuse the exact same [¶n] marker parsing the tooling uses.
from open_text import read_paragraphs
from lib.normalize import normalize

REPO_ROOT = Path(__file__).resolve().parent
CS_INDEX = REPO_ROOT / "cs_index"
DB_URI = "file:cs_index/catalog.sqlite?mode=ro"
SCRATCH = REPO_ROOT / "scratchpad"

RANDOM_SEED = 20260729  # deterministic sampling for reproducible spot-checks


# --------------------------------------------------------------------------
# Environment-representation synonym list.
# Seeded from data/term_dict.yaml (canonical 환경개인정보진술: ko 환경/환경법규;
# en environmental matters) and data/v4_term_mapping.yaml (환경개인정보진술 ->
# RW.ENVIRONMENT), then extended with the task-mandated minimum set.
#
# Korean needles are matched as plain substrings (no word boundaries in Korean).
# Latin needles are matched with word boundaries to avoid spurious substrings.
# --------------------------------------------------------------------------
KO_TERMS = [
    "환경",          # environment (broad -- deliberately kept; false-alarm risk evaluated)
    "환경법",        # environmental law
    "환경법규",      # environmental laws/regulations (from term_dict)
    "환경 관련 법",  # environment-related law
    "환경인허가",    # environmental permit
    "환경 인허가",
    "환경허가",
    "오염",          # pollution/contamination
    "토양오염",      # soil contamination
    "토양 오염",
    "수질오염",      # water pollution
    "대기오염",      # air pollution
    "유해물질",      # hazardous substances
    "유해 물질",
    "유해화학물질",  # hazardous chemicals
    "폐기물",        # waste
    "오염물질",      # pollutant
    "정화",          # remediation / clean-up (env context; false-alarm risk evaluated)
    "토양정화",
]
# Latin terms (word-boundary matched, casefolded).
EN_TERMS = [
    "environmental",
    "environment",
    "contamination",
    "contaminant",
    "contaminated",
    "hazardous material",
    "hazardous materials",
    "hazardous substance",
    "hazardous substances",
    "pollution",
    "pollutant",
    "remediation",
    "remediate",
    "waste",
    "environmental permit",
    "environmental law",
    "environmental laws",
    "environmental regulation",
    "environmental regulations",
    "environmental matters",
]

# Pre-compile latin word-boundary patterns once.
_EN_PATTERNS: List[Tuple[str, re.Pattern]] = [
    (t, re.compile(r"\b" + re.escape(t) + r"\b")) for t in EN_TERMS
]


def build_pool(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    """RW body_status='complete' AND status ok AND non-empty txt AND ZERO
    RW.ENVIRONMENT-subtree clause items."""
    sql = """
    SELECT f.file_key, f.filename, f.txt_path, f.dup_group, f.char_count
    FROM v4_document_coverage c
    JOIN files f ON f.file_key = c.file_key
    WHERE c.family = 'RW'
      AND c.body_status = 'complete'
      AND f.status = 'ok'
      AND COALESCE(f.char_count, 0) > 0
      AND NOT EXISTS (
          SELECT 1 FROM v4_clause_item i
          WHERE i.file_key = f.file_key
            AND (i.taxonomy_id = 'RW.ENVIRONMENT'
                 OR i.taxonomy_id LIKE 'RW.ENVIRONMENT.%')
      )
    ORDER BY f.file_key
    """
    return list(conn.execute(sql))


def resolve_txt(file_key: str, txt_path: Optional[str]) -> Optional[Path]:
    """Path from files.txt_path (relative to cs_index/), fallback txt/<file_key>.txt."""
    candidates: List[Path] = []
    if txt_path:
        p = Path(txt_path)
        candidates.append(p if p.is_absolute() else CS_INDEX / p)
    candidates.append(CS_INDEX / "txt" / f"{file_key}.txt")
    for c in candidates:
        if c.exists():
            return c
    return None


def scan_doc(path: Path) -> List[Tuple[str, str]]:
    """Return list of (matched_term, snippet). Empty => clean_absent.
    Scans paragraph by paragraph so we can attach a real surrounding snippet."""
    paras = read_paragraphs(path)
    hits: List[Tuple[str, str]] = []
    seen_terms = set()
    for _num, raw in paras:
        norm = normalize(raw)
        folded = norm.casefold()
        if not folded:
            continue
        # Korean substrings
        for t in KO_TERMS:
            if t in folded and t not in seen_terms:
                hits.append((t, _snippet(norm, t)))
                seen_terms.add(t)
        # Latin word-boundary
        for t, pat in _EN_PATTERNS:
            if t in seen_terms:
                continue
            m = pat.search(folded)
            if m:
                hits.append((t, _snippet(norm, t, m.start())))
                seen_terms.add(t)
    return hits


def _snippet(norm_text: str, term: str, at: Optional[int] = None) -> str:
    folded = norm_text.casefold()
    if at is None:
        at = folded.find(term.casefold())
    if at < 0:
        at = 0
    start = max(0, at - 60)
    end = min(len(norm_text), at + len(term) + 60)
    s = norm_text[start:end].strip()
    if start > 0:
        s = "..." + s
    if end < len(norm_text):
        s = s + "..."
    return s


def main() -> int:
    SCRATCH.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_URI, uri=True)
    conn.row_factory = sqlite3.Row

    pool = build_pool(conn)
    raw_size = len(pool)

    # Dedupe by dup_group: keep one representative per group, but retain all in
    # the full listing. dup_group may be NULL -> treat file_key as its own group.
    groups_seen = set()
    deduped: List[sqlite3.Row] = []
    for r in pool:
        g = r["dup_group"] or r["file_key"]
        if g in groups_seen:
            continue
        groups_seen.add(g)
        deduped.append(r)
    dedup_size = len(deduped)

    records = []
    missing_txt = []
    for r in pool:  # classify ALL pool docs (list all, per spec)
        fk = r["file_key"]
        path = resolve_txt(fk, r["txt_path"])
        if path is None:
            missing_txt.append(fk)
            records.append({
                "file_key": fk,
                "filename": r["filename"],
                "dup_group": r["dup_group"] or fk,
                "classification": "no_txt",
                "hits": [],
            })
            continue
        hits = scan_doc(path)
        records.append({
            "file_key": fk,
            "filename": r["filename"],
            "dup_group": r["dup_group"] or fk,
            "classification": "suspect" if hits else "clean_absent",
            "hits": [{"term": t, "snippet": s} for t, s in hits],
        })

    by_key = {rec["file_key"]: rec for rec in records}

    # Dedup-scoped counts (one per dup_group) for the headline numbers.
    dedup_records = [by_key[r["file_key"]] for r in deduped]
    clean_dd = [x for x in dedup_records if x["classification"] == "clean_absent"]
    suspect_dd = [x for x in dedup_records if x["classification"] == "suspect"]
    notxt_dd = [x for x in dedup_records if x["classification"] == "no_txt"]

    # Raw (all rows) counts too.
    clean_raw = [x for x in records if x["classification"] == "clean_absent"]
    suspect_raw = [x for x in records if x["classification"] == "suspect"]

    report = {
        "generated_for": "RW.ENVIRONMENT pre-release (선해제) grounding check",
        "read_only": True,
        "pool_definition": (
            "RW coverage body_status='complete' AND files.status='ok' AND "
            "char_count>0 AND zero v4_clause_item rows with taxonomy_id in "
            "RW.ENVIRONMENT subtree"
        ),
        "pool_size_raw": raw_size,
        "pool_size_deduped": dedup_size,
        "counts_deduped": {
            "clean_absent": len(clean_dd),
            "suspect": len(suspect_dd),
            "no_txt": len(notxt_dd),
        },
        "counts_raw": {
            "clean_absent": len(clean_raw),
            "suspect": len(suspect_raw),
            "no_txt": len(missing_txt),
        },
        "suspect_rate_deduped": (
            round(len(suspect_dd) / dedup_size, 4) if dedup_size else None
        ),
        "suspects": [
            {
                "file_key": x["file_key"],
                "filename": x["filename"],
                "dup_group": x["dup_group"],
                "matched_terms": [h["term"] for h in x["hits"]],
                "snippets": [
                    {"term": h["term"], "snippet": h["snippet"]}
                    for h in x["hits"][:5]
                ],
            }
            for x in suspect_dd
        ],
        "synonym_terms": {"ko": KO_TERMS, "en": EN_TERMS},
    }

    (SCRATCH / "env_absence_pool.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Full pool CSV (all rows, list all).
    with (SCRATCH / "env_absence_pool.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["file_key", "filename", "dup_group", "classification", "matched_terms"])
        for rec in records:
            w.writerow([
                rec["file_key"], rec["filename"], rec["dup_group"],
                rec["classification"],
                "; ".join(h["term"] for h in rec["hits"]),
            ])

    # Samples: 12 random clean_absent + 8 random suspect (dedup-scoped).
    rng = random.Random(RANDOM_SEED)
    clean_sample = rng.sample(clean_dd, min(12, len(clean_dd)))
    suspect_sample = rng.sample(suspect_dd, min(8, len(suspect_dd)))

    lines: List[str] = []
    lines.append("=== RW.ENVIRONMENT absence pool -- spot-check samples ===")
    lines.append(f"pool raw={raw_size} deduped={dedup_size} | "
                 f"clean_absent={len(clean_dd)} suspect={len(suspect_dd)} "
                 f"no_txt={len(notxt_dd)} (deduped)")
    lines.append("")
    lines.append(f"--- 12 RANDOM clean_absent (expect: NO env language) ---")
    for x in clean_sample:
        lines.append(f"[{x['file_key']}] {x['filename']}")
        lines.append("   -> no env language found")
    lines.append("")
    lines.append(f"--- 8 RANDOM suspect (env text present, no env ITEM) ---")
    for x in suspect_sample:
        lines.append(f"[{x['file_key']}] {x['filename']}")
        for h in x["hits"][:4]:
            lines.append(f"   MATCH '{h['term']}': {h['snippet']}")
    lines.append("")
    (SCRATCH / "env_absence_samples.txt").write_text("\n".join(lines), encoding="utf-8")

    # Console echo.
    print(json.dumps({
        "pool_size_raw": raw_size,
        "pool_size_deduped": dedup_size,
        "counts_deduped": report["counts_deduped"],
        "suspect_rate_deduped": report["suspect_rate_deduped"],
        "missing_txt": missing_txt,
    }, ensure_ascii=False, indent=2))
    print("\n" + "\n".join(lines))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
