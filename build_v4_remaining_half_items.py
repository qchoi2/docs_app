"""Build audited partial-coverage V4 items confirmed during the 652-doc review."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path


# taxonomy_id, file_key, paragraph, proposition, polarity, subject_role
SPECS = (
    ("RW.REAL_ESTATE.ZONING", "1b8c393f95eea771", 155, "해당 부동산은 현재 용도·점유·건축과 관련된 환경·용도지역·토지이용 요건을 준수한다.", "affirmative", "대상회사"),
    ("RW.REAL_ESTATE.NO_CONDEMNATION", "62f355e124ff00df", 386, "소유 부동산에 예정된 수용·협의취득 등 유사 절차나 관련 서면통지가 없다.", "none_exist", "대상회사"),
    ("RW.LABOR.IMMIGRATION", "7ea64578b32dc4d5", 391, "모든 근로자의 취업허가 서류가 구비되었고 적용 이민법을 준수하였다.", "affirmative", "매도인·관계회사"),
    ("RW.FINANCIAL.DEBT_COMPLIANCE", "8de77a0a1239e26a", 77, "대상회사와 자회사는 차입·대출·신용공여의 재무약정을 준수한다.", "affirmative", "대상회사·자회사"),
    ("RW.FINANCIAL.NO_GOVERNMENT_GRANT_CLAWBACK", "69f5e7b0be9164f4", 709, "정부 지원금 조건을 준수하였고 그 반환의무가 없다.", "none_exist", "매도인"),
    ("RW.COMPLIANCE.COMPETITION", "20f705c6cb680f13", 449, "대상회사는 독점규제 및 공정거래법을 포함한 경쟁법을 중요한 측면에서 준수하였다.", "affirmative", "대상회사"),
    ("RW.COMPLIANCE.CUSTOMS", "14f9e70a3cc2d65a", 534, "대상회사는 관세 및 수출통제 관련 법령을 중요한 측면에서 준수하였다.", "affirmative", "대상회사"),
    ("RW.GOVERNMENT_CONTRACTS.COMPLIANCE", "7ea64578b32dc4d5", 407, "매도인과 자회사는 정부 원도급·하도급·입찰계약의 조건을 중요한 측면에서 준수하였다.", "affirmative", "매도인·자회사"),
    ("RW.IP.DOMAIN_NAMES", "bf0d051b54bbd083", 247, "대상회사 등은 인터넷 도메인을 포함한 중요 지식재산권 내역을 제공하고 적법한 소유·사용권을 보유한다.", "affirmative", "대상회사"),
    ("CP.ESCROW_AGREEMENT", "1422d84ab8d3309f", 1376, "각 매도인이 서명한 에스크로계약 사본을 매수인에게 교부하여야 한다.", "affirmative", "매도인"),
    ("CP.KEY_EMPLOYEE", "abe00bf57680df34", 372, "핵심인력은 거래종결일 현재 대상회사에 재직하여야 한다.", "affirmative", "핵심인력"),
    ("CP.DISSENTERS_RIGHTS", "4f52b5c6f70ad5d0", 278, "반대주주의 주식매수청구권 행사규모가 기준금액을 초과하지 않는 것이 종결조건이다.", "affirmative", "양수인"),
    ("COV.NON_DISPARAGEMENT", "e7ce3f8a57347935", 193, "매도인은 기본합의서에 따른 비방금지의무를 부담한다.", "affirmative", "매도인"),
    ("COV.STANDSTILL", "53503385c86ef92b", 274, "투자자와 관계인은 상대방 동의 없이 회사증권 취득·공개매수 등 지배권 행위를 하지 않는다.", "negative", "투자자"),
    ("COV.PRIVACY_REMEDIATION", "789c633a97d092a7", 398, "회사들은 개인정보처리방침·동의·처리위탁계약·파기·안전성조치 등 개인정보 위반사항을 시정하여야 한다.", "affirmative", "회사·의식주테크랩"),
    ("COV.TAX.REFUND", "ab02d34ba6746929", 237, "매수인은 원천징수세 환급을 매도인이 수령하도록 환급청구·수령·지급에 협력한다.", "affirmative", "매수인"),
    ("COV.SHA.REGISTRATION_RIGHTS", "329b70754c8bde87", 18, "우선주주는 piggyback 등록권과 일정 시점 이후의 demand registration 권리를 가진다.", "affirmative", "우선주주"),
    ("COV.SHA.VOTING_PROXY", "068120c8242fcf70", 60, "매도인은 2차 대상주식의 의결권 행사를 매수인에게 위임하고 필요한 위임장을 제공한다.", "affirmative", "매도인"),
    ("COV.SHA.QUORUM", "167299b34d606e60", 231, "재직 이사 과반수의 출석이 이사회 정족수를 구성한다.", "affirmative", "이사회"),
    ("COV.SHA.CASTING_VOTE", "797e7859fd1b93ab", 145, "의장 또는 지정 이사는 이사회 가부동수 시 결정표를 가진다.", "affirmative", "이사회 의장"),
    ("DEF.ACCOUNTING_PRINCIPLES", "7ea64578b32dc4d5", 845, "회계원칙은 별첨에 기재된 회계정책·관행·방법론을 의미한다.", "affirmative", "계약당사자"),
    ("DEF.DISCLOSURE_SCHEDULE", "4596477fe5af5444", 16, "공개목록은 계약 별지에 첨부되고 종결 전 서면통지로 수정된 공개목록을 포함한다.", "affirmative", "계약당사자"),
    ("DEF.DATA_ROOM", "b9ca268b0dba03d3", 24, "데이터룸은 지정 가상 데이터룸에서 기준일 현재 제공되고 저장매체로 교부된 문서·정보의 범위이다.", "affirmative", "계약당사자"),
    ("DEF.DEBT.CLOSING_NET_DEBT", "0b086d458c144b1f", 183, "종결 순차입금은 거래종결일 현재의 순차입금을 의미한다.", "affirmative", "계약당사자"),
    ("DEF.WORKING_CAPITAL.TARGET", "0b086d458c144b1f", 229, "목표운전자본은 별지에 기재된 기준금액을 의미한다.", "affirmative", "계약당사자"),
    ("PAY.MILESTONE", "38b1634bea851dbd", 66, "사업가치 증대 마일스톤 달성 시 각 마일스톤별 추가 매매대금을 지급한다.", "affirmative", "매수인"),
    ("PAY.EQUITY_CONSIDERATION", "4dc2df305c7f400e", 343, "거래종결 대가의 일부는 매수인 관계회사의 자기주식으로 지급된다.", "affirmative", "매수인"),
    ("PAY.TRUE_UP_DEADLINE", "1f037d5d2639a0ca", 15, "사후 정산금은 정산금액 확정일부터 정해진 영업일 이내 지급한다.", "affirmative", "당사자"),
    ("PAY.EARNOUT.GUARANTEE", "2e46d615d7904477", 81, "매수인과 모회사는 유동성 사건별 언아웃 대금을 연대하여 지급한다.", "affirmative", "매수인·모회사"),
    ("REM.BASKET.DEDUCTIBLE", "4523d65ec8836daa", 175, "누적 손해가 기준액을 초과하면 그 초과분에 한하여 배상한다.", "affirmative", "매도인"),
    ("REM.BASKET.TIPPING", "2fc326c9c86d3acd", 152, "누적 손해가 기준액을 초과하면 기준액 이하를 포함한 손해 전액을 배상한다.", "affirmative", "배상의무자"),
    ("REM.CONSEQUENTIAL.PUNITIVE", "04abaca09c3aec13", 150, "각 당사자는 제재적 또는 징벌적 손해에 대한 배상책임을 부담하지 않는다.", "negative", "각 당사자"),
    ("REM.EXCLUSIVE_REMEDY.RESCISSION_WAIVER", "3c993d206977a606", 313, "매수인은 위반을 이유로 계약취소·대가감액·해지 취급을 할 권리를 포기한다.", "negative", "매수인"),
    ("REM.EXCLUSIVE_REMEDY.ESCROW_SOLE_RECOURSE", "d313b345e29510e8", 548, "가격조정 부족액에 대한 유일한 구제와 회수재원은 에스크로 자금으로 제한된다.", "affirmative", "매수인"),
    ("REM.DIRECT_CLAIMS.CLAIMS_REPRESENTATIVE", "ceccbf5dd0817e5e", 188, "복수 매수인의 손해배상 청구는 매수인대표자를 통하여 통지·행사한다.", "affirmative", "매수인"),
    ("REM.INDEMNITY.RECOVERY_PRIORITY", "75d01740842662b3", 531, "매수인측은 매도인에게 직접 청구하기 전에 에스크로계좌에서 먼저 회수하여야 한다.", "affirmative", "매수인"),
)

FAMILIES = ("RW", "CP", "COV", "DEF", "PAY", "REM")


def read_paragraphs(path: Path) -> dict[int, str]:
    rows: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"^\[¶(\d+)\]\s*(.*)$", line)
        if match:
            rows[int(match.group(1))] = match.group(2)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--review-json", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    reviewed = json.loads(args.review_json.read_text(encoding="utf-8"))
    selected = {str(row["file_key"]) for row in reviewed["documents"]}
    spec_keys = {row[1] for row in SPECS}
    missing_from_review = sorted(spec_keys - selected)
    if missing_from_review:
        raise SystemExit(
            f"evidence documents are outside selected half: {missing_from_review}"
        )

    with sqlite3.connect(args.out / "catalog.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        taxonomy_version = int(
            conn.execute(
                "SELECT value FROM v4_meta WHERE key='taxonomy_version'"
            ).fetchone()[0]
        )
        known = {
            str(row[0]): str(row[1])
            for row in conn.execute(
                "SELECT taxonomy_id,family FROM v4_taxonomy_node WHERE status='active'"
            )
        }
        placeholders = ",".join("?" for _ in spec_keys)
        files = {
            str(row["file_key"]): dict(row)
            for row in conn.execute(
                f"""
                SELECT file_key,path,ctype,lang,content_hash,txt_path
                FROM files WHERE file_key IN ({placeholders}) AND status='ok'
                """,
                tuple(sorted(spec_keys)),
            )
        }
    for taxonomy_id, *_ in SPECS:
        if taxonomy_id not in known:
            raise SystemExit(f"unknown taxonomy: {taxonomy_id}")

    grouped: dict[str, list[tuple]] = defaultdict(list)
    for row in SPECS:
        grouped[row[1]].append(row)

    args.input_dir.mkdir(parents=True, exist_ok=True)
    args.result_dir.mkdir(parents=True, exist_ok=True)
    manifest_items = []
    total_items = 0
    for file_key, specs in sorted(grouped.items()):
        meta = files[file_key]
        txt_path = Path(meta["txt_path"])
        if not txt_path.is_absolute():
            txt_path = args.out / txt_path
        paragraphs = read_paragraphs(txt_path)
        evidence_numbers = sorted({int(row[2]) for row in specs})
        missing = [number for number in evidence_numbers if number not in paragraphs]
        if missing:
            raise SystemExit(f"{file_key}: missing paragraphs {missing}")
        paragraph_rows = [
            {"para": number, "text": paragraphs[number]}
            for number in evidence_numbers
        ]
        input_payload = {
            "file_key": file_key,
            "content_hash": meta["content_hash"],
            "ctype": meta["ctype"],
            "lang": meta["lang"],
            "path": meta["path"],
            "taxonomy_version": taxonomy_version,
            "paragraphs": paragraph_rows,
            "family_sections": {},
            "source_inventory": [],
            "review_scope": "confirmed atomic evidence only; document coverage is partial",
        }
        (args.input_dir / f"{file_key}.json").write_text(
            json.dumps(input_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        family_counter: Counter[str] = Counter()
        items = []
        for index, (
            taxonomy_id,
            _,
            para,
            proposition,
            polarity,
            subject,
        ) in enumerate(specs, start=1):
            family = known[taxonomy_id]
            family_counter[family] += 1
            items.append(
                {
                    "item_ref": f"{family}-{family_counter[family]:03d}",
                    "family": family,
                    "taxonomy_id": taxonomy_id,
                    "proposition": proposition,
                    "statement_polarity": polarity,
                    "subject_role": subject,
                    "counterparty_role": None,
                    "action": None,
                    "object_type": None,
                    "effective_time": None,
                    "source_kind": "body",
                    "source_id": None,
                    "source_name": None,
                    "source_ref": f"¶{para}",
                    "parent_clause_ref": None,
                    "related_item_ref": None,
                    "qualifier": {
                        "review_scope": "bounded paragraph confirmation",
                        "document_coverage": "partial",
                    },
                    "verbatim": paragraphs[int(para)],
                    "loc_start": int(para),
                    "loc_end": int(para),
                    "normalized": {},
                    "confidence": "high",
                    "review_status": "approved",
                }
            )
        coverage = {
            family: {
                "body_status": (
                    "partial" if family_counter[family] else "not_evaluated"
                ),
                "annex_status": "not_evaluated",
                "reason": (
                    "652건 범위검토 중 확정된 원자명제만 부분 정독·적재"
                    if family_counter[family]
                    else "이번 부분 근거확인 범위 외"
                ),
            }
            for family in FAMILIES
        }
        result = {
            "file_key": file_key,
            "meta_schema_version": 4,
            "taxonomy_version": taxonomy_version,
            "extractor_version": "local-remaining-half-confirmed-1",
            "prompt_version": "v4-prompt-7",
            "items": items,
            "coverage": coverage,
            "source_coverage": [],
            "taxonomy_candidates": [],
        }
        (args.result_dir / f"{file_key}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        total_items += len(items)
        manifest_items.append(
            {
                "file_key": file_key,
                "ctype": meta["ctype"],
                "lang": meta["lang"],
                "path": meta["path"],
                "confirmed_item_count": len(items),
            }
        )

    manifest = {
        "meta_schema_version": 4,
        "schema_revision": "1R2",
        "taxonomy_version": taxonomy_version,
        "batch": "V4 remaining-half confirmed partial items",
        "count": len(manifest_items),
        "item_count": total_items,
        "items": manifest_items,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "documents": len(manifest_items),
                "items": total_items,
                "taxonomy_version": taxonomy_version,
                "manifest": str(args.manifest),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
