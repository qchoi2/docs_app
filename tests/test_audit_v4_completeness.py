from audit_t3_v4 import document_coverage_issues, paragraph_map
from v4_schema import FAMILIES


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
