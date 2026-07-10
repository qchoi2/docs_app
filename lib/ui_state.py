"""ui_state.sqlite — 사용자 UI 상태 저장소 (IMPLEMENTATION_BRIEF §2.11).

경계 원칙:
- `query_log.jsonl` 은 CLI/운영 자동 분석용 로그다 (search_contracts.py가 기록).
- `ui_state.sqlite` 는 사용자가 UI에서 다시 여는 재생성 불가능한 상태다.
- `catalog.sqlite` 는 재색인으로 언제든 재구축되는 색인 산출물이므로
  사용자 상태를 절대 넣지 않는다. `--full` 재색인도 ui_state를 건드리지 않는다.

UI-3 현재 범위는 search_history(최근 검색)만 사용한다. 나머지 테이블은
Brief §2.11 예약 스키마로 함께 생성만 해 둔다.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


UI_STATE_DDL = """
CREATE TABLE IF NOT EXISTS search_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  query TEXT NOT NULL,
  filters_json TEXT,
  expand_mode TEXT,
  corpus_scope TEXT,
  result_count INTEGER,
  top_file_keys_json TEXT,
  duration_ms INTEGER,
  user_note TEXT
);
CREATE TABLE IF NOT EXISTS saved_searches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  query TEXT NOT NULL,
  filters_json TEXT,
  expand_mode TEXT,
  created_at TEXT NOT NULL,
  last_run_at TEXT
);
CREATE TABLE IF NOT EXISTS user_marks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_key TEXT NOT NULL,
  para INTEGER,
  mark_type TEXT NOT NULL,
  note TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS result_feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  search_history_id INTEGER,
  file_key TEXT,
  para INTEGER,
  feedback TEXT NOT NULL,
  note TEXT,
  created_at TEXT NOT NULL
);
"""


def ui_state_path(out: Path) -> Path:
    return Path(out) / "ui_state.sqlite"


def connect_ui_state(out: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(ui_state_path(out))
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn


def ensure_ui_state(out: Path) -> Path:
    path = ui_state_path(out)
    with closing(connect_ui_state(out)) as conn:
        conn.executescript(UI_STATE_DDL)
    return path


def record_search(
    out: Path,
    query: str,
    filters: Dict[str, object],
    expand_mode: str,
    result_count: int,
    top_file_keys: Optional[List[str]] = None,
    duration_ms: Optional[int] = None,
) -> None:
    with closing(connect_ui_state(out)) as conn:
        conn.execute(
            """
            INSERT INTO search_history
              (ts, query, filters_json, expand_mode, corpus_scope,
               result_count, top_file_keys_json, duration_ms)
            VALUES (?, ?, ?, ?, NULL, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                query,
                json.dumps(filters, ensure_ascii=False),
                expand_mode,
                result_count,
                json.dumps(top_file_keys or [], ensure_ascii=False),
                duration_ms,
            ),
        )
        conn.commit()


def recent_searches(out: Path, limit: int = 10) -> List[Dict[str, object]]:
    """최근 검색 목록 — 같은 조건은 최신 1건만 남긴다."""
    with closing(connect_ui_state(out)) as conn:
        rows = conn.execute(
            """
            SELECT id, ts, query, filters_json, expand_mode, result_count
            FROM search_history
            ORDER BY id DESC
            LIMIT 100
            """
        ).fetchall()
    seen = set()
    items: List[Dict[str, object]] = []
    for row in rows:
        dedupe_key = (row["query"], row["filters_json"], row["expand_mode"])
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        try:
            filters = json.loads(row["filters_json"] or "{}")
        except json.JSONDecodeError:
            filters = {}
        items.append(
            {
                "id": row["id"],
                "ts": row["ts"],
                "query": row["query"],
                "filters": filters,
                "expand_mode": row["expand_mode"],
                "result_count": row["result_count"],
            }
        )
        if len(items) >= limit:
            break
    return items
