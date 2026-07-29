"""Reclassify the pending taxonomy-candidate backlog (V4_PLAN §9.2 T-D).

The 29,807 pending rows in ``v4_taxonomy_candidate`` are not 29,807 taxonomy
proposals.  Most are a single paragraph from a single contract that the
rule-based classifier could not place, minted before the admission gate in
``lib.v4_candidate_policy`` existed.  While they sit in ``pending`` they keep
their document's family coverage at ``needs_review``, which is what switches off
the absence ("이 조항이 없는 계약") query for that family.

This tool sorts the existing backlog with the same predicate the generator now
applies at write time:

* **generic** -- the row names a specific sub-node (dotted
  ``recommended_parent_id``) or its normalized recurrence key is attested in
  ``--min-documents`` or more distinct documents.  Kept ``pending`` for human
  review; these are the real taxonomy proposals.
* **document-specific one-off** -- everything else.  Retired to ``merged`` with
  ``resolution_json.action = 'absorb_catch_all'`` and materialized as a
  ``v4_clause_item`` under the family catch-all node, so the text stays
  FTS-searchable (V4_PLAN 원칙 5) while no longer blocking absence.

Human decisions are never touched: the tool only ever reads and writes rows with
``status='pending'``, and it verifies the approved/merged/rejected counts that
predate this run are unchanged before committing.

Dry-run by default; pass ``--apply`` to write.  Run
``backfill_v4_candidate_recurrence.py --apply`` first -- this tool refuses to
run when ``recurrence_key`` has not been backfilled.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from lib.catalog import catalog_path
from lib.console import configure_utf8_stdio
from lib import v4_candidate_policy


POLICY_ACTION = "absorb_catch_all"
BATCH = 2000


class ReclassifyError(ValueError):
    pass


def _human_decision_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Count resolutions that a person made, excluding policy absorptions."""

    counts = {}
    for row in conn.execute(
        """
        SELECT status, COUNT(*) AS n
        FROM v4_taxonomy_candidate
        WHERE status<>'pending'
          AND COALESCE(json_extract(resolution_json,'$.action'),'') <> ?
        GROUP BY status
        """,
        (POLICY_ACTION,),
    ):
        counts[str(row["status"])] = int(row["n"])
    return counts


def classify(conn: sqlite3.Connection, *, min_documents: int) -> dict:
    rows = conn.execute(
        """
        SELECT candidate_id,family,recommended_parent_id,evidence_file_key,
               verbatim,recurrence_key,document_count,source_kind,source_id,
               source_name,source_ref,parent_clause_ref,qualifier_json,
               distinction_reason,loc_start,loc_end,txt_hash,proposed_ko,
               extractor_version,prompt_version
        FROM v4_taxonomy_candidate
        WHERE status='pending'
        ORDER BY candidate_id
        """
    ).fetchall()
    missing_key = sum(1 for row in rows if not str(row["recurrence_key"] or ""))
    if rows and missing_key:
        raise ReclassifyError(
            f"{missing_key} pending rows have no recurrence_key; run "
            "backfill_v4_candidate_recurrence.py --apply first"
        )
    generic: list[sqlite3.Row] = []
    oneoff: list[sqlite3.Row] = []
    reasons = Counter()
    per_family = {}
    for row in rows:
        admission = v4_candidate_policy.admit(
            family=str(row["family"]),
            verbatim=str(row["verbatim"]),
            recommended_parent_id=row["recommended_parent_id"],
            document_count=int(row["document_count"] or 1),
            min_documents=min_documents,
        )
        reasons[admission.reason] += 1
        bucket = per_family.setdefault(
            str(row["family"]), {"generic": 0, "one_off": 0}
        )
        if admission.admitted:
            generic.append(row)
            bucket["generic"] += 1
        else:
            oneoff.append(row)
            bucket["one_off"] += 1
    return {
        "rows": rows,
        "generic": generic,
        "one_off": oneoff,
        "reasons": dict(sorted(reasons.items())),
        "per_family": {k: per_family[k] for k in sorted(per_family)},
    }


def _absorb(conn: sqlite3.Connection, rows, *, now: str) -> int:
    taxonomy_version_row = conn.execute(
        "SELECT value FROM v4_meta WHERE key='taxonomy_version'"
    ).fetchone()
    taxonomy_version = int(taxonomy_version_row[0]) if taxonomy_version_row else 0
    node_family = {
        str(r[0]): str(r[1])
        for r in conn.execute(
            "SELECT taxonomy_id,family FROM v4_taxonomy_node WHERE status='active'"
        )
    }
    made = 0
    for row in rows:
        family = str(row["family"])
        target = v4_candidate_policy.catch_all_taxonomy_id(family)
        if target not in node_family:
            raise ReclassifyError(f"catch-all node missing for family {family}: {target}")
        candidate_id = int(row["candidate_id"])
        try:
            qualifier = json.loads(str(row["qualifier_json"] or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            qualifier = {}
        if not isinstance(qualifier, dict):
            qualifier = {}
        qualifier.update(
            {
                "candidate_id": candidate_id,
                "candidate_admission": v4_candidate_policy.ABSORBED_MARKER,
                "admission_policy": v4_candidate_policy.POLICY_VERSION,
                "candidate_resolution": POLICY_ACTION,
                "distinction_reason": row["distinction_reason"],
            }
        )
        normalized = {
            "candidate_id": candidate_id,
            "recurrence_key": str(row["recurrence_key"] or ""),
            "absorbed_by": v4_candidate_policy.POLICY_VERSION,
            "resolved_taxonomy_id": target,
        }
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO v4_clause_item(
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
                f"{family}-ABS{candidate_id:06d}",
                family,
                target,
                str(row["verbatim"]).strip(),
                "not_applicable",
                None,
                None,
                None,
                (
                    v4_candidate_policy.defined_term(str(row["verbatim"]))
                    if family == "DEF"
                    else None
                ),
                None,
                str(row["source_kind"] or "body"),
                row["source_id"],
                row["source_name"],
                row["source_ref"] or f"¶{row['loc_start']}",
                row["parent_clause_ref"]
                or v4_candidate_policy.strip_candidate_prefix(row["proposed_ko"])
                or None,
                None,
                json.dumps(qualifier, ensure_ascii=False, sort_keys=True),
                row["verbatim"],
                row["loc_start"],
                row["loc_end"],
                json.dumps(normalized, ensure_ascii=False, sort_keys=True),
                "low",
                row["txt_hash"] or f"unknown:{row['evidence_file_key']}",
                taxonomy_version,
                row["extractor_version"] or "candidate-admission-policy",
                row["prompt_version"] or "candidate-admission-policy",
                "approved",
                now,
                now,
            ),
        )
        made += int(cursor.rowcount or 0)
    return made


def reclassify(
    *, out: Path, apply: bool, min_documents: int, report: Path | None = None
) -> dict:
    db_path = catalog_path(out)
    if not db_path.exists():
        raise ReclassifyError(f"catalog.sqlite not found: {db_path}")
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN IMMEDIATE")
        before_human = _human_decision_counts(conn)
        buckets = classify(conn, min_documents=min_documents)
        summary = {
            "pending_before": len(buckets["rows"]),
            "keep_as_candidate_generic": len(buckets["generic"]),
            "retire_document_specific_one_off": len(buckets["one_off"]),
            "pending_after": len(buckets["generic"]),
            "admission_reasons": buckets["reasons"],
            "per_family": buckets["per_family"],
            "human_decisions_before": before_human,
            "min_documents": min_documents,
            "applied": bool(apply),
        }
        if apply:
            absorbed = _absorb(conn, buckets["one_off"], now=now)
            resolution = json.dumps(
                {
                    "action": POLICY_ACTION,
                    "policy": v4_candidate_policy.POLICY_VERSION,
                    "decided_by": "policy",
                    "reason": (
                        "document-specific one-off; absorbed into the family "
                        "catch-all and kept FTS-searchable"
                    ),
                    "resolved_at": now,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            ids = [int(row["candidate_id"]) for row in buckets["one_off"]]
            for start in range(0, len(ids), BATCH):
                chunk = ids[start : start + BATCH]
                placeholders = ",".join("?" for _ in chunk)
                conn.execute(
                    f"""
                    UPDATE v4_taxonomy_candidate
                    SET status='merged',resolution_json=?,updated_at=?
                    WHERE status='pending' AND candidate_id IN ({placeholders})
                    """,
                    (resolution, now, *chunk),
                )
            after_human = _human_decision_counts(conn)
            if after_human != before_human:
                raise ReclassifyError(
                    "human decision counts changed during reclassification: "
                    f"{before_human} -> {after_human}"
                )
            # ``action`` is CHECK-constrained to the UI-5 verbs; the policy run
            # is a merge into the catch-all, distinguished inside the payload.
            conn.execute(
                """
                INSERT INTO v4_taxonomy_action_log(
                  action,candidate_ids_json,target_taxonomy_id,payload_json,created_at
                ) VALUES ('merge',?,?,?,?)
                """,
                (
                    json.dumps(ids),
                    None,
                    json.dumps(
                        {**summary, "policy_action": POLICY_ACTION},
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    now,
                ),
            )
            summary["absorbed_items_created"] = absorbed
            summary["human_decisions_after"] = after_human
            conn.commit()
        else:
            conn.rollback()
        if report is not None:
            report.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return summary
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the reclassification. Without it the tool reports and rolls back.",
    )
    parser.add_argument(
        "--min-documents",
        type=int,
        default=v4_candidate_policy.GENERIC_MIN_DOCUMENTS,
        help="Documents a candidate must recur in to stay a taxonomy proposal.",
    )
    parser.add_argument("--report", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        summary = reclassify(
            out=args.out,
            apply=args.apply,
            min_documents=args.min_documents,
            report=args.report,
        )
    except (OSError, ReclassifyError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
