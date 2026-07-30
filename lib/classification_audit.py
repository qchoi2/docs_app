"""Classification-audit net: detect clause items mistagged across a known-confusion
taxonomy pair by STRUCTURE (subject + mood), not by keyword.

Third safety axis alongside the absence recall-net (omission) and full_read_guard
(heading): MISCLASSIFICATION. 정독 guarantees completeness, not correct classification —
a fully-read clause can still land in the wrong taxonomy node when a trigger word lives
in two very different sentence types.

Seeded with COV.NON_COMPETE ↔ RW.CONTRACTS. "경업금지/non-compete" appears in both:
  - a seller's COVENANT: promisor subject + obligation mood
    ("매도인은 … 하여서는 아니 된다" / "Seller shall not compete").  -> keep COV.NON_COMPETE
  - a disclosure REP enumerating the target's contracts that contain a non-compete
    clause ("경업금지 조항을 포함하고 있는 계약").                      -> belongs in RW.CONTRACTS
The classifier keyed on the word alone and mislabelled ~1/3 of COV.NON_COMPETE. This net
separates them by mood/subject and only auto-reclassifies the airtight disclosure-rep
bucket; ambiguous items are flagged for review, never silently moved.

Buckets: reclassify (mistagged, safe to move) · keep · noise (heading/TOC fragment) ·
review (uncertain — no change). Read-only unless a caller applies the reclassify bucket.
"""
from __future__ import annotations

import re
import sqlite3
from typing import Dict, List

# --- structural patterns (see module docstring) ---
_NOISE = re.compile(
    r"^\s*((section|article)\b|제\s*[\d.]+\s*조?|\d+(\.\d+)*\.?)\s*\S[^\n]{0,45}$", re.I)
_COV = re.compile(
    # promisor subject (now incl. buyer-side 양수인/매수인 — a buyer non-compete is still
    # a covenant, not a disclosure rep) ... obligation mood. Gap widened 90->160 because
    # real non-compete clauses carry a long scope ("... 대한민국 내에서 (i) ... 사업을") between
    # the subject and the prohibition verb.
    r"(매도인|양도인|양수인|매수인|주주|seller|purchaser|buyer|shareholder).{0,160}"
    r"(하지\s*아니|하지\s*않|않기로|영위할\s*수\s*없|영위하지|경쟁하지|개발.{0,10}생산|"
    r"shall\s+not|covenants?\s+(that|not)|undertakes?\s+not|refrain)",
    re.I | re.S,
)
# The "party + from-closing + for N years" frame is unmistakably a non-compete covenant
# (a disclosure rep never promises on behalf of a party over a term), so it is a covenant
# even when the prohibition verb sits past the 160-char window.
_COV_FRAME = re.compile(
    r"(매도인|양도인|양수인|매수인|주주).{0,20}"
    r"(체결일|거래\s*종결|종결일|클로징).{0,12}(로?부터|이후).{0,120}"
    r"(년간|년\s*동안|개월간|개월\s*동안)",
    re.S,
)
_COV_KR = re.compile(r"경업금지기간|경쟁사업을\s*영위(하지|할\s*수\s*없)|경쟁을\s*하지")
_REP = re.compile(
    r"포함하?(고\s*있)?는\s*계약|포함한\s*계약|조항을\s*포함|자유롭게\s*사업을\s*영위할\s*수\s*없도록|"
    r"제약하는\s*계약|제한하는\s*내용의\s*계약|"
    # material-contracts disclosure rep: "중요(한) 계약(은/는) ... 유효/적법하게 체결/제공/구속력"
    # (a representation about the target's contracts, never a promise — the reclassify
    # path already excludes anything with obligation mood).
    r"중요\s*계약(은|는|의|,|\s)[^가-힣]{0,4}[가-힣].{0,90}(유효|적법하게\s*체결|제공되었|구속력\s*있는\s*의무)|"
    r"contracts?\s+(that\s+contain|containing|which\s+contain|that\s+limit|that\s+restrict)|"
    r"any\s+contract[^.]{0,60}(contain|limit|restrict)|provision\s+restricting|"
    r"non[-\s]?competition\s+agreements?\s+or\s+other\s+contracts|"
    r"contracts?\s+restricting\s+(all\s+or\s+a\s+part|the\s+business)",
    re.I | re.S,
)
# A table-of-contents fragment carries 3+ "N.NN Title" section markers — never a clause.
_TOC = re.compile(r"\d+\.\d{2}\s+[A-Z]")
# Any obligation mood anywhere => promissory, not a pure disclosure noun-phrase => never
# auto-reclassify (protects buyer-side / oddly-phrased covenants the _COV subject list misses).
_OBLIG = re.compile(
    r"아니\s*된다|아니\s*한다|해서는\s*안|할\s*수\s*없다|하여서는|하지\s*아니하|하지\s*않기로|"
    r"shall\s+not|agree[s]?\s+not|covenant|아니\s*되며",
    re.I,
)

# Known-confusion rules. Keyed by the currently-stored node.
CONFUSION_RULES: Dict[str, dict] = {
    "COV.NON_COMPETE": {
        "target": "RW.CONTRACTS",
        "keep": "covenant (매도인 promise)",
        "reclassify": "disclosure rep (경업금지 조항 포함 계약 열거)",
    },
}

_MIN_LEN = 30


def classify_verbatim(node: str, verbatim: str) -> str:
    """Bucket one item's verbatim for a confusion node: 'reclassify' | 'keep' | 'noise'
    | 'review'. Only COV.NON_COMPETE has structural rules today; other nodes -> 'review'."""
    v = (verbatim or "").strip()
    if node != "COV.NON_COMPETE":
        return "review"
    # keep is checked before noise so a short/numbered line that is a real covenant
    # ("6.2 매도인은 … 영위할 수 없다") is not mislabelled a heading.
    if _COV.search(v) or _COV_KR.search(v) or _COV_FRAME.search(v):
        return "keep"
    if len(v) < _MIN_LEN or _NOISE.match(v) or len(_TOC.findall(v)) >= 3:
        return "noise"
    if _REP.search(v) and not _OBLIG.search(v):
        return "reclassify"
    return "review"


def audit_node(conn: sqlite3.Connection, node: str) -> List[dict]:
    """Classify every item currently tagged `node`. Read-only."""
    rows = conn.execute(
        "SELECT item_id, file_key, item_ref, family, verbatim "
        "FROM v4_clause_item WHERE taxonomy_id=?",
        (node,),
    ).fetchall()
    out = []
    for item_id, file_key, item_ref, family, verbatim in rows:
        out.append({
            "item_id": item_id, "file_key": file_key, "item_ref": item_ref,
            "family": family, "verbatim": verbatim,
            "bucket": classify_verbatim(node, verbatim),
        })
    return out


def summarize(items: List[dict]) -> Dict[str, int]:
    from collections import Counter
    return dict(Counter(it["bucket"] for it in items))
