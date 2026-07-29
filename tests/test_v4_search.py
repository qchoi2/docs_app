import sqlite3
from contextlib import closing

import pytest

from lib.catalog import initialize_catalog
from v4_schema import initialize_v4_schema
from v4_search import (
    V4SearchError,
    compare_clause_items,
    search_clause_absence,
    search_clause_items,
)


NOW = "2026-07-24T00:00:00+00:00"


def make_index(tmp_path):
    out = tmp_path / "cs_index"
    db_path = initialize_catalog(out / "catalog.sqlite")
    with closing(sqlite3.connect(db_path)) as conn:
        rows = []
        for letter, name in (("a", "present"), ("b", "absent"), ("c", "partial")):
            key = letter * 16
            rows.append(
                (
                    key,
                    f"{name}.docx",
                    "",
                    f"{name}.docx",
                    "SPA",
                    "국문",
                    ".docx",
                    1,
                    1,
                    f"txt/{letter}.txt",
                    10,
                    "ok",
                    "{}",
                    "full",
                    key,
                    key,
                    NOW,
                )
            )
        conn.executemany(
            """
            INSERT INTO files(
              file_key,path,folder,filename,ctype,lang,ext,size,mtime,txt_path,
              char_count,status,source_signals,batch_label,content_hash,
              dup_group,indexed_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            rows,
        )
        initialize_v4_schema(conn)
        conn.execute(
            """
            INSERT INTO v4_clause_item(
              file_key,item_ref,family,taxonomy_id,proposition,statement_polarity,
              source_kind,verbatim,loc_start,loc_end,confidence,txt_hash,
              taxonomy_version,extractor_version,prompt_version,review_status,
              created_at,updated_at
            ) VALUES (?,?,?,?,?,?,'body',?,?,?,'high',?,12,'test','test',
                      'approved',?,?)
            """,
            (
                "a" * 16,
                "RW-001",
                "RW",
                "RW.LABOR.NO_VIOLATION",
                "노무 관련 법령 위반이 없다.",
                "none_exist",
                "법령 위반이 없다.",
                10,
                10,
                "a" * 16,
                NOW,
                NOW,
            ),
        )
        # doc a also has a CP item, so CP (non-gated) exercises the full
        # present/confirmed_absent/needs_review classification.
        conn.execute(
            """
            INSERT INTO v4_clause_item(
              file_key,item_ref,family,taxonomy_id,proposition,statement_polarity,
              source_kind,verbatim,loc_start,loc_end,confidence,txt_hash,
              taxonomy_version,extractor_version,prompt_version,review_status,
              created_at,updated_at
            ) VALUES (?,?,?,?,?,?,'body',?,?,?,'high',?,12,'test','test',
                      'approved',?,?)
            """,
            (
                "a" * 16, "CP-001", "CP", "CP.THIRD_PARTY_CONSENT",
                "제3자 동의를 종결 선행조건으로 한다.", "affirmative",
                "제3자 동의를 얻어야 한다.", 12, 12, "a" * 16, NOW, NOW,
            ),
        )
        for letter, body_status in (("a", "complete"), ("b", "complete"), ("c", "partial")):
            # RW and CP coverage; no CP items exist, so CP (a covenant/condition
            # family, not absence-gated) can exercise the confirmed_absent path.
            for family in ("RW", "CP"):
                conn.execute(
                    """
                    INSERT INTO v4_document_coverage(
                      file_key,family,body_status,annex_status,txt_hash,
                      taxonomy_version,extractor_version,prompt_version,reviewed_at
                    ) VALUES (?,?,?,'no_annex',?,12,'test','test',?)
                    """,
                    (letter * 16, family, body_status, letter * 16, NOW),
                )
        conn.commit()
    return out


def test_search_resolves_alias_and_returns_atomic_coordinates(tmp_path):
    out = make_index(tmp_path)
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        label = conn.execute(
            "SELECT canonical_ko FROM v4_taxonomy_node "
            "WHERE taxonomy_id='RW.LABOR.NO_VIOLATION'"
        ).fetchone()[0]
    result = search_clause_items(out, label, polarity="none_exist")
    assert result["query"]["taxonomy_id"] == "RW.LABOR.NO_VIOLATION"
    assert result["total_documents"] == 1
    assert result["results"][0]["loc_start"] == 10
    assert result["results"][0]["match_path"] == "v4_atomic_item"


def test_rw_absence_is_demoted_to_needs_review(tmp_path):
    # RW coverage is unverified (see V4_RW_COVERAGE_DEFECT), so even a complete
    # RW family never confirms absence — it is demoted to needs_review.
    out = make_index(tmp_path)
    result = search_clause_absence(out, "RW.LABOR.NO_VIOLATION")
    assert result["confirmed_absent"] == []
    review_keys = {row["file_key"] for row in result["needs_review"]}
    assert review_keys == {"b" * 16, "c" * 16}
    assert result["present_excluded_count"] == 1
    by_key = {row["file_key"]: row for row in result["needs_review"]}
    assert "rw_coverage_unverified" in by_key["b" * 16]["coverage"]["reasons"]
    assert "body_partial" in by_key["c" * 16]["coverage"]["reasons"]
    assert "rw_absence_unverified_demoted_to_needs_review" in result["warnings"]


def test_non_rw_family_confirms_absent(tmp_path):
    # CP is a covenant/condition family (not gated); complete coverage with no
    # CP item still proves absence.
    out = make_index(tmp_path)
    result = search_clause_absence(out, "CP.THIRD_PARTY_CONSENT")
    # doc a has a CP item (present, excluded); doc b is complete+no item.
    assert [row["file_key"] for row in result["confirmed_absent"]] == ["b" * 16]
    assert [row["file_key"] for row in result["needs_review"]] == ["c" * 16]
    assert result["present_excluded_count"] == 1
    assert "rw_absence_unverified_demoted_to_needs_review" not in result["warnings"]


def test_pending_family_candidate_blocks_absence(tmp_path):
    out = make_index(tmp_path)
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        conn.execute(
            """
            INSERT INTO v4_taxonomy_candidate(
              proposed_ko,family,recommended_parent_id,distinction_reason,
              evidence_file_key,loc_start,loc_end,verbatim,status,
              created_at,updated_at
            ) VALUES ('새 노무 명제','RW','RW.LABOR','검토 필요',?,1,1,
                      '새 노무 명제','pending',?,?)
            """,
            ("b" * 16, NOW, NOW),
        )
        conn.commit()
    result = search_clause_absence(out, "RW.LABOR.NO_VIOLATION")
    assert not result["confirmed_absent"]
    assert "pending_taxonomy_candidates:1" in result["needs_review"][0]["coverage"]["reasons"]


def _insert_candidate(conn, *, proposed_ko, family, parent, file_key, document_count=1):
    conn.execute(
        """
        INSERT INTO v4_taxonomy_candidate(
          proposed_ko,family,recommended_parent_id,distinction_reason,
          evidence_file_key,loc_start,loc_end,verbatim,document_count,status,
          created_at,updated_at
        ) VALUES (?,?,?,'검토 필요',?,1,1,?,?,'pending',?,?)
        """,
        (proposed_ko, family, parent, file_key, proposed_ko, document_count, NOW, NOW),
    )


def test_one_off_document_specific_candidate_does_not_block_absence(tmp_path):
    # A pending document-specific one-off (single doc, bare family-root catch-all
    # parent, no cross-doc cluster) must NOT demote confirmed_absent. Per
    # V4_PLAN §9.2 T-D absence eligibility is decoupled from that backlog.
    out = make_index(tmp_path)
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        _insert_candidate(
            conn,
            proposed_ko="이 계약 고유 정의어",
            family="CP",
            parent="CP",  # bare family root => catch-all one-off
            file_key="b" * 16,
        )
        conn.commit()
    result = search_clause_absence(out, "CP.THIRD_PARTY_CONSENT")
    assert [row["file_key"] for row in result["confirmed_absent"]] == ["b" * 16]
    reasons = result["confirmed_absent"][0]["coverage"]["reasons"]
    assert not any(r.startswith("pending_taxonomy_candidates") for r in reasons)


def test_specific_subnode_candidate_still_blocks_absence(tmp_path):
    # A pending candidate recommended under a specific sub-node (dotted parent)
    # is a genuine taxonomy gap, not a one-off — it still demotes to needs_review.
    out = make_index(tmp_path)
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        _insert_candidate(
            conn,
            proposed_ko="새 종결 선행조건 명제",
            family="CP",
            parent="CP.THIRD_PARTY_CONSENT",  # dotted => specific sub-node
            file_key="b" * 16,
        )
        conn.commit()
    result = search_clause_absence(out, "CP.THIRD_PARTY_CONSENT")
    assert result["confirmed_absent"] == []
    by_key = {row["file_key"]: row for row in result["needs_review"]}
    assert "pending_taxonomy_candidates:1" in by_key["b" * 16]["coverage"]["reasons"]


def test_cross_document_candidate_still_blocks_absence(tmp_path):
    # The same proposed name appearing across >1 document is a genuine cross-doc
    # cluster (not a one-off) even with a bare catch-all parent — still blocks.
    out = make_index(tmp_path)
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        for fk in ("b" * 16, "c" * 16):
            _insert_candidate(
                conn,
                proposed_ko="여러 계약 공통 명제",
                family="CP",
                parent="CP",  # bare, but recurs across docs
                file_key=fk,
            )
        conn.commit()
    result = search_clause_absence(out, "CP.THIRD_PARTY_CONSENT")
    assert result["confirmed_absent"] == []
    by_key = {row["file_key"]: row for row in result["needs_review"]}
    assert "pending_taxonomy_candidates:1" in by_key["b" * 16]["coverage"]["reasons"]


def test_compare_distinguishes_present_absent_and_review(tmp_path):
    out = make_index(tmp_path)
    result = compare_clause_items(
        out,
        "RW.LABOR.NO_VIOLATION",
        ["a" * 16, "b" * 16, "c" * 16],
    )
    assert [row["state"] for row in result["comparison"]] == [
        "confirmed_present",
        "confirmed_absent",
        "needs_review",
    ]


def test_compare_rejects_unknown_file(tmp_path):
    out = make_index(tmp_path)
    with pytest.raises(V4SearchError) as exc:
        compare_clause_items(
            out, "RW.LABOR.NO_VIOLATION", ["a" * 16, "z" * 16]
        )
    assert exc.value.code == "FILE_NOT_FOUND"


def test_search_pagination_reports_full_totals(tmp_path):
    out = make_index(tmp_path)
    first = search_clause_items(
        out, "RW.LABOR.NO_VIOLATION", limit=1, offset=0
    )
    assert first["total_items"] == 1
    assert first["returned_items"] == 1
    assert first["has_more"] is False
