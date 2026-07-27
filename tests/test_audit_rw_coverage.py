import sqlite3
from contextlib import closing

from audit_rw_coverage import audit, apply_reclassify
from tests.test_v4_search import make_index


def _add_rw_items(out, file_key, domains):
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        for i, dom in enumerate(domains):
            conn.execute(
                """
                INSERT INTO v4_clause_item(
                  file_key,item_ref,family,taxonomy_id,proposition,statement_polarity,
                  source_kind,verbatim,loc_start,loc_end,confidence,txt_hash,
                  taxonomy_version,extractor_version,prompt_version,review_status,
                  created_at,updated_at
                ) VALUES (?,?,?,?,?,'affirmative','body',?,?,?,'high',?,12,'t','t',
                          'approved','t','t')
                """,
                (file_key, f"X-{i}", "RW", f"{dom}.SUB", "p", "v", 1, 1, file_key),
            )
        conn.commit()


def test_audit_flags_underextracted_rw_docs(tmp_path):
    out = make_index(tmp_path)  # docs a,b,c have RW complete/complete/partial
    # doc a: rich (7 core sub-domains) -> not flagged
    _add_rw_items(out, "a" * 16, [
        "RW.TAX", "RW.LITIGATION", "RW.COMPLIANCE", "RW.CONTRACTS",
        "RW.LABOR", "RW.IP", "RW.ENVIRONMENT",
    ])
    # doc b: thin (1 core) -> flagged
    _add_rw_items(out, "b" * 16, ["RW.TAX"])
    report = audit(out, min_core=6)
    assert report["rw_complete_docs"] == 2  # a and b (c is partial)
    assert "b" * 16 in report["flagged_underextracted"]
    assert "a" * 16 not in report["flagged_underextracted"]
    assert report["core_domain_doc_coverage"]["RW.TAX"]["docs"] == 2


def test_apply_reclassifies_flagged_to_partial(tmp_path):
    out = make_index(tmp_path)
    _add_rw_items(out, "b" * 16, ["RW.TAX"])  # thin -> flagged
    report = audit(out, min_core=6)
    changed = apply_reclassify(out, report["flagged_underextracted"])
    assert changed >= 1
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        status = conn.execute(
            "SELECT body_status,reason FROM v4_document_coverage "
            "WHERE family='RW' AND file_key=?",
            ("b" * 16,),
        ).fetchone()
    assert status[0] == "partial"
    assert "rw_subdomain_audit_pending" in status[1]
