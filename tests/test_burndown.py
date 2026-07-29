"""burndown.py (PLAN_REVIEW 권고 5) — 지표 계산과 웹 패널 노출 테스트."""

import io
import json
import sqlite3
from contextlib import closing

import burndown
from lib.catalog import initialize_catalog
from v4_schema import initialize_v4_schema
from v4_search import search_clause_absence
from webapp import App


NOW = "2026-07-29T00:00:00+00:00"

FILE_COLUMNS = """
  file_key,path,folder,filename,ctype,lang,ext,size,mtime,txt_path,
  char_count,status,source_signals,batch_label,content_hash,
  dup_group,indexed_at
"""

# (file_key 문자, path, ctype, dup_group 문자) — path/filename은 SHA·별지 정규식에
# 걸리지 않는 중립 이름을 쓴다.
DOCS = [
    ("a", "corp/deal_a.docx", "SPA", "a"),
    ("b", "corp/deal_b.docx", "SPA", "b"),
    ("c", "corp/deal_c.docx", "SPA", "b"),  # b와 같은 dup_group → 대표 1건만 집계
    ("d", "corp/deal_d.docx", "SSA", "d"),
    ("e", "corp/deal_e.docx", "MOU", "e"),  # 대상유형 아님 → 제외
]


def make_index(tmp_path, *, with_rw_reextract=True, with_result_dir=True):
    out = tmp_path / "cs_index"
    db_path = initialize_catalog(out / "catalog.sqlite")
    with closing(sqlite3.connect(db_path)) as conn:
        conn.executemany(
            f"INSERT INTO files({FILE_COLUMNS}) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    letter * 16, path, "", path.split("/")[-1], ctype, "국문",
                    ".docx", 1, 1, f"txt/{letter}.txt", 10, "ok", "{}", "full",
                    letter * 16, group * 16, NOW,
                )
                for letter, path, ctype, group in DOCS
            ],
        )
        initialize_v4_schema(conn)
        # a: CP 완전(부재 질의 가능) / b: CP body partial / d: coverage 행 없음(미평가)
        for letter, body_status, annex_status in (
            ("a", "complete", "no_annex"),
            ("b", "partial", "partial"),
        ):
            for family in ("RW", "CP"):
                conn.execute(
                    """
                    INSERT INTO v4_document_coverage(
                      file_key,family,body_status,annex_status,reason,txt_hash,
                      taxonomy_version,extractor_version,prompt_version,reviewed_at
                    ) VALUES (?,?,?,?,?,?,12,'test','test',?)
                    """,
                    (
                        letter * 16, family, body_status, annex_status,
                        "rw_subdomain_audit_pending"
                        if (family == "RW" and letter == "b")
                        else "reviewed",
                        letter * 16, NOW,
                    ),
                )
        if with_rw_reextract:
            conn.execute(
                """
                INSERT INTO v4_clause_item(
                  file_key,item_ref,family,taxonomy_id,proposition,
                  statement_polarity,source_kind,verbatim,loc_start,loc_end,
                  confidence,txt_hash,taxonomy_version,extractor_version,
                  prompt_version,review_status,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,'body',?,?,?,'high',?,12,'test','test',
                          'approved',?,?)
                """,
                (
                    "a" * 16, "RWRX-001", "RW", "RW.LABOR.NO_VIOLATION",
                    "노무 관련 법령 위반이 없다.", "none_exist",
                    "법령 위반이 없다.", 10, 10, "a" * 16, NOW, NOW,
                ),
            )
        conn.commit()
    if with_result_dir:
        results = out / burndown.RW_RESULT_DIRNAME
        results.mkdir(parents=True, exist_ok=True)
        (results / "aaaa.json").write_text("{}", encoding="utf-8")
    return out


def add_candidate(out, *, proposed_ko, family, parent, file_key, document_count=1):
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        conn.execute(
            """
            INSERT INTO v4_taxonomy_candidate(
              proposed_ko,family,recommended_parent_id,distinction_reason,
              evidence_file_key,loc_start,loc_end,verbatim,document_count,status,
              created_at,updated_at
            ) VALUES (?,?,?,'검토 필요',?,1,1,?,?,'pending',?,?)
            """,
            (proposed_ko, family, parent, file_key, proposed_ko,
             document_count, NOW, NOW),
        )
        conn.commit()


# ---------------- 계산 ----------------

def test_type_progress_dedupes_and_scopes_by_contract_type(tmp_path):
    result = burndown.build_burndown(make_index(tmp_path))
    progress = result["type_progress"]
    by_type = {row["ctype"]: row for row in progress["by_type"]}
    # c는 b와 같은 dup_group이라 대표 1건만, MOU는 대상유형이 아니라 제외된다.
    assert by_type["SPA"]["total"] == 2
    assert by_type["SPA"]["evaluated"] == 2
    assert by_type["SSA"] == {
        "ctype": "SSA", "evaluated": 0, "total": 1, "remaining": 1,
        "percent": 0.0,
        "primary_only": {"evaluated": 0, "total": 1, "remaining": 1, "percent": 0.0},
    }
    assert progress["core_planned"]["total"] == 3
    assert progress["core_planned"]["evaluated"] == 2
    assert progress["core_planned"]["percent"] == 66.7
    assert progress["scope_added"]["total"] == 0
    assert progress["scope_added"]["percent"] is None
    assert result["index"]["taxonomy_version"] is not None
    assert result["generated_at"].endswith("Z")


def test_family_coverage_reports_body_and_annex_separately(tmp_path):
    result = burndown.build_burndown(make_index(tmp_path))
    families = result["family_coverage"]["families"]
    scope = families["CP"]["target_scope"]
    assert scope["body"] == {"complete": 1, "partial": 1}
    assert scope["annex"] == {"no_annex": 1, "partial": 1}
    assert scope["target_documents"] == 3
    assert scope["with_coverage_row"] == 2
    # coverage 행이 아예 없는 문서(d)는 present=false가 아니라 미평가다.
    assert scope["no_coverage_row_not_evaluated"] == 1
    # 평가된 적 없는 family는 전부 미평가로 잡힌다.
    assert families["PAY"]["target_scope"]["no_coverage_row_not_evaluated"] == 3
    assert families["PAY"]["documents_with_coverage_row"] == 0


def test_absence_eligibility_matches_search_and_bins_reasons(tmp_path):
    out = make_index(tmp_path)
    result = burndown.build_burndown(out)
    absence = result["absence_eligibility"]
    assert absence["pairs_total"] == 3 * len(burndown.FAMILY_ORDER)

    # 실제 검색(search_clause_absence)과 같은 판정이어야 한다.
    # 검색은 대상유형 밖 문서(MOU)도 훑으므로 대상 모집단으로 좁혀 비교한다.
    target = {"a" * 16, "b" * 16, "d" * 16}
    search = search_clause_absence(out, "CP.THIRD_PARTY_CONSENT")
    eligible = {row["file_key"] for row in search["confirmed_absent"]} & target
    blocked = {row["file_key"] for row in search["needs_review"]} & target
    assert eligible == {"a" * 16}
    assert absence["families"]["CP"]["absence_eligible"] == len(eligible) == 1
    assert absence["families"]["CP"]["absence_blocked"] == len(blocked) == 2

    reasons = absence["families"]["CP"]["blocking_reasons"]
    assert reasons["body_partial"] == 1
    assert reasons["annex_partial"] == 1
    assert reasons["family_not_evaluated"] == 1

    # RW는 ABSENCE_UNVERIFIED_FAMILIES라 complete여도 가능이 되지 않는다.
    assert absence["families"]["RW"]["family_gated"] is True
    assert absence["families"]["RW"]["absence_eligible"] == 0
    assert absence["families"]["RW"]["blocking_reasons"]["rw_coverage_unverified"] == 1
    assert "RW" in absence["family_gated_families"]


def test_absence_reason_histogram_includes_pending_candidates(tmp_path):
    out = make_index(tmp_path)
    add_candidate(
        out,
        proposed_ko="새 종결 선행조건 명제",
        family="CP",
        parent="CP.THIRD_PARTY_CONSENT",  # dotted → 실제 taxonomy 공백(blocking)
        file_key="a" * 16,
    )
    absence = burndown.build_burndown(out)["absence_eligibility"]
    assert absence["families"]["CP"]["absence_eligible"] == 0
    assert absence["families"]["CP"]["blocking_reasons"][
        "pending_taxonomy_candidates"
    ] == 1
    assert absence["blocking_reasons"]["pending_taxonomy_candidates"] == 1


def test_backlog_splits_blocking_from_document_specific_one_offs(tmp_path):
    out = make_index(tmp_path)
    add_candidate(
        out, proposed_ko="이 계약 고유 정의어", family="DEF", parent="DEF",
        file_key="a" * 16,
    )  # 문서-특정 일회성 → 비차단
    add_candidate(
        out, proposed_ko="새 종결 선행조건 명제", family="CP",
        parent="CP.THIRD_PARTY_CONSENT", file_key="a" * 16,
    )  # 특정 하위노드 추천 → 차단
    backlog = burndown.build_burndown(out)["taxonomy_backlog"]
    assert backlog["status_counts"]["pending"] == 2
    assert backlog["pending_total"] == 2
    assert backlog["pending_blocking"] == 1
    assert backlog["pending_non_blocking"] == 1
    assert backlog["documents_blocked_by_pending"] == 1
    assert backlog["by_family"]["CP"]["blocking_candidates"] == 1
    assert backlog["by_family"]["DEF"]["blocking_candidates"] == 0
    assert backlog["pending_outside_known_families"] == 0


def test_rw_reextraction_progress_is_derived_not_hardcoded(tmp_path):
    rw = burndown.build_burndown(make_index(tmp_path))["rw_reextraction"]
    assert rw["stored_documents"] == 1          # RWRX item 보유 문서
    assert rw["remaining_audit_pending"] == 1   # reason 표식이 남은 문서
    assert rw["target_documents"] == 2
    assert rw["percent"] == 50.0
    assert rw["result_files"] == 1
    assert "target_documents_unavailable_reason" not in rw


def test_non_derivable_metrics_emit_null_with_reason(tmp_path):
    out = make_index(tmp_path, with_rw_reextract=False, with_result_dir=False)
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        conn.execute(
            "UPDATE v4_document_coverage SET reason='reviewed' WHERE family='RW'"
        )
        conn.execute("DELETE FROM v4_meta WHERE key='taxonomy_version'")
        conn.commit()
    result = burndown.build_burndown(out)
    rw = result["rw_reextraction"]
    # 목표치를 지어내지 않는다: null + 사유.
    assert rw["stored_documents"] == 0
    assert rw["target_documents"] is None
    assert "산출 불가" in rw["target_documents_unavailable_reason"]
    assert rw["percent"] is None
    assert rw["percent_unavailable_reason"]
    assert rw["result_files"] is None
    assert burndown.RW_RESULT_DIRNAME in rw["result_files_unavailable_reason"]
    assert result["index"]["taxonomy_version"] is None
    assert result["index"]["taxonomy_version_unavailable_reason"]


def test_cli_json_and_text_output(tmp_path, capsys):
    out = make_index(tmp_path)
    assert burndown.main(["--out", str(out), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["type_progress"]["core_planned"]["total"] == 3

    assert burndown.main(["--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert "대상유형 진행률" in text
    assert "부재 질의 가능 vs 차단" in text
    assert "RW 재추출 진척" in text


def test_cli_reports_missing_catalog(tmp_path, capsys):
    assert burndown.main(["--out", str(tmp_path / "missing")]) == 2
    assert "ERROR" in capsys.readouterr().err


# ---------------- 웹 패널 ----------------

def call(app, method, path):
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": "0",
        "wsgi.input": io.BytesIO(b""),
    }
    captured = {}

    def start_response(status, headers):
        captured["status"] = int(status.split()[0])
        captured["headers"] = dict(headers)

    payload = b"".join(app(environ, start_response))
    return captured["status"], captured["headers"], payload


def test_ops_burndown_api_and_panel_render(tmp_path):
    app = App(make_index(tmp_path))
    try:
        status, headers, payload = call(app, "GET", "/api/ops/burndown")
        assert status == 200
        assert "application/json" in headers["Content-Type"]
        data = json.loads(payload.decode("utf-8"))
        assert data["type_progress"]["core_planned"]["total"] == 3
        assert data["absence_eligibility"]["families"]["RW"]["family_gated"] is True
        assert data["generated_at"]

        status, headers, page = call(app, "GET", "/operations")
        assert status == 200
        html = page.decode("utf-8")
        assert "번다운" in html
        for element_id in (
            "burndown-types", "burndown-families", "burndown-reasons",
            "burndown-backlog", "burndown-meta",
        ):
            assert f'id="{element_id}"' in html

        status, _, script = call(app, "GET", "/static/operations.js")
        assert status == 200
        source = script.decode("utf-8")
        assert "/api/ops/burndown" in source
        assert "renderBurndown" in source
    finally:
        app.shutdown()
