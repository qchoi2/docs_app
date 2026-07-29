import sqlite3
from contextlib import closing

from store_pay_reextraction import store_one
from tests.test_v4_search import make_index

NOW = "2026-07-29T00:00:00+00:00"


def _known_pay(conn):
    return {r[0] for r in conn.execute("SELECT taxonomy_id FROM v4_taxonomy_node WHERE family='PAY'")}


def _add_pay_item(conn, file_key, item_ref, taxonomy_id, polarity="affirmative"):
    """Insert a single PAY item (make_index seeds only RW/CP items)."""
    conn.execute(
        """
        INSERT INTO v4_clause_item(
          file_key,item_ref,family,taxonomy_id,proposition,statement_polarity,
          source_kind,verbatim,loc_start,loc_end,confidence,txt_hash,
          taxonomy_version,extractor_version,prompt_version,review_status,
          created_at,updated_at
        ) VALUES (?,?,'PAY',?,?,?,'body',?,?,?,'high',?,12,'test','test',
                  'approved',?,?)
        """,
        (file_key, item_ref, taxonomy_id, f"{taxonomy_id} 명제", polarity,
         f"{taxonomy_id} 원문", 5, 5, file_key, NOW, NOW),
    )


def test_store_one_replaces_pay_and_marks_complete(tmp_path):
    out = make_index(tmp_path)
    data = {
        "file_key": "b" * 16,  # doc b has no PAY items -> no regression
        "reason": "re-extracted",
        "items": [
            {"taxonomy_id": "PAY.BASE_PRICE", "proposition": "매매대금은 총 Y원으로 한다.",
             "verbatim": "매매대금 Y원", "loc_start": 5, "loc_end": 6,
             "statement_polarity": "affirmative", "subject_role": "매수인", "confidence": "high"},
            {"taxonomy_id": "PAY.ESCROW.RELEASE", "proposition": "에스크로 해제 조건",
             "verbatim": "에스크로 해제", "loc_start": 8, "loc_end": 8,
             "statement_polarity": "affirmative", "subject_role": "매수인"},
        ],
    }
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        result = store_one(conn, out, data, _known_pay(conn))
        conn.commit()
        pay = conn.execute(
            "SELECT taxonomy_id,item_ref FROM v4_clause_item WHERE file_key=? AND family='PAY' ORDER BY item_ref",
            ("b" * 16,),
        ).fetchall()
        cov = conn.execute(
            "SELECT body_status,reason FROM v4_document_coverage WHERE file_key=? AND family='PAY'",
            ("b" * 16,),
        ).fetchone()
    assert result["status"] == "stored"
    assert result["pay_items"] == 2
    assert {r[0] for r in pay} == {"PAY.BASE_PRICE", "PAY.ESCROW.RELEASE"}
    assert all(r[1].startswith("PAYRX-") for r in pay)
    assert cov[0] == "complete" and cov[1] == "re-extracted"  # upserted (row did not exist)


def test_store_one_add_mode_appends_without_deleting(tmp_path):
    out = make_index(tmp_path)
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        _add_pay_item(conn, "a" * 16, "PAY-001", "PAY.BASE_PRICE")
        conn.commit()
        data = {
            "file_key": "a" * 16,
            "items": [
                {"taxonomy_id": "PAY.VAT", "proposition": "부가세는 별도로 한다.",
                 "verbatim": "부가세 별도", "loc_start": 3, "statement_polarity": "affirmative"},
            ],
        }
        before = conn.execute(
            "SELECT COUNT(*) FROM v4_clause_item WHERE file_key=? AND family='PAY'", ("a" * 16,)
        ).fetchone()[0]
        result = store_one(conn, out, data, _known_pay(conn), mode="add")
        conn.commit()
        rows = conn.execute(
            "SELECT taxonomy_id,item_ref FROM v4_clause_item WHERE file_key=? AND family='PAY'", ("a" * 16,)
        ).fetchall()
    after = {r[0] for r in rows}
    assert result["status"] == "stored" and result["mode"] == "add"
    assert result["pay_items"] == before + 1  # appended, not replaced
    assert "PAY.VAT" in after and "PAY.BASE_PRICE" in after
    assert any(r[1].startswith("PAYADD-") for r in rows)  # appended item uses PAYADD prefix


def test_store_one_skips_regression_without_marker(tmp_path):
    out = make_index(tmp_path)  # add PAY.BASE_PRICE -> domain PAY.BASE_PRICE
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        _add_pay_item(conn, "a" * 16, "PAY-001", "PAY.BASE_PRICE")
        conn.commit()
        data = {  # replace with only PAY.ESCROW drops PAY.BASE_PRICE; no marker
            "file_key": "a" * 16,
            "items": [{"taxonomy_id": "PAY.ESCROW", "proposition": "에스크로 예치",
                       "verbatim": "에스크로", "loc_start": 2, "statement_polarity": "affirmative"}],
        }
        result = store_one(conn, out, data, _known_pay(conn))
        conn.commit()
        after = {r[0] for r in conn.execute(
            "SELECT taxonomy_id FROM v4_clause_item WHERE file_key=? AND family='PAY'", ("a" * 16,)
        )}
    assert result["status"] == "skipped_regression"
    assert result["lost_domains"] == ["PAY.BASE_PRICE"]
    assert "PAY.BASE_PRICE" in after  # existing payment elements protected


def test_full_read_marker_overrides_regression(tmp_path):
    out = make_index(tmp_path)  # add PAY.BASE_PRICE -> domain PAY.BASE_PRICE
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        _add_pay_item(conn, "a" * 16, "PAY-001", "PAY.BASE_PRICE")
        conn.commit()
        data = {  # same drop, but proofread result is authoritative for this doc
            "file_key": "a" * 16,
            "review_method": "full_read",
            "items": [{"taxonomy_id": "PAY.ESCROW", "proposition": "에스크로 예치",
                       "verbatim": "에스크로", "loc_start": 2, "statement_polarity": "affirmative"}],
        }
        result = store_one(conn, out, data, _known_pay(conn))
        conn.commit()
        after = {r[0] for r in conn.execute(
            "SELECT taxonomy_id FROM v4_clause_item WHERE file_key=? AND family='PAY'", ("a" * 16,)
        )}
    assert result["status"] == "stored"
    assert result["review_method"] == "full_read"
    assert result.get("regress_overridden") is True
    assert result["lost_domains"] == ["PAY.BASE_PRICE"]  # surfaced for owner review
    assert after == {"PAY.ESCROW"}  # proofread set fully replaced the old auto set


def test_unknown_leaf_resolves_to_ancestor(tmp_path):
    out = make_index(tmp_path)
    data = {
        "file_key": "b" * 16,
        "items": [{"taxonomy_id": "PAY.EARNOUT.CLAWBACK",  # invented leaf
                   "proposition": "언아웃 환수 조항", "verbatim": "환수",
                   "loc_start": 4, "statement_polarity": "affirmative"}],
    }
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        result = store_one(conn, out, data, _known_pay(conn))
        conn.commit()
        stored = {r[0] for r in conn.execute(
            "SELECT taxonomy_id FROM v4_clause_item WHERE file_key=? AND family='PAY'", ("b" * 16,)
        )}
    assert result["status"] == "stored"
    assert stored == {"PAY.EARNOUT"}  # resolved to nearest known PAY ancestor


def test_store_one_rejects_non_pay_taxonomy(tmp_path):
    out = make_index(tmp_path)
    data = {
        "file_key": "b" * 16,
        "items": [{"taxonomy_id": "CP.THIRD_PARTY_CONSENT", "proposition": "x",
                   "verbatim": "x", "loc_start": 1, "statement_polarity": "affirmative"}],
    }
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        import pytest
        with pytest.raises(ValueError):
            store_one(conn, out, data, _known_pay(conn))
