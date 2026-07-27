from index_contracts import classify_path, load_type_rules


def test_cb_purchase_and_warrant_purchase_are_distinct_contract_types():
    rules = load_type_rules()
    cb = classify_path(
        "05-4_CB매수계약_국문/Nature_CB매매계약_체결본.docx",
        "",
        rules,
    )
    warrant = classify_path(
        "06-3_W_매수계약/Broccoli_Warrant Purchase Agreement.docx",
        "",
        rules,
    )
    assert cb[0] == "CB매수"
    assert warrant[0] == "W매수"


def test_cbsa_bwsa_and_ebsa_acronyms_are_in_full_v4_scope():
    rules = load_type_rules()
    assert classify_path("incoming/Issuer_CBSA_execution.docx", "", rules)[0] == "CB인수"
    assert classify_path("incoming/Issuer_BWSA_execution.docx", "", rules)[0] == "BW인수"
    assert classify_path("incoming/Issuer_EBSA_execution.docx", "", rules)[0] == "EB인수"
