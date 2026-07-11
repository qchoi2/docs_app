from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from lib.console import configure_utf8_stdio


META_SCHEMA_VERSION = 1
DEFAULT_PRIORITY = (
    "SPA",
    "SHA",
    "SSA",
    "MOU",
    "ATA/BTA",
    "JVA",
    "CB",
    "BW",
    "EB",
    "二쇱떇援먰솚",
    "遺꾪븷?⑸퀝",
)
REQUIRED_RESULT_KEYS = (
    "file_key",
    "meta_schema_version",
    "parties_json",
    "deal_type_detail",
    "consideration_json",
    "clause_map_json",
    "special_notes",
    "definitions_json",
    "confidence",
)
CONFIDENCE_VALUES = ("low", "med", "high")
DOC_META_EXTRA_COLUMNS = (
    ("parties_json", "TEXT"),
    ("deal_type_detail", "TEXT"),
    ("consideration_json", "TEXT"),
    ("clause_map_json", "TEXT"),
    ("special_notes", "TEXT"),
    ("definitions_json", "TEXT"),
)


@dataclass
class Candidate:
    file_key: str
    path: str
    ctype: str
    lang: str
    content_hash: str
    txt_path: str
    char_count: int


class EnrichError(RuntimeError):
    pass


def load_txt_cache(out_dir: Path, txt_path: str) -> List[Dict[str, object]]:
    path = out_dir / txt_path
    if not path.exists():
        raise EnrichError("txt cache not found: %s" % txt_path)
    paragraphs: List[Dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("[쨋") or "]\t" not in line:
            continue
        marker, text = line.split("]\t", 1)
        try:
            para = int(marker[2:])
        except ValueError:
            continue
        paragraphs.append({"para": para, "text": text})
    return paragraphs


def _priority_index(ctype: str, priority: Sequence[str]) -> int:
    try:
        return list(priority).index(ctype)
    except ValueError:
        return len(priority)


def select_candidates(
    conn: sqlite3.Connection,
    *,
    priority: Sequence[str] = DEFAULT_PRIORITY,
    file_key: Optional[str] = None,
    limit: Optional[int] = None,
    meta_schema_version: int = META_SCHEMA_VERSION,
) -> List[Candidate]:
    params: List[object] = []
    where = [
        "f.status = 'ok'",
        "COALESCE(f.dup_group, f.file_key) = f.file_key",
        """
        NOT EXISTS (
          SELECT 1 FROM doc_meta dm
          WHERE dm.file_key = f.file_key
            AND dm.meta_schema_version = ?
            AND COALESCE(dm.txt_hash, '') = COALESCE(f.content_hash, '')
        )
        """,
    ]
    params.append(meta_schema_version)
    if file_key:
        where.append("f.file_key = ?")
        params.append(file_key)
    rows = conn.execute(
        """
        SELECT f.file_key, f.path, f.ctype, f.lang, f.content_hash,
               f.txt_path, COALESCE(f.char_count, 0)
        FROM files f
        WHERE %s
        """ % " AND ".join(where),
        params,
    ).fetchall()
    candidates = [
        Candidate(
            file_key=str(row[0]),
            path=str(row[1]),
            ctype=str(row[2]),
            lang=str(row[3]),
            content_hash=str(row[4] or ""),
            txt_path=str(row[5] or ""),
            char_count=int(row[6] or 0),
        )
        for row in rows
    ]
    candidates.sort(
        key=lambda item: (
            _priority_index(item.ctype, priority),
            item.ctype,
            item.path,
            item.file_key,
        )
    )
    if limit is not None:
        candidates = candidates[:limit]
    return candidates


def ensure_doc_meta_columns(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(doc_meta)").fetchall()
    existing = {str(row[1]) for row in rows}
    for name, column_type in DOC_META_EXTRA_COLUMNS:
        if name not in existing:
            conn.execute("ALTER TABLE doc_meta ADD COLUMN %s %s" % (name, column_type))


def build_agent_input(out_dir: Path, candidate: Candidate) -> Dict[str, object]:
    return {
        "file_key": candidate.file_key,
        "path": candidate.path,
        "ctype": candidate.ctype,
        "lang": candidate.lang,
        "content_hash": candidate.content_hash,
        "meta_schema_version": META_SCHEMA_VERSION,
        "paragraphs": load_txt_cache(out_dir, candidate.txt_path),
        "instructions": {
            "task": "extract_structured_contract_metadata",
            "no_paid_api": True,
            "output_file": "%s.json" % candidate.file_key,
            "required_keys": list(REQUIRED_RESULT_KEYS),
        },
    }


def write_agent_input(input_dir: Path, payload: Dict[str, object]) -> Path:
    input_dir.mkdir(parents=True, exist_ok=True)
    path = input_dir / ("%s.json" % payload["file_key"])
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _validate_clause_map(value: object) -> None:
    if not isinstance(value, dict):
        raise EnrichError("clause_map_json must be an object")
    for tag, item in value.items():
        if not isinstance(tag, str):
            raise EnrichError("clause_map_json keys must be strings")
        if not isinstance(item, dict):
            raise EnrichError("clause_map_json[%s] must be an object" % tag)
        present = item.get("present")
        if present is not None and not isinstance(present, bool):
            raise EnrichError("clause_map_json[%s].present must be boolean/null" % tag)
        loc_start = item.get("loc_start")
        loc_end = item.get("loc_end")
        for key, value_at_key in (("loc_start", loc_start), ("loc_end", loc_end)):
            if value_at_key is not None:
                if not isinstance(value_at_key, int) or value_at_key < 1:
                    raise EnrichError("clause_map_json[%s].%s must be positive integer/null" % (tag, key))
        if loc_start is not None and loc_end is not None and loc_start > loc_end:
            raise EnrichError("clause_map_json[%s] location range is reversed" % tag)


def validate_result(data: Dict[str, object], candidate: Candidate) -> Dict[str, object]:
    for key in REQUIRED_RESULT_KEYS:
        if key not in data:
            raise EnrichError("missing result key: %s" % key)
    if data["file_key"] != candidate.file_key:
        raise EnrichError("result file_key does not match candidate")
    if int(data["meta_schema_version"]) != META_SCHEMA_VERSION:
        raise EnrichError("unsupported meta_schema_version")
    confidence = str(data["confidence"])
    if confidence not in CONFIDENCE_VALUES:
        raise EnrichError("confidence must be one of: %s" % ", ".join(CONFIDENCE_VALUES))
    _validate_clause_map(data["clause_map_json"])
    for key in ("parties_json", "consideration_json", "definitions_json"):
        if not isinstance(data[key], (dict, list)):
            raise EnrichError("%s must be object or array" % key)
    if not isinstance(data["special_notes"], (str, list)):
        raise EnrichError("special_notes must be string or array")
    return data


def read_result(result_dir: Path, candidate: Candidate) -> Optional[Dict[str, object]]:
    path = result_dir / ("%s.json" % candidate.file_key)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EnrichError("invalid JSON in %s: %s" % (path.name, exc))
    if not isinstance(data, dict):
        raise EnrichError("result JSON must be an object")
    return validate_result(data, candidate)


def upsert_doc_meta(conn: sqlite3.Connection, candidate: Candidate, data: Dict[str, object]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    stored = dict(data)
    stored["extracted_at"] = now
    conn.execute(
        """
        INSERT OR REPLACE INTO doc_meta (
          file_key, meta_schema_version, txt_hash, extracted_at,
          parties_json, deal_type_detail, consideration_json, clause_map_json,
          special_notes, definitions_json, json, confidence
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate.file_key,
            META_SCHEMA_VERSION,
            candidate.content_hash,
            now,
            json.dumps(data["parties_json"], ensure_ascii=False, sort_keys=True),
            str(data["deal_type_detail"]),
            json.dumps(data["consideration_json"], ensure_ascii=False, sort_keys=True),
            json.dumps(data["clause_map_json"], ensure_ascii=False, sort_keys=True),
            json.dumps(data["special_notes"], ensure_ascii=False, sort_keys=True)
            if isinstance(data["special_notes"], list)
            else str(data["special_notes"]),
            json.dumps(data["definitions_json"], ensure_ascii=False, sort_keys=True),
            json.dumps(stored, ensure_ascii=False, sort_keys=True),
            str(data["confidence"]),
        ),
    )


def write_progress(out_dir: Path, payload: Dict[str, object]) -> Path:
    path = out_dir / "enrich_progress.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def enrich_contracts(
    out: Path,
    *,
    priority: Sequence[str] = DEFAULT_PRIORITY,
    file_key: Optional[str] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
    input_dir: Optional[Path] = None,
    result_dir: Optional[Path] = None,
) -> Dict[str, object]:
    out_dir = Path(out).resolve()
    db_path = out_dir / "catalog.sqlite"
    if not db_path.exists():
        raise EnrichError("catalog.sqlite not found: %s" % db_path)
    input_dir = input_dir or out_dir / "enrich_inputs"
    result_dir = result_dir or out_dir / "enrich_results"

    processed: List[str] = []
    pending: List[str] = []
    errors: List[Dict[str, str]] = []
    written_inputs: List[str] = []

    with closing(sqlite3.connect(db_path)) as conn:
        ensure_doc_meta_columns(conn)
        candidates = select_candidates(
            conn,
            priority=priority,
            file_key=file_key,
            limit=limit,
            meta_schema_version=META_SCHEMA_VERSION,
        )
        for candidate in candidates:
            try:
                payload = build_agent_input(out_dir, candidate)
                if not dry_run:
                    written_inputs.append(str(write_agent_input(input_dir, payload)))
                    result = read_result(result_dir, candidate)
                    if result is None:
                        pending.append(candidate.file_key)
                        continue
                    upsert_doc_meta(conn, candidate, result)
                    processed.append(candidate.file_key)
                else:
                    pending.append(candidate.file_key)
            except EnrichError as exc:
                errors.append({"file_key": candidate.file_key, "error": str(exc)})
        if not dry_run:
            conn.commit()

    result_payload = {
        "out": str(out_dir),
        "meta_schema_version": META_SCHEMA_VERSION,
        "candidate_count": len(candidates),
        "processed_count": len(processed),
        "pending_count": len(pending),
        "error_count": len(errors),
        "processed": processed,
        "pending": pending,
        "errors": errors,
        "input_dir": str(input_dir),
        "result_dir": str(result_dir),
        "written_inputs": written_inputs,
        "dry_run": dry_run,
    }
    if not dry_run:
        write_progress(out_dir, result_payload)
    return result_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare and record T3 enrichment metadata.")
    parser.add_argument("--out", required=True, type=Path, help="cs_index folder")
    parser.add_argument("--priority", nargs="*", default=list(DEFAULT_PRIORITY))
    parser.add_argument("--file-key")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--result-dir", type=Path)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = enrich_contracts(
            args.out,
            priority=args.priority,
            file_key=args.file_key,
            limit=args.limit,
            dry_run=args.dry_run,
            input_dir=args.input_dir,
            result_dir=args.result_dir,
        )
    except EnrichError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["error_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
