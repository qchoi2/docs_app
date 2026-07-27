"""Read-only MCP adapter for the local M&A contract search corpus.

The web app remains the owner of indexing, settings, and other write paths.
This adapter exposes the existing deterministic search/read functions to an
AI client over local stdio. The MCP dependency is optional; the web app and
CLI continue to work with requirements.txt alone.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, List, Optional

from inspect_file import inspect_file
from lib.console import configure_utf8_stdio
from open_text import open_text
from read_contract import read_contract
from search_contracts import connect_search_db, search_contracts as run_contract_search


FILE_KEY_RE = re.compile(r"^[0-9a-f]{16}$")
EXPAND_MODES = {"strict", "normal", "broad"}
MAX_KEYWORDS = 10
MAX_RESULTS = 30
MAX_SEARCH_CONTEXT = 3
MAX_READ_CONTEXT = 5

SERVER_INSTRUCTIONS = """
이 서버는 현재 색인된 M&A 계약서 샘플 코퍼스의 검색·부분 정독 도구다.
법률 자문을 제공하지 않는다. 답변할 때 다음 원칙을 지켜라.
1. 사실·수치·조항 내용마다 [file_key]를 붙이고 필요한 원문만 짧게 인용한다.
2. 검색 결과의 why, score_breakdown, snippet_paras, clause 근거를 우선 사용한다.
3. 조항 부재는 키워드 미검출로 단정하지 말고 clause_absent=true 결과만 사용한다.
4. 미평가와 평가 후 부재를 구분하고 confidence=low 또는 stale은 확인 필요로 표시한다.
5. 중복 제거가 기본이며 요청 개수를 정확히 맞춘다. 부족하면 확인된 수만 명시한다.
6. 후보가 30건을 넘으면 조건을 더 좁힌다. 한 답변에서 조항 정독은 5건 이내가 기본이다.
7. status=empty/error 문서는 본문 검색 불가 문서로 고지한다.
8. 웹앱이 색인·설정·저장 작업을 담당한다. 이 MCP 서버는 코퍼스를 변경하지 않는다.
""".strip()


class McpServiceError(ValueError):
    """Safe validation/configuration error suitable for an MCP tool result."""


def _public_result(value: Any) -> Any:
    """Remove local cache locations while preserving citation evidence."""
    if isinstance(value, dict):
        return {
            key: _public_result(item)
            for key, item in value.items()
            if key not in {"txt_path", "out"}
        }
    if isinstance(value, list):
        return [_public_result(item) for item in value]
    return value


class ContractMcpService:
    """Pure service layer used by the MCP transport and deterministic tests."""

    def __init__(self, out: Path):
        raw = str(out)
        if raw.startswith("\\\\") or raw.startswith("//"):
            raise McpServiceError("cs_index must be on a local disk, not a network share")
        self.out = Path(out).resolve()
        if not (self.out / "catalog.sqlite").exists():
            raise McpServiceError("catalog.sqlite not found in the configured cs_index")

    def _connect(self) -> sqlite3.Connection:
        conn = connect_search_db(self.out / "catalog.sqlite", read_only=True)
        conn.row_factory = sqlite3.Row
        return conn

    def _file_key(self, value: str) -> str:
        if not isinstance(value, str) or not FILE_KEY_RE.fullmatch(value):
            raise McpServiceError("file_key must be 16 lowercase hexadecimal characters")
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT 1 FROM files WHERE file_key=? AND status!='missing'", (value,)
            ).fetchone()
        if row is None:
            raise McpServiceError("file_key is not present in the current catalog")
        return value

    @staticmethod
    def _bounded_int(value: int, name: str, low: int, high: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise McpServiceError("%s must be between %d and %d" % (name, low, high))
        return value

    def search(
        self,
        keywords: Optional[List[str]] = None,
        ctype: Optional[str] = None,
        lang: Optional[str] = None,
        clause: Optional[str] = None,
        clause_absent: bool = False,
        expand: str = "normal",
        no_expand: bool = False,
        exclude_drafts: bool = False,
        show_duplicates: bool = False,
        limit: int = 10,
        context: int = 1,
        party_name: Optional[str] = None,
        party_role: Optional[str] = None,
        payment_method: Optional[str] = None,
        amount_min: Optional[float] = None,
        amount_max: Optional[float] = None,
        cap_pct_min: Optional[float] = None,
        cap_pct_max: Optional[float] = None,
        survival_months_min: Optional[int] = None,
        survival_months_max: Optional[int] = None,
        governing_law: Optional[str] = None,
        forum: Optional[str] = None,
    ) -> Dict[str, Any]:
        terms = keywords or []
        if not isinstance(terms, list) or any(not isinstance(item, str) for item in terms):
            raise McpServiceError("keywords must be a list of strings")
        terms = [item.strip() for item in terms if item.strip()]
        if len(terms) > MAX_KEYWORDS:
            raise McpServiceError("keywords accepts at most %d terms" % MAX_KEYWORDS)
        if expand not in EXPAND_MODES:
            raise McpServiceError("expand must be strict, normal, or broad")
        if clause_absent and not clause:
            raise McpServiceError("clause is required when clause_absent is true")
        limit = self._bounded_int(limit, "limit", 1, MAX_RESULTS)
        context = self._bounded_int(context, "context", 0, MAX_SEARCH_CONTEXT)

        result, _returned = run_contract_search(
            self.out,
            ctype=ctype or None,
            lang=lang or None,
            keywords=terms,
            limit=limit,
            context=context,
            expand=expand,
            no_expand=no_expand,
            exclude_drafts=exclude_drafts,
            show_duplicates=show_duplicates,
            read_only=True,
            clause=clause or None,
            clause_present=bool(clause and not clause_absent),
            clause_absent=clause_absent,
            party_name=party_name,
            party_role=party_role,
            payment_method=payment_method,
            amount_min=amount_min,
            amount_max=amount_max,
            cap_pct_min=cap_pct_min,
            cap_pct_max=cap_pct_max,
            survival_months_min=survival_months_min,
            survival_months_max=survival_months_max,
            governing_law=governing_law,
            forum=forum,
        )
        result["mcp_guidance"] = {
            "citation_format": "[file_key]",
            "corpus_scope": "현재 색인된 문서 기준",
            "deduplicated": not show_duplicates,
            "narrow_before_reading": int(result.get("total", 0)) > MAX_RESULTS,
            "absence_rule": "키워드 미검출은 부재 증명이 아님",
        }
        return _public_result(result)

    def read_clause(self, file_key: str, section: str, context: int = 0) -> Dict[str, Any]:
        key = self._file_key(file_key)
        if not isinstance(section, str) or not section.strip():
            raise McpServiceError("section is required")
        context = self._bounded_int(context, "context", 0, MAX_READ_CONTEXT)
        try:
            result = read_contract(self.out, key, section.strip(), context)
        except (KeyError, ValueError, FileNotFoundError) as exc:
            raise McpServiceError(str(exc)) from None
        return _public_result(result)

    def read_context(
        self,
        file_key: str,
        para: Optional[int] = None,
        search: Optional[str] = None,
        context: int = 2,
    ) -> Dict[str, Any]:
        key = self._file_key(file_key)
        has_search = isinstance(search, str) and bool(search.strip())
        if (para is None) == (not has_search):
            raise McpServiceError("provide exactly one of para or search")
        if para is not None:
            para = self._bounded_int(para, "para", 1, 10_000_000)
        search_term = search.strip() if has_search else None
        context = self._bounded_int(context, "context", 0, MAX_READ_CONTEXT)
        try:
            result = open_text(self.out, key, para=para, search=search_term, context=context)
        except (KeyError, ValueError, FileNotFoundError) as exc:
            raise McpServiceError(str(exc)) from None
        return _public_result(result)

    def inspect(self, file_key: str, include_duplicate_members: bool = False) -> Dict[str, Any]:
        key = self._file_key(file_key)
        try:
            result = inspect_file(self.out, key, show_dup_group=include_duplicate_members)
        except (KeyError, ValueError, FileNotFoundError) as exc:
            raise McpServiceError(str(exc)) from None
        return _public_result(result)

    def duplicates(self, file_key: str) -> Dict[str, Any]:
        key = self._file_key(file_key)
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT dup_group FROM files WHERE file_key=?", (key,)
            ).fetchone()
            dup_group = row["dup_group"] or key
            members = conn.execute(
                """
                SELECT file_key, path, status, is_draft, version_hint
                FROM files WHERE dup_group=? ORDER BY path, file_key
                """,
                (dup_group,),
            ).fetchall()
        return {
            "file_key": key,
            "dup_group": dup_group,
            "count": len(members),
            "members": [dict(member) for member in members],
        }

    def corpus_status(self) -> Dict[str, Any]:
        with closing(self._connect()) as conn:
            statuses = dict(
                conn.execute("SELECT status, COUNT(*) FROM files GROUP BY status").fetchall()
            )
            batches = dict(
                conn.execute(
                    """
                    SELECT COALESCE(batch_label, ''), COUNT(*)
                    FROM files WHERE status!='missing' GROUP BY batch_label
                    """
                ).fetchall()
            )
            last_indexed = conn.execute("SELECT MAX(indexed_at) FROM files").fetchone()[0]
            unsearchable = conn.execute(
                "SELECT COUNT(*) FROM files WHERE status IN ('empty','error')"
            ).fetchone()[0]
            searchable = conn.execute(
                "SELECT COUNT(*) FROM files WHERE status='ok'"
            ).fetchone()[0]
        labels = [label for label in batches if label]
        return {
            "statuses": statuses,
            "batch_labels": batches,
            "last_indexed_at": last_indexed,
            "searchable_docs": searchable,
            "unsearchable_docs": unsearchable,
            "pilot_corpus": bool(labels) and all(label.startswith("pilot") for label in labels),
            "scope_label": "현재 색인된 문서 기준",
        }

    def facets(self) -> Dict[str, Any]:
        with closing(self._connect()) as conn:
            result: Dict[str, Any] = {}
            for column in ("ctype", "lang", "batch_label"):
                rows = conn.execute(
                    "SELECT %s, COUNT(*) FROM files WHERE status!='missing' "
                    "GROUP BY %s ORDER BY COUNT(*) DESC, %s" % (column, column, column)
                ).fetchall()
                result[column] = [
                    {"value": row[0], "count": row[1]} for row in rows if row[0]
                ]
        return result


def build_mcp(service: ContractMcpService):
    """Build the optional FastMCP transport around the shared service."""
    try:
        from mcp.server.fastmcp import FastMCP
        from mcp.types import ToolAnnotations
    except ModuleNotFoundError as exc:
        raise McpServiceError(
            "MCP dependency is not installed; run: python -m pip install -r requirements-mcp.txt"
        ) from exc

    mcp = FastMCP("M&A Contract Search", instructions=SERVER_INSTRUCTIONS)
    read_only = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @mcp.tool(
        name="search_contracts",
        title="계약서 검색",
        annotations=read_only,
        structured_output=True,
    )
    def search_tool(
        keywords: Optional[List[str]] = None,
        ctype: Optional[str] = None,
        lang: Optional[str] = None,
        clause: Optional[str] = None,
        clause_absent: bool = False,
        expand: str = "normal",
        no_expand: bool = False,
        exclude_drafts: bool = False,
        show_duplicates: bool = False,
        limit: int = 10,
        context: int = 1,
        party_name: Optional[str] = None,
        party_role: Optional[str] = None,
        payment_method: Optional[str] = None,
        amount_min: Optional[float] = None,
        amount_max: Optional[float] = None,
        cap_pct_min: Optional[float] = None,
        cap_pct_max: Optional[float] = None,
        survival_months_min: Optional[int] = None,
        survival_months_max: Optional[int] = None,
        governing_law: Optional[str] = None,
        forum: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search indexed contracts. Keywords use AND semantics; term_dict expansion is on by default. A clause means evaluated-present unless clause_absent is true. T3 v3 filters cover parties, consideration, indemnity cap, survival, governing law, and forum; older metadata is reported as unevaluated. Preserve file_key and evidence in the answer."""
        return service.search(
            keywords=keywords,
            ctype=ctype,
            lang=lang,
            clause=clause,
            clause_absent=clause_absent,
            expand=expand,
            no_expand=no_expand,
            exclude_drafts=exclude_drafts,
            show_duplicates=show_duplicates,
            limit=limit,
            context=context,
            party_name=party_name,
            party_role=party_role,
            payment_method=payment_method,
            amount_min=amount_min,
            amount_max=amount_max,
            cap_pct_min=cap_pct_min,
            cap_pct_max=cap_pct_max,
            survival_months_min=survival_months_min,
            survival_months_max=survival_months_max,
            governing_law=governing_law,
            forum=forum,
        )

    @mcp.tool(
        name="read_contract_clause",
        title="계약 조항 부분 정독",
        annotations=read_only,
        structured_output=True,
    )
    def read_clause_tool(file_key: str, section: str, context: int = 0) -> Dict[str, Any]:
        """Read one evaluated clause using doc_meta coordinates. Distinguishes confirmed, evaluated-absent, unevaluated, stale, and low-confidence states."""
        return service.read_clause(file_key, section, context)

    @mcp.tool(
        name="open_contract_context",
        title="계약 문단 주변 읽기",
        annotations=read_only,
        structured_output=True,
    )
    def read_context_tool(
        file_key: str,
        para: Optional[int] = None,
        search: Optional[str] = None,
        context: int = 2,
    ) -> Dict[str, Any]:
        """Read a small paragraph window by paragraph number or the first occurrence of a term. Provide exactly one of para or search; never use this to read a whole contract."""
        return service.read_context(file_key, para=para, search=search, context=context)

    @mcp.tool(
        name="inspect_contract",
        title="계약 문서 상태 점검",
        annotations=read_only,
        structured_output=True,
    )
    def inspect_tool(
        file_key: str, include_duplicate_members: bool = False
    ) -> Dict[str, Any]:
        """Inspect classification, indexing status, draft/version signals, duplicate state, term matches, and doc_meta freshness for one file_key."""
        return service.inspect(file_key, include_duplicate_members)

    @mcp.tool(
        name="list_contract_duplicates",
        title="중복·버전 문서 확인",
        annotations=read_only,
        structured_output=True,
    )
    def duplicates_tool(file_key: str) -> Dict[str, Any]:
        """List records in the same duplicate group so one representative can be counted and draft/final versions can be identified."""
        return service.duplicates(file_key)

    @mcp.tool(
        name="get_corpus_status",
        title="코퍼스 상태 확인",
        annotations=read_only,
        structured_output=True,
    )
    def corpus_status_tool() -> Dict[str, Any]:
        """Return searchable/unsearchable counts, status distribution, batches, last indexing time, and whether the corpus is pilot-only."""
        return service.corpus_status()

    @mcp.tool(
        name="get_corpus_facets",
        title="검색 필터 값 확인",
        annotations=read_only,
        structured_output=True,
    )
    def facets_tool() -> Dict[str, Any]:
        """List available contract type, language, and batch-label filters with counts."""
        return service.facets()

    return mcp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local read-only contract MCP server.")
    parser.add_argument("--out", required=True, type=Path, help="Local cs_index folder")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate the corpus and print server/tool information without starting stdio",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        service = ContractMcpService(args.out)
        if args.check:
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "transport": "stdio",
                        "read_only": True,
                        "tools": [
                            "search_contracts",
                            "read_contract_clause",
                            "open_contract_context",
                            "inspect_contract",
                            "list_contract_duplicates",
                            "get_corpus_status",
                            "get_corpus_facets",
                        ],
                        "corpus": service.corpus_status(),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        mcp = build_mcp(service)
        mcp.run(transport="stdio")
        return 0
    except McpServiceError as exc:
        print("mcp_server: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
