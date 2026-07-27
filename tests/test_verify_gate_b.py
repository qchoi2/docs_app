import json

from eval_v4_gate import evaluate_pooled
from tests.test_v4_search import make_index
from verify_gate_b import _auto_verdict, build_cards, ingest, parse_worksheet


def test_auto_verdict_is_bias_safe():
    # existence: text shows clause -> correct; miss -> leave for human
    assert _auto_verdict("present", True)[0] == "correct"
    assert _auto_verdict("present", False)[0] is None
    # absence: text shows clause -> flag false absence; miss -> NOT auto-confirmed
    assert _auto_verdict("absent", True)[0] == "incorrect"
    assert _auto_verdict("absent", False)[0] is None


def test_parse_worksheet_ignores_auto_comment():
    text = (
        "## Q1 — x  [mode: present]\n"
        "### f.docx  [SPA 국문]\n"
        "- 파일키: aaaaaaaaaaaaaaaa\n"
        "- verdict: correct   # auto: 원문에 조항 확인\n"
    )
    assert parse_worksheet(text)["Q1"]["correct"] == ["aaaaaaaaaaaaaaaa"]


def test_ingest_merges_per_file_key(tmp_path):
    from verify_gate_b import _merge_query
    old = {"correct": ["a", "b"], "incorrect": ["c"], "unknown": []}
    new = {"correct": [], "incorrect": ["a"], "unknown": []}  # a: correct -> incorrect
    merged = _merge_query(old, new)
    assert "a" not in merged["correct"] and "a" in merged["incorrect"]
    assert merged["correct"] == ["b"]  # b untouched


def test_parse_worksheet_maps_verdicts():
    text = (
        "## V4A07 — 환경 없는 계약  [mode: absent]\n"
        "### x.docx  [SPA 국문]\n"
        "- 파일키: aaaaaaaaaaaaaaaa\n"
        "- verdict: correct\n"
        "### y.docx  [SPA 국문]\n"
        "- 파일키: bbbbbbbbbbbbbbbb\n"
        "- verdict: x\n"
        "### z.docx  [SPA 국문]\n"
        "- 파일키: cccccccccccccccc\n"
        "- verdict: \n"  # blank -> skipped
        "## V4E01 — 미지급 임금  [mode: present]\n"
        "### w.docx  [SPA 국문]\n"
        "- 파일키: dddddddddddddddd\n"
        "- verdict: 모름\n"
    )
    parsed = parse_worksheet(text)
    assert parsed["V4A07"]["correct"] == ["aaaaaaaaaaaaaaaa"]
    assert parsed["V4A07"]["incorrect"] == ["bbbbbbbbbbbbbbbb"]
    assert parsed["V4A07"]["unknown"] == []
    assert parsed["V4E01"]["unknown"] == ["dddddddddddddddd"]


def test_cards_then_ingest_then_score_roundtrip(tmp_path):
    out = make_index(tmp_path)
    seed = tmp_path / "seed.yaml"
    seed.write_text(
        "queries:\n"
        "  - id: E1\n"
        "    intent: existence\n"
        "    query: 노무 위반 없음 진술\n"
        "    taxonomy: RW.LABOR.NO_VIOLATION\n",
        encoding="utf-8",
    )
    cards = build_cards(out, seed, depth=25, only=None)
    # present pool = v4 arm {doc a}; card lists it by filename + 파일키
    assert "- 파일키: aaaaaaaaaaaaaaaa" in cards
    assert "- verdict:" in cards

    filled = cards.replace("- verdict: \n", "- verdict: correct\n", 1)
    worksheet = tmp_path / "ws.md"
    worksheet.write_text(filled, encoding="utf-8")
    verdicts_path = tmp_path / "verdicts.json"
    summary = ingest(seed, worksheet, verdicts_path)
    assert "E1" in summary["queries_ingested"]

    verdicts = json.loads(verdicts_path.read_text(encoding="utf-8"))
    report = evaluate_pooled(out, seed, verdicts=verdicts)
    row = {r["id"]: r for r in report["details"]}["E1"]
    assert row["status"] == "scored"
    assert row["scores"]["v4"]["relative_recall"] == 1.0
