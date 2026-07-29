"""Admission policy for ``v4_taxonomy_candidate`` rows.

Implements the second half of the owner decision in ``.docs/V4_PLAN.md`` §9.2
T-D ("후보 생성기를 조인다") together with 교정 A·B of
``.docs/PLAN_REVIEW_20260727.md`` §"항목 2 심화".

Why this module exists
----------------------
Every unclassified paragraph used to mint its own row in
``v4_taxonomy_candidate``.  A *global* taxonomy candidate is a proposal to grow
the controlled taxonomy, so it only makes sense for wording that recurs across
contracts.  A one-off, document-specific definition or list item is not a
taxonomy proposal at all -- it is just text that the rule-based classifier could
not place.  Minting a candidate for it produced the 29,807-row backlog while
adding nothing reviewable.

Three rules live here, in one place, so every writer shares them:

1. **Admission** (:func:`admit`) -- a proposed candidate becomes a pending
   ``v4_taxonomy_candidate`` row only when it looks *general*.  Otherwise it is
   absorbed into the family catch-all as a normal ``v4_clause_item`` so it stays
   FTS-searchable (V4_PLAN 원칙 5 / §4).
2. **Naming** (:func:`candidate_name`, 교정 A) -- DEF candidates are named by the
   term they define, never by the paragraph position.  ``정의 ¶18`` means a
   different thing in every contract, so position-based names made name
   recurrence actively misleading.
3. **Recurrence** (:func:`recurrence_key`, 교정 B) -- generality is measured on a
   normalized key (defined term for DEF, digit-masked text signature otherwise),
   which is what ``document_count`` counts.

The module is intentionally dependency-free (stdlib only) so ``v4_schema`` and
the offline tools can all import it without a cycle.
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from typing import Iterable, Mapping, NamedTuple, Sequence


FAMILIES = ("RW", "CP", "COV", "DEF", "PAY", "REM")

#: A candidate must be attested in at least this many distinct documents before
#: it is worth proposing as a *global* taxonomy node.
GENERIC_MIN_DOCUMENTS = 2

#: Family catch-all node that absorbs document-specific one-offs.  Only DEF has
#: a dedicated catch-all leaf; for the other families the family root itself is
#: the "inside this family but not placed under any sub-node" bucket.  A root
#: item never satisfies a sub-node absence query, so absorbing here cannot
#: manufacture a false "present" for ``RW.TAX`` and friends.
CATCH_ALL_TAXONOMY_ID = {
    "DEF": "DEF.CONTRACT_TERM",
    "RW": "RW",
    "CP": "CP",
    "COV": "COV",
    "PAY": "PAY",
    "REM": "REM",
}

#: Stamped on absorbed items so an audit can tell them apart from reviewed ones.
ABSORBED_MARKER = "absorbed_one_off"
POLICY_VERSION = "v4-candidate-admission-1"

_QUOTE = "\"“”‘’「」『』"
_QUOTED_TERM = r"[%s]([^%s\n]{1,80})[%s]" % (_QUOTE, _QUOTE, _QUOTE)

# Definition grammars, most specific first.  All of them require an explicit
# quoted term: an unquoted match ("... 라 함은") drags in whole sentence
# fragments and produced junk names such as "대한민국 서울 강남구 테헤".
_DEFINITION_PATTERNS = (
    re.compile(
        r"^\s*%s\s*(?:은|는|이란|란|이라\s*함은|라\s*함은|이라\s*한다|이라고\s*한다)"
        % _QUOTED_TERM
    ),
    re.compile(
        r"^\s*%s\s*(?:\([^)]{0,40}\)\s*)?(?:shall\s+)?"
        r"(?:mean|means|has\s+the\s+meaning|have\s+the\s+meaning|is\s+defined)"
        % _QUOTED_TERM,
        re.IGNORECASE,
    ),
    re.compile(
        r"%s\s*(?:이란|란|이라\s*함은|라\s*함은|이라\s*한다)" % _QUOTED_TERM
    ),
    re.compile(
        r"%s\s*(?:shall\s+)?(?:mean|means|has\s+the\s+meaning|have\s+the\s+meaning)"
        % _QUOTED_TERM,
        re.IGNORECASE,
    ),
)

_TERM_TRIM = " \t\r\n" + _QUOTE + "()[]{}<>:;,.·"
_PARTICLE_RE = re.compile(r"(?:이란|란|이라|은|는|이|가|의|을|를)$")
_NON_SIGNIFICANT_RE = re.compile(r"[^0-9a-z가-힣#]+")
_DIGIT_RE = re.compile(r"\d+")


class Admission(NamedTuple):
    """Outcome of the admission gate for one proposed candidate."""

    admitted: bool
    reason: str
    recurrence_key: str
    document_count: int
    catch_all_taxonomy_id: str


def catch_all_taxonomy_id(family: str) -> str:
    """Return the node that absorbs one-off evidence for ``family``."""

    return CATCH_ALL_TAXONOMY_ID.get(str(family), str(family))


def defined_term(text: str) -> str | None:
    """Return the term a definition paragraph defines, if it states one.

    Deliberately stricter than the extractor in ``finalize_v4_remaining_nine``:
    that one gates *item* creation, this one gates a *global taxonomy name*, so
    a wrong term is more expensive than a missing one.
    """

    if not text:
        return None
    for pattern in _DEFINITION_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        term = str(match.group(1) or "").strip(_TERM_TRIM)
        term = " ".join(term.split())
        if term and not term.isdigit():
            return term
    return None


def normalize_term(value: str) -> str:
    """Fold a defined term so the same term matches across documents."""

    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = text.strip(_TERM_TRIM)
    text = "".join(text.split())
    text = _PARTICLE_RE.sub("", text)
    return _NON_SIGNIFICANT_RE.sub("", text)


def normalize_proposition(value: str) -> str:
    """Fold paragraph text into a cross-document signature.

    Digits are masked because thresholds (``금 1억원``/``KRW 100,000,000``) and
    article numbers are the part that legitimately varies between contracts that
    otherwise share identical boilerplate.
    """

    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = _DIGIT_RE.sub("#", text)
    return _NON_SIGNIFICANT_RE.sub("", text)


def recurrence_key(family: str, verbatim: str) -> str:
    """Return the key on which cross-document recurrence is counted (교정 B).

    DEF paragraphs that actually state a term key on the *term*; everything else
    keys on a normalized text signature.  Position is never part of the key --
    that was the defect 교정 A names.
    """

    family = str(family)
    if family == "DEF":
        term = defined_term(verbatim)
        if term:
            normalized = normalize_term(term)
            if normalized:
                return f"DEF.TERM:{normalized}"
    return f"{family}.TEXT:{normalize_proposition(verbatim)}"


def candidate_name(
    family: str,
    verbatim: str,
    *,
    source_name: str | None = None,
    loc_start: int | None = None,
) -> str:
    """Build the ``proposed_ko`` label for a candidate (교정 A).

    A DEF candidate is named by the term it defines.  Only when no term can be
    read does the label fall back to a positional label -- and such a candidate
    fails :func:`admit` anyway unless its text recurs, so the misleading
    positional name can no longer masquerade as cross-document recurrence.
    """

    if str(family) == "DEF":
        term = defined_term(verbatim)
        if term:
            return f"정의용어 후보: {term}"
    location = f"¶{int(loc_start)}" if loc_start is not None else "¶?"
    where = str(source_name or "본문").strip() or "본문"
    return f"검토후보: {where} {location} 명제"


CANDIDATE_NAME_PREFIXES = ("검토후보: ", "정의용어 후보: ")


def strip_candidate_prefix(value: str | None) -> str:
    """Drop the label prefix so a candidate name can seed a taxonomy label."""

    text = str(value or "")
    for prefix in CANDIDATE_NAME_PREFIXES:
        if text.startswith(prefix):
            return text[len(prefix) :].strip()
    return text.strip()


def is_generic(
    *,
    recommended_parent_id: str | None,
    document_count: int,
    min_documents: int = GENERIC_MIN_DOCUMENTS,
) -> bool:
    """The admission predicate, stated once.

    A proposed candidate is *general* -- and therefore worth a global taxonomy
    row -- when either:

    * ``recommended_parent_id`` names a specific sub-node (it contains a dot,
      e.g. ``RW.TAX``): the generator already placed it beside a real
      sub-domain, so it describes a sub-domain gap rather than stray text; or
    * its recurrence key is attested in ``min_documents`` or more distinct
      documents: the wording is contract-general, not document-specific.

    Everything else -- a bare family-root parent *and* a single attesting
    document -- is a document-specific one-off.
    """

    dotted = "." in str(recommended_parent_id or "")
    return dotted or int(document_count or 0) >= int(min_documents)


def admit(
    *,
    family: str,
    verbatim: str,
    recommended_parent_id: str | None,
    document_count: int,
    min_documents: int = GENERIC_MIN_DOCUMENTS,
) -> Admission:
    """Apply :func:`is_generic` and report why."""

    key = recurrence_key(family, verbatim)
    generic = is_generic(
        recommended_parent_id=recommended_parent_id,
        document_count=document_count,
        min_documents=min_documents,
    )
    if generic:
        reason = (
            "specific_parent"
            if "." in str(recommended_parent_id or "")
            else "recurs_across_documents"
        )
    else:
        reason = "document_specific_one_off"
    return Admission(
        admitted=generic,
        reason=reason,
        recurrence_key=key,
        document_count=int(document_count or 0),
        catch_all_taxonomy_id=catch_all_taxonomy_id(family),
    )


# ---------------------------------------------------------------------------
# Recurrence bookkeeping (교정 B): the real "발견 문서 수 자동 갱신"
# ---------------------------------------------------------------------------

RECURRENCE_DDL = (
    """
    CREATE TABLE IF NOT EXISTS v4_candidate_recurrence (
      recurrence_key TEXT NOT NULL,
      file_key TEXT NOT NULL,
      family TEXT NOT NULL,
      origin TEXT NOT NULL DEFAULT 'candidate',
      updated_at TEXT,
      PRIMARY KEY (recurrence_key, file_key)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_v4_candidate_recurrence_key
      ON v4_candidate_recurrence(recurrence_key)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_v4_candidate_recurrence_file
      ON v4_candidate_recurrence(file_key)
    """,
)


def ensure_recurrence_table(conn: sqlite3.Connection) -> None:
    """Create the recurrence index.

    Uses individual statements rather than ``executescript`` because callers run
    inside an open transaction and ``executescript`` would commit it.
    """

    for statement in RECURRENCE_DDL:
        conn.execute(statement)


def clear_document_recurrence(conn: sqlite3.Connection, file_key: str) -> None:
    """Drop a document's attestations before its rows are rewritten."""

    conn.execute(
        "DELETE FROM v4_candidate_recurrence WHERE file_key=?", (str(file_key),)
    )


def record_recurrence(
    conn: sqlite3.Connection,
    *,
    file_key: str,
    family: str,
    recurrence_key: str,
    origin: str = "candidate",
    updated_at: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO v4_candidate_recurrence(
          recurrence_key,file_key,family,origin,updated_at
        ) VALUES (?,?,?,?,?)
        ON CONFLICT(recurrence_key,file_key) DO UPDATE SET
          family=excluded.family,
          origin=excluded.origin,
          updated_at=excluded.updated_at
        """,
        (str(recurrence_key), str(file_key), str(family), str(origin), updated_at),
    )


def document_counts(
    conn: sqlite3.Connection, keys: Iterable[str]
) -> dict[str, int]:
    """Return, per key, how many distinct documents attest it."""

    wanted = sorted({str(key) for key in keys})
    counts: dict[str, int] = {key: 0 for key in wanted}
    for start in range(0, len(wanted), 400):
        chunk = wanted[start : start + 400]
        placeholders = ",".join("?" for _ in chunk)
        for row in conn.execute(
            f"""
            SELECT recurrence_key, COUNT(DISTINCT file_key) AS n
            FROM v4_candidate_recurrence
            WHERE recurrence_key IN ({placeholders})
            GROUP BY recurrence_key
            """,
            chunk,
        ):
            counts[str(row[0])] = int(row[1])
    return counts


def sync_document_counts(
    conn: sqlite3.Connection, keys: Sequence[str] | None = None
) -> int:
    """Write the real recurrence count back onto ``document_count``.

    This is the "발견 문서 수 자동 갱신" that ``.docs/V4_PLAN.md`` §2 promised and
    that PLAN_REVIEW 교정 B found had never been implemented (every row was 1).
    """

    if keys is None:
        cursor = conn.execute(
            """
            UPDATE v4_taxonomy_candidate
            SET document_count = MAX(1, COALESCE((
                  SELECT COUNT(DISTINCT r.file_key)
                  FROM v4_candidate_recurrence r
                  WHERE r.recurrence_key = v4_taxonomy_candidate.recurrence_key
                ), 1))
            WHERE recurrence_key IS NOT NULL
            """
        )
        return int(cursor.rowcount or 0)
    unique = sorted({str(key) for key in keys})
    changed = 0
    for start in range(0, len(unique), 400):
        chunk = unique[start : start + 400]
        placeholders = ",".join("?" for _ in chunk)
        cursor = conn.execute(
            f"""
            UPDATE v4_taxonomy_candidate
            SET document_count = MAX(1, COALESCE((
                  SELECT COUNT(DISTINCT r.file_key)
                  FROM v4_candidate_recurrence r
                  WHERE r.recurrence_key = v4_taxonomy_candidate.recurrence_key
                ), 1))
            WHERE recurrence_key IN ({placeholders})
            """,
            chunk,
        )
        changed += int(cursor.rowcount or 0)
    return changed


def absorbed_item(
    candidate: Mapping[str, object],
    *,
    family: str,
    item_ref: str,
    admission: Admission,
) -> dict:
    """Turn a rejected candidate into a catch-all ``v4_clause_item`` payload.

    V4_PLAN 원칙 5 requires that a classification miss degrade to "findable as
    text", never to "not searchable".  Before this policy the generator dropped
    unclassified paragraphs into the candidate queue *without* an item, so their
    text never reached ``v4_item_fts`` at all; absorbing them restores the
    guarantee.
    """

    verbatim = str(candidate.get("verbatim") or "").strip()
    qualifier = candidate.get("qualifier")
    qualifier = dict(qualifier) if isinstance(qualifier, dict) else {}
    qualifier.update(
        {
            "candidate_admission": ABSORBED_MARKER,
            "admission_policy": POLICY_VERSION,
            "admission_reason": admission.reason,
            "distinction_reason": candidate.get("distinction_reason"),
        }
    )
    loc_start = int(candidate.get("loc_start") or 0)
    return {
        "item_ref": item_ref,
        "family": str(family),
        "taxonomy_id": admission.catch_all_taxonomy_id,
        "proposition": verbatim,
        "statement_polarity": "not_applicable",
        "subject_role": None,
        "counterparty_role": None,
        "action": None,
        "object_type": (
            defined_term(verbatim) if str(family) == "DEF" else None
        ),
        "effective_time": None,
        "source_kind": str(candidate.get("source_kind") or "body"),
        "source_id": candidate.get("source_id"),
        "source_name": candidate.get("source_name"),
        "source_ref": candidate.get("source_ref") or f"¶{loc_start}",
        "parent_clause_ref": candidate.get("parent_clause_ref"),
        "related_item_ref": None,
        "qualifier": qualifier,
        "verbatim": verbatim,
        "loc_start": loc_start,
        "loc_end": int(candidate.get("loc_end") or loc_start),
        "normalized": {
            "recurrence_key": admission.recurrence_key,
            "absorbed_by": POLICY_VERSION,
        },
        "confidence": "low",
        "review_status": "approved",
    }
