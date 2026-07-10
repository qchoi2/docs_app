"""Read-only web API for the contract search MVP (Web Backend Step 1).

Wraps the existing CLI search layer for a local web UI. Standard library
only (wsgiref) per the Phase 1 dependency whitelist; request validation is
manual. Not yet here (later steps): job queue, Runtime API Settings,
Agent Setup Wizard, AI answers.

Principles (IMPLEMENTATION_BRIEF §2.0, BACKEND_REVIEW_PC):
- default binding 127.0.0.1
- catalog.sqlite must live on a local cs_index (UNC paths rejected)
- searches use short-lived read-only connections
- file access is by file_key only (validated format, catalog lookup)
- raw exceptions are never sent to the client (standard error codes)
- CSV exports are utf-8-sig
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sqlite3
import sys
import traceback
from contextlib import closing
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

from lib.console import configure_utf8_stdio
from open_text import open_text
from search_contracts import connect_search_db, search_contracts


FILE_KEY_RE = re.compile(r"^[0-9a-f]{16}$")
EXPAND_MODES = {"strict", "normal", "broad"}
MAX_LIMIT = 100
MAX_KEYWORDS = 10


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def ensure_local_cs_index(out: Path) -> Path:
    raw = str(out)
    if raw.startswith("\\\\") or raw.startswith("//"):
        raise ApiError(400, "CONFIG_INDEX_PATH_NOT_LOCAL",
                       "cs_index must be on a local disk, not a network share.")
    out = Path(out)
    if not (out / "catalog.sqlite").exists():
        raise ApiError(500, "FILE_NOT_FOUND_IN_CATALOG",
                       "catalog.sqlite not found in the configured cs_index.")
    return out


def open_catalog_ro(out: Path) -> sqlite3.Connection:
    conn = connect_search_db(out / "catalog.sqlite", read_only=True)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- request parsing helpers ----------------

def parse_body(environ) -> Dict[str, object]:
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        length = 0
    raw = environ["wsgi.input"].read(length) if length else b""
    if not raw:
        return {}
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ApiError(400, "VALIDATION_ERROR", "Request body must be valid JSON.")
    if not isinstance(body, dict):
        raise ApiError(400, "VALIDATION_ERROR", "Request body must be a JSON object.")
    return body


def validated_search_params(body: Dict[str, object]) -> Dict[str, object]:
    keywords = body.get("kw") or []
    if not isinstance(keywords, list) or any(not isinstance(k, str) for k in keywords):
        raise ApiError(400, "VALIDATION_ERROR", "'kw' must be a list of strings.")
    keywords = [k.strip() for k in keywords if k.strip()]
    if len(keywords) > MAX_KEYWORDS:
        raise ApiError(400, "VALIDATION_ERROR", f"'kw' accepts at most {MAX_KEYWORDS} terms.")

    def opt_str(name):
        value = body.get(name)
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise ApiError(400, "VALIDATION_ERROR", f"'{name}' must be a string.")
        return value

    def opt_bool(name):
        value = body.get(name, False)
        if not isinstance(value, bool):
            raise ApiError(400, "VALIDATION_ERROR", f"'{name}' must be a boolean.")
        return value

    def opt_int(name, default, low, high):
        value = body.get(name, default)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ApiError(400, "VALIDATION_ERROR", f"'{name}' must be an integer.")
        if not (low <= value <= high):
            raise ApiError(400, "VALIDATION_ERROR", f"'{name}' must be between {low} and {high}.")
        return value

    expand = body.get("expand", "normal")
    if expand not in EXPAND_MODES:
        raise ApiError(400, "VALIDATION_ERROR", "'expand' must be strict|normal|broad.")

    return {
        "keywords": keywords,
        "ctype": opt_str("type"),
        "lang": opt_str("lang"),
        "expand": expand,
        "no_expand": opt_bool("no_expand"),
        "exclude_drafts": opt_bool("exclude_drafts"),
        "show_duplicates": opt_bool("show_duplicates"),
        "context": opt_int("context", 1, 0, 5),
        "limit": opt_int("limit", 20, 1, MAX_LIMIT),
        "offset": opt_int("offset", 0, 0, 10000),
    }


def run_search(out: Path, params: Dict[str, object]) -> Dict[str, object]:
    limit = params["limit"]
    offset = params["offset"]
    result, _count = search_contracts(
        out,
        ctype=params["ctype"],
        lang=params["lang"],
        keywords=params["keywords"],
        limit=offset + limit,
        context=params["context"],
        expand=params["expand"],
        no_expand=params["no_expand"],
        exclude_drafts=params["exclude_drafts"],
        show_duplicates=params["show_duplicates"],
        read_only=True,
    )
    result["results"] = result["results"][offset:offset + limit]
    result["limit"] = limit
    result["offset"] = offset
    return result


def require_file_key(raw: str) -> str:
    if not FILE_KEY_RE.match(raw or ""):
        raise ApiError(400, "VALIDATION_ERROR", "file_key must be 16 lowercase hex characters.")
    return raw


# ---------------- handlers ----------------

def handle_health(app, match, query, body):
    ok = (app.out / "catalog.sqlite").exists()
    return 200, {"status": "ok" if ok else "error", "sqlite_version": sqlite3.sqlite_version,
                 "catalog_found": ok}


def handle_corpus_status(app, match, query, body):
    with closing(open_catalog_ro(app.out)) as conn:
        statuses = dict(conn.execute(
            "SELECT status, COUNT(*) FROM files GROUP BY status").fetchall())
        batches = dict(conn.execute(
            "SELECT COALESCE(batch_label, ''), COUNT(*) FROM files WHERE status != 'missing' GROUP BY batch_label"
        ).fetchall())
        last_indexed = conn.execute("SELECT MAX(indexed_at) FROM files").fetchone()[0]
        unsearchable = conn.execute(
            "SELECT COUNT(*) FROM files WHERE status IN ('empty', 'error')").fetchone()[0]
    pilot_only = bool(batches) and all(label.startswith("pilot") for label in batches if label)
    return 200, {
        "statuses": statuses,
        "batch_labels": batches,
        "last_indexed_at": last_indexed,
        "unsearchable_docs": unsearchable,
        "pilot_corpus": pilot_only,
    }


def handle_search(app, match, query, body):
    params = validated_search_params(body)
    return 200, run_search(app.out, params)


def handle_context(app, match, query, body):
    file_key = require_file_key(match.group("file_key"))
    para = query.get("para")
    search = query.get("search")
    context = query.get("context", "3")
    try:
        para_value = int(para) if para is not None else None
        context_value = max(0, min(int(context), 10))
    except ValueError:
        raise ApiError(400, "VALIDATION_ERROR", "'para' and 'context' must be integers.")
    if (para_value is None) == (search is None):
        raise ApiError(400, "VALIDATION_ERROR", "Provide exactly one of 'para' or 'search'.")
    try:
        result = open_text(app.out, file_key, para_value, search, context_value)
    except KeyError:
        raise ApiError(404, "FILE_NOT_FOUND_IN_CATALOG", "Unknown file_key.")
    except FileNotFoundError:
        raise ApiError(404, "FILE_NOT_FOUND_IN_CATALOG", "Text cache not found for this file.")
    except ValueError as exc:
        raise ApiError(400, "VALIDATION_ERROR", str(exc))
    return 200, result


def handle_duplicates(app, match, query, body):
    file_key = require_file_key(match.group("file_key"))
    with closing(open_catalog_ro(app.out)) as conn:
        row = conn.execute(
            "SELECT file_key, dup_group FROM files WHERE file_key = ?", (file_key,)
        ).fetchone()
        if row is None:
            raise ApiError(404, "FILE_NOT_FOUND_IN_CATALOG", "Unknown file_key.")
        dup_group = row["dup_group"] or file_key
        members = conn.execute(
            """
            SELECT file_key, path, status, is_draft, version_hint
            FROM files WHERE dup_group = ? AND status != 'missing'
            ORDER BY path, file_key
            """,
            (dup_group,),
        ).fetchall()
    return 200, {
        "file_key": file_key,
        "dup_group": dup_group,
        "count": len(members),
        "members": [dict(member) for member in members],
    }


def handle_facets(app, match, query, body):
    with closing(open_catalog_ro(app.out)) as conn:
        def facet(column):
            rows = conn.execute(
                f"SELECT {column}, COUNT(*) FROM files WHERE status != 'missing' "
                f"GROUP BY {column} ORDER BY COUNT(*) DESC, {column}"
            ).fetchall()
            return [{"value": row[0], "count": row[1]} for row in rows if row[0]]
        return 200, {"ctype": facet("ctype"), "lang": facet("lang"),
                     "batch_label": facet("batch_label")}


def _export_rows(result: Dict[str, object]) -> List[Dict[str, object]]:
    rows = []
    for item in result["results"]:
        rows.append({
            "file_key": item["file_key"],
            "path": item["path"],
            "ctype": item["ctype"],
            "lang": item["lang"],
            "is_draft": item["is_draft"],
            "version_hint": item["version_hint"] or "",
            "dup_count": item["dup_count"],
            "snippet_paras": " ".join(str(p) for p in item["snippet_paras"]),
            "snippet": item["snippet"].replace("\n", " / "),
        })
    return rows


def handle_export_markdown(app, match, query, body):
    params = validated_search_params(body)
    result = run_search(app.out, params)
    lines = ["# 검색 결과 내보내기", ""]
    lines.append(f"- 키워드: {', '.join(params['keywords']) or '(없음)'}")
    lines.append(f"- 필터: type={params['ctype'] or '-'} lang={params['lang'] or '-'}")
    lines.append(f"- total: {result['total']} (files: {result['total_files']})")
    if result["warnings"]:
        lines.append(f"- warnings: {', '.join(result['warnings'])}")
    lines.append("")
    for item in result["results"]:
        paras = ",".join(str(p) for p in item["snippet_paras"])
        lines.append(f"## [{item['file_key']}] {item['path']}")
        lines.append(f"- ctype: {item['ctype']} / lang: {item['lang']} / draft: {item['is_draft']} / 중복 {item['dup_count']}건 / ¶{paras}")
        lines.append("")
        lines.append("```")
        lines.append(item["snippet"])
        lines.append("```")
        lines.append("")
    text = "\n".join(lines)
    return ("raw", 200, "text/markdown; charset=utf-8", text.encode("utf-8"),
            [("Content-Disposition", 'attachment; filename="search_export.md"')])


def handle_export_csv(app, match, query, body):
    params = validated_search_params(body)
    result = run_search(app.out, params)
    rows = _export_rows(result)
    buffer = io.StringIO()
    fieldnames = ["file_key", "path", "ctype", "lang", "is_draft", "version_hint",
                  "dup_count", "snippet_paras", "snippet"]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    payload = buffer.getvalue().encode("utf-8-sig")  # BOM for Korean Windows Excel
    return ("raw", 200, "text/csv; charset=utf-8", payload,
            [("Content-Disposition", 'attachment; filename="search_export.csv"')])


ROUTES = [
    ("GET", re.compile(r"^/api/health$"), handle_health),
    ("GET", re.compile(r"^/api/corpus/status$"), handle_corpus_status),
    ("POST", re.compile(r"^/api/search$"), handle_search),
    ("GET", re.compile(r"^/api/files/(?P<file_key>[^/]+)/context$"), handle_context),
    ("GET", re.compile(r"^/api/files/(?P<file_key>[^/]+)/duplicates$"), handle_duplicates),
    ("POST", re.compile(r"^/api/export/markdown$"), handle_export_markdown),
    ("POST", re.compile(r"^/api/export/csv$"), handle_export_csv),
    ("GET", re.compile(r"^/api/search/facets$"), handle_facets),
    ("GET", re.compile(r"^/api/catalog/facets$"), handle_facets),  # documented alias
]


class App:
    def __init__(self, out: Path):
        self.out = ensure_local_cs_index(Path(out))

    def __call__(self, environ, start_response):
        status, content_type, payload, extra = self.dispatch(environ)
        headers = [("Content-Type", content_type),
                   ("Content-Length", str(len(payload)))] + extra
        start_response(f"{status} {_reason(status)}", headers)
        return [payload]

    def dispatch(self, environ) -> Tuple[int, str, bytes, List[Tuple[str, str]]]:
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "/")
        query = {key: values[0] for key, values in
                 parse_qs(environ.get("QUERY_STRING", "")).items()}
        try:
            matched_path = False
            for route_method, pattern, handler in ROUTES:
                match = pattern.match(path)
                if not match:
                    continue
                matched_path = True
                if route_method != method:
                    continue
                body = parse_body(environ) if method == "POST" else {}
                outcome = handler(self, match, query, body)
                if isinstance(outcome, tuple) and outcome and outcome[0] == "raw":
                    _tag, status, content_type, payload, extra = outcome
                    return status, content_type, payload, extra
                status, data = outcome
                return status, "application/json; charset=utf-8", _json_bytes(data), []
            if matched_path:
                raise ApiError(405, "METHOD_NOT_ALLOWED", "Method not allowed for this path.")
            raise ApiError(404, "NOT_FOUND", "Unknown API path.")
        except ApiError as exc:
            return exc.status, "application/json; charset=utf-8", _json_bytes(
                {"error": {"code": exc.code, "message": exc.message}}), []
        except sqlite3.OperationalError as exc:
            code = "SQLITE_BUSY" if "lock" in str(exc).lower() or "busy" in str(exc).lower() else "INTERNAL_ERROR"
            print(f"[webapp] sqlite error: {exc}", file=sys.stderr)
            return 503, "application/json; charset=utf-8", _json_bytes(
                {"error": {"code": code, "message": "Database is temporarily unavailable."}}), []
        except Exception:
            # Raw exceptions must never reach the client (BACKEND_REVIEW_PC §2.9).
            traceback.print_exc(file=sys.stderr)
            return 500, "application/json; charset=utf-8", _json_bytes(
                {"error": {"code": "INTERNAL_ERROR",
                           "message": "Unexpected server error. See server log."}}), []


def _json_bytes(data) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def _reason(status: int) -> str:
    return {200: "OK", 400: "Bad Request", 404: "Not Found", 405: "Method Not Allowed",
            500: "Internal Server Error", 503: "Service Unavailable"}.get(status, "OK")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only web API for contract search.")
    parser.add_argument("--out", required=True, type=Path, help="local cs_index folder")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    if args.host != "127.0.0.1":
        print("WARNING: binding beyond 127.0.0.1 exposes the API to the network. "
              "This app has no authentication yet.", file=sys.stderr)
    try:
        app = App(args.out)
    except ApiError as exc:
        print(f"ERROR: {exc.code}: {exc.message}", file=sys.stderr)
        return 2
    with make_server(args.host, args.port, app) as server:
        print(f"contract-search API listening on http://{args.host}:{args.port} (out={args.out})")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("shutting down")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
