from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from lib.console import configure_utf8_stdio
from lib.normalize import normalize


MARKER_RE = re.compile(r"^\[[^\d\]]*(\d+)\]\t?(.*)$")


def connect(out: Path) -> sqlite3.Connection:
    db_path = out / "catalog.sqlite"
    if not db_path.exists():
        raise FileNotFoundError(f"catalog.sqlite not found: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def txt_cache_path(out: Path, file_key: str) -> Path:
    with closing(connect(out)) as conn:
        row = conn.execute(
            "SELECT txt_path FROM files WHERE file_key = ?",
            (file_key,),
        ).fetchone()
        if row is None:
            raise KeyError(f"file_key not found: {file_key}")
        txt_path = row["txt_path"] or f"txt/{file_key}.txt"
    path = Path(txt_path)
    if not path.is_absolute():
        path = out / path
    if not path.exists():
        raise FileNotFoundError(f"txt cache not found: {path}")
    return path


def read_paragraphs(path: Path) -> List[Tuple[int, str]]:
    paragraphs: List[Tuple[int, str]] = []
    for fallback_index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        match = MARKER_RE.match(line)
        if match:
            paragraphs.append((int(match.group(1)), match.group(2)))
        else:
            paragraphs.append((fallback_index, line))
    return paragraphs


def window_for_para(paragraphs: List[Tuple[int, str]], para: int, context: int) -> List[Tuple[int, str]]:
    if para < 1:
        raise ValueError("--para must be >= 1")
    context = max(context, 0)
    by_number = {number: text for number, text in paragraphs}
    if para not in by_number:
        raise KeyError(f"paragraph not found: {para}")
    start = max(1, para - context)
    end = para + context
    return [(number, text) for number, text in paragraphs if start <= number <= end]


def first_search_hit(paragraphs: List[Tuple[int, str]], term: str) -> Optional[int]:
    needle = normalize(term).casefold()
    if not needle:
        raise ValueError("--search requires a non-empty term")
    for number, text in paragraphs:
        if needle in normalize(text).casefold():
            return number
    return None


def open_text(
    out: Path,
    file_key: str,
    para: Optional[int] = None,
    search: Optional[str] = None,
    context: int = 3,
) -> Dict[str, object]:
    path = txt_cache_path(out, file_key)
    paragraphs = read_paragraphs(path)
    if para is None and search is None:
        raise ValueError("either --para or --search is required")
    if para is not None and search is not None:
        raise ValueError("--para and --search cannot be used together")

    matched_para = para
    if search is not None:
        matched_para = first_search_hit(paragraphs, search)
        if matched_para is None:
            return {
                "file_key": file_key,
                "txt_path": str(path),
                "mode": "search",
                "query": search,
                "matched_para": None,
                "paragraphs": [],
            }

    selected = window_for_para(paragraphs, int(matched_para), context)
    return {
        "file_key": file_key,
        "txt_path": str(path),
        "mode": "para" if para is not None else "search",
        "query": search,
        "matched_para": matched_para,
        "context": max(context, 0),
        "paragraphs": [{"para": number, "text": text} for number, text in selected],
    }


def print_text(result: Dict[str, object]) -> None:
    print(f"file_key: {result['file_key']}")
    print(f"txt_path: {result['txt_path']}")
    if result.get("query") is not None:
        print(f"search: {result['query']}")
    print(f"matched_para: {result.get('matched_para')}")
    for item in result["paragraphs"]:
        print(f"[¶{item['para']}]\t{item['text']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Open a small window from an indexed txt cache.")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--file-key", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--para", type=int)
    group.add_argument("--search")
    parser.add_argument("--context", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = open_text(args.out, args.file_key, args.para, args.search, args.context)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_text(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
