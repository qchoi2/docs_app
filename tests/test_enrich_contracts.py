import json
import sqlite3
from contextlib import closing

from enrich_contracts import enrich_contracts, load_txt_cache, select_candidates
from lib.catalog import initialize_catalog


def insert_doc(conn, out, file_key, path, content, *, ctype="SPA", dup_group=None, status="ok"):
    dup_group = dup_group or file_key
    txt_path = "txt/%s.txt" % file_key
    conn.execute(
        """
        INSERT INTO files (
          file_key, path, folder, filename, ctype, lang, ext, size, mtime,
          txt_path, char_count, status, error_reason, source_signals,
          batch_label, content_hash, dup_group, is_draft, version_hint, indexed_at
        )
        VALUES (?, ?, '', ?, ?, '국문', '.docx', 1, 1, ?, ?, ?, NULL, '{}',
          'test', ?, ?, 0, 'final', '2026-07-11T00:00:00+00:00')
        """,
        (file_key, path, path, ctype, txt_path, len(content), status, file_key, dup_group),
    )
    txt_file = out / "txt" / ("%s.txt" % file_key)
    txt_file.parent.mkdir(exist_ok=True)
    if status == "ok":
        txt_file.write_text(
            "\n".join(
                "[\u00b6%d]\t%s" % (index, paragraph)
                for index, paragraph in enumerate(content.split("\n"), start=1)
            ) + "\n",
            encoding="utf-8",
        )


def make_out(tmp_path):
    out = tmp_path / "cs_index"
    db_path = initialize_catalog(out / "catalog.sqlite")
    return out, db_path


def test_load_txt_cache_reads_paragraph_markers(tmp_path):
    out = tmp_path / "cs_index"
    txt_dir = out / "txt"
    txt_dir.mkdir(parents=True)
    (txt_dir / "sample.txt").write_text("[\u00b61]\tone\n[\u00b62]\t손해배상\n", encoding="utf-8")

    paragraphs = load_txt_cache(out, "txt/sample.txt")

    assert paragraphs == [
        {"para": 1, "text": "one"},
        {"para": 2, "text": "손해배상"},
    ]


def valid_result(file_key):
    return {
        "file_key": file_key,
        "meta_schema_version": 1,
        "parties_json": [],
        "deal_type_detail": "sample",
        "consideration_json": {},
        "clause_map_json": {
            "손해배상": {
                "present": True,
                "loc_start": 2,
                "loc_end": 3,
                "summary": "sample",
            }
        },
        "special_notes": "",
        "definitions_json": {},
        "confidence": "med",
    }


def test_select_candidates_uses_priority_and_dup_representative(tmp_path):
    out, db_path = make_out(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        insert_doc(conn, out, "sha", "b_sha.docx", "SHA", ctype="SHA")
        insert_doc(conn, out, "spa", "a_spa.docx", "SPA", ctype="SPA")
        insert_doc(conn, out, "dup2", "dup_member.docx", "DUP", ctype="SPA", dup_group="spa")
        insert_doc(conn, out, "empty", "empty.pdf", "", status="empty")
        conn.commit()
        candidates = select_candidates(conn)

    assert [item.file_key for item in candidates] == ["spa", "sha"]


def test_enrich_writes_input_and_records_result(tmp_path):
    out, db_path = make_out(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        insert_doc(conn, out, "a" * 16, "spa.docx", "intro\nindemnity\nend", ctype="SPA")
        conn.commit()
    result_dir = out / "enrich_results"
    result_dir.mkdir()
    (result_dir / ("%s.json" % ("a" * 16))).write_text(
        json.dumps(valid_result("a" * 16), ensure_ascii=False),
        encoding="utf-8",
    )

    result = enrich_contracts(out)

    assert result["processed"] == ["a" * 16]
    assert result["pending"] == []
    input_payload = json.loads((out / "enrich_inputs" / ("%s.json" % ("a" * 16))).read_text(encoding="utf-8"))
    assert input_payload["paragraphs"][1]["para"] == 2
    with closing(sqlite3.connect(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT file_key, meta_schema_version, txt_hash, confidence,
                   clause_map_json, json
            FROM doc_meta
            """
        ).fetchall()
    assert rows[0][0:4] == ("a" * 16, 1, "a" * 16, "med")
    clause_map = json.loads(rows[0][4])
    assert clause_map["손해배상"]["loc_start"] == 2
    stored = json.loads(rows[0][5])
    assert stored["clause_map_json"]["손해배상"]["loc_start"] == 2


def test_enrich_pending_then_incremental_skip_after_result(tmp_path):
    out, db_path = make_out(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        insert_doc(conn, out, "b" * 16, "spa.docx", "one", ctype="SPA")
        conn.commit()

    first = enrich_contracts(out)
    assert first["pending"] == ["b" * 16]
    result_dir = out / "enrich_results"
    result_dir.mkdir(exist_ok=True)
    (result_dir / ("%s.json" % ("b" * 16))).write_text(
        json.dumps(valid_result("b" * 16), ensure_ascii=False),
        encoding="utf-8",
    )
    second = enrich_contracts(out)
    third = enrich_contracts(out)

    assert second["processed"] == ["b" * 16]
    assert third["candidate_count"] == 0


def test_invalid_result_is_reported_without_commit(tmp_path):
    out, db_path = make_out(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        insert_doc(conn, out, "c" * 16, "spa.docx", "one", ctype="SPA")
        conn.commit()
    result_dir = out / "enrich_results"
    result_dir.mkdir()
    bad = valid_result("c" * 16)
    bad["confidence"] = "maybe"
    (result_dir / ("%s.json" % ("c" * 16))).write_text(
        json.dumps(bad, ensure_ascii=False),
        encoding="utf-8",
    )

    result = enrich_contracts(out)

    assert result["error_count"] == 1
    with closing(sqlite3.connect(db_path)) as conn:
        count = conn.execute("SELECT COUNT(*) FROM doc_meta").fetchone()[0]
    assert count == 0
