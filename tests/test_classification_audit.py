from lib.classification_audit import classify_verbatim


def test_disclosure_rep_is_reclassified():
    # a descriptive noun-phrase enumerating the target's contracts -> RW.CONTRACTS
    v = "경업금지, 비밀유지 조항을 포함하고 있거나 달리 회사가 자유롭게 사업을 영위할 수 없도록 하는 조항을 포함하고 있는 계약"
    assert classify_verbatim("COV.NON_COMPETE", v) == "reclassify"
    en = "Contracts containing any non-compete provision restricting the Company from competing"
    assert classify_verbatim("COV.NON_COMPETE", en) == "reclassify"


def test_seller_covenant_is_kept():
    v = "매도인들은 거래종결일로부터 오(5)년간 국내에서 경업금지대상사업을 영위할 수 없다."
    assert classify_verbatim("COV.NON_COMPETE", v) == "keep"


def test_covenant_that_mentions_contract_is_not_reclassified():
    # promissory mood present -> never auto-moved even though '계약' appears (protects
    # buyer-side / oddly-phrased covenants the subject list would miss)
    v = "매도인은 경업금지 조항을 포함하는 계약을 체결하여서는 아니 된다."
    assert classify_verbatim("COV.NON_COMPETE", v) != "reclassify"


def test_toc_heading_is_noise():
    assert classify_verbatim("COV.NON_COMPETE", "Section 4.24. Non-Compete 27") == "noise"
    assert classify_verbatim("COV.NON_COMPETE", "13.3 Non-Compete; Non-Solicitation.") == "noise"


def test_uncertain_goes_to_review_not_reclassify():
    # buyer-side restriction (no 매도인 subject, no clean disclosure phrase) -> review
    v = "양수인은 본 계약 체결일로부터 10년간 양도인 사업분야 내에서 제품을 개발 또는 생산할 수 없다"
    assert classify_verbatim("COV.NON_COMPETE", v) in ("review", "keep")
    assert classify_verbatim("COV.NON_COMPETE", v) != "reclassify"


def test_unknown_node_is_review():
    assert classify_verbatim("RW.TAX", "anything") == "review"
