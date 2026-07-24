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
        for letter, body_status in (("a", "complete"), ("b", "complete"), ("c", "partial")):
            conn.execute(
                """
                INSERT INTO v4_document_coverage(
                  file_key,family,body_status,annex_status,txt_hash,
                  taxonomy_version,extractor_version,prompt_version,reviewed_at
                ) VALUES (?,?,?,'no_annex',?,12,'test','test',?)
                """,
                (letter * 16, "RW", body_status, letter * 16, NOW),
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


def test_absence_requires_complete_coverage(tmp_path):
    out = make_index(tmp_path)
    result = search_clause_absence(out, "RW.LABOR.NO_VIOLATION")
    assert [row["file_key"] for row in result["confirmed_absent"]] == ["b" * 16]
    assert [row["file_key"] for row in result["needs_review"]] == ["c" * 16]
    assert result["present_excluded_count"] == 1
    assert "body_partial" in result["needs_review"][0]["coverage"]["reasons"]


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
