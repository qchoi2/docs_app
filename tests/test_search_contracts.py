import json
import sqlite3
from contextlib import closing
from pathlib import Path

from lib.catalog import initialize_catalog
from search_contracts import escape_fts_phrase, main, search_contracts


def insert_doc(
    conn,
    file_key,
    path,
    content,
    *,
    ctype="SPA",
    lang="국문",
    dup_group=None,
    is_draft=None,
    version_hint=None,
):
    dup_group = dup_group or file_key
    conn.execute(
        """
        INSERT INTO files (
          file_key, path, folder, filename, ctype, lang, ext, size, mtime,
          txt_path, char_count, status, error_reason, source_signals,
          batch_label, content_hash, dup_group, is_draft, version_hint, indexed_at
        )
        VALUES (?, ?, '', ?, ?, ?, '.docx', 1, 1, ?, ?, 'ok', NULL, '{}',
          'test', ?, ?, ?, ?, '2026-07-10T00:00:00+00:00')
        """,
        (
            file_key,
            path,
            path,
            ctype,
            lang,
            f"txt/{file_key}.txt",
            len(content),
            file_key,
            dup_group,
            is_draft,
            version_hint,
        ),
    )
    for index, paragraph in enumerate(content.split("\n"), start=1):
        conn.execute(
            "INSERT INTO fts(content, file_key, para) VALUES (?, ?, ?)",
            (paragraph, file_key, index),
        )


def make_search_db(tmp_path):
    out = tmp_path / "cs_index"
    db_path = initialize_catalog(out / "catalog.sqlite")
    return out, db_path


def test_exact_search_ranks_above_expanded_search(tmp_path):
    out, db_path = make_search_db(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        insert_doc(conn, "exact", "exact.docx", "손해배상 조항")
        insert_doc(conn, "expanded", "expanded.docx", "면책 조항")
        conn.commit()

    result, count = search_contracts(out, keywords=["손해배상"])

    assert count == 2
    assert result["results"][0]["file_key"] == "exact"
    assert result["results"][0]["score_breakdown"]["exact_rank"] == 1
    assert result["results"][0]["matched_terms"][0]["canonical"] == "손해배상"
    assert result["results"][1]["file_key"] == "expanded"
    assert result["results"][1]["score_breakdown"]["expanded_rank"] == 1


def test_short_korean_term_uses_like_fallback(tmp_path):
    out, db_path = make_search_db(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        insert_doc(conn, "short", "short.docx", "계약 해제 조항")
        conn.commit()

    result, count = search_contracts(out, keywords=["해제"], no_expand=True)

    assert count == 1
    assert result["results"][0]["file_key"] == "short"
    assert "short_term_fallback:해제" in result["warnings"]


def test_fts_phrase_escapes_hyphen_quotes_and_boolean_words(tmp_path):
    out, db_path = make_search_db(tmp_path)
    special = 'earn-out AND OR "quoted"'
    with closing(sqlite3.connect(db_path)) as conn:
        insert_doc(conn, "special", "special.docx", special)
        conn.commit()

    assert escape_fts_phrase(special) == '"earn-out AND OR ""quoted"""'
    result, count = search_contracts(out, keywords=[special], no_expand=True)

    assert count == 1
    assert result["results"][0]["file_key"] == "special"


def test_dedup_default_and_show_duplicates(tmp_path):
    out, db_path = make_search_db(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        insert_doc(conn, "final", "final.docx", "손해배상", dup_group="dup", is_draft=0, version_hint="final")
        insert_doc(conn, "draft", "draft.docx", "손해배상", dup_group="dup", is_draft=1)
        conn.commit()

    deduped, _ = search_contracts(out, keywords=["손해배상"], no_expand=True)
    expanded, _ = search_contracts(out, keywords=["손해배상"], no_expand=True, show_duplicates=True)

    assert deduped["total"] == 1
    assert deduped["total_files"] == 2
    assert deduped["results"][0]["file_key"] == "final"
    assert deduped["results"][0]["dup_count"] == 2
    assert expanded["total"] == 2


def test_repeated_kw_is_and_condition(tmp_path):
    out, db_path = make_search_db(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        insert_doc(conn, "both", "both.docx", "손해배상\n진술보장")
        insert_doc(conn, "one", "one.docx", "손해배상")
        conn.commit()

    result, count = search_contracts(out, keywords=["손해배상", "진술보장"], no_expand=True)

    assert count == 1
    assert result["results"][0]["file_key"] == "both"


def test_exclude_drafts_removes_only_true_drafts(tmp_path):
    out, db_path = make_search_db(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        insert_doc(conn, "draft", "draft.docx", "손해배상", is_draft=1)
        insert_doc(conn, "unknown", "unknown.docx", "손해배상", is_draft=None)
        conn.commit()

    result, count = search_contracts(out, keywords=["손해배상"], no_expand=True, exclude_drafts=True, show_duplicates=True)

    assert count == 1
    assert result["results"][0]["file_key"] == "unknown"


def test_strict_expand_uses_canonical_only(tmp_path):
    out, db_path = make_search_db(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        insert_doc(conn, "expanded", "expanded.docx", "면책 조항")
        conn.commit()

    strict_result, strict_count = search_contracts(out, keywords=["손해배상"], expand="strict")
    normal_result, normal_count = search_contracts(out, keywords=["손해배상"], expand="normal")

    assert strict_count == 0
    assert normal_count == 1
    assert normal_result["results"][0]["file_key"] == "expanded"
    assert strict_result["query"]["expanded"]["손해배상"] == []


def test_json_schema_and_query_log(tmp_path, capsys):
    out, db_path = make_search_db(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        insert_doc(conn, "schema", "schema.docx", "손해배상")
        conn.commit()

    rc = main(["--out", str(out), "--kw", "손해배상", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert set(["query", "total", "total_files", "results", "warnings"]).issubset(payload)
    item = payload["results"][0]
    assert set(["why", "score_breakdown", "snippet_paras", "matched_terms"]).issubset(item)
    assert (out / "query_log.jsonl").exists()
    log_line = json.loads((out / "query_log.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert log_line["result_count"] == payload["total"]


def test_snippet_context_includes_surrounding_paragraphs(tmp_path):
    out, db_path = make_search_db(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        insert_doc(conn, "ctx", "ctx.docx", "first\n손해배상\nthird\nfourth")
        conn.commit()

    result, count = search_contracts(out, keywords=["손해배상"], no_expand=True, context=1)

    assert count == 1
    item = result["results"][0]
    assert item["snippet_paras"] == [1, 2, 3]
    assert "[¶1] first" in item["snippet"]
    assert "[¶2] 손해배상" in item["snippet"]
    assert "[¶3] third" in item["snippet"]


def test_expanded_rrf_uses_best_rank_per_source_not_variant_count(tmp_path):
    out, db_path = make_search_db(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        insert_doc(conn, "exact", "exact.docx", "손해배상")
        insert_doc(conn, "many_variants", "many.docx", "면책\nindemnity\nindemnification")
        conn.commit()

    result, count = search_contracts(out, keywords=["손해배상"])

    assert count == 2
    assert result["results"][0]["file_key"] == "exact"
    assert result["results"][1]["file_key"] == "many_variants"


def test_no_results_is_not_error(tmp_path, capsys):
    out, db_path = make_search_db(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        insert_doc(conn, "other", "other.docx", "손해배상")
        conn.commit()

    rc = main(["--out", str(out), "--kw", "존재하지않는검색어", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["total"] == 0
    assert payload["results"] == []


def test_missing_term_dict_warns_instead_of_silent_no_expansion(tmp_path, monkeypatch):
    import search_contracts as sc

    out, db_path = make_search_db(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        insert_doc(conn, "doc", "doc.docx", "손해배상")
        conn.commit()
    monkeypatch.setattr(sc, "TERM_DICT_PATHS", (Path("no_such_term_dict.yaml"),))

    result, count = sc.search_contracts(out, keywords=["손해배상"])

    assert count == 1
    assert "term_dict_not_found" in result["warnings"]
