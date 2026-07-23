"""Build audited partial V4 results for confirmed remaining-rest evidence.

Only the bounded paragraphs manually confirmed during the 300/351 review are
stored.  Relevant families are marked partial and all annexes not_evaluated,
so these rows can support positive retrieval but never an absence assertion.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path


# taxonomy_id, file_key, paragraph, proposition, polarity, subject
SPECS = (
    ("RW.LABOR.NO_STRIKE", "a3cad0bc63f7fa08", 226, "대상회사에 중대한 영향을 미치는 파업·태업·작업중단 등이 진행 중이거나 위협되지 않았다고 진술한다.", "none_exist", "대상회사"),
    ("RW.LABOR.NO_UNION_ORGANIZING", "ced966fb03a5de65", 152, "사업의 직원과 관련한 노동조합 조직화 노력이 현재 또는 최근 2년 내 없었다고 진술한다.", "none_exist", "매도인"),
    ("RW.FINANCIAL.NO_OFF_BALANCE_SHEET", "3d6e2bcbe565f412", 236, "재무제표와 통상과정 장부에 반영된 채무 외 부외부채·우발채무가 없다고 진술한다.", "none_exist", "회사"),
    ("RW.IT.SYSTEMS_SUFFICIENCY", "6b490cb70a9e2d62", 357, "IT 시스템이 현재 사업을 독립적으로 운영하기에 충분하고 요구되는 방식으로 작동한다고 진술한다.", "affirmative", "대상회사"),
    ("RW.IT.DISASTER_RECOVERY", "198595774b9d19ed", 327, "중대한 IT 손상 시 사업을 계속할 수 있는 문서화된 재해복구계획을 갖추었다고 진술한다.", "affirmative", "대상회사"),
    ("RW.ENVIRONMENT.NO_UNDERGROUND_STORAGE_TANKS", "7f60095f191b3e04", 47, "대상 부동산의 지상 또는 지하에 지하저장탱크가 존재하지 않는다고 진술한다.", "none_exist", "매도인"),
    ("RW.TAX.NO_PERMANENT_ESTABLISHMENT", "198595774b9d19ed", 301, "설립지 외 관할의 고정사업장·과세상 존재로 인한 납세의무가 없다고 진술한다.", "none_exist", "대상회사"),
    ("CP.DEBT_RELEASE.PAYOFF_LETTER", "8a88d300b2815935", 215, "매도인은 종결일 지급대상 거래비용의 금액과 송금정보를 확인하는 payoff letter를 교부하여야 한다.", "affirmative", "매도인"),
    ("CP.DEBT_RELEASE.LIEN_RELEASE", "c163e7d36d6264df", 134, "양도인은 대상자산의 제한부담을 해소하는 담보권자 동의서·담보말소계약서 등 서류를 교부하여야 한다.", "affirmative", "양도인"),
    ("CP.ANCILLARY.RESTRICTIVE_COVENANT_AGREEMENT", "0b73c004dc993cbd", 44, "회사는 경업금지의무자들로부터 퇴사제한·경업금지 약정서에 서명을 받아 투자자에게 교부하여야 한다.", "affirmative", "회사"),
    ("CP.GOVERNMENT_APPROVAL.FOREIGN_INVESTMENT", "8b1417ad848b3bb2", 40, "외국인투자촉진법상 외국인투자신고 수리가 추가출자 거래종결의 선행조건이다.", "affirmative", "당사자"),
    ("COV.EMPLOYEE_BENEFITS_CONTINUATION", "1289f43bbd364dcd", 235, "매수인은 종결 후 일정 기간 대상회사 직원의 고용과 보상·복리후생을 유지하도록 하여야 한다.", "affirmative", "매수인"),
    ("COV.TAX.CONSISTENT_REPORTING", "127844bc34157180", 209, "당사자들은 손해배상금을 세무상 인수가격 조정으로 취급하고 그와 일치하는 세금신고를 하여야 한다.", "affirmative", "각 당사자"),
    ("COV.TAX.AUDIT_CONTROL", "927a0d97d97af639", 504, "배상권리자는 관련 세무조사를 통지하고 배상의무자는 비용을 부담하여 그 방어를 단독으로 통제한다.", "affirmative", "배상권리자·배상의무자"),
    ("COV.TAX.TRANSFER_TAX", "ced966fb03a5de65", 187, "양도세는 매도인이, 취득세·자산등록세는 매수인이 납부하고 기타 거래세는 법률상 부과받는 당사자가 부담한다.", "affirmative", "매도인·매수인"),
    ("COV.REGULATORY.DIVESTITURE", "e0e9acb2e97d2878", 205, "매수인은 기업결합승인을 위해 구조적 시정조치가 아닌 승인조건을 제안·협상·약속하고 이행하여야 한다.", "affirmative", "매수인"),
    ("COV.REGULATORY.HOLD_SEPARATE", "127844bc34157180", 151, "당사자는 거래금지 장애를 제거하기 위해 자산매각·분리보유 등 경쟁법상 조치를 제안하고 수용하여야 한다.", "affirmative", "각 당사자"),
    ("COV.RWI.PROCUREMENT", "5b77c491f91848c7", 168, "매수인은 종결 전 진술보장보험에 가입하고 종결일에 보험증권 사본을 매도인에게 교부하여야 한다.", "affirmative", "매수인"),
    ("COV.RWI.MAINTENANCE", "0df3b7a8cf1ba31f", 528, "매수인은 조건부 바인더의 조건을 충족하여 진술보장보험을 유효하게 유지하여야 한다.", "affirmative", "매수인"),
    ("COV.RWI.SUBROGATION_WAIVER", "ad00e647fb73f30c", 157, "매수인은 보험자가 매도인·대상회사에 구상권이나 대위권을 행사하지 못하는 조건으로 진술보장보험에 가입하여야 한다.", "affirmative", "매수인"),
    ("COV.SHA.ANTI_DILUTION", "7101ea75c598ac35", 107, "우선주 전환 전 더 낮은 발행가의 신주·주식연계사채가 발행되면 가중평균 방식으로 전환가액을 조정한다.", "affirmative", "회사"),
    ("COV.SHA.BUSINESS_PLAN_BUDGET", "5c011a0e170a38c7", 213, "연간 시설운영예산과 사업계획은 이사회 특별다수결 승인을 받아야 한다.", "affirmative", "회사"),
    ("COV.SHA.AFFILIATE_TRANSFER", "1eb4538a9df9abbb", 114, "투자자와 지배주주는 계열회사에 주식을 양도할 수 있고 양수인은 계약에 서면으로 구속되어야 한다.", "affirmative", "투자자·지배주주"),
    ("DEF.WORKING_CAPITAL.NET", "6b490cb70a9e2d62", 163, "순운전자본은 매출채권과 재고 등을 더하고 매입채무와 기타 유동부채 등을 차감하여 K-GAAP에 따라 계산한다.", "affirmative", "계약"),
    ("DEF.LEAKAGE.PERMITTED", "6056f50af3ee0a9f", 157, "허용누출은 locked-box 기준일 직후부터 종결일까지 허용되는 특정 지급·거래를 의미한다.", "affirmative", "계약"),
    ("PAY.HOLDBACK", "608947db630584c4", 81, "종결 시 기본대금에서 사후조정 holdback 금액을 차감한 순대금을 지급한다.", "affirmative", "매수인"),
    ("PAY.EARNOUT.DISPUTE", "73613d49cf1d8b27", 444, "기관매도인이 언아웃 명세서에 이의가 있으면 15영업일 내 분쟁금액·성격·근거를 서면 통지하여야 한다.", "affirmative", "기관매도인"),
    ("PAY.ESCROW.RELEASE", "5b7dbce4644ff76d", 196, "에스크로기간 만료 후 미확정 청구금액을 제외한 잔액과 이자를 매도인이 인출할 수 있다.", "affirmative", "매도인"),
    ("REM.CONSEQUENTIAL.LOST_PROFITS", "2d4a3a3f9ad4c7bf", 408, "배상의무자는 장래 수익·이익·소득의 상실에 대한 손해를 부담하지 않는다.", "negative", "배상의무자"),
    ("REM.CONSEQUENTIAL.DIMINUTION_IN_VALUE", "2d4a3a3f9ad4c7bf", 408, "배상의무자는 가치감소 방식으로 산정한 손해를 부담하지 않는다.", "negative", "배상의무자"),
    ("REM.CONSEQUENTIAL.MULTIPLE_BASED", "2d4a3a3f9ad4c7bf", 408, "배상의무자는 이익·매출 기타 성과지표의 배수를 적용해 산정한 손해를 부담하지 않는다.", "negative", "배상의무자"),
    ("REM.THIRD_PARTY_CLAIMS.DEFENSE_CONTROL", "127844bc34157180", 206, "배상의무자는 통지 수령 후 제3자청구의 방어에 참여하거나 이를 인수·통제할 수 있다.", "affirmative", "배상의무자"),
    ("REM.THIRD_PARTY_CLAIMS.SETTLEMENT_CONSENT", "127844bc34157180", 206, "배상의무자는 완전면책 조건을 충족하거나 배상권리자의 서면동의를 받아야 제3자청구를 합의할 수 있다.", "affirmative", "배상의무자"),
    ("REM.THIRD_PARTY_CLAIMS.COOPERATION", "127844bc34157180", 207, "배상권리자는 제3자청구 방어를 위해 관련 문서를 보존하고 합리적 열람·복사 요청에 협조하여야 한다.", "affirmative", "배상권리자"),
    ("REM.DIRECT_CLAIMS.NOTICE_CONTENT", "2a85f1dd1f73b0e2", 200, "손해배상청구 통지에는 이용 가능한 정보에 기초한 청구 근거와 세부사항 및 중요 제3자 통지를 포함하여야 한다.", "affirmative", "배상권리자"),
    ("REM.EXCLUSIVE_REMEDY.FRAUD_CARVEOUT", "127844bc34157180", 202, "배타적 구제 제한은 사기·중과실·고의적 위법행위·고의적 허위진술에는 적용되지 않는다.", "affirmative", "각 당사자"),
    ("REM.EXCLUSIVE_REMEDY.SPECIFIC_PERFORMANCE_CARVEOUT", "127844bc34157180", 202, "배타적 구제 조항은 당사자가 계약상 확약의 특정이행을 청구하는 것을 제한하지 않는다.", "affirmative", "각 당사자"),
    ("REM.SURVIVAL.STATUTE_OF_LIMITATIONS", "2a85f1dd1f73b0e2", 184, "특정 진술보장은 적용되는 법정 소멸시효 기간 동안 존속한다.", "affirmative", "각 당사자"),
    ("REM.INDEMNITY.TAX", "8a88d300b2815935", 427, "매도인은 종결 전 과세기간과 straddle period의 종결 전 부분에 귀속되는 미납세금으로부터 매수인을 면책한다.", "affirmative", "매도인"),
    ("REM.INDEMNITY.COVENANT_BREACH", "2a85f1dd1f73b0e2", 182, "매도인은 계약상 의무·약속·확약의 위반으로 발생한 손해를 매수인에게 배상한다.", "affirmative", "매도인"),
    ("REM.INDEMNITY.RW_BREACH", "2a85f1dd1f73b0e2", 182, "매도인은 자신의 진술보장의 부정확·불완전·위반으로 발생한 손해를 매수인에게 배상한다.", "affirmative", "매도인"),
    ("REM.INDEMNITY.EXCLUDED_LIABILITIES", "2a85f1dd1f73b0e2", 182, "매도인은 제외채무로 발생한 손해를 매수인에게 배상한다.", "affirmative", "매도인"),
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

    review = json.loads(args.review_json.read_text(encoding="utf-8"))
    selected = {str(row["file_key"]) for row in review["documents"]}
    spec_keys = {row[1] for row in SPECS}
    outside = sorted(spec_keys - selected)
    if outside:
        raise SystemExit(f"evidence documents are outside remaining-rest review: {outside}")

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

        input_payload = {
            "file_key": file_key,
            "content_hash": meta["content_hash"],
            "ctype": meta["ctype"],
            "lang": meta["lang"],
            "path": meta["path"],
            "taxonomy_version": taxonomy_version,
            "paragraphs": [
                {"para": number, "text": paragraphs[number]}
                for number in evidence_numbers
            ],
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
        for taxonomy_id, _, para, proposition, polarity, subject in specs:
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
                    "잔여 651건 범위검토 중 확정된 원자명제만 부분 정독·적재"
                    if family_counter[family]
                    else "이번 부분 근거확인 범위 밖"
                ),
            }
            for family in FAMILIES
        }
        result = {
            "file_key": file_key,
            "meta_schema_version": 4,
            "taxonomy_version": taxonomy_version,
            "extractor_version": "local-remaining-rest-confirmed-1",
            "prompt_version": "v4-prompt-8",
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
        "batch": "V4 remaining-rest confirmed partial items",
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
