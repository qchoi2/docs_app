"""Measure CP/COV/REM auto-extraction defect rate against a full_read result JSON.

Phase 0-4 (measure-first). CP/COV/REM/DEF are 100% original auto-extraction
(codex-context-review-1). This diffs a coordinator full_read (authoritative) against
the existing auto items for the same document, WITHOUT storing (storing would clobber
the doc's already-re-extracted RW). Read-only.

For each family in {CP,COV,REM}, matching by paragraph-loc overlap (loc_start/loc_end):
  correct        auto item overlaps a full_read item of the same sub-domain
  misclassified  auto item overlaps a full_read item of a DIFFERENT family/sub-domain
  over_extracted auto item overlaps NO full_read item and is heading/TOC/short-like
                 (the auto item is a boundary/over-extraction artifact the read rejected)
  unmatched_auto auto item overlaps no full_read item but is substantive (needs eyeball)
  missed         full_read item overlaps NO auto item (auto missed this clause)

Usage: python measure_cpcovrem.py <result.json> [<result2.json> ...]
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

OUT = Path("cs_index")
FAMS = ("CP", "COV", "REM")
_TOC = re.compile(r"^\s*((section|article)\b|제\s*[\d.]+\s*조?|\d+(\.\d+)*\.?)\s*\S[^\n]{0,45}$", re.I)


def lineage_match(x: str, y: str) -> bool:
    """Same taxonomy lineage: one tag is a prefix (ancestor) of the other. Treats a
    coarser auto tag ('CP') vs the read's finer child ('CP.THIRD_PARTY_CONSENT') as a
    match (under-specified, not wrong); only a genuinely different branch (REM.BASKET.
    TIPPING vs .DEDUCTIBLE, or COV.* vs REM.*) counts as misclassified."""
    xs, ys = str(x or "").split("."), str(y or "").split(".")
    n = min(len(xs), len(ys))
    return n > 0 and xs[:n] == ys[:n]


def _int(x, d=-1):
    try:
        return int(x)
    except (TypeError, ValueError):
        return d


def overlaps(a0, a1, b0, b1):
    a1 = max(a1, a0); b1 = max(b1, b0)
    return a0 >= 0 and b0 >= 0 and a0 <= b1 and b0 <= a1


def load_read_items(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    fk = str(data.get("file_key") or path.stem)
    items = []
    for it in data.get("items", []):
        items.append({
            "family": it.get("family"), "taxonomy_id": it.get("taxonomy_id"),
            "loc_start": _int(it.get("loc_start")), "loc_end": _int(it.get("loc_end")),
            "verbatim": it.get("verbatim") or "",
        })
    return fk, items, data.get("review_method")


def measure(path: Path):
    fk, read_items, rm = load_read_items(path)
    conn = sqlite3.connect(f"file:{OUT/'catalog.sqlite'}?mode=ro", uri=True)
    auto = [{"taxonomy_id": r[0], "family": r[1], "loc_start": _int(r[2]),
             "loc_end": _int(r[3]), "verbatim": r[4] or "", "extractor_version": r[5]}
            for r in conn.execute(
                "SELECT taxonomy_id,family,loc_start,loc_end,verbatim,extractor_version "
                "FROM v4_clause_item WHERE file_key=?", (fk,))]
    report = {"file_key": fk, "review_method": rm, "read_items_total": len(read_items),
              "auto_items_total": len(auto), "by_family": {}}
    for fam in FAMS:
        auto_f = [a for a in auto if a["family"] == fam]
        read_f = [r for r in read_items if r["family"] == fam]
        buckets = {"correct": 0, "misclassified": 0, "over_extracted": 0,
                   "unmatched_auto": 0, "missed": 0}
        misclass_ex, over_ex, missed_ex = [], [], []
        for a in auto_f:
            ov = [r for r in read_items if overlaps(a["loc_start"], a["loc_end"], r["loc_start"], r["loc_end"])]
            if not ov:
                v = " ".join(str(a["verbatim"]).split())
                if len(v) < 30 or _TOC.match(v):
                    buckets["over_extracted"] += 1
                    if len(over_ex) < 6: over_ex.append(f"¶{a['loc_start']} [{a['taxonomy_id']}] {v[:70]}")
                else:
                    buckets["unmatched_auto"] += 1
            elif any(lineage_match(r["taxonomy_id"], a["taxonomy_id"]) for r in ov):
                buckets["correct"] += 1
            else:
                buckets["misclassified"] += 1
                if len(misclass_ex) < 6:
                    tgt = ",".join(sorted({r["taxonomy_id"] for r in ov})[:2])
                    misclass_ex.append(f"¶{a['loc_start']} auto={a['taxonomy_id']} -> read={tgt}")
        for r in read_f:
            if not any(overlaps(r["loc_start"], r["loc_end"], a["loc_start"], a["loc_end"]) for a in auto):
                buckets["missed"] += 1
                if len(missed_ex) < 6:
                    missed_ex.append(f"¶{r['loc_start']} [{r['taxonomy_id']}] {' '.join(str(r['verbatim']).split())[:70]}")
        denom = len(auto_f) or 1
        report["by_family"][fam] = {
            "auto_items": len(auto_f), "read_items": len(read_f), **buckets,
            "precision_auto": round(buckets["correct"] / denom, 3),
            "misclass_rate": round(buckets["misclassified"] / denom, 3),
            "over_extract_rate": round(buckets["over_extracted"] / denom, 3),
            "examples": {"misclassified": misclass_ex, "over_extracted": over_ex, "missed": missed_ex},
        }
    return report


def main(argv=None):
    from lib.console import configure_utf8_stdio
    configure_utf8_stdio()
    paths = [Path(p) for p in (argv or sys.argv[1:])]
    if not paths:
        print("usage: python measure_cpcovrem.py <result.json> [...]"); return 1
    reports = [measure(p) for p in paths if p.exists()]
    # aggregate
    agg = {fam: {k: 0 for k in ("auto_items", "correct", "misclassified", "over_extracted", "unmatched_auto", "missed", "read_items")} for fam in FAMS}
    for rep in reports:
        for fam in FAMS:
            for k in agg[fam]:
                agg[fam][k] += rep["by_family"][fam][k]
    for fam in FAMS:
        d = agg[fam]["auto_items"] or 1
        agg[fam]["precision_auto"] = round(agg[fam]["correct"] / d, 3)
        agg[fam]["misclass_rate"] = round(agg[fam]["misclassified"] / d, 3)
        agg[fam]["over_extract_rate"] = round(agg[fam]["over_extracted"] / d, 3)
    print(json.dumps({"per_doc": reports, "aggregate": agg, "docs": len(reports)},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
