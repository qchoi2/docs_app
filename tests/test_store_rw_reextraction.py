import sqlite3
from contextlib import closing

from store_rw_reextraction import store_one
from tests.test_v4_search import make_index


def _known_rw(conn):
    return {r[0] for r in conn.execute("SELECT taxonomy_id FROM v4_taxonomy_node WHERE family='RW'")}


def test_store_one_replaces_rw_and_marks_complete(tmp_path):
    out = make_index(tmp_path)
    data = {
        "file_key": "b" * 16,  # doc b has no RW items, RW coverage complete
        "reason": "re-extracted",
        "items": [
            {"taxonomy_id": "RW.LABOR.NO_VIOLATION", "proposition": "노무 위반 없음",
             "verbatim": "위반 없음", "loc_start": 5, "loc_end": 5,
             "statement_polarity": "none_exist", "subject_role": "대상회사", "confidence": "high"},
            {"taxonomy_id": "RW.TAX", "proposition": "조세 신고·납부 완료",
             "verbatim": "세금 납부", "loc_start": 8, "loc_end": 8,
             "statement_polarity": "affirmative", "subject_role": "대상회사"},
        ],
    }
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        result = store_one(conn, out, data, _known_rw(conn))
        conn.commit()
        rw = conn.execute(
            "SELECT taxonomy_id,item_ref FROM v4_clause_item WHERE file_key=? AND family='RW' ORDER BY item_ref",
            ("b" * 16,),
        ).fetchall()
        cov = conn.execute(
            "SELECT body_status,reason FROM v4_document_coverage WHERE file_key=? AND family='RW'",
            ("b" * 16,),
        ).fetchone()
    assert result["status"] == "stored"
    assert result["rw_items"] == 2
    assert {r[0] for r in rw} == {"RW.LABOR.NO_VIOLATION", "RW.TAX"}
    assert all(r[1].startswith("RWRX-") for r in rw)
    assert cov[0] == "complete" and cov[1] == "re-extracted"


def test_store_one_rejects_non_rw_taxonomy(tmp_path):
    out = make_index(tmp_path)
    data = {
        "file_key": "b" * 16,
        "items": [{"taxonomy_id": "CP.THIRD_PARTY_CONSENT", "proposition": "x",
                   "verbatim": "x", "loc_start": 1, "statement_polarity": "affirmative"}],
    }
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        import pytest
        with pytest.raises(ValueError):
            store_one(conn, out, data, _known_rw(conn))
