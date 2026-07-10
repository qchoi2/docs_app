import csv
import io
import json
import sqlite3
from contextlib import closing

from lib.catalog import initialize_catalog
from webapp import App


def insert_doc(conn, file_key, path, content, *, ctype="SPA", lang="국문",
               dup_group=None, is_draft=None, version_hint=None, status="ok"):
    dup_group = dup_group or file_key
    conn.execute(
        """
        INSERT INTO files (
          file_key, path, folder, filename, ctype, lang, ext, size, mtime,
          txt_path, char_count, status, error_reason, source_signals,
          batch_label, content_hash, dup_group, is_draft, version_hint, indexed_at
        )
        VALUES (?, ?, '', ?, ?, ?, '.docx', 1, 1, ?, ?, ?, NULL, '{}',
          'pilot_001', ?, ?, ?, ?, '2026-07-10T00:00:00+00:00')
        """,
        (file_key, path, path, ctype, lang, f"txt/{file_key}.txt", len(content),
         status, file_key, dup_group, is_draft, version_hint),
    )
    if status == "ok":
        for index, paragraph in enumerate(content.split("\n"), start=1):
            conn.execute(
                "INSERT INTO fts(content, file_key, para) VALUES (?, ?, ?)",
                (paragraph, file_key, index),
            )


def make_app(tmp_path):
    out = tmp_path / "cs_index"
    db_path = initialize_catalog(out / "catalog.sqlite")
    txt_dir = out / "txt"
    txt_dir.mkdir()
    with closing(sqlite3.connect(db_path)) as conn:
        insert_doc(conn, "a" * 16, "spa_one.docx", "제1조 목적\n손해배상 조항\n제3조 기타",
                   is_draft=0, version_hint="final", dup_group="dupg")
        insert_doc(conn, "b" * 16, "spa_two.docx", "손해배상 및 면책", is_draft=1, dup_group="dupg")
        insert_doc(conn, "c" * 16, "sha_one.docx", "주주간 계약", ctype="SHA", lang="영문")
        insert_doc(conn, "d" * 16, "scan.pdf", "", status="empty")
        conn.commit()
    (txt_dir / ("a" * 16 + ".txt")).write_text(
        "[¶1]\t제1조 목적\n[¶2]\t손해배상 조항\n[¶3]\t제3조 기타\n", encoding="utf-8")
    return App(out)


def call(app, method, path, body=None, query=""):
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else b""
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


def get_json(app, method, path, body=None, query=""):
    status, headers, payload = call(app, method, path, body, query)
    return status, json.loads(payload.decode("utf-8"))


def test_smoke_health_status_facets_and_errors(tmp_path):
    app = make_app(tmp_path)

    status, data = get_json(app, "GET", "/api/health")
    assert status == 200 and data["status"] == "ok" and data["catalog_found"] is True

    status, data = get_json(app, "GET", "/api/corpus/status")
    assert status == 200
    assert data["statuses"]["ok"] == 3 and data["statuses"]["empty"] == 1
    assert data["pilot_corpus"] is True
    assert data["unsearchable_docs"] == 1

    status, data = get_json(app, "GET", "/api/search/facets")
    assert status == 200
    assert {f["value"] for f in data["ctype"]} == {"SPA", "SHA"}
    assert {f["value"] for f in data["lang"]} == {"국문", "영문"}

    status, data = get_json(app, "GET", "/api/nope")
    assert status == 404 and data["error"]["code"] == "NOT_FOUND"

    status, data = get_json(app, "GET", "/api/search")  # wrong method
    assert status == 405 and data["error"]["code"] == "METHOD_NOT_ALLOWED"

    status, data = get_json(app, "GET", "/api/files/NOT-A-KEY/context", query="para=1")
    assert status == 400 and data["error"]["code"] == "VALIDATION_ERROR"


def test_search_json_schema_and_pagination(tmp_path):
    app = make_app(tmp_path)

    status, data = get_json(app, "POST", "/api/search",
                            body={"kw": ["손해배상"], "no_expand": True, "limit": 1, "offset": 0})
    assert status == 200
    assert {"query", "total", "total_files", "results", "warnings", "limit", "offset"} <= set(data)
    assert data["limit"] == 1 and data["offset"] == 0
    item = data["results"][0]
    assert {"file_key", "path", "ctype", "lang", "is_draft", "version_hint", "dup_group",
            "dup_count", "matched_terms", "score_breakdown", "why",
            "snippet", "snippet_paras"} <= set(item)

    status, page2 = get_json(app, "POST", "/api/search",
                             body={"kw": ["손해배상"], "no_expand": True,
                                   "show_duplicates": True, "limit": 1, "offset": 1})
    assert status == 200
    assert page2["results"][0]["file_key"] != item["file_key"]

    status, data = get_json(app, "POST", "/api/search", body={"kw": "문자열이면안됨"})
    assert status == 400 and data["error"]["code"] == "VALIDATION_ERROR"


def test_context_and_duplicates_by_file_key(tmp_path):
    app = make_app(tmp_path)

    status, data = get_json(app, "GET", f"/api/files/{'a'*16}/context", query="para=2&context=1")
    assert status == 200
    assert [p["para"] for p in data["paragraphs"]] == [1, 2, 3]

    status, data = get_json(app, "GET", f"/api/files/{'a'*16}/duplicates")
    assert status == 200
    assert data["count"] == 2
    assert {m["file_key"] for m in data["members"]} == {"a" * 16, "b" * 16}

    status, data = get_json(app, "GET", f"/api/files/{'f'*16}/duplicates")
    assert status == 404 and data["error"]["code"] == "FILE_NOT_FOUND_IN_CATALOG"


def test_csv_export_is_utf8_sig_and_parseable(tmp_path):
    app = make_app(tmp_path)

    status, headers, payload = call(app, "POST", "/api/export/csv",
                                    body={"kw": ["손해배상"], "no_expand": True})
    assert status == 200
    assert payload.startswith(b"\xef\xbb\xbf")  # utf-8-sig BOM
    assert "text/csv" in headers["Content-Type"]
    rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))
    assert rows and rows[0]["file_key"] and "손해배상" in rows[0]["snippet"]


def test_markdown_export_contains_citations(tmp_path):
    app = make_app(tmp_path)

    status, headers, payload = call(app, "POST", "/api/export/markdown",
                                    body={"kw": ["손해배상"], "no_expand": True})
    text = payload.decode("utf-8")
    assert status == 200
    assert "text/markdown" in headers["Content-Type"]
    assert f"[{'a'*16}]" in text or f"[{'b'*16}]" in text


def test_static_ui_is_served(tmp_path):
    app = make_app(tmp_path)

    status, headers, payload = call(app, "GET", "/")
    assert status == 200
    assert "text/html" in headers["Content-Type"]
    text = payload.decode("utf-8")
    assert 'id="search-input"' in text and 'aria-live' in text

    status, headers, payload = call(app, "GET", "/static/app.js")
    assert status == 200 and "javascript" in headers["Content-Type"]
    status, headers, payload = call(app, "GET", "/static/app.css")
    assert status == 200 and "text/css" in headers["Content-Type"]


def test_static_traversal_and_unknown_files_blocked(tmp_path):
    app = make_app(tmp_path)

    for path in ["/static/..", "/static/.%2e", "/static/webapp.py.bak",
                 "/static/no_such.js", "/static/..%2fwebapp.py"]:
        status, data = get_json(app, "GET", path)
        assert status == 404, path
        assert data["error"]["code"] == "NOT_FOUND"

    # 서버 소스 파일은 정적 경로로 노출되지 않아야 한다
    status, data = get_json(app, "GET", "/static/webapp.py")
    assert status == 404


def test_ui_uses_no_external_resources():
    from pathlib import Path
    static_dir = Path(__file__).resolve().parent.parent / "static"
    for name in ["index.html", "app.css", "app.js"]:
        text = (static_dir / name).read_text(encoding="utf-8")
        assert "http://" not in text and "https://" not in text, name  # 오프라인 원칙


def test_ui_does_not_hardcode_facet_options():
    from pathlib import Path
    static_dir = Path(__file__).resolve().parent.parent / "static"
    html = (static_dir / "index.html").read_text(encoding="utf-8")
    # 계약 유형/언어 옵션은 "전체"만 정적으로 두고 나머지는 facets에서 채운다
    for value in ["SPA", "SHA", "국문", "영문"]:
        assert f'<option value="{value}"' not in html, value


def test_search_history_persisted_in_ui_state(tmp_path):
    app = make_app(tmp_path)
    out = tmp_path / "cs_index"

    # ui_state.sqlite는 catalog와 분리 생성된다
    assert (out / "ui_state.sqlite").exists()

    status, _ = get_json(app, "POST", "/api/search",
                         body={"kw": ["손해배상"], "type": "SPA", "expand": "broad",
                               "exclude_drafts": True, "no_expand": True})
    assert status == 200

    with closing(sqlite3.connect(out / "ui_state.sqlite")) as conn:
        rows = conn.execute(
            "SELECT query, filters_json, expand_mode, result_count FROM search_history"
        ).fetchall()
    assert len(rows) == 1
    query, filters_json, expand_mode, result_count = rows[0]
    assert query == "손해배상"
    filters = json.loads(filters_json)
    assert filters["kw"] == ["손해배상"]
    assert filters["type"] == "SPA" and filters["exclude_drafts"] is True
    assert expand_mode == "broad"
    assert result_count >= 1

    # catalog.sqlite에는 사용자 상태 테이블이 없어야 한다 (경계 유지)
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "search_history" not in tables


def test_recent_searches_endpoint_dedupes_and_orders(tmp_path):
    app = make_app(tmp_path)

    for _ in range(2):  # 같은 검색 2번 → 1건으로 dedupe
        get_json(app, "POST", "/api/search", body={"kw": ["손해배상"], "no_expand": True})
    get_json(app, "POST", "/api/search", body={"kw": ["주주간"], "no_expand": True})
    get_json(app, "POST", "/api/search", body={})  # 빈 검색은 기록하지 않음

    status, data = get_json(app, "GET", "/api/history/recent")
    assert status == 200
    queries = [item["query"] for item in data["items"]]
    assert queries == ["주주간", "손해배상"]
    assert data["items"][0]["filters"]["kw"] == ["주주간"]


def test_export_does_not_add_history_rows(tmp_path):
    app = make_app(tmp_path)
    out = tmp_path / "cs_index"

    call(app, "POST", "/api/export/csv", body={"kw": ["손해배상"], "no_expand": True})

    with closing(sqlite3.connect(out / "ui_state.sqlite")) as conn:
        count = conn.execute("SELECT COUNT(*) FROM search_history").fetchone()[0]
    assert count == 0
