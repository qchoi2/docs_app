"""Build review artifacts for the single-document V4-2 trial."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path


FILE_KEY = "0ba3a1b8246c5dd5"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--node-json", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    result = json.loads(args.result.read_text(encoding="utf-8"))
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    with sqlite3.connect(args.out / "catalog.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        nodes = [
            dict(row)
            for row in conn.execute(
                """
                SELECT taxonomy_id,parent_id,family,canonical_ko,canonical_en,
                       depth,taxonomy_version,origin
                FROM v4_taxonomy_node
                WHERE status='active'
                ORDER BY taxonomy_version,taxonomy_id
                """
            )
        ]
        alias_count = int(
            conn.execute("SELECT COUNT(*) FROM v4_taxonomy_alias").fetchone()[0]
        )
        source = dict(
            conn.execute(
                "SELECT file_key,path,ctype,lang,status,is_draft,dup_group "
                "FROM files WHERE file_key=?",
                (FILE_KEY,),
            ).fetchone()
        )
        stored_item_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM v4_clause_item WHERE file_key=?",
                (FILE_KEY,),
            ).fetchone()[0]
        )
        stored_approved_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM v4_clause_item "
                "WHERE file_key=? AND review_status='approved'",
                (FILE_KEY,),
            ).fetchone()[0]
        )

    parents = {row["taxonomy_id"]: row["parent_id"] for row in nodes}
    names = {row["taxonomy_id"]: row["canonical_ko"] for row in nodes}

    def domain(taxonomy_id: str) -> str:
        current = taxonomy_id
        while parents.get(current) not in (None, "RW"):
            current = str(parents[current])
        return current

    phase_nodes = {
        "before_refinement": [row for row in nodes if row["taxonomy_version"] <= 4],
        "cumulative_320_refinement": [
            row for row in nodes if row["taxonomy_version"] == 5
        ],
        "representative_document_refinement": [
            row for row in nodes if row["taxonomy_version"] == 6
        ],
    }
    item_domains = Counter(domain(item["taxonomy_id"]) for item in result["items"])
    used_taxonomy = Counter(item["taxonomy_id"] for item in result["items"])
    node_update = {
        "file_key": FILE_KEY,
        "taxonomy_version": result["taxonomy_version"],
        "phase_summary": {
            "before_refinement": {
                "all_nodes": len(phase_nodes["before_refinement"]),
                "rw_nodes": sum(
                    row["family"] == "RW"
                    for row in phase_nodes["before_refinement"]
                ),
                "aliases": 732,
            },
            "after_320_document_refinement": {
                "all_nodes": len(phase_nodes["before_refinement"])
                + len(phase_nodes["cumulative_320_refinement"]),
                "rw_nodes": sum(
                    row["family"] == "RW"
                    for row in phase_nodes["before_refinement"]
                    + phase_nodes["cumulative_320_refinement"]
                ),
                "aliases": 896,
                "added_nodes": len(phase_nodes["cumulative_320_refinement"]),
            },
            "after_representative_trial": {
                "all_nodes": len(nodes),
                "rw_nodes": sum(row["family"] == "RW" for row in nodes),
                "aliases": alias_count,
                "added_nodes": len(
                    phase_nodes["representative_document_refinement"]
                ),
            },
        },
        "version_5_nodes": phase_nodes["cumulative_320_refinement"],
        "version_6_nodes": phase_nodes["representative_document_refinement"],
        "trial_result": {
            "items": len(result["items"]),
            "unique_taxonomy_nodes_used": len(used_taxonomy),
            "source_kind_counts": dict(
                sorted(Counter(item["source_kind"] for item in result["items"]).items())
            ),
            "polarity_counts": dict(
                sorted(
                    Counter(
                        item["statement_polarity"] for item in result["items"]
                    ).items()
                )
            ),
            "domain_counts": [
                {
                    "taxonomy_id": taxonomy_id,
                    "canonical_ko": names[taxonomy_id],
                    "item_count": count,
                }
                for taxonomy_id, count in item_domains.most_common()
            ],
            "version_6_nodes_used": [
                {
                    "taxonomy_id": row["taxonomy_id"],
                    "canonical_ko": row["canonical_ko"],
                    "item_count": used_taxonomy[row["taxonomy_id"]],
                }
                for row in phase_nodes["representative_document_refinement"]
                if used_taxonomy[row["taxonomy_id"]]
            ],
            "audit": audit["summary"],
            "operational_store": {
                "stored_item_count": stored_item_count,
                "approved_item_count": stored_approved_count,
            },
        },
    }
    args.node_json.parent.mkdir(parents=True, exist_ok=True)
    args.node_json.write_text(
        json.dumps(node_update, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    v5_by_parent = Counter(
        str(row["parent_id"]) for row in phase_nodes["cumulative_320_refinement"]
    )
    v6_rows = phase_nodes["representative_document_refinement"]
    domain_lines = "\n".join(
        f"| `{taxonomy_id}` | {names[taxonomy_id]} | {count} |"
        for taxonomy_id, count in item_domains.most_common()
    )
    v5_lines = "\n".join(
        f"| `{parent}` | {names.get(parent, parent)} | {count} |"
        for parent, count in sorted(v5_by_parent.items())
    )
    v6_lines = "\n".join(
        f"| `{row['taxonomy_id']}` | `{row['parent_id'] or '-'}` | "
        f"{row['canonical_ko']} | {used_taxonomy[row['taxonomy_id']]} |"
        for row in v6_rows
    )
    markdown = f"""# V4-2 국문 SPA 대표시험 결과

기준일: 2026-07-23
대표 문서: `[{FILE_KEY}]` {source['path']}
범위: RW 본문, 별지 5.1(8) 대상회사 진술 및 보장, 공개목록 세부자료

## 결론

- V4-2 시험 결과는 **131개 원자 item**으로 분해되었다: 본문 19개,
  진술보장 별지 102개, 공개목록 10개.
- 94개의 서로 다른 최하위 taxonomy 노드가 실제로 사용되었다.
- 자동 감사 결과는 **pass 1 / review 0 / error 0**이고 이슈는 0개다.
- 소유자 승인에 따라 131개 모두 `review_status=approved`로 전환했고,
  `v4_clause_item` 운영 테이블에 적재했다.

## 노드 변화

| 단계 | 전체 노드 | RW 노드 | alias | 이번 단계 추가 |
|---|---:|---:|---:|---:|
| 기존 V4-1R2 + 200건 보강 후 | 184 | 41 | 732 | - |
| 누적 320건 RW 세분화 후(v5) | 266 | 123 | 896 | 82 |
| 이 대표계약 반영 후(v6) | 290 | 147 | {alias_count} | 24 |

### 누적 320건에서 추가한 RW 하위노드

| 상위노드 | 영역 | 추가 수 |
|---|---|---:|
{v5_lines}

### 대표계약에서 추가·확정한 v6 노드

`실사용 수=0`인 두 행은 검색계층을 위한 구조 노드이고, 그 하위 leaf가 실제
item에 사용되었다.

| 신규 노드 | 상위노드 | 명칭 | 이 계약 실사용 수 |
|---|---|---|---:|
{v6_lines}

## 대표계약 원자화 분포

| RW 영역 | 명칭 | item 수 |
|---|---|---:|
{domain_lines}

극성은 affirmative 67개, `none_exist` 57개, 공개예외 등 negative 7개다.

## 별지·공개목록 연결 사례

- 본문은 대상회사 진술보장을 별지 5.1(8)로 편입한다
  (`RW.DISCLOSURE.ACCURACY`, `[0ba3a1b8246c5dd5] ¶65`).
- 별지는 개인정보 법규준수와 보호조치를 진술하지만
  (`RW.PRIVACY.COMPLIANCE`, `[0ba3a1b8246c5dd5] ¶270`),
  공개목록은 동의 미수령·퇴직자 정보 미파기·보호조치 미이행을
  반대 극성 item으로 연결한다(`[0ba3a1b8246c5dd5] ¶297`).
- 노무 진술보장(`[0ba3a1b8246c5dd5] ¶276`)에는 겸직·공동인력과
  외국인 근로자 법정 보험 미가입 예외가 각각 연결된다
  (`[0ba3a1b8246c5dd5] ¶299-¶300`).
- 환경·안전·보건 준수 진술(`[0ba3a1b8246c5dd5] ¶277`)에는
  공정안전보고서·작업환경측정·안전검사·MSDS 조치 미이행이 연결된다
  (`[0ba3a1b8246c5dd5] ¶302`).
- 보험 적정성 진술(`[0ba3a1b8246c5dd5] ¶278`)에는 환경책임보험
  미가입 예외가 연결된다(`[0ba3a1b8246c5dd5] ¶304`).

## 파일

- 원자 item 전체: `cs_index/enrich_results_v4_v2_trial/{FILE_KEY}.json`
- 입력 및 근거 범위: `cs_index/enrich_inputs_v4_v2_trial/{FILE_KEY}.json`
- 감사 결과: `cs_index/v4_v2_trial_audit.json`
- 노드 증분 전체(v5 82개 + v6 24개): `cs_index/v4_v2_trial_node_update.json`
- 누적 320건 근거 스캔: `cs_index/rw_leaf_gaps_320.json`
"""
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(markdown, encoding="utf-8")
    print(
        json.dumps(
            {
                "report": str(args.report),
                "node_json": str(args.node_json),
                "items": len(result["items"]),
                "audit": audit["summary"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
