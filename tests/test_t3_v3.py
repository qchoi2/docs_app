import json
import sqlite3
from contextlib import closing

import pytest

from enrich_contracts import enrich_contracts
from lib.catalog import initialize_catalog
from plan_t3_v3_pilot import plan_pilot, select_pilot, PilotCandidate
from t3_schema import T3SchemaError, V3_SCHEMA_VERSION, required_clause_tags, validate_v3_result
from enrich_contracts import Candidate
from audit_t3_v3 import _normalized_number_is_supported, audit_pilot


def v3_result(file_key="a" * 16, ctype="SPA"):
    clauses = {}
    for tag in required_clause_tags(ctype):
        clauses[tag] = {
            "present": False,
            "loc_start": None,
            "loc_end": None,
            "summary": "평가 후 확인하지 못함",
            "verbatim": None,
            "normalized": {},
            "confidence": "med",
            "confidence_reason": "표현 변이 가능성",
        }
    clauses["손해배상"] = {
        "present": True,
        "loc_start": 2,
        "loc_end": 3,
        "summary": "책임 제한",
        "verbatim": "총 책임은 매매대금의 10%",
        "normalized": {"cap_pct_of_price": 10, "survival_months": 18},
        "confidence": "high",
        "confidence_reason": None,
    }
    return {
        "file_key": file_key,
        "meta_schema_version": V3_SCHEMA_VERSION,
        "document_status": "contract",
        "deal_type_detail": "구주매매",
        "parties_json": {
            "evaluated": True,
            "items": [
                {
                    "name": "매도인 주식회사",
                    "role": "매도인",
                    "loc_start": 1,
                    "loc_end": 1,
                    "confidence": "high",
                    "confidence_reason": None,
                }
            ],
            "confidence": "high",
            "confidence_reason": None,
        },
        "consideration_json": {
            "evaluated": True,
            "amount_verbatim": "금 일백억원",
            "amount_value": 10000000000,
            "currency": "KRW",
            "payment_methods": ["현금"],
            "adjustment_mechanism": "고정대금",
            "has_earnout": False,
            "loc_start": 2,
            "loc_end": 2,
            "confidence": "high",
            "confidence_reason": None,
        },
        "clause_map_json": clauses,
        "definitions_json": {
            "evaluated": True,
            "items": [],
            "confidence": "med",
            "confidence_reason": None,
        },
        "special_notes": [],
        "confidence": "med",
        "confidence_reason": "파일럿",
    }


def insert_doc(conn, out, file_key, *, ctype="SPA", lang="국문", confidence="low"):
    txt_path = "txt/%s.txt" % file_key
    conn.execute(
        """
        INSERT INTO files(
          file_key,path,folder,filename,ctype,lang,ext,size,mtime,txt_path,char_count,
          status,source_signals,batch_label,content_hash,dup_group,is_draft,version_hint,indexed_at
        ) VALUES (?, ?, '', ?, ?, ?, '.docx', 1, 1, ?, 10,
                  'ok', '{}', 'test', ?, ?, 0, 'final', '2026-07-16')
        """,
        (file_key, file_key + ".docx", file_key + ".docx", ctype, lang, txt_path, file_key, file_key),
    )
    conn.execute(
        "INSERT INTO doc_meta(file_key,meta_schema_version,txt_hash,json,confidence) VALUES (?,2,?,'{}',?)",
        (file_key, file_key, confidence),
    )
    (out / "txt").mkdir(exist_ok=True)
    (out / txt_path).write_text("[¶1]\t당사자\n[¶2]\t손해배상\n[¶3]\t끝\n", encoding="utf-8")


def test_v3_schema_accepts_precise_result_and_requires_type_tags():
    data = v3_result()
    assert validate_v3_result(data, file_key="a" * 16, ctype="SPA") is data
    del data["clause_map_json"]["대금조정"]
    with pytest.raises(T3SchemaError, match="대금조정"):
        validate_v3_result(data, file_key="a" * 16, ctype="SPA")


def test_v3_schema_rejects_present_clause_without_evidence():
    data = v3_result()
    data["clause_map_json"]["손해배상"]["verbatim"] = None
    with pytest.raises(T3SchemaError, match="verbatim"):
        validate_v3_result(data, file_key="a" * 16, ctype="SPA")


def test_v3_schema_accepts_explicit_non_contract_without_clause_guessing():
    data = {
        "file_key": "a" * 16,
        "meta_schema_version": 3,
        "document_status": "not_contract",
        "deal_type_detail": None,
        "parties_json": {"evaluated": False},
        "consideration_json": {"evaluated": False},
        "clause_map_json": {},
        "definitions_json": {"evaluated": False},
        "special_notes": ["킥오프 자료"],
        "confidence": "high",
        "confidence_reason": "계약 체결문이 아니라 자문 범위 설명",
    }
    assert validate_v3_result(data, file_key="a" * 16, ctype="ATA/BTA") is data


def test_audit_accepts_year_to_month_normalization():
    assert _normalized_number_is_supported("survival_months", 36, "거래종결일로부터 3년")
    assert _normalized_number_is_supported("survival_months", 12, "종료 후 [1]년")
    assert not _normalized_number_is_supported("survival_months", 24, "종료 후 1년")


def test_audit_accepts_decimal_eok_normalization():
    assert _normalized_number_is_supported("de_minimis_amount", 50_000_000, "0.5억원")
    assert not _normalized_number_is_supported("de_minimis_amount", 60_000_000, "0.5억원")


def test_enrich_v3_uses_separate_directories_and_records_only_valid_result(tmp_path):
    out = tmp_path / "cs_index"
    db_path = initialize_catalog(out / "catalog.sqlite")
    file_key = "b" * 16
    with closing(sqlite3.connect(db_path)) as conn:
        insert_doc(conn, out, file_key)
        conn.commit()
    result_dir = out / "enrich_results_v3"
    result_dir.mkdir()
    (result_dir / (file_key + ".json")).write_text(
        json.dumps(v3_result(file_key), ensure_ascii=False), encoding="utf-8"
    )

    result = enrich_contracts(out, meta_schema_version=V3_SCHEMA_VERSION)

    assert result["processed"] == [file_key]
    assert (out / "enrich_inputs_v3" / (file_key + ".json")).exists()
    with closing(sqlite3.connect(db_path)) as conn:
        row = conn.execute("SELECT meta_schema_version,confidence FROM doc_meta WHERE file_key=?", (file_key,)).fetchone()
    assert row == (3, "med")


def test_pilot_planner_is_deterministic_and_writes_review_artifacts(tmp_path):
    out = tmp_path / "cs_index"
    db_path = initialize_catalog(out / "catalog.sqlite")
    with closing(sqlite3.connect(db_path)) as conn:
        for index in range(8):
            insert_doc(
                conn,
                out,
                ("%016x" % index),
                ctype="SPA" if index % 2 == 0 else "MOU",
                lang="국문" if index % 3 else "영문",
                confidence="low" if index < 4 else "med",
            )
        conn.commit()

    first = plan_pilot(out, limit=6, write_inputs=True)
    second = plan_pilot(out, limit=6)

    assert [item["file_key"] for item in first["items"]] == [item["file_key"] for item in second["items"]]
    assert first["count"] == 6
    assert (out / "t3_v3_pilot_manifest.json").exists()
    assert (out / "t3_v3_pilot_review.md").exists()
    assert len(list((out / "enrich_inputs_v3").glob("*.json"))) == 6


def test_audit_reports_pending_and_checks_evidence_without_db_write(tmp_path):
    out = tmp_path / "cs_index"
    db_path = initialize_catalog(out / "catalog.sqlite")
    with closing(sqlite3.connect(db_path)) as conn:
        insert_doc(conn, out, "1" * 16, ctype="SPA")
        insert_doc(conn, out, "2" * 16, ctype="SPA")
        conn.commit()
    manifest = plan_pilot(out, limit=2, write_inputs=True)
    first_key = manifest["items"][0]["file_key"]
    result = v3_result(first_key)
    result["clause_map_json"]["손해배상"]["verbatim"] = "손해배상"
    result["clause_map_json"]["손해배상"]["normalized"] = {}
    result_dir = out / "enrich_results_v3"
    result_dir.mkdir()
    (result_dir / (first_key + ".json")).write_text(
        json.dumps(result, ensure_ascii=False), encoding="utf-8"
    )

    report = audit_pilot(out / "t3_v3_pilot_manifest.json")

    assert report["summary"]["total"] == 2
    assert report["summary"]["pass"] == 1
    assert report["summary"]["pending"] == 1
    with closing(sqlite3.connect(db_path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM doc_meta WHERE meta_schema_version=3").fetchone()[0] == 0
