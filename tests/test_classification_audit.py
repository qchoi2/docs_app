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


def test_buyer_side_covenant_is_kept():
    # a buyer/양수인 non-compete is still a covenant, not a disclosure rep
    v = ("양수인은 본 계약 체결일로부터 10년간, 양도인 사업분야 내에서 에스테틱 의약성분을 함유한 "
         "제품을 직접 또는 간접적으로 개발, 생산, 상업화할 수 없다.")
    assert classify_verbatim("COV.NON_COMPETE", v) == "keep"


def test_long_noncompete_frame_is_kept():
    # subject + from-closing + N years frame => covenant even if the verb is far away
    v = ("경업금지. 매도인들은 거래종결일로부터 10년 동안, 매도인들이 직접 또는 그 특수관계인을 통하여 "
         "간접적으로, 매수인의 사전 서면 동의 없이는 대상회사가 영위하는 사업과 경쟁하는 행위를 한다.")
    assert classify_verbatim("COV.NON_COMPETE", v) == "keep"


def test_disclosure_rep_with_no_obligation_still_reclassifies():
    # widening 'keep' must not steal a mood-less disclosure rep from 'reclassify'
    v = ("대상회사가 당사자로서 경업금지, 비밀유지 조항을 포함하고 있는 계약의 완전한 목록은 "
         "공개목록에 첨부되어 있으며 모두 유효하다.")
    assert classify_verbatim("COV.NON_COMPETE", v) == "reclassify"


def test_material_contracts_disclosure_rep_reclassifies():
    v = ("계약: 대상회사가 당사자인 중요 계약은 모두 적법하게 체결되어 유효하며 대상회사와 상대방 "
         "당사자의 법률적으로 구속력 있는 의무를 구성하고, 관련 법률에 부합한다.")
    assert classify_verbatim("COV.NON_COMPETE", v) == "reclassify"


def test_toc_section_list_is_noise():
    v = ("6.01 COOPERATION; FURTHER ASSURANCE. 6.02 GOVERNMENTAL APPROVALS. "
         "6.03 CONDUCT OF BUSINESS PRIOR TO CLOSING. 6.04 ACCESS.")
    assert classify_verbatim("COV.NON_COMPETE", v) == "noise"


def test_seller_covenant_mentioning_contracts_still_kept():
    # a covenant that happens to mention 중요계약 must not be pulled into reclassify —
    # keep is checked first and the obligation mood is present
    v = "매도인은 거래종결 후 5년간 대상회사의 중요계약과 경쟁하는 사업을 영위할 수 없다."
    assert classify_verbatim("COV.NON_COMPETE", v) == "keep"


def test_unknown_node_is_review():
    assert classify_verbatim("RW.TAX", "anything") == "review"
