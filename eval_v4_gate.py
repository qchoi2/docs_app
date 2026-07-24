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
                structured = search_clause_items(
                    out,
                    taxonomy_id,
                    polarity=polarity,
                    show_duplicates=True,
                    limit=500,
                )
                v4_ms = (time.perf_counter() - v4_started) * 1000
                v4_keys = {str(item["file_key"]) for item in structured["results"]}
                details.append(
                    {
                        **query,
                        "reference_documents": len(gold),
                        "legacy_recall": len(gold & legacy) / len(gold) if gold else None,
                        "v4_recall": len(gold & v4_keys) / len(gold) if gold else None,
                        "legacy_candidate_documents_to_read": len(legacy),
                        "v4_source_documents_to_read": structured["stale_items"],
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


def main(argv=None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("cs_index"))
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/v4_gate_b_golden.json"),
    )
    args = parser.parse_args(argv)
    print(json.dumps(evaluate(args.out, args.manifest), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
