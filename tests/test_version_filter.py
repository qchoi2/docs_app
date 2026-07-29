"""Tests for the contract version-role (--version) search filter.

Covers both the T2 keyword search (search_contracts.py) and the V4 atomic-item
search (v4_search.py), including Korean-label input, comma-separated multi-value,
invalid-value errors, and version_role/version_label on result rows.

Also covers the honesty layer around that filter: every assignment carries a
basis + confidence (classify_version_detail / files.version_basis /
files.version_confidence), a --version-filtered response always reports the
population it excluded (version_filter_notice), and a catalog that has not been
backfilled degrades to "확인 필요" instead of crashing or looking confident.
"""
import json
import sqlite3
from contextlib import closing

import pytest

from classify_version import (
    apply_to_db,
    build_version_filter_notice,
    classify_version,
    classify_version_detail,
    dry_run,
    has_version_meta,
    resolve_version_filter,
    version_basis_summary,
)
from search_contracts import search_contracts
from v4_search import V4SearchError, search_clause_absence, search_clause_items
from tests.test_search_contracts import insert_doc, make_search_db
from tests.test_v4_search import make_index

NOW = "2026-07-24T00:00:00+00:00"


def _set_version(db_path, mapping, *, confidence=None, basis=None):
    """mapping: file_key -> role. confidence/basis: file_key -> value (optional)."""
    with closing(sqlite3.connect(db_path)) as conn:
        for file_key, role in mapping.items():
            conn.execute(
                "UPDATE files SET version_role=? WHERE file_key=?", (role, file_key)
            )
        for file_key, level in (confidence or {}).items():
            conn.execute(
                "UPDATE files SET version_confidence=? WHERE file_key=?",
                (level, file_key),
            )
        for file_key, value in (basis or {}).items():
            conn.execute(
                "UPDATE files SET version_basis=? WHERE file_key=?",
                (json.dumps(value, ensure_ascii=False), file_key),
            )
        conn.commit()


def _drop_version_meta(db_path):
    """백필 전(구 스키마) DB를 재현한다 — 컬럼 자체가 없는 상태."""
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("ALTER TABLE files DROP COLUMN version_basis")
        conn.execute("ALTER TABLE files DROP COLUMN version_confidence")
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


# --------------------------------------------------------------------------- #
# 분류 근거 + 신뢰도 (classify_version_detail)
# --------------------------------------------------------------------------- #

def test_detail_strong_execution_token_is_high_confidence():
    detail = classify_version_detail("2024_SPA_체결본.docx")
    assert detail["role"] == "execution"
    assert detail["confidence"] == "high"
    assert detail["basis"]["rule"] == "execution_token"
    assert "체결" in detail["basis"]["matched"]
    assert detail["basis"]["source"] == "filename"


def test_detail_weak_execution_token_with_draft_conflict_is_low():
    # "final draft"는 execution으로 분류되지만 초안 토큰과 충돌한다 —
    # 라벨은 유지하되 신뢰도로 그 사실을 드러낸다.
    detail = classify_version_detail("SPA_final_draft.docx")
    assert detail["role"] == "execution"
    assert detail["confidence"] == "low"
    assert detail["basis"]["token_strength"] == "weak"
    assert "draft" in detail["basis"]["conflicts"]


def test_detail_round_ordinal_only_stage_is_low_confidence():
    # "1st draft"는 라운드 토큰 때문에 markup으로 잡힌다(기존 동작) —
    # 이 추정은 약하므로 low여야 한다.
    detail = classify_version_detail("SPA 1st draft.docx")
    assert detail["role"] == "markup_unknown"
    assert detail["confidence"] == "low"
    assert detail["basis"]["stage_strength"] == "round_ordinal"


def test_detail_party_and_explicit_stage_is_high():
    detail = classify_version_detail("SPA_buyer_draft_v2.docx")
    assert detail["role"] == "buyer_draft"
    assert detail["confidence"] == "high"
    assert detail["basis"]["rule"] == "party_and_stage"
    assert detail["basis"]["party"] == "buyer"


def test_detail_party_only_and_no_signal():
    party_only = classify_version_detail("매수인 검토본.docx")
    assert party_only["role"] == "buyer_ver"
    assert party_only["confidence"] == "med"
    assert party_only["basis"]["rule"] == "party_only"

    blank = classify_version_detail("무제-1.docx")
    assert blank["role"] == "unknown"
    assert blank["confidence"] == "low"
    assert blank["basis"]["rule"] == "no_signal"
    assert blank["basis"]["source"] == "none"


def test_classify_version_stays_backward_compatible():
    assert classify_version("SPA_체결본.docx") == "execution"
    assert classify_version("무제-1.docx") == "unknown"
    assert isinstance(classify_version("SPA_buyer_draft.docx"), str)


def test_version_basis_summary_says_so_when_basis_is_missing():
    summary = version_basis_summary("execution", None, None)
    assert "근거 미기록" in summary
    assert "classify_version.py --apply" in summary


# --------------------------------------------------------------------------- #
# 마이그레이션/백필 (apply_to_db) — 실제 DB가 아닌 tmp 카탈로그에서만 실행한다
# --------------------------------------------------------------------------- #

def _catalog_with_filenames(tmp_path, names):
    out, db_path = make_search_db(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        for index, name in enumerate(names):
            insert_doc(conn, f"{index:016x}", name, "본문")
        conn.commit()
    return out, db_path


def test_apply_to_db_backfills_basis_and_confidence(tmp_path):
    out, db_path = _catalog_with_filenames(tmp_path, [
        "projectA/SPA_체결본.docx",
        "projectA/SPA_seller_draft.docx",
        "projectA/SPA 2nd markup.docx",
        "무제-1.docx",
    ])
    _drop_version_meta(db_path)          # 구 스키마에서 시작

    report = apply_to_db(out)

    assert set(report["columns_added"]) == {"version_basis", "version_confidence"}
    assert report["integrity"] == "ok"
    assert report["counts"]["execution"] == 1
    assert report["confidence"]["high"] >= 1
    assert (out / ".backups" / report["backup"]).exists()

    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        assert has_version_meta(conn)
        rows = {
            row["filename"]: row
            for row in conn.execute(
                "SELECT filename,version_role,version_basis,version_confidence FROM files"
            )
        }
    signed = rows["projectA/SPA_체결본.docx"]
    assert signed["version_role"] == "execution"
    assert signed["version_confidence"] == "high"
    assert json.loads(signed["version_basis"])["rule"] == "execution_token"

    # 같은 거래의 2nd mark-up은 라운드 패리티 추론 → 작성자(seller)로 귀속되고
    # 추론이라는 사실이 basis/confidence에 남는다.
    markup = rows["projectA/SPA 2nd markup.docx"]
    assert markup["version_role"] == "seller_markup"
    assert markup["version_confidence"] == "low"
    assert json.loads(markup["version_basis"])["inference"]["kind"] == "round_parity"

    blank = rows["무제-1.docx"]
    assert blank["version_role"] == "unknown"
    assert blank["version_confidence"] == "low"


def test_apply_to_db_is_idempotent(tmp_path):
    out, db_path = _catalog_with_filenames(tmp_path, ["SPA_체결본.docx"])
    first = apply_to_db(out)
    second = apply_to_db(out)
    assert second["columns_added"] == []          # 이미 있는 컬럼은 다시 안 만든다
    assert second["counts"] == first["counts"]
    assert second["confidence"] == first["confidence"]


def test_dry_run_reports_without_writing(tmp_path):
    out, db_path = _catalog_with_filenames(tmp_path, ["SPA_체결본.docx", "무제.docx"])
    report = dry_run(out)
    assert report["counts"] == {"execution": 1, "unknown": 1}
    assert report["version_meta_columns_present"] is True
    with closing(sqlite3.connect(db_path)) as conn:
        roles = [row[0] for row in conn.execute("SELECT version_role FROM files")]
    assert roles == [None, None]                  # dry-run은 아무것도 쓰지 않는다


# --------------------------------------------------------------------------- #
# 고지 구조체 (build_version_filter_notice)
# --------------------------------------------------------------------------- #

def test_notice_counts_unknown_partial_and_low_confidence():
    notice = build_version_filter_notice(
        ["buyer_draft"],
        [
            ("buyer_draft", "high", 3),
            ("buyer_draft", "low", 1),
            ("draft_unknown", "med", 4),      # 부분 미상 — 매수인 초안일 수 있다
            ("unknown", "low", 5),            # 버전 미상
            ("execution", "high", 7),         # 명백히 다른 버전
        ],
    )
    assert notice["matched_documents"] == 4
    assert notice["matched_low_confidence"] == 1
    assert notice["excluded_total"] == 16
    assert notice["excluded_unknown"] == 5
    assert notice["excluded_partial"] == {"draft_unknown": 4}
    assert notice["excluded_low_confidence"] == 5
    assert notice["excluded_by_role"]["execution"] == 7
    assert "version_filter_excluded_unknown:5" in notice["warnings"]
    assert "version_filter_excluded_partial:4" in notice["warnings"]
    assert "version_filter_excluded_low_confidence:5" in notice["warnings"]
    assert "version_low_confidence_results:1" in notice["warnings"]
    assert "파일명 휴리스틱" in notice["warning"]


def test_notice_flags_a_catalog_without_backfill():
    notice = build_version_filter_notice(
        ["execution"], [("execution", None, 2), ("unknown", None, 3)],
        meta_available=False,
    )
    assert notice["classification_recorded"] is False
    assert notice["excluded_unrated"] == 3
    assert "version_classification_not_backfilled" in notice["warnings"]
    assert "classify_version.py" in notice["warning"]


# --------------------------------------------------------------------------- #
# T2 키워드 검색 — 고지 + 근거 전파 + 미백필 degrade
# --------------------------------------------------------------------------- #

def _make_notice_index(tmp_path):
    out, db_path = make_search_db(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        for key, name in (
            ("a" * 16, "buyer_draft.docx"),
            ("b" * 16, "draft_unknown.docx"),
            ("c" * 16, "unknown.docx"),
            ("d" * 16, "execution.docx"),
        ):
            insert_doc(conn, key, name, "자산에 관한 진술보장")
        conn.commit()
    _set_version(
        db_path,
        {"a" * 16: "buyer_draft", "b" * 16: "draft_unknown",
         "c" * 16: "unknown", "d" * 16: "execution"},
        confidence={"a" * 16: "high", "b" * 16: "med",
                    "c" * 16: "low", "d" * 16: "high"},
        basis={"a" * 16: {"rule": "party_and_stage", "matched": ["buyer", "draft"]}},
    )
    return out, db_path


def test_kw_version_filter_reports_what_it_excluded(tmp_path):
    out, _ = _make_notice_index(tmp_path)
    result, count = search_contracts(out, keywords=["진술보장"], version="buyer_draft")

    assert count == 1                       # 결과 자체는 하위호환 (요청한 role만)
    notice = result["version_filter_notice"]
    assert notice["requested"] == ["buyer_draft"]
    assert notice["matched_documents"] == 1
    assert notice["excluded_total"] == 3
    assert notice["excluded_unknown"] == 1
    assert notice["excluded_partial"] == {"draft_unknown": 1}
    assert notice["excluded_low_confidence"] == 1
    assert notice["classification_recorded"] is True
    assert "version_filter_excluded_unknown:1" in result["warnings"]
    # 제외된 문서를 세기만 하지 않고 "확인 필요" 후보로 드러낸다.
    reasons = {row["file_key"]: row["exclusion_reason"]
               for row in notice["review_candidates"]}
    assert reasons["c" * 16] == "version_unknown"
    assert reasons["b" * 16] == "partial_version"


def test_kw_rows_carry_basis_and_confidence(tmp_path):
    out, _ = _make_notice_index(tmp_path)
    result, _ = search_contracts(out, keywords=["진술보장"])
    by_key = {row["file_key"]: row for row in result["results"]}

    buyer = by_key["a" * 16]
    assert buyer["version_confidence"] == "high"
    assert buyer["version_basis"]["rule"] == "party_and_stage"
    assert "buyer" in buyer["version_basis_summary"]
    assert buyer["version_review_required"] is False

    unknown = by_key["c" * 16]
    assert unknown["version_review_required"] is True
    assert any("버전 분류 확인 필요" in reason for reason in unknown["why"])


def test_kw_search_degrades_when_columns_are_missing(tmp_path):
    out, db_path = _make_notice_index(tmp_path)
    _drop_version_meta(db_path)             # 백필 전 카탈로그

    result, count = search_contracts(out, keywords=["진술보장"], version="buyer_draft")

    assert count == 1                       # 죽지 않는다
    row = result["results"][0]
    assert row["version_confidence"] is None
    assert row["version_basis"] is None
    assert row["version_review_required"] is True     # 확신처럼 보이지 않는다
    notice = result["version_filter_notice"]
    assert notice["classification_recorded"] is False
    assert notice["excluded_unrated"] == 3
    assert "version_classification_not_backfilled" in result["warnings"]


def test_kw_version_notice_present_even_with_zero_results(tmp_path):
    out, _ = _make_notice_index(tmp_path)
    result, count = search_contracts(
        out, keywords=["존재하지않는키워드"], version="buyer_draft"
    )
    assert count == 0
    assert result["version_filter_notice"]["requested"] == ["buyer_draft"]


# --------------------------------------------------------------------------- #
# V4 검색 — 고지 + 근거 전파
# --------------------------------------------------------------------------- #

def test_v4_items_report_version_exclusions(tmp_path):
    out = _make_v4_index(tmp_path)
    db_path = out / "catalog.sqlite"
    _set_version(
        db_path,
        {"a" * 16: "buyer_draft", "b" * 16: "draft_unknown", "c" * 16: "execution"},
        confidence={"a" * 16: "high", "b" * 16: "low"},
        basis={"a" * 16: {"rule": "party_and_stage", "matched": ["buyer", "draft"]}},
    )
    result = search_clause_items(
        out, "RW.LABOR.NO_VIOLATION", version="buyer_draft"
    )
    assert result["total_documents"] == 1
    notice = result["version_filter_notice"]
    assert notice["matched_documents"] == 1
    assert notice["excluded_total"] == 1             # 항목이 있는 문서 기준
    assert notice["excluded_partial"] == {"draft_unknown": 1}
    assert "version_filter_excluded_partial:1" in result["warnings"]
    row = result["results"][0]
    assert row["version_confidence"] == "high"
    assert row["version_basis"]["rule"] == "party_and_stage"
    assert row["version_review_required"] is False


def test_v4_items_without_version_filter_have_no_notice(tmp_path):
    out = _make_v4_index(tmp_path)
    result = search_clause_items(out, "RW.LABOR.NO_VIOLATION")
    assert "version_filter_notice" not in result       # 하위 호환 (가산 필드)


def test_v4_absence_reports_version_exclusions(tmp_path):
    out = _make_v4_index(tmp_path)
    result = search_clause_absence(out, "RW.LABOR.NO_VIOLATION", version="체결본")
    notice = result["version_filter_notice"]
    assert notice["requested"] == ["execution"]
    assert notice["matched_documents"] == 1
    assert notice["excluded_total"] == 2               # buyer_draft + seller_draft
    assert notice["excluded_unrated"] == 2             # 신뢰도 미기록 상태
    assert "version_classification_not_backfilled" in result["warnings"]
    rows = result["confirmed_absent"] + result["needs_review"]
    assert rows[0]["version_review_required"] is True  # 근거 미기록 → 확인 필요


def test_v4_search_survives_missing_version_columns(tmp_path):
    out = _make_v4_index(tmp_path)
    _drop_version_meta(out / "catalog.sqlite")
    result = search_clause_items(out, "RW.LABOR.NO_VIOLATION", version="buyer_draft")
    assert result["total_documents"] == 1
    assert result["results"][0]["version_confidence"] is None
    assert result["version_filter_notice"]["classification_recorded"] is False
    absence = search_clause_absence(out, "RW.LABOR.NO_VIOLATION", version="체결본")
    assert absence["version_filter_notice"]["classification_recorded"] is False


# --------------------------------------------------------------------------- #
# 인터페이스 전파 — 웹 API / MCP
# --------------------------------------------------------------------------- #

def test_web_search_returns_version_notice_and_facets(tmp_path):
    from tests.test_webapp import get_json, make_app

    app = make_app(tmp_path)
    db_path = tmp_path / "cs_index" / "catalog.sqlite"
    _set_version(
        db_path,
        {"a" * 16: "execution", "b" * 16: "unknown", "c" * 16: "draft_unknown"},
        confidence={"a" * 16: "high", "b" * 16: "low", "c" * 16: "med"},
    )

    status, data = get_json(app, "POST", "/api/search", body={
        "kw": ["손해배상"], "no_expand": True, "show_duplicates": True,
        "version": "체결본",
    })
    assert status == 200
    notice = data["version_filter_notice"]
    assert notice["requested"] == ["execution"]
    assert notice["excluded_unknown"] == 1
    assert "version_filter_excluded_unknown:1" in data["warnings"]
    assert data["results"][0]["version_confidence"] == "high"

    status, facets = get_json(app, "GET", "/api/search/facets")
    assert status == 200
    version_facet = {row["value"]: row for row in facets["version_role"]}
    assert version_facet["execution"]["label"] == "체결본"
    assert facets["version_meta"]["unattributed_docs"] == 2   # unknown + 미분류
    assert facets["version_meta"]["classification_recorded"] is True


def test_web_export_carries_version_confidence(tmp_path):
    from tests.test_webapp import call, make_app

    app = make_app(tmp_path)
    _set_version(tmp_path / "cs_index" / "catalog.sqlite",
                 {"a" * 16: "execution"}, confidence={"a" * 16: "high"})
    status, _headers, payload = call(app, "POST", "/api/export/csv", body={
        "kw": ["손해배상"], "no_expand": True, "show_duplicates": True,
    })
    assert status == 200
    text = payload.decode("utf-8-sig")
    assert "version_confidence" in text.splitlines()[0]
    assert "체결본" in text


def test_mcp_search_exposes_notice_and_guidance(tmp_path):
    from mcp_server import ContractMcpService
    from tests.test_mcp_server import DUP_KEY, FILE_KEY, make_corpus

    out = make_corpus(tmp_path)
    _set_version(out / "catalog.sqlite",
                 {FILE_KEY: "execution", DUP_KEY: "unknown"},
                 confidence={FILE_KEY: "high", DUP_KEY: "low"})
    result = ContractMcpService(out).search(
        keywords=["목적"], no_expand=True, show_duplicates=True,
        version="execution", limit=5,
    )
    notice = result["version_filter_notice"]
    assert notice["excluded_unknown"] == 1
    assert result["mcp_guidance"]["version_excluded_documents"] == 1
    assert "휴리스틱" in result["mcp_guidance"]["version_rule"]
    assert result["results"][0]["version_confidence"] == "high"
