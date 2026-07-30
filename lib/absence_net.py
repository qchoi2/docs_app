"""Absence recall-net: shared vocabulary + scan for false-absence detection (V4_PLAN §9.3).

The breadth half of net-then-confirm. For a taxonomy sub-domain, derive a
Korean/English vocabulary and test whether a document MENTIONS it. A document whose
extraction produced zero items in a sub-domain it demonstrably mentions is a likely
SILENT OMISSION (false absence) — the exact pathology that hid environment reps behind
a blanket 'complete' stamp. This module makes that pathology visible cheaply (no APIs,
no writes; pure text + two yaml dictionaries + taxonomy node names).

Two consumers:
  1. subdomain_absence_pool.py -- corpus-wide standing audit, per sub-domain.
  2. store_*_reextraction.py    -- per-doc guard wired into every re-extraction store,
     so a future re-extraction that marks a family complete while still leaving a
     mentioned sub-domain empty is flagged automatically (res["absence_suspects"]).

Vocabulary is DERIVED, not hand-listed, from three sources (union, de-duped):
  - data/v4_term_mapping.yaml + data/term_dict.yaml: concept term -> node, then the
    concept's curated ko/en synonym variants (richest where present).
  - v4_taxonomy_node.canonical_ko/_en for the node and its subtree: guarantees every
    sub-domain has at least baseline vocabulary (English names are word-split into
    distinctive needles; short/stopword tokens dropped).
  - TERM_SUPPLEMENTS: task-tuned needles not yet in the dictionary (env is seeded).

A sub-domain whose vocabulary is only generic single words will over-flag; callers
should treat an implausibly high suspect rate as "vocabulary too broad, needs curated
terms", not as a clean audit.
"""
from __future__ import annotations

import functools
import json
import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from open_text import read_paragraphs
from lib.normalize import normalize

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"
CS_INDEX = REPO_ROOT / "cs_index"

_EN_MIN_LEN = 4  # Latin needles shorter than this fire on unrelated substrings
_EN_STOP = {"and", "the", "for", "with", "non", "any", "all", "such", "other",
            "from", "into", "plan", "list", "matters", "representation",
            "representations", "warranties", "warranty"}

# Task-mandated needles beyond term_dict, keyed by taxonomy node. Add here (owner
# review) rather than editing term_dict directly; RW.ENVIRONMENT reproduces the tuned
# env_absence_pool.py list so the generalized net matches the original audit.
TERM_SUPPLEMENTS: Dict[str, Dict[str, List[str]]] = {
    "RW.ENVIRONMENT": {
        "ko": [
            "환경", "환경법", "환경법규", "환경 관련 법", "환경인허가", "환경 인허가",
            "환경허가", "오염", "토양오염", "토양 오염", "수질오염", "대기오염",
            "유해물질", "유해 물질", "유해화학물질", "폐기물", "오염물질", "정화", "토양정화",
        ],
        "en": [
            "environmental", "environment", "contamination", "contaminant",
            "contaminated", "hazardous material", "hazardous materials",
            "hazardous substance", "hazardous substances", "pollution", "pollutant",
            "remediation", "remediate", "environmental permit", "environmental law",
            "environmental laws", "environmental regulation", "environmental matters",
        ],
    },
}


def _is_latin(term: str) -> bool:
    return bool(re.search(r"[a-zA-Z]", term)) and not re.search(r"[가-힣]", term)


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@functools.lru_cache(maxsize=1)
def _mapping() -> dict:
    return load_yaml(DATA / "v4_term_mapping.yaml")


@functools.lru_cache(maxsize=1)
def _term_dict() -> dict:
    return load_yaml(DATA / "term_dict.yaml")


def _split_needles(ko_raw: List[str], en_raw: List[str]) -> Tuple[List[str], List[str]]:
    """Route mixed-script needles to Korean-substring vs Latin-word matchers, casefold,
    drop short/stopword Latin tokens, de-dup preserving order."""
    ko: List[str] = []
    en: List[str] = []
    for t in list(ko_raw) + list(en_raw):
        if not t:
            continue
        if _is_latin(t):
            # An English canonical name may be a phrase ("No asset encumbrance"); split
            # into distinctive words so it matches however the doc phrases the concept.
            for w in re.findall(r"[a-zA-Z]+", t.casefold()):
                if len(w) >= _EN_MIN_LEN and w not in _EN_STOP:
                    en.append(w)
        else:
            ko.append(t.casefold())
    return list(dict.fromkeys(ko)), list(dict.fromkeys(en))


def derive_terms(
    subdomain: str,
    mapping: dict,
    term_dict: dict,
    supplements: Optional[Dict[str, Dict[str, List[str]]]] = None,
    node_names: Optional[List[Tuple[str, str]]] = None,
) -> Tuple[List[str], List[str], List[str]]:
    """(ko_needles, en_needles, source_canonicals) for a taxonomy node.

    A concept contributes its synonyms when mapped to the node or a node in its subtree.
    ``node_names`` (optional (ko, en) canonical pairs for the subtree) supply baseline
    vocabulary for sub-domains no concept maps to. Supplements for the node are merged."""
    supplements = supplements if supplements is not None else TERM_SUPPLEMENTS
    prefix = subdomain + "."
    canon_for_node: List[str] = []
    for canonical, nodes in (mapping.get("mappings") or {}).items():
        if any(n == subdomain or n.startswith(prefix) for n in nodes):
            canon_for_node.append(canonical)

    by_canonical = {t.get("canonical"): t for t in (term_dict.get("terms") or [])}
    ko_raw: List[str] = []
    en_raw: List[str] = []
    for canonical in canon_for_node:
        entry = by_canonical.get(canonical) or {}
        ko_raw += entry.get("ko") or []
        en_raw += entry.get("en") or []
    for ko_name, en_name in (node_names or []):
        if ko_name:
            ko_raw.append(ko_name)
        if en_name:
            en_raw.append(en_name)
    sup = supplements.get(subdomain, {})
    ko_raw += sup.get("ko") or []
    en_raw += sup.get("en") or []

    ko_needles, en_needles = _split_needles(ko_raw, en_raw)
    return ko_needles, en_needles, canon_for_node


def text_hits(folded: str, ko_needles: List[str], en_patterns) -> List[str]:
    """Distinct matched terms in an already-normalized+casefolded text."""
    hits: List[str] = []
    for t in ko_needles:
        if t in folded:
            hits.append(t)
    for t, pat in en_patterns:
        if pat.search(folded):
            hits.append(t)
    return hits


def compile_en(en_needles: List[str]):
    return [(t, re.compile(r"\b" + re.escape(t) + r"\b")) for t in en_needles]


def compile_any(ko_needles: List[str], en_needles: List[str]):
    """One combined pattern that matches ANY needle (Korean as substring, Latin word-
    bounded). A single C-level search replaces the per-needle Python loop — used as a
    fast boolean gate before the detailed, term-attributing scan. None if no needles."""
    parts = [re.escape(t) for t in ko_needles]
    parts += [r"\b" + re.escape(t) + r"\b" for t in en_needles]
    return re.compile("|".join(parts)) if parts else None


def resolve_txt(out: Path, file_key: str, txt_path: Optional[str]) -> Optional[Path]:
    cs = Path(out)
    candidates: List[Path] = []
    if txt_path:
        p = Path(txt_path)
        candidates.append(p if p.is_absolute() else cs / p)
    candidates.append(cs / "txt" / f"{file_key}.txt")
    for c in candidates:
        if c.exists():
            return c
    return None


def doc_folded(conn: sqlite3.Connection, out: Path, file_key: str) -> Optional[str]:
    """Whole-document normalized+casefolded text (markers stripped), or None if the
    txt cache is unavailable. Reuses the caller's connection for the path lookup."""
    row = conn.execute("SELECT txt_path FROM files WHERE file_key=?", (file_key,)).fetchone()
    path = resolve_txt(out, file_key, row[0] if row else None)
    if path is None:
        return None
    return normalize(" ".join(text for _n, text in read_paragraphs(path))).casefold()


def family_subdomains(conn: sqlite3.Connection, family: str) -> List[str]:
    """Distinct 2-segment sub-domains present in the taxonomy for a family."""
    seen: Dict[str, None] = {}
    for (t,) in conn.execute(
        "SELECT taxonomy_id FROM v4_taxonomy_node WHERE family=?", (family,)
    ):
        parts = str(t).split(".")
        if len(parts) >= 2:
            seen.setdefault(".".join(parts[:2]), None)
    return sorted(seen)


def _node_names(conn: sqlite3.Connection, subdomain: str) -> List[Tuple[str, str]]:
    rows = conn.execute(
        "SELECT canonical_ko, canonical_en FROM v4_taxonomy_node "
        "WHERE taxonomy_id=? OR taxonomy_id LIKE ?",
        (subdomain, subdomain + ".%"),
    ).fetchall()
    return [(ko or "", en or "") for ko, en in rows]


DF_MAX = 0.5           # a needle appearing in > this fraction of docs is non-discriminating
DF_CACHE = "absence_net_df.json"  # under the index dir; built by build_needle_df


@functools.lru_cache(maxsize=4)
def _needle_df(out: str) -> dict:
    """{needle: doc-frequency fraction} from the DF cache, or {} if not built yet.
    Keyed by str(out) so the lru_cache holds per-index caches."""
    p = Path(out) / DF_CACHE
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("df", {})
    except (ValueError, OSError):
        return {}


def _drop_high_df(needles: List[str], df: dict) -> List[str]:
    """Remove needles that appear in > DF_MAX of the corpus — generic words like
    'material', 'agreement', 'capital', '환경'(경영환경) that fire regardless of the
    specific rep. Needles absent from the cache are kept (unknown DF)."""
    return [t for t in needles if df.get(t, 0.0) <= DF_MAX]


def build_vocab_for(conn: sqlite3.Connection, subdomain: str, out: Path = CS_INDEX,
                    apply_df: bool = False):
    """(ko_needles, en_patterns, source_canonicals) for one sub-domain, from all sources.

    The recall net's job is CANDIDATE GENERATION (150-selection, owner worksheets), where
    over-inclusion is fine because a human/heading-guard verdicts downstream — so DF
    filtering is OFF by default to preserve recall. A corpus-DF cut is too blunt to enable
    globally: it drops legitimate-but-common core terms (인사/자산/소송, DF>0.5) alongside
    generic noise (material/agreement). Opt in with apply_df=True only for a precision view.
    """
    ko, en, canon = derive_terms(
        subdomain, _mapping(), _term_dict(), node_names=_node_names(conn, subdomain)
    )
    if apply_df:
        df = _needle_df(str(out))
        if df:
            ko, en = _drop_high_df(ko, df), _drop_high_df(en, df)
    return ko, compile_en(en), canon


def build_needle_df(conn: sqlite3.Connection, out: Path = CS_INDEX,
                    families: Tuple[str, ...] = ("RW", "PAY", "DEF", "COV", "REM", "CP")) -> dict:
    """Compute each needle's document-frequency over all ok/non-empty docs and write it to
    the DF cache. One-time (re-run when the corpus or vocabulary changes). Read-only on the
    DB. Uses the UNFILTERED derivation so the cache is independent of its own output."""
    all_ko: set = set()
    all_en: set = set()
    for fam in families:
        for sd in family_subdomains(conn, fam):
            ko, en, _c = derive_terms(sd, _mapping(), _term_dict(),
                                      node_names=_node_names(conn, sd))
            all_ko |= set(ko)
            all_en |= set(en)
    en_pats = [(t, re.compile(r"\b" + re.escape(t) + r"\b")) for t in all_en]
    rows = conn.execute(
        "SELECT file_key, txt_path FROM files WHERE status='ok' AND COALESCE(char_count,0)>0"
    ).fetchall()
    from collections import Counter
    dfc: Counter = Counter()
    n = 0
    for file_key, txt_path in rows:
        path = resolve_txt(out, file_key, txt_path)
        if path is None:
            continue
        folded = normalize(" ".join(t for _n, t in read_paragraphs(path))).casefold()
        if not folded:
            continue
        n += 1
        for t in all_ko:
            if t in folded:
                dfc[t] += 1
        for t, pat in en_pats:
            if pat.search(folded):
                dfc[t] += 1
    df = {t: round(c / n, 4) for t, c in dfc.items()} if n else {}
    payload = {"docs": n, "df_max": DF_MAX, "df": df}
    (Path(out) / DF_CACHE).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _needle_df.cache_clear()
    return payload


_VOCAB_CACHE: Dict[Tuple[int, str], Dict[str, tuple]] = {}


def family_vocab(conn: sqlite3.Connection, family: str) -> Dict[str, tuple]:
    """{subdomain: (ko_needles, en_patterns, canonicals)} for a family, built once per
    (connection, family)."""
    key = (id(conn), family)
    if key not in _VOCAB_CACHE:
        _VOCAB_CACHE[key] = {
            sd: build_vocab_for(conn, sd) for sd in family_subdomains(conn, family)
        }
    return _VOCAB_CACHE[key]


def covered_subdomains(conn: sqlite3.Connection, file_key: str, family: str,
                       subdomains: List[str]) -> set:
    """Sub-domains for which the document currently has >= 1 stored item."""
    tids = [r[0] for r in conn.execute(
        "SELECT DISTINCT taxonomy_id FROM v4_clause_item WHERE file_key=? AND family=?",
        (file_key, family),
    )]
    return {sd for sd in subdomains
            if any(t == sd or str(t).startswith(sd + ".") for t in tids)}


def doc_absence_suspects(conn: sqlite3.Connection, out: Path, file_key: str,
                         family: str, max_terms: int = 8) -> Dict[str, List[str]]:
    """Sub-domains the document MENTIONS but has ZERO stored items for -> likely missed
    extraction. Reads items in the caller's transaction (sees uncommitted inserts), so a
    store can call this right after inserting to self-verify. {} when clean."""
    vocab = family_vocab(conn, family)
    if not vocab:
        return {}
    covered = covered_subdomains(conn, file_key, family, list(vocab))
    uncovered = [sd for sd in vocab if sd not in covered]
    if not uncovered:
        return {}
    folded = doc_folded(conn, out, file_key)
    if not folded:
        return {}
    suspects: Dict[str, List[str]] = {}
    for sd in uncovered:
        ko, en_pat, _canon = vocab[sd]
        matched = text_hits(folded, ko, en_pat)
        if matched:
            suspects[sd] = matched[:max_terms]
    return suspects
