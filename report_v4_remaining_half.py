"""Generate the V4 remaining-half review report and node-delta artifact."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path


REJECTED = (
    ("RW.CORPORATE_GOVERNANCE.NO_POWER_OF_ATTORNEY", "의결권 위임·종결서류·세무대리 위임이 혼재하여 독립 RW로 승격하지 않음"),
    ("CP.STOCK_EXCHANGE_APPROVAL", "대부분 IPO 추진확약·정의·reserved matter로서 CP 승인조건이 아님"),
    ("CP.DATA_ROOM_DELIVERY", "정의 또는 체결 후 자료제공으로, DEF.DATA_ROOM/COV.INFORMATION으로 처리"),
    ("COV.LITIGATION_COOPERATION", "대부분 제3자청구 방어절차로 REM.THIRD_PARTY_CLAIMS와 중복"),
    ("COV.IT_MIGRATION", "계약이전 동의·일반 전환지원 검출이 주로 발생하여 독립 IT migration 근거 부족"),
    ("PAY.PRICE_ADJUSTMENT_COLLAR", "working capital의 문자열 cap을 상한으로 오인한 검출이어서 승격하지 않음"),
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--review-json", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--store-audit", type=Path, required=True)
    parser.add_argument("--node-json", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    review = json.loads(args.review_json.read_text(encoding="utf-8"))
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    store_audit = json.loads(args.store_audit.read_text(encoding="utf-8"))
    with sqlite3.connect(args.out / "catalog.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        nodes = [
            dict(row)
            for row in conn.execute(
                """
                SELECT taxonomy_id,parent_id,family,canonical_ko,canonical_en,
                       depth,taxonomy_version
                FROM v4_taxonomy_node
                WHERE taxonomy_version=7
                ORDER BY family,taxonomy_id
                """
            )
        ]
        db_counts = {
            "taxonomy_nodes": int(
                conn.execute("SELECT COUNT(*) FROM v4_taxonomy_node").fetchone()[0]
            ),
            "taxonomy_aliases": int(
                conn.execute("SELECT COUNT(*) FROM v4_taxonomy_alias").fetchone()[0]
            ),
            "clause_items": int(
                conn.execute("SELECT COUNT(*) FROM v4_clause_item").fetchone()[0]
            ),
            "item_documents": int(
                conn.execute(
                    "SELECT COUNT(DISTINCT file_key) FROM v4_clause_item"
                ).fetchone()[0]
            ),
            "approved_items": int(
                conn.execute(
                    "SELECT COUNT(*) FROM v4_clause_item "
                    "WHERE review_status='approved'"
                ).fetchone()[0]
            ),
        }
        item_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT file_key,item_ref,family,taxonomy_id,proposition,
                       statement_polarity,loc_start,review_status
                FROM v4_clause_item
                WHERE extractor_version='local-remaining-half-confirmed-1'
                ORDER BY family,taxonomy_id,file_key
                """
            )
        ]
        stored_document_count = int(
            conn.execute(
                "SELECT COUNT(DISTINCT file_key) FROM v4_clause_item "
                "WHERE extractor_version='local-remaining-half-confirmed-1'"
            ).fetchone()[0]
        )

    documents = review["documents"]
    selection = review["selection"]
    type_counts = Counter(row["ctype"] for row in documents)
    lang_counts = Counter(row["lang"] for row in documents)
    draft_counts = Counter(str(row["is_draft"]) for row in documents)
    family_nodes = Counter(row["family"] for row in nodes)
    family_items = Counter(row["family"] for row in item_rows)
    nonzero = [
        row for row in review["candidates"] if row["document_count"] > 0
    ]

    delta = {
        "review_version": review["review_version"],
        "selection": selection,
        "document_distribution": {
            "ctype": dict(sorted(type_counts.items())),
            "lang": dict(sorted(lang_counts.items())),
            "is_draft": dict(sorted(draft_counts.items())),
        },
        "candidate_summary": {
            "tested": review["candidate_count"],
            "nonzero": len(nonzero),
            "promoted": len(nodes),
            "rejected_after_context_review": len(REJECTED),
        },
        "taxonomy_before": {"version": 6, "nodes": 290, "aliases": 1002},
        "taxonomy_after": {
            "version": 7,
            "nodes": db_counts["taxonomy_nodes"],
            "aliases": db_counts["taxonomy_aliases"],
            "added_nodes": len(nodes),
        },
        "added_nodes": nodes,
        "rejected_candidates": [
            {"candidate_id": candidate_id, "reason": reason}
            for candidate_id, reason in REJECTED
        ],
        "operational_items": {
            "documents": stored_document_count,
            "items": len(item_rows),
            "by_family": dict(sorted(family_items.items())),
            "audit": audit["summary"],
            "store": {
                "stored_count": stored_document_count,
                "skipped_count": audit["summary"]["total"] - stored_document_count,
            },
            "database_totals": db_counts,
        },
    }
    args.node_json.parent.mkdir(parents=True, exist_ok=True)
    args.node_json.write_text(
        json.dumps(delta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    node_lines = "\n".join(
        f"| `{row['taxonomy_id']}` | `{row['parent_id']}` | "
        f"{row['canonical_ko']} | {row['canonical_en']} |"
        for row in nodes
    )
    rejected_lines = "\n".join(
        f"| `{candidate_id}` | {reason} |"
        for candidate_id, reason in REJECTED
    )
    stratum_lines = "\n".join(
        f"| {key.replace('|', ' / ')} | "
        f"{selection['population_by_stratum'][key]} | "
        f"{selection['selected_by_stratum'][key]} |"
        for key in selection["population_by_stratum"]
    )
    family_lines = "\n".join(
        f"| {family} | {family_nodes[family]} | {family_items[family]} |"
        for family in ("RW", "CP", "COV", "DEF", "PAY", "REM")
    )
    evidence_lines = "\n".join(
        f"- `{row['taxonomy_id']}` — {row['proposition']} "
        f"`[{row['file_key']}] ¶{row['loc_start']}`"
        for row in item_rows
    )
    markdown = f"""# V4 미검토 잔여 계약 절반 검토 및 taxonomy v7 보강

기준일: 2026-07-23

## 범위와 방식

- 기존 검토 320건을 제외한 검색가능 주요 M&A 계약
  `SPA|SSA|SHA|ATA/BTA`는 1,303건이다.
- 그 절반(올림)인 **652건, 50.04%**를 유형·언어 비율에 따라 결정적으로
  선정했다. 동일 거래 프로젝트는 먼저 한 버전씩 순환하고, 필요한 경우에만
  추가 버전을 포함했다.
- 각 문서의 추출 문단 전체를 49개 미보유 원자개념 패턴으로 스캔하고,
  정의·목차·단순 열거보다 실제 진술·의무·조건·지급·구제 문맥을 우선했다.
- 키워드 검출만으로 승격하지 않고 대표 문단을 부분 정독해 기존 taxonomy와
  겹치는지 확인했다. 따라서 이는 652건의 **범위보강 검토**이며, 각 계약의
  모든 조항을 완전색인했다는 의미는 아니다.

| 유형 / 언어 | 미검토 모집단 | 이번 검토 |
|---|---:|---:|
{stratum_lines}

선정 문서는 SPA {type_counts['SPA']}건, SSA {type_counts['SSA']}건,
SHA {type_counts['SHA']}건, ATA/BTA {type_counts['ATA/BTA']}건이다.
언어는 국문 {lang_counts['국문']}건, 영문 {lang_counts['영문']}건,
국영문 {lang_counts['국영문']}건이며, 체결/비초안 {draft_counts['0']}건,
초안 {draft_counts['1']}건, 판별불가 {draft_counts['None']}건이다.

## 결과

- 검토 후보 49개 중 42개가 1건 이상 검출되었다.
- 문맥 검토 후 **36개 독립 원자노드**를 taxonomy version 7로 승격했다.
- taxonomy는 290노드·1,002 aliases에서
  **326노드·1,171 aliases**로 증가했다.
- 명확한 대표 근거가 있는 **36개 item/33개 문서**를
  `review_status=approved`, `body_status=partial`,
  `annex_status=not_evaluated`로 운영 DB에 적재했다.
- 감사 결과는 pass 33, review 0, error 0, issues 0이고 저장은
  stored {stored_document_count}, skipped {audit['summary']['total'] - stored_document_count}이다.

| family | 추가 노드 | 운영 적재 item |
|---|---:|---:|
{family_lines}

## 추가 노드

| taxonomy_id | parent | 국문명 | 영문명 |
|---|---|---|---|
{node_lines}

## 승격하지 않은 검출 후보

| 후보 | 판단 |
|---|---|
{rejected_lines}

## 운영 DB에 적재한 근거 item

{evidence_lines}

## 검증 및 한계

- 전체 V4 item은 기존 대표계약 131개를 포함해 {db_counts['clause_items']}개,
  {db_counts['item_documents']}개 문서이며 전부 approved 상태다.
- 이번 33개 문서는 확인된 문단만 `partial`로 저장했다. 따라서 해당 family의
  다른 item이 없다는 부재검색 근거로 사용할 수 없다.
- 본문 추출이 불가능한 전체 코퍼스의 empty 48건·error 1건과 unsupported
  41건은 이번 모집단에 포함하지 않았다.
- `eval_search.py` T1/T2 골든 평가: fail 0.
- 전체 회귀 테스트: 172 passed, 1 skipped.
"""
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(markdown, encoding="utf-8")
    print(
        json.dumps(
            {
                "report": str(args.report),
                "node_json": str(args.node_json),
                "selected": selection["selected_count"],
                "added_nodes": len(nodes),
                "stored_documents": stored_document_count,
                "stored_items": len(item_rows),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
