import io
import json

from tests.test_taxonomy_web import make_app


def call(app, method, path, body=None):
    raw = json.dumps(body or {}).encode("utf-8")
    captured = {}
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": str(len(raw)),
        "wsgi.input": io.BytesIO(raw),
    }

    def start_response(status, headers):
        captured["status"] = int(status.split()[0])
        captured["headers"] = dict(headers)

    payload = b"".join(app(environ, start_response))
    return captured["status"], captured["headers"], payload


def test_v4_search_page(tmp_path):
    app = make_app(tmp_path)
    status, headers, payload = call(app, "GET", "/v4-search")
    assert status == 200
    assert "text/html" in headers["Content-Type"]
    assert "원자 명제 검색" in payload.decode("utf-8")


def test_v4_search_api_validation(tmp_path):
    app = make_app(tmp_path)
    status, _, payload = call(
        app,
        "POST",
        "/api/v4/items/search",
        {"taxonomy_id": "RW.NOT_A_NODE"},
    )
    assert status == 404
    data = json.loads(payload.decode("utf-8"))
    assert data["error"]["code"] == "TAXONOMY_NOT_FOUND"
