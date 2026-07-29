import asyncio
import json
import sqlite3
from contextlib import closing

import pytest

from lib.catalog import initialize_catalog
from mcp_server import ContractMcpService, McpServiceError, build_mcp


FILE_KEY = "a" * 16
DUP_KEY = "b" * 16


def make_corpus(tmp_path):
    out = tmp_path / "cs_index"
    db_path = initialize_catalog(out / "catalog.sqlite")
    (out / "txt").mkdir()
    text = "제1조 목적\n제2조 손해배상 책임\n손해배상 상한은 매매대금의 10%로 한다."
    (out / "txt" / (FILE_KEY + ".txt")).write_text(
        "[¶1]\t제1조 목적\n[¶2]\t제2조 손해배상 책임\n"
        "[¶3]\t손해배상 상한은 매매대금의 10%로 한다.\n",
        encoding="utf-8",
    )
    (out / "txt" / (DUP_KEY + ".txt")).write_text(
        "[¶1]\t제1조 목적\n", encoding="utf-8"
    )
    with closing(sqlite3.connect(db_path)) as conn:
        for key, path, content, draft in (
            (FILE_KEY, "spa_final.docx", text, 0),
            (DUP_KEY, "spa_draft.docx", "제1조 목적", 1),
        ):
            conn.execute(
                """
                INSERT INTO files (
                  file_key, path, folder, filename, ctype, lang, ext, size, mtime,
                  txt_path, char_count, status, error_reason, source_signals,
                  batch_label, content_hash, dup_group, is_draft, version_hint, indexed_at
                ) VALUES (?, ?, '', ?, 'SPA', '국문', '.docx', 1, 1, ?, ?, 'ok',
                  NULL, '{}', 'pilot_test', ?, 'dup-one', ?, ?, '2026-07-16T00:00:00+00:00')
                """,
                (
                    key,
                    path,
                    path,
                    "txt/%s.txt" % key,
                    len(content),
                    key,
                    draft,
                    "final" if not draft else "draft",
                ),
            )
            for para, paragraph in enumerate(content.split("\n"), start=1):
                conn.execute(
                    "INSERT INTO fts(content, file_key, para) VALUES (?, ?, ?)",
                    (paragraph, key, para),
                )
        clause_map = {
            "손해배상": {
                "present": True,
                "loc_start": 2,
                "loc_end": 3,
                "summary": "손해배상 책임과 10% 상한",
                "cap_verbatim": "매매대금의 10%",
                "basket_verbatim": "not confirmed",
                "de_minimis_verbatim": "not confirmed",
                "survival_verbatim": "not confirmed",
            },
            "경업금지": {
                "present": False,
                "loc_start": None,
                "loc_end": None,
                "summary": "평가 후 부재",
            },
        }
        conn.execute(
            """
            INSERT INTO doc_meta (
              file_key, meta_schema_version, txt_hash, extracted_at,
              clause_map_json, json, confidence
            ) VALUES (?, 2, ?, '2026-07-16T00:00:00+00:00', ?, '{}', 'high')
            """,
            (FILE_KEY, FILE_KEY, json.dumps(clause_map, ensure_ascii=False)),
        )
        conn.commit()
    return out


def test_service_search_clause_and_context(tmp_path):
    service = ContractMcpService(make_corpus(tmp_path))

    result = service.search(
        keywords=["손해배상"], no_expand=True, exclude_drafts=True, limit=5
    )
    assert result["total"] == 1
    assert result["results"][0]["file_key"] == FILE_KEY
    assert result["mcp_guidance"]["citation_format"] == "[file_key]"

    clause = service.read_clause(FILE_KEY, "손해배상")
    assert clause["status"] == "ok"
    assert [row["para"] for row in clause["paragraphs"]] == [2, 3]
    assert "txt_path" not in clause

    context = service.read_context(FILE_KEY, para=3, context=1)
    assert context["matched_para"] == 3
    assert "txt_path" not in context


def test_service_absence_duplicates_status_and_facets(tmp_path):
    service = ContractMcpService(make_corpus(tmp_path))

    absent = service.search(clause="경업금지", clause_absent=True, limit=5)
    assert absent["total"] == 1
    assert absent["results"][0]["file_key"] == FILE_KEY

    duplicates = service.duplicates(FILE_KEY)
    assert duplicates["count"] == 2
    assert {row["file_key"] for row in duplicates["members"]} == {FILE_KEY, DUP_KEY}

    status = service.corpus_status()
    assert status["searchable_docs"] == 2
    assert status["pilot_corpus"] is True
    assert service.facets()["ctype"] == [{"value": "SPA", "count": 2}]


def test_service_search_exposes_v3_structured_filters(tmp_path):
    out = make_corpus(tmp_path)
    parties = {
        "evaluated": True,
        "items": [{"name": "알파 주식회사", "role": "매수인", "loc_start": 1, "loc_end": 1, "confidence": "high"}],
        "confidence": "high",
        "confidence_reason": None,
    }
    consideration = {
        "evaluated": True,
        "amount_value": 10000000000,
        "payment_methods": ["현금"],
        "confidence": "high",
        "confidence_reason": None,
    }
    clause_map = {
        "손해배상": {
            "present": True, "loc_start": 2, "loc_end": 3,
            "summary": "10% 상한", "verbatim": "매매대금의 10%",
            "normalized": {"cap_pct_of_price": 10}, "confidence": "high",
        }
    }
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        conn.execute(
            "UPDATE doc_meta SET meta_schema_version=3,parties_json=?,consideration_json=?,clause_map_json=? WHERE file_key=?",
            (json.dumps(parties, ensure_ascii=False), json.dumps(consideration, ensure_ascii=False),
             json.dumps(clause_map, ensure_ascii=False), FILE_KEY),
        )
        conn.commit()

    result = ContractMcpService(out).search(party_name="알파", party_role="매수인", cap_pct_max=10)

    assert result["total"] == 1
    assert result["results"][0]["structured"]["손해배상"]["normalized"]["cap_pct_of_price"] == 10

def _set_version_roles(out, roles):
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        for key, role in roles.items():
            conn.execute("UPDATE files SET version_role=? WHERE file_key=?", (role, key))
        conn.commit()


def test_service_search_filters_by_version_role(tmp_path):
    out = make_corpus(tmp_path)
    _set_version_roles(out, {FILE_KEY: "execution", DUP_KEY: "buyer_draft"})
    service = ContractMcpService(out)

    # role key로 필터: 매수인 초안(DUP_KEY)만 남는다.
    by_key = service.search(keywords=["목적"], no_expand=True, show_duplicates=True,
                            version="buyer_draft", limit=5)
    assert by_key["total"] == 1
    assert by_key["results"][0]["file_key"] == DUP_KEY
    # 해석된 canonical role을 query echo로 돌려준다.
    assert by_key["query"]["version"] == ["buyer_draft"]

    # 한글 라벨(공백 포함)도 동일하게 동작한다.
    by_label = service.search(keywords=["목적"], no_expand=True, show_duplicates=True,
                              version="매수인 초안", limit=5)
    assert by_label["total"] == 1
    assert by_label["results"][0]["file_key"] == DUP_KEY

    # 다른 버전(체결본)은 FILE_KEY만 남는다.
    execution = service.search(keywords=["목적"], no_expand=True, show_duplicates=True,
                               version="execution", limit=5)
    assert {row["file_key"] for row in execution["results"]} == {FILE_KEY}


def test_service_search_rejects_unknown_version(tmp_path):
    service = ContractMcpService(make_corpus(tmp_path))
    with pytest.raises(McpServiceError) as excinfo:
        service.search(keywords=["목적"], version="not-a-version")
    # CLI와 동일한 안내(유효 옵션 목록)를 담는다.
    assert "Valid role keys" in str(excinfo.value)


def test_service_rejects_unsafe_or_ambiguous_reads(tmp_path):
    service = ContractMcpService(make_corpus(tmp_path))
    with pytest.raises(McpServiceError):
        service.read_context(FILE_KEY)
    with pytest.raises(McpServiceError):
        service.read_context(FILE_KEY, para=1, search="목적")
    with pytest.raises(McpServiceError):
        service.inspect("not-a-file-key")
    with pytest.raises(McpServiceError):
        service.search(keywords=["x"] * 11)


def test_fastmcp_exposes_only_read_tools(tmp_path):
    pytest.importorskip("mcp")
    mcp = build_mcp(ContractMcpService(make_corpus(tmp_path)))

    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert names == {
        "search_contracts",
        "read_contract_clause",
        "open_contract_context",
        "inspect_contract",
        "list_contract_duplicates",
        "get_corpus_status",
        "get_corpus_facets",
    }
    assert all(tool.annotations.readOnlyHint is True for tool in tools)
    assert all(tool.annotations.destructiveHint is False for tool in tools)

    content, structured = asyncio.run(
        mcp.call_tool(
            "search_contracts",
            {"keywords": ["손해배상"], "no_expand": True, "limit": 5},
        )
    )
    assert content
    assert structured["result"]["results"][0]["file_key"] == FILE_KEY
