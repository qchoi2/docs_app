import json
import sqlite3
from contextlib import closing

from lib.catalog import initialize_catalog
from read_contract import read_contract


def make_db(tmp_path):
    out = tmp_path / "cs_index"
    db_path = initialize_catalog(out / "catalog.sqlite")
    (out / "txt").mkdir()
    return out, db_path


def insert_file(conn, file_key, content_hash="hash1"):
    conn.execute(
        """
        INSERT INTO files (
          file_key, path, folder, filename, ctype, lang, ext, size, mtime,
          txt_path, char_count, status, error_reason, source_signals,
          batch_label, content_hash, dup_group, is_draft, version_hint, indexed_at
        )
        VALUES (?, ?, '', ?, 'SPA', '국문', '.docx', 1, 1, ?, 1, 'ok', NULL, '{}',
          'pilot', ?, ?, 0, 'final', '2026-07-12T00:00:00+00:00')
        """,
        (
            file_key,
            "%s.docx" % file_key,
            "%s.docx" % file_key,
            "txt/%s.txt" % file_key,
            content_hash,
            file_key,
        ),
    )


def write_txt(out, file_key, paragraphs):
    lines = ["[\u00b6%d]\t%s" % (index, text) for index, text in enumerate(paragraphs, start=1)]
    (out / "txt" / ("%s.txt" % file_key)).write_text("\n".join(lines) + "\n", encoding="utf-8")


def insert_meta(conn, file_key, clause_map, txt_hash="hash1"):
    conn.execute(
        """
        INSERT INTO doc_meta (
          file_key, meta_schema_version, txt_hash, extracted_at,
          clause_map_json, json, confidence
        )
        VALUES (?, 1, ?, '2026-07-12T00:00:00+00:00', ?, '{}', 'high')
        """,
        (file_key, txt_hash, json.dumps(clause_map, ensure_ascii=False, sort_keys=True)),
    )


def test_read_contract_outputs_exact_clause_range_with_normalized_section(tmp_path):
    out, db_path = make_db(tmp_path)
    file_key = "doc1"
    with closing(sqlite3.connect(db_path)) as conn:
        insert_file(conn, file_key)
        insert_meta(
            conn,
            file_key,
            {
                "손해배상": {
                    "present": True,
                    "loc_start": 2,
                    "loc_end": 3,
                    "summary": "sample",
                }
            },
        )
        conn.commit()
    write_txt(out, file_key, ["intro", "indemnity one", "indemnity two", "tail"])

    result = read_contract(out, file_key, "indemnity")

    assert result["status"] == "ok"
    assert result["canonical_section"] == "손해배상"
    assert result["loc_start"] == 2
    assert result["loc_end"] == 3
    assert result["paragraphs"] == [
        {"para": 2, "text": "indemnity one"},
        {"para": 3, "text": "indemnity two"},
    ]


def test_read_contract_distinguishes_unevaluated_and_absent(tmp_path):
    out, db_path = make_db(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        insert_file(conn, "unevaluated")
        insert_meta(conn, "unevaluated", {"진술보장": {"present": True, "loc_start": 1, "loc_end": 1}})
        insert_file(conn, "absent")
        insert_meta(conn, "absent", {"손해배상": {"present": False, "summary": "not found"}})
        conn.commit()
    write_txt(out, "unevaluated", ["one"])
    write_txt(out, "absent", ["one"])

    unevaluated = read_contract(out, "unevaluated", "손해배상")
    absent = read_contract(out, "absent", "손해배상")

    assert unevaluated["status"] == "unevaluated"
    assert unevaluated["status_label"] == "미평가"
    assert absent["status"] == "absent"
    assert absent["status_label"] == "평가 후 부재"
    assert absent["paragraphs"] == []


def test_read_contract_marks_stale_metadata(tmp_path):
    out, db_path = make_db(tmp_path)
    file_key = "stale"
    with closing(sqlite3.connect(db_path)) as conn:
        insert_file(conn, file_key, content_hash="new_hash")
        insert_meta(
            conn,
            file_key,
            {"손해배상": {"present": True, "loc_start": 1, "loc_end": 1}},
            txt_hash="old_hash",
        )
        conn.commit()
    write_txt(out, file_key, ["indemnity"])

    result = read_contract(out, file_key, "손해배상")

    assert result["status"] == "ok"
    assert result["stale"] is True
    assert result["stale_label"] == "재추출 전"
    assert result["paragraphs"] == [{"para": 1, "text": "indemnity"}]

