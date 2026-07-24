"""WSGI handlers for the standalone V4 atomic-search workbench."""

from __future__ import annotations

from pathlib import Path

from v4_search import (
    V4SearchError,
    compare_clause_items,
    search_clause_absence,
    search_clause_items,
)


def _error(exc: V4SearchError):
    status = 404 if exc.code in {"TAXONOMY_NOT_FOUND", "FILE_NOT_FOUND"} else 400
    if exc.code in {"CATALOG_NOT_FOUND", "V4_INDEX_NOT_INITIALIZED"}:
        status = 500
    return status, {"error": {"code": exc.code, "message": str(exc)}}


def handle_v4_search_page(app, match, query, body):
    path = Path(__file__).resolve().parent / "static" / "v4-search.html"
    return ("raw", 200, "text/html; charset=utf-8", path.read_bytes(), [])


def handle_v4_item_search(app, match, query, body):
    try:
        mode = str(body.get("mode") or "present")
        taxonomy_id = str(body.get("taxonomy_id") or "")
        common = {
            "polarity": body.get("polarity") or None,
            "ctype": body.get("ctype") or None,
            "lang": body.get("lang") or None,
            "include_descendants": body.get("include_descendants", True) is not False,
            "show_duplicates": body.get("show_duplicates", False) is True,
            "limit": body.get("limit", 50),
        }
        if mode == "present":
            return 200, search_clause_items(
                app.out,
                taxonomy_id,
                subject=body.get("subject") or None,
                effective_time=body.get("effective_time") or None,
                text=body.get("text") or None,
                offset=body.get("offset", 0),
                **common,
            )
        if mode == "absent":
            return 200, search_clause_absence(app.out, taxonomy_id, **common)
        raise V4SearchError("'mode' must be present or absent.")
    except V4SearchError as exc:
        return _error(exc)


def handle_v4_item_compare(app, match, query, body):
    try:
        file_keys = body.get("file_keys")
        if not isinstance(file_keys, list):
            raise V4SearchError("'file_keys' must be a list.")
        return 200, compare_clause_items(
            app.out,
            str(body.get("taxonomy_id") or ""),
            file_keys,
            polarity=body.get("polarity") or None,
            include_descendants=body.get("include_descendants", True) is not False,
        )
    except V4SearchError as exc:
        return _error(exc)
