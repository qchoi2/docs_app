from audit_t3_v4 import (
    document_coverage_issues,
    oversegmentation_issues,
    paragraph_map,
)
from v4_schema import FAMILIES


def _item(ref, family, loc_start, loc_end, verbatim):
    return {
        "item_ref": ref,
        "family": family,
        "source_kind": "body",
        "loc_start": loc_start,
        "loc_end": loc_end,
        "verbatim": verbatim,
    }


def test_all_body_families_not_evaluated_is_an_audit_issue():
    data = {
        "coverage": {
            family: {
                "body_status": "not_evaluated",
                "annex_status": "no_annex",
            }
            for family in FAMILIES
        }
    }
    assert document_coverage_issues(data) == [
        {
            "code": "document_body_not_evaluated",
            "detail": "all clause families have body_status=not_evaluated",
        }
    ]


def test_one_completed_body_family_avoids_empty_review_issue():
    data = {
        "coverage": {
            family: {
                "body_status": "complete" if family == "RW" else "not_evaluated",
                "annex_status": "no_annex",
            }
            for family in FAMILIES
        }
    }
    assert document_coverage_issues(data) == []


def test_unscoped_body_paragraphs_are_valid_evidence_coordinates():
    assert paragraph_map(
        {
            "family_sections": {},
            "source_inventory": [],
            "unscoped_body_paragraphs": [
                {"para": 12, "text": "The Company shall issue the Bonds."}
            ],
        }
    ) == {12: "The Company shall issue the Bonds."}


def test_density_flags_paragraph_with_six_items():
    data = {
        "items": [
            _item(f"RWRX-{i}", "RW", 40, 40, f"진술보장 항목 {i}입니다.")
            for i in range(6)
        ]
    }
    findings = oversegmentation_issues(data)
    density = [f for f in findings if f["code"] == "paragraph_oversegmented"]
    assert len(density) == 1
    detail = density[0]["detail"]
    assert detail["family"] == "RW"
    assert detail["loc_start"] == 40
    assert detail["item_count"] == 6
    assert detail["item_refs"] == [f"RWRX-{i}" for i in range(6)]


def test_duplicate_verbatim_is_flagged():
    data = {
        "items": [
            _item("A-1", "REM", 12, 12, "손해배상의 상한은 매매대금의 10%로 한다."),
            _item("A-2", "REM", 12, 12, "손해배상의 상한은  매매대금의 10%로 한다."),
        ]
    }
    findings = oversegmentation_issues(data)
    dupes = [f for f in findings if f["code"] == "duplicate_verbatim"]
    assert len(dupes) == 1
    assert sorted(dupes[0]["detail"]["item_refs"]) == ["A-1", "A-2"]


def test_normal_document_produces_no_oversegmentation_finding():
    data = {
        "items": [
            _item("N-1", "RW", 10, 10, "대상회사는 조세를 성실히 납부하였다."),
            _item("N-2", "RW", 11, 12, "다만 진행 중인 세무조사가 1건 있다."),
            _item("N-3", "COV", 20, 21, "매도인은 통상적인 영업을 유지한다."),
        ]
    }
    assert oversegmentation_issues(data) == []
