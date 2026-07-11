"""jobs.sqlite — 색인 등 장시간 write 작업을 위한 job 큐 (BACKEND_REVIEW_PC §2.3).

원칙:
- one writer: catalog.sqlite 쓰기는 단일 worker thread에서만 실행한다.
- 영속화: job 상태를 메모리 큐에만 두지 않고 SQLite `jobs` 테이블에 기록한다.
- 크래시 복구: 앱 시작 시 running/queued로 남은 job은 failed(error_code=interrupted)로 정리한다.
- 협조적 취소: worker는 파일 단위 체크포인트마다 취소 플래그를 확인하고, 이미 커밋된
  파일은 유지한다(부분 결과는 정상 증분으로 남는다).

경계:
- jobs는 사용자 상태(ui_state.sqlite)도, 재색인으로 재구축되는 색인 산출물(catalog.sqlite)도
  아니다. 별도 `jobs.sqlite`에 둔다.
- 검색 read 경로(webapp read-only)는 이 계층을 거치지 않는다.
"""

from __future__ import annotations

import json
import queue
import sqlite3
import threading
import time
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional


JOBS_DDL = """
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  status TEXT NOT NULL,
  params_json TEXT,
  progress_done INTEGER NOT NULL DEFAULT 0,
  progress_total INTEGER NOT NULL DEFAULT 0,
  current_item TEXT,
  error_code TEXT,
  message TEXT,
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT
);
CREATE TABLE IF NOT EXISTS job_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL,
  ts TEXT NOT NULL,
  line TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_job_logs_job ON job_logs(job_id, id);
"""

# 상태 전이: queued -> running -> completed | failed | cancelled
TERMINAL_STATES = {"completed", "failed", "cancelled"}
JOB_COLUMNS = [
    "id", "type", "status", "params_json", "progress_done", "progress_total",
    "current_item", "error_code", "message", "created_at", "started_at", "finished_at",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def jobs_path(out: Path) -> Path:
    return Path(out) / "jobs.sqlite"


def connect_jobs(out: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(jobs_path(out), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn


class JobCancelled(Exception):
    """worker handler가 협조적 취소를 감지했을 때 던진다."""


class JobError(Exception):
    """handler가 표준 error_code와 함께 실패를 알릴 때 던진다."""

    def __init__(self, error_code: str, message: str = ""):
        super().__init__(message or error_code)
        self.error_code = error_code
        self.message = message or error_code


# handler(queue, job_id, params, progress, cancel_check) -> Optional[dict]
#   progress(done, total, current_item): 진행률 갱신
#   cancel_check() -> bool: 취소 요청 여부
JobHandler = Callable[["JobQueue", str, Dict[str, object],
                       Callable[[int, int, str], None], Callable[[], bool]], Optional[dict]]


class JobQueue:
    """표준 라이브러리 queue.Queue + worker thread 1개. one-writer 보장."""

    def __init__(self, out: Path):
        self.out = Path(out)
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._handlers: Dict[str, JobHandler] = {}
        self._cancel_flags: Dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        self._worker: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._min_progress_interval = 0.3  # 초당 과도한 DB write 방지
        ensure_jobs(self.out)
        self.recover_interrupted()

    # ---------- 등록/기동 ----------

    def register(self, job_type: str, handler: JobHandler) -> None:
        self._handlers[job_type] = handler

    def start(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._stop.clear()
        self._worker = threading.Thread(target=self._run, name="job-worker", daemon=True)
        self._worker.start()

    def shutdown(self, wait: bool = True, timeout: float = 5.0) -> None:
        self._stop.set()
        self._queue.put("")  # worker 깨우기
        if wait and self._worker:
            self._worker.join(timeout=timeout)

    # ---------- 공개 API ----------

    def enqueue(self, job_type: str, params: Dict[str, object]) -> str:
        if job_type not in self._handlers:
            raise JobError("UNKNOWN_JOB_TYPE", f"Unknown job type: {job_type}")
        job_id = uuid.uuid4().hex
        with closing(connect_jobs(self.out)) as conn:
            conn.execute(
                "INSERT INTO jobs (id, type, status, params_json, created_at) "
                "VALUES (?, ?, 'queued', ?, ?)",
                (job_id, job_type, json.dumps(params, ensure_ascii=False), _now()),
            )
            conn.commit()
        self._cancel_flags[job_id] = threading.Event()
        self._queue.put(job_id)
        return job_id

    def get(self, job_id: str) -> Optional[Dict[str, object]]:
        with closing(connect_jobs(self.out)) as conn:
            row = conn.execute(
                f"SELECT {', '.join(JOB_COLUMNS)} FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
        return _row_to_dict(row) if row else None

    def append_log(self, job_id: str, line: str) -> None:
        with closing(connect_jobs(self.out)) as conn:
            conn.execute(
                "INSERT INTO job_logs (job_id, ts, line) VALUES (?, ?, ?)",
                (job_id, _now(), line),
            )
            conn.commit()

    def get_logs(self, job_id: str, limit: int = 500) -> List[Dict[str, object]]:
        with closing(connect_jobs(self.out)) as conn:
            rows = conn.execute(
                "SELECT ts, line FROM job_logs WHERE job_id = ? ORDER BY id LIMIT ?",
                (job_id, int(limit)),
            ).fetchall()
        return [{"ts": row["ts"], "line": row["line"]} for row in rows]

    def list_jobs(self, limit: int = 20) -> List[Dict[str, object]]:
        with closing(connect_jobs(self.out)) as conn:
            rows = conn.execute(
                f"SELECT {', '.join(JOB_COLUMNS)} FROM jobs "
                f"ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [_row_to_dict(row) for row in rows]

    def cancel(self, job_id: str) -> bool:
        """취소 요청. queued면 즉시 cancelled로, running이면 협조적 취소 플래그를 세운다."""
        with closing(connect_jobs(self.out)) as conn:
            row = conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if row is None:
                return False
            status = row["status"]
            if status in TERMINAL_STATES:
                return False
            flag = self._cancel_flags.setdefault(job_id, threading.Event())
            flag.set()
            if status == "queued":
                conn.execute(
                    "UPDATE jobs SET status='cancelled', finished_at=?, "
                    "error_code='cancelled' WHERE id=? AND status='queued'",
                    (_now(), job_id),
                )
                conn.commit()
        return True

    # ---------- worker ----------

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                job_id = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if not job_id or self._stop.is_set():
                continue
            self._process(job_id)

    def _process(self, job_id: str) -> None:
        job = self.get(job_id)
        if job is None:
            return
        if job["status"] != "queued":
            return  # 이미 취소/처리됨
        flag = self._cancel_flags.setdefault(job_id, threading.Event())
        if flag.is_set():
            self._set_terminal(job_id, "cancelled", error_code="cancelled")
            return
        handler = self._handlers.get(job["type"])
        if handler is None:
            self._set_terminal(job_id, "failed", error_code="UNKNOWN_JOB_TYPE")
            return

        self._mark_running(job_id)
        params = job["params"]
        last = [0.0]

        def progress(done: int, total: int, current_item: str) -> None:
            now = time.monotonic()
            # 완료(done==total)나 간격 경과 시에만 기록해 write 폭주를 막는다.
            if now - last[0] < self._min_progress_interval and not (total and done >= total):
                return
            last[0] = now
            self._update_progress(job_id, done, total, current_item)

        def cancel_check() -> bool:
            return flag.is_set()

        try:
            result = handler(self, job_id, params, progress, cancel_check)
            if flag.is_set():
                self._set_terminal(job_id, "cancelled", error_code="cancelled",
                                   message=_summ(result))
            else:
                self._set_terminal(job_id, "completed", message=_summ(result))
        except JobCancelled:
            self._set_terminal(job_id, "cancelled", error_code="cancelled")
        except JobError as exc:
            self._set_terminal(job_id, "failed", error_code=exc.error_code, message=exc.message)
        except Exception as exc:  # noqa: BLE001 — 표준 error_code로 봉인
            self._set_terminal(job_id, "failed", error_code="INTERNAL_ERROR", message=str(exc))

    # ---------- 상태 기록 ----------

    def _mark_running(self, job_id: str) -> None:
        with closing(connect_jobs(self.out)) as conn:
            conn.execute(
                "UPDATE jobs SET status='running', started_at=? WHERE id=?",
                (_now(), job_id),
            )
            conn.commit()
        self.append_log(job_id, "started")

    def _update_progress(self, job_id: str, done: int, total: int, current_item: str) -> None:
        with closing(connect_jobs(self.out)) as conn:
            conn.execute(
                "UPDATE jobs SET progress_done=?, progress_total=?, current_item=? "
                "WHERE id=? AND status='running'",
                (done, total, current_item, job_id),
            )
            conn.commit()

    def _set_terminal(self, job_id: str, status: str, error_code: Optional[str] = None,
                      message: Optional[str] = None) -> None:
        with closing(connect_jobs(self.out)) as conn:
            conn.execute(
                "UPDATE jobs SET status=?, error_code=?, message=?, finished_at=? WHERE id=?",
                (status, error_code, message, _now(), job_id),
            )
            conn.commit()
        summary = f"{status}"
        if error_code:
            summary += f": {error_code}"
        if message:
            summary += f": {message}"
        self.append_log(job_id, summary)
        self._cancel_flags.pop(job_id, None)

    def recover_interrupted(self) -> int:
        """앱 시작 시 running/queued로 남은 job을 failed(interrupted)로 정리한다."""
        with closing(connect_jobs(self.out)) as conn:
            cur = conn.execute(
                "UPDATE jobs SET status='failed', error_code='interrupted', finished_at=? "
                "WHERE status IN ('running', 'queued')",
                (_now(),),
            )
            conn.commit()
            return cur.rowcount


def ensure_jobs(out: Path) -> Path:
    path = jobs_path(out)
    with closing(connect_jobs(out)) as conn:
        conn.executescript(JOBS_DDL)
    return path


def _row_to_dict(row: sqlite3.Row) -> Dict[str, object]:
    data = {key: row[key] for key in JOB_COLUMNS}
    try:
        data["params"] = json.loads(data.pop("params_json") or "{}")
    except (json.JSONDecodeError, TypeError):
        data["params"] = {}
    return data


def _summ(result: Optional[dict]) -> Optional[str]:
    if not isinstance(result, dict):
        return None
    return json.dumps(result, ensure_ascii=False)[:1000]
