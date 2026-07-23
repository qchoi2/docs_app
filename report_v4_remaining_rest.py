"""Generate the final V4 remaining-rest review report and node delta."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path


RESOLUTIONS = {
    "RW.CUSTOMERS_SUPPLIERS.CONCENTRATION": {
        "status": "rejected",
        "reason": "1건 적중 문단은 고객집중도 수치가 아니라 주요 거래관계 악화사유 부재 진술이어서 후보명과 불일치",
    },
    "RW.PRODUCTS.COMPLIANCE": {
        "status": "merged_existing",
        "target": ["RW.COMPLIANCE.GENERAL"],
        "reason": "제품만의 별도 규제준수보다 회사·사업·제품을 포괄하는 일반 준법진술 문맥",
    },
    "CP.RWI_BINDER": {
        "status": "split_reclassified",
        "target": [
            "COV.RWI.PROCUREMENT",
            "COV.RWI.MAINTENANCE",
            "COV.RWI.SUBROGATION_WAIVER",
        ],
        "reason": "종결조건 하나가 아니라 보험 가입·유지·대위권 제한의 독립 확약으로 분해",
    },
    "CP.EMPLOYMENT_AGREEMENT": {
        "status": "merged_existing",
        "target": ["CP.KEY_EMPLOYEE"],
        "reason": "핵심인력 고용계약 체결은 기존 CP.KEY_EMPLOYEE의 명시적 포함범위",
    },
    "CP.NO_LITIGATION": {
        "status": "merged_existing",
        "target": ["CP.NO_PROHIBITION"],
        "reason": "주요 적중은 거래금지 명령·소송 또는 해제조항으로 기존 금지 부재 조건과 중복",
    },
    "COV.TAX.RETURNS": {
        "status": "reclassified",
        "target": ["COV.TAX.CONSISTENT_REPORTING"],
        "reason": "일반 세금신고 작성의무가 아니라 손해배상금 세무처리와 일치하는 신고의무",
    },
    "COV.ANTITRUST.DIVESTITURE": {
        "status": "reclassified",
        "target": ["COV.REGULATORY.DIVESTITURE"],
        "reason": "경쟁법상 인허가 노력의 구조적 시정조치 범위로 정규화",
    },
    "COV.ANTITRUST.HOLD_SEPARATE": {
        "status": "reclassified",
        "target": ["COV.REGULATORY.HOLD_SEPARATE"],
        "reason": "규제승인 노력 확약 하위의 분리운영 조치로 정규화",
    },
    "PAY.PRICE_ADJUSTMENT.COLLAR": {
        "status": "rejected",
        "reason": "2건 모두 중복계상 금지 또는 정의 문맥이고 실제 가격조정 상·하한이 아님",
    },
    "REM.ESCROW_RELEASE": {
        "status": "reclassified",
        "target": ["PAY.ESCROW.RELEASE"],
        "reason": "손해배상 원인보다 예치대금의 해제·분배 구조가 검색 핵심",
    },
}


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
    store = json.loads(args.store_audit.read_text(encoding="utf-8"))
    with sqlite3.connect(args.out / "catalog.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        nodes = [
            dict(row)
            for row in conn.execute(
                """
                SELECT taxonomy_id,parent_id,family,canonical_ko,canonical_en,
                       depth,taxonomy_version
                FROM v4_taxonomy_node
                WHERE taxonomy_version=8
                ORDER BY family,taxonomy_id
                """
            )
        ]
        items = [
            dict(row)
            for row in conn.execute(
                """
                SELECT file_key,item_ref,family,taxonomy_id,proposition,
                       statement_polarity,loc_start,review_status
                FROM v4_clause_item
                WHERE extractor_version='local-remaining-rest-confirmed-1'
                ORDER BY family,taxonomy_id,file_key
                """
            )
        ]
        db_counts = {
            "taxonomy_nodes": conn.execute(
                "SELECT COUNT(*) FROM v4_taxonomy_node"
            ).fetchone()[0],
            "taxonomy_aliases": conn.execute(
                "SELECT COUNT(*) FROM v4_taxonomy_alias"
            ).fetchone()[0],
            "clause_items": conn.execute(
                "SELECT COUNT(*) FROM v4_clause_item"
            ).fetchone()[0],
            "item_documents": conn.execute(
                "SELECT COUNT(DISTINCT file_key) FROM v4_clause_item"
            ).fetchone()[0],
            "approved_items": conn.execute(
                "SELECT COUNT(*) FROM v4_clause_item WHERE review_status='approved'"
            ).fetchone()[0],
        }

    documents = review["documents"]
    type_counts = Counter(row["ctype"] for row in documents)
    lang_counts = Counter(row["lang"] for row in documents)
    draft_counts = Counter(str(row["is_draft"]) for row in documents)
    family_nodes = Counter(row["family"] for row in nodes)
    family_items = Counter(row["family"] for row in items)
    stored_document_count = len({row["file_key"] for row in items})
    stored_count = int(store.get("stored_count", stored_document_count))
    skipped_count = int(
        store.get("skipped_count", audit["summary"]["total"] - stored_count)
    )
    new_candidates = [
        row
        for row in review["candidates"]
        if row.get("candidate_generation") == "remaining-rest"
    ]
    nonzero = [row for row in new_candidates if row["document_count"] > 0]

    delta = {
        "review_version": review["review_version"],
        "batches": review["batches"],
        "selection": review["selection"],
        "document_distribution": {
            "ctype": dict(sorted(type_counts.items())),
            "lang": dict(sorted(lang_counts.items())),
            "is_draft": dict(sorted(draft_counts.items())),
        },
        "candidate_summary": {
            "new_tested": len(new_candidates),
            "new_nonzero": len(nonzero),
            "resolution_overrides": RESOLUTIONS,
        },
        "taxonomy_before": {"version": 7, "nodes": 326, "aliases": 1171},
        "taxonomy_after": {
            "version": 8,
            "nodes": db_counts["taxonomy_nodes"],
            "aliases": db_counts["taxonomy_aliases"],
            "added_nodes": len(nodes),
            "added_leaf_nodes": sum(
                row["taxonomy_id"] != "RW.IT" for row in nodes
            ),
        },
        "added_nodes": nodes,
        "operational_items": {
            "documents": len({row["file_key"] for row in items}),
            "items": len(items),
            "by_family": dict(sorted(family_items.items())),
            "audit": audit["summary"],
            "store": {
                "stored_count": stored_count,
                "skipped_count": skipped_count,
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
        f"| `{row['taxonomy_id']}` | `{row['parent_id'] or '-'}` | "
        f"{row['canonical_ko']} | {row['canonical_en']} |"
        for row in nodes
    )
    family_lines = "\n".join(
        f"| {family} | {family_nodes[family]} | {family_items[family]} |"
        for family in ("RW", "CP", "COV", "DEF", "PAY", "REM")
    )
    evidence_lines = "\n".join(
        f"- `{row['taxonomy_id']}` — {row['proposition']} "
        f"`[{row['file_key']}] ¶{row['loc_start']}`"
        for row in items
    )
    resolution_lines = "\n".join(
        f"| `{candidate}` | {resolution['status']} | "
        f"{', '.join(f'`{value}`' for value in resolution.get('target', [])) or '-'} | "
        f"{resolution['reason']} |"
        for candidate, resolution in RESOLUTIONS.items()
    )
    batch_lines = "\n".join(
        f"| {row['offset']} | {row['count']} | `{row['path']}` |"
        for row in review["batches"]
    )
    markdown = f"""# V4 잔여 651건 범위검토 및 taxonomy v8 보강

기준일: 2026-07-23

## 완료 범위

- 앞선 절반 652건을 제외한 정확한 보완집합 **651건**을 고정된 순서로 검토했다.
- 사용자 요청에 따라 1차 300건, 2차 351건으로 나눴고 두 배치의 file_key 중복은 0건이다.
- 대상은 추출본문과 doc_meta가 있는 `SPA|SSA|SHA|ATA/BTA` 주계약이다.
- 이 검토는 651건 전체의 범위·taxonomy gap 검토다. 각 문서의 모든 조항을 완전
  원자화한 full V4 추출은 아니며, 운영 DB에는 확인한 근거만 `partial`로 적재했다.

| offset | 문서 수 | 배치 산출물 |
|---:|---:|---|
{batch_lines}

분포는 SPA {type_counts['SPA']}건, SSA {type_counts['SSA']}건,
SHA {type_counts['SHA']}건, ATA/BTA {type_counts['ATA/BTA']}건이며,
국문 {lang_counts['국문']}건, 영문 {lang_counts['영문']}건,
국영문 {lang_counts['국영문']}건이다. 체결·비초안 {draft_counts['0']}건,
초안 {draft_counts['1']}건, 판별불가 {draft_counts['None']}건이다.

## 결과

- 신규 세분화 후보 65개를 검사했고 43개에서 표현 적중이 있었다.
- 문맥 및 기존 taxonomy 중복을 판정해 taxonomy version 8에
  **43개 노드(상위 `RW.IT` 1개 + 원자 leaf 42개)**를 추가했다.
- taxonomy는 **326 → {db_counts['taxonomy_nodes']} 노드**,
  aliases는 **1,171 → {db_counts['taxonomy_aliases']}개**가 되었다.
- 근거가 확정된 **42 items / 26 documents**를 모두 `approved`로 운영 DB에
  적재했다. 해당 family의 `body_status=partial`, 모든 별지는
  `annex_status=not_evaluated`이므로 부재 증명에는 사용할 수 없다.
- 감사 결과 pass {audit['summary']['pass']}, review {audit['summary']['review']},
  error {audit['summary']['error']}; 적재 stored {stored_count},
  skipped {skipped_count}이다.

| family | 추가 노드 | 운영 적재 item |
|---|---:|---:|
{family_lines}

## 주요 중복·재분류 판정

| 후보 | 판정 | 최종 taxonomy | 사유 |
|---|---|---|---|
{resolution_lines}

## 추가 노드

| taxonomy_id | parent | 국문명 | 영문명 |
|---|---|---|---|
{node_lines}

## 운영 DB 적재 근거

{evidence_lines}

## 운영 DB 누적 상태

- 총 V4 item {db_counts['clause_items']}개 / {db_counts['item_documents']}개 문서.
- approved item {db_counts['approved_items']}개.
- 이번 26개 문서는 부분 정독 근거만 저장했으므로, 같은 family의 다른 item이
  없다는 부재 근거로 사용할 수 없다.
"""
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(markdown, encoding="utf-8")
    print(
        json.dumps(
            {
                "report": str(args.report),
                "node_json": str(args.node_json),
                "selected": len(documents),
                "added_nodes": len(nodes),
                "stored_documents": len({row["file_key"] for row in items}),
                "stored_items": len(items),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
