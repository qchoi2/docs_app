import sqlite3
from contextlib import closing

from plan_rw_reextraction import plan
from tests.test_v4_search import make_index


def test_plan_lists_audit_flagged_docs_with_missing_subdomains(tmp_path):
    out = make_index(tmp_path)
    # mark doc b's RW coverage as audit-flagged (as audit --apply would)
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        conn.execute(
            "UPDATE v4_document_coverage SET reason='x | rw_subdomain_audit_pending' "
            "WHERE family='RW' AND file_key=?",
            ("b" * 16,),
        )
        conn.commit()
    rows = plan(out)
    keys = [r["file_key"] for r in rows]
    assert "b" * 16 in keys
    row = next(r for r in rows if r["file_key"] == "b" * 16)
    # doc b has no RW items -> all core sub-domains missing
    assert "RW.IP" in row["missing_subdomains"]
    assert row["present_subdomains"] == []
    assert row["ctype"] == "SPA"
