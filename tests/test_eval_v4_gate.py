import json

from eval_v4_gate import evaluate
from tests.test_v4_search import make_index


def test_gate_evaluator_scores_present_absent_and_flags_unscored_compare(tmp_path):
    out = make_index(tmp_path)
    manifest = tmp_path / "golden.json"
    manifest.write_text(
        json.dumps(
            {
                "queries": [
                    {
                        "id": "p1",
                        "mode": "present",
                        "taxonomy_id": "RW.LABOR.NO_VIOLATION",
                    },
                    {
                        "id": "a1",
                        "mode": "absent",
                        "taxonomy_id": "RW.LABOR.NO_VIOLATION",
                    },
                    {
                        "id": "c1",
                        "mode": "compare",
                        "taxonomy_id": "RW.LABOR.NO_VIOLATION",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    result = evaluate(out, manifest)
    assert result["query_count"] == 3
    assert result["scored_count"] == 3
    assert result["present_mean_v4_recall"] == 1.0
    assert result["details"][1]["confirmed_absent"] == 1
    assert result["details"][2]["states"] == [
        "confirmed_present",
        "confirmed_absent",
        "needs_review",
    ]
