"""Over-/under-extraction gate for re-extraction stores (V4_PLAN §9.3, root fix ③).

A proofread result is authoritative, but two failure modes can still slip in and
corrupt the golden set: OVER-extraction (one ¶ shotgunned into many pseudo-items,
or the same text tagged twice) and HALLUCINATION (a verbatim not actually in the
source). ``gate_items`` screens a family's items BEFORE any DELETE/INSERT so a bad
result can never half-write a document.

The gate is deliberately NON-BLOCKING and NON-DESTRUCTIVE except for provably-
identical rows: whole-doc rejection proved too coarse (one stray dup pair would
drop dozens of good items), and taxonomy-shotgun density needs taxonomy judgment
(a separate semantic-review lane), so suspected over-extraction is surfaced as
flags for owner review, not blocked.

  - exact-duplicate items (identical FULL tuple) -> auto-collapsed (safe, silent)
  - duplicate_verbatim (same text+tag, overlapping ¶ span) -> flagged
  - dense ¶ (>= DENSITY_SHOTGUN_SEVERE marked severe) -> flagged
  - low char-shingle coverage of a verbatim in the txt cache -> flagged (grounding;
    coverage tolerates redline/mark-up txt artifacts; a mostly-ungrounded doc
    becomes one grounding_suspect flag — that signals a poor txt extraction, not
    N distinct hallucinations)

Family-agnostic: pass the family the items will be stored under. The reject path
(``gate_items`` returning a status dict) is retained but currently unused; per-
signal hard-blocking can be enabled once thresholds are calibrated.
"""

from __future__ import annotations

import sqlite3
import unicodedata
from pathlib import Path

from audit_t3_v4 import oversegmentation_issues
from open_text import read_paragraphs

DENSITY_SHOTGUN_SEVERE = 8    # a ¶ with >= this many items is marked severe for review
GROUNDING_MIN_LEN = 12        # only grounding-check verbatims with >= this many norm chars
GROUNDING_MIN_COVERAGE = 0.7  # fraction of a verbatim's char-shingles that must appear in txt
GROUNDING_SUSPECT_RATE = 0.5  # above this ungrounded fraction the txt cache itself is suspect


def _norm(s) -> str:
    """Grounding normalizer: NFKC + case-fold + whitespace-strip, so Unicode/case/spacing
    differences between a proofread verbatim and the txt cache do not cause false misses."""
    return "".join(unicodedata.normalize("NFKC", str(s or "")).split()).casefold()


def dup_tuple(it: dict) -> tuple:
    """Full semantic identity of an item — two items with the same tuple are redundant
    copies (verbatim is whitespace-insensitive but case-sensitive on purpose)."""
    return (
        "".join(str(it.get("verbatim") or "").split()), str(it.get("proposition") or ""),
        it.get("statement_polarity"), it.get("subject_role"),
        it.get("counterparty_role"), it.get("action"), it.get("object_type"),
        it.get("effective_time"), it.get("taxonomy_id"),
    )


def grounding_coverage(verbatim, doc_norm: str):
    """Fraction of a verbatim's overlapping char-shingles present in the document text.
    Tolerant of the interruptions redline/mark-up txt caches insert ("[deleted]", merged
    numbering) that defeat a contiguous-substring check, while a hallucinated verbatim
    (few shingles present) still scores near zero. None if the verbatim is too short."""
    v = _norm(verbatim)
    if len(v) < GROUNDING_MIN_LEN:
        return None
    w = 12
    shingles = [v[i:i + w] for i in range(0, len(v) - w + 1, 6)] or [v]
    return sum(1 for sh in shingles if sh in doc_norm) / len(shingles)


def doc_text_compact(conn: sqlite3.Connection, out: Path, file_key: str):
    """NFKC/case/whitespace-normalized full document text (markers removed) for grounding,
    or None if the txt cache is unavailable. Reads the file directly; the txt_path lookup
    reuses the caller's connection to avoid a nested DB connection."""
    row = conn.execute("SELECT txt_path FROM files WHERE file_key=?", (file_key,)).fetchone()
    rel = (row[0] if row and row[0] else f"txt/{file_key}.txt")
    path = Path(rel)
    if not path.is_absolute():
        path = out / path
    if not path.exists():
        return None
    return _norm(" ".join(text for _n, text in read_paragraphs(path)))


def gate_items(conn: sqlite3.Connection, out: Path, file_key: str, items: list, family: str):
    """Screen a proofread result for over-extraction / hallucination.

    Returns (kept_items, flags, reject). ``reject`` is None to proceed, or a status dict
    to return from the caller's store_one WITHOUT touching the DB. ``flags`` is advisory
    metadata (deduped count, dense paragraphs, grounding misses) stored with the doc and
    surfaced in the run report.
    """
    flags: dict = {}

    # (1) auto-collapse exact-duplicate items (identical full tuple) — provably safe,
    #     prevents re-introducing the redundancy a prior bulk pass produced.
    seen: set = set()
    kept = []
    for it in items:
        k = dup_tuple(it)
        if k in seen:
            continue
        seen.add(k)
        kept.append(it)
    if len(kept) != len(items):
        flags["deduped"] = len(items) - len(kept)

    # (2) over-segmentation: reuse the audit's family-agnostic detector on the items as
    #     they will be stored. Everything here is FLAGGED, not blocked.
    probe = [{**it, "family": family} for it in kept]
    findings = oversegmentation_issues({"items": probe})
    dense, dup = [], []
    for f in findings:
        if f["code"] == "paragraph_oversegmented":
            dense.append({"loc_start": f["detail"]["loc_start"],
                          "item_count": f["detail"]["item_count"]})
        elif f["code"] in ("duplicate_verbatim", "duplicate_verbatim_substring"):
            dup.append({"code": f["code"],
                        "loc_start": f["detail"].get("loc_start"),
                        "item_refs": f["detail"].get("item_refs")})
    if dense:
        dense.sort(key=lambda d: -d["item_count"])
        flags["dense_paragraphs"] = dense
        if dense[0]["item_count"] >= DENSITY_SHOTGUN_SEVERE:
            flags["shotgun_severe"] = dense[0]["item_count"]
    if dup:
        flags["duplicate_verbatim"] = dup

    # (3) grounding: every substantive verbatim should appear in the source text.
    doc = doc_text_compact(conn, out, file_key)
    if doc is None:
        flags["txt_unavailable"] = True
    else:
        ungrounded, checked = [], 0
        for i, it in enumerate(kept, 1):
            cov = grounding_coverage(it.get("verbatim"), doc)
            if cov is None:
                continue
            checked += 1
            if cov < GROUNDING_MIN_COVERAGE:
                ungrounded.append(it.get("item_ref") or f"#{i}")
        if ungrounded:
            if checked and len(ungrounded) / checked > GROUNDING_SUSPECT_RATE:
                flags["grounding_suspect"] = {"ungrounded": len(ungrounded), "checked": checked}
            else:
                flags["ungrounded"] = ungrounded[:20]
                if len(ungrounded) > 20:
                    flags["ungrounded_count"] = len(ungrounded)

    return kept, flags, None
