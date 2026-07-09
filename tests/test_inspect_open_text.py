import json
import sqlite3
from contextlib import closing

from inspect_file import inspect_file, main as inspect_main
from lib.catalog import initialize_catalog
from open_text import main as open_text_main
from open_text import open_text


def make_db(tmp_path):
    out = tmp_path / "cs_index"
    db_path = initialize_catalog(out / "catalog.sqlite")
    (out / "txt").mkdir()
    return out, db_path


def insert_file(
    conn,
    file_key,
    *,
    path=None,
    ctype="SPA",
    lang="국문",
    status="ok",
    error_reason=None,
    source_signals='{"ctype": {"value": "SPA"}}',
    txt_path=None,
    content_hash=None,
    dup_group=None,
):
    path = path or f"{file_key}.docx"
    txt_path = txt_path or f"txt/{file_key}.txt"
    content_hash = content_hash or file_key
    dup_group = dup_group or file_key
    conn.execute(
        """
        INSERT INTO files (
          file_key, path, folder, filename, ctype, lang, ext, size, mtime,
          txt_path, char_count, status, error_reason, source_signals,
          batch_label, content_hash, dup_group, is_draft, version_hint, indexed_at
        )
        VALUES (?, ?, '', ?, ?, ?, '.docx', 1, 1, ?, 1, ?, ?, ?,
          'pilot', ?, ?, 0, 'final', '2026-07-10T00:00:00+00:00')
        """,
        (
            file_key,
            path,
            path,
            ctype,
            lang,
            txt_path,
            status,
            error_reason,
            source_signals,
            content_hash,
            dup_group,
        ),
    )


def write_txt(out, file_key, paragraphs):
    lines = [f"[¶{index}]\t{text}" for index, text in enumerate(paragraphs, start=1)]
    (out / "txt" / f"{file_key}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_inspect_file_key_lookup_includes_metadata_dup_and_doc_meta_slot(tmp_path):
    out, db_path = make_db(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        insert_file(conn, "target", status="error", error_reason="docx_extract_failed", dup_group="dup")
        insert_file(conn, "sibling", path="copy.docx", dup_group="dup")
        conn.execute(
            """
            INSERT INTO doc_meta(file_key, meta_schema_version, txt_hash, extracted_at, json, confidence)
            VALUES ('target', 1, 'old_hash', '2026-07-10T00:00:00+00:00', '{}', 'high')
            """
        )
        conn.commit()

    result = inspect_file(out, "target", show_dup_group=True)

    assert result["file_key"] == "target"
    assert result["ctype"] == "SPA"
    assert result["lang"] == "국문"
    assert result["status"] == "error"
    assert result["error_reason"] == "docx_extract_failed"
    assert result["source_signals"]["ctype"]["value"] == "SPA"
    assert result["dup_group"]["id"] == "dup"
    assert result["dup_group"]["count"] == 2
    assert {member["file_key"] for member in result["dup_group"]["members"]} == {"target", "sibling"}
    assert result["doc_meta"]["present"] is True
    assert result["doc_meta"]["stale"] is True


def test_open_text_outputs_surrounding_paragraphs_only(tmp_path):
    out, db_path = make_db(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        insert_file(conn, "doc")
        conn.commit()
    write_txt(out, "doc", ["one", "two", "three", "four", "five"])

    result = open_text(out, "doc", para=3, context=1)

    assert result["matched_para"] == 3
    assert result["paragraphs"] == [
        {"para": 2, "text": "two"},
        {"para": 3, "text": "three"},
        {"para": 4, "text": "four"},
    ]


def test_open_text_search_outputs_first_match_window(tmp_path):
    out, db_path = make_db(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        insert_file(conn, "doc")
        conn.commit()
    write_txt(out, "doc", ["alpha", "손해배상 조항", "beta", "손해배상 반복"])

    result = open_text(out, "doc", search="손해배상", context=1)

    assert result["mode"] == "search"
    assert result["matched_para"] == 2
    assert result["paragraphs"] == [
        {"para": 1, "text": "alpha"},
        {"para": 2, "text": "손해배상 조항"},
        {"para": 3, "text": "beta"},
    ]


def test_cli_json_for_inspect_and_open_text(tmp_path, capsys):
    out, db_path = make_db(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        insert_file(conn, "doc")
        conn.commit()
    write_txt(out, "doc", ["alpha", "beta"])

    inspect_rc = inspect_main(["--out", str(out), "--file-key", "doc", "--json"])
    inspect_payload = json.loads(capsys.readouterr().out)
    open_rc = open_text_main(["--out", str(out), "--file-key", "doc", "--para", "1", "--context", "0", "--json"])
    open_payload = json.loads(capsys.readouterr().out)

    assert inspect_rc == 0
    assert inspect_payload["file_key"] == "doc"
    assert open_rc == 0
    assert open_payload["paragraphs"] == [{"para": 1, "text": "alpha"}]
