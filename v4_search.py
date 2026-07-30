"""Read-only search over V4 atomic contract propositions.

The module is the shared service for the CLI, web handlers, and MCP adapter.
It deliberately distinguishes a proved absence from an unevaluated or stale
document: keyword non-detection is never treated as absence.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from classify_version import (
    UNATTRIBUTED_ROLES,
    VERSION_PARTIAL_MATCHES,
    annotate_version_row,
    build_version_filter_notice,
    has_version_meta,
    normalize_confidence,
    resolve_version_filter,
    row_value,
    version_label,
    version_meta_select,
)
from lib.catalog import CatalogNotFoundError, catalog_path, require_catalog
from lib.console import configure_utf8_stdio


FAMILIES = {"RW", "CP", "COV", "DEF", "PAY", "REM"}
POLARITIES = {"affirmative", "negative", "none_exist", "not_applicable"}
MAX_LIMIT = 500
MAX_COMPARE = 10
# A concept query with no narrowing signal (no text/subject/polarity/ctype/lang) that
# still returns more items than this is an unranked alphabetical enumeration — the
# result carries a machine-readable low_query_signal hint so an agent re-queries with
# keywords instead of scrolling (V4_PLAN §9.6).
LOW_SIGNAL_POPULATION = 200


class V4SearchError(ValueError):
    def __init__(self, message: str, *, code: str = "VALIDATION_ERROR"):
        super().__init__(message)
        self.code = code


def connect_v4_ro(out: Path) -> sqlite3.Connection:
    db_path = catalog_path(out).resolve()
    # require_catalog never creates the file: a wrong --out must fail loudly
    # rather than leave an empty second catalog behind.
    try:
        require_catalog(db_path)
    except CatalogNotFoundError as exc:
        raise V4SearchError(str(exc), code="CATALOG_NOT_FOUND") from exc
    conn = sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    required = {"v4_taxonomy_node", "v4_clause_item", "v4_document_coverage"}
    existing = {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' OR type='view'"
        )
    }
    if not required.issubset(existing):
        conn.close()
        raise V4SearchError(
            "V4 index is not initialized.", code="V4_INDEX_NOT_INITIALIZED"
        )
    return conn


def log_v4_query(out: Path, record: dict) -> None:
    """Append one real-usage search query to ``out/v4_query_log.jsonl``.

    v3's search_contracts logs to query_log.jsonl but v4_search never did, so we had
    no way to measure what fraction of real queries arrive concept-only — which is the
    actual size of the problem T4/embeddings would solve (V4_PLAN §9.6, §10.1). This
    is a plain file append, not a DB write, so it is safe under the single-writer rule.
    Call it ONLY from real entry points (MCP/CLI/web), never from search_clause_items
    itself, so eval/probe traffic that drives the library directly does not pollute the
    usage signal. Best-effort: a logging failure must never break a search."""
    try:
        rec = {"ts": datetime.now(timezone.utc).isoformat(), **record}
        with (Path(out) / "v4_query_log.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 — logging is never allowed to fail a query
        pass


def _bounded_int(value: object, name: str, default: int, high: int) -> int:
    if value in (None, ""):
        return default
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        raise V4SearchError(f"'{name}' must be an integer.")
    if not 1 <= parsed <= high:
        raise V4SearchError(f"'{name}' must be between 1 and {high}.")
    return parsed


def _offset_int(value: object) -> int:
    if value in (None, ""):
        return 0
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        raise V4SearchError("'offset' must be an integer.")
    if not 0 <= parsed <= 1_000_000:
        raise V4SearchError("'offset' must be between 0 and 1000000.")
    return parsed


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def resolve_taxonomy(conn: sqlite3.Connection, value: str) -> dict:
    query = str(value or "").strip()
    if not query:
        raise V4SearchError("'taxonomy_id' is required.")
    row = conn.execute(
        """
        SELECT taxonomy_id,parent_id,family,canonical_ko,canonical_en,depth
        FROM v4_taxonomy_node
        WHERE taxonomy_id=? AND status='active'
        """,
        (query.upper(),),
    ).fetchone()
    if row is not None:
        return dict(row)
    normalized = _normalize(query)
    rows = conn.execute(
        """
        SELECT DISTINCT n.taxonomy_id,n.parent_id,n.family,n.canonical_ko,
                        n.canonical_en,n.depth
        FROM v4_taxonomy_node n
        LEFT JOIN v4_taxonomy_alias a ON a.taxonomy_id=n.taxonomy_id
        WHERE n.status='active'
          AND (
            lower(n.canonical_ko)=? OR lower(n.canonical_en)=?
            OR a.normalized_alias=?
          )
        ORDER BY n.taxonomy_id
        """,
        (normalized, normalized, normalized),
    ).fetchall()
    if not rows:
        raise V4SearchError(
            f"Unknown active taxonomy node: {query}", code="TAXONOMY_NOT_FOUND"
        )
    if len(rows) > 1:
        choices = ", ".join(str(item["taxonomy_id"]) for item in rows)
        raise V4SearchError(
            f"Ambiguous taxonomy label '{query}': {choices}",
            code="TAXONOMY_AMBIGUOUS",
        )
    return dict(rows[0])


def taxonomy_descendants(
    conn: sqlite3.Connection, taxonomy_id: str, include_descendants: bool = True
) -> list[str]:
    if not include_descendants:
        return [taxonomy_id]
    rows = conn.execute(
        """
        WITH RECURSIVE subtree(taxonomy_id) AS (
          SELECT taxonomy_id FROM v4_taxonomy_node
          WHERE taxonomy_id=? AND status='active'
          UNION ALL
          SELECT n.taxonomy_id
          FROM v4_taxonomy_node n
          JOIN subtree s ON n.parent_id=s.taxonomy_id
          WHERE n.status='active'
        )
        SELECT taxonomy_id FROM subtree ORDER BY taxonomy_id
        """,
        (taxonomy_id,),
    ).fetchall()
    return [str(row[0]) for row in rows]


def _resolve_version(version) -> list | None:
    """Parse a --version value into role keys, re-raising as V4SearchError."""
    try:
        return resolve_version_filter(version)
    except ValueError as exc:
        raise V4SearchError(str(exc))


def _file_filters(
    *,
    ctype: str | None,
    lang: str | None,
    version_roles: Sequence[str] | None = None,
    file_keys: Sequence[str] | None = None,
) -> tuple[list[str], list[object]]:
    clauses = ["f.status!='missing'"]
    params: list[object] = []
    if ctype:
        clauses.append("f.ctype=?")
        params.append(ctype)
    if lang:
        clauses.append("f.lang=?")
        params.append(lang)
    if version_roles:
        clause, version_params = _version_clause(version_roles)
        clauses.append(clause)
        params.extend(version_params)
    if file_keys is not None:
        if not file_keys:
            return clauses + ["0"], params
        clauses.append("f.file_key IN (%s)" % ",".join("?" for _ in file_keys))
        params.extend(file_keys)
    return clauses, params


def _version_clause(version_roles: Sequence[str]) -> tuple[str, list[object]]:
    return (
        "f.version_role IN (%s)" % ",".join("?" for _ in version_roles),
        list(version_roles),
    )


def _version_exclusion_reason(role, version_roles: Sequence[str]) -> str:
    partial: set[str] = set()
    for wanted in version_roles:
        partial.update(VERSION_PARTIAL_MATCHES.get(wanted, ()))
    if role in UNATTRIBUTED_ROLES:
        return "version_unknown"
    return "partial_version" if role in partial else "low_confidence"


def _version_review_row(row, version_roles: Sequence[str]) -> dict:
    item = annotate_version_row({
        "file_key": row_value(row, "file_key"),
        "path": row_value(row, "path"),
        "ctype": row_value(row, "ctype"),
        "lang": row_value(row, "lang"),
        "version_role": row_value(row, "version_role"),
        "version_basis": row_value(row, "version_basis"),
        "version_confidence": row_value(row, "version_confidence"),
    })
    item["exclusion_reason"] = _version_exclusion_reason(
        item["version_role"], version_roles
    )
    return item


def _is_version_review_row(row, version_roles: Sequence[str]) -> bool:
    role = row_value(row, "version_role")
    if role in UNATTRIBUTED_ROLES:
        return True
    partial: set[str] = set()
    for wanted in version_roles:
        partial.update(VERSION_PARTIAL_MATCHES.get(wanted, ()))
    if role in partial:
        return True
    return normalize_confidence(row_value(row, "version_confidence")) == "low"


def _version_notice_from_rows(
    conn: sqlite3.Connection,
    rows: Iterable[dict],
    version_roles: Sequence[str],
    *,
    sample: int = 20,
) -> dict:
    """버전 필터 적용 전 문서 행들로 고지 구조체를 만든다."""
    rows = list(rows)
    buckets: dict[tuple, int] = {}
    for row in rows:
        key = (
            row_value(row, "version_role"),
            normalize_confidence(row_value(row, "version_confidence")),
        )
        buckets[key] = buckets.get(key, 0) + 1
    candidates = [
        _version_review_row(row, version_roles)
        for row in rows
        if row_value(row, "version_role") not in version_roles
        and _is_version_review_row(row, version_roles)
    ]
    return build_version_filter_notice(
        version_roles,
        [(role, confidence, count) for (role, confidence), count in buckets.items()],
        meta_available=has_version_meta(conn),
        review_candidates=candidates[:sample],
    )


def _dedupe_by_group(rows: Iterable[dict], show_duplicates: bool) -> list[dict]:
    if show_duplicates:
        return list(rows)
    result = []
    seen: set[str] = set()
    for row in rows:
        group = str(row.get("dup_group") or row["file_key"])
        if group in seen:
            continue
        seen.add(group)
        result.append(row)
    return result


def _dedupe_item_rows(rows: Iterable[dict], show_duplicates: bool) -> list[dict]:
    """Drop duplicate documents while retaining every item in the representative."""
    if show_duplicates:
        return list(rows)
    result = []
    representative: dict[str, str] = {}
    for row in rows:
        group = str(row.get("dup_group") or row["file_key"])
        chosen = representative.setdefault(group, str(row["file_key"]))
        if str(row["file_key"]) == chosen:
            result.append(row)
    return result


def _blocking_pending_candidates(
    conn: sqlite3.Connection,
    family: str,
    file_keys: Iterable[str] | None = None,
) -> dict[str, int]:
    """Count pending taxonomy candidates that genuinely block absence.

    Per .docs/V4_PLAN.md §9.2 T-D (owner decision 2026-07-29), absence
    eligibility is DECOUPLED from the document-specific taxonomy-candidate
    backlog. A pending candidate that is a document-specific one-off — a single
    defined term / catch-all clause snippet that the generator could not place
    under any specific taxonomy sub-node — must NOT block a document from
    confirmed_absent. Such a candidate is the generator's per-document noise,
    not evidence that a whole family/sub-domain went unextracted.

    A pending candidate still blocks (is counted here) when it looks like a
    genuine, potentially systematic taxonomy gap rather than a one-off:
      * it is recommended under a specific sub-node (dotted ``recommended_parent_id``
        such as ``RW.TAX``), i.e. it was placed near a real sub-domain; OR
      * the generator marked it multi-document (``document_count > 1``); OR
      * its proposed name recurs across more than one evidence document
        (a genuine cross-document cluster).

    Document-specific one-offs — a bare family-root catch-all parent (no dot, or
    NULL) AND ``document_count <= 1`` AND no cross-document cluster — are ignored.

    This is a query-time decoupling only: the candidate rows are not modified.
    Genuine per-family/per-sub-domain coverage gating is unaffected, and the RW
    ABSENCE_UNVERIFIED_FAMILIES safety gate stays intact independently.
    """
    rows = conn.execute(
        """
        WITH crossdoc AS (
            SELECT proposed_ko
            FROM v4_taxonomy_candidate
            WHERE family=? AND status='pending' AND proposed_ko IS NOT NULL
            GROUP BY proposed_ko
            HAVING COUNT(DISTINCT evidence_file_key) > 1
        )
        SELECT evidence_file_key, COUNT(*) AS n
        FROM v4_taxonomy_candidate c
        WHERE c.family=? AND c.status='pending'
          AND (
                c.recommended_parent_id LIKE '%.%'
             OR COALESCE(c.document_count, 1) > 1
             OR c.proposed_ko IN (SELECT proposed_ko FROM crossdoc)
          )
        GROUP BY evidence_file_key
        """,
        (family, family),
    )
    counts = {
        str(row["evidence_file_key"]): int(row["n"])
        for row in rows
    }
    if file_keys is not None:
        wanted = {str(key) for key in file_keys}
        counts = {key: n for key, n in counts.items() if key in wanted}
    return counts


def _coverage_state(
    conn: sqlite3.Connection,
    file_row: sqlite3.Row | dict,
    family: str,
) -> dict:
    file_key = str(file_row["file_key"])
    content_hash = str(file_row["content_hash"] or "")
    coverage = conn.execute(
        """
        SELECT body_status,annex_status,reason,txt_hash,taxonomy_version,
               reviewed_at
        FROM v4_document_coverage WHERE file_key=? AND family=?
        """,
        (file_key, family),
    ).fetchone()
    reasons: list[str] = []
    if coverage is None:
        return {
            "state": "needs_review",
            "reasons": ["family_not_evaluated"],
            "body_status": "not_evaluated",
            "annex_status": "not_evaluated",
        }
    body_status = str(coverage["body_status"])
    annex_status = str(coverage["annex_status"])
    if body_status != "complete":
        reasons.append(f"body_{body_status}")
    if annex_status not in {"complete", "no_annex"}:
        reasons.append(f"annex_{annex_status}")
    if str(coverage["txt_hash"] or "") != content_hash:
        reasons.append("coverage_stale")
    bad_sources = conn.execute(
        """
        SELECT source_kind,status,COUNT(*) AS n
        FROM v4_source_coverage
        WHERE file_key=? AND family=? AND status!='complete'
        GROUP BY source_kind,status
        ORDER BY source_kind,status
        """,
        (file_key, family),
    ).fetchall()
    for source in bad_sources:
        reasons.append(
            f"{source['source_kind']}_{source['status']}:{int(source['n'])}"
        )
    source_rows = conn.execute(
        """
        SELECT source_kind,source_id,storage_file_key,txt_hash
        FROM v4_source_coverage
        WHERE file_key=? AND family=? AND status='complete'
        """,
        (file_key, family),
    ).fetchall()
    stale_sources = 0
    for source in source_rows:
        storage_key = source["storage_file_key"]
        expected_hash = content_hash
        if storage_key:
            storage = conn.execute(
                "SELECT content_hash FROM files WHERE file_key=? AND status!='missing'",
                (storage_key,),
            ).fetchone()
            expected_hash = str(storage[0] or "") if storage is not None else ""
        if not expected_hash or str(source["txt_hash"] or "") != expected_hash:
            stale_sources += 1
    if stale_sources:
        reasons.append(f"source_stale:{stale_sources}")
    pending = _blocking_pending_candidates(conn, family, [file_key]).get(file_key, 0)
    if pending:
        reasons.append(f"pending_taxonomy_candidates:{pending}")
    return {
        "state": "complete" if not reasons else "needs_review",
        "reasons": reasons,
        "body_status": body_status,
        "annex_status": annex_status,
        "coverage_reason": coverage["reason"],
        "taxonomy_version": coverage["taxonomy_version"],
        "reviewed_at": coverage["reviewed_at"],
    }


def _bulk_coverage_states(
    conn: sqlite3.Connection,
    file_rows: Sequence[sqlite3.Row | dict],
    family: str,
) -> dict[str, dict]:
    """Load family/source freshness once instead of issuing queries per item."""

    requested = {str(row["file_key"]): row for row in file_rows}
    if not requested:
        return {}
    coverage_by_file = {
        str(row["file_key"]): row
        for row in conn.execute(
            """
            SELECT file_key,body_status,annex_status,reason,txt_hash,
                   taxonomy_version,reviewed_at
            FROM v4_document_coverage
            WHERE family=?
            """,
            (family,),
        )
        if str(row["file_key"]) in requested
    }
    bad_sources: dict[str, list[sqlite3.Row]] = {}
    for row in conn.execute(
        """
        SELECT file_key,source_kind,status,COUNT(*) AS n
        FROM v4_source_coverage
        WHERE family=? AND status!='complete'
        GROUP BY file_key,source_kind,status
        ORDER BY file_key,source_kind,status
        """,
        (family,),
    ):
        if str(row["file_key"]) in requested:
            bad_sources.setdefault(str(row["file_key"]), []).append(row)
    complete_sources: dict[str, list[sqlite3.Row]] = {}
    for row in conn.execute(
        """
        SELECT s.file_key,s.storage_file_key,s.txt_hash,
               owner.content_hash AS owner_hash,
               storage.content_hash AS storage_hash,
               storage.status AS storage_status
        FROM v4_source_coverage s
        JOIN files owner ON owner.file_key=s.file_key
        LEFT JOIN files storage ON storage.file_key=s.storage_file_key
        WHERE s.family=? AND s.status='complete'
        """,
        (family,),
    ):
        if str(row["file_key"]) in requested:
            complete_sources.setdefault(str(row["file_key"]), []).append(row)
    pending = _blocking_pending_candidates(conn, family, requested.keys())

    states = {}
    for file_key, file_row in requested.items():
        content_hash = str(file_row["content_hash"] or "")
        coverage = coverage_by_file.get(file_key)
        if coverage is None:
            states[file_key] = {
                "state": "needs_review",
                "reasons": ["family_not_evaluated"],
                "body_status": "not_evaluated",
                "annex_status": "not_evaluated",
            }
            continue
        body_status = str(coverage["body_status"])
        annex_status = str(coverage["annex_status"])
        reasons = []
        if body_status != "complete":
            reasons.append(f"body_{body_status}")
        if annex_status not in {"complete", "no_annex"}:
            reasons.append(f"annex_{annex_status}")
        if str(coverage["txt_hash"] or "") != content_hash:
            reasons.append("coverage_stale")
        for source in bad_sources.get(file_key, []):
            reasons.append(
                f"{source['source_kind']}_{source['status']}:{int(source['n'])}"
            )
        stale_sources = 0
        for source in complete_sources.get(file_key, []):
            if source["storage_file_key"]:
                expected_hash = (
                    str(source["storage_hash"] or "")
                    if source["storage_status"] != "missing"
                    else ""
                )
            else:
                expected_hash = str(source["owner_hash"] or "")
            if not expected_hash or str(source["txt_hash"] or "") != expected_hash:
                stale_sources += 1
        if stale_sources:
            reasons.append(f"source_stale:{stale_sources}")
        pending_count = pending.get(file_key, 0)
        if pending_count:
            reasons.append(f"pending_taxonomy_candidates:{pending_count}")
        states[file_key] = {
            "state": "complete" if not reasons else "needs_review",
            "reasons": reasons,
            "body_status": body_status,
            "annex_status": annex_status,
            "coverage_reason": coverage["reason"],
            "taxonomy_version": coverage["taxonomy_version"],
            "reviewed_at": coverage["reviewed_at"],
        }
    return states


def _item_dict(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["freshness"] = (
        "current"
        if str(item.get("txt_hash") or "") == str(item.get("content_hash") or "")
        else "stale"
    )
    item["match_path"] = (
        "v4_atomic_item"
        if item["freshness"] == "current"
        else "v4_atomic_item_stale"
    )
    return annotate_version_row(item)


def search_clause_items(
    out: Path,
    taxonomy_id: str,
    *,
    polarity: str | None = None,
    subject: str | None = None,
    effective_time: str | None = None,
    text: str | None = None,
    ctype: str | None = None,
    lang: str | None = None,
    version: str | Sequence[str] | None = None,
    include_descendants: bool = True,
    show_duplicates: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Return approved atomic items and their source coordinates."""
    if polarity and polarity not in POLARITIES:
        raise V4SearchError("Unknown statement polarity.")
    version_roles = _resolve_version(version)
    limit = _bounded_int(limit, "limit", 50, MAX_LIMIT)
    offset = _offset_int(offset)
    with closing(connect_v4_ro(out)) as conn:
        node = resolve_taxonomy(conn, taxonomy_id)
        subtree = taxonomy_descendants(
            conn, str(node["taxonomy_id"]), include_descendants
        )
        # 버전 절은 마지막에 따로 붙인다 — 같은 조건에서 버전만 뺀 모집단을
        # 세어 "무엇이 제외됐는지" 고지해야 하기 때문이다.
        clauses, params = _file_filters(ctype=ctype, lang=lang)
        clauses.extend(
            [
                "i.review_status='approved'",
                "i.taxonomy_id IN (%s)" % ",".join("?" for _ in subtree),
            ]
        )
        params.extend(subtree)
        if polarity:
            clauses.append("i.statement_polarity=?")
            params.append(polarity)
        if subject:
            clauses.append("lower(COALESCE(i.subject_role,''))=lower(?)")
            params.append(subject.strip())
        if effective_time:
            clauses.append("lower(COALESCE(i.effective_time,''))=lower(?)")
            params.append(effective_time.strip())
        # A `text` query is tokenized on whitespace: every token must appear in the
        # item's verbatim OR proposition (AND across tokens). A single token degrades
        # to the old substring filter; multi-keyword queries ("손해배상 상한 10%") — the
        # common real query, not an exact quote — used to return 0 unless the whole
        # string sat contiguously in one field, and now match on keyword coverage.
        text_tokens = [tok for tok in text.lower().split() if tok] if text else []
        text_raw = text.strip().lower() if text else ""
        for tok in text_tokens:
            clauses.append("(lower(i.verbatim) LIKE ? OR lower(i.proposition) LIKE ?)")
            like = f"%{tok}%"
            params.extend([like, like])
        version_notice = None
        if version_roles:
            scope_rows = conn.execute(
                f"""
                SELECT DISTINCT f.file_key,f.path,f.ctype,f.lang,f.version_role,
                       {version_meta_select(conn)}
                FROM v4_clause_item i
                JOIN files f ON f.file_key=i.file_key
                WHERE {' AND '.join(clauses)}
                """,
                params,
            ).fetchall()
            version_notice = _version_notice_from_rows(
                conn, [dict(row) for row in scope_rows], version_roles
            )
            version_sql, version_params = _version_clause(version_roles)
            clauses.append(version_sql)
            params.extend(version_params)
        # Ordering. A bare concept query has no signal that distinguishes one item
        # from its hundreds of same-node siblings, so it stays in a stable document
        # order (file_key, ¶) — an *enumeration* for compare/count queries. But when
        # a `text` query is given it DOES carry a discriminating signal, and file_key
        # order buries the best match (measured: recall@1 ~0.54 on distinctive queries
        # because a sibling sorts first). Rank those by match quality: more query tokens
        # landing in the verbatim (the clause text) beats a proposition-only hit, a
        # contiguous full-phrase match beats scattered tokens, an earlier first-token
        # position beats a later one, and a shorter (more focused) item beats a long
        # catch-all. Purely a reorder — totals/pagination and the no-text path untouched.
        order_params: list = []
        if text_tokens:
            coverage = "+".join(
                ["CASE WHEN instr(lower(i.verbatim),?)>0 THEN 1 ELSE 0 END"] * len(text_tokens)
            )
            order_sql = (
                f"({coverage}) DESC,"
                "CASE WHEN instr(lower(i.verbatim),?)>0 THEN 1 ELSE 0 END DESC,"
                "CASE WHEN instr(lower(i.verbatim),?)>0 THEN instr(lower(i.verbatim),?) "
                "     ELSE 2147483647 END,"
                "length(COALESCE(i.verbatim,'')),f.file_key,i.loc_start,i.item_id"
            )
            order_params = [*text_tokens, text_raw, text_tokens[0], text_tokens[0]]
        else:
            order_sql = "f.file_key,i.loc_start,i.item_id"
        select_sql = f"""
            SELECT i.item_id,i.item_ref,i.file_key,i.family,i.taxonomy_id,
                   n.canonical_ko,n.canonical_en,i.proposition,
                   i.statement_polarity,i.subject_role,i.counterparty_role,
                   i.action,i.object_type,i.effective_time,i.source_kind,
                   i.source_id,i.source_name,i.source_ref,i.parent_clause_ref,
                   i.related_item_ref,i.qualifier_json,i.verbatim,
                   i.loc_start,i.loc_end,i.confidence,i.txt_hash,
                   i.taxonomy_version,i.extractor_version,i.review_status,
                   f.path,f.filename,f.ctype,f.lang,f.status,f.content_hash,
                   f.dup_group,f.is_draft,f.version_hint,f.version_role,
                   {version_meta_select(conn)}
            FROM v4_clause_item i
            JOIN v4_taxonomy_node n ON n.taxonomy_id=i.taxonomy_id
            JOIN files f ON f.file_key=i.file_key
            WHERE {' AND '.join(clauses)}
            ORDER BY {order_sql}
        """
        if show_duplicates:
            totals = conn.execute(
                f"""
                SELECT COUNT(*) AS total_items,
                       COUNT(DISTINCT i.file_key) AS total_documents,
                       COALESCE(SUM(
                         CASE WHEN COALESCE(i.txt_hash,'') !=
                                        COALESCE(f.content_hash,'')
                              THEN 1 ELSE 0 END
                       ),0) AS stale_items
                FROM v4_clause_item i
                JOIN files f ON f.file_key=i.file_key
                WHERE {' AND '.join(clauses)}
                """,
                params,
            ).fetchone()
            total_items = int(totals["total_items"])
            total_documents = int(totals["total_documents"])
            stale = int(totals["stale_items"])
            page_rows = conn.execute(
                select_sql + " LIMIT ? OFFSET ?",
                [*params, *order_params, limit, offset],
            ).fetchall()
            items = [_item_dict(row) for row in page_rows]
        else:
            rows = conn.execute(select_sql, [*params, *order_params]).fetchall()
            all_items = _dedupe_item_rows(
                (_item_dict(row) for row in rows), show_duplicates
            )
            total_items = len(all_items)
            total_documents = len({item["file_key"] for item in all_items})
            stale = sum(item["freshness"] == "stale" for item in all_items)
            items = all_items[offset: offset + limit]
        coverage_by_file = _bulk_coverage_states(
            conn, items, str(node["family"])
        )
        for item in items:
            item["coverage"] = coverage_by_file[str(item["file_key"])]
        warnings = ["stale_items_require_source_recheck"] if stale else []
        if version_notice:
            warnings.extend(version_notice["warnings"])
        result = {
            "query": {
                "taxonomy_id": node["taxonomy_id"],
                "resolved_label_ko": node["canonical_ko"],
                "resolved_label_en": node["canonical_en"],
                "family": node["family"],
                "include_descendants": include_descendants,
                "taxonomy_scope": subtree,
                "polarity": polarity,
                "subject": subject,
                "effective_time": effective_time,
                "text": text,
                "ctype": ctype,
                "lang": lang,
                "version": version_roles,
            },
            "total_items": total_items,
            "total_documents": total_documents,
            "returned_items": len(items),
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(items) < total_items,
            "next_offset": (
                offset + len(items)
                if offset + len(items) < total_items
                else None
            ),
            "stale_items": stale,
            "results": items,
            "warnings": warnings,
        }
        if version_notice is not None:
            result["version_filter_notice"] = version_notice
        narrowed = bool(
            text_tokens or polarity or subject or effective_time or ctype or lang
            or version_roles
        )
        if not narrowed and total_items > LOW_SIGNAL_POPULATION:
            result["low_query_signal"] = {
                "population": total_items,
                "hint": (
                    "개념 라벨만으로는 좁혀지지 않아 결과가 관련도순이 아닌 문서 순서로 열거됩니다. "
                    "사용자 질의의 변별 키워드를 text로 전달하거나 subject/polarity/ctype/lang으로 "
                    "좁히면 관련도 정렬이 작동합니다."
                ),
            }
        return result


# Families whose coverage='complete' cannot currently be trusted to prove
# absence. Per .docs/V4_RW_COVERAGE_DEFECT_20260727.md, RW (representations)
# was blanket-stamped complete while whole rep sub-domains (IP 98%, labor 84%,
# environment 68%, tax 36% of docs) were never extracted — so RW confirmed_absent
# is mostly false. Until re-extraction + a real per-sub-domain coverage audit,
# RW absence is demoted to needs_review. Covenant/condition families stay trusted.
ABSENCE_UNVERIFIED_FAMILIES = {"RW"}

# Sub-domains inside an otherwise-unverified family that HAVE passed a per-sub-domain
# coverage re-verification (re-extraction complete + absence pool verified with
# recorded evidence) and so MAY confirm absence again — the "선(先)해제" exception
# (V4_PLAN §9.1 #3). A sub-domain is admitted ONLY once its golden absence query's
# pool_verified is populated; an empty set keeps the whole family gated. Keyed by the
# 2-segment sub-domain id (e.g. "RW.ENVIRONMENT").
ABSENCE_VERIFIED_SUBDOMAINS: set[str] = {"RW.ENVIRONMENT"}


def _absence_subdomain(taxonomy_id: str) -> str:
    """2-segment sub-domain of a taxonomy id (RW.ENVIRONMENT.PERMITS -> RW.ENVIRONMENT;
    the bare family root RW -> RW, which no sub-domain exception can match)."""
    parts = str(taxonomy_id).split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else str(taxonomy_id)


def search_clause_absence(
    out: Path,
    taxonomy_id: str,
    *,
    polarity: str | None = None,
    ctype: str | None = None,
    lang: str | None = None,
    version: str | Sequence[str] | None = None,
    include_descendants: bool = True,
    show_duplicates: bool = False,
    limit: int = 50,
) -> dict:
    """Classify documents as confirmed_absent or needs_review.

    Only a current, complete body+annex family review with no unresolved
    family candidate can prove absence. Representation families whose coverage
    is not trustworthy (ABSENCE_UNVERIFIED_FAMILIES) never confirm absence.
    """
    if polarity and polarity not in POLARITIES:
        raise V4SearchError("Unknown statement polarity.")
    version_roles = _resolve_version(version)
    limit = _bounded_int(limit, "limit", 50, MAX_LIMIT)
    with closing(connect_v4_ro(out)) as conn:
        node = resolve_taxonomy(conn, taxonomy_id)
        subtree = taxonomy_descendants(
            conn, str(node["taxonomy_id"]), include_descendants
        )
        # 버전 절 없이 모집단을 읽고 파이썬에서 나눈다 — 제외된 문서를 세어
        # 고지하기 위해서다(부재 질의에서 조용한 누락은 특히 위험하다).
        clauses, params = _file_filters(ctype=ctype, lang=lang)
        rows = conn.execute(
            f"""
            SELECT f.file_key,f.path,f.filename,f.ctype,f.lang,f.status,
                   f.content_hash,f.dup_group,f.is_draft,f.version_hint,
                   f.version_role,{version_meta_select(conn)}
            FROM files f
            WHERE {' AND '.join(clauses)}
            ORDER BY f.file_key
            """,
            params,
        ).fetchall()
        scope = [dict(row) for row in rows]
        version_notice = None
        if version_roles:
            version_notice = _version_notice_from_rows(conn, scope, version_roles)
            scope = [row for row in scope
                     if row.get("version_role") in version_roles]
        files = _dedupe_by_group(scope, show_duplicates)
        item_clauses = [
            "review_status='approved'",
            "taxonomy_id IN (%s)" % ",".join("?" for _ in subtree),
        ]
        item_params: list[object] = [*subtree]
        if polarity:
            item_clauses.append("statement_polarity=?")
            item_params.append(polarity)
        present_counts = {
            str(row["file_key"]): int(row["n"])
            for row in conn.execute(
                f"""
                SELECT file_key,COUNT(*) AS n
                FROM v4_clause_item
                WHERE {' AND '.join(item_clauses)}
                GROUP BY file_key
                """,
                item_params,
            )
        }
        coverage_by_file = _bulk_coverage_states(
            conn, files, str(node["family"])
        )
        # Family is gated UNLESS the queried sub-domain has been re-verified. A query
        # at the family root spans unverified sub-domains too, so it stays gated; a
        # query at/below a verified sub-domain (whole subtree ⊆ that sub-domain) opens.
        family_gated = (
            str(node["family"]) in ABSENCE_UNVERIFIED_FAMILIES
            and _absence_subdomain(str(node["taxonomy_id"])) not in ABSENCE_VERIFIED_SUBDOMAINS
        )
        absent: list[dict] = []
        needs_review: list[dict] = []
        present_excluded = 0
        for file_row in files:
            file_key = str(file_row["file_key"])
            if present_counts.get(file_key, 0):
                present_excluded += 1
                continue
            coverage = coverage_by_file[file_key]
            # RW-family 'complete' coverage is not verified per sub-domain, so it
            # cannot prove absence — flag the reason and demote to needs_review.
            if family_gated and coverage["state"] == "complete":
                coverage = {
                    **coverage,
                    "reasons": [*coverage.get("reasons", []), "rw_coverage_unverified"],
                }
            result = annotate_version_row({
                **file_row,
                "taxonomy_id": node["taxonomy_id"],
                "family": node["family"],
                "coverage": coverage,
                "match_path": "v4_coverage",
            })
            if coverage["state"] == "complete" and not family_gated:
                result["state"] = "confirmed_absent"
                absent.append(result)
            else:
                result["state"] = "needs_review"
                needs_review.append(result)
        warnings = (
            (["unevaluated_or_incomplete_documents_are_not_absent"] if needs_review else [])
            + (
                ["rw_absence_unverified_demoted_to_needs_review"]
                if family_gated
                else []
            )
        )
        if version_notice:
            warnings.extend(version_notice["warnings"])
        result = {
            "query": {
                "taxonomy_id": node["taxonomy_id"],
                "resolved_label_ko": node["canonical_ko"],
                "resolved_label_en": node["canonical_en"],
                "family": node["family"],
                "include_descendants": include_descendants,
                "taxonomy_scope": subtree,
                "polarity": polarity,
                "ctype": ctype,
                "lang": lang,
                "version": version_roles,
            },
            "confirmed_absent_count": len(absent),
            "needs_review_count": len(needs_review),
            "present_excluded_count": present_excluded,
            "confirmed_absent": absent[:limit],
            "needs_review": needs_review[:limit],
            "warnings": warnings,
        }
        if version_notice is not None:
            result["version_filter_notice"] = version_notice
        return result


def compare_clause_items(
    out: Path,
    taxonomy_id: str,
    file_keys: Sequence[str],
    *,
    polarity: str | None = None,
    include_descendants: bool = True,
) -> dict:
    keys = list(dict.fromkeys(str(key).strip() for key in file_keys if str(key).strip()))
    if not 2 <= len(keys) <= MAX_COMPARE:
        raise V4SearchError(f"'file_keys' must contain 2 to {MAX_COMPARE} unique keys.")
    if polarity and polarity not in POLARITIES:
        raise V4SearchError("Unknown statement polarity.")
    with closing(connect_v4_ro(out)) as conn:
        node = resolve_taxonomy(conn, taxonomy_id)
        subtree = taxonomy_descendants(
            conn, str(node["taxonomy_id"]), include_descendants
        )
        placeholders = ",".join("?" for _ in keys)
        rows = conn.execute(
            f"""
            SELECT file_key,path,filename,ctype,lang,status,content_hash,
                   dup_group,is_draft,version_hint,version_role,
                   {version_meta_select(conn, "")}
            FROM files WHERE file_key IN ({placeholders}) AND status!='missing'
            """,
            keys,
        ).fetchall()
        by_key = {str(row["file_key"]): row for row in rows}
        missing = [key for key in keys if key not in by_key]
        if missing:
            raise V4SearchError(
                "Unknown or missing file_key: " + ", ".join(missing),
                code="FILE_NOT_FOUND",
            )
        comparison = []
        for key in keys:
            file_row = by_key[key]
            clauses = [
                "i.file_key=?",
                "i.review_status='approved'",
                "i.taxonomy_id IN (%s)" % ",".join("?" for _ in subtree),
            ]
            params: list[object] = [key, *subtree]
            if polarity:
                clauses.append("i.statement_polarity=?")
                params.append(polarity)
            item_rows = conn.execute(
                f"""
                SELECT i.*,n.canonical_ko,n.canonical_en,f.content_hash
                FROM v4_clause_item i
                JOIN v4_taxonomy_node n ON n.taxonomy_id=i.taxonomy_id
                JOIN files f ON f.file_key=i.file_key
                WHERE {' AND '.join(clauses)}
                ORDER BY i.loc_start,i.item_id
                """,
                params,
            ).fetchall()
            items = [_item_dict(row) for row in item_rows]
            coverage = _coverage_state(conn, file_row, str(node["family"]))
            current = [item for item in items if item["freshness"] == "current"]
            if current:
                state = "confirmed_present"
            elif items:
                state = "needs_review"
                coverage = dict(coverage)
                coverage["reasons"] = [
                    *coverage.get("reasons", []),
                    "matching_items_stale",
                ]
            elif coverage["state"] == "complete":
                state = "confirmed_absent"
            else:
                state = "needs_review"
            file_info = annotate_version_row(dict(file_row))
            comparison.append(
                {
                    "file": file_info,
                    "state": state,
                    "items": items,
                    "coverage": coverage,
                    "match_path": "v4_atomic_item" if items else "v4_coverage",
                }
            )
        return {
            "query": {
                "taxonomy_id": node["taxonomy_id"],
                "resolved_label_ko": node["canonical_ko"],
                "resolved_label_en": node["canonical_en"],
                "family": node["family"],
                "include_descendants": include_descendants,
                "taxonomy_scope": subtree,
                "polarity": polarity,
            },
            "comparison": comparison,
        }


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--item", required=True, dest="taxonomy_id")
    parser.add_argument("--polarity", choices=sorted(POLARITIES))
    parser.add_argument("--exact-node", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search V4 atomic M&A contract propositions."
    )
    parser.add_argument("--out", type=Path, default=Path("cs_index"))
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    present = sub.add_parser("search", help="Find approved atomic items.")
    _add_common(present)
    present.add_argument("--subject")
    present.add_argument("--time", dest="effective_time")
    present.add_argument("--text")
    present.add_argument("--type", dest="ctype")
    present.add_argument("--lang")
    present.add_argument("--version",
                         help="버전 필터: role key 또는 한글 라벨(콤마로 다중). "
                              "예: buyer_draft / '매수인 초안,매도인 초안'. "
                              "파일명 휴리스틱 분류이므로 제외 모집단은 "
                              "version_filter_notice로 고지된다.")
    present.add_argument("--show-duplicates", action="store_true")
    present.add_argument("--limit", type=int, default=50)
    present.add_argument("--offset", type=int, default=0)
    present.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    absent = sub.add_parser("absent", help="Find coverage-proved absence.")
    _add_common(absent)
    absent.add_argument("--type", dest="ctype")
    absent.add_argument("--lang")
    absent.add_argument("--version",
                        help="버전 필터: role key 또는 한글 라벨(콤마로 다중). "
                             "제외 모집단은 version_filter_notice로 고지된다.")
    absent.add_argument("--show-duplicates", action="store_true")
    absent.add_argument("--limit", type=int, default=50)
    absent.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    compare = sub.add_parser("compare", help="Compare 2-10 contracts.")
    _add_common(compare)
    compare.add_argument("--file-key", action="append", required=True)
    compare.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        common = {
            "polarity": args.polarity,
            "include_descendants": not args.exact_node,
        }
        if args.command == "search":
            result = search_clause_items(
                args.out,
                args.taxonomy_id,
                subject=args.subject,
                effective_time=args.effective_time,
                text=args.text,
                ctype=args.ctype,
                lang=args.lang,
                version=args.version,
                show_duplicates=args.show_duplicates,
                limit=args.limit,
                offset=args.offset,
                **common,
            )
        elif args.command == "absent":
            result = search_clause_absence(
                args.out,
                args.taxonomy_id,
                ctype=args.ctype,
                lang=args.lang,
                version=args.version,
                show_duplicates=args.show_duplicates,
                limit=args.limit,
                **common,
            )
        else:
            result = compare_clause_items(
                args.out, args.taxonomy_id, args.file_key, **common
            )
    except V4SearchError as exc:
        print(json.dumps({"error": {"code": exc.code, "message": str(exc)}}))
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "search":
        print(
            f"{result['query']['taxonomy_id']}: "
            f"{result['total_items']} items / {result['total_documents']} documents"
        )
        for item in result["results"]:
            version = item.get("version_label") or item.get("version_role") or "-"
            mark = "?" if item.get("version_review_required") else ""
            print(
                f"[{item['file_key']}] {item['item_ref']} "
                f"{item['taxonomy_id']} ¶{item['loc_start']}-{item['loc_end']} "
                f"({item['freshness']}) [{version}{mark}]"
            )
    elif args.command == "absent":
        print(
            f"{result['query']['taxonomy_id']}: "
            f"confirmed_absent={result['confirmed_absent_count']} "
            f"needs_review={result['needs_review_count']}"
        )
        for item in result["confirmed_absent"]:
            version = item.get("version_label") or item.get("version_role") or "-"
            mark = "?" if item.get("version_review_required") else ""
            print(f"[{item['file_key']}] confirmed_absent [{version}{mark}] {item['path']}")
    else:
        for item in result["comparison"]:
            print(f"[{item['file']['file_key']}] {item['state']}")
    notice = result.get("version_filter_notice") if isinstance(result, dict) else None
    if notice and not args.json:
        print("[버전 필터 고지] " + notice["warning"], file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
