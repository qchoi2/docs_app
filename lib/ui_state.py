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
CREATE TABLE IF NOT EXISTS research_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  note TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS session_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL,
  file_key TEXT NOT NULL,
  para INTEGER,
  note TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS compare_lists (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS compare_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  list_id INTEGER NOT NULL,
  file_key TEXT NOT NULL,
  para INTEGER,
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _loads_json(raw: Optional[str], fallback):
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


def saved_searches(out: Path, limit: int = 50) -> List[Dict[str, object]]:
    with closing(connect_ui_state(out)) as conn:
        rows = conn.execute(
            """
            SELECT id, name, query, filters_json, expand_mode, created_at, last_run_at
            FROM saved_searches
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "query": row["query"],
            "filters": _loads_json(row["filters_json"], {}),
            "expand_mode": row["expand_mode"],
            "created_at": row["created_at"],
            "last_run_at": row["last_run_at"],
        }
        for row in rows
    ]


def create_saved_search(
    out: Path,
    name: str,
    query: str,
    filters: Dict[str, object],
    expand_mode: str,
) -> Dict[str, object]:
    now = _utc_now()
    with closing(connect_ui_state(out)) as conn:
        cur = conn.execute(
            """
            INSERT INTO saved_searches
              (name, query, filters_json, expand_mode, created_at, last_run_at)
            VALUES (?, ?, ?, ?, ?, NULL)
            """,
            (name, query, json.dumps(filters, ensure_ascii=False), expand_mode, now),
        )
        conn.commit()
        search_id = cur.lastrowid
    return {
        "id": search_id,
        "name": name,
        "query": query,
        "filters": filters,
        "expand_mode": expand_mode,
        "created_at": now,
        "last_run_at": None,
    }


def delete_saved_search(out: Path, search_id: int) -> bool:
    with closing(connect_ui_state(out)) as conn:
        cur = conn.execute("DELETE FROM saved_searches WHERE id = ?", (search_id,))
        conn.commit()
        return cur.rowcount > 0


def record_feedback(
    out: Path,
    feedback: str,
    *,
    search_history_id: Optional[int] = None,
    file_key: Optional[str] = None,
    para: Optional[int] = None,
    note: Optional[str] = None,
) -> Dict[str, object]:
    now = _utc_now()
    with closing(connect_ui_state(out)) as conn:
        cur = conn.execute(
            """
            INSERT INTO result_feedback
              (search_history_id, file_key, para, feedback, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (search_history_id, file_key, para, feedback, note, now),
        )
        conn.commit()
        feedback_id = cur.lastrowid
    return {
        "id": feedback_id,
        "search_history_id": search_history_id,
        "file_key": file_key,
        "para": para,
        "feedback": feedback,
        "note": note,
        "created_at": now,
    }


def feedback_summary(out: Path) -> Dict[str, int]:
    with closing(connect_ui_state(out)) as conn:
        rows = conn.execute(
            "SELECT feedback, COUNT(*) FROM result_feedback GROUP BY feedback"
        ).fetchall()
    return {str(row[0]): int(row[1]) for row in rows}


def add_mark(
    out: Path,
    file_key: str,
    para: Optional[int],
    mark_type: str,
    note: Optional[str],
) -> Dict[str, object]:
    now = _utc_now()
    with closing(connect_ui_state(out)) as conn:
        cur = conn.execute(
            """
            INSERT INTO user_marks (file_key, para, mark_type, note, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (file_key, para, mark_type, note, now),
        )
        conn.commit()
        mark_id = cur.lastrowid
    return {
        "id": mark_id,
        "file_key": file_key,
        "para": para,
        "mark_type": mark_type,
        "note": note,
        "created_at": now,
    }


def list_marks(out: Path, limit: int = 100) -> List[Dict[str, object]]:
    with closing(connect_ui_state(out)) as conn:
        rows = conn.execute(
            """
            SELECT id, file_key, para, mark_type, note, created_at
            FROM user_marks
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_mark(out: Path, mark_id: int) -> bool:
    with closing(connect_ui_state(out)) as conn:
        cur = conn.execute("DELETE FROM user_marks WHERE id = ?", (mark_id,))
        conn.commit()
        return cur.rowcount > 0


def ensure_default_compare_list(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT id FROM compare_lists WHERE name = ? ORDER BY id LIMIT 1",
        ("Default",),
    ).fetchone()
    if row:
        return int(row["id"])
    now = _utc_now()
    cur = conn.execute(
        "INSERT INTO compare_lists (name, created_at, updated_at) VALUES (?, ?, ?)",
        ("Default", now, now),
    )
    return int(cur.lastrowid)


def compare_items(out: Path) -> List[Dict[str, object]]:
    with closing(connect_ui_state(out)) as conn:
        list_id = ensure_default_compare_list(conn)
        conn.commit()
        rows = conn.execute(
            """
            SELECT id, list_id, file_key, para, note, created_at
            FROM compare_items
            WHERE list_id = ?
            ORDER BY id DESC
            """,
            (list_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def add_compare_item(
    out: Path,
    file_key: str,
    para: Optional[int],
    note: Optional[str],
) -> Dict[str, object]:
    now = _utc_now()
    with closing(connect_ui_state(out)) as conn:
        list_id = ensure_default_compare_list(conn)
        cur = conn.execute(
            """
            INSERT INTO compare_items (list_id, file_key, para, note, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (list_id, file_key, para, note, now),
        )
        conn.execute(
            "UPDATE compare_lists SET updated_at = ? WHERE id = ?",
            (now, list_id),
        )
        conn.commit()
        item_id = cur.lastrowid
    return {
        "id": item_id,
        "list_id": list_id,
        "file_key": file_key,
        "para": para,
        "note": note,
        "created_at": now,
    }


def delete_compare_item(out: Path, item_id: int) -> bool:
    with closing(connect_ui_state(out)) as conn:
        cur = conn.execute("DELETE FROM compare_items WHERE id = ?", (item_id,))
        conn.commit()
        return cur.rowcount > 0


def research_sessions(out: Path, limit: int = 50) -> List[Dict[str, object]]:
    with closing(connect_ui_state(out)) as conn:
        rows = conn.execute(
            """
            SELECT id, name, note, created_at, updated_at
            FROM research_sessions
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def create_research_session(out: Path, name: str, note: Optional[str]) -> Dict[str, object]:
    now = _utc_now()
    with closing(connect_ui_state(out)) as conn:
        cur = conn.execute(
            """
            INSERT INTO research_sessions (name, note, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (name, note, now, now),
        )
        conn.commit()
        session_id = cur.lastrowid
    return {"id": session_id, "name": name, "note": note, "created_at": now, "updated_at": now}


def add_session_item(
    out: Path,
    session_id: int,
    file_key: str,
    para: Optional[int],
    note: Optional[str],
) -> Dict[str, object]:
    now = _utc_now()
    with closing(connect_ui_state(out)) as conn:
        row = conn.execute(
            "SELECT id FROM research_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            raise KeyError("research session not found")
        cur = conn.execute(
            """
            INSERT INTO session_items (session_id, file_key, para, note, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, file_key, para, note, now),
        )
        conn.execute(
            "UPDATE research_sessions SET updated_at = ? WHERE id = ?",
            (now, session_id),
        )
        conn.commit()
        item_id = cur.lastrowid
    return {
        "id": item_id,
        "session_id": session_id,
        "file_key": file_key,
        "para": para,
        "note": note,
        "created_at": now,
    }
