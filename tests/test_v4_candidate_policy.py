"""Candidate admission policy — V4_PLAN §9.2 T-D (2), PLAN_REVIEW 교정 A·B."""

import json
import sqlite3

import pytest

from lib import v4_candidate_policy as policy
from v4_schema import initialize_v4_schema, replace_v4_result


# --------------------------------------------------------------------------
# 교정 A — name a DEF candidate by the term it defines, never by position
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ('"영업일"이란 대한민국에서 은행이 영업하는 날을 말한다.', "영업일"),
        ('"중요 계약"은 대상회사가 당사자인 계약으로서 다음 각 호를 말한다.', "중요 계약"),
        ('"Business Day" means a day on which banks are open.', "Business Day"),
        ('본 계약에서 "손해"라 함은 일체의 손실을 의미한다.', "손해"),
    ],
)
def test_defined_term_reads_the_quoted_term(text, expected):
    assert policy.defined_term(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "금 1억원을 초과하는 부동산의 임대차에 관한 계약",
        "노동조합과 체결한 단체협약 기타 이에 부수하는 계약;",
        "",
    ],
)
def test_defined_term_returns_none_without_definition_grammar(text):
    assert policy.defined_term(text) is None


def test_candidate_name_uses_the_term_not_the_paragraph_number():
    name = policy.candidate_name(
        "DEF", '"영업일"이란 은행 영업일을 말한다.', source_name="본문", loc_start=18
    )
    assert name == "정의용어 후보: 영업일"
    assert "¶" not in name


def test_candidate_name_falls_back_to_position_only_without_a_term():
    name = policy.candidate_name(
        "DEF", "금 1억원을 초과하는 계약", source_name="별지 1", loc_start=18
    )
    assert name == "검토후보: 별지 1 ¶18 명제"


def test_strip_candidate_prefix_handles_both_label_shapes():
    assert policy.strip_candidate_prefix("정의용어 후보: 영업일") == "영업일"
    assert policy.strip_candidate_prefix("검토후보: 본문 ¶18 명제") == "본문 ¶18 명제"
    assert policy.strip_candidate_prefix(None) == ""


# --------------------------------------------------------------------------
# 교정 B — recurrence measured on a normalized key, not on the label
# --------------------------------------------------------------------------


def test_def_recurrence_keys_on_the_term_so_the_same_term_matches():
    first = policy.recurrence_key("DEF", '"영업일"이란 은행이 영업하는 날을 말한다.')
    second = policy.recurrence_key(
        "DEF", '"영업일"이란 대한민국 은행이 영업하는 날 전부를 의미한다.'
    )
    assert first == second == "DEF.TERM:영업일"


def test_positionally_named_paragraphs_do_not_collide_on_the_key():
    # ``정의 ¶18`` means something different in every contract; the old
    # name-based recurrence signal treated those as one recurring candidate.
    left = policy.recurrence_key("DEF", "대상회사의 임대차 계약 목록")
    right = policy.recurrence_key("DEF", "대상회사의 지적재산권 라이선스 계약")
    assert left != right


def test_text_signature_masks_amounts_so_boilerplate_recurs():
    left = policy.recurrence_key("RW", "금 100,000,000원을 초과하는 계약")
    right = policy.recurrence_key("RW", "금 500,000,000원을 초과하는 계약")
    assert left == right


def test_normalize_term_folds_particles_quotes_and_case():
    assert policy.normalize_term(' "영업일"은 ') == policy.normalize_term("영업일")
    assert policy.normalize_term("Business Day") == policy.normalize_term("business  day")


# --------------------------------------------------------------------------
# The admission predicate itself
# --------------------------------------------------------------------------


def test_one_off_under_a_bare_family_root_is_not_admitted():
    decision = policy.admit(
        family="DEF",
        verbatim="이 계약에 특유한 일회성 목록 항목",
        recommended_parent_id="DEF",
        document_count=1,
    )
    assert decision.admitted is False
    assert decision.reason == "document_specific_one_off"
    assert decision.catch_all_taxonomy_id == "DEF.CONTRACT_TERM"


def test_specific_sub_node_parent_is_admitted_even_when_unique():
    decision = policy.admit(
        family="RW",
        verbatim="조세 신고가 적법하게 이루어졌다",
        recommended_parent_id="RW.TAX",
        document_count=1,
    )
    assert decision.admitted is True
    assert decision.reason == "specific_parent"


def test_recurring_wording_is_admitted_even_at_the_family_root():
    decision = policy.admit(
        family="COV",
        verbatim="당사자는 비밀을 유지하여야 한다",
        recommended_parent_id="COV",
        document_count=2,
    )
    assert decision.admitted is True
    assert decision.reason == "recurs_across_documents"


def test_non_def_families_absorb_into_the_family_root():
    for family in ("RW", "CP", "COV", "PAY", "REM"):
        assert policy.catch_all_taxonomy_id(family) == family
    assert policy.catch_all_taxonomy_id("DEF") == "DEF.CONTRACT_TERM"


# --------------------------------------------------------------------------
# Recurrence bookkeeping against a database
# --------------------------------------------------------------------------


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE files(file_key TEXT PRIMARY KEY)")
    for key in ("doc1", "doc2", "doc3"):
        conn.execute("INSERT INTO files(file_key) VALUES (?)", (key,))
    initialize_v4_schema(conn)
    return conn


def test_document_counts_count_distinct_documents():
    conn = _conn()
    for file_key in ("doc1", "doc2", "doc1"):
        policy.record_recurrence(
            conn, file_key=file_key, family="DEF", recurrence_key="DEF.TERM:영업일"
        )
    counts = policy.document_counts(conn, ["DEF.TERM:영업일", "DEF.TERM:없음"])
    assert counts == {"DEF.TERM:영업일": 2, "DEF.TERM:없음": 0}


def test_clear_document_recurrence_only_drops_that_document():
    conn = _conn()
    policy.record_recurrence(
        conn, file_key="doc1", family="DEF", recurrence_key="k"
    )
    policy.record_recurrence(
        conn, file_key="doc2", family="DEF", recurrence_key="k"
    )
    policy.clear_document_recurrence(conn, "doc1")
    assert policy.document_counts(conn, ["k"]) == {"k": 1}


def _result(file_key, candidates, *, coverage_family="DEF"):
    coverage = {
        family: {
            "body_status": "complete" if family == coverage_family else "not_evaluated",
            "annex_status": "no_annex" if family == coverage_family else "not_evaluated",
            "reason": None,
        }
        for family in ("RW", "CP", "COV", "DEF", "PAY", "REM")
    }
    return {
        "file_key": file_key,
        "meta_schema_version": 4,
        "taxonomy_version": 1,
        "extractor_version": "test-1",
        "prompt_version": "v4-prompt-1",
        "items": [],
        "coverage": coverage,
        "source_coverage": [],
        "taxonomy_candidates": candidates,
    }


def _candidate(verbatim, *, family="DEF", parent="DEF", loc=10):
    return {
        "proposed_ko": policy.candidate_name(
            family, verbatim, source_name="본문", loc_start=loc
        ),
        "proposed_en": None,
        "family": family,
        "recommended_parent_id": parent,
        "nearest_taxonomy_id": parent,
        "distinction_reason": "기존 taxonomy 규칙으로 분류되지 않음",
        "verbatim": verbatim,
        "loc_start": loc,
        "loc_end": loc,
        "source_kind": "body",
        "source_id": None,
        "source_name": "계약서 본문",
        "source_ref": f"¶{loc}",
        "parent_clause_ref": None,
        "qualifier": {},
    }


ONE_OFF = "본건 부동산 임대차 계약 제3호 목록에 기재된 개별 항목"
RECURRING = '"영업일"이란 대한민국에서 은행이 영업하는 날을 말한다.'


def test_store_absorbs_a_one_off_instead_of_minting_a_candidate():
    conn = _conn()
    replace_v4_result(
        conn,
        file_key="doc1",
        txt_hash="hash1",
        data=_result("doc1", [_candidate(ONE_OFF)]),
    )
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM v4_taxonomy_candidate WHERE status='pending'"
        ).fetchone()[0]
        == 0
    )
    row = conn.execute(
        "SELECT taxonomy_id,item_ref,verbatim,normalized_json,review_status,confidence"
        " FROM v4_clause_item"
    ).fetchone()
    assert row["taxonomy_id"] == "DEF.CONTRACT_TERM"
    assert row["item_ref"].startswith("DEF-ABS")
    assert row["verbatim"] == ONE_OFF
    assert row["confidence"] == "low"
    normalized = json.loads(row["normalized_json"])
    assert normalized["recurrence_key"] == policy.recurrence_key("DEF", ONE_OFF)


def test_absorbed_one_off_stays_searchable_in_fts():
    conn = _conn()
    replace_v4_result(
        conn,
        file_key="doc1",
        txt_hash="hash1",
        data=_result("doc1", [_candidate(ONE_OFF)]),
    )
    # V4_PLAN 원칙 5: a classification miss must degrade to "found as text",
    # never to "not searchable". Before the policy the paragraph reached the
    # candidate queue without an item, so it never entered v4_item_fts at all.
    hits = conn.execute(
        "SELECT COUNT(*) FROM v4_item_fts WHERE v4_item_fts MATCH ?", ("임대차",)
    ).fetchone()[0]
    assert hits == 1


def test_second_document_promotes_a_recurring_term_to_a_candidate():
    conn = _conn()
    replace_v4_result(
        conn,
        file_key="doc1",
        txt_hash="h1",
        data=_result("doc1", [_candidate(RECURRING)]),
    )
    assert (
        conn.execute("SELECT COUNT(*) FROM v4_taxonomy_candidate").fetchone()[0] == 0
    )
    replace_v4_result(
        conn,
        file_key="doc2",
        txt_hash="h2",
        data=_result("doc2", [_candidate(RECURRING)]),
    )
    row = conn.execute(
        "SELECT proposed_ko,document_count,recurrence_key,status,evidence_file_key"
        " FROM v4_taxonomy_candidate"
    ).fetchone()
    assert row["status"] == "pending"
    assert row["evidence_file_key"] == "doc2"
    assert row["proposed_ko"] == "정의용어 후보: 영업일"
    assert row["recurrence_key"] == "DEF.TERM:영업일"
    # 교정 B: the promise of V4_PLAN §2 that document_count tracks the real
    # number of documents a candidate was found in.
    assert row["document_count"] == 2


def test_specific_sub_node_candidate_is_stored_on_first_sight():
    conn = _conn()
    replace_v4_result(
        conn,
        file_key="doc1",
        txt_hash="h1",
        data=_result(
            "doc1",
            [_candidate("조세 신고 관련 특약", family="RW", parent="RW.TAX")],
            coverage_family="RW",
        ),
    )
    row = conn.execute(
        "SELECT recommended_parent_id,status,document_count FROM v4_taxonomy_candidate"
    ).fetchone()
    assert (row["recommended_parent_id"], row["status"]) == ("RW.TAX", "pending")
    assert row["document_count"] == 1


def test_restoring_a_document_does_not_double_count_recurrence():
    conn = _conn()
    data = _result("doc1", [_candidate(RECURRING)])
    replace_v4_result(conn, file_key="doc1", txt_hash="h1", data=data)
    replace_v4_result(conn, file_key="doc1", txt_hash="h1", data=data)
    assert policy.document_counts(conn, ["DEF.TERM:영업일"]) == {"DEF.TERM:영업일": 1}
    assert (
        conn.execute("SELECT COUNT(*) FROM v4_taxonomy_candidate").fetchone()[0] == 0
    )
