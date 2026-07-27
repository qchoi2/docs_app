"""Store only the human-approved T3 v3 pilot manifest in doc_meta."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from enrich_contracts import enrich_contracts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--result-dir", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    approval = json.loads(args.approval.read_text(encoding="utf-8"))
    approved = {item["file_key"] for item in approval["items"] if item.get("approved")}
    keys = [item["file_key"] for item in manifest["items"]]
    if not approval.get("approved") or set(keys) != approved:
        raise SystemExit("approval record does not cover the manifest exactly")

    processed: list[str] = []
    errors: list[dict] = []
    for key in keys:
        result = enrich_contracts(
            args.out,
            file_key=key,
            input_dir=args.input_dir,
            result_dir=args.result_dir,
            meta_schema_version=3,
        )
        processed.extend(result["processed"])
        errors.extend(result["errors"])

    with sqlite3.connect(args.out / "catalog.sqlite") as conn:
        placeholders = ",".join("?" for _ in keys)
        stored = conn.execute(
            f"SELECT COUNT(*) FROM doc_meta WHERE meta_schema_version=3 AND file_key IN ({placeholders})",
            keys,
        ).fetchone()[0]

    payload = {
        "meta_schema_version": 3,
        "manifest_count": len(keys),
        "processed_count": len(processed),
        "stored_count": stored,
        "error_count": len(errors),
        "processed": processed,
        "errors": errors,
    }
    (args.out / "enrich_progress_v3.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({key: payload[key] for key in ("manifest_count", "processed_count", "stored_count", "error_count")}, ensure_ascii=False))
    return 0 if stored == len(keys) and not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
