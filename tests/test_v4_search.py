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


def test_verified_rw_subdomain_confirms_absent(tmp_path, monkeypatch):
    # Once a sub-domain passes re-verification it joins ABSENCE_VERIFIED_SUBDOMAINS
    # and may confirm absence again (the 선(先)해제 exception, V4_PLAN §9.1 #3).
    import v4_search
    monkeypatch.setattr(v4_search, "ABSENCE_VERIFIED_SUBDOMAINS", {"RW.LABOR"})
    out = make_index(tmp_path)
    result = search_clause_absence(out, "RW.LABOR.NO_VIOLATION")
    # doc b: complete RW coverage, no labor item -> now confirmed_absent, not gated.
    assert [row["file_key"] for row in result["confirmed_absent"]] == ["b" * 16]
    assert "rw_absence_unverified_demoted_to_needs_review" not in result["warnings"]


def test_unverified_rw_subdomain_stays_gated(tmp_path, monkeypatch):
    # Verifying one sub-domain must NOT open the others: a query on a still-unverified
    # RW sub-domain is demoted to needs_review as before.
    import v4_search
    monkeypatch.setattr(v4_search, "ABSENCE_VERIFIED_SUBDOMAINS", {"RW.LABOR"})
    out = make_index(tmp_path)
    result = search_clause_absence(out, "RW.TAX")
    assert result["confirmed_absent"] == []
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


def _seed_text_ranking_items(out):
    """Three items in one node, one per document, all matching the needle
    '인허가 취득' but with different match quality:
      c(=verbatim prefix) beats a(=verbatim, later position) beats b(=proposition only).
    Document/file_key order (a<b<c) is the OPPOSITE, so a correct relevance sort
    must override the enumeration order."""
    needle_docs = [
        # (file_key, verbatim, proposition, loc_start)
        ("a" * 16, "매도인은 계약상 인허가 취득 의무를 부담한다 추가 문구로 길게 늘림", "동의 관련", 21),
        ("b" * 16, "제3자 동의가 필요하다", "인허가 취득 관련 동의 명제", 22),
        ("c" * 16, "인허가 취득 특약의 세부", "특약 명제", 23),
    ]
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        for i, (fk, verbatim, prop, loc) in enumerate(needle_docs):
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
                (fk, f"CPX-{i}", "CP", "CP.THIRD_PARTY_CONSENT", prop, "affirmative",
                 verbatim, loc, loc, fk, NOW, NOW),
            )
        conn.commit()


def test_text_query_ranks_by_match_quality_over_file_key(tmp_path):
    out = make_index(tmp_path)
    _seed_text_ranking_items(out)
    result = search_clause_items(
        out, "CP.THIRD_PARTY_CONSENT", text="인허가 취득", show_duplicates=True, limit=10
    )
    order = [row["file_key"] for row in result["results"]]
    # bm25 ranks the focused item (c: both terms in a short verbatim) first — the item
    # that sorts LAST alphabetically, so relevance provably beats the file_key
    # enumeration order (a < b < c). The exact tail order is bm25-specific.
    assert order[0] == "c" * 16
    assert order != sorted(order)
    assert set(order) == {"a" * 16, "b" * 16, "c" * 16}


def test_concept_query_keeps_stable_enumeration_order(tmp_path):
    # No text signal -> the enumeration order (file_key, ¶) is preserved, so
    # compare/count queries stay deterministic and unaffected by the change.
    out = make_index(tmp_path)
    _seed_text_ranking_items(out)
    result = search_clause_items(
        out, "CP.THIRD_PARTY_CONSENT", show_duplicates=True, limit=10
    )
    keys = [row["file_key"] for row in result["results"]]
    assert keys == sorted(keys)


def test_multi_keyword_text_query_ands_scattered_tokens(tmp_path):
    # "인허가 위약벌" as two keywords: only the item carrying BOTH (scattered, not
    # contiguous) matches. The old single-substring filter needed them adjacent and
    # would have returned 0 for this common keyword-style query.
    out = make_index(tmp_path)
    seeds = [
        ("a" * 16, "매도인은 인허가 취득 위반 시 위약벌을 부담한다", "위반 제재 명제"),  # both -> match
        ("b" * 16, "인허가 취득 관련 동의가 필요하다", "동의 명제"),              # 인허가 only
        ("c" * 16, "위약벌 관련 조항 없음", "제재 명제"),                      # 위약벌 only
    ]
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        for i, (fk, verbatim, prop) in enumerate(seeds):
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
                (fk, f"CPK-{i}", "CP", "CP.THIRD_PARTY_CONSENT", prop, "affirmative",
                 verbatim, 30, 30, fk, NOW, NOW),
            )
        conn.commit()
    result = search_clause_items(
        out, "CP.THIRD_PARTY_CONSENT", text="인허가 위약벌", show_duplicates=True, limit=10
    )
    keys = [row["file_key"] for row in result["results"]]
    assert keys == ["a" * 16]
    assert result["total_items"] == 1


def test_low_query_signal_hint_on_broad_concept_query(tmp_path, monkeypatch):
    # A bare concept query over a population above the threshold gets a machine-readable
    # hint so an agent re-queries with keywords; a text-narrowed query never does.
    import v4_search
    monkeypatch.setattr(v4_search, "LOW_SIGNAL_POPULATION", 1)
    out = make_index(tmp_path)
    _seed_text_ranking_items(out)  # -> several CP.THIRD_PARTY_CONSENT items
    broad = search_clause_items(out, "CP.THIRD_PARTY_CONSENT", show_duplicates=True)
    assert broad["total_items"] > 1
    assert "low_query_signal" in broad
    assert broad["low_query_signal"]["population"] == broad["total_items"]
    narrowed = search_clause_items(
        out, "CP.THIRD_PARTY_CONSENT", text="인허가", show_duplicates=True
    )
    assert "low_query_signal" not in narrowed
    # lang/ctype only shrink the file set without ranking it, so they must NOT
    # suppress the hint — the ranking signal is text/subject/polarity.
    lang_only = search_clause_items(
        out, "CP.THIRD_PARTY_CONSENT", lang="국문", show_duplicates=True
    )
    assert "low_query_signal" in lang_only


def test_zero_result_multi_keyword_gets_absence_safe_hint(tmp_path):
    # An AND text query that no item satisfies returns 0 — the response must flag that
    # 0 != absence so an agent re-queries instead of misreading it (project principle).
    out = make_index(tmp_path)
    _seed_text_ranking_items(out)
    result = search_clause_items(
        out, "CP.THIRD_PARTY_CONSENT", text="존재하지 않는키워드조합", show_duplicates=True
    )
    assert result["total_items"] == 0
    assert "zero_result_hint" in result
    assert result["zero_result_hint"]["tokens"] == ["존재하지", "않는키워드조합"]


def test_log_v4_query_appends_jsonl(tmp_path):
    import json as _json
    from v4_search import log_v4_query
    out = make_index(tmp_path)
    log_v4_query(out, {"tool": "search_clause_items", "has_text": False, "population": 42})
    lines = (out / "v4_query_log.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = _json.loads(lines[0])
    assert record["population"] == 42 and record["has_text"] is False
    assert "ts" in record  # timestamp is stamped by the logger
