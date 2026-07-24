import io
import json
import sqlite3
from contextlib import closing

from lib.catalog import initialize_catalog
from v4_schema import initialize_v4_schema
from webapp import App


def make_app(tmp_path):
    out = tmp_path / "cs_index"
    db_path = initialize_catalog(out / "catalog.sqlite")
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO files(
              file_key,path,folder,filename,ctype,lang,ext,size,mtime,txt_path,
              char_count,status,source_signals,batch_label,content_hash,
              dup_group,indexed_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "a" * 16,
                "sample.docx",
                "",
                "sample.docx",
                "SPA",
                "국문",
                ".docx",
                1,
                1,
                "txt/a.txt",
                10,
                "ok",
                "{}",
                "pilot",
                "a" * 16,
                "a" * 16,
                "2026-07-24T00:00:00+00:00",
            ),
        )
        initialize_v4_schema(conn)
        now = "2026-07-24T00:00:00+00:00"
        conn.execute(
            """
            INSERT INTO v4_taxonomy_candidate(
              proposed_ko,family,recommended_parent_id,distinction_reason,
              evidence_file_key,loc_start,loc_end,verbatim,nearest_taxonomy_id,
              created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "신규 후보",
                "RW",
                "RW.LABOR",
                "구별 필요",
                "a" * 16,
                1,
                1,
                "신규 후보 원문",
                "RW.LABOR.NO_VIOLATION",
                now,
                now,
            ),
        )
        conn.commit()
    return App(out)


def call(app, method, path, body=None, query=""):
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8") if body else b""
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(raw)),
        "wsgi.input": io.BytesIO(raw),
    }
    captured = {}

    def start_response(status, headers):
        captured["status"] = int(status.split()[0])
        captured["headers"] = dict(headers)

    payload = b"".join(app(environ, start_response))
    return captured["status"], captured["headers"], payload


def json_call(app, method, path, body=None, query=""):
    status, _, payload = call(app, method, path, body, query)
    return status, json.loads(payload.decode("utf-8"))


def test_taxonomy_page_and_read_apis(tmp_path):
    app = make_app(tmp_path)
    try:
        status, headers, payload = call(app, "GET", "/taxonomy")
        assert status == 200
        assert "text/html" in headers["Content-Type"]
        assert "원자 명제 후보 관리" in payload.decode("utf-8")

        status, summary = json_call(app, "GET", "/api/v4/taxonomy/summary")
        assert status == 200
        assert summary["candidate_status_counts"]["pending"] == 1

        status, candidates = json_call(
            app,
            "GET",
            "/api/v4/taxonomy/candidates",
            query="family=RW&status=pending",
        )
        assert status == 200
        assert candidates["total_clusters"] == 1
        assert candidates["clusters"][0]["candidate_ids"] == [1]

        status, nodes = json_call(
            app,
            "GET",
            "/api/v4/taxonomy/nodes",
            query="family=RW",
        )
        assert status == 200
        assert any(row["taxonomy_id"] == "RW.LABOR.NO_VIOLATION" for row in nodes["nodes"])
    finally:
        app.shutdown()


def test_taxonomy_resolution_api(tmp_path):
    app = make_app(tmp_path)
    try:
        status, result = json_call(
            app,
            "POST",
            "/api/v4/taxonomy/candidates/resolve",
            {
                "action": "merge",
                "candidate_ids": [1],
                "taxonomy_id": "RW.LABOR.NO_VIOLATION",
                "reason": "동일 명제",
            },
        )
        assert status == 200
        assert result["resolved_count"] == 1

        status, result = json_call(
            app,
            "POST",
            "/api/v4/taxonomy/candidates/resolve",
            {
                "action": "merge",
                "candidate_ids": [1],
                "taxonomy_id": "RW.LABOR.NO_VIOLATION",
            },
        )
        assert status == 409
        assert result["error"]["code"] == "CANDIDATE_ALREADY_RESOLVED"
    finally:
        app.shutdown()
