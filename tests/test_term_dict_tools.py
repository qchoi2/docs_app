import json

from term_dict_tools import main


GOOD_DICT = """
terms:
  - canonical: 배상상한
    kind: concept
    ko: [배상상한, 배상 상한, 손해배상 상한]
    en: [liability cap]
  - canonical: 해제
    kind: clause
    ko: [해제, 계약해제]
    expansion_strength: normal
"""


def test_validate_passes_on_well_formed_dict(tmp_path, capsys):
    path = tmp_path / "term_dict.yaml"
    path.write_text(GOOD_DICT, encoding="utf-8")

    rc = main(["--validate", "--dict", str(path)])
    out = capsys.readouterr().out

    assert rc == 0
    assert "errors: 0" in out


def test_validate_fails_on_missing_canonical_and_bad_strength(tmp_path, capsys):
    path = tmp_path / "term_dict.yaml"
    path.write_text(
        """
terms:
  - kind: clause
    ko: [고아 변이]
  - canonical: 해제
    expansion_strength: loose
""",
        encoding="utf-8",
    )

    rc = main(["--validate", "--dict", str(path)])
    out = capsys.readouterr().out

    assert rc == 2
    assert "canonical is required" in out
    assert "invalid expansion_strength" in out


def test_suggest_reports_unknown_terms_with_evidence(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "term_dict.yaml").write_text(GOOD_DICT, encoding="utf-8")
    out = tmp_path / "cs_index"
    out.mkdir()
    records = [
        {"query": {"kw": ["손해배상 상한"]}, "result_count": 12},   # known -> excluded
        {"query": {"kw": ["웨런티보험"]}, "result_count": 0},        # unknown -> candidate
        {"query": {"kw": ["웨런티보험"]}, "result_count": 1},
    ]
    (out / "query_log.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )

    rc = main(["--suggest", "--out", str(out)])
    assert rc == 0

    import yaml
    pending = yaml.safe_load((out / "pending_terms.yaml").read_text(encoding="utf-8"))
    terms = [c["term"] for c in pending["candidates"]]
    assert terms == ["웨런티보험"]
    assert pending["candidates"][0]["seen"] == 2
    assert sorted(pending["candidates"][0]["result_counts"]) == [0, 1]
