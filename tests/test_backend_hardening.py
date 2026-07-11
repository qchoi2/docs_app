import json
import sqlite3
import time
from contextlib import closing

from backup_index import run_backup
from tests.test_webapp import call, get_json, make_app


def test_index_job_rejected_while_one_is_active(tmp_path):
    app = make_app(tmp_path)
    # worker를 시작하지 않은 큐가 아니므로, 대기 상태를 만들기 위해 느린 핸들러로 교체
    app.jobs.shutdown()

    def slow_handler(queue, job_id, params, progress, cancel_check):
        time.sleep(0.2)
        return {}
    app.jobs.register("index", slow_handler)

    root = tmp_path / "root"
    root.mkdir()
    status, data = call_json(app, {"root": str(root)})
    assert status == 202

    status, data = call_json(app, {"root": str(root)})
    assert status == 409
    assert data["error"]["code"] == "INDEX_JOB_ALREADY_RUNNING"


def test_oversized_body_rejected(tmp_path):
    app = make_app(tmp_path)
    big = {"kw": ["x" * 2_000_000]}
    status, headers, payload = call(app, "POST", "/api/search", body=big)
    assert status == 413
    assert json.loads(payload.decode("utf-8"))["error"]["code"] == "VALIDATION_ERROR"


def test_backup_creates_wal_safe_snapshot(tmp_path):
    app = make_app(tmp_path)  # catalog/ui_state/jobs.sqlite 생성됨
    out = tmp_path / "cs_index"
    (out / "query_log.jsonl").write_text('{"q":1}\n', encoding="utf-8")

    dest = run_backup(out, tmp_path / "backup")
    assert (dest / "catalog.sqlite").exists()
    assert (dest / "ui_state.sqlite").exists()
    assert (dest / "jobs.sqlite").exists()
    assert (dest / "query_log.jsonl").exists()
    assert (dest / "txt").is_dir()
    # 백업된 catalog가 실제로 열리고 데이터가 보인다
    with closing(sqlite3.connect(dest / "catalog.sqlite")) as conn:
        count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    assert count >= 4


def call_json(app, body):
    status, headers, payload = call(app, "POST", "/api/jobs/index", body=body)
    return status, json.loads(payload.decode("utf-8"))
