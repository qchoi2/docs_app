import sqlite3

from lib.db_guard import integrity_warnings, risky_out_path_warnings


def test_clean_local_path_has_no_warning(tmp_path):
    assert risky_out_path_warnings(tmp_path / "cs_index") == []


def test_sync_folder_path_warns():
    warnings = risky_out_path_warnings("C:\\Users\\me\\OneDrive\\cs_index")
    assert len(warnings) == 1
    assert "sync_folder" in warnings[0]


def test_network_share_path_warns():
    warnings = risky_out_path_warnings("\\\\server\\share\\cs_index")
    assert any("network_share" in w for w in warnings)


def test_integrity_ok_for_healthy_db(tmp_path):
    db = tmp_path / "catalog.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    conn.executemany("INSERT INTO t (v) VALUES (?)", [(str(i),) for i in range(50)])
    conn.commit()
    conn.close()
    assert integrity_warnings(db) == []


def test_integrity_missing_db_is_silent(tmp_path):
    assert integrity_warnings(tmp_path / "does_not_exist.sqlite") == []


def test_integrity_detects_truncated_db(tmp_path):
    db = tmp_path / "catalog.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    conn.executemany("INSERT INTO t (v) VALUES (?)", [(str(i) * 200,) for i in range(2000)])
    conn.commit()
    conn.close()
    # Simulate the observed corruption: keep the SQLite header, drop most pages.
    size = db.stat().st_size
    with open(db, "r+b") as handle:
        handle.truncate(size // 4)
    warnings = integrity_warnings(db)
    assert warnings
    assert "RECOVERY_20260712.md" in warnings[0]
