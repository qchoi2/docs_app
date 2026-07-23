import sqlite3

from propose_v4_remaining_nine import (
    build_result,
    load_nodes,
    paragraph_matches,
    polarity,
)
from v4_schema import initialize_v4_schema, validate_v4_result


def _payload():
    return {
        "file_key": "test-file",
        "taxonomy_version": 1,
        "family_sections": {
            "RW": {
                "paragraphs": [
                    {"para": 10, "text": "회사는 임직원에 대한 미지급 보수 없음이라고 확인한다."}
                ],
                "atomic_unit_hints": [
                    {
                        "unit_id": "rw-1",
                        "loc_start": 10,
                        "loc_end": 10,
                        "heading": "미지급 보수",
                    }
                ],
            },
            "CP": {"paragraphs": [], "atomic_unit_hints": []},
            "COV": {"paragraphs": [], "atomic_unit_hints": []},
            "DEF": {"paragraphs": [], "atomic_unit_hints": []},
            "PAY": {"paragraphs": [], "atomic_unit_hints": []},
            "REM": {"paragraphs": [], "atomic_unit_hints": []},
        },
        "source_inventory": [],
    }


def test_alias_proposal_is_schema_valid_and_kept_for_review():
    conn = sqlite3.connect(":memory:")
    initialize_v4_schema(conn)
    nodes, _index = load_nodes(conn)
    payload = _payload()

    result = build_result(payload, nodes)

    assert result["items"]
    assert any(
        row["taxonomy_id"] == "RW.LABOR.UNPAID_COMPENSATION"
        for row in result["items"]
    )
    assert all(row["review_status"] == "needs_review" for row in result["items"])
    assert result["coverage"]["RW"]["body_status"] == "partial"
    known = {
        taxonomy_id: family
        for taxonomy_id, family in conn.execute(
            "SELECT taxonomy_id,family FROM v4_taxonomy_node"
        )
    }
    validate_v4_result(result, file_key="test-file", known_taxonomy=known)


def test_matcher_and_polarity_are_conservative():
    conn = sqlite3.connect(":memory:")
    initialize_v4_schema(conn)
    nodes, _index = load_nodes(conn)

    matches = paragraph_matches(
        "대상회사는 미지급 보수 없음이라고 진술한다.",
        "RW",
        nodes,
    )

    assert any(row[0] == "RW.LABOR.UNPAID_COMPENSATION" for row in matches)
    assert polarity("미지급 보수가 없다.") == "none_exist"
    assert polarity("당사자는 비밀을 공개하여서는 아니 된다.") == "negative"
