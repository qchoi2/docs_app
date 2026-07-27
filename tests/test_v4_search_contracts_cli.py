import json

from search_contracts import main
from tests.test_v4_search import make_index


def test_existing_cli_accepts_v4_item_search(tmp_path, capsys):
    out = make_index(tmp_path)
    code = main(
        [
            "--out",
            str(out),
            "--item",
            "RW.LABOR.NO_VIOLATION",
            "--polarity",
            "none_exist",
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["total_documents"] == 1
    assert payload["results"][0]["item_ref"] == "RW-001"


def test_existing_cli_preserves_safe_absence_split(tmp_path, capsys):
    out = make_index(tmp_path)
    # CP (non-gated covenant/condition family) confirms absence.
    code = main(
        ["--out", str(out), "--item", "CP.THIRD_PARTY_CONSENT", "--item-absent", "--json"]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["confirmed_absent_count"] == 1
    assert payload["needs_review_count"] == 1


def test_cli_rw_absence_is_demoted_to_needs_review(tmp_path, capsys):
    out = make_index(tmp_path)
    code = main(
        ["--out", str(out), "--item", "RW.LABOR.NO_VIOLATION", "--item-absent", "--json"]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["confirmed_absent_count"] == 0
    assert "rw_absence_unverified_demoted_to_needs_review" in payload["warnings"]
