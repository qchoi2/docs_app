import json
import sqlite3
from contextlib import closing

import pytest

from taxonomy_admin import (
    TaxonomyAdminError,
    list_candidate_clusters,
    resolve_candidates,
    taxonomy_summary,
)
from v4_schema import initialize_v4_schema


def database(tmp_path):
    out = tmp_path / "cs_index"
    out.mkdir()
    path = out / "catalog.sqlite"
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(
            """
            CREATE TABLE files(
              file_key TEXT PRIMARY KEY,
              path TEXT NOT NULL,
              content_hash TEXT,
              txt_path TEXT
            )
            """
        )
        conn.executemany(
            "INSERT INTO files(file_key,path,content_hash) VALUES (?,?,?)",
            [
                ("a" * 16, "one.docx", "hash-a"),
                ("b" * 16, "two.docx", "hash-b"),
            ],
        )
        initialize_v4_schema(conn)
        now = "2026-07-24T00:00:00+00:00"
        conn.executemany(
            """
            INSERT INTO v4_taxonomy_candidate(
              proposed_ko,proposed_en,family,recommended_parent_id,
              distinction_reason,evidence_file_key,loc_start,loc_end,verbatim,
              document_count,nearest_taxonomy_id,status,resolution_json,
              created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,1,?,'pending','{}',?,?)
            """,
            [
                (
                    "신규 노무 명제",
                    None,
                    "RW",
                    "RW.LABOR",
                    "구별 필요",
                    "a" * 16,
                    10,
                    10,
                    "동일한 신규 노무 명제",
                    "RW.LABOR.NO_VIOLATION",
                    now,
                    now,
                ),
                (
                    "신규 노무 명제",
                    None,
                    "RW",
                    "RW.LABOR",
                    "구별 필요",
                    "b" * 16,
                    20,
                    20,
                    "동일한 신규 노무 명제",
                    "RW.LABOR.NO_VIOLATION",
                    now,
                    now,
                ),
            ],
        )
        conn.commit()
    return out


def test_candidate_clusters_group_identical_evidence(tmp_path):
    out = database(tmp_path)
    result = list_candidate_clusters(out)
    assert result["total_clusters"] == 1
    cluster = result["clusters"][0]
    assert cluster["candidate_count"] == 2
    assert cluster["document_count"] == 2
    assert cluster["candidate_ids"] == [1, 2]


def test_merge_is_transactional_and_logged(tmp_path):
    out = database(tmp_path)
    result = resolve_candidates(
        out,
        {
            "action": "merge",
            "candidate_ids": [1, 2],
            "taxonomy_id": "RW.LABOR.NO_VIOLATION",
            "reason": "기존 노드와 동일",
        },
    )
    assert result["status"] == "merged"
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM v4_taxonomy_candidate WHERE status='merged'"
        ).fetchone()[0] == 2
        assert conn.execute(
            "SELECT action,target_taxonomy_id FROM v4_taxonomy_action_log"
        ).fetchone() == ("merge", "RW.LABOR.NO_VIOLATION")
        items = conn.execute(
            """
            SELECT item_ref,taxonomy_id,review_status,qualifier_json
            FROM v4_clause_item ORDER BY item_ref
            """
        ).fetchall()
        assert [row[0] for row in items] == ["RW-TC000001", "RW-TC000002"]
        assert {row[1] for row in items} == {"RW.LABOR.NO_VIOLATION"}
        assert {row[2] for row in items} == {"approved"}
        assert all(json.loads(row[3])["candidate_resolution"] == "merge" for row in items)
        assert result["materialized_count"] == 2


def test_promote_creates_node_aliases_and_increments_version(tmp_path):
    out = database(tmp_path)
    before = taxonomy_summary(out)["taxonomy_version"]
    result = resolve_candidates(
        out,
        {
            "action": "promote",
            "candidate_ids": [1, 2],
            "taxonomy_id": "RW.LABOR.NEW_PILOT_RULE",
            "parent_id": "RW.LABOR",
            "canonical_ko": "파일럿 신규 노무 명제",
            "canonical_en": "New pilot labor proposition",
            "definition": "테스트용 독립 노무 명제",
            "aliases": ["동일한 신규 노무 명제"],
            "reason": "두 문서 반복",
        },
    )
    assert result["status"] == "approved"
    assert result["taxonomy_version"] == before + 1
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        assert conn.execute(
            """
            SELECT parent_id,origin,taxonomy_version
            FROM v4_taxonomy_node WHERE taxonomy_id='RW.LABOR.NEW_PILOT_RULE'
            """
        ).fetchone() == ("RW.LABOR", "promoted", before + 1)
        assert conn.execute(
            """
            SELECT COUNT(*) FROM v4_taxonomy_alias
            WHERE taxonomy_id='RW.LABOR.NEW_PILOT_RULE'
            """
        ).fetchone()[0] == 3
        assert conn.execute(
            """
            SELECT COUNT(*) FROM v4_clause_item
            WHERE taxonomy_id='RW.LABOR.NEW_PILOT_RULE'
            """
        ).fetchone()[0] == 2


def test_reject_requires_reason_and_resolved_candidates_cannot_repeat(tmp_path):
    out = database(tmp_path)
    with pytest.raises(TaxonomyAdminError, match="reason"):
        resolve_candidates(out, {"action": "reject", "candidate_ids": [1]})
    resolve_candidates(
        out,
        {"action": "reject", "candidate_ids": [1], "reason": "표 조각"},
    )
    with pytest.raises(TaxonomyAdminError) as exc:
        resolve_candidates(
            out,
            {
                "action": "merge",
                "candidate_ids": [1],
                "taxonomy_id": "RW.LABOR.NO_VIOLATION",
            },
        )
    assert exc.value.status == 409
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        assert conn.execute("SELECT COUNT(*) FROM v4_clause_item").fetchone()[0] == 0


def test_stale_candidate_rolls_back_resolution(tmp_path):
    out = database(tmp_path)
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        conn.execute(
            "UPDATE v4_taxonomy_candidate SET txt_hash='old-hash' WHERE candidate_id=1"
        )
        conn.commit()
    with pytest.raises(TaxonomyAdminError) as exc:
        resolve_candidates(
            out,
            {
                "action": "merge",
                "candidate_ids": [1],
                "taxonomy_id": "RW.LABOR.NO_VIOLATION",
                "reason": "기존 노드와 동일",
            },
        )
    assert exc.value.code == "STALE_CANDIDATE"
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        assert conn.execute(
            "SELECT status FROM v4_taxonomy_candidate WHERE candidate_id=1"
        ).fetchone()[0] == "pending"
        assert conn.execute("SELECT COUNT(*) FROM v4_clause_item").fetchone()[0] == 0


def test_merge_can_atomize_one_candidate_into_multiple_taxonomy_items(tmp_path):
    out = database(tmp_path)
    result = resolve_candidates(
        out,
        {
            "action": "merge",
            "candidate_ids": [1],
            "taxonomy_ids": [
                "RW.LABOR.NO_VIOLATION",
                "RW.LABOR.WORKING_CONDITIONS",
            ],
            "reason": "한 문단에 독립된 두 명제가 포함됨",
        },
    )
    assert result["materialized_count"] == 2
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        rows = conn.execute(
            "SELECT item_ref,taxonomy_id FROM v4_clause_item ORDER BY item_ref"
        ).fetchall()
        assert rows == [
            ("RW-TC000001-01", "RW.LABOR.NO_VIOLATION"),
            ("RW-TC000001-02", "RW.LABOR.WORKING_CONDITIONS"),
        ]


def test_alias_collision_rolls_back_promotion(tmp_path):
    out = database(tmp_path)
    with pytest.raises(TaxonomyAdminError) as exc:
        resolve_candidates(
            out,
            {
                "action": "promote",
                "candidate_ids": [1, 2],
                "taxonomy_id": "RW.LABOR.COLLISION",
                "parent_id": "RW.LABOR",
                "canonical_ko": "노무 관련 위반사항 없음",
                "canonical_en": "Collision test",
                "definition": "충돌 테스트",
            },
        )
    assert exc.value.code == "ALIAS_COLLISION"
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM v4_taxonomy_node WHERE taxonomy_id='RW.LABOR.COLLISION'"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM v4_taxonomy_candidate WHERE status='pending'"
        ).fetchone()[0] == 2
