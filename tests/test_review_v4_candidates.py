import sqlite3

from review_v4_candidates import analyze_candidates, apply_analysis
from v4_schema import initialize_v4_schema


def database(tmp_path):
    out = tmp_path / "cs_index"
    out.mkdir()
    with sqlite3.connect(out / "catalog.sqlite") as conn:
        conn.execute(
            """
            CREATE TABLE files(
              file_key TEXT PRIMARY KEY,
              path TEXT NOT NULL,
              content_hash TEXT
            )
            """
        )
        conn.execute("INSERT INTO files VALUES ('doc1','one.docx','hash1')")
        initialize_v4_schema(conn)
        now = "2026-07-24T00:00:00+00:00"
        rows = [
            (
                "소송 부재",
                "RW",
                "RW.LITIGATION",
                "doc1",
                10,
                "본건 거래를 금지하는 소송은 제기되지 아니하였다.",
                "RW.LITIGATION.NO_PENDING",
            ),
            (
                "확약 리드인",
                "COV",
                "COV",
                "doc1",
                20,
                "각 당사자는 상대방 당사자에게 아래와 같이 확약한다.",
                "COV.TRANSITION",
            ),
            (
                "미분류",
                "RW",
                "RW",
                "doc1",
                30,
                "이 문구는 아직 새로운 검토가 필요하다.",
                "RW.AUTHORITY.POWER",
            ),
        ]
        for proposed, family, parent, file_key, para, verbatim, nearest in rows:
            conn.execute(
                """
                INSERT INTO v4_taxonomy_candidate(
                  proposed_ko,family,recommended_parent_id,distinction_reason,
                  evidence_file_key,loc_start,loc_end,verbatim,
                  nearest_taxonomy_id,txt_hash,status,resolution_json,
                  created_at,updated_at
                ) VALUES (?,?,?,'test',?,?,?,?,?,'hash1','pending','{}',?,?)
                """,
                (
                    proposed,
                    family,
                    parent,
                    file_key,
                    para,
                    para,
                    verbatim,
                    nearest,
                    now,
                    now,
                ),
            )
        conn.commit()
    return out


def test_candidate_review_dry_run_and_apply(tmp_path):
    out = database(tmp_path)
    analysis = analyze_candidates(out)
    assert analysis["merge_candidate_count"] == 1
    assert analysis["materialized_item_count"] == 1
    assert analysis["reject_candidate_count"] == 1
    assert analysis["unresolved_candidate_count"] == 1

    result = apply_analysis(out, analysis)
    assert result["resolved_candidate_count"] == 2
    assert result["materialized_item_count"] == 1
    assert result["pending_after"] == 1
    with sqlite3.connect(out / "catalog.sqlite") as conn:
        assert conn.execute(
            "SELECT taxonomy_id FROM v4_clause_item"
        ).fetchone()[0] == "RW.LITIGATION.NO_PENDING"
