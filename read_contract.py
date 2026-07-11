from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from lib.console import configure_utf8_stdio
from lib.normalize import normalize
from open_text import read_paragraphs, txt_cache_path
from search_contracts import load_term_dict


STATUS_OK = "ok"
STATUS_UNEVALUATED = "unevaluated"
STATUS_ABSENT = "absent"


def connect(out: Path) -> sqlite3.Connection:
    db_path = out / "catalog.sqlite"
    if not db_path.exists():
        raise FileNotFoundError("catalog.sqlite not found: %s" % db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def normalized_key(value: str) -> str:
    return normalize(value).casefold()


def resolve_section(section: str, out: Optional[Path] = None) -> str:
    requested = normalized_key(section)
    entries = load_term_dict(out) or []
    for entry in entries:
        candidates = [(entry.canonical, "strict")] + list(entry.variants)
        for variant, _strength in candidates:
            if requested == normalized_key(variant):
                return entry.canonical
    return normalize(section)


def parse_clause_map(value: Optional[str]) -> Dict[str, object]:
    if not value:
        return {}
    data = json.loads(value)
    if not isinstance(data, dict):
        raise ValueError("doc_meta.clause_map_json must be an object")
    return data


def find_clause_item(clause_map: Dict[str, object], canonical_section: str) -> Tuple[Optional[str], Optional[Dict[str, object]]]:
    wanted = normalized_key(canonical_section)
    for key, value in clause_map.items():
        if normalized_key(str(key)) == wanted:
            if isinstance(value, dict):
                return str(key), value
            raise ValueError("clause_map_json[%s] must be an object" % key)
    return None, None


def select_range(
    paragraphs: List[Tuple[int, str]],
    loc_start: int,
    loc_end: int,
    context: int,
) -> Tuple[int, int, List[Dict[str, object]]]:
    if loc_start < 1 or loc_end < 1 or loc_start > loc_end:
        raise ValueError("invalid clause location range")
    context = max(context, 0)
    output_start = max(1, loc_start - context)
    output_end = loc_end + context
    selected = [
        {"para": number, "text": text}
        for number, text in paragraphs
        if output_start <= number <= output_end
    ]
    return output_start, output_end, selected


def read_contract(
    out: Path,
    file_key: str,
    section: str,
    context: int = 0,
) -> Dict[str, object]:
    canonical = resolve_section(section, out)
    with closing(connect(out)) as conn:
        file_row = conn.execute(
            """
            SELECT file_key, path, txt_path, content_hash
            FROM files
            WHERE file_key = ?
            """,
            (file_key,),
        ).fetchone()
        if file_row is None:
            raise KeyError("file_key not found: %s" % file_key)

        meta_row = conn.execute(
            """
            SELECT txt_hash, confidence, clause_map_json
            FROM doc_meta
            WHERE file_key = ?
            """,
            (file_key,),
        ).fetchone()

    base: Dict[str, object] = {
        "file_key": file_key,
        "path": file_row["path"],
        "section": section,
        "canonical_section": canonical,
        "status": STATUS_UNEVALUATED,
        "status_label": "미평가",
        "stale": False,
        "stale_label": "",
        "confidence": None,
        "matched_tag": None,
        "loc_start": None,
        "loc_end": None,
        "output_start": None,
        "output_end": None,
        "context": max(context, 0),
        "paragraphs": [],
    }

    if meta_row is None:
        return base

    base["confidence"] = meta_row["confidence"]
    if meta_row["txt_hash"] and file_row["content_hash"] and meta_row["txt_hash"] != file_row["content_hash"]:
        base["stale"] = True
        base["stale_label"] = "재추출 전"

    clause_map = parse_clause_map(meta_row["clause_map_json"])
    matched_tag, clause_item = find_clause_item(clause_map, canonical)
    if clause_item is None:
        return base

    base["matched_tag"] = matched_tag
    present = clause_item.get("present")
    if present is False:
        base["status"] = STATUS_ABSENT
        base["status_label"] = "평가 후 부재"
        return base
    if present is not True:
        return base

    loc_start = clause_item.get("loc_start")
    loc_end = clause_item.get("loc_end")
    if not isinstance(loc_start, int) or not isinstance(loc_end, int):
        raise ValueError("clause_map_json[%s] lacks integer loc_start/loc_end" % matched_tag)

    path = txt_cache_path(out, file_key)
    paragraphs = read_paragraphs(path)
    output_start, output_end, selected = select_range(paragraphs, loc_start, loc_end, context)
    base.update(
        {
            "status": STATUS_OK,
            "status_label": "확인",
            "loc_start": loc_start,
            "loc_end": loc_end,
            "output_start": output_start,
            "output_end": output_end,
            "txt_path": str(path),
            "paragraphs": selected,
        }
    )
    return base


def print_text(result: Dict[str, object]) -> None:
    print("file_key: %s" % result["file_key"])
    print("section: %s" % result["section"])
    print("canonical_section: %s" % result["canonical_section"])
    print("status: %s" % result["status_label"])
    if result.get("stale"):
        print("stale: %s" % result["stale_label"])
    if result.get("matched_tag"):
        print("matched_tag: %s" % result["matched_tag"])
    if result.get("loc_start") is not None:
        print("location: ¶%s-¶%s" % (result["loc_start"], result["loc_end"]))
    if result.get("output_start") is not None:
        print("output_range: ¶%s-¶%s" % (result["output_start"], result["output_end"]))
    for item in result["paragraphs"]:
        print("[¶%s]\t%s" % (item["para"], item["text"]))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read one extracted contract clause by doc_meta paragraph range.")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--file-key", required=True)
    parser.add_argument("--section", required=True)
    parser.add_argument("--context", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = read_contract(args.out, args.file_key, args.section, args.context)
    except Exception as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_text(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
