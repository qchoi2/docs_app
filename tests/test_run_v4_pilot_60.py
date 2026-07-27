from run_v4_pilot_60 import (
    allocate_quotas,
    locate_family_ranges,
    normalize_title,
    repair_family_sections,
)
from v4_schema import FAMILIES


def paragraphs(*texts):
    return [
        {"para": index, "text": text}
        for index, text in enumerate(texts, 1)
    ]


def test_allocate_quotas_is_proportional_and_exact():
    quotas = allocate_quotas(
        {("SPA", "국문"): 16, ("SPA", "영문"): 17, ("SSA", "국문"): 4},
        target=30,
    )
    assert sum(quotas.values()) == 30
    assert quotas[("SPA", "영문")] >= quotas[("SPA", "국문")]
    assert quotas[("SSA", "국문")] > 0


def test_article_mode_closes_each_family_at_next_article():
    rows = paragraphs(
        "ARTICLE 1. DEFINITIONS",
        '"Business Day" means a day other than Saturday or Sunday.',
        "ARTICLE 2. PURCHASE PRICE",
        "The purchase price is USD 100.",
        "ARTICLE 3. REPRESENTATIONS AND WARRANTIES",
        "The Seller is duly organized.",
        "ARTICLE 4. COVENANTS",
        "The Seller shall operate in the ordinary course.",
        "ARTICLE 5. CONDITIONS PRECEDENT",
        "All approvals shall have been obtained.",
        "ARTICLE 6. INDEMNIFICATION",
        "The Seller shall indemnify the Buyer.",
        "ARTICLE 7. TERMINATION",
    )
    ranges = locate_family_ranges(rows)
    assert ranges["DEF"] == [(1, 2)]
    assert ranges["PAY"] == [(3, 4)]
    assert ranges["RW"] == [(5, 6)]
    assert ranges["COV"] == [(7, 8)]
    assert ranges["CP"] == [(9, 10)]
    assert ranges["REM"] == [(11, 12)]


def test_later_schedule_articles_do_not_erase_main_agreement_headings():
    rows = paragraphs(
        "DEFINITIONS",
        '"Business Day" means a weekday.',
        "REPRESENTATIONS AND WARRANTIES OF THE COMPANY",
        "The Company is duly organized.",
        "COVENANTS",
        "The Company shall operate in the ordinary course.",
        "CONDITIONS PRECEDENT",
        "All approvals shall have been obtained.",
        "INDEMNIFICATION",
        "The Seller shall indemnify the Buyer.",
        "SCHEDULE 1",
        "Article 1 (Voting Rights)",
        "Each share carries one vote.",
        "Article 2 (Dividends)",
        "Dividends shall be paid pro rata.",
        "Article 3 (Conversion)",
        "The preferred shares may be converted.",
    )
    ranges = locate_family_ranges(rows)
    assert ranges["DEF"] == [(1, 2)]
    assert ranges["RW"] == [(3, 4)]
    assert ranges["COV"] == [(5, 6)]
    assert ranges["CP"] == [(7, 8)]
    assert ranges["REM"] == [(9, 10)]


def test_table_of_contents_hit_is_not_used_as_actual_article():
    rows = paragraphs(
        "Interpretation ........................................ 1",
        "Purchase Price ....................................... 4",
        "Conditions Precedent to Completion ................... 5",
        "Warranties of Sellers ............................... 8",
        "Limitations on Claims against the Sellers ........... 9",
        "Undertakings ........................................ 10",
        "1.",
        "Interpretation",
        '"Business Day" means a weekday.',
        "2.",
        "Purchase Price",
        "The consideration is USD 100.",
        "3.",
        "Conditions Precedent to Completion",
        "Regulatory approval must be obtained.",
        "4.",
        "Warranties of Sellers",
        "The Seller has capacity.",
        "5.",
        "Limitations on Claims against the Sellers",
        "Liability shall not exceed USD 10.",
        "6.",
        "Undertakings",
        "The Seller shall cooperate.",
        "7.",
        "Completion",
    )
    ranges = locate_family_ranges(rows)
    assert ranges["DEF"][0][0] == 8
    assert ranges["PAY"][0][0] == 11
    assert ranges["CP"][0][0] == 14
    assert ranges["RW"][0][0] == 17
    assert ranges["REM"][0][0] == 20
    assert ranges["COV"][0][0] == 23


def test_normalize_title_removes_leader_and_page_number():
    assert normalize_title("Purchase Price ............... 25") == "purchaseprice"


def test_headingless_document_preserves_unscoped_physical_paragraphs():
    rows = paragraphs(
        "CONVERTIBLE BOND SUBSCRIPTION AGREEMENT",
        "The Company shall issue the Bonds to the Investor.",
    )
    payload = {
        "family_sections": {
            family: {"paragraphs": [], "atomic_unit_hints": []}
            for family in FAMILIES
        },
        "source_inventory": [],
    }

    repaired = repair_family_sections(
        payload,
        {
            "file_key": "doc1",
            "path": "CBSA.docx",
            "paragraphs": rows,
        },
    )

    assert repaired["unscoped_body_paragraphs"] == rows
