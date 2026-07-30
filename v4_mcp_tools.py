"""Optional MCP registration for V4 atomic proposition tools.

This module has no hard dependency on the MCP package. Pass any FastMCP-like
object exposing ``tool(...)`` and the two read-only tools are registered.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from v4_search import (
    compare_clause_items,
    log_v4_query,
    search_clause_absence,
    search_clause_items,
)


class V4McpService:
    def __init__(self, out: Path):
        self.out = Path(out)

    def search_clause_items(
        self,
        taxonomy_id: str,
        polarity: Optional[str] = None,
        subject: Optional[str] = None,
        effective_time: Optional[str] = None,
        text: Optional[str] = None,
        ctype: Optional[str] = None,
        lang: Optional[str] = None,
        version: Optional[str] = None,
        include_descendants: bool = True,
        item_absent: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search atomic propositions or safely classified absence.

        A version filter never silently omits: the result carries
        ``version_filter_notice`` with the unknown / partially-unknown /
        low-confidence population that did not match."""
        if item_absent:
            return search_clause_absence(
                self.out,
                taxonomy_id,
                polarity=polarity,
                ctype=ctype,
                lang=lang,
                version=version,
                include_descendants=include_descendants,
                limit=limit,
            )
        result = search_clause_items(
            self.out,
            taxonomy_id,
            polarity=polarity,
            subject=subject,
            effective_time=effective_time,
            text=text,
            ctype=ctype,
            lang=lang,
            version=version,
            include_descendants=include_descendants,
            limit=limit,
            offset=offset,
        )
        # Real-usage signal for the §9.6 / T4 decision: how often does a query arrive
        # concept-only (no text), and how large is the node it hits? File append only.
        log_v4_query(self.out, {
            "tool": "search_clause_items",
            "taxonomy_id": taxonomy_id,
            "has_text": bool(text and text.strip()),
            "narrowed_by": [k for k, v in (
                ("text", text), ("subject", subject), ("polarity", polarity),
                ("effective_time", effective_time), ("ctype", ctype),
                ("lang", lang), ("version", version),
            ) if v],
            "population": result.get("total_items"),
            "low_query_signal": "low_query_signal" in result,
            "offset": offset,
        })
        return result

    def compare_clause_items(
        self,
        taxonomy_id: str,
        file_keys: list[str],
        polarity: Optional[str] = None,
        include_descendants: bool = True,
    ) -> dict[str, Any]:
        """Compare one atomic proposition across two to ten contracts."""
        return compare_clause_items(
            self.out,
            taxonomy_id,
            file_keys,
            polarity=polarity,
            include_descendants=include_descendants,
        )


def register_v4_tools(mcp: Any, out: Path, annotations: Any = None) -> V4McpService:
    """Register the two V4 tools without changing any existing MCP tools."""
    service = V4McpService(out)
    options = {"annotations": annotations} if annotations is not None else {}

    @mcp.tool(
        name="search_clause_items",
        title="V4 원자 명제 검색",
        structured_output=True,
        **options,
    )
    def search_tool(
        taxonomy_id: str,
        polarity: Optional[str] = None,
        subject: Optional[str] = None,
        effective_time: Optional[str] = None,
        text: Optional[str] = None,
        ctype: Optional[str] = None,
        lang: Optional[str] = None,
        version: Optional[str] = None,
        include_descendants: bool = True,
        item_absent: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search approved V4 atomic items. text is not just a filter but the RANKING signal: a bare concept query (taxonomy_id only) returns the whole node's items in document order (unranked enumeration — a node holds hundreds to thousands of items), so ALWAYS pass the user query's distinctive keywords as text. text is whitespace-tokenized (each token must appear in the item's verbatim or proposition — keyword-style, not an exact quote); tokens >=3 chars use the FTS trigram index and rank by a contiguous-phrase hit then bm25 (relevance + IDF), shorter tokens fall back to a substring scan. Ranking engages only when text is present; subject / polarity / ctype / lang narrow further. If a result carries low_query_signal (population N), the query was too broad — re-issue with the user's keywords. If it carries zero_result_hint, the AND of keywords matched nothing (that is NOT clause absence) — drop or change a keyword and retry. When structured search returns 0 or very few hits for a concept you expect to exist, also run the paragraph/document search (search_contracts) and report those as needs_review beside the structured hits rather than concluding absence — the two paths are complementary (§4 hybrid). If item_absent is true, only complete current body/annex coverage can produce confirmed_absent; all other non-matches are needs_review. version filters by contract version-role (execution/buyer_draft/... or Korean labels, comma-separated). That role is a FILENAME HEURISTIC, so a version-filtered call also returns version_filter_notice (excluded_unknown / excluded_partial / excluded_low_confidence / review_candidates): report those counts and never present the result as the complete population of that version. Rows carry version_confidence (high/med/low; null = not backfilled), version_basis and version_review_required — treat true as 확인 필요."""
        return service.search_clause_items(
            taxonomy_id,
            polarity=polarity,
            subject=subject,
            effective_time=effective_time,
            text=text,
            ctype=ctype,
            lang=lang,
            version=version,
            include_descendants=include_descendants,
            item_absent=item_absent,
            limit=limit,
            offset=offset,
        )

    @mcp.tool(
        name="compare_clause_items",
        title="V4 원자 명제 계약 비교",
        structured_output=True,
        **options,
    )
    def compare_tool(
        taxonomy_id: str,
        file_keys: list[str],
        polarity: Optional[str] = None,
        include_descendants: bool = True,
    ) -> dict[str, Any]:
        """Compare an atomic item across 2-10 contracts as confirmed_present, confirmed_absent, or needs_review, with verbatim evidence and coverage."""
        return service.compare_clause_items(
            taxonomy_id,
            file_keys,
            polarity=polarity,
            include_descendants=include_descendants,
        )

    return service
