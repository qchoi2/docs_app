"""Initialize or migrate the V4 schema and controlled taxonomy."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from v4_schema import FAMILIES, SEED_TAXONOMY, initialize_v4_schema


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    db = args.out / "catalog.sqlite"
    if not db.exists():
        raise SystemExit(f"catalog.sqlite not found: {db}")
    with sqlite3.connect(db) as conn:
        initialize_v4_schema(conn)
        conn.commit()
        counts = {
            "taxonomy_nodes": conn.execute("SELECT COUNT(*) FROM v4_taxonomy_node").fetchone()[0],
            "taxonomy_aliases": conn.execute("SELECT COUNT(*) FROM v4_taxonomy_alias").fetchone()[0],
            "clause_items": conn.execute("SELECT COUNT(*) FROM v4_clause_item").fetchone()[0],
            "coverage": conn.execute("SELECT COUNT(*) FROM v4_document_coverage").fetchone()[0],
            "source_coverage": conn.execute("SELECT COUNT(*) FROM v4_source_coverage").fetchone()[0],
            "schema_revision": conn.execute(
                "SELECT value FROM v4_meta WHERE key='schema_revision'"
            ).fetchone()[0],
            "taxonomy_version": conn.execute(
                "SELECT value FROM v4_meta WHERE key='taxonomy_version'"
            ).fetchone()[0],
        }
    print(json.dumps(counts, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
