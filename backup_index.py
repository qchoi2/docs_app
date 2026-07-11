"""cs_index 백업 도구 (BACKEND_REVIEW_PC §2.4).

SQLite 파일(catalog/ui_state/jobs)은 파일 복사가 아니라
`sqlite3.Connection.backup()`으로 백업해 -wal 미체크포인트 내용 누락을 방지한다.
txt 캐시·로그(jsonl 등)는 일반 파일 복사로 담는다.

사용:
    python backup_index.py --out C:\\cs_index --dest C:\\backup
    python backup_index.py --out C:\\cs_index --dest C:\\backup --db-only

복구는 백업 폴더 내용을 원래 위치로 되돌려 놓으면 된다 (README §7).
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from lib.console import configure_utf8_stdio

SQLITE_FILES = ["catalog.sqlite", "ui_state.sqlite", "jobs.sqlite"]
COPY_GLOBS = ["*.jsonl", "*.md"]
COPY_DIRS = ["txt"]


def backup_sqlite(src: Path, dst: Path) -> None:
    """온라인 백업 — WAL 내용까지 일관된 스냅샷을 만든다."""
    with closing(sqlite3.connect(f"file:{src}?mode=ro", uri=True)) as source:
        source.execute("PRAGMA busy_timeout=5000")
        with closing(sqlite3.connect(dst)) as target:
            source.backup(target)


def run_backup(out: Path, dest_root: Path, db_only: bool = False) -> Path:
    out = Path(out)
    if not (out / "catalog.sqlite").exists():
        raise SystemExit(f"ERROR: catalog.sqlite not found in {out}")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = Path(dest_root) / f"cs_index_backup_{stamp}"
    dest.mkdir(parents=True, exist_ok=False)

    for name in SQLITE_FILES:
        src = out / name
        if src.exists():
            backup_sqlite(src, dest / name)
            print(f"backup(sqlite): {name}")

    if not db_only:
        for pattern in COPY_GLOBS:
            for src in sorted(out.glob(pattern)):
                shutil.copy2(src, dest / src.name)
                print(f"copy: {src.name}")
        for dirname in COPY_DIRS:
            src_dir = out / dirname
            if src_dir.is_dir():
                shutil.copytree(src_dir, dest / dirname)
                print(f"copy(dir): {dirname}/")

    print(f"완료: {dest}")
    return dest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WAL-safe cs_index backup.")
    parser.add_argument("--out", required=True, type=Path, help="cs_index 폴더")
    parser.add_argument("--dest", required=True, type=Path, help="백업 저장 폴더")
    parser.add_argument("--db-only", action="store_true",
                        help="SQLite 파일만 백업 (txt 캐시/로그 제외)")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    run_backup(args.out, args.dest, db_only=args.db_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
