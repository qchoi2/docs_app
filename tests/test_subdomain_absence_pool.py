from subdomain_absence_pool import derive_terms
from lib.absence_net import _drop_high_df


MAPPING = {
    "mappings": {
        "인사노무진술": ["RW.LABOR"],
        "조세진술": ["RW.TAX"],
        "환경개인정보진술": ["RW.ENVIRONMENT", "RW.PRIVACY"],
        "무관한개념": ["COV.SHA.TAG_ALONG"],
    }
}
TERM_DICT = {
    "terms": [
        {"canonical": "인사노무진술", "ko": ["인사", "노무", "근로계약"],
         "en": ["labor", "employment"]},
        {"canonical": "조세진술", "ko": ["조세", "세금"], "en": ["tax", "taxes"]},
        {"canonical": "환경개인정보진술", "ko": ["환경법규"], "en": ["environmental matters"]},
    ]
}


def test_derive_terms_pulls_mapped_canonical_synonyms():
    ko, en, canon = derive_terms("RW.LABOR", MAPPING, TERM_DICT, supplements={})
    assert canon == ["인사노무진술"]
    assert "인사" in ko and "노무" in ko and "근로계약" in ko
    assert "labor" in en and "employment" in en
    # unrelated canonical's terms must not leak in
    assert "tax" not in en and "조세" not in ko


def test_derive_terms_merges_supplements_and_routes_by_script():
    supp = {"RW.LABOR": {"ko": ["임금체불"], "en": ["strike"]}}
    ko, en, _ = derive_terms("RW.LABOR", MAPPING, TERM_DICT, supplements=supp)
    assert "임금체불" in ko
    assert "strike" in en


def test_derive_terms_drops_short_latin_needles():
    # a 2-char latin term would fire on unrelated substrings; excluded by _EN_MIN_LEN
    td = {"terms": [{"canonical": "조세진술", "ko": ["조세"], "en": ["MA", "taxes"]}]}
    _ko, en, _ = derive_terms("RW.TAX", MAPPING, td, supplements={})
    assert "taxes" in en and "ma" not in en


def test_derive_terms_empty_when_no_mapping_or_supplement():
    ko, en, canon = derive_terms("RW.AUTHORITY", MAPPING, TERM_DICT, supplements={})
    assert ko == [] and en == [] and canon == []


def test_drop_high_df_removes_generic_needles_keeps_distinctive():
    # 'material'/'agreement' fire in nearly every contract -> non-discriminating; a
    # distinctive term like 'encumbrance' stays. Needles absent from the cache are kept.
    df = {"material": 0.82, "agreement": 0.91, "encumbrance": 0.07, "환경": 0.68}
    kept = _drop_high_df(["material", "agreement", "encumbrance", "environmental"], df)
    assert kept == ["encumbrance", "environmental"]   # environmental unknown -> kept
    assert _drop_high_df(["환경", "오염"], df) == ["오염"]  # 환경(경영환경) dropped


def test_derive_terms_includes_subtree_mappings():
    mapping = {"mappings": {"오염진술": ["RW.ENVIRONMENT.CONTAMINATION"]}}
    td = {"terms": [{"canonical": "오염진술", "ko": ["오염"], "en": []}]}
    ko, _en, canon = derive_terms("RW.ENVIRONMENT", mapping, td, supplements={})
    # a mapping to a node in the subtree still contributes
    assert canon == ["오염진술"] and "오염" in ko
