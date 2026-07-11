import json
import sqlite3
from contextlib import closing

from lib.catalog import initialize_catalog
from eval_search import main, run_eval


def insert_doc(conn, file_key, path, content, *, ctype="SPA", lang="국문", is_draft=None):
    conn.execute(
        """
        INSERT INTO files (
          file_key, path, folder, filename, ctype, lang, ext, size, mtime,
          txt_path, char_count, status, error_reason, source_signals,
          batch_label, content_hash, dup_group, is_draft, version_hint, indexed_at
        )
        VALUES (?, ?, '', ?, ?, ?, '.docx', 1, 1, ?, ?, 'ok', NULL, '{}',
          'test', ?, ?, ?, NULL, '2026-07-10T00:00:00+00:00')
        """,
        (file_key, path, path, ctype, lang, f"txt/{file_key}.txt", len(content), file_key, file_key, is_draft),
    )
    for index, paragraph in enumerate(content.split("\n"), start=1):
        conn.execute(
            "INSERT INTO fts(content, file_key, para) VALUES (?, ?, ?)",
            (paragraph, file_key, index),
        )


def insert_doc_meta(conn, file_key, clause_map, confidence="high"):
    conn.execute(
        """
        INSERT INTO doc_meta (
          file_key, meta_schema_version, txt_hash, extracted_at,
          clause_map_json, json, confidence
        )
        VALUES (?, 1, ?, '2026-07-12T00:00:00+00:00', ?, '{}', ?)
        """,
        (file_key, file_key, json.dumps(clause_map, ensure_ascii=False, sort_keys=True), confidence),
    )


def make_corpus(tmp_path):
    out = tmp_path / "cs_index"
    db_path = initialize_catalog(out / "catalog.sqlite")
    with closing(sqlite3.connect(db_path)) as conn:
        insert_doc(conn, "spa1", "spa1.docx", "손해배상 조항", ctype="SPA", lang="국문")
        insert_doc(conn, "spa2", "spa2.docx", "진술보장 조항", ctype="SPA", lang="국문")
        insert_doc(conn, "sha1", "sha1.docx", "shareholders", ctype="SHA", lang="영문")
        insert_doc_meta(conn, "spa1", {"손해배상": {"present": True, "loc_start": 1, "loc_end": 1}})
        insert_doc_meta(conn, "spa2", {"손해배상": {"present": False, "summary": "none"}})
        conn.commit()
    return out


GOLDEN = """
queries:
  - id: T1a
    tier: T1
    intent: 메타목록
    query: "국문 SPA"
    expected_filter: { ctype: SPA, lang: 국문 }
    expected_count: 2
    expected_files: []
  - id: T2a
    tier: T2
    intent: 키워드
    query: "earn-out"
    expected_filter: {}
    expected_files: []
  - id: T1b
    tier: T1
    intent: 메타목록
    query: "recall"
    expected_filter: { ctype: SPA }
    expected_files: [spa1]
  - id: T3skip
    tier: T3
    intent: skip
    query: "skip"
    expected_filter: {}
    expected_files: []
"""


def write_golden(tmp_path):
    golden = tmp_path / "golden.yaml"
    golden.write_text(GOLDEN, encoding="utf-8")
    return golden


def test_eval_runs_only_t1_t2_and_writes_history(tmp_path):
    out = make_corpus(tmp_path)
    golden = write_golden(tmp_path)

    record = run_eval(out, golden_path=golden, tiers=["T1", "T2"])

    ids = [q["id"] for q in record["queries"]]
    assert ids == ["T1a", "T2a", "T1b"]  # T3 excluded
    assert record["summary"]["total"] == 3
    assert (out / "eval_history.jsonl").exists()
    lines = (out / "eval_history.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["summary"]["total"] == 3


def test_partial_filter_scoring_and_count(tmp_path):
    out = make_corpus(tmp_path)
    golden = write_golden(tmp_path)

    record = run_eval(out, golden_path=golden, tiers=["T1", "T2"])
    by_id = {q["id"]: q for q in record["queries"]}

    t1a = by_id["T1a"]
    assert t1a["mode"] == "partial(filter-only)"
    assert t1a["precision"] == 1.0
    assert t1a["actual_count"] == 2
    assert t1a["count_ok"] is True
    assert t1a["status"] == "pass"


def test_empty_filter_query_is_unscored(tmp_path):
    out = make_corpus(tmp_path)
    golden = write_golden(tmp_path)

    record = run_eval(out, golden_path=golden, tiers=["T1", "T2"])
    t2a = {q["id"]: q for q in record["queries"]}["T2a"]

    assert t2a["precision"] is None
    assert t2a["recall"] is None
    assert t2a["status"] == "unscored"


def test_expected_files_enable_recall(tmp_path):
    out = make_corpus(tmp_path)
    golden = write_golden(tmp_path)

    record = run_eval(out, golden_path=golden, tiers=["T1", "T2"])
    t1b = {q["id"]: q for q in record["queries"]}["T1b"]

    assert t1b["mode"] == "full"
    assert t1b["recall"] == 1.0
    assert t1b["status"] == "pass"


def test_cli_prints_summary_and_returns_zero(tmp_path, capsys):
    out = make_corpus(tmp_path)
    golden = write_golden(tmp_path)

    rc = main(["--out", str(out), "--golden", str(golden)])
    captured = capsys.readouterr()

    assert rc == 0
    assert "summary: total=3" in captured.out


def test_cli_json_output(tmp_path, capsys):
    out = make_corpus(tmp_path)
    golden = write_golden(tmp_path)

    rc = main(["--out", str(out), "--golden", str(golden), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["summary"]["total"] == 3
    assert {"ts", "golden", "tiers", "summary", "queries"}.issubset(payload)


def test_golden_kw_field_drives_keyword_search(tmp_path):
    out = make_corpus(tmp_path)
    golden = tmp_path / "golden_kw.yaml"
    golden.write_text(
        """
queries:
  - id: KW1
    tier: T2
    intent: 키워드
    query: "손해배상 있는 SPA"
    kw: ["손해배상"]
    expected_filter: { ctype: SPA }
    expected_files: [spa1]
""",
        encoding="utf-8",
    )

    record = run_eval(out, golden_path=golden, tiers=["T1", "T2"])
    kw1 = {q["id"]: q for q in record["queries"]}["KW1"]

    assert kw1["kw"] == ["손해배상"]
    # spa2 (진술보장) is excluded by the keyword, so recall on spa1 passes
    assert kw1["recall"] == 1.0
    assert kw1["status"] == "pass"


def test_t3_clause_query_scores_via_clause_filter(tmp_path):
    out = make_corpus(tmp_path)
    golden = tmp_path / "golden_t3.yaml"
    golden.write_text(
        """
queries:
  - id: T3_present
    tier: T3
    intent: 조항존재
    query: "손해배상 조항 있는 계약"
    expected_filter: { ctype: SPA, clause: indemnity, present: true }
    expected_files: [spa1]
""",
        encoding="utf-8",
    )

    record = run_eval(out, golden_path=golden, tiers=["T3"])
    query = record["queries"][0]

    assert query["mode"] == "full"
    assert query["scored_filter"]["clause"] == "indemnity"
    assert query["scored_filter"]["present"] is True
    assert query["precision"] == 1.0
    assert query["recall"] == 1.0
    assert query["status"] == "pass"


def test_t3_absent_query_separates_present_false_from_missing_tag(tmp_path):
    out = make_corpus(tmp_path)
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        insert_doc(conn, "unknown", "unknown.docx", "손해배상 없음", ctype="SPA", lang="국문")
        insert_doc_meta(conn, "unknown", {"진술보장": {"present": True, "loc_start": 1, "loc_end": 1}})
        conn.commit()
    golden = tmp_path / "golden_t3_absent.yaml"
    golden.write_text(
        """
queries:
  - id: T3_absent
    tier: T3
    intent: 조항부재
    query: "손해배상 없는 계약"
    expected_filter: { ctype: SPA, clause: 손해배상, present: false }
    expected_files: [spa2]
""",
        encoding="utf-8",
    )

    record = run_eval(out, golden_path=golden, tiers=["T3"])
    query = record["queries"][0]

    assert query["recall"] == 1.0
    assert query["status"] == "pass"
    assert {"file_key": "unknown", "reason": "미평가"} in query["clause_needs_review"]


def test_t3_query_without_clause_is_skipped(tmp_path):
    out = make_corpus(tmp_path)
    golden = write_golden(tmp_path)

    record = run_eval(out, golden_path=golden, tiers=["T3"])
    query = record["queries"][0]

    assert query["id"] == "T3skip"
    assert query["status"] == "skipped"
    assert query["skip_reason"] == "t3_clause_filter_missing"
    assert record["summary"]["skipped"] == 1


def test_t3_tier_absent_runs_and_logs_empty_result(tmp_path):
    out = make_corpus(tmp_path)
    golden = tmp_path / "no_t3.yaml"
    golden.write_text(
        """
queries:
  - id: OnlyT1
    tier: T1
    expected_filter: { ctype: SPA }
    expected_files: []
""",
        encoding="utf-8",
    )

    record = run_eval(out, golden_path=golden, tiers=["T3"])

    assert record["summary"]["total"] == 0
    assert record["summary"]["skipped"] == 0
    history = (out / "eval_history.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(history[-1])["tiers"] == ["T3"]
