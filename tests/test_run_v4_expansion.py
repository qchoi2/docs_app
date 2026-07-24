import sqlite3
from contextlib import closing

from lib.catalog import initialize_catalog
from run_v4_expansion import select_expansion
from v4_schema import initialize_v4_schema


def test_selection_prioritizes_spa_and_deduplicates(tmp_path):
    out = tmp_path / "cs_index"
    db = initialize_catalog(out / "catalog.sqlite")
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("DROP TABLE IF EXISTS doc_meta")
        conn.execute(
            "CREATE TABLE doc_meta(file_key TEXT PRIMARY KEY,txt_hash TEXT)"
        )
        for index, (ctype, lang, group) in enumerate(
            [
                ("SPA", "국문", "g1"),
                ("SPA", "국문", "g1"),
                ("SPA", "영문", "g2"),
                ("SSA", "국문", "g3"),
            ]
        ):
            key = f"{index:016x}"
            conn.execute(
                """
                INSERT INTO files(
                  file_key,path,folder,filename,ctype,lang,ext,size,mtime,
                  txt_path,char_count,status,source_signals,batch_label,
                  content_hash,dup_group,indexed_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    key, f"{key}.docx", "", f"{key}.docx", ctype, lang,
                    ".docx", 1, 1, f"txt/{key}.txt", 10, "ok", "{}",
                    "full", key, group, "2026-07-24T00:00:00Z",
                ),
            )
            conn.execute("INSERT INTO doc_meta VALUES (?,?)", (key, key))
        initialize_v4_schema(conn)
        selected, summary = select_expansion(conn, target=2)
    assert len(selected) == 2
    assert {row["ctype"] for row in selected} == {"SPA"}
    assert {row["dup_group"] for row in selected} == {"g1", "g2"}
    assert summary["selected_by_type"] == {"SPA": 2}


def test_selection_moves_to_next_type_when_spa_exhausted(tmp_path):
    out = tmp_path / "cs_index"
    db = initialize_catalog(out / "catalog.sqlite")
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("DROP TABLE IF EXISTS doc_meta")
        conn.execute(
            "CREATE TABLE doc_meta(file_key TEXT PRIMARY KEY,txt_hash TEXT)"
        )
        for index, ctype in enumerate(("SPA", "SSA")):
            key = f"{index:016x}"
            conn.execute(
                """
                INSERT INTO files(
                  file_key,path,folder,filename,ctype,lang,ext,size,mtime,
                  txt_path,char_count,status,source_signals,batch_label,
                  content_hash,dup_group,indexed_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    key, f"{key}.docx", "", f"{key}.docx", ctype, "국문",
                    ".docx", 1, 1, f"txt/{key}.txt", 10, "ok", "{}",
                    "full", key, key, "2026-07-24T00:00:00Z",
                ),
            )
            conn.execute("INSERT INTO doc_meta VALUES (?,?)", (key, key))
        initialize_v4_schema(conn)
        selected, summary = select_expansion(conn, target=2)
    assert [row["ctype"] for row in selected] == ["SPA", "SSA"]
    assert summary["selected_by_type"] == {"SPA": 1, "SSA": 1}
