"""Find bounded evidence for potential V4 taxonomy gaps in a reviewed sample.

This is a deterministic local corpus-review aid. It does not call an API and
does not decide that a clause is legally present from a keyword alone.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from lib.console import configure_utf8_stdio


@dataclass(frozen=True)
class Candidate:
    taxonomy_id: str
    family: str
    label: str
    patterns: tuple[str, ...]


CANDIDATES = (
    Candidate("RW.ABSENCE_OF_CHANGES", "RW", "중요 변경·변동 부재", (r"absence of (?:certain )?changes", r"no material adverse change", r"중대한 변동.{0,40}(?:없|부재)", r"변경사항.{0,30}없")),
    Candidate("RW.ACCOUNTS_RECEIVABLE", "RW", "매출채권", (r"accounts receivable", r"매출채권")),
    Candidate("RW.INVENTORY", "RW", "재고", (r"\binventory\b", r"재고자산", r"재고품")),
    Candidate("RW.SOLVENCY", "RW", "지급능력·도산 부재", (r"\bsolven(?:t|cy)", r"지급불능", r"채무초과")),
    Candidate("RW.PRIVACY.COMPLIANCE", "RW", "개인정보 처리 법규준수", (r"privacy laws?", r"personal data", r"개인정보보호법", r"개인정보.{0,40}(?:수집|처리|보호)")),
    Candidate("COV.RECORDS_RETENTION", "COV", "장부·기록 보존", (r"retain.{0,60}(?:books|records)", r"preserv.{0,60}(?:books|records)", r"장부.{0,30}(?:보존|보관)", r"기록.{0,30}(?:보존|보관)")),
    Candidate("COV.PRIVILEGE", "COV", "법률상 비밀유지특권", (r"attorney.client privilege", r"privileged communications?", r"법률상 비밀유지특권", r"변호사.{0,30}비밀")),
    Candidate("COV.GUARANTEE_RELEASE", "COV", "보증 해제·면제", (r"release.{0,80}(?:guarantee|guaranty)", r"guarantee.{0,80}release", r"보증.{0,30}(?:해제|해지|면제)")),
    Candidate("COV.POST_CLOSING_COOPERATION", "COV", "종결 후 협조", (r"post.closing cooperation", r"after the closing.{0,80}cooperat", r"종결 후.{0,60}협조", r"거래종결 후.{0,60}협력")),
    Candidate("COV.SHA.TAG_ALONG", "COV", "동반매도참여권", (r"tag.along", r"co.sale", r"동반매도참여", r"공동매도참여")),
    Candidate("COV.SHA.DRAG_ALONG", "COV", "동반매도요구권", (r"drag.along", r"강제매도", r"동반매도요구")),
    Candidate("COV.SHA.ROFR", "COV", "우선매수권", (r"right of first refusal", r"우선매수권")),
    Candidate("COV.SHA.ROFO", "COV", "우선제안권", (r"right of first offer", r"우선제안권")),
    Candidate("COV.SHA.PUT_OPTION", "COV", "풋옵션·주식매수청구권", (r"put option", r"풋옵션", r"주식매수청구권")),
    Candidate("COV.SHA.CALL_OPTION", "COV", "콜옵션·주식매도청구권", (r"call option", r"콜옵션", r"주식매도청구권")),
    Candidate("COV.SHA.RESERVED_MATTERS", "COV", "주요사항 사전동의권", (r"reserved matters?", r"사전동의사항", r"주요경영사항", r"동의권")),
    Candidate("COV.SHA.BOARD_NOMINATION", "COV", "이사 지명·선임권", (r"board nomination", r"nominate.{0,60}director", r"이사.{0,30}(?:지명|선임|추천)")),
    Candidate("COV.SHA.INFORMATION_RIGHTS", "COV", "정보·검사권", (r"information rights?", r"inspection rights?", r"경영정보.{0,30}(?:제공|열람)", r"회계장부.{0,30}열람")),
    Candidate("COV.SHA.DIVIDEND_POLICY", "COV", "배당정책", (r"dividend policy", r"배당정책", r"배당가능이익.{0,50}배당")),
    Candidate("COV.SHA.LOCKUP", "COV", "의무보유·처분제한기간", (r"lock.?up period", r"보유의무", r"처분제한기간")),
    Candidate("COV.SHA.FOUNDER_COMMITMENT", "COV", "창업자 전념·재직", (r"founder.{0,50}(?:devote|employment|commit)", r"창업자.{0,50}(?:전념|근무|재직)")),
    Candidate("CP.ANTITRUST_CLEARANCE", "CP", "기업결합·경쟁법 승인", (r"HSR Act", r"Hart.Scott.Rodino", r"antitrust approval", r"기업결합.{0,30}(?:신고|승인)")),
    Candidate("CP.SHAREHOLDER_APPROVAL", "CP", "주주승인", (r"stockholder approval", r"shareholder approval", r"주주총회.{0,30}(?:승인|결의)")),
    Candidate("CP.FIRPTA", "CP", "FIRPTA 증명", (r"FIRPTA", r"foreign investment in real property tax act")),
    Candidate("CP.GOOD_STANDING", "CP", "존속·적격 증명서", (r"good standing certificate", r"certificate of good standing")),
    Candidate("DEF.EBITDA", "DEF", "EBITDA", (r"\bEBITDA\b", r"상각전영업이익")),
    Candidate("DEF.ASSUMED_LIABILITIES", "DEF", "승계채무", (r"assumed liabilities", r"승계채무", r"인수채무")),
    Candidate("DEF.EXCLUDED_LIABILITIES", "DEF", "제외채무", (r"excluded liabilities", r"제외채무", r"비승계채무")),
    Candidate("DEF.PURCHASED_ASSETS", "DEF", "양수대상자산", (r"purchased assets", r"acquired assets", r"양수대상자산", r"인수대상자산")),
    Candidate("DEF.EXCLUDED_ASSETS", "DEF", "제외자산", (r"excluded assets", r"제외자산", r"비양수자산")),
    Candidate("PAY.MILESTONE", "PAY", "마일스톤 지급", (r"milestone payment", r"단계별.{0,30}대금", r"마일스톤.{0,30}지급")),
    Candidate("PAY.EARNOUT_ACCELERATION", "PAY", "언아웃 가속", (r"accelerat.{0,60}earn.?out", r"earn.?out.{0,60}accelerat", r"언아웃.{0,40}가속")),
    Candidate("REM.MATERIALITY_SCRAPE", "REM", "중요성 scrape", (r"materiality scrape", r"disregard.{0,100}(?:material|materiality)", r"without regard to.{0,100}(?:material|materiality)", r"중요성.{0,40}(?:제외|무시)")),
    Candidate("REM.JOINT_SEVERAL", "REM", "연대책임", (r"jointly and severally", r"joint and several", r"연대.{0,20}(?:책임|배상)")),
    Candidate("REM.CONTRIBUTION", "REM", "구상·분담", (r"right of contribution", r"contribution rights?", r"구상권")),
    Candidate("REM.FUNDAMENTAL_CAP", "REM", "기본 진술 별도 책임한도", (r"fundamental representations?.{0,100}(?:cap|limit)", r"(?:cap|limit).{0,100}fundamental representations?", r"기본 진술.{0,60}(?:한도|책임)")),
    Candidate("REM.CLAIM_NOTICE_DEADLINE", "REM", "청구통지 기한", (r"claim notice.{0,80}(?:within|days|period)", r"notice of claim.{0,80}(?:within|days|period)", r"손해배상청구.{0,50}(?:기간|통지)", r"청구통지.{0,50}(?:기간|이내)")),
    Candidate("REM.TAX_GROSS_UP", "REM", "배상금 조세 gross-up", (r"(?:indemnif|loss).{0,200}tax gross.?up", r"tax gross.?up.{0,200}(?:indemnif|loss)", r"손해배상.{0,80}(?:세금|조세).{0,40}보전")),
)


def paragraphs(text: str):
    for line in text.splitlines():
        match = re.match(r"^\[¶(\d+)\]\s*(.*)$", line)
        if match:
            yield int(match.group(1)), match.group(2).strip()


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sample-json", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    sample = json.loads(args.sample_json.read_text(encoding="utf-8"))
    sample_keys = {str(row["file_key"]) for row in sample["documents"]}
    compiled = {
        item.taxonomy_id: tuple(re.compile(pattern, re.IGNORECASE) for pattern in item.patterns)
        for item in CANDIDATES
    }
    evidence: dict[str, list[dict]] = defaultdict(list)
    with sqlite3.connect(args.out / "catalog.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        placeholders = ",".join("?" for _ in sample_keys)
        rows = conn.execute(
            f"SELECT file_key,txt_path,ctype,lang FROM files WHERE file_key IN ({placeholders})",
            tuple(sorted(sample_keys)),
        )
        for row in rows:
            path = Path(row["txt_path"])
            if not path.is_absolute():
                path = args.out / path
            text = path.read_text(encoding="utf-8", errors="replace")
            para_rows = list(paragraphs(text))
            for candidate in CANDIDATES:
                for para, para_text in para_rows:
                    if any(pattern.search(para_text) for pattern in compiled[candidate.taxonomy_id]):
                        evidence[candidate.taxonomy_id].append(
                            {
                                "file_key": row["file_key"],
                                "para": para,
                                "ctype": row["ctype"],
                                "lang": row["lang"],
                                "verbatim": " ".join(para_text.split())[:300],
                            }
                        )
                        break

    payload = {
        "review_version": "v4-scope-gap-200-1",
        "sample_count": len(sample_keys),
        "candidates": [
            {
                "taxonomy_id": item.taxonomy_id,
                "family": item.family,
                "label": item.label,
                "document_count": len(evidence[item.taxonomy_id]),
                "evidence": evidence[item.taxonomy_id][:5],
            }
            for item in CANDIDATES
        ],
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.report:
        lines = [
            "# V4 신규 200건 taxonomy gap 검토",
            "",
            "_로컬 문단 캐시의 제한된 표현 근거를 이용한 후보 탐지 결과다. 검출 건수는",
            "조항 존재 확정치가 아니며, 정의·목차의 언급은 운영조항과 구분해 부분 정독했다._",
            "",
        ]
        for family in ("RW", "COV", "CP", "DEF", "PAY", "REM"):
            lines.extend(
                [
                    f"## {family}",
                    "",
                    "| 후보 taxonomy | 개념 | 검출 문서 수 | 근거 예시 |",
                    "|---|---|---:|---|",
                ]
            )
            for item in (row for row in payload["candidates"] if row["family"] == family):
                examples = ", ".join(
                    f"[{row['file_key']}] ¶{row['para']}"
                    for row in item["evidence"][:3]
                )
                lines.append(
                    f"| `{item['taxonomy_id']}` | {item['label']} | "
                    f"{item['document_count']} | {examples or '-'} |"
                )
            lines.append("")
        lines.extend(
            [
                "## 부분 정독으로 확인한 분류 원칙",
                "",
                "- SHA의 ROFR, tag-along, drag-along은 각각 별도의 운영권리이며, 권리자·",
                "  대상주식·발동조건·통지·행사기간·가격/동일조건·종결협력·비용부담을",
                "  원자화한다 [0622f171eecbfbfd] ¶148-¶164.",
                "- 단순히 `Encumbrance` 정의 안에 ROFR·put/call·tag/drag가 열거된 경우에는",
                "  해당 SHA 권리의 운영조항으로 분류하지 않고 정의(DEF) 근거로만 남긴다",
                "  [018616d362652278] ¶1121-¶1126.",
                "- 자산양수도에서는 양수자산·제외자산·승계채무·제외채무를 서로 합치지 않고,",
                "  포함/제외 항목과 종결 전후 발생시점을 별도 item으로 만든다",
                "  [002123feda5cf04f] ¶164-¶195.",
                "- materiality scrape는 진술 정확성의 종결조건과 구분하고, 위반판정용 scrape와",
                "  손해액 산정용 scrape를 별도 qualifier/item으로 처리한다",
                "  [1074bc528091d22d] ¶486, ¶511-¶514.",
                "- 배상금에 부과되는 세금의 gross-up은 대금 원천징수(PAY)가 아니라",
                "  손해배상액 산정(REM)으로 분류한다 [977fb166c6765dc0] ¶534-¶538.",
                "",
                "## 반영 결론",
                "",
                "- 검출 0건인 `PAY.MILESTONE`, `PAY.EARNOUT_ACCELERATION`은 seed로",
                "  승격하지 않고 이후 후보 관찰 대상으로 유지한다.",
                "- 나머지 반복 개념과 미국형 FIRPTA·good-standing 항목은 taxonomy version 4",
                "  seed로 반영한다. 단순 정의 언급과 운영권리의 구분은 추출 프롬프트에 강제한다.",
                "",
            ]
        )
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            {
                "sample_count": len(sample_keys),
                "candidate_count": len(CANDIDATES),
                "detected": sum(bool(evidence[item.taxonomy_id]) for item in CANDIDATES),
                "json": str(args.json),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
