"""Backlog backfill and reclassification tools (PLAN_REVIEW 교정 A·B)."""

import json
import sqlite3

import pytest

from backfill_v4_candidate_recurrence import backfill
from lib import v4_candidate_policy as policy
from reclassify_v4_candidate_backlog import ReclassifyError, reclassify
from v4_schema import initialize_v4_schema


NOW = "2026-07-29T00:00:00+00:00"
ONE_OFF_A = "본건 부동산 임대차 계약 제3호 목록에 기재된 개별 항목"
ONE_OFF_B = "대상회사가 보유한 특정 상표 제7호의 사용 범위"
SHARED = "당사자는 본 계약의 내용에 대하여 비밀을 유지하여야 한다"


def _insert_candidate(
    conn,
    *,
    candidate_id,
    file_key,
    verbatim,
    family="DEF",
    parent="DEF",
    status="pending",
    resolution=None,
    proposed_ko=None,
):
    conn.execute(
        """
        INSERT INTO v4_taxonomy_candidate(
          candidate_id,proposed_ko,family,recommended_parent_id,distinction_reason,
          evidence_file_key,loc_start,loc_end,verbatim,nearest_taxonomy_id,
          status,resolution_json,created_at,updated_at
        ) VALUES (?,?,?,?,'분류되지 않음',?,10,10,?,?,?,?,?,?)
        """,
        (
            candidate_id,
            proposed_ko or f"검토후보: 본문 ¶10 명제",
            family,
            parent,
            file_key,
            verbatim,
            parent,
            status,
            json.dumps(resolution or {}, ensure_ascii=False, sort_keys=True),
            NOW,
            NOW,
        ),
    )


@pytest.fixture()
def out(tmp_path):
    directory = tmp_path / "cs_index"
    directory.mkdir()
    conn = sqlite3.connect(directory / "catalog.sqlite")
    conn.execute(
        "CREATE TABLE files(file_key TEXT PRIMARY KEY, content_hash TEXT)"
    )
    for key in ("doc1", "doc2", "doc3"):
        conn.execute("INSERT INTO files VALUES (?,?)", (key, f"hash-{key}"))
    initialize_v4_schema(conn)
    # Two documents share one wording (generic) and each has a private one-off.
    _insert_candidate(conn, candidate_id=1, file_key="doc1", verbatim=SHARED)
    _insert_candidate(conn, candidate_id=2, file_key="doc2", verbatim=SHARED)
    _insert_candidate(conn, candidate_id=3, file_key="doc1", verbatim=ONE_OFF_A)
    _insert_candidate(conn, candidate_id=4, file_key="doc2", verbatim=ONE_OFF_B)
    # A sub-node proposal is a real taxonomy gap even in a single document.
    _insert_candidate(
        conn,
        candidate_id=5,
        file_key="doc3",
        verbatim="조세 신고 관련 개별 특약",
        family="RW",
        parent="RW.TAX",
    )
    # Human decisions that must survive untouched.
    _insert_candidate(
        conn,
        candidate_id=6,
        file_key="doc3",
        verbatim="사람이 승인한 후보",
        family="REM",
        parent="REM",
        status="approved",
        resolution={"action": "promote", "taxonomy_id": "REM.X"},
    )
    _insert_candidate(
        conn,
        candidate_id=7,
        file_key="doc3",
        verbatim="사람이 병합한 후보",
        family="REM",
        parent="REM",
        status="merged",
        resolution={"action": "merge", "taxonomy_id": "REM.INDEMNITY"},
    )
    _insert_candidate(
        conn,
        candidate_id=8,
        file_key="doc3",
        verbatim="사람이 기각한 후보",
        family="REM",
        parent="REM",
        status="rejected",
        resolution={"action": "reject", "reason": "불필요"},
    )
    conn.commit()
    conn.close()
    return directory


def _rows(out, sql, params=()):
    conn = sqlite3.connect(out / "catalog.sqlite")
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_backfill_dry_run_reports_without_writing(out):
    summary = backfill(out=out, apply=False)
    assert summary["applied"] is False
    assert summary["candidate_rows"] == 8
    assert summary["keys_seen_in_multiple_documents"] == 1
    counts = {
        int(row["document_count"])
        for row in _rows(out, "SELECT document_count FROM v4_taxonomy_candidate")
    }
    assert counts == {1}


def test_backfill_writes_the_real_document_count(out):
    backfill(out=out, apply=True)
    rows = {
        int(row["candidate_id"]): row
        for row in _rows(
            out,
            "SELECT candidate_id,document_count,recurrence_key"
            " FROM v4_taxonomy_candidate",
        )
    }
    # The shared wording is attested by two documents; everything else by one.
    assert rows[1]["document_count"] == 2
    assert rows[2]["document_count"] == 2
    assert rows[3]["document_count"] == 1
    assert rows[5]["document_count"] == 1
    assert rows[1]["recurrence_key"] == rows[2]["recurrence_key"]
    assert rows[1]["recurrence_key"] != rows[3]["recurrence_key"]


def test_reclassify_refuses_before_the_backfill(out):
    with pytest.raises(ReclassifyError, match="recurrence_key"):
        reclassify(out=out, apply=False, min_documents=2)


def test_reclassify_dry_run_buckets_the_backlog(out):
    backfill(out=out, apply=True)
    summary = reclassify(out=out, apply=False, min_documents=2)
    assert summary["applied"] is False
    assert summary["pending_before"] == 5
    assert summary["keep_as_candidate_generic"] == 3  # ids 1, 2 (recurring), 5 (RW.TAX)
    assert summary["retire_document_specific_one_off"] == 2  # ids 3, 4
    assert summary["admission_reasons"] == {
        "document_specific_one_off": 2,
        "recurs_across_documents": 2,
        "specific_parent": 1,
    }
    still_pending = _rows(
        out, "SELECT COUNT(*) n FROM v4_taxonomy_candidate WHERE status='pending'"
    )[0]["n"]
    assert still_pending == 5


def test_reclassify_apply_retires_one_offs_and_keeps_them_searchable(out):
    backfill(out=out, apply=True)
    summary = reclassify(out=out, apply=True, min_documents=2)
    assert summary["applied"] is True
    assert summary["absorbed_items_created"] == 2

    pending = [
        int(row["candidate_id"])
        for row in _rows(
            out,
            "SELECT candidate_id FROM v4_taxonomy_candidate"
            " WHERE status='pending' ORDER BY candidate_id",
        )
    ]
    assert pending == [1, 2, 5]

    absorbed = _rows(
        out,
        "SELECT taxonomy_id,item_ref,verbatim,review_status,confidence,normalized_json"
        " FROM v4_clause_item ORDER BY item_ref",
    )
    assert [row["taxonomy_id"] for row in absorbed] == [
        "DEF.CONTRACT_TERM",
        "DEF.CONTRACT_TERM",
    ]
    assert all(row["review_status"] == "approved" for row in absorbed)
    assert all(row["confidence"] == "low" for row in absorbed)
    assert {row["verbatim"] for row in absorbed} == {ONE_OFF_A, ONE_OFF_B}
    assert json.loads(absorbed[0]["normalized_json"])["absorbed_by"] == (
        policy.POLICY_VERSION
    )

    conn = sqlite3.connect(out / "catalog.sqlite")
    try:
        hits = conn.execute(
            "SELECT COUNT(*) FROM v4_item_fts WHERE v4_item_fts MATCH ?", ("임대차",)
        ).fetchone()[0]
    finally:
        conn.close()
    assert hits == 1


def test_reclassify_never_touches_a_human_decision(out):
    backfill(out=out, apply=True)
    before = _rows(
        out,
        "SELECT candidate_id,status,resolution_json,updated_at"
        " FROM v4_taxonomy_candidate WHERE candidate_id IN (6,7,8)"
        " ORDER BY candidate_id",
    )
    summary = reclassify(out=out, apply=True, min_documents=2)
    after = _rows(
        out,
        "SELECT candidate_id,status,resolution_json,updated_at"
        " FROM v4_taxonomy_candidate WHERE candidate_id IN (6,7,8)"
        " ORDER BY candidate_id",
    )
    assert [tuple(row) for row in before] == [tuple(row) for row in after]
    assert summary["human_decisions_before"] == {
        "approved": 1,
        "merged": 1,
        "rejected": 1,
    }
    assert summary["human_decisions_after"] == summary["human_decisions_before"]


def test_retired_rows_are_marked_as_policy_not_human_merges(out):
    backfill(out=out, apply=True)
    reclassify(out=out, apply=True, min_documents=2)
    resolutions = [
        json.loads(row["resolution_json"])
        for row in _rows(
            out,
            "SELECT resolution_json FROM v4_taxonomy_candidate"
            " WHERE candidate_id IN (3,4) ORDER BY candidate_id",
        )
    ]
    assert all(item["action"] == "absorb_catch_all" for item in resolutions)
    assert all(item["decided_by"] == "policy" for item in resolutions)
    statuses = {
        str(row["status"])
        for row in _rows(
            out,
            "SELECT status FROM v4_taxonomy_candidate WHERE candidate_id IN (3,4)",
        )
    }
    assert statuses == {"merged"}


def test_reclassify_is_idempotent(out):
    backfill(out=out, apply=True)
    reclassify(out=out, apply=True, min_documents=2)
    second = reclassify(out=out, apply=True, min_documents=2)
    assert second["pending_before"] == 3
    assert second["retire_document_specific_one_off"] == 0
    assert (
        _rows(out, "SELECT COUNT(*) n FROM v4_clause_item")[0]["n"] == 2
    )


def test_action_log_records_the_policy_run(out):
    backfill(out=out, apply=True)
    reclassify(out=out, apply=True, min_documents=2)
    row = _rows(
        out,
        "SELECT action,candidate_ids_json,payload_json FROM v4_taxonomy_action_log"
        " ORDER BY created_at DESC LIMIT 1",
    )[0]
    assert row["action"] == "merge"
    assert json.loads(row["payload_json"])["policy_action"] == "absorb_catch_all"
    assert json.loads(row["candidate_ids_json"]) == [3, 4]
