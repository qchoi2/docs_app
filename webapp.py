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
import os
import re
import sqlite3
import sys
import time
import traceback
from contextlib import closing
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

from index_contracts import IndexOptions, index_contracts
from lib.console import configure_utf8_stdio
from lib.jobs import JobError, JobQueue
from lib.settings_store import (ai_status, api_key_status, delete_api_key,
                                save_api_key, save_budget)
from lib.ui_state import (add_compare_item, add_mark, add_session_item,
                          compare_items, create_research_session,
                          create_saved_search, delete_compare_item,
                          delete_mark, delete_saved_search, ensure_ui_state,
                          feedback_summary, list_marks, recent_searches,
                          record_feedback, record_search, research_sessions,
                          saved_searches)
from open_text import open_text
from search_contracts import connect_search_db, search_contracts


FILE_KEY_RE = re.compile(r"^[0-9a-f]{16}$")
JOB_ID_RE = re.compile(r"^[0-9a-f]{32}$")
ROOT_SCAN_CAP = 20000  # root-path 검증 시 스캔 상한(대형 코퍼스에서 폭주 방지)
SUPPORTED_INDEX_EXTS = {".docx", ".pdf"}
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9]+$")
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}
EXPAND_MODES = {"strict", "normal", "broad"}
MAX_LIMIT = 100
MAX_KEYWORDS = 10
MAX_NOTE_CHARS = 2000
FEEDBACK_VALUES = {"useful", "wrong", "missing", "unclear"}
MAX_BODY_BYTES = 1_000_000  # 로컬 앱 기준 요청 본문 상한 (실수/폭주 방지)


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
    if length > MAX_BODY_BYTES:
        raise ApiError(413, "VALIDATION_ERROR", "Request body too large.")
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


def require_positive_int(value, name: str) -> int:
    if isinstance(value, bool):
        raise ApiError(400, "VALIDATION_ERROR", f"'{name}' must be a positive integer.")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ApiError(400, "VALIDATION_ERROR", f"'{name}' must be a positive integer.")
    if number < 1:
        raise ApiError(400, "VALIDATION_ERROR", f"'{name}' must be a positive integer.")
    return number


def optional_para(body: Dict[str, object]) -> Optional[int]:
    value = body.get("para")
    if value is None or value == "":
        return None
    return require_positive_int(value, "para")


def optional_note(body: Dict[str, object]) -> Optional[str]:
    value = body.get("note")
    if value is None:
        return None
    if not isinstance(value, str):
        raise ApiError(400, "VALIDATION_ERROR", "'note' must be a string.")
    value = value.strip()
    if len(value) > MAX_NOTE_CHARS:
        raise ApiError(400, "VALIDATION_ERROR", "'note' is too long.")
    return value


def require_short_text(body: Dict[str, object], name: str, max_len: int = 120) -> str:
    value = body.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(400, "VALIDATION_ERROR", f"'{name}' is required.")
    value = value.strip()
    if len(value) > max_len:
        raise ApiError(400, "VALIDATION_ERROR", f"'{name}' is too long.")
    return value


def file_exists(out: Path, file_key: str) -> bool:
    with closing(open_catalog_ro(out)) as conn:
        row = conn.execute(
            "SELECT 1 FROM files WHERE file_key = ? AND status != 'missing'",
            (file_key,),
        ).fetchone()
    return row is not None


def require_existing_file_key(out: Path, raw: str) -> str:
    file_key = require_file_key(raw)
    if not file_exists(out, file_key):
        raise ApiError(404, "FILE_NOT_FOUND_IN_CATALOG", "Unknown file_key.")
    return file_key


# ---------------- job / indexing write layer ----------------

def index_job_handler(queue, job_id, params, progress, cancel_check):
    """색인 job worker. one-writer 원칙에 따라 이 경로에서만 catalog를 쓴다."""
    root = params.get("root")
    if not isinstance(root, str) or not root.strip():
        raise JobError("VALIDATION_ERROR", "index job requires a 'root' path.")
    options = IndexOptions(
        full=bool(params.get("full", False)),
        include_misc=bool(params.get("include_misc", False)),
        batch_label=params.get("batch_label") or None,
        sample=params.get("sample"),
        sample_seed=int(params.get("sample_seed", 0) or 0),
        progress_callback=progress,
        cancel_check=cancel_check,
    )
    try:
        result = index_contracts(root, queue.out, options)
    except ValueError as exc:
        raise JobError("ROOT_NOT_FOUND", str(exc))
    return {
        "indexed": result["indexed"],
        "skipped": result["skipped"],
        "statuses": result["statuses"],
        "cancelled": result["cancelled"],
        "report": result.get("report"),
    }


def _scan_root(path: Path) -> Dict[str, object]:
    """root 폴더를 상한까지 훑어 대략적 파일 수/지원 확장자 수를 센다."""
    total = 0
    supported = 0
    truncated = False
    try:
        for entry in path.rglob("*"):
            if not entry.is_file():
                continue
            total += 1
            if entry.suffix.lower() in SUPPORTED_INDEX_EXTS:
                supported += 1
            if total >= ROOT_SCAN_CAP:
                truncated = True
                break
    except OSError:
        pass
    return {"file_count": total, "supported_file_count": supported, "scan_truncated": truncated}


def handle_root_path_validate(app, match, query, body):
    raw = body.get("path")
    if not isinstance(raw, str) or not raw.strip():
        raise ApiError(400, "VALIDATION_ERROR", "'path' is required.")
    raw = raw.strip()
    network_drive = raw.startswith("\\\\") or raw.startswith("//")
    path = Path(raw)
    exists = path.exists()
    is_dir = path.is_dir()
    readable = bool(is_dir and os.access(path, os.R_OK))
    info: Dict[str, object] = {
        "path": raw,
        "exists": exists,
        "is_dir": is_dir,
        "readable": readable,
        "network_drive": network_drive,
        "index_dir": str(app.out),
        "read_only_notice": "원본 폴더는 읽기 전용으로만 접근합니다.",
        "file_count": 0,
        "supported_file_count": 0,
        "scan_truncated": False,
    }
    if readable:
        info.update(_scan_root(path))
    if not exists:
        info["message"] = "경로가 존재하지 않습니다."
    elif not is_dir:
        info["message"] = "폴더가 아닙니다."
    elif not readable:
        info["message"] = "읽기 권한이 없습니다."
    elif network_drive:
        info["message"] = "네트워크 드라이브로 보입니다. 로컬 디스크를 권장합니다."
    else:
        info["message"] = "사용 가능한 경로입니다."
    return 200, info


def _job_int(body, name, low, high):
    value = body.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ApiError(400, "VALIDATION_ERROR", f"'{name}' must be an integer.")
    if not (low <= value <= high):
        raise ApiError(400, "VALIDATION_ERROR", f"'{name}' must be between {low} and {high}.")
    return value


def handle_jobs_index(app, match, query, body):
    root = body.get("root")
    if not isinstance(root, str) or not root.strip():
        raise ApiError(400, "VALIDATION_ERROR", "'root' is required.")
    for flag in ("full", "include_misc"):
        if flag in body and not isinstance(body[flag], bool):
            raise ApiError(400, "VALIDATION_ERROR", f"'{flag}' must be a boolean.")
    batch_label = body.get("batch_label")
    if batch_label is not None and not isinstance(batch_label, str):
        raise ApiError(400, "VALIDATION_ERROR", "'batch_label' must be a string.")
    params = {
        "root": root.strip(),
        "full": bool(body.get("full", False)),
        "include_misc": bool(body.get("include_misc", False)),
        "batch_label": batch_label,
        "sample": _job_int(body, "sample", 1, 1000000),
        "sample_seed": _job_int(body, "sample_seed", 0, 2**31) or 0,
    }
    # one-writer 원칙 + 사용자 혼란 방지: 색인 job은 동시에 하나만 허용한다.
    if app.jobs.has_active("index"):
        raise ApiError(409, "INDEX_JOB_ALREADY_RUNNING",
                       "이미 대기/실행 중인 색인 작업이 있습니다. 완료나 취소 후 다시 시도하세요.")
    job_id = app.jobs.enqueue("index", params)
    return 202, {"job_id": job_id, "status": "queued"}


def handle_jobs_list(app, match, query, body):
    try:
        limit = max(1, min(int(query.get("limit", "20")), 100))
    except ValueError:
        raise ApiError(400, "VALIDATION_ERROR", "'limit' must be an integer.")
    return 200, {"jobs": app.jobs.list_jobs(limit)}


def handle_job_get(app, match, query, body):
    job_id = match.group("job_id")
    if not JOB_ID_RE.match(job_id):
        raise ApiError(400, "VALIDATION_ERROR", "job_id must be 32 lowercase hex characters.")
    job = app.jobs.get(job_id)
    if job is None:
        raise ApiError(404, "JOB_NOT_FOUND", "Unknown job_id.")
    return 200, job


def handle_job_cancel(app, match, query, body):
    job_id = match.group("job_id")
    if not JOB_ID_RE.match(job_id):
        raise ApiError(400, "VALIDATION_ERROR", "job_id must be 32 lowercase hex characters.")
    ok = app.jobs.cancel(job_id)
    if not ok and app.jobs.get(job_id) is None:
        raise ApiError(404, "JOB_NOT_FOUND", "Unknown job_id.")
    return 200, {"job_id": job_id, "cancel_requested": ok}


def handle_job_log(app, match, query, body):
    job_id = match.group("job_id")
    if not JOB_ID_RE.match(job_id):
        raise ApiError(400, "VALIDATION_ERROR", "job_id must be 32 lowercase hex characters.")
    if app.jobs.get(job_id) is None:
        raise ApiError(404, "JOB_NOT_FOUND", "Unknown job_id.")
    return 200, {"job_id": job_id, "entries": app.jobs.get_logs(job_id)}


# ---------------- Runtime API Settings (UI_PRODUCT_SPEC §15.1) ----------------
# 원칙: 키 전문은 응답·로그에 싣지 않는다. 마지막 4자리만 표시한다.
# Codex용 OpenAI API key 입력은 만들지 않는다.

API_KEY_RE = re.compile(r"^sk-ant-[A-Za-z0-9_\-]{10,250}$")


def handle_runtime_api_settings(app, match, query, body):
    status = api_key_status()
    ai = ai_status()
    return 200, {
        "anthropic": {"api_key_set": status["api_key_set"],
                      "api_key_last4": status["api_key_last4"],
                      "storage": status["storage"]},
        "budget": ai["budget"],
        "ai": {"enabled": ai["enabled"], "disabled_reason": ai["disabled_reason"]},
    }


def handle_anthropic_key_save(app, match, query, body):
    api_key = body.get("api_key")
    if not isinstance(api_key, str) or not api_key.strip():
        raise ApiError(400, "VALIDATION_ERROR", "'api_key' is required.")
    api_key = api_key.strip()
    if not API_KEY_RE.match(api_key):
        raise ApiError(400, "VALIDATION_ERROR",
                       "API key must look like sk-ant-... (format check only).")
    saved = save_api_key(api_key)
    ai = ai_status()
    return 200, {"api_key_set": True, "api_key_last4": saved["api_key_last4"],
                 "storage": saved["storage"],
                 "ai": {"enabled": ai["enabled"], "disabled_reason": ai["disabled_reason"]}}


def handle_anthropic_key_delete(app, match, query, body):
    removed = delete_api_key()
    ai = ai_status()
    return 200, {"api_key_set": False, "removed": removed,
                 "ai": {"enabled": ai["enabled"], "disabled_reason": ai["disabled_reason"]}}


def handle_anthropic_key_test(app, match, query, body):
    # 실제 Anthropic API는 호출하지 않는다 (대량 호출 금지 단계).
    # 저장된 키의 존재·형식만 확인하는 mock 연결 테스트다.
    status = api_key_status()
    if not status["api_key_set"]:
        return 200, {"tested": False, "mode": "format_only",
                     "message": "저장된 API key가 없습니다."}
    return 200, {"tested": True, "mode": "format_only",
                 "message": "키 형식 확인 완료. 실제 호출 테스트는 AI 기능 단계에서 제공됩니다."}


def _budget_value(body, name):
    value = body.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ApiError(400, "VALIDATION_ERROR", f"'{name}' must be a number or null.")
    if not (0 < float(value) <= 1000):
        raise ApiError(400, "VALIDATION_ERROR", f"'{name}' must be between 0 and 1000 USD.")
    return float(value)


def handle_budget_save(app, match, query, body):
    per_call = _budget_value(body, "per_call_limit_usd")
    per_run = _budget_value(body, "per_run_limit_usd")
    budget = save_budget(per_call, per_run)
    ai = ai_status()
    return 200, {"budget": budget,
                 "ai": {"enabled": ai["enabled"], "disabled_reason": ai["disabled_reason"]}}


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
    started = time.perf_counter()
    result = run_search(app.out, params)
    # 최근 검색은 ui_state.sqlite(사용자 UI 상태)에 기록한다.
    # query_log.jsonl은 search_contracts가 남기는 운영 로그로, 여기서 겸용하지 않는다.
    if params["keywords"] or params["ctype"] or params["lang"]:
        try:
            record_search(
                app.out,
                query=", ".join(params["keywords"]),
                filters={
                    "kw": params["keywords"],
                    "type": params["ctype"],
                    "lang": params["lang"],
                    "exclude_drafts": params["exclude_drafts"],
                    "show_duplicates": params["show_duplicates"],
                },
                expand_mode=params["expand"],
                result_count=result["total"],
                top_file_keys=[row["file_key"] for row in result["results"][:5]],
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
        except Exception as exc:  # 기록 실패가 검색을 막으면 안 된다
            print(f"[webapp] search_history write failed: {exc}", file=sys.stderr)
    return 200, result


def handle_recent_searches(app, match, query, body):
    try:
        limit = max(1, min(int(query.get("limit", "10")), 30))
    except ValueError:
        raise ApiError(400, "VALIDATION_ERROR", "'limit' must be an integer.")
    return 200, {"items": recent_searches(app.out, limit)}


def handle_ops_dashboard(app, match, query, body):
    with closing(open_catalog_ro(app.out)) as conn:
        statuses = dict(conn.execute(
            "SELECT status, COUNT(*) FROM files GROUP BY status"
        ).fetchall())
        batches = [
            {"batch_label": row[0] or "(none)", "count": row[1]}
            for row in conn.execute(
                """
                SELECT COALESCE(batch_label, ''), COUNT(*)
                FROM files
                WHERE status != 'missing'
                GROUP BY COALESCE(batch_label, '')
                ORDER BY COUNT(*) DESC, 1
                """
            ).fetchall()
        ]
        failures = [
            dict(row)
            for row in conn.execute(
                """
                SELECT file_key, path, status, error_reason, ctype, lang
                FROM files
                WHERE status IN ('empty', 'error', 'unsupported')
                ORDER BY status, path, file_key
                LIMIT 50
                """
            ).fetchall()
        ]
        unclassified = [
            {"folder": row[0] or ".", "count": row[1]}
            for row in conn.execute(
                """
                SELECT COALESCE(NULLIF(folder, ''), '.'), COUNT(*)
                FROM files
                WHERE ctype = ? AND status != 'missing'
                GROUP BY COALESCE(NULLIF(folder, ''), '.')
                ORDER BY COUNT(*) DESC, 1
                LIMIT 30
                """,
                ("미분류",),
            ).fetchall()
        ]
        last_indexed = conn.execute("SELECT MAX(indexed_at) FROM files").fetchone()[0]
    return 200, {
        "statuses": statuses,
        "batch_labels": batches,
        "failures": failures,
        "unclassified_folders": unclassified,
        "last_indexed_at": last_indexed,
        "jobs": app.jobs.list_jobs(10),
        "saved_search_count": len(saved_searches(app.out, 200)),
        "feedback": feedback_summary(app.out),
    }


def handle_ops_failures(app, match, query, body):
    try:
        limit = max(1, min(int(query.get("limit", "100")), 500))
    except ValueError:
        raise ApiError(400, "VALIDATION_ERROR", "'limit' must be an integer.")
    with closing(open_catalog_ro(app.out)) as conn:
        rows = conn.execute(
            """
            SELECT file_key, path, status, error_reason, ctype, lang, batch_label
            FROM files
            WHERE status IN ('empty', 'error', 'unsupported')
            ORDER BY status, path, file_key
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return 200, {"items": [dict(row) for row in rows]}


def handle_manual_overrides_export(app, match, query, body):
    with closing(open_catalog_ro(app.out)) as conn:
        rows = conn.execute(
            """
            SELECT path, ctype, lang, is_draft, version_hint, status, error_reason
            FROM files
            WHERE ctype = ? OR lang = ? OR status IN ('error', 'unsupported')
            ORDER BY path
            LIMIT 200
            """,
            ("미분류", "미상"),
        ).fetchall()
    lines = [
        "# manual_overrides candidates",
        "# Review these suggestions before copying them into data/manual_overrides.yaml.",
        "paths:",
    ]
    if not rows:
        lines.append("  {}")
    for row in rows:
        path = str(row["path"]).replace("\\", "/").replace('"', '\\"')
        lines.append(f'  "{path}":')
        lines.append(f"    # current: ctype={row['ctype']} lang={row['lang']} status={row['status']} reason={row['error_reason'] or ''}")
        lines.append("    # ctype: SPA")
        lines.append("    # lang: 국문")
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    return ("raw", 200, "text/yaml; charset=utf-8", payload,
            [("Content-Disposition", 'attachment; filename="manual_overrides_candidates.yaml"')])


def handle_saved_searches(app, match, query, body):
    return 200, {"items": saved_searches(app.out, 100)}


def handle_saved_search_create(app, match, query, body):
    name = require_short_text(body, "name")
    query_text = body.get("query") or ""
    if not isinstance(query_text, str):
        raise ApiError(400, "VALIDATION_ERROR", "'query' must be a string.")
    filters = body.get("filters") or {}
    if not isinstance(filters, dict):
        raise ApiError(400, "VALIDATION_ERROR", "'filters' must be an object.")
    expand_mode = body.get("expand_mode") or "normal"
    if expand_mode not in EXPAND_MODES:
        raise ApiError(400, "VALIDATION_ERROR", "'expand_mode' must be strict|normal|broad.")
    item = create_saved_search(app.out, name, query_text.strip(), filters, expand_mode)
    return 201, item


def handle_saved_search_delete(app, match, query, body):
    search_id = require_positive_int(match.group("id"), "id")
    if not delete_saved_search(app.out, search_id):
        raise ApiError(404, "NOT_FOUND", "Saved search not found.")
    return 200, {"deleted": True, "id": search_id}


def handle_feedback_create(app, match, query, body):
    feedback = require_short_text(body, "feedback", 40)
    if feedback not in FEEDBACK_VALUES:
        raise ApiError(400, "VALIDATION_ERROR", "'feedback' is not supported.")
    file_key = body.get("file_key")
    if file_key is not None:
        file_key = require_existing_file_key(app.out, str(file_key))
    para = optional_para(body)
    search_history_id = body.get("search_history_id")
    if search_history_id is not None:
        search_history_id = require_positive_int(search_history_id, "search_history_id")
    item = record_feedback(
        app.out,
        feedback,
        search_history_id=search_history_id,
        file_key=file_key,
        para=para,
        note=optional_note(body),
    )
    return 201, item


def handle_marks(app, match, query, body):
    try:
        limit = max(1, min(int(query.get("limit", "100")), 500))
    except ValueError:
        raise ApiError(400, "VALIDATION_ERROR", "'limit' must be an integer.")
    return 200, {"items": list_marks(app.out, limit)}


def handle_mark_create(app, match, query, body):
    file_key = require_existing_file_key(app.out, str(body.get("file_key") or ""))
    mark_type = body.get("mark_type") or "bookmark"
    if mark_type not in {"bookmark", "note"}:
        raise ApiError(400, "VALIDATION_ERROR", "'mark_type' must be bookmark|note.")
    item = add_mark(app.out, file_key, optional_para(body), mark_type, optional_note(body))
    return 201, item


def handle_mark_delete(app, match, query, body):
    mark_id = require_positive_int(match.group("id"), "id")
    if not delete_mark(app.out, mark_id):
        raise ApiError(404, "NOT_FOUND", "Mark not found.")
    return 200, {"deleted": True, "id": mark_id}


def handle_compare_default(app, match, query, body):
    return 200, {"items": enrich_file_refs(app.out, compare_items(app.out))}


def handle_compare_item_create(app, match, query, body):
    file_key = require_existing_file_key(app.out, str(body.get("file_key") or ""))
    item = add_compare_item(app.out, file_key, optional_para(body), optional_note(body))
    return 201, item


def handle_compare_item_delete(app, match, query, body):
    item_id = require_positive_int(match.group("id"), "id")
    if not delete_compare_item(app.out, item_id):
        raise ApiError(404, "NOT_FOUND", "Compare item not found.")
    return 200, {"deleted": True, "id": item_id}


def handle_research_sessions(app, match, query, body):
    return 200, {"items": research_sessions(app.out, 100)}


def handle_research_session_create(app, match, query, body):
    item = create_research_session(app.out, require_short_text(body, "name"), optional_note(body))
    return 201, item


def handle_research_session_item_create(app, match, query, body):
    session_id = require_positive_int(match.group("id"), "id")
    file_key = require_existing_file_key(app.out, str(body.get("file_key") or ""))
    try:
        item = add_session_item(app.out, session_id, file_key, optional_para(body), optional_note(body))
    except KeyError:
        raise ApiError(404, "NOT_FOUND", "Research session not found.")
    return 201, item


def enrich_file_refs(out: Path, items: List[Dict[str, object]]) -> List[Dict[str, object]]:
    if not items:
        return []
    keys = sorted({str(item["file_key"]) for item in items})
    placeholders = ",".join("?" for _ in keys)
    with closing(open_catalog_ro(out)) as conn:
        rows = conn.execute(
            f"SELECT file_key, path, ctype, lang, status FROM files WHERE file_key IN ({placeholders})",
            keys,
        ).fetchall()
    by_key = {row["file_key"]: dict(row) for row in rows}
    enriched = []
    for item in items:
        merged = dict(item)
        merged["file"] = by_key.get(str(item["file_key"]))
        enriched.append(merged)
    return enriched


def selected_paragraph_lines(out: Path, items: List[Dict[str, object]], context: int = 0) -> List[str]:
    lines: List[str] = []
    for item in items:
        file_key = require_existing_file_key(out, str(item.get("file_key") or ""))
        para = item.get("para")
        note = item.get("note")
        with closing(open_catalog_ro(out)) as conn:
            row = conn.execute(
                "SELECT path, ctype, lang FROM files WHERE file_key = ?",
                (file_key,),
            ).fetchone()
        title = row["path"] if row else file_key
        lines.append(f"## [{file_key}] {title}")
        if note:
            lines.append(f"- note: {note}")
        if para is None or para == "":
            lines.append("")
            continue
        para_value = require_positive_int(para, "para")
        try:
            data = open_text(out, file_key, para_value, None, context)
        except (KeyError, FileNotFoundError, ValueError):
            lines.extend(["", "_paragraph unavailable_", ""])
            continue
        lines.append("")
        lines.append("```")
        for paragraph in data["paragraphs"]:
            lines.append(f"[¶{paragraph['para']}] {paragraph['text']}")
        lines.append("```")
        lines.append("")
    return lines


def handle_export_paragraphs(app, match, query, body):
    items = body.get("items")
    if not isinstance(items, list) or not items:
        raise ApiError(400, "VALIDATION_ERROR", "'items' must be a non-empty list.")
    if len(items) > 50 or any(not isinstance(item, dict) for item in items):
        raise ApiError(400, "VALIDATION_ERROR", "'items' is invalid.")
    context = body.get("context", 0)
    if isinstance(context, bool) or not isinstance(context, int) or not (0 <= context <= 5):
        raise ApiError(400, "VALIDATION_ERROR", "'context' must be between 0 and 5.")
    lines = ["# Selected Contract Paragraphs", ""]
    lines.extend(selected_paragraph_lines(app.out, items, context))
    payload = "\n".join(lines).encode("utf-8")
    return ("raw", 200, "text/markdown; charset=utf-8", payload,
            [("Content-Disposition", 'attachment; filename="selected_paragraphs.md"')])


def handle_compare_export(app, match, query, body):
    items = compare_items(app.out)
    lines = ["# Compare List Export", ""]
    lines.extend(selected_paragraph_lines(app.out, items, 0))
    payload = "\n".join(lines).encode("utf-8")
    return ("raw", 200, "text/markdown; charset=utf-8", payload,
            [("Content-Disposition", 'attachment; filename="compare_list.md"')])


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


def _export_filters_text(params: Dict[str, object]) -> str:
    parts = []
    if params["ctype"]:
        parts.append(f"type={params['ctype']}")
    if params["lang"]:
        parts.append(f"lang={params['lang']}")
    parts.append(f"expand={params['expand']}")
    if params["exclude_drafts"]:
        parts.append("exclude_drafts")
    if params["show_duplicates"]:
        parts.append("show_duplicates")
    return " ".join(parts)


def _export_rows(result: Dict[str, object], params: Dict[str, object]) -> List[Dict[str, object]]:
    # UI_PRODUCT_SPEC §13: query, filters, export_created_at, file_key, filename,
    # ctype, lang, para, snippet, why를 포함한다.
    query = ", ".join(params["keywords"])
    filters_text = _export_filters_text(params)
    created_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    rows = []
    for item in result["results"]:
        rows.append({
            "query": query,
            "filters": filters_text,
            "export_created_at": created_at,
            "file_key": item["file_key"],
            "filename": os.path.basename(item["path"]),
            "path": item["path"],
            "ctype": item["ctype"],
            "lang": item["lang"],
            "is_draft": item["is_draft"],
            "version_hint": item["version_hint"] or "",
            "dup_count": item["dup_count"],
            "para": " ".join(str(p) for p in item["snippet_paras"]),
            "snippet": item["snippet"].replace("\n", " / "),
            "why": " / ".join(item.get("why") or []),
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
        for reason in item.get("why") or []:
            lines.append(f"- 검색 사유: {reason}")
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
    rows = _export_rows(result, params)
    buffer = io.StringIO()
    fieldnames = ["query", "filters", "export_created_at", "file_key", "filename", "path",
                  "ctype", "lang", "is_draft", "version_hint", "dup_count", "para",
                  "snippet", "why"]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    payload = buffer.getvalue().encode("utf-8-sig")  # BOM for Korean Windows Excel
    return ("raw", 200, "text/csv; charset=utf-8", payload,
            [("Content-Disposition", 'attachment; filename="search_export.csv"')])


def _serve_static(name: str):
    """Serve a bundled UI file. Single path segment only - no traversal."""
    if not STATIC_NAME_RE.match(name) or ".." in name:
        raise ApiError(404, "NOT_FOUND", "Unknown static file.")
    path = STATIC_DIR / name
    if not path.is_file():
        raise ApiError(404, "NOT_FOUND", "Unknown static file.")
    content_type = STATIC_TYPES.get(path.suffix.lower())
    if content_type is None:
        raise ApiError(404, "NOT_FOUND", "Unknown static file.")
    return ("raw", 200, content_type, path.read_bytes(), [])


def handle_index(app, match, query, body):
    return _serve_static("index.html")


def handle_setup(app, match, query, body):
    return _serve_static("setup.html")


def handle_settings_page(app, match, query, body):
    return _serve_static("settings.html")


def handle_operations_page(app, match, query, body):
    return _serve_static("operations.html")


def handle_research_page(app, match, query, body):
    return _serve_static("research.html")


def handle_static(app, match, query, body):
    return _serve_static(match.group("name"))


ROUTES = [
    ("GET", re.compile(r"^/$"), handle_index),
    ("GET", re.compile(r"^/setup$"), handle_setup),
    ("GET", re.compile(r"^/settings$"), handle_settings_page),
    ("GET", re.compile(r"^/operations$"), handle_operations_page),
    ("GET", re.compile(r"^/research$"), handle_research_page),
    ("GET", re.compile(r"^/api/settings/runtime-api$"), handle_runtime_api_settings),
    ("POST", re.compile(r"^/api/settings/anthropic-key$"), handle_anthropic_key_save),
    ("DELETE", re.compile(r"^/api/settings/anthropic-key$"), handle_anthropic_key_delete),
    ("POST", re.compile(r"^/api/settings/anthropic-key/test$"), handle_anthropic_key_test),
    ("POST", re.compile(r"^/api/settings/budget$"), handle_budget_save),
    ("GET", re.compile(r"^/static/(?P<name>[^/]+)$"), handle_static),
    ("GET", re.compile(r"^/api/health$"), handle_health),
    ("GET", re.compile(r"^/api/corpus/status$"), handle_corpus_status),
    ("POST", re.compile(r"^/api/search$"), handle_search),
    ("GET", re.compile(r"^/api/history/recent$"), handle_recent_searches),
    ("GET", re.compile(r"^/api/ops/dashboard$"), handle_ops_dashboard),
    ("GET", re.compile(r"^/api/ops/failures$"), handle_ops_failures),
    ("GET", re.compile(r"^/api/ops/manual-overrides/export$"), handle_manual_overrides_export),
    ("GET", re.compile(r"^/api/saved-searches$"), handle_saved_searches),
    ("POST", re.compile(r"^/api/saved-searches$"), handle_saved_search_create),
    ("DELETE", re.compile(r"^/api/saved-searches/(?P<id>[0-9]+)$"), handle_saved_search_delete),
    ("POST", re.compile(r"^/api/feedback$"), handle_feedback_create),
    ("GET", re.compile(r"^/api/marks$"), handle_marks),
    ("POST", re.compile(r"^/api/marks$"), handle_mark_create),
    ("DELETE", re.compile(r"^/api/marks/(?P<id>[0-9]+)$"), handle_mark_delete),
    ("GET", re.compile(r"^/api/compare/default$"), handle_compare_default),
    ("POST", re.compile(r"^/api/compare/default/items$"), handle_compare_item_create),
    ("DELETE", re.compile(r"^/api/compare/default/items/(?P<id>[0-9]+)$"), handle_compare_item_delete),
    ("GET", re.compile(r"^/api/compare/default/export$"), handle_compare_export),
    ("GET", re.compile(r"^/api/research/sessions$"), handle_research_sessions),
    ("POST", re.compile(r"^/api/research/sessions$"), handle_research_session_create),
    ("POST", re.compile(r"^/api/research/sessions/(?P<id>[0-9]+)/items$"), handle_research_session_item_create),
    ("POST", re.compile(r"^/api/export/paragraphs$"), handle_export_paragraphs),
    ("GET", re.compile(r"^/api/files/(?P<file_key>[^/]+)/context$"), handle_context),
    ("GET", re.compile(r"^/api/files/(?P<file_key>[^/]+)/duplicates$"), handle_duplicates),
    ("POST", re.compile(r"^/api/export/markdown$"), handle_export_markdown),
    ("POST", re.compile(r"^/api/export/csv$"), handle_export_csv),
    ("GET", re.compile(r"^/api/search/facets$"), handle_facets),
    ("GET", re.compile(r"^/api/catalog/facets$"), handle_facets),  # documented alias
    ("POST", re.compile(r"^/api/settings/root-path/validate$"), handle_root_path_validate),
    ("POST", re.compile(r"^/api/jobs/index$"), handle_jobs_index),
    ("GET", re.compile(r"^/api/jobs$"), handle_jobs_list),
    ("GET", re.compile(r"^/api/jobs/(?P<job_id>[^/]+)/log$"), handle_job_log),
    ("POST", re.compile(r"^/api/jobs/(?P<job_id>[^/]+)/cancel$"), handle_job_cancel),
    ("GET", re.compile(r"^/api/jobs/(?P<job_id>[^/]+)$"), handle_job_get),
]


class App:
    def __init__(self, out: Path):
        self.out = ensure_local_cs_index(Path(out))
        ensure_ui_state(self.out)
        # 색인 등 write 작업은 별도 job 계층(one-writer)으로 처리한다.
        self.jobs = JobQueue(self.out)
        self.jobs.register("index", index_job_handler)
        self.jobs.start()

    def shutdown(self) -> None:
        self.jobs.shutdown()

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
            # Raw exceptions must never reach the client (BACKEND_REVIEW_PC 2.9).
            traceback.print_exc(file=sys.stderr)
            return 500, "application/json; charset=utf-8", _json_bytes(
                {"error": {"code": "INTERNAL_ERROR",
                           "message": "Unexpected server error. See server log."}}), []


def _json_bytes(data) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def _reason(status: int) -> str:
    return {200: "OK", 201: "Created", 202: "Accepted", 400: "Bad Request", 404: "Not Found",
            405: "Method Not Allowed", 409: "Conflict", 413: "Payload Too Large",
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
        finally:
            app.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
