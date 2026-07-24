from run_v4_pilot_60 import (
    allocate_quotas,
    locate_family_ranges,
    normalize_title,
)


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
