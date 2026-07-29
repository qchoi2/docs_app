"""A wrong --out must fail loudly, never mint an empty second catalog.

Root cause (2026-07-29): a bare ``sqlite3.connect('catalog.sqlite')`` run from
the repo root left a 0-byte catalog.sqlite next to the real 1.7 GB
cs_index/catalog.sqlite, and the caller then read an "empty corpus".
"""

import sqlite3

import pytest

from lib.catalog import (
    CatalogError,
    CatalogNotFoundError,
    catalog_path,
    connect_catalog,
    initialize_catalog,
    require_catalog,
)


def test_require_catalog_rejects_a_missing_file(tmp_path):
    missing = tmp_path / "catalog.sqlite"
    with pytest.raises(CatalogNotFoundError) as excinfo:
        require_catalog(missing)
    message = str(excinfo.value)
    assert "색인 DB가 없습니다" in message
    assert "--out" in message
    assert str(missing) in message
    assert not missing.exists()  # the check itself must not create it


def test_require_catalog_rejects_a_zero_byte_stray(tmp_path):
    stray = tmp_path / "catalog.sqlite"
    stray.touch()
    with pytest.raises(CatalogNotFoundError) as excinfo:
        require_catalog(stray)
    assert "0바이트" in str(excinfo.value)


def test_require_catalog_rejects_a_directory(tmp_path):
    as_dir = tmp_path / "catalog.sqlite"
    as_dir.mkdir()
    with pytest.raises(CatalogNotFoundError):
        require_catalog(as_dir)


def test_require_catalog_accepts_a_real_catalog(tmp_path):
    db = initialize_catalog(catalog_path(tmp_path))
    assert require_catalog(db) == db


def test_catalog_not_found_is_also_a_file_not_found_error(tmp_path):
    # webapp.py / mcp_server.py catch FileNotFoundError; keep them working.
    with pytest.raises(FileNotFoundError):
        require_catalog(tmp_path / "catalog.sqlite")
    assert issubclass(CatalogNotFoundError, CatalogError)


def test_connect_catalog_does_not_create_a_missing_database(tmp_path):
    missing = catalog_path(tmp_path)
    with pytest.raises(CatalogNotFoundError):
        connect_catalog(missing)
    assert not missing.exists()


def test_connect_catalog_read_only_does_not_create_either(tmp_path):
    missing = catalog_path(tmp_path)
    with pytest.raises(CatalogNotFoundError):
        connect_catalog(missing, read_only=True)
    assert not missing.exists()


def test_connect_catalog_create_still_allows_the_build_path(tmp_path):
    # index_contracts.py / init_v4_schema.py must keep being able to create.
    db = catalog_path(tmp_path)
    with connect_catalog(db, create=True) as conn:
        conn.execute("CREATE TABLE t (id INTEGER)")
    assert db.exists() and db.stat().st_size > 0


def test_initialize_catalog_is_unaffected(tmp_path):
    db = initialize_catalog(catalog_path(tmp_path))
    with sqlite3.connect(db) as conn:
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "files" in names


def test_search_contracts_refuses_a_bad_out(tmp_path):
    from search_contracts import search_contracts
    with pytest.raises(CatalogNotFoundError):
        search_contracts(out=tmp_path, ctype="SPA")
    assert not catalog_path(tmp_path).exists()


def test_connect_search_db_refuses_a_bad_path(tmp_path):
    from search_contracts import connect_search_db
    missing = catalog_path(tmp_path)
    with pytest.raises(CatalogNotFoundError):
        connect_search_db(missing, read_only=True)
    with pytest.raises(CatalogNotFoundError):
        connect_search_db(missing)
    assert not missing.exists()


def test_v4_search_reports_catalog_not_found(tmp_path):
    from v4_search import V4SearchError, connect_v4_ro
    with pytest.raises(V4SearchError) as excinfo:
        connect_v4_ro(tmp_path)
    assert excinfo.value.code == "CATALOG_NOT_FOUND"
    assert "색인 DB가 없습니다" in str(excinfo.value)
    assert not catalog_path(tmp_path).exists()


def test_v4_search_reports_a_zero_byte_stray(tmp_path):
    from v4_search import V4SearchError, connect_v4_ro
    catalog_path(tmp_path).touch()
    with pytest.raises(V4SearchError) as excinfo:
        connect_v4_ro(tmp_path)
    assert excinfo.value.code == "CATALOG_NOT_FOUND"


def test_taxonomy_admin_refuses_a_bad_out(tmp_path):
    from taxonomy_admin import connect_admin
    with pytest.raises(CatalogNotFoundError):
        connect_admin(tmp_path)
    assert not catalog_path(tmp_path).exists()
