import json
import sqlite3
from contextlib import closing

from lib.catalog import initialize_catalog
from stats_contracts import build_stats, main


def make_stats_db(tmp_path):
    out = tmp_path / "cs_index"
    db_path = initialize_catalog(out / "catalog.sqlite")
    return out, db_path


def insert_file(
    conn,
    file_key,
    *,
    ctype="SPA",
    lang="국문",
    status="ok",
    error_reason=None,
    batch_label="pilot",
    dup_group=None,
    is_draft=0,
    version_hint="final",
):
    dup_group = dup_group or file_key
    conn.execute(
        """
        INSERT INTO files (
          file_key, path, folder, filename, ctype, lang, ext, size, mtime,
          txt_path, char_count, status, error_reason, source_signals,
          batch_label, content_hash, dup_group, is_draft, version_hint, indexed_at
        )
        VALUES (?, ?, '', ?, ?, ?, '.docx', 1, 1, ?, 1, ?, ?, '{}',
          ?, ?, ?, ?, ?, '2026-07-10T00:00:00+00:00')
        """,
        (
            file_key,
            f"{file_key}.docx",
            f"{file_key}.docx",
            ctype,
            lang,
            f"txt/{file_key}.txt",
            status,
            error_reason,
            batch_label,
            file_key,
            dup_group,
            is_draft,
            version_hint,
        ),
    )


def by_values(payload, section):
    return {(row.get("ctype"), row.get("lang")): row["count"] for row in payload["by"][section]}


def test_by_ctype_lang_separates_ok_counts_from_all_counts(tmp_path):
    out, db_path = make_stats_db(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        insert_file(conn, "spa_ok", ctype="SPA", lang="국문", status="ok")
        insert_file(conn, "sha_ok", ctype="SHA", lang="영문", status="ok")
        insert_file(conn, "spa_empty", ctype="SPA", lang="영문", status="empty", error_reason="pdf_text_empty")
        conn.commit()

    stats = build_stats(out, by="ctype,lang", include_status=True)

    assert by_values(stats, "ok") == {("SHA", "영문"): 1, ("SPA", "국문"): 1}
    assert by_values(stats, "all") == {
        ("SHA", "영문"): 1,
        ("SPA", "국문"): 1,
        ("SPA", "영문"): 1,
    }
    assert stats["status"]["ok"] == 2
    assert stats["status"]["empty"] == 1


def test_dedup_counts_duplicate_groups_by_representative(tmp_path):
    out, db_path = make_stats_db(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        insert_file(conn, "spa_final", ctype="SPA", dup_group="dup", is_draft=0, version_hint="final")
        insert_file(conn, "spa_draft", ctype="SPA", dup_group="dup", is_draft=1, version_hint=None)
        insert_file(conn, "sha_one", ctype="SHA")
        conn.commit()

    raw = build_stats(out, by="ctype")
    deduped = build_stats(out, by="ctype", include_dedup=True, dedup=True)

    assert {row["ctype"]: row["count"] for row in raw["by"]["ok"]} == {"SPA": 2, "SHA": 1}
    assert {row["ctype"]: row["count"] for row in deduped["by"]["ok"]} == {"SPA": 1, "SHA": 1}
    assert deduped["dedup_summary"]["ok_files"] == 3
    assert deduped["dedup_summary"]["ok_groups"] == 2
    assert deduped["dedup_summary"]["duplicate_groups"] == [
        {"dup_group": "dup", "count": 2, "ok_count": 2}
    ]


def test_cli_outputs_status_errors_batches_and_dedup_json(tmp_path, capsys):
    out, db_path = make_stats_db(tmp_path)
    with closing(sqlite3.connect(db_path)) as conn:
        insert_file(conn, "ok", status="ok", batch_label="pilot")
        insert_file(conn, "err", status="error", error_reason="docx_extract_failed", batch_label="full")
        conn.commit()

    rc = main(
        [
            "--out",
            str(out),
            "--status",
            "--errors",
            "--batches",
            "--dedup",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["status"]["ok"] == 1
    assert payload["errors"] == [{"count": 1, "value": "docx_extract_failed"}]
    assert {row["value"]: row["count"] for row in payload["batches"]} == {"full": 1, "pilot": 1}
    assert payload["dedup"] is True
    assert payload["dedup_summary"]["total_groups"] == 2
