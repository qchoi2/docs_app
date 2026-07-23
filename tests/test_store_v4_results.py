import json
import sqlite3

from store_v4_results import store_results
from v4_schema import initialize_v4_schema


def test_store_results_audits_and_persists_passed_document(tmp_path):
    out = tmp_path / "cs_index"
    out.mkdir()
    db = out / "catalog.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE files(file_key TEXT PRIMARY KEY, content_hash TEXT)"
        )
        conn.execute("INSERT INTO files VALUES ('doc1','hash1')")
        initialize_v4_schema(conn)
        conn.commit()

    input_dir = out / "enrich_inputs_v4"
    result_dir = out / "enrich_results_v4"
    input_dir.mkdir()
    result_dir.mkdir()
    source = {
        "file_key": "doc1",
        "family_sections": {
            "RW": {
                "paragraphs": [{"para": 10, "text": "노동관계법령을 위반한 사실이 없다."}],
                "atomic_unit_hints": [
                    {
                        "unit_id": "u-10",
                        "loc_start": 10,
                        "loc_end": 10,
                        "heading": "노동관계법령 위반 없음",
                    }
                ],
            },
            "CP": {"paragraphs": [], "atomic_unit_hints": []},
            "COV": {"paragraphs": [], "atomic_unit_hints": []},
            "DEF": {"paragraphs": [], "atomic_unit_hints": []},
            "PAY": {"paragraphs": [], "atomic_unit_hints": []},
            "REM": {"paragraphs": [], "atomic_unit_hints": []},
        },
        "source_inventory": [],
    }
    result = {
        "file_key": "doc1",
        "meta_schema_version": 4,
        "taxonomy_version": 2,
        "extractor_version": "test",
        "prompt_version": "v4-prompt-3",
        "coverage": {
            "RW": {"body_status": "complete", "annex_status": "no_annex", "reason": None},
            "CP": {"body_status": "not_evaluated", "annex_status": "not_evaluated", "reason": "입력 없음"},
            "COV": {"body_status": "not_evaluated", "annex_status": "not_evaluated", "reason": "입력 없음"},
            "DEF": {"body_status": "not_evaluated", "annex_status": "not_evaluated", "reason": "입력 없음"},
            "PAY": {"body_status": "not_evaluated", "annex_status": "not_evaluated", "reason": "입력 없음"},
            "REM": {"body_status": "not_evaluated", "annex_status": "not_evaluated", "reason": "입력 없음"},
        },
        "source_coverage": [],
        "items": [
            {
                "item_ref": "rw-001",
                "family": "RW",
                "taxonomy_id": "RW.LABOR.NO_VIOLATION",
                "proposition": "대상회사는 노동관계법령을 위반하지 않았다.",
                "statement_polarity": "none_exist",
                "subject_role": "대상회사",
                "counterparty_role": "매수인",
                "action": "진술",
                "object_type": "노동관계법령 위반",
                "effective_time": "계약체결일",
                "source_kind": "body",
                "source_id": None,
                "source_name": "계약서 본문",
                "source_ref": "¶10",
                "parent_clause_ref": None,
                "qualifier": {},
                "verbatim": "노동관계법령을 위반한 사실이 없다.",
                "loc_start": 10,
                "loc_end": 10,
                "normalized": {},
                "confidence": "high",
                "review_status": "approved",
            }
        ],
        "taxonomy_candidates": [],
    }
    (input_dir / "doc1.json").write_text(
        json.dumps(source, ensure_ascii=False), encoding="utf-8"
    )
    (result_dir / "doc1.json").write_text(
        json.dumps(result, ensure_ascii=False), encoding="utf-8"
    )
    manifest = out / "manifest.json"
    manifest.write_text(
        json.dumps({"items": [{"file_key": "doc1"}]}), encoding="utf-8"
    )

    payload = store_results(
        out=out,
        manifest=manifest,
        input_dir=input_dir,
        result_dir=result_dir,
        report=out / "audit.json",
    )

    assert payload["stored"] == ["doc1"]
    with sqlite3.connect(db) as conn:
        assert conn.execute(
            "SELECT taxonomy_id FROM v4_clause_item"
        ).fetchone()[0] == "RW.LABOR.NO_VIOLATION"
