import json
import sqlite3

from audit_t3_v4 import atomicity_issues, source_coverage_issues
from plan_v4_batch import build_input, expand_family_range, expand_title_only_range
from review_v4_scope_sample import balanced_quotas
from v4_schema import initialize_v4_schema, taxonomy_parents


def sample_source():
    return {
        "file_key": "doc1",
        "content_hash": "hash",
        "ctype": "SPA",
        "lang": "국문",
        "path": "sample.docx",
        "paragraphs": [
            {"para": 1, "text": "매도인의 진술 및 보장"},
            {"para": 2, "text": "노무."},
            {"para": 3, "text": "대상회사는 노동관계법령을 위반한 사실이 없다."},
            {"para": 4, "text": "예외는 별지 1에 기재된 바와 같다."},
            {"para": 5, "text": "선행조건"},
            {"para": 6, "text": "진술 및 보장은 종결일에 진실하고 정확하여야 한다."},
            {"para": 7, "text": "확약"},
            {"para": 8, "text": "매도인은 통상적인 영업을 유지한다."},
            {"para": 10, "text": "별지 1 매도인 공개사항"},
            {"para": 11, "text": "노동관계법 위반 조사 1건이 진행 중이다."},
        ],
    }


def sample_v3_result():
    return {
        "document_status": "contract",
        "deal_type_detail": "구주매매",
        "confidence": "high",
        "clause_map_json": {
            "진술보장": {
                "present": True,
                "loc_start": 1,
                "loc_end": 4,
                "summary": "진술보장",
            },
            "선행조건": {
                "present": True,
                "loc_start": 5,
                "loc_end": 6,
                "summary": "선행조건",
            },
            "확약": {
                "present": True,
                "loc_start": 7,
                "loc_end": 8,
                "summary": "확약",
            },
        },
    }


def test_build_input_tracks_referenced_annex_and_atomic_units():
    payload = build_input(sample_source(), sample_v3_result(), taxonomy_version=2)
    inventory = payload["source_inventory"]
    assert len(inventory) == 1
    assert inventory[0]["source_kind"] == "annex"
    assert inventory[0]["status_hint"] == "available"
    assert inventory[0]["paragraphs"][0]["para"] == 10
    hints = payload["family_sections"]["RW"]["atomic_unit_hints"]
    assert any(hint["heading"] == "노무." for hint in hints)


def test_source_coverage_audit_requires_every_inventory_row():
    payload = build_input(sample_source(), sample_v3_result(), taxonomy_version=2)
    issues = source_coverage_issues({"source_coverage": []}, payload)
    assert any(issue["code"] == "source_coverage_missing" for issue in issues)


def test_atomicity_audit_rejects_parent_domain_and_uncovered_unit():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE files(file_key TEXT PRIMARY KEY)")
    initialize_v4_schema(conn)
    payload = build_input(sample_source(), sample_v3_result(), taxonomy_version=2)
    result = {
        "coverage": {
            "RW": {"body_status": "complete"},
            "CP": {"body_status": "partial"},
            "COV": {"body_status": "partial"},
            "DEF": {"body_status": "partial"},
            "PAY": {"body_status": "partial"},
            "REM": {"body_status": "partial"},
        },
        "items": [
            {
                "family": "RW",
                "taxonomy_id": "RW.LABOR",
                "source_kind": "body",
                "loc_start": 1,
                "loc_end": 1,
            }
        ],
        "taxonomy_candidates": [],
    }
    issues = atomicity_issues(result, payload, taxonomy_parents(conn))
    codes = {issue["code"] for issue in issues}
    assert "non_leaf_taxonomy_without_candidate" in codes
    assert "atomic_unit_uncovered" in codes


def test_heading_only_v3_range_expands_until_next_article():
    paragraphs = {
        10: "ARTICLE III",
        11: "Representations and Warranties of Sellers",
        12: "Section 3.1 Seller represents and warrants subject to Schedule 3.1.",
        13: "ARTICLE IV",
        14: "Representations and Warranties of Buyer",
    }
    assert expand_title_only_range(paragraphs, 11, 11) == (11, 12)


def test_family_range_expands_to_next_family_start():
    result = sample_v3_result()
    result["clause_map_json"]["진술보장"]["loc_end"] = 2
    paragraphs = {number: f"문단 {number}" for number in range(1, 10)}
    assert expand_family_range(paragraphs, result, "RW", 1, 2) == (1, 4)


def test_build_input_includes_definitions_payment_and_remedies():
    source = sample_source()
    source["paragraphs"].extend(
        [
            {"para": 12, "text": "제1조 용어의 정의"},
            {"para": 13, "text": '"매매대금"은 금 100원이다.'},
            {"para": 14, "text": "제2조 매매대금"},
            {"para": 15, "text": "매수인은 종결일에 매매대금을 지급한다."},
            {"para": 16, "text": "손해배상"},
            {"para": 17, "text": "책임한도는 매매대금의 10%이다."},
        ]
    )
    result = sample_v3_result()
    result["definitions_json"] = {
        "items": [{"term": "매매대금", "loc_start": 13, "loc_end": 13}]
    }
    result["consideration_json"] = {
        "loc_start": 15,
        "loc_end": 15,
        "evaluated": True,
    }
    result["clause_map_json"]["손해배상"] = {
        "present": True,
        "loc_start": 16,
        "loc_end": 17,
    }
    payload = build_input(source, result, taxonomy_version=3)
    assert list(payload["family_sections"]) == [
        "RW",
        "CP",
        "COV",
        "DEF",
        "PAY",
        "REM",
    ]
    assert payload["family_sections"]["DEF"]["v3_present"] is True
    assert payload["family_sections"]["PAY"]["v3_present"] is True
    assert payload["family_sections"]["REM"]["v3_present"] is True


def test_scope_review_balances_200_across_type_and_language():
    quotas = balanced_quotas(200)
    assert sum(quotas.values()) == 200
    assert set(quotas.values()) == {25}
