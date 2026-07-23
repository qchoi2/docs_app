import json
import sqlite3

import pytest

from v4_schema import (
    SEED_TAXONOMY,
    V4SchemaError,
    absence_is_provable,
    initialize_v4_schema,
    replace_v4_result,
    taxonomy_ids,
    validate_v4_result,
)


def database():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE files(file_key TEXT PRIMARY KEY)")
    conn.execute("INSERT INTO files(file_key) VALUES ('doc1')")
    initialize_v4_schema(conn)
    return conn


def valid_result():
    return {
        "file_key": "doc1",
        "meta_schema_version": 4,
        "taxonomy_version": 1,
        "extractor_version": "test-1",
        "prompt_version": "v4-prompt-1",
        "items": [
            {
                "item_ref": "rw-001",
                "family": "RW",
                "taxonomy_id": "RW.LABOR",
                "proposition": "대상회사는 미지급 임금이 없다고 진술한다.",
                "statement_polarity": "none_exist",
                "subject_role": "대상회사",
                "counterparty_role": "매수인",
                "action": "진술",
                "object_type": "미지급 임금",
                "effective_time": "계약체결일",
                "source_kind": "body",
                "source_id": None,
                "source_name": "계약서 본문",
                "source_ref": "¶10",
                "parent_clause_ref": None,
                "qualifier": {},
                "verbatim": "미지급된 임금이 없다",
                "loc_start": 10,
                "loc_end": 10,
                "normalized": {},
                "confidence": "high",
                "review_status": "pending",
            }
        ],
        "coverage": {
            "RW": {"body_status": "complete", "annex_status": "no_annex", "reason": None},
            "CP": {"body_status": "partial", "annex_status": "no_annex", "reason": "입력 범위 일부"},
            "COV": {"body_status": "not_evaluated", "annex_status": "not_evaluated", "reason": "입력 없음"},
            "DEF": {"body_status": "not_evaluated", "annex_status": "not_evaluated", "reason": "입력 없음"},
            "PAY": {"body_status": "not_evaluated", "annex_status": "not_evaluated", "reason": "입력 없음"},
            "REM": {"body_status": "not_evaluated", "annex_status": "not_evaluated", "reason": "입력 없음"},
        },
        "source_coverage": [],
        "taxonomy_candidates": [],
    }


def test_seed_taxonomy_and_fts_are_initialized():
    conn = database()
    assert conn.execute("SELECT COUNT(*) FROM v4_taxonomy_node").fetchone()[0] == len(SEED_TAXONOMY)
    assert (
        conn.execute(
            "SELECT parent_id FROM v4_taxonomy_node WHERE taxonomy_id='RW.LABOR.NO_VIOLATION'"
        ).fetchone()[0]
        == "RW.LABOR"
    )
    assert conn.execute(
        "SELECT parent_id FROM v4_taxonomy_node WHERE taxonomy_id='COV.SHA.TAG_ALONG'"
    ).fetchone()[0] == "COV.SHA"
    assert conn.execute(
        "SELECT parent_id FROM v4_taxonomy_node WHERE taxonomy_id='RW.TAX.RETURNS_FILED'"
    ).fetchone()[0] == "RW.TAX"
    assert conn.execute(
        "SELECT parent_id FROM v4_taxonomy_node WHERE taxonomy_id='REM.BASKET.TIPPING'"
    ).fetchone()[0] == "REM.BASKET"
    assert conn.execute(
        "SELECT parent_id FROM v4_taxonomy_node WHERE taxonomy_id='COV.SHA.QUORUM'"
    ).fetchone()[0] == "COV.SHA"
    assert conn.execute(
        "SELECT parent_id FROM v4_taxonomy_node WHERE taxonomy_id='PAY.EARNOUT.GUARANTEE'"
    ).fetchone()[0] == "PAY.EARNOUT"
    assert conn.execute(
        "SELECT parent_id FROM v4_taxonomy_node WHERE taxonomy_id='RW.IT.SYSTEMS_SUFFICIENCY'"
    ).fetchone()[0] == "RW.IT"
    assert conn.execute(
        "SELECT parent_id FROM v4_taxonomy_node WHERE taxonomy_id='COV.RWI.SUBROGATION_WAIVER'"
    ).fetchone()[0] == "COV.RWI"
    assert conn.execute(
        "SELECT parent_id FROM v4_taxonomy_node WHERE taxonomy_id='REM.THIRD_PARTY_CLAIMS.DEFENSE_CONTROL'"
    ).fetchone()[0] == "REM.THIRD_PARTY_CLAIMS"
    assert conn.execute(
        "SELECT parent_id FROM v4_taxonomy_node WHERE taxonomy_id='PAY.ESCROW.RELEASE'"
    ).fetchone()[0] == "PAY.ESCROW"
    assert conn.execute(
        """
        SELECT taxonomy_id FROM v4_taxonomy_alias
        WHERE normalized_alias='board nomination'
        """
    ).fetchone()[0] == "COV.SHA.BOARD_NOMINATION"
    assert conn.execute(
        """
        SELECT taxonomy_id FROM v4_taxonomy_alias
        WHERE normalized_alias='주주총회 승인'
        """
    ).fetchone()[0] == "CP.SHAREHOLDER_APPROVAL"
    assert "source_kind" in {
        row[1] for row in conn.execute("PRAGMA table_info(v4_clause_item)")
    }
    assert conn.execute(
        "SELECT value FROM v4_meta WHERE key='schema_revision'"
    ).fetchone()[0] == "1R2"
    now = "2026-07-16T00:00:00+00:00"
    conn.execute(
        """
        INSERT INTO v4_clause_item(
          file_key,item_ref,family,taxonomy_id,proposition,statement_polarity,
          qualifier_json,verbatim,loc_start,loc_end,normalized_json,confidence,
          txt_hash,taxonomy_version,extractor_version,prompt_version,review_status,
          created_at,updated_at
        ) VALUES ('doc1','rw-001','RW','RW.LABOR','미지급 임금이 없다','none_exist','{}',
                  '미지급된 임금이 없다',10,10,'{}','high','hash',1,'test','prompt',
                  'pending',?,?)
        """,
        (now, now),
    )
    assert conn.execute("SELECT COUNT(*) FROM v4_item_fts WHERE v4_item_fts MATCH '미지급' ").fetchone()[0] == 1


def test_validate_v4_result_and_none_exist_polarity():
    conn = database()
    result = valid_result()
    assert validate_v4_result(result, file_key="doc1", known_taxonomy=taxonomy_ids(conn)) is result
    assert result["items"][0]["statement_polarity"] == "none_exist"


def test_unknown_taxonomy_and_family_mismatch_are_rejected():
    conn = database()
    result = valid_result()
    result["items"][0]["taxonomy_id"] = "RW.NOT_REAL"
    with pytest.raises(V4SchemaError, match="unknown"):
        validate_v4_result(result, file_key="doc1", known_taxonomy=taxonomy_ids(conn))
    result = valid_result()
    result["items"][0]["family"] = "CP"
    with pytest.raises(V4SchemaError, match="another family"):
        validate_v4_result(result, file_key="doc1", known_taxonomy=taxonomy_ids(conn))


def test_items_cannot_exist_for_unreadable_family():
    conn = database()
    result = valid_result()
    result["coverage"]["RW"]["body_status"] = "unreadable"
    with pytest.raises(V4SchemaError, match="cannot exist"):
        validate_v4_result(result, file_key="doc1", known_taxonomy=taxonomy_ids(conn))


@pytest.mark.parametrize(
    ("coverage", "expected"),
    [
        ({"body_status": "complete", "annex_status": "complete"}, True),
        ({"body_status": "complete", "annex_status": "no_annex"}, True),
        ({"body_status": "complete", "annex_status": "not_evaluated"}, False),
        ({"body_status": "partial", "annex_status": "complete"}, False),
    ],
)
def test_absence_requires_complete_body_and_annex(coverage, expected):
    assert absence_is_provable(coverage) is expected


def test_source_coverage_blocks_false_complete_annex():
    conn = database()
    result = valid_result()
    result["coverage"]["RW"]["annex_status"] = "complete"
    result["source_coverage"] = [
        {
            "family": "RW",
            "source_id": "rw-schedule",
            "source_kind": "disclosure_schedule",
            "source_name": "매도인 공개사항",
            "source_ref": "별지",
            "storage_file_key": "doc1",
            "status": "missing",
            "reason": "입력에 없음",
        }
    ]
    with pytest.raises(V4SchemaError, match="cannot be complete"):
        validate_v4_result(result, file_key="doc1", known_taxonomy=taxonomy_ids(conn))


def test_replace_v4_result_persists_source_links_without_touching_doc_meta():
    conn = database()
    result = valid_result()
    replace_v4_result(conn, file_key="doc1", txt_hash="hash", data=result)
    item = conn.execute(
        "SELECT taxonomy_id,source_kind,source_ref FROM v4_clause_item"
    ).fetchone()
    assert item == ("RW.LABOR", "body", "¶10")
    assert conn.execute("SELECT COUNT(*) FROM v4_document_coverage").fetchone()[0] == 6
