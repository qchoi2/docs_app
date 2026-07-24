from finalize_v4_remaining_nine import (
    classify_text,
    defined_term,
    definition_taxonomy,
    reject_as_non_atomic,
)


def test_definition_classifier_uses_defined_term_not_incidental_terms():
    text = (
        '"Applicable Exchange Rate" shall mean the first USD/KRW exchange '
        "rate published on the Business Day before payment."
    )
    term = defined_term(text)
    assert term == "Applicable Exchange Rate"
    assert definition_taxonomy(term, text) == "DEF.CONTRACT_TERM"


def test_korean_quoted_definitions_map_to_asset_and_liability_leaves():
    asset = (
        '(a) "해당 인수대상자산"이란 부록에 명시된 자산을 포함한 '
        "인수대상자산을 의미한다."
    )
    liability = (
        '(b) "해당 인수대상채무"란 부록에 명시된 채무를 포함한 '
        "인수대상채무를 의미한다."
    )
    assert classify_text(asset) == ["DEF.PURCHASED_ASSETS"]
    assert classify_text(liability) == ["DEF.ASSUMED_LIABILITIES"]
    business_day = '"영업일"은 토요일, 일요일 및 공휴일을 제외한 날을 의미한다.'
    assert defined_term(business_day) == "영업일"
    assert classify_text(business_day) == ["DEF.BUSINESS_DAY"]


def test_new_v10_and_v11_leaf_classifications():
    assert classify_text(
        "본 계약 관련 세금 및 비용은 각 당사자가 각자 부담한다."
    ) == ["PAY.TRANSACTION_COSTS"]
    assert classify_text(
        "본 계약은 대한민국 법규에 의하여 규율, 해석 및 집행된다."
    ) == ["REM.GOVERNING_LAW"]
    assert classify_text(
        "정부기관의 승인을 거래종결 전에 취득하여야 한다."
    ) == ["CP.GOVERNMENT_APPROVAL.GENERAL"]


def test_v12_buyer_condition_and_earnout_classifications():
    assert classify_text(
        "매수인은 매매대금을 지급할 충분한 자금을 보유한다."
    ) == ["RW.BUYER.SUFFICIENT_FUNDS"]
    assert classify_text(
        "매수인은 독자적인 평가에 기초하여 거래를 결정하였다."
    ) == ["RW.BUYER.INDEPENDENT_INVESTIGATION"]
    assert classify_text(
        "매수인은 명시된 진술 외의 자료에 의존하지 아니하였다."
    ) == ["RW.BUYER.NO_RELIANCE"]
    assert classify_text(
        "본건 소수지분 매매계약이 유효하게 체결되고 본건 거래와 동시에 종결될 것."
    ) == ["CP.ANCILLARY.TRANSACTION_CLOSING"]
    assert classify_text(
        "최종 매매대금이 확정되고 매매대금 조정 절차가 완료될 것."
    ) == ["CP.PURCHASE_PRICE_ADJUSTMENT"]
    assert classify_text(
        "Additional Consideration shall be paid within five Business Days."
    ) == ["PAY.EARNOUT.PAYMENT"]


def test_assignment_and_contract_compliance_are_reclassified_by_context():
    assert classify_text(
        "상대방의 사전 서면 동의 없이는 본 계약상 권리 또는 의무를 "
        "제3자에게 양도 또는 이전할 수 없다."
    ) == ["COV.ASSIGNMENT"]
    assert classify_text(
        "각 계약의 상대방은 계약상의 약정을 준수하고 있으며 장래에도 "
        "이를 위반할 사정은 존재하지 않는다."
    ) == ["RW.CONTRACTS.NO_DEFAULT"]


def test_lead_ins_and_signature_blocks_are_rejected_as_non_atomic():
    assert reject_as_non_atomic(
        "매도인은 별지 6에 기재된 바와 같이 진술 및 보장한다."
    )
    assert reject_as_non_atomic(
        "본 계약이 적법하게 체결되었음을 증명하기 위하여 당사자들은 "
        "본 계약서에 기명날인한다."
    )
