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


def test_store_one_add_mode_appends_without_deleting(tmp_path):
    out = make_index(tmp_path)  # doc a has 1 RW item (RW.LABOR.NO_VIOLATION)
    data = {
        "file_key": "a" * 16,
        "items": [
            {"taxonomy_id": "RW.ENVIRONMENT", "proposition": "환경 법령 준수",
             "verbatim": "환경 준수", "loc_start": 3, "statement_polarity": "affirmative"},
        ],
    }
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        before = conn.execute(
            "SELECT COUNT(*) FROM v4_clause_item WHERE file_key=? AND family='RW'", ("a" * 16,)
        ).fetchone()[0]
        result = store_one(conn, out, data, _known_rw(conn), mode="add")
        conn.commit()
        after = {r[0] for r in conn.execute(
            "SELECT taxonomy_id FROM v4_clause_item WHERE file_key=? AND family='RW'", ("a" * 16,)
        )}
    assert result["status"] == "stored" and result["mode"] == "add"
    assert result["rw_items"] == before + 1  # appended, not replaced
    assert "RW.ENVIRONMENT" in after and "RW.LABOR.NO_VIOLATION" in after


def test_store_one_skips_regression_without_marker(tmp_path):
    out = make_index(tmp_path)  # doc a has RW.LABOR.NO_VIOLATION -> domain RW.LABOR
    data = {  # replace with only RW.TAX drops RW.LABOR; no proofread marker
        "file_key": "a" * 16,
        "items": [{"taxonomy_id": "RW.TAX", "proposition": "조세 신고 완료",
                   "verbatim": "세금", "loc_start": 2, "statement_polarity": "affirmative"}],
    }
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        result = store_one(conn, out, data, _known_rw(conn))
        conn.commit()
        after = {r[0] for r in conn.execute(
            "SELECT taxonomy_id FROM v4_clause_item WHERE file_key=? AND family='RW'", ("a" * 16,)
        )}
    assert result["status"] == "skipped_regression"
    assert result["lost_domains"] == ["RW.LABOR"]
    assert "RW.LABOR.NO_VIOLATION" in after  # existing reps protected


def test_full_read_marker_overrides_regression(tmp_path):
    out = make_index(tmp_path)  # doc a has RW.LABOR.NO_VIOLATION -> domain RW.LABOR
    data = {  # same drop, but proofread result is authoritative for this doc
        "file_key": "a" * 16,
        "review_method": "full_read",
        "items": [{"taxonomy_id": "RW.TAX", "proposition": "조세 신고 완료",
                   "verbatim": "세금", "loc_start": 2, "statement_polarity": "affirmative"}],
    }
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        result = store_one(conn, out, data, _known_rw(conn))
        conn.commit()
        after = {r[0] for r in conn.execute(
            "SELECT taxonomy_id FROM v4_clause_item WHERE file_key=? AND family='RW'", ("a" * 16,)
        )}
    assert result["status"] == "stored"
    assert result["review_method"] == "full_read"
    assert result.get("regress_overridden") is True
    assert result["lost_domains"] == ["RW.LABOR"]  # surfaced for owner review
    assert after == {"RW.TAX"}  # proofread set fully replaced the old auto set


def test_gate_collapses_exact_duplicate_items(tmp_path):
    out = make_index(tmp_path)  # doc b has no RW items -> no regression on replace
    dup = {"taxonomy_id": "RW.TAX", "proposition": "조세 신고·납부 완료",
           "verbatim": "세금 납부", "loc_start": 8, "loc_end": 8,
           "statement_polarity": "affirmative", "subject_role": "대상회사"}
    data = {"file_key": "b" * 16, "items": [dict(dup), dict(dup),  # byte-identical pair
             {"taxonomy_id": "RW.LABOR.NO_VIOLATION", "proposition": "노무 위반 없음",
              "verbatim": "위반 없음", "loc_start": 5, "loc_end": 5,
              "statement_polarity": "none_exist", "subject_role": "대상회사"}]}
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        result = store_one(conn, out, data, _known_rw(conn))
        conn.commit()
        n = conn.execute(
            "SELECT COUNT(*) FROM v4_clause_item WHERE file_key=? AND family='RW'", ("b" * 16,)
        ).fetchone()[0]
    assert result["status"] == "stored"
    assert result["rw_items"] == 2  # identical pair collapsed to one
    assert result["gate_flags"]["deduped"] == 1
    assert n == 2


def test_gate_flags_duplicate_verbatim_without_dropping(tmp_path):
    out = make_index(tmp_path)
    # same verbatim + same taxonomy + overlapping ¶, DIFFERENT proposition:
    # not an exact duplicate (proposition differs) so both are kept, but flagged.
    data = {"file_key": "b" * 16, "items": [
        {"taxonomy_id": "RW.TAX", "proposition": "명제 A", "verbatim": "동일한 세무 문장",
         "loc_start": 8, "loc_end": 8, "statement_polarity": "affirmative"},
        {"taxonomy_id": "RW.TAX", "proposition": "명제 B", "verbatim": "동일한 세무 문장",
         "loc_start": 8, "loc_end": 8, "statement_polarity": "affirmative"}]}
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        result = store_one(conn, out, data, _known_rw(conn))
        conn.commit()
    assert result["status"] == "stored"
    assert result["rw_items"] == 2  # both kept — distinct propositions preserved
    assert "duplicate_verbatim" in result["gate_flags"]


def test_gate_flags_shotgun_density(tmp_path):
    out = make_index(tmp_path)
    # 8 distinct-verbatim items sharing one ¶ -> over-segmentation density flag.
    items = [{"taxonomy_id": "RW.TAX", "proposition": f"명제 {i}",
              "verbatim": f"세무 관련 문장 번호 {i}", "loc_start": 8, "loc_end": 8,
              "statement_polarity": "affirmative"} for i in range(8)]
    data = {"file_key": "b" * 16, "items": items}
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        result = store_one(conn, out, data, _known_rw(conn))
        conn.commit()
    assert result["status"] == "stored"  # flagged, never blocked
    assert result["gate_flags"]["dense_paragraphs"][0]["item_count"] == 8
    assert result["gate_flags"]["shotgun_severe"] == 8


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
