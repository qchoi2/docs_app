"""Backfill ``recurrence_key`` and the real ``document_count`` (PLAN_REVIEW 교정 B).

``.docs/V4_PLAN.md`` §2 promised that ``v4_taxonomy_candidate.document_count``
tracks "발견 문서 수 자동 갱신".  It never did: every one of the 31,394 rows sits
at the ``DEFAULT 1`` written by the INSERT, so "generic term used across many
contracts" could not be told apart from "one-off definition in one contract".

This tool rebuilds the derived state, and nothing else:

* computes ``lib.v4_candidate_policy.recurrence_key`` for every candidate row;
* rebuilds ``v4_candidate_recurrence`` (one row per key x document) from both
  candidate rows and previously absorbed catch-all items;
* writes ``document_count = COUNT(DISTINCT file_key)`` for that key.

It never changes ``status`` and never touches a human decision.  Run it before
``reclassify_v4_candidate_backlog.py``, which depends on the counts.

Dry-run by default; pass ``--apply`` to write.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from lib.catalog import catalog_path
from lib.console import configure_utf8_stdio
from lib import v4_candidate_policy


BATCH = 5000


def _rows(conn: sqlite3.Connection):
    return conn.execute(
        """
        SELECT candidate_id,family,evidence_file_key,verbatim,status,recurrence_key
        FROM v4_taxonomy_candidate
        ORDER BY candidate_id
        """
    )


def _absorbed_item_rows(conn: sqlite3.Connection):
    """Catch-all items the admission gate already absorbed keep attesting."""

    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='v4_clause_item'"
    ).fetchone()
    if table is None:
        return []
    return conn.execute(
        """
        SELECT file_key,family,normalized_json
        FROM v4_clause_item
        WHERE item_ref LIKE '%-ABS%'
        """
    ).fetchall()


def backfill(*, out: Path, apply: bool) -> dict:
    db_path = catalog_path(out)
    if not db_path.exists():
        raise ValueError(f"catalog.sqlite not found: {db_path}")
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN IMMEDIATE")
        v4_candidate_policy.ensure_recurrence_table(conn)
        try:
            conn.execute(
                "ALTER TABLE v4_taxonomy_candidate ADD COLUMN recurrence_key TEXT"
            )
        except sqlite3.OperationalError:
            pass
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_v4_candidate_recurrence_key_col "
            "ON v4_taxonomy_candidate(recurrence_key)"
        )

        attest: dict[str, set[str]] = defaultdict(set)
        families: dict[str, str] = {}
        keyed: list[tuple[str, int]] = []
        by_status = Counter()
        for row in _rows(conn).fetchall():
            family = str(row["family"])
            key = v4_candidate_policy.recurrence_key(family, str(row["verbatim"]))
            keyed.append((key, int(row["candidate_id"])))
            attest[key].add(str(row["evidence_file_key"]))
            families.setdefault(key, family)
            by_status[str(row["status"])] += 1

        absorbed = 0
        for row in _absorbed_item_rows(conn):
            try:
                normalized = json.loads(str(row["normalized_json"] or "{}"))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            key = normalized.get("recurrence_key")
            if not isinstance(key, str) or not key:
                continue
            attest[key].add(str(row["file_key"]))
            families.setdefault(key, str(row["family"]))
            absorbed += 1

        counts = {key: len(docs) for key, docs in attest.items()}
        distribution = Counter(counts.values())
        summary = {
            "candidate_rows": len(keyed),
            "candidate_rows_by_status": dict(sorted(by_status.items())),
            "absorbed_items_seen": absorbed,
            "distinct_recurrence_keys": len(counts),
            "keys_seen_in_one_document": distribution.get(1, 0),
            "keys_seen_in_multiple_documents": sum(
                n for size, n in distribution.items() if size > 1
            ),
            "max_documents_per_key": max(counts.values()) if counts else 0,
            "rows_document_count_would_change": sum(
                1 for key, _cid in keyed if counts.get(key, 1) != 1
            ),
            "applied": bool(apply),
        }
        if not apply:
            conn.rollback()
            return summary

        conn.execute("DELETE FROM v4_candidate_recurrence")
        conn.executemany(
            """
            INSERT INTO v4_candidate_recurrence(
              recurrence_key,file_key,family,origin,updated_at
            ) VALUES (?,?,?,'backfill',?)
            """,
            [
                (key, file_key, families.get(key, "RW"), now)
                for key, docs in attest.items()
                for file_key in docs
            ],
        )
        for start in range(0, len(keyed), BATCH):
            conn.executemany(
                "UPDATE v4_taxonomy_candidate SET recurrence_key=? WHERE candidate_id=?",
                keyed[start : start + BATCH],
            )
        changed = v4_candidate_policy.sync_document_counts(conn)
        summary["document_count_rows_written"] = int(changed)
        conn.commit()
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
        help="Write the backfill. Without it the tool reports and rolls back.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        summary = backfill(out=args.out, apply=args.apply)
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
