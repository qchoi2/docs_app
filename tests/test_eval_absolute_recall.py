import json

import pytest

from eval_absolute_recall import (
    FULL_READ_MARKERS,
    _recall_at,
    diagnose,
    evaluate,
    load_ground_truth,
    match_item,
    normalize_text,
    paragraph_hit,
    subdomain,
)
from tests.test_v4_search import make_index

RW_ONLY = (("rw_reextract_results", "RW"),)
STORED_VERBATIM = "법령 위반이 없다."
DOC_A = "a" * 16


def write_result(out, family_dir, file_key, items, review_method="full_read"):
    directory = out / family_dir
    directory.mkdir(parents=True, exist_ok=True)
    payload = {"file_key": file_key, "reason": "test", "items": items}
    if review_method is not None:
        payload["review_method"] = review_method
    (directory / f"{file_key}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def rw_item(taxonomy_id, verbatim, loc_start, loc_end=None):
    return {
        "taxonomy_id": taxonomy_id,
        "proposition": f"{taxonomy_id} 명제",
        "verbatim": verbatim,
        "loc_start": loc_start,
        "loc_end": loc_end if loc_end is not None else loc_start,
        "statement_polarity": "none_exist",
    }


def test_full_read_markers_stay_in_sync_with_the_store_convention():
    # The answer key is defined by the store modules' marker set. If that
    # convention moves, this evaluator silently scores the wrong population.
    seen = 0
    for module_name in ("store_rw_reextraction", "store_pay_reextraction"):
        try:
            module = __import__(module_name)
        except Exception:  # pragma: no cover - a mid-edit store must not fail this
            continue
        assert module._FULL_READ_MARKERS == FULL_READ_MARKERS
        seen += 1
    assert seen, "neither store module could be imported"


def test_load_ground_truth_takes_only_full_read_results_with_items(tmp_path):
    out = tmp_path / "cs_index"
    write_result(out, "rw_reextract_results", "a" * 16, [rw_item("RW.TAX", "조세", 3)])
    write_result(out, "rw_reextract_results", "b" * 16, [rw_item("RW.TAX", "조세", 3)],
                 review_method=None)  # auto-extraction: not authoritative
    write_result(out, "rw_reextract_results", "c" * 16, [])  # store skips these
    write_result(out, "rw_reextract_results", "d" * 16, [rw_item("RW.TAX", "조세", 3)],
                 review_method="정독")  # Korean marker is equivalent

    docs = load_ground_truth(out, RW_ONLY)
    assert sorted(doc["file_key"] for doc in docs) == ["a" * 16, "d" * 16]
    assert all(doc["family"] == "RW" for doc in docs)
    assert docs[0]["items"][0]["gt_id"] == f"{'a' * 16}:RW:0"


def test_full_read_marker_is_scoped_to_its_own_family(tmp_path):
    # A document proofread for RW says nothing about its PAY items. Scoring PAY
    # against it would manufacture misses that do not exist.
    out = tmp_path / "cs_index"
    write_result(out, "rw_reextract_results", DOC_A, [rw_item("RW.TAX", "조세", 3)])
    write_result(out, "pay_reextract_results", DOC_A,
                 [rw_item("PAY.BASE_PRICE", "매매대금", 8)])

    rw_docs = load_ground_truth(out, RW_ONLY)
    assert {doc["family"] for doc in rw_docs} == {"RW"}
    assert all(item["family"] == "RW" for doc in rw_docs for item in doc["items"])

    both = load_ground_truth(out)
    assert {(doc["file_key"], doc["family"]) for doc in both} == {
        (DOC_A, "RW"), (DOC_A, "PAY")
    }


def test_match_item_identity_rules():
    quoted = "대상회사는 노무 관련 법령을 위반한 사실이 없다."
    gt = {
        "file_key": DOC_A, "taxonomy_id": "RW.LABOR.NO_VIOLATION",
        "verbatim": quoted, "loc_start": 10, "loc_end": 10,
    }
    assert match_item(gt, {"file_key": DOC_A, "verbatim": f" {quoted}  ",
                           "taxonomy_id": "RW.LABOR.NO_VIOLATION",
                           "loc_start": 10, "loc_end": 10}) == "verbatim_exact"
    # store truncates verbatim at 2000 chars, and quoting varies -> containment
    assert match_item(gt, {"file_key": DOC_A, "verbatim": f"제5조 ({quoted}) 라고 진술한다",
                           "taxonomy_id": "RW.LABOR", "loc_start": 99,
                           "loc_end": 99}) == "verbatim_containment"
    # different wording, but same paragraph and same sub-domain
    assert match_item(gt, {"file_key": DOC_A, "verbatim": "노무 관련 위반 사실 없음",
                           "taxonomy_id": "RW.LABOR.OTHER", "loc_start": 9,
                           "loc_end": 11}) == "loc_subdomain"
    # same paragraph but a different sub-domain is a different clause
    assert match_item(gt, {"file_key": DOC_A, "verbatim": "조세 신고를 완료하였다",
                           "taxonomy_id": "RW.TAX", "loc_start": 10,
                           "loc_end": 10}) is None
    # the right clause in the wrong contract is never a hit
    assert match_item(gt, {"file_key": "b" * 16, "verbatim": quoted,
                           "taxonomy_id": "RW.LABOR.NO_VIOLATION", "loc_start": 10,
                           "loc_end": 10}) is None


def test_short_verbatim_never_matches_by_containment():
    gt = {"file_key": DOC_A, "taxonomy_id": "RW.TAX", "verbatim": "없음",
          "loc_start": 5, "loc_end": 5}
    assert match_item(gt, {"file_key": DOC_A, "verbatim": "조세 채무가 없음을 진술한다",
                           "taxonomy_id": "RW.TAX", "loc_start": 40,
                           "loc_end": 40}) is None


def test_normalize_and_subdomain():
    assert normalize_text("권한·구속력 (A)") == normalize_text("권한구속력A")
    assert normalize_text("ＡＢＣ") == "abc"
    assert subdomain("RW.LABOR.NO_VIOLATION") == "RW.LABOR"
    assert subdomain("PAY") == "PAY"


def test_paragraph_hit_requires_the_para_inside_the_item_range():
    gt = {"loc_start": 10, "loc_end": 12}
    assert paragraph_hit(gt, {11})
    assert not paragraph_hit(gt, {9, 13})
    assert not paragraph_hit({"loc_start": -1, "loc_end": -1}, {5})


def test_recall_at_is_rank_sensitive():
    ranks = {"a": 3, "b": 40, "c": 900}
    grid = _recall_at(ranks, 4, (10, 100, 1000))
    assert grid["@10"] == 0.25
    assert grid["@100"] == 0.5
    assert grid["@1000"] == 0.75


def test_evaluate_scores_items_and_reports_the_miss(tmp_path):
    out = make_index(tmp_path)
    write_result(
        out, "rw_reextract_results", DOC_A,
        [
            rw_item("RW.LABOR.NO_VIOLATION", STORED_VERBATIM, 10),
            # proofread but never stored: the absolute miss pooling cannot see
            rw_item("RW.LABOR.NO_VIOLATION", "쟁의행위가 진행 중이지 아니하다.", 900),
        ],
    )
    report = evaluate(out, max_depth=200, doc_depth=20, sources=RW_ONLY,
                      diagnose_n=2, miss_sample=5)

    assert report["ground_truth"]["documents"] == 1
    assert report["ground_truth"]["items"] == 2
    assert report["ground_truth"]["documents_by_family"] == {"RW": 1}
    assert report["total_gt_items"] == 2

    structured = report["by_path"]["structured"]
    assert structured["rank_unit"] == "item"
    assert structured["retrieved"] == 1
    assert structured["recall_within_max_depth"] == 0.5
    assert structured["recall_at"]["@10"] == 0.5

    assert report["by_family"]["RW"]["gt_items"] == 2
    assert report["by_family"]["RW"]["hybrid_item_paths"]["recall_within_max_depth"] == 0.5
    assert report["missed_by_item_paths"] == 1

    miss = report["miss_sample"][0]
    assert miss["file_key"] == DOC_A
    assert miss["taxonomy_id"] == "RW.LABOR.NO_VIOLATION"
    assert "쟁의행위" in miss["verbatim"]
    assert miss["diagnosis"] == "text_not_in_index"
    assert set(report["match_rules"]) == {"structured:verbatim_exact"}


def test_evaluate_scopes_each_family_to_its_own_answer_key(tmp_path):
    # The RW doc is also handed a PAY answer key; RW recall must not change.
    out = make_index(tmp_path)
    write_result(out, "rw_reextract_results", DOC_A,
                 [rw_item("RW.LABOR.NO_VIOLATION", STORED_VERBATIM, 10)])
    write_result(out, "pay_reextract_results", DOC_A,
                 [rw_item("PAY.BASE_PRICE", "매매대금은 100원으로 한다.", 20)])

    report = evaluate(out, max_depth=200, doc_depth=20, diagnose_n=0, miss_sample=5)
    assert report["ground_truth"]["items_by_family"] == {"RW": 1, "PAY": 1}
    # RW is fully retrieved; the (never extracted) PAY item is the only miss.
    assert report["by_family"]["RW"]["structured"]["recall_within_max_depth"] == 1.0
    assert report["by_family"]["PAY"]["structured"]["recall_within_max_depth"] == 0.0
    assert report["by_path"]["structured"]["recall_within_max_depth"] == 0.5


def test_report_states_its_hit_definition_and_limits(tmp_path):
    out = make_index(tmp_path)
    write_result(out, "rw_reextract_results", DOC_A,
                 [rw_item("RW.LABOR.NO_VIOLATION", STORED_VERBATIM, 10)])
    report = evaluate(out, max_depth=50, doc_depth=10, sources=RW_ONLY,
                      diagnose_n=0, miss_sample=0)
    definition = report["hit_definition"]
    assert definition["granularity"].startswith("answer-key item")
    assert "(file_key, family)" in definition["scope"]
    assert any("SPA-skewed" in limit for limit in report["limits"])
    assert report["parameters"]["max_depth"] == 50


def test_diagnose_reports_a_taxonomy_mismatch(tmp_path):
    out = make_index(tmp_path)
    gt = {
        "file_key": DOC_A, "family": "RW", "taxonomy_id": "RW.TAX",
        "verbatim": STORED_VERBATIM, "loc_start": 10, "loc_end": 10,
    }
    result = diagnose(out, gt)
    assert result["diagnosis"] == "taxonomy_mismatch"
    assert result["stored_taxonomy_ids"] == ["RW.LABOR.NO_VIOLATION"]


def test_diagnose_skips_a_verbatim_too_short_to_identify(tmp_path):
    out = make_index(tmp_path)
    gt = {"file_key": DOC_A, "family": "RW", "taxonomy_id": "RW.TAX",
          "verbatim": "없음", "loc_start": 1, "loc_end": 1}
    assert diagnose(out, gt)["diagnosis"] == "verbatim_too_short_to_probe"


@pytest.mark.parametrize("missing_dir", ["rw_reextract_results", "pay_reextract_results"])
def test_missing_result_directory_is_not_an_error(tmp_path, missing_dir):
    out = tmp_path / "cs_index"
    out.mkdir()
    assert load_ground_truth(out, ((missing_dir, "RW"),)) == []
