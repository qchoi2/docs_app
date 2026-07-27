"""Provisional Gate B benchmark for V4 atomic proposition retrieval.

The reviewed V4 items are the reference set. This is useful for comparing the
legacy keyword candidate path with structured retrieval, but it is not an
independent human-labelled gold set and therefore cannot by itself close Gate A.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from statistics import mean

from lib.console import configure_utf8_stdio
from v4_search import (
    compare_clause_items,
    connect_v4_ro,
    resolve_taxonomy,
    search_clause_absence,
    search_clause_items,
    taxonomy_descendants,
)


def aliases(conn: sqlite3.Connection, taxonomy_id: str) -> list[str]:
    node = conn.execute(
        "SELECT canonical_ko,canonical_en FROM v4_taxonomy_node WHERE taxonomy_id=?",
        (taxonomy_id,),
    ).fetchone()
    values = [str(node[0]), str(node[1])]
    values.extend(
        str(row[0])
        for row in conn.execute(
            "SELECT alias FROM v4_taxonomy_alias WHERE taxonomy_id=? ORDER BY alias_id",
            (taxonomy_id,),
        )
    )
    # Very short aliases create unusably broad keyword candidates.
    return list(dict.fromkeys(value.strip() for value in values if len(value.strip()) >= 3))


def legacy_candidates(
    conn: sqlite3.Connection, taxonomy_id: str, ctype: str | None = None
) -> set[str]:
    terms = aliases(conn, taxonomy_id)
    if not terms:
        return set()
    result: set[str] = set()
    for term in terms:
        clauses = ["f.status!='missing'", "fts MATCH ?"]
        phrase = '"' + term.replace('"', '""') + '"'
        params: list[object] = [phrase]
        if ctype:
            clauses.append("f.ctype=?")
            params.append(ctype)
        try:
            rows = conn.execute(
                f"""
                SELECT DISTINCT f.file_key
                FROM fts JOIN files f ON f.file_key=fts.file_key
                WHERE {' AND '.join(clauses)}
                """,
                params,
            ).fetchall()
        except sqlite3.OperationalError:
            # Punctuation-only/short terms can be invalid for trigram FTS.
            continue
        result.update(str(row[0]) for row in rows)
    return result


def reviewed_gold(
    conn: sqlite3.Connection, taxonomy_id: str, polarity: str | None
) -> set[str]:
    node = resolve_taxonomy(conn, taxonomy_id)
    scope = taxonomy_descendants(conn, str(node["taxonomy_id"]), True)
    clauses = [
        "review_status='approved'",
        "taxonomy_id IN (%s)" % ",".join("?" for _ in scope),
    ]
    params: list[object] = list(scope)
    if polarity:
        clauses.append("statement_polarity=?")
        params.append(polarity)
    return {
        str(row[0])
        for row in conn.execute(
            f"SELECT DISTINCT file_key FROM v4_clause_item WHERE {' AND '.join(clauses)}",
            params,
        )
    }


def comparison_keys(out: Path, taxonomy_id: str) -> list[str] | None:
    present = search_clause_items(
        out, taxonomy_id, show_duplicates=True, limit=500
    )["results"]
    absence = search_clause_absence(
        out, taxonomy_id, show_duplicates=True, limit=500
    )
    states = [
        next((str(item["file_key"]) for item in present if item["freshness"] == "current"), None),
        next((str(item["file_key"]) for item in absence["confirmed_absent"]), None),
        next((str(item["file_key"]) for item in absence["needs_review"]), None),
    ]
    return states if all(states) and len(set(states)) == 3 else None


def paged_v4_keys(
    out: Path, taxonomy_id: str, polarity: str | None
) -> tuple[set[str], int]:
    keys: set[str] = set()
    offset = 0
    stale = 0
    while True:
        page = search_clause_items(
            out,
            taxonomy_id,
            polarity=polarity,
            show_duplicates=True,
            limit=500,
            offset=offset,
        )
        keys.update(str(item["file_key"]) for item in page["results"])
        stale += sum(
            item["freshness"] == "stale" for item in page["results"]
        )
        if not page["has_more"]:
            return keys, stale
        offset = int(page["next_offset"])


def evaluate(out: Path, manifest: Path) -> dict:
    spec = json.loads(manifest.read_text(encoding="utf-8"))
    details = []
    with closing(connect_v4_ro(out)) as conn:
        searchable_docs = int(
            conn.execute("SELECT COUNT(*) FROM files WHERE status!='missing'").fetchone()[0]
        )
        for query in spec["queries"]:
            started = time.perf_counter()
            taxonomy_id = query["taxonomy_id"]
            polarity = query.get("polarity")
            mode = query["mode"]
            if mode == "present":
                gold = reviewed_gold(conn, taxonomy_id, polarity)
                legacy_started = time.perf_counter()
                legacy = legacy_candidates(conn, taxonomy_id)
                legacy_ms = (time.perf_counter() - legacy_started) * 1000
                v4_started = time.perf_counter()
                v4_keys, stale_items = paged_v4_keys(
                    out, taxonomy_id, polarity
                )
                v4_ms = (time.perf_counter() - v4_started) * 1000
                details.append(
                    {
                        **query,
                        "reference_documents": len(gold),
                        "legacy_recall": len(gold & legacy) / len(gold) if gold else None,
                        "v4_recall": len(gold & v4_keys) / len(gold) if gold else None,
                        "legacy_candidate_documents_to_read": len(legacy),
                        "v4_source_documents_to_read": stale_items,
                        "legacy_ms": round(legacy_ms, 3),
                        "v4_ms": round(v4_ms, 3),
                        "status": "scored" if gold else "unscored_no_reference",
                    }
                )
            elif mode == "absent":
                legacy_started = time.perf_counter()
                legacy_candidates(conn, taxonomy_id)
                legacy_ms = (time.perf_counter() - legacy_started) * 1000
                v4_started = time.perf_counter()
                result = search_clause_absence(
                    out, taxonomy_id, show_duplicates=True, limit=500
                )
                v4_ms = (time.perf_counter() - v4_started) * 1000
                details.append(
                    {
                        **query,
                        "confirmed_absent": result["confirmed_absent_count"],
                        "needs_review": result["needs_review_count"],
                        "legacy_documents_to_read": searchable_docs,
                        "v4_source_documents_to_read": result["needs_review_count"],
                        "legacy_ms": round(legacy_ms, 3),
                        "v4_ms": round(v4_ms, 3),
                        "status": (
                            "scored"
                            if result["confirmed_absent_count"] > 0
                            else "unscored_no_confirmed_absence"
                        ),
                    }
                )
            else:
                keys = comparison_keys(out, taxonomy_id)
                if keys is None:
                    details.append({**query, "status": "unscored_missing_state_mix"})
                    continue
                v4_started = time.perf_counter()
                result = compare_clause_items(out, taxonomy_id, keys)
                v4_ms = (time.perf_counter() - v4_started) * 1000
                details.append(
                    {
                        **query,
                        "file_keys": keys,
                        "states": [item["state"] for item in result["comparison"]],
                        "legacy_documents_to_read": len(keys),
                        "v4_source_documents_to_read": sum(
                            item["state"] == "needs_review"
                            for item in result["comparison"]
                        ),
                        "v4_ms": round(v4_ms, 3),
                        "status": "scored",
                    }
                )
            details[-1]["elapsed_ms"] = round(
                (time.perf_counter() - started) * 1000, 3
            )
    present = [row for row in details if row["mode"] == "present" and row["status"] == "scored"]
    scored = [row for row in details if row["status"] == "scored"]
    legacy_reads = sum(
        row.get("legacy_candidate_documents_to_read", row.get("legacy_documents_to_read", 0))
        for row in scored
    )
    v4_reads = sum(row.get("v4_source_documents_to_read", 0) for row in scored)
    return {
        "benchmark": "V4 Gate B provisional",
        "reference": "reviewed V4 items, not independent human labels",
        "query_count": len(details),
        "scored_count": len(scored),
        "unscored_count": len(details) - len(scored),
        "present_mean_legacy_recall": round(
            mean(row["legacy_recall"] for row in present), 4
        ) if present else None,
        "present_mean_v4_recall": round(
            mean(row["v4_recall"] for row in present), 4
        ) if present else None,
        "legacy_documents_to_read": legacy_reads,
        "v4_source_documents_to_read": v4_reads,
        "document_read_reduction": round(1 - (v4_reads / legacy_reads), 4)
        if legacy_reads
        else None,
        "legacy_measured_total_ms": round(
            sum(float(row.get("legacy_ms", 0)) for row in scored), 3
        ),
        "v4_measured_total_ms": round(
            sum(float(row.get("v4_ms", 0)) for row in scored), 3
        ),
        "details": details,
    }


# ---------------------------------------------------------------------------
# Pooled Gate B (independent). Instead of scoring against V4's own approved
# items (self-referential), the owner verifies only the *pool* of results the
# two methods actually surface. From those verdicts we derive precision and
# pooled relative recall — no exhaustive corpus labelling required.
# ---------------------------------------------------------------------------

_INTENT_MODE = {"existence": "present", "absence": "absent", "comparison": "compare"}


def score_pooled_present(arms: dict, verified: dict) -> dict:
    """Precision + pooled relative recall for present-mode retrieval arms."""
    correct = set(verified.get("correct", []))
    incorrect = set(verified.get("incorrect", []))
    judged = correct | incorrect
    scores = {}
    for name, keys in arms.items():
        keys = set(keys)
        judged_in_arm = keys & judged
        hit = len(keys & correct)
        scores[name] = {
            "returned": len(keys),
            "correct": hit,
            "precision": round(hit / len(judged_in_arm), 4) if judged_in_arm else None,
            "relative_recall": round(hit / len(correct), 4) if correct else None,
        }
    return scores


def score_pooled_absence(confirmed: set, needs_review: set, verified: dict) -> dict:
    """Confirmed-absence precision + coverage backlog for absence retrieval."""
    correct = set(verified.get("correct", []))       # verified truly absent
    incorrect = set(verified.get("incorrect", []))   # false absence (actually present)
    judged = confirmed & (correct | incorrect)
    hit = len(confirmed & correct)
    return {
        "confirmed_absent_returned": len(confirmed),
        "confirmed_absent_correct": hit,
        "confirmed_absent_false": len(confirmed & incorrect),
        "confirmed_absent_precision": round(hit / len(judged), 4) if judged else None,
        "needs_review_backlog": len(needs_review),
    }


def _pool_present(conn: sqlite3.Connection, out: Path, taxonomy_id: str, ctype, depth: int):
    """Top-`depth` from each arm by its native ranking, capped for human review.

    v4 arm uses the structured search ranking; the legacy FTS arm is a bounded
    deterministic sample (by file_key) — full breadth is still reported as
    arm_returned so the owner sees how wide each arm actually was.
    """
    legacy_full = legacy_candidates(conn, taxonomy_id, ctype)
    legacy = set(sorted(legacy_full)[:depth])
    ranked = search_clause_items(
        out, taxonomy_id, ctype=ctype, show_duplicates=True, limit=depth
    )["results"]
    v4 = {str(item["file_key"]) for item in ranked}
    return {"legacy": legacy, "v4": v4}, {"legacy": len(legacy_full)}


def evaluate_pooled(
    out: Path, seed_path: Path, pool_depth: int = 25, verdicts: dict | None = None
) -> dict:
    import yaml

    seed = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
    queries = seed.get("queries", [])
    verdicts = verdicts or {}
    details = []
    with closing(connect_v4_ro(out)) as conn:
        for query in queries:
            qid = query.get("id")
            intent = query.get("intent")
            mode = _INTENT_MODE.get(intent)
            taxonomy = query.get("taxonomy")
            # External verdicts (from verify_gate_b ingest) win over seed placeholders.
            verified = verdicts.get(qid) or query.get("pool_verified") or {}
            row = {"id": qid, "intent": intent, "taxonomy": taxonomy}
            if not taxonomy or mode is None:
                row["status"] = "unbound"
                details.append(row)
                continue
            try:
                resolve_taxonomy(conn, str(taxonomy))
            except Exception:
                row["status"] = "unresolved_taxonomy"
                details.append(row)
                continue
            ctype = query.get("ctype")
            judged = (
                set(verified.get("correct", []))
                | set(verified.get("incorrect", []))
                | set(verified.get("unknown", []))
            )
            if mode == "present":
                arms, breadth = _pool_present(conn, out, str(taxonomy), ctype, pool_depth)
                pool = arms["legacy"] | arms["v4"]
                row.update(
                    {
                        "mode": "present",
                        "pool_size": len(pool),
                        "arm_pooled": {k: len(v) for k, v in arms.items()},
                        "legacy_full_breadth": breadth["legacy"],
                        "unjudged": sorted(pool - judged),
                        "scores": score_pooled_present(arms, verified) if judged else None,
                        "status": "scored" if judged else "pending_verification",
                    }
                )
            elif mode == "absent":
                result = search_clause_absence(
                    out, str(taxonomy), ctype=ctype, show_duplicates=True, limit=pool_depth
                )
                confirmed = {str(r["file_key"]) for r in result["confirmed_absent"]}
                review = {str(r["file_key"]) for r in result["needs_review"]}
                pool = confirmed | review
                row.update(
                    {
                        "mode": "absent",
                        "pool_size": len(pool),
                        "confirmed_absent": len(confirmed),
                        "needs_review": len(review),
                        "unjudged": sorted(pool - judged),
                        "scores": score_pooled_absence(confirmed, review, verified)
                        if judged
                        else None,
                        "status": "scored" if judged else "pending_verification",
                    }
                )
            else:  # compare: pool of candidate docs only, no recall
                arms, _ = _pool_present(conn, out, str(taxonomy), ctype, pool_depth)
                pool = arms["legacy"] | arms["v4"]
                row.update(
                    {
                        "mode": "compare",
                        "pool_size": len(pool),
                        "unjudged": sorted(pool - judged),
                        "status": "worklist_only",
                    }
                )
            details.append(row)

    bound = [r for r in details if r["status"] not in ("unbound", "unresolved_taxonomy")]
    scored = [r for r in details if r["status"] == "scored"]
    pending = [r for r in details if r["status"] == "pending_verification"]
    present_scored = [r for r in scored if r.get("mode") == "present"]
    return {
        "benchmark": "V4 Gate B (independent, pooled verification)",
        "method": "pool = union(legacy_fts, v4_structured); owner verifies pool -> precision + relative recall",
        "seed": str(seed_path),
        "query_count": len(details),
        "bound_count": len(bound),
        "unbound": [r["id"] for r in details if r["status"] in ("unbound", "unresolved_taxonomy")],
        "scored_count": len(scored),
        "pending_verification_count": len(pending),
        "total_unjudged_pool_items": sum(len(r.get("unjudged", [])) for r in details),
        "present_mean_relative_recall": {
            "legacy": _safe_mean(
                r["scores"]["legacy"]["relative_recall"] for r in present_scored
            ),
            "v4": _safe_mean(
                r["scores"]["v4"]["relative_recall"] for r in present_scored
            ),
        }
        if present_scored
        else None,
        "details": details,
    }


def _safe_mean(values):
    vals = [v for v in values if v is not None]
    return round(mean(vals), 4) if vals else None


def main(argv=None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("cs_index"))
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/v4_gate_b_golden.json"),
    )
    parser.add_argument(
        "--pooled",
        action="store_true",
        help="Independent pooled-verification Gate B (uses --seed).",
    )
    parser.add_argument(
        "--seed",
        type=Path,
        default=Path("data/golden_queries_v4_independent.seed.yaml"),
        help="Pooled-mode seed with per-query taxonomy binding and pool_verified.",
    )
    parser.add_argument(
        "--worklist",
        type=Path,
        help="Write the owner verification worklist (unjudged pool items) to this JSON path.",
    )
    parser.add_argument(
        "--pool-depth",
        type=int,
        default=25,
        help="Max results pooled per arm for owner verification (default 25).",
    )
    parser.add_argument(
        "--verdicts",
        type=Path,
        default=Path("data/v4_gate_b_verdicts.json"),
        help="Owner verdicts JSON (qid -> {correct,incorrect,unknown}); merged over seed.",
    )
    args = parser.parse_args(argv)
    if args.pooled:
        verdicts = None
        if args.verdicts and args.verdicts.exists():
            verdicts = json.loads(args.verdicts.read_text(encoding="utf-8"))
        report = evaluate_pooled(
            args.out, args.seed, pool_depth=args.pool_depth, verdicts=verdicts
        )
        if args.worklist:
            worklist = {
                r["id"]: r.get("unjudged", [])
                for r in report["details"]
                if r.get("unjudged")
            }
            args.worklist.write_text(
                json.dumps(worklist, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(evaluate(args.out, args.manifest), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
