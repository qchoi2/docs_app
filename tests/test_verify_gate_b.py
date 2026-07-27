import json

from eval_v4_gate import evaluate_pooled
from tests.test_v4_search import make_index
from verify_gate_b import build_cards, ingest, parse_worksheet


def test_parse_worksheet_maps_verdicts():
    text = (
        "## V4A07 — 환경 없는 계약  [mode: absent]\n"
        "### aaaaaaaaaaaaaaaa  [SPA 국문] x.docx\n"
        "- verdict: correct\n"
        "### bbbbbbbbbbbbbbbb  [SPA 국문] y.docx\n"
        "- verdict: x\n"
        "### cccccccccccccccc  [SPA 국문] z.docx\n"
        "- verdict: \n"  # blank -> skipped
        "## V4E01 — 미지급 임금  [mode: present]\n"
        "### dddddddddddddddd  [SPA 국문] w.docx\n"
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
    # present pool = v4 arm {doc a}; card lists it with a verdict slot
    assert "### aaaaaaaaaaaaaaaa" in cards
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
