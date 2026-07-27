from tests.test_v4_search import make_index
from v4_mcp_tools import register_v4_tools


class FakeMcp:
    def __init__(self):
        self.tools = {}
        self.options = {}

    def tool(self, **options):
        def decorate(function):
            self.tools[options["name"]] = function
            self.options[options["name"]] = options
            return function
        return decorate


def test_registers_two_read_only_compatible_tools(tmp_path):
    out = make_index(tmp_path)
    mcp = FakeMcp()
    register_v4_tools(mcp, out, annotations={"readOnlyHint": True})
    assert set(mcp.tools) == {"search_clause_items", "compare_clause_items"}
    assert mcp.options["search_clause_items"]["structured_output"] is True
    assert mcp.options["search_clause_items"]["annotations"]["readOnlyHint"] is True

    result = mcp.tools["search_clause_items"](
        "RW.LABOR.NO_VIOLATION", polarity="none_exist"
    )
    assert result["total_documents"] == 1


def test_mcp_absence_preserves_needs_review(tmp_path):
    out = make_index(tmp_path)
    mcp = FakeMcp()
    register_v4_tools(mcp, out)
    # CP (non-gated) still confirms absence via the MCP adapter.
    result = mcp.tools["search_clause_items"](
        "CP.THIRD_PARTY_CONSENT", item_absent=True
    )
    assert result["confirmed_absent_count"] == 1
    assert result["needs_review_count"] == 1
    # RW absence is demoted (coverage unverified).
    rw = mcp.tools["search_clause_items"](
        "RW.LABOR.NO_VIOLATION", item_absent=True
    )
    assert rw["confirmed_absent_count"] == 0


def test_mcp_compare_returns_three_states(tmp_path):
    out = make_index(tmp_path)
    mcp = FakeMcp()
    register_v4_tools(mcp, out)
    result = mcp.tools["compare_clause_items"](
        "RW.LABOR.NO_VIOLATION", ["a" * 16, "b" * 16, "c" * 16]
    )
    assert [item["state"] for item in result["comparison"]] == [
        "confirmed_present",
        "confirmed_absent",
        "needs_review",
    ]
