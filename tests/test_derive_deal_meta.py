"""Tests for derive_deal_meta.py — 거래 메타데이터(연도·규모·준거법·관할) 로컬 파생.

이 도구의 계약은 "많이 채우는 것"이 아니라 **틀린 값을 만들지 않는 것**이다.
따라서 테스트의 중심은 커버리지가 아니라 다음 네 가지다:

1. 모르는 것은 unknown(value=None)으로 표현된다 — 추측으로 채우지 않는다.
2. 서로 다른 사실을 합치지 않는다 — 체결일/작성일, 준거법/중재지/관할법원.
3. 공란·미확정(placeholder, 괄호 선택지)은 값으로 승격되지 않는다.
4. 모든 값에 근거(basis)와 신뢰도(confidence)가 붙는다 — classify_version과 동일한 형태.

DB에 쓰지 않는다(읽기 전용 도구). 테스트도 임시 DB만 만든다.
"""
import json
import sqlite3
from contextlib import closing

import pytest

from classify_version import CONFIDENCE_LEVELS
from derive_deal_meta import (
    BAND_NAMES,
    DERIVER_VERSION,
    FIELDS,
    band_for,
    build_report,
    derive_deal_year,
    derive_document,
    derive_forum,
    derive_governing_law,
    derive_industry,
    derive_size_band,
    detail,
    is_unknown,
    load_paras,
    summarize,
    unknown,
)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def paras(*texts):
    """[¶n] 캐시와 같은 (번호, 본문) 시퀀스를 만든다."""
    return [(i + 1, t) for i, t in enumerate(texts)]


def write_txt(tmp_path, file_key, *texts):
    txt_dir = tmp_path / "txt"
    txt_dir.mkdir(exist_ok=True)
    body = "\n".join(f"[¶{i + 1}]\t{t}" for i, t in enumerate(texts))
    (txt_dir / f"{file_key}.txt").write_text(body, encoding="utf-8")
    return txt_dir


# --------------------------------------------------------------------------- #
# 0. 파생 결과의 형태 — classify_version과 같은 3종 세트
# --------------------------------------------------------------------------- #
def test_detail_shape_matches_version_provenance():
    result = detail("대한민국", "med", rule="governing_law_clause", para=12)
    assert set(result) == {"value", "confidence", "basis"}
    assert result["confidence"] in CONFIDENCE_LEVELS
    assert result["basis"]["rule"] == "governing_law_clause"
    assert result["basis"]["deriver"] == DERIVER_VERSION


def test_detail_drops_empty_basis_entries():
    """빈 근거를 기록하면 '근거가 있다'는 착시가 생긴다 — 넣지 않는다."""
    result = detail(2024, "high", rule="x", matched=None, conflicts=[], note="")
    assert "matched" not in result["basis"]
    assert "conflicts" not in result["basis"]
    assert "note" not in result["basis"]


def test_unknown_is_a_first_class_value():
    result = unknown("no_date_signal", note="단서 없음")
    assert result["value"] is None
    assert result["confidence"] is None          # 저신뢰가 아니라 '미평가'다
    assert result["basis"]["rule"] == "no_date_signal"
    assert is_unknown(result)


def test_unrecognised_confidence_degrades_to_none():
    assert detail("x", "매우높음")["confidence"] is None


# --------------------------------------------------------------------------- #
# 1. 거래 연도 — 체결일 / 작성일 / 버전일자를 구분한다
# --------------------------------------------------------------------------- #
def test_execution_sentence_gives_signing_year_with_high_confidence():
    body = paras(
        "주식매매계약서",
        '본 주식매매계약("본 계약")은 2023년 9월 4일자로 다음 당사자들 사이에서 체결되었다.',
    )
    result = derive_deal_year("SPA.docx", body, version_role="execution")
    assert result["value"] == 2023
    assert result["confidence"] == "high"
    assert result["basis"]["date_kind"] == "체결일"
    assert result["basis"]["rule"] == "preamble_execution_sentence"


def test_same_sentence_in_a_draft_is_not_called_a_signing_date():
    """초안의 전문 날짜는 작성일/체결예정일이지 체결일이 아니다."""
    body = paras('본 계약은 2023년 9월 4일자로 당사자들 사이에서 체결되었다.')
    result = derive_deal_year("SPA_draft.docx", body, version_role="draft_unknown")
    assert result["value"] == 2023
    assert result["confidence"] == "med"
    assert result["basis"]["date_kind"] == "작성일/체결예정일"


def test_reference_date_is_not_taken_as_the_deal_year():
    """실측 결함 재현: 전문의 '기준일'을 계약 연도로 집으면 안 된다.

    (1591cdd7ac895b9a — 체결일 2024년인데 기준일 2023년을 집던 사례)"""
    body = paras(
        '본 주주간계약서는 2024년 [4]월 [26]일 다음 당사자들 사이에서 체결되었다.',
        "기준일은 2023년 12월 31일을 의미한다.",
    )
    result = derive_deal_year("SHA_체결본_20240426.docx", body, version_role="execution")
    assert result["value"] == 2024


def test_covenant_deadline_and_prior_contract_date_are_not_the_deal_year():
    """확약 기한(2017년까지)·선행 계약 체결일(2014년)이 계약 연도가 되면 안 된다.

    (1672a994a13f2323 — 실제 체결일 2015년)"""
    body = paras(
        '본 주주간계약(이하 "본 계약")은 2015년 4월 30일(이하 "본 계약 체결일") '
        "아래 당사자들 사이에서 체결되었다.",
        "당사자들은 주식매매계약을 2014년 11월 26일 체결하였다.",
        "한화 주주들은 2017년 12월 31일까지 거래관계를 존중하여야 한다.",
    )
    result = derive_deal_year("SHA_체결본_20140527.doc", body, version_role="execution")
    assert result["value"] == 2015


def test_blank_month_and_day_lowers_confidence_and_says_so():
    body = paras("주식매매계약서", "본 계약은 2024. [*]. [*]. 다음 당사자들 사이에서 체결되었다.")
    result = derive_deal_year("SPA_draft.docx", body, version_role="draft_unknown")
    assert result["value"] == 2024
    assert result["confidence"] == "low"
    assert "공란" in result["basis"]["note"]


def test_year_only_preamble_without_execution_verb_is_low_and_labelled():
    body = paras("주식매매계약서", "2024. [*]. [*].")
    result = derive_deal_year("SPA.docx", body, version_role="draft_unknown")
    assert result["value"] == 2024
    assert result["confidence"] == "low"
    assert result["basis"]["date_kind"] == "작성 연도(체결일 공란)"


def test_filename_date_is_labelled_as_a_version_date_not_a_signing_date():
    result = derive_deal_year("SPA_1st_markup_20220518.docx", None,
                              version_role="buyer_markup")
    assert result["value"] == 2022
    assert result["confidence"] == "low"
    assert result["basis"]["date_kind"] == "버전 일자(파일명)"
    assert result["basis"]["source"] == "filename"


def test_six_digit_filename_date_is_low_confidence():
    result = derive_deal_year("SPA_draft_220518.docx", None)
    assert result["value"] == 2022
    assert result["confidence"] == "low"
    assert "버전번호" in result["basis"]["note"]


def test_header_footer_date_is_a_distribution_date():
    body = [(1, "주식매매계약서"), (2, "[머리글] 매수인 수정안 / 2024. 11. 26")]
    result = derive_deal_year("SPA.docx", body, version_role="buyer_markup")
    assert result["value"] == 2024
    assert result["confidence"] == "low"
    assert "머리글" in result["basis"]["date_kind"]


def test_no_date_signal_returns_unknown_not_a_guess():
    result = derive_deal_year("계약서.docx", paras("주식매매계약서", "제1조 목적"))
    assert is_unknown(result)
    assert result["basis"]["rule"] == "no_date_signal"


def test_file_mtime_is_never_a_year_source():
    """파일 mtime은 전량 재색인 시각(전 문서 2026)이라 신호가 아니다."""
    result = derive_deal_year("계약서.docx", paras("본문"))
    assert result["basis"].get("source") != "mtime"


# --------------------------------------------------------------------------- #
# 2. 거래 규모 구간 — 사람이 검수한 v3 금액만 구간화한다
# --------------------------------------------------------------------------- #
def _consideration(**kwargs):
    base = {"evaluated": True, "amount_value": 50_000_000_000, "currency": "KRW",
            "confidence": "high", "payment_methods": []}
    base.update(kwargs)
    return base


@pytest.mark.parametrize("amount,expected", [
    (5_000_000_000, "소형"),
    (10_000_000_000, "중형"),
    (99_000_000_000, "중형"),
    (100_000_000_000, "대형"),
    (999_000_000_000, "대형"),
    (1_000_000_000_000, "초대형"),
])
def test_band_boundaries(amount, expected):
    assert band_for(amount) == expected
    assert expected in BAND_NAMES


def test_curated_v3_amount_bands_with_evidence():
    result = derive_size_band(_consideration(loc_start=101,
                                             amount_verbatim="총 금 500억원"),
                              ctype="SPA", is_draft=0, meta_schema_version=3)
    assert result["value"] == "중형"
    assert result["confidence"] == "high"
    assert result["basis"]["source"] == "doc_meta_v3"
    assert result["basis"]["para"] == 101


def test_v2_metadata_cannot_be_banded():
    """v2의 consideration_json은 후보 문단 목록이라 정규화 금액이 아니다."""
    v2 = {"candidates": [{"para": 37, "text": "매매대금"}], "source": "heuristic"}
    result = derive_size_band(v2, ctype="SPA", meta_schema_version=2)
    assert is_unknown(result)
    assert result["basis"]["rule"] == "meta_schema_v2_not_normalized"


def test_unevaluated_consideration_is_unknown_not_absent():
    result = derive_size_band({"evaluated": False}, ctype="SPA", meta_schema_version=3)
    assert is_unknown(result)
    assert result["basis"]["rule"] == "consideration_not_evaluated"


def test_amount_null_after_human_review_stays_unknown():
    """별도 계약의 참조금액을 걷어낸 결과 null이 된 문서는 구간이 없다.

    (a5da55951cfdabfb — SHA 본문의 300억원은 별도 신주인수계약의 RCPS 투자금이라
    사람 검수에서 amount_value=null로 바뀌었다.)"""
    result = derive_size_band(
        _consideration(amount_value=None, amount_verbatim="관련 신주인수계약 투자금액 300억원"),
        ctype="SHA", is_draft=0, meta_schema_version=3)
    assert is_unknown(result)
    assert result["basis"]["rule"] == "amount_value_null_after_review"
    assert "300억원" in result["basis"]["amount_verbatim"]


def test_non_binding_mou_amount_is_not_banded():
    """비구속 MOU·텀시트의 금액은 확정 대가가 아니다(30fae2c6d27a9f8c 500억원)."""
    result = derive_size_band(_consideration(), ctype="MOU", is_draft=0,
                              meta_schema_version=3)
    assert is_unknown(result)
    assert result["basis"]["rule"] == "non_binding_instrument"


def test_draft_amount_is_not_banded():
    result = derive_size_band(_consideration(), ctype="SPA", is_draft=1,
                              meta_schema_version=3)
    assert is_unknown(result)
    assert result["basis"]["rule"] == "draft_amount_not_final"


def test_non_krw_amount_needs_fx_and_is_not_guessed():
    result = derive_size_band(_consideration(amount_value=10_000_000, currency="USD"),
                              ctype="SSA", is_draft=0, meta_schema_version=3)
    assert is_unknown(result)
    assert result["basis"]["rule"] == "non_krw_requires_fx"


def test_low_confidence_amount_is_not_banded():
    result = derive_size_band(_consideration(confidence="low"), ctype="SPA",
                              is_draft=0, meta_schema_version=3)
    assert is_unknown(result)
    assert result["basis"]["rule"] == "amount_confidence_low"


# --------------------------------------------------------------------------- #
# 3. 준거법
# --------------------------------------------------------------------------- #
def test_governing_law_from_operative_sentence():
    body = paras("제10조 (준거법 및 분쟁해결)",
                 "본 계약의 준거법은 대한민국 법률로 한다.")
    result = derive_governing_law(body)
    assert result["value"] == "대한민국"
    assert result["confidence"] == "med"
    assert "대한민국" in result["basis"]["verbatim"]
    assert result["basis"]["para"] == 1


def test_table_of_contents_line_does_not_become_the_clause():
    """목차 '10.10 준거법 및 분쟁해결 19'가 본문 조항보다 먼저 나온다."""
    body = paras(
        "목 차",
        "10.10 준거법 및 분쟁해결 19",
        "별지 1 정의 조항 24",
        "10.10 준거법 및 분쟁해결. 본 계약의 준거법은 대한민국 법률로 한다.",
    )
    result = derive_governing_law(body)
    assert result["value"] == "대한민국"
    assert result["basis"]["para"] == 4          # 목차(¶2)가 아니라 본문


def test_toc_only_document_is_unknown_not_a_guess():
    body = paras("목 차", "10.10 준거법 및 분쟁해결 19")
    result = derive_governing_law(body)
    assert is_unknown(result)


def test_blank_governing_law_in_a_template_is_unknown():
    """'the internal laws of ___ without reference' — 공란은 값이 아니다."""
    body = paras("Governing Law.",
                 "This Agreement shall be governed by and construed in accordance "
                 "with the internal laws of  without reference to choice of law.")
    result = derive_governing_law(body)
    assert is_unknown(result)
    assert result["basis"]["rule"] == "placeholder_in_clause"


def test_unresolved_bracket_options_are_unknown():
    """'the laws of [Hong Kong; the United Kingdom]' — 초안의 미확정 선택지."""
    body = paras("Governing Law; Forum.",
                 "This Agreement shall be governed in all respects by the laws of "
                 "[Hong Kong; the United Kingdom].")
    result = derive_governing_law(body)
    assert is_unknown(result)
    assert result["basis"]["rule"] == "unresolved_bracket_options"


def test_arbitration_seat_is_not_mistaken_for_governing_law():
    """실측 오판 재현: 준거법은 인도네시아법인데 중재지 Singapore를 준거법으로 집던 사례."""
    body = paras(
        "Governing Law and Arbitration.",
        "This Agreement and any non-contractual obligations arising out of or in "
        "connection with this Agreement shall be governed by and construed in "
        "accordance with Indonesian law.",
        "Any dispute shall be finally settled by arbitration. The seat of the "
        "arbitration shall be Singapore.",
    )
    result = derive_governing_law(body)
    assert result["value"] == "Indonesia"
    # 중재지는 준거법 문장 밖이므로 값에도, 상충 목록에도 올라오지 않는다.
    assert "Singapore" not in (result["basis"].get("conflicts") or [])
    assert "Indonesian law" in result["basis"]["verbatim"]
    # 같은 문서의 중재 축에서는 Singapore가 '중재지'로 따로 기록된다.
    assert derive_forum(body)["arbitration_seat"]["value"] == "Singapore"


def test_governing_law_conflict_is_reported_when_the_clause_window_names_another():
    """준거를 정하는 문장 밖에서 다른 관할지법이 보이면 상충으로 고지한다."""
    body = paras(
        "Governing Law.",
        "This Agreement shall be governed by and construed in accordance with "
        "Indonesian law.",
        "Nothing herein limits the application of Singapore law to the Escrow Deed.",
    )
    result = derive_governing_law(body)
    assert result["value"] == "Indonesia"
    assert result["basis"]["conflicts"] == ["Singapore"]


def test_two_jurisdictions_in_the_operative_sentence_is_unknown():
    body = paras("Governing Law.",
                 "This Agreement shall be governed by the laws of Delaware and the "
                 "laws of New York.")
    result = derive_governing_law(body)
    assert is_unknown(result)
    assert result["basis"]["rule"] == "multiple_jurisdictions_in_operative_sentence"
    assert sorted(result["basis"]["candidates"]) == ["Delaware", "New York"]


def test_missing_clause_is_undetected_not_absent():
    result = derive_governing_law(paras("주식매매계약서", "제1조 목적"))
    assert is_unknown(result)
    assert result["basis"]["rule"] == "no_governing_law_clause_found"
    assert "부재가 아니라" in result["basis"]["note"]


def test_no_text_cache_is_reported_as_such():
    result = derive_governing_law(None)
    assert is_unknown(result)
    assert result["basis"]["rule"] == "no_text_cache"


# --------------------------------------------------------------------------- #
# 4. 관할 / 중재 — 준거법과 분리된 별개의 사실
# --------------------------------------------------------------------------- #
def test_named_exclusive_court_forum():
    body = paras("제10조 (준거법 및 관할법원)",
                 "본 계약과 관련한 분쟁은 서울중앙지방법원을 1심의 전속적 관할법원으로 한다.")
    result = derive_forum(body)
    assert result["forum_court"]["value"] == "서울중앙지방법원"
    assert result["forum_type"]["value"] == "court"


def test_arbitration_mention_in_a_definition_is_not_an_agreement():
    """정의조항의 '중재절차' 열거는 중재합의가 아니다 — 실측 1,022건이 이 경우다."""
    body = paras(
        '"소송"이란 정부기관에서 진행중인 소송절차, 신청절차, 화해절차, 중재절차, '
        "행정심판절차를 말한다.")
    result = derive_forum(body)
    assert result["arbitration"]["value"] is False
    assert result["arbitration"]["basis"]["rule"] == "arbitration_mentioned_without_agreement"
    assert is_unknown(result["arbitration_institution"])


def test_real_arbitration_agreement_records_institution_and_seat_separately():
    body = paras(
        "Dispute Resolution.",
        "All disputes arising out of or in connection with this Agreement shall be "
        "finally settled under the Rules of Arbitration of the International Chamber "
        "of Commerce. The seat of the arbitration shall be Singapore.",
    )
    result = derive_forum(body)
    assert result["arbitration"]["value"] is True
    assert result["arbitration_institution"]["value"] == "ICC"
    assert result["arbitration_seat"]["value"] == "Singapore"
    assert result["forum_type"]["value"] == "arbitration"
    # 중재지는 준거법이 아니라는 사실을 근거에 남긴다
    assert "준거법이 아니다" in result["arbitration_seat"]["basis"]["note"]


def test_court_and_arbitration_together_is_not_collapsed():
    """단계적 분쟁해결 조항은 어느 쪽이 주된 절차인지 자동 판정하지 않는다."""
    body = paras(
        "분쟁해결.",
        "본 계약과 관련한 분쟁은 서울중앙지방법원을 전속적 관할법원으로 한다.",
        "다만 당사자가 합의하는 경우 분쟁은 대한상사중재원의 중재로 해결한다.",
    )
    result = derive_forum(body)
    assert result["forum_court"]["value"] == "서울중앙지방법원"
    assert result["arbitration"]["value"] is True
    assert is_unknown(result["forum_type"])
    assert result["forum_type"]["basis"]["rule"] == "court_and_arbitration_both_present"


def test_forum_clause_without_a_named_court_is_unknown():
    body = paras("분쟁의 해결.", "당사자들은 분쟁을 우호적으로 해결하기 위하여 노력한다.")
    result = derive_forum(body)
    assert is_unknown(result["forum_court"])


def test_forum_axis_degrades_wholesale_without_a_text_cache():
    result = derive_forum(None)
    assert all(is_unknown(result[key]) for key in result)
    assert result["forum_court"]["basis"]["rule"] == "no_text_cache"


# --------------------------------------------------------------------------- #
# 5. 업종 — 로컬 파생 불가를 값이 아니라 사유로 돌려준다
# --------------------------------------------------------------------------- #
def test_industry_never_produces_a_value():
    body = paras("대상회사는 반도체 제조업을 영위한다.",
                 "매도인은 제조물책임과 관련한 청구가 없음을 진술한다.")
    result = derive_industry(body)
    assert is_unknown(result)
    assert result["basis"]["rule"] == "not_locally_derivable"


def test_industry_reports_the_boilerplate_trap_it_found():
    """'제조물책임'은 거의 모든 SPA에 있는 진술보장 문구지 업종 신호가 아니다."""
    result = derive_industry(paras("매도인은 제조물책임 청구가 없음을 진술한다."))
    assert "제조물책임" in result["basis"]["boilerplate_traps"]


# --------------------------------------------------------------------------- #
# 6. 문서 단위 파생 + 집계 (임시 DB, 읽기 전용 계약 확인)
# --------------------------------------------------------------------------- #
@pytest.fixture()
def mini_index(tmp_path):
    db = tmp_path / "catalog.sqlite"
    with closing(sqlite3.connect(db)) as conn:
        conn.execute(
            "CREATE TABLE files (file_key TEXT PRIMARY KEY, filename TEXT, ctype TEXT,"
            " lang TEXT, status TEXT, is_draft INTEGER, version_role TEXT)")
        conn.execute(
            "CREATE TABLE doc_meta (file_key TEXT PRIMARY KEY, consideration_json TEXT,"
            " meta_schema_version INTEGER)")
        conn.execute(
            "INSERT INTO files VALUES ('k1','SPA_체결본_20230904.docx','SPA','국문','ok',0,'execution')")
        conn.execute(
            "INSERT INTO files VALUES ('k2','SPA_scan.pdf','SPA','국문','empty',NULL,'unknown')")
        conn.execute(
            "INSERT INTO doc_meta VALUES ('k1',?,3)",
            (json.dumps(_consideration(loc_start=9, amount_verbatim="총 금 500억원")),))
        conn.commit()
    write_txt(tmp_path, "k1",
              "주식매매계약서",
              '본 주식매매계약("본 계약")은 2023년 9월 4일자로 다음 당사자들 사이에서 체결되었다.',
              "제10조 (준거법 및 분쟁해결)",
              "본 계약의 준거법은 대한민국 법률로 한다. 본 계약과 관련한 분쟁은 "
              "서울중앙지방법원을 1심의 전속적 관할법원으로 한다.")
    return tmp_path


def test_document_derivation_carries_every_axis(mini_index):
    with closing(sqlite3.connect(mini_index / "catalog.sqlite")) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT f.*, d.consideration_json, d.meta_schema_version FROM files f"
            " LEFT JOIN doc_meta d ON d.file_key=f.file_key WHERE f.file_key='k1'"
        ).fetchone()
    record = derive_document(row, mini_index / "txt")
    for field in FIELDS:
        assert set(record[field]) == {"value", "confidence", "basis"}
    assert record["deal_year"]["value"] == 2023
    assert record["governing_law"]["value"] == "대한민국"
    assert record["forum_court"]["value"] == "서울중앙지방법원"
    assert record["size_band"]["value"] == "중형"


def test_document_without_text_cache_degrades_but_does_not_crash(mini_index):
    with closing(sqlite3.connect(mini_index / "catalog.sqlite")) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT f.*, d.consideration_json, d.meta_schema_version FROM files f"
            " LEFT JOIN doc_meta d ON d.file_key=f.file_key WHERE f.file_key='k2'"
        ).fetchone()
    record = derive_document(row, mini_index / "txt")
    assert record["text_cache"] is False
    assert is_unknown(record["governing_law"])
    assert is_unknown(record["deal_year"]) or record["deal_year"]["value"] is None


def test_build_report_performs_no_writes(mini_index):
    before = (mini_index / "catalog.sqlite").stat().st_mtime_ns
    report = build_report(mini_index)
    assert report["writes_performed"] == 0
    assert report["documents"] == 2
    assert (mini_index / "catalog.sqlite").stat().st_mtime_ns == before


def test_summary_reports_coverage_and_unknown_reasons(mini_index):
    report = build_report(mini_index)
    summary = report["summary"]
    assert set(summary) == set(FIELDS)
    year = summary["deal_year"]
    assert year["documents"] == 2
    assert year["populated"] == 1
    assert year["coverage_pct"] == 50.0
    # 못 채운 이유가 사유별로 남아야 한다 — "왜 비었는지"가 판단 근거다
    assert summary["governing_law"]["unknown_reasons"]["no_text_cache"] == 1


def test_summary_separates_confident_coverage_from_raw_coverage():
    """low만 채워진 축을 '커버리지 100%'로 읽으면 안 된다."""
    records = [{f: unknown("x") for f in FIELDS} for _ in range(2)]
    records[0]["deal_year"] = detail(2024, "low", rule="filename_yymmdd")
    records[1]["deal_year"] = detail(2023, "high", rule="preamble_execution_sentence")
    summary = summarize(records)["deal_year"]
    assert summary["coverage_pct"] == 100.0
    assert summary["high_or_med_pct"] == 50.0


def test_load_paras_returns_none_for_missing_cache(tmp_path):
    assert load_paras(tmp_path / "txt", "nope") is None
