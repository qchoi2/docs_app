"""Local V4 taxonomy-candidate administration service and web handlers.

The service is deliberately deterministic and API-free. Candidate resolutions
are transactional, preserve the original evidence, and write an append-only
action log. The web handlers follow webapp.py's ``(status, data)`` convention.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from v4_schema import initialize_v4_schema, normalize_alias


FAMILIES = {"RW", "CP", "COV", "DEF", "PAY", "REM"}
STATUSES = {"pending", "approved", "merged", "rejected"}
TAXONOMY_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]*(?:\.[A-Z0-9_]+)+$")
MAX_BATCH = 500


class TaxonomyAdminError(ValueError):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect_admin(out: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(Path(out) / "catalog.sqlite", timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    initialize_v4_schema(conn)
    ensure_action_log(conn)
    return conn


def ensure_action_log(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS v4_taxonomy_action_log (
          action_id INTEGER PRIMARY KEY AUTOINCREMENT,
          action TEXT NOT NULL CHECK (action IN ('merge','promote','reject')),
          candidate_ids_json TEXT NOT NULL,
          target_taxonomy_id TEXT,
          payload_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_v4_taxonomy_action_created
          ON v4_taxonomy_action_log(created_at DESC);
        """
    )


def _int_param(value: object, name: str, default: int, low: int, high: int) -> int:
    if value in (None, ""):
        return default
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        raise TaxonomyAdminError(400, "VALIDATION_ERROR", f"'{name}' must be an integer.")
    if not low <= parsed <= high:
        raise TaxonomyAdminError(
            400,
            "VALIDATION_ERROR",
            f"'{name}' must be between {low} and {high}.",
        )
    return parsed


def _cluster_text(value: str) -> str:
    return re.sub(r"[\W_]+", " ", value.casefold(), flags=re.UNICODE).strip()


def _cluster_key(family: str, verbatim: str, nearest: str | None) -> str:
    raw = f"{family}|{_cluster_text(verbatim)}|{nearest or ''}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def list_candidate_clusters(
    out: Path,
    *,
    status: str = "pending",
    family: str | None = None,
    query: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    if status not in STATUSES:
        raise TaxonomyAdminError(400, "VALIDATION_ERROR", "Unknown candidate status.")
    if family is not None and family not in FAMILIES:
        raise TaxonomyAdminError(400, "VALIDATION_ERROR", "Unknown family.")
    limit = _int_param(limit, "limit", 50, 1, 100)
    offset = _int_param(offset, "offset", 0, 0, 10000)
    clauses = ["c.status=?"]
    params: list[object] = [status]
    if family:
        clauses.append("c.family=?")
        params.append(family)
    if query:
        clauses.append(
            "(c.verbatim LIKE ? OR c.proposed_ko LIKE ? OR "
            "c.nearest_taxonomy_id LIKE ? OR c.evidence_file_key LIKE ?)"
        )
        needle = f"%{query.strip()}%"
        params.extend([needle, needle, needle, needle])
    sql = f"""
        SELECT c.*,f.path,n.canonical_ko AS nearest_ko,n.canonical_en AS nearest_en
        FROM v4_taxonomy_candidate c
        JOIN files f ON f.file_key=c.evidence_file_key
        LEFT JOIN v4_taxonomy_node n ON n.taxonomy_id=c.nearest_taxonomy_id
        WHERE {' AND '.join(clauses)}
        ORDER BY c.family,c.nearest_taxonomy_id,c.verbatim,c.candidate_id
    """
    with connect_admin(out) as conn:
        rows = [dict(row) for row in conn.execute(sql, params)]
    grouped: dict[str, dict] = {}
    for row in rows:
        key = _cluster_key(
            str(row["family"]),
            str(row["verbatim"]),
            row.get("nearest_taxonomy_id"),
        )
        cluster = grouped.setdefault(
            key,
            {
                "cluster_key": key,
                "family": row["family"],
                "verbatim": row["verbatim"],
                "proposed_ko": row["proposed_ko"],
                "proposed_en": row["proposed_en"],
                "recommended_parent_id": row["recommended_parent_id"],
                "distinction_reason": row["distinction_reason"],
                "nearest_taxonomy_id": row["nearest_taxonomy_id"],
                "nearest_ko": row["nearest_ko"],
                "nearest_en": row["nearest_en"],
                "candidate_ids": [],
                "document_count": 0,
                "_document_keys": [],
                "evidence": [],
            },
        )
        cluster["candidate_ids"].append(int(row["candidate_id"]))
        if row["evidence_file_key"] not in cluster["_document_keys"]:
            cluster["_document_keys"].append(row["evidence_file_key"])
        if len(cluster["evidence"]) < 5:
            cluster["evidence"].append(
                {
                    "candidate_id": int(row["candidate_id"]),
                    "file_key": row["evidence_file_key"],
                    "path": row["path"],
                    "loc_start": int(row["loc_start"]),
                    "loc_end": int(row["loc_end"]),
                }
            )
    clusters = list(grouped.values())
    for cluster in clusters:
        cluster["document_count"] = len(cluster.pop("_document_keys"))
        cluster["candidate_count"] = len(cluster["candidate_ids"])
    clusters.sort(
        key=lambda row: (
            -int(row["candidate_count"]),
            str(row["family"]),
            str(row["cluster_key"]),
        )
    )
    return {
        "status": status,
        "family": family,
        "query": query,
        "total_clusters": len(clusters),
        "total_candidates": sum(row["candidate_count"] for row in clusters),
        "limit": limit,
        "offset": offset,
        "clusters": clusters[offset : offset + limit],
    }


def list_taxonomy_nodes(out: Path, *, family: str | None = None) -> dict:
    if family is not None and family not in FAMILIES:
        raise TaxonomyAdminError(400, "VALIDATION_ERROR", "Unknown family.")
    where = "WHERE n.status='active'"
    params: tuple[object, ...] = ()
    if family:
        where += " AND n.family=?"
        params = (family,)
    with connect_admin(out) as conn:
        rows = [
            dict(row)
            for row in conn.execute(
                f"""
                SELECT n.taxonomy_id,n.parent_id,n.family,n.canonical_ko,
                       n.canonical_en,n.definition,n.depth,n.taxonomy_version,
                       CASE WHEN EXISTS(
                         SELECT 1 FROM v4_taxonomy_node child
                         WHERE child.parent_id=n.taxonomy_id AND child.status='active'
                       ) THEN 0 ELSE 1 END AS is_leaf,
                       COUNT(a.alias_id) AS alias_count
                FROM v4_taxonomy_node n
                LEFT JOIN v4_taxonomy_alias a USING(taxonomy_id)
                {where}
                GROUP BY n.taxonomy_id
                ORDER BY n.family,n.taxonomy_id
                """,
                params,
            )
        ]
    return {"family": family, "count": len(rows), "nodes": rows}


def taxonomy_summary(out: Path) -> dict:
    with connect_admin(out) as conn:
        version = int(
            conn.execute(
                "SELECT value FROM v4_meta WHERE key='taxonomy_version'"
            ).fetchone()[0]
        )
        status_counts = {
            str(row[0]): int(row[1])
            for row in conn.execute(
                "SELECT status,COUNT(*) FROM v4_taxonomy_candidate GROUP BY status"
            )
        }
        family_counts = {
            str(row[0]): int(row[1])
            for row in conn.execute(
                """
                SELECT family,COUNT(*) FROM v4_taxonomy_candidate
                WHERE status='pending' GROUP BY family
                """
            )
        }
        recent_actions = [
            dict(row)
            for row in conn.execute(
                """
                SELECT action_id,action,target_taxonomy_id,created_at
                FROM v4_taxonomy_action_log
                ORDER BY action_id DESC LIMIT 10
                """
            )
        ]
        node_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM v4_taxonomy_node WHERE status='active'"
            ).fetchone()[0]
        )
    return {
        "taxonomy_version": version,
        "node_count": node_count,
        "candidate_status_counts": status_counts,
        "pending_by_family": family_counts,
        "recent_actions": recent_actions,
    }


def _candidate_ids(value: object) -> list[int]:
    if not isinstance(value, list) or not value:
        raise TaxonomyAdminError(
            400, "VALIDATION_ERROR", "'candidate_ids' must be a non-empty list."
        )
    if len(value) > MAX_BATCH:
        raise TaxonomyAdminError(400, "VALIDATION_ERROR", "Candidate batch is too large.")
    ids: list[int] = []
    for raw in value:
        if isinstance(raw, bool) or not isinstance(raw, int) or raw <= 0:
            raise TaxonomyAdminError(
                400, "VALIDATION_ERROR", "Candidate ids must be positive integers."
            )
        if raw not in ids:
            ids.append(raw)
    return ids


def _load_pending_candidates(
    conn: sqlite3.Connection, candidate_ids: list[int]
) -> list[sqlite3.Row]:
    placeholders = ",".join("?" for _ in candidate_ids)
    rows = list(
        conn.execute(
            f"""
            SELECT * FROM v4_taxonomy_candidate
            WHERE candidate_id IN ({placeholders})
            ORDER BY candidate_id
            """,
            candidate_ids,
        )
    )
    if len(rows) != len(candidate_ids):
        raise TaxonomyAdminError(404, "CANDIDATE_NOT_FOUND", "Candidate not found.")
    non_pending = [int(row["candidate_id"]) for row in rows if row["status"] != "pending"]
    if non_pending:
        raise TaxonomyAdminError(
            409,
            "CANDIDATE_ALREADY_RESOLVED",
            f"Candidates already resolved: {non_pending}",
        )
    return rows


def _aliases(value: object) -> list[str]:
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise TaxonomyAdminError(400, "VALIDATION_ERROR", "'aliases' must be a list.")
    rows = []
    for raw in value:
        if not isinstance(raw, str) or not raw.strip() or len(raw.strip()) > 200:
            raise TaxonomyAdminError(400, "VALIDATION_ERROR", "Alias is invalid.")
        cleaned = " ".join(raw.split())
        if cleaned not in rows:
            rows.append(cleaned)
    return rows


NEGATIVE_ABSENCE = re.compile(
    r"(없(?:다|으며|고|는|음)|존재하지|발생하지|해당하지|부담하지|"
    r"제기되지|진행되고 있지|\bno\b|\bnone\b|\bwithout\b|"
    r"\bdoes not exist\b|\bhas not\b|\bnot pending\b)",
    re.IGNORECASE,
)
NEGATIVE_PROHIBITION = re.compile(
    r"(하여서는 아니|해서는 아니|금지|제한한다|않아야|"
    r"\bshall not\b|\bmay not\b|\bmust not\b)",
    re.IGNORECASE,
)


def _resolved_polarity(text: str) -> str:
    if NEGATIVE_ABSENCE.search(text):
        return "none_exist"
    if NEGATIVE_PROHIBITION.search(text):
        return "negative"
    return "affirmative"


def _materialize_candidate_items(
    conn: sqlite3.Connection,
    rows: list[sqlite3.Row],
    *,
    action: str,
    target_taxonomy_ids: list[str],
    reason: str,
    resolved_at: str,
) -> dict[int, list[int]]:
    """Create searchable items for merged/promoted evidence in the same transaction."""

    targets = {}
    for taxonomy_id in target_taxonomy_ids:
        target = conn.execute(
            """
            SELECT taxonomy_id,family,canonical_ko
            FROM v4_taxonomy_node
            WHERE taxonomy_id=? AND status='active'
            """,
            (taxonomy_id,),
        ).fetchone()
        if target is None:
            raise TaxonomyAdminError(404, "TAXONOMY_NOT_FOUND", "Target node not found.")
        targets[taxonomy_id] = target
    taxonomy_version = int(
        conn.execute(
            "SELECT value FROM v4_meta WHERE key='taxonomy_version'"
        ).fetchone()[0]
    )
    materialized: dict[int, list[int]] = {}
    for row in rows:
        candidate_id = int(row["candidate_id"])
        file_row = conn.execute(
            "SELECT content_hash FROM files WHERE file_key=?",
            (row["evidence_file_key"],),
        ).fetchone()
        current_hash = str(file_row["content_hash"] or "") if file_row else ""
        candidate_hash = str(row["txt_hash"] or "")
        if candidate_hash and current_hash and candidate_hash != current_hash:
            raise TaxonomyAdminError(
                409,
                "STALE_CANDIDATE",
                f"Candidate {candidate_id} was extracted from an older document version.",
            )
        source_kind = str(row["source_kind"] or "body")
        source_id = row["source_id"]
        if source_kind != "body":
            source_exists = conn.execute(
                """
                SELECT 1 FROM v4_source_coverage
                WHERE file_key=? AND family=? AND source_id=?
                """,
                (row["evidence_file_key"], row["family"], source_id),
            ).fetchone()
            if not source_id or source_exists is None:
                raise TaxonomyAdminError(
                    409,
                    "SOURCE_EVIDENCE_MISSING",
                    f"Candidate {candidate_id} has no matching annex source record.",
                )
        candidate_item_ids = []
        try:
            original_qualifier = json.loads(str(row["qualifier_json"] or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            original_qualifier = {}
        for target_index, target_taxonomy_id in enumerate(target_taxonomy_ids, 1):
            target = targets[target_taxonomy_id]
            item_ref = f"{row['family']}-TC{candidate_id:06d}"
            if len(target_taxonomy_ids) > 1:
                item_ref += f"-{target_index:02d}"
            qualifier = {
                "candidate_id": candidate_id,
                "candidate_resolution": action,
                "distinction_reason": row["distinction_reason"],
                "resolution_reason": reason,
            }
            if isinstance(original_qualifier, dict):
                qualifier = {**original_qualifier, **qualifier}
            normalized = {
                "candidate_id": candidate_id,
                "resolved_taxonomy_id": target_taxonomy_id,
            }
            cursor = conn.execute(
                """
                INSERT INTO v4_clause_item(
                  file_key,item_ref,family,taxonomy_id,proposition,statement_polarity,
                  subject_role,counterparty_role,action,object_type,effective_time,
                  source_kind,source_id,source_name,source_ref,parent_clause_ref,
                  related_item_ref,qualifier_json,verbatim,loc_start,loc_end,
                  normalized_json,confidence,txt_hash,taxonomy_version,
                  extractor_version,prompt_version,review_status,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    row["evidence_file_key"],
                    item_ref,
                    row["family"],
                    target_taxonomy_id,
                    f"{target['canonical_ko']}: {str(row['verbatim']).strip()}",
                    _resolved_polarity(str(row["verbatim"])),
                    None,
                    None,
                    None,
                    None,
                    None,
                    source_kind,
                    source_id,
                    row["source_name"],
                    row["source_ref"] or f"¶{row['loc_start']}",
                    row["parent_clause_ref"]
                    or str(row["proposed_ko"]).removeprefix("검토후보: ").strip()
                    or None,
                    None,
                    json.dumps(qualifier, ensure_ascii=False, sort_keys=True),
                    row["verbatim"],
                    row["loc_start"],
                    row["loc_end"],
                    json.dumps(normalized, ensure_ascii=False, sort_keys=True),
                    "high",
                    candidate_hash
                    or current_hash
                    or f"unknown:{row['evidence_file_key']}",
                    taxonomy_version,
                    row["extractor_version"] or "taxonomy-candidate-resolution-1",
                    row["prompt_version"] or "taxonomy-admin-resolution-1",
                    "approved",
                    resolved_at,
                    resolved_at,
                ),
            )
            candidate_item_ids.append(int(cursor.lastrowid))
        materialized[candidate_id] = candidate_item_ids
    return materialized


def resolve_candidates(out: Path, body: dict) -> dict:
    action = body.get("action")
    if action not in {"merge", "promote", "reject"}:
        raise TaxonomyAdminError(400, "VALIDATION_ERROR", "Unknown resolution action.")
    candidate_ids = _candidate_ids(body.get("candidate_ids"))
    reason = str(body.get("reason") or "").strip()
    if action == "reject" and not reason:
        raise TaxonomyAdminError(400, "VALIDATION_ERROR", "Rejection reason is required.")

    with connect_admin(out) as conn:
        conn.execute("BEGIN IMMEDIATE")
        rows = _load_pending_candidates(conn, candidate_ids)
        families = {str(row["family"]) for row in rows}
        if len(families) != 1:
            raise TaxonomyAdminError(
                400, "VALIDATION_ERROR", "A resolution batch must use one family."
            )
        family = next(iter(families))
        target_taxonomy_id: str | None = None
        payload: dict = {"reason": reason}
        new_version: int | None = None

        if action == "merge":
            raw_targets = body.get("taxonomy_ids")
            if raw_targets is None:
                raw_targets = [body.get("taxonomy_id")]
            if not isinstance(raw_targets, list) or not raw_targets:
                raise TaxonomyAdminError(
                    400, "VALIDATION_ERROR", "At least one target taxonomy id is required."
                )
            target_taxonomy_ids = []
            for raw_target in raw_targets:
                taxonomy_id = str(raw_target or "").strip()
                if taxonomy_id and taxonomy_id not in target_taxonomy_ids:
                    target_taxonomy_ids.append(taxonomy_id)
            if not target_taxonomy_ids or len(target_taxonomy_ids) > 20:
                raise TaxonomyAdminError(
                    400, "VALIDATION_ERROR", "Target taxonomy ids must contain 1 to 20 values."
                )
            for taxonomy_id in target_taxonomy_ids:
                target = conn.execute(
                    """
                    SELECT taxonomy_id,family FROM v4_taxonomy_node
                    WHERE taxonomy_id=? AND status='active'
                    """,
                    (taxonomy_id,),
                ).fetchone()
                if target is None:
                    raise TaxonomyAdminError(
                        404, "TAXONOMY_NOT_FOUND", "Target node not found."
                    )
                if target["family"] != family:
                    raise TaxonomyAdminError(
                        400, "FAMILY_MISMATCH", "Target node belongs to another family."
                    )
            target_taxonomy_id = target_taxonomy_ids[0]
            payload["taxonomy_ids"] = target_taxonomy_ids
            resolved_status = "merged"
        elif action == "promote":
            target_taxonomy_id = str(body.get("taxonomy_id") or "").strip().upper()
            canonical_ko = str(body.get("canonical_ko") or "").strip()
            canonical_en = str(body.get("canonical_en") or "").strip()
            definition = str(body.get("definition") or "").strip()
            parent_id = str(body.get("parent_id") or "").strip()
            aliases = _aliases(body.get("aliases"))
            if not TAXONOMY_ID_RE.fullmatch(target_taxonomy_id):
                raise TaxonomyAdminError(
                    400, "VALIDATION_ERROR", "Invalid canonical taxonomy id."
                )
            if not target_taxonomy_id.startswith(f"{family}."):
                raise TaxonomyAdminError(
                    400, "FAMILY_MISMATCH", "Taxonomy id must start with the family."
                )
            if not canonical_ko or not canonical_en or not definition or not parent_id:
                raise TaxonomyAdminError(
                    400,
                    "VALIDATION_ERROR",
                    "Canonical labels, definition, and parent are required.",
                )
            if conn.execute(
                "SELECT 1 FROM v4_taxonomy_node WHERE taxonomy_id=?",
                (target_taxonomy_id,),
            ).fetchone():
                raise TaxonomyAdminError(409, "TAXONOMY_EXISTS", "Taxonomy id already exists.")
            parent = conn.execute(
                """
                SELECT taxonomy_id,family,depth FROM v4_taxonomy_node
                WHERE taxonomy_id=? AND status='active'
                """,
                (parent_id,),
            ).fetchone()
            if parent is None:
                raise TaxonomyAdminError(404, "TAXONOMY_NOT_FOUND", "Parent node not found.")
            if parent["family"] != family:
                raise TaxonomyAdminError(
                    400, "FAMILY_MISMATCH", "Parent belongs to another family."
                )
            alias_values = [canonical_ko, canonical_en, *aliases]
            normalized = [normalize_alias(value) for value in alias_values]
            placeholders = ",".join("?" for _ in normalized)
            collisions = list(
                conn.execute(
                    f"""
                    SELECT DISTINCT taxonomy_id,alias FROM v4_taxonomy_alias
                    WHERE normalized_alias IN ({placeholders})
                    """,
                    normalized,
                )
            )
            if collisions:
                detail = ", ".join(
                    f"{row['alias']}→{row['taxonomy_id']}" for row in collisions[:5]
                )
                raise TaxonomyAdminError(
                    409, "ALIAS_COLLISION", f"Alias already classified: {detail}"
                )
            current_version = int(
                conn.execute(
                    "SELECT value FROM v4_meta WHERE key='taxonomy_version'"
                ).fetchone()[0]
            )
            new_version = current_version + 1
            conn.execute(
                """
                INSERT INTO v4_taxonomy_node(
                  taxonomy_id,parent_id,family,canonical_ko,canonical_en,
                  definition,include_criteria,exclude_criteria,depth,status,
                  taxonomy_version,origin
                ) VALUES (?,?,?,?,?,?,?,? ,?,'active',?,'promoted')
                """,
                (
                    target_taxonomy_id,
                    parent_id,
                    family,
                    canonical_ko,
                    canonical_en,
                    definition,
                    body.get("include_criteria"),
                    body.get("exclude_criteria"),
                    int(parent["depth"]) + 1,
                    new_version,
                ),
            )
            for alias in alias_values:
                conn.execute(
                    """
                    INSERT INTO v4_taxonomy_alias(
                      taxonomy_id,alias,lang,normalized_alias
                    ) VALUES (?,?,'auto',?)
                    """,
                    (target_taxonomy_id, alias, normalize_alias(alias)),
                )
            conn.execute(
                "UPDATE v4_meta SET value=? WHERE key='taxonomy_version'",
                (str(new_version),),
            )
            payload.update(
                {
                    "canonical_ko": canonical_ko,
                    "canonical_en": canonical_en,
                    "definition": definition,
                    "parent_id": parent_id,
                    "aliases": aliases,
                    "taxonomy_version": new_version,
                }
            )
            resolved_status = "approved"
            target_taxonomy_ids = [target_taxonomy_id]
        else:
            resolved_status = "rejected"
            target_taxonomy_ids = []

        resolved_at = utc_now()
        materialized = {}
        if target_taxonomy_id is not None:
            materialized = _materialize_candidate_items(
                conn,
                rows,
                action=action,
                target_taxonomy_ids=target_taxonomy_ids,
                reason=reason,
                resolved_at=resolved_at,
            )
        resolution = {
            "action": action,
            "taxonomy_id": target_taxonomy_id,
            "reason": reason,
            "resolved_at": resolved_at,
        }
        for candidate_id in candidate_ids:
            candidate_resolution = dict(resolution)
            if candidate_id in materialized:
                candidate_resolution["materialized_item_ids"] = materialized[candidate_id]
            conn.execute(
                """
                UPDATE v4_taxonomy_candidate
                SET status=?,resolution_json=?,updated_at=?
                WHERE candidate_id=?
                """,
                (
                    resolved_status,
                    json.dumps(
                        candidate_resolution,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    resolution["resolved_at"],
                    candidate_id,
                ),
            )
        materialized_item_ids = [
            item_id for item_ids in materialized.values() for item_id in item_ids
        ]
        payload["materialized_item_ids"] = materialized_item_ids
        cursor = conn.execute(
            """
            INSERT INTO v4_taxonomy_action_log(
              action,candidate_ids_json,target_taxonomy_id,payload_json,created_at
            ) VALUES (?,?,?,?,?)
            """,
            (
                action,
                json.dumps(candidate_ids),
                target_taxonomy_id,
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                resolution["resolved_at"],
            ),
        )
        conn.commit()
        return {
            "action_id": int(cursor.lastrowid),
            "action": action,
            "candidate_ids": candidate_ids,
            "resolved_count": len(candidate_ids),
            "status": resolved_status,
            "taxonomy_id": target_taxonomy_id,
            "taxonomy_version": new_version,
            "taxonomy_ids": target_taxonomy_ids,
            "materialized_count": len(materialized_item_ids),
            "materialized_item_ids": materialized_item_ids,
        }


def _admin_response(callable_, *args, **kwargs):
    try:
        return 200, callable_(*args, **kwargs)
    except TaxonomyAdminError as exc:
        return exc.status, {"error": {"code": exc.code, "message": exc.message}}


def handle_taxonomy_page(app, match, query, body):
    path = Path(__file__).resolve().parent / "static" / "taxonomy.html"
    return ("raw", 200, "text/html; charset=utf-8", path.read_bytes(), [])


def handle_taxonomy_summary(app, match, query, body):
    return _admin_response(taxonomy_summary, app.out)


def handle_taxonomy_candidates(app, match, query, body):
    return _admin_response(
        list_candidate_clusters,
        app.out,
        status=query.get("status", "pending"),
        family=query.get("family") or None,
        query=query.get("q") or None,
        limit=query.get("limit", 50),
        offset=query.get("offset", 0),
    )


def handle_taxonomy_nodes(app, match, query, body):
    return _admin_response(
        list_taxonomy_nodes,
        app.out,
        family=query.get("family") or None,
    )


def handle_taxonomy_resolve(app, match, query, body):
    try:
        return 200, resolve_candidates(app.out, body)
    except TaxonomyAdminError as exc:
        return exc.status, {"error": {"code": exc.code, "message": exc.message}}
