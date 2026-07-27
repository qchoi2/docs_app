import json

from eval_v4_gate import (
    evaluate,
    evaluate_pooled,
    score_pooled_absence,
    score_pooled_present,
)
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
                        "taxonomy_id": "CP.THIRD_PARTY_CONSENT",
                    },
                    {
                        "id": "c1",
                        "mode": "compare",
                        "taxonomy_id": "CP.THIRD_PARTY_CONSENT",
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


def test_score_pooled_present_precision_and_relative_recall():
    # correct pool = {a, b, c}; legacy found {a, x(wrong)}; v4 found {a, b, c}
    arms = {"legacy": {"a", "x"}, "v4": {"a", "b", "c"}}
    verified = {"correct": ["a", "b", "c"], "incorrect": ["x"]}
    scores = score_pooled_present(arms, verified)
    assert scores["legacy"]["precision"] == 0.5          # 1 correct of 2 judged
    assert scores["legacy"]["relative_recall"] == round(1 / 3, 4)
    assert scores["v4"]["precision"] == 1.0
    assert scores["v4"]["relative_recall"] == 1.0


def test_score_pooled_absence_precision_and_backlog():
    scores = score_pooled_absence(
        confirmed={"a", "b"}, needs_review={"c", "d", "e"},
        verified={"correct": ["a"], "incorrect": ["b"], "unknown": ["c"]},
    )
    assert scores["confirmed_absent_precision"] == 0.5   # a truly absent, b false
    assert scores["confirmed_absent_false"] == 1
    assert scores["needs_review_backlog"] == 3


def test_evaluate_pooled_builds_pool_worklist_and_scores(tmp_path):
    out = make_index(tmp_path)
    seed = tmp_path / "seed.yaml"
    seed.write_text(
        "queries:\n"
        "  - id: E1\n"
        "    intent: existence\n"
        "    taxonomy: RW.LABOR.NO_VIOLATION\n"
        "    pool_verified: { correct: [aaaaaaaaaaaaaaaa], incorrect: [] }\n"
        "  - id: A1\n"
        "    intent: absence\n"
        "    taxonomy: CP.THIRD_PARTY_CONSENT\n"
        "    pool_verified: { correct: [bbbbbbbbbbbbbbbb], incorrect: [], unknown: [] }\n"
        "  - id: U1\n"
        "    intent: existence\n"
        "    taxonomy: NOT.A.REAL.NODE\n",
        encoding="utf-8",
    )
    report = evaluate_pooled(out, seed)
    assert report["query_count"] == 3
    assert "U1" in report["unbound"]
    by_id = {row["id"]: row for row in report["details"]}
    # present: v4 arm found doc a; owner verified it correct
    assert by_id["E1"]["scores"]["v4"]["relative_recall"] == 1.0
    # absence: b confirmed_absent and verified truly absent -> precision 1.0
    assert by_id["A1"]["scores"]["confirmed_absent_precision"] == 1.0
    assert by_id["A1"]["needs_review"] == 1
