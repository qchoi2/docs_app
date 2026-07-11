import threading
import time
from pathlib import Path

import pytest

from lib.jobs import JobError, JobQueue, connect_jobs, ensure_jobs


def _wait(queue: JobQueue, job_id: str, statuses, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = queue.get(job_id)
        if job and job["status"] in statuses:
            return job
        time.sleep(0.02)
    return queue.get(job_id)


def test_success_job_records_terminal_state(tmp_path):
    q = JobQueue(tmp_path)
    q.register("noop", lambda queue, jid, params, progress, cancel: {"ok": params["n"]})
    q.start()
    try:
        job_id = q.enqueue("noop", {"n": 3})
        job = _wait(q, job_id, {"completed", "failed"})
        assert job["status"] == "completed"
        assert job["started_at"] and job["finished_at"]
        assert '"ok": 3' in (job["message"] or "")
    finally:
        q.shutdown()


def test_progress_updates_are_persisted(tmp_path):
    q = JobQueue(tmp_path)
    q._min_progress_interval = 0.0  # 테스트에서는 throttle 해제

    def handler(queue, jid, params, progress, cancel):
        for i in range(5):
            progress(i, 5, f"file-{i}")
            time.sleep(0.01)
        progress(5, 5, "")
        return None

    q.register("prog", handler)
    q.start()
    try:
        job_id = q.enqueue("prog", {})
        job = _wait(q, job_id, {"completed"})
        assert job["status"] == "completed"
        assert job["progress_total"] == 5
        assert job["progress_done"] == 5
    finally:
        q.shutdown()


def test_cooperative_cancel_of_running_job(tmp_path):
    q = JobQueue(tmp_path)
    q._min_progress_interval = 0.0
    started = threading.Event()

    def handler(queue, jid, params, progress, cancel):
        started.set()
        for i in range(1000):
            if cancel():
                return {"stopped_at": i}
            progress(i, 1000, f"f-{i}")
            time.sleep(0.01)
        return {"stopped_at": 1000}

    q.register("slow", handler)
    q.start()
    try:
        job_id = q.enqueue("slow", {})
        assert started.wait(2.0)
        assert q.cancel(job_id) is True
        job = _wait(q, job_id, {"cancelled", "completed"})
        assert job["status"] == "cancelled"
        assert job["progress_done"] < 1000  # 도중에 멈췄다
    finally:
        q.shutdown()


def test_failed_job_uses_standard_error_code(tmp_path):
    q = JobQueue(tmp_path)

    def boom(queue, jid, params, progress, cancel):
        raise JobError("ROOT_NOT_FOUND", "no such dir")

    def crash(queue, jid, params, progress, cancel):
        raise RuntimeError("unexpected")

    q.register("boom", boom)
    q.register("crash", crash)
    q.start()
    try:
        j1 = _wait(q, q.enqueue("boom", {}), {"failed"})
        assert j1["status"] == "failed" and j1["error_code"] == "ROOT_NOT_FOUND"
        j2 = _wait(q, q.enqueue("crash", {}), {"failed"})
        assert j2["status"] == "failed" and j2["error_code"] == "INTERNAL_ERROR"
    finally:
        q.shutdown()


def test_unknown_job_type_rejected_at_enqueue(tmp_path):
    q = JobQueue(tmp_path)
    with pytest.raises(JobError):
        q.enqueue("does-not-exist", {})


def test_recovery_marks_interrupted_jobs_failed(tmp_path):
    # running/queued로 남은 레코드를 직접 심고 새 큐가 정리하는지 확인.
    ensure_jobs(tmp_path)
    with connect_jobs(tmp_path) as conn:
        conn.execute("INSERT INTO jobs (id, type, status, created_at) VALUES "
                     "('r1','index','running','2026-07-11T00:00:00+00:00')")
        conn.execute("INSERT INTO jobs (id, type, status, created_at) VALUES "
                     "('q1','index','queued','2026-07-11T00:00:00+00:00')")
        conn.commit()
    q = JobQueue(tmp_path)  # __init__에서 recover_interrupted 실행
    try:
        for jid in ("r1", "q1"):
            job = q.get(jid)
            assert job["status"] == "failed"
            assert job["error_code"] == "interrupted"
            assert job["finished_at"]
    finally:
        q.shutdown()
