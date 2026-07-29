"""Tests for the contract version-role (--version) search filter.

Covers both the T2 keyword search (search_contracts.py) and the V4 atomic-item
search (v4_search.py), including Korean-label input, comma-separated multi-value,
invalid-value errors, and version_role/version_label on result rows.
"""
import sqlite3
from contextlib import closing

import pytest

from classify_version import resolve_version_filter
from search_contracts import search_contracts
from v4_search import V4SearchError, search_clause_absence, search_clause_items
from tests.test_search_contracts import insert_doc, make_search_db
from tests.test_v4_search import make_index

NOW = "2026-07-24T00:00:00+00:00"


def _set_version(db_path, mapping):
    with closing(sqlite3.connect(db_path)) as conn:
        for file_key, role in mapping.items():
            conn.execute(
                "UPDATE files SET version_role=? WHERE file_key=?", (role, file_key)
            )
        conn.commit()


# --------------------------------------------------------------------------- #
# resolve_version_filter (shared helper)
# --------------------------------------------------------------------------- #

def test_resolve_accepts_role_key_label_and_nospace():
    assert resolve_version_filter("buyer_draft") == ["buyer_draft"]
    assert resolve_version_filter("매수인 초안") == ["buyer_draft"]
    assert resolve_version_filter("매수인초안") == ["buyer_draft"]
    assert resolve_version_filter("BUYER_DRAFT") == ["buyer_draft"]


def test_resolve_comma_separated_multi_and_dedup():
    assert resolve_version_filter("매수인 초안,매도인 초안") == [
        "buyer_draft",
        "seller_draft",
    ]
    # duplicates collapse, order preserved
    assert resolve_version_filter("execution, 체결본") == ["execution"]


def test_resolve_none_and_empty():
    assert resolve_version_filter(None) is None
    assert resolve_version_filter("") is None
    assert resolve_version_filter(" , ") is None


def test_resolve_invalid_lists_valid_options():
    with pytest.raises(ValueError) as exc:
        resolve_version_filter("not_a_version")
    message = str(exc.value)
    assert "not_a_version" in message
    assert "buyer_draft" in message  # role keys listed
    assert "매수인 초안" in message  # labels listed


# --------------------------------------------------------------------------- #
# T2 keyword search (search_contracts.py)
# --------------------------------------------------------------------------- #

def _make_kw_index(tmp_path):
    out, db_path = make_search_db(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        insert_doc(conn, "aaaaaaaaaaaaaaaa", "buyer_draft.docx", "자산에 관한 진술보장")
        insert_doc(conn, "bbbbbbbbbbbbbbbb", "seller_draft.docx", "자산에 관한 진술보장")
        insert_doc(conn, "cccccccccccccccc", "execution.docx", "자산에 관한 진술보장")
        conn.commit()
    _set_version(
        db_path,
        {
            "aaaaaaaaaaaaaaaa": "buyer_draft",
            "bbbbbbbbbbbbbbbb": "seller_draft",
            "cccccccccccccccc": "execution",
        },
    )
    return out


def test_kw_version_key_filter(tmp_path):
    out = _make_kw_index(tmp_path)
    result, count = search_contracts(out, keywords=["진술보장"], version="buyer_draft")
    assert count == 1
    assert {r["version_role"] for r in result["results"]} == {"buyer_draft"}


def test_kw_version_korean_label_filter(tmp_path):
    out = _make_kw_index(tmp_path)
    result, count = search_contracts(out, keywords=["진술보장"], version="매수인 초안")
    assert count == 1
    assert result["results"][0]["file_key"] == "aaaaaaaaaaaaaaaa"


def test_kw_version_comma_separated_multi(tmp_path):
    out = _make_kw_index(tmp_path)
    result, count = search_contracts(
        out, keywords=["진술보장"], version="매수인 초안,매도인 초안"
    )
    assert count == 2
    assert {r["version_role"] for r in result["results"]} == {
        "buyer_draft",
        "seller_draft",
    }


def test_kw_version_invalid_errors(tmp_path):
    out = _make_kw_index(tmp_path)
    with pytest.raises(ValueError) as exc:
        search_contracts(out, keywords=["진술보장"], version="garbage")
    assert "garbage" in str(exc.value)


def test_kw_rows_carry_version_role_and_label(tmp_path):
    out = _make_kw_index(tmp_path)
    result, _ = search_contracts(out, keywords=["진술보장"])
    by_key = {r["file_key"]: r for r in result["results"]}
    assert by_key["aaaaaaaaaaaaaaaa"]["version_role"] == "buyer_draft"
    assert by_key["aaaaaaaaaaaaaaaa"]["version_label"] == "매수인 초안"
    assert by_key["cccccccccccccccc"]["version_label"] == "체결본"


# --------------------------------------------------------------------------- #
# V4 atomic-item search (v4_search.py) — the primary target
# --------------------------------------------------------------------------- #

def _make_v4_index(tmp_path):
    """make_index has an RW item on doc a; add one on doc b so multi-version
    filtering distinguishes buyer_draft (a) from seller_draft (b)."""
    out = make_index(tmp_path)
    db_path = out / "catalog.sqlite"
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO v4_clause_item(
              file_key,item_ref,family,taxonomy_id,proposition,statement_polarity,
              source_kind,verbatim,loc_start,loc_end,confidence,txt_hash,
              taxonomy_version,extractor_version,prompt_version,review_status,
              created_at,updated_at
            ) VALUES (?,?,?,?,?,?,'body',?,?,?,'high',?,12,'test','test',
                      'approved',?,?)
            """,
            (
                "b" * 16, "RW-002", "RW", "RW.LABOR.NO_VIOLATION",
                "노무 관련 법령 위반이 없다.", "none_exist",
                "법령 위반이 없다.", 10, 10, "b" * 16, NOW, NOW,
            ),
        )
        conn.commit()
    _set_version(
        db_path,
        {"a" * 16: "buyer_draft", "b" * 16: "seller_draft", "c" * 16: "execution"},
    )
    return out


def test_v4_version_key_filter(tmp_path):
    out = _make_v4_index(tmp_path)
    result = search_clause_items(out, "RW.LABOR.NO_VIOLATION", version="buyer_draft")
    assert result["total_documents"] == 1
    assert {r["version_role"] for r in result["results"]} == {"buyer_draft"}
    assert result["query"]["version"] == ["buyer_draft"]


def test_v4_version_korean_label_filter(tmp_path):
    out = _make_v4_index(tmp_path)
    result = search_clause_items(out, "RW.LABOR.NO_VIOLATION", version="매수인 초안")
    assert result["total_documents"] == 1
    assert result["results"][0]["file_key"] == "a" * 16


def test_v4_version_comma_separated_multi(tmp_path):
    out = _make_v4_index(tmp_path)
    result = search_clause_items(
        out, "RW.LABOR.NO_VIOLATION", version="매수인 초안,매도인 초안"
    )
    assert result["total_documents"] == 2
    assert {r["version_role"] for r in result["results"]} == {
        "buyer_draft",
        "seller_draft",
    }


def test_v4_version_invalid_errors(tmp_path):
    out = _make_v4_index(tmp_path)
    with pytest.raises(V4SearchError) as exc:
        search_clause_items(out, "RW.LABOR.NO_VIOLATION", version="nope")
    assert "nope" in str(exc.value)


def test_v4_rows_carry_version_role_and_label(tmp_path):
    out = _make_v4_index(tmp_path)
    result = search_clause_items(out, "RW.LABOR.NO_VIOLATION")
    by_key = {r["file_key"]: r for r in result["results"]}
    assert by_key["a" * 16]["version_role"] == "buyer_draft"
    assert by_key["a" * 16]["version_label"] == "매수인 초안"
    assert by_key["b" * 16]["version_label"] == "매도인 초안"


def test_v4_absence_respects_version_filter_and_labels(tmp_path):
    out = _make_v4_index(tmp_path)
    # execution doc c has no RW item; version filter narrows the universe to it.
    result = search_clause_absence(out, "RW.LABOR.NO_VIOLATION", version="체결본")
    all_rows = result["confirmed_absent"] + result["needs_review"]
    assert {r["file_key"] for r in all_rows} == {"c" * 16}
    assert all_rows[0]["version_role"] == "execution"
    assert all_rows[0]["version_label"] == "체결본"
    assert result["query"]["version"] == ["execution"]
