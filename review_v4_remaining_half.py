"""Review half of the previously unreviewed M&A contract corpus.

Selection is deterministic and proportional by agreement type/language.  The
analysis records bounded first-paragraph evidence for candidate atomic
concepts; it does not treat keyword hits as confirmed legal clauses and does
not call an external API.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from review_v4_scope_sample import EXISTING_REVIEW_KEYS, _project_key


PRINCIPAL_TYPES = ("SPA", "SSA", "SHA", "ATA/BTA")


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    family: str
    recommended_parent_id: str
    label_ko: str
    label_en: str
    patterns: tuple[str, ...]


CANDIDATES = (
    # RW
    Candidate("RW.LABOR.IMMIGRATION", "RW", "RW.LABOR", "외국인근로자·이민법 준수", "Immigration compliance", (r"\bI-9\b", r"immigration law", r"work (?:permit|authorization)", r"외국인\s*근로자", r"체류자격")),
    Candidate("RW.REAL_ESTATE.ZONING", "RW", "RW.REAL_ESTATE", "용도지역·건축법 준수", "Zoning and building compliance", (r"\bzoning\b", r"building code", r"용도지역", r"건축법", r"불법건축")),
    Candidate("RW.REAL_ESTATE.NO_CONDEMNATION", "RW", "RW.REAL_ESTATE", "수용·철거 절차 부재", "No condemnation", (r"\bcondemnation\b", r"eminent domain", r"수용.{0,30}(?:절차|예정|통지)", r"철거명령")),
    Candidate("RW.REAL_ESTATE.NO_TENANT_DISPUTE", "RW", "RW.REAL_ESTATE", "임대인·임차인 분쟁 부재", "No landlord or tenant dispute", (r"(?:landlord|tenant).{0,50}(?:dispute|claim)", r"임대인.{0,30}분쟁", r"임차인.{0,30}분쟁")),
    Candidate("RW.FINANCIAL.DEBT_COMPLIANCE", "RW", "RW.FINANCIAL", "금융약정 준수", "Debt covenant compliance", (r"financial covenant", r"debt covenant", r"대출약정.{0,30}(?:준수|위반)", r"재무약정")),
    Candidate("RW.FINANCIAL.NO_GOVERNMENT_GRANT_CLAWBACK", "RW", "RW.FINANCIAL", "보조금 환수사유 부재", "No grant clawback", (r"(?:government grant|subsidy).{0,50}(?:clawback|repay)", r"보조금.{0,30}(?:환수|반환)")),
    Candidate("RW.COMPLIANCE.COMPETITION", "RW", "RW.COMPLIANCE", "경쟁법 준수", "Competition law compliance", (r"antitrust laws?", r"competition laws?", r"독점규제", r"공정거래법.{0,30}준수")),
    Candidate("RW.COMPLIANCE.CUSTOMS", "RW", "RW.COMPLIANCE", "관세·무역 준수", "Customs and trade compliance", (r"customs law", r"import.{0,20}export.{0,20}compliance", r"관세법", r"수출입.{0,30}준수")),
    Candidate("RW.GOVERNMENT_CONTRACTS.COMPLIANCE", "RW", "RW.GOVERNMENT_CONTRACTS", "정부계약 준수", "Government contract compliance", (r"government contract.{0,50}(?:compl|default)", r"public procurement", r"정부계약.{0,30}(?:준수|위반)", r"공공조달")),
    Candidate("RW.PRODUCTS.NO_SAFETY_NOTICE", "RW", "RW.PRODUCTS", "제품안전 통지 부재", "No product safety notice", (r"product safety.{0,40}(?:notice|warning)", r"제품안전.{0,30}(?:통지|경고|명령)")),
    Candidate("RW.IP.DOMAIN_NAMES", "RW", "RW.IP", "도메인명·소셜미디어 계정", "Domain names and social accounts", (r"domain names?", r"social media accounts?", r"도메인명", r"인터넷\s*도메인")),
    Candidate("RW.PRIVACY.DATA_PROCESSING_AGREEMENTS", "RW", "RW.PRIVACY", "개인정보 처리위탁계약", "Data processing agreements", (r"data processing agreement", r"\bDPA\b", r"개인정보.{0,20}(?:처리위탁|위탁계약)")),
    Candidate("RW.CORPORATE_GOVERNANCE.NO_POWER_OF_ATTORNEY", "RW", "RW.CORPORATE_GOVERNANCE", "미공개 위임장 부재", "No outstanding power of attorney", (r"power of attorney.{0,50}(?:outstanding|granted)", r"위임장.{0,30}(?:교부|수여|존재)")),
    # CP
    Candidate("CP.ESCROW_AGREEMENT", "CP", "CP", "에스크로계약 체결·교부", "Escrow agreement delivery", (r"deliver.{0,50}escrow agreement", r"execution.{0,30}escrow agreement", r"에스크로계약.{0,30}(?:체결|교부)")),
    Candidate("CP.MINIMUM_CASH", "CP", "CP", "최소 현금 보유", "Minimum cash condition", (r"minimum cash", r"cash balance.{0,40}(?:closing|condition)", r"최소.{0,10}현금", r"현금잔액.{0,30}선행조건")),
    Candidate("CP.KEY_EMPLOYEE", "CP", "CP", "핵심인력 재직·계약", "Key employee condition", (r"key employees?.{0,50}(?:remain|employment)", r"employment agreement.{0,40}closing", r"핵심인력.{0,30}(?:재직|근로계약)")),
    Candidate("CP.DISSENTERS_RIGHTS", "CP", "CP", "주식매수청구권 제한", "Dissenters' rights condition", (r"dissenters?.{0,30}rights?", r"appraisal rights?.{0,30}(?:not|no|threshold)", r"주식매수청구권.{0,30}(?:행사|기준|제한)")),
    Candidate("CP.STOCK_EXCHANGE_APPROVAL", "CP", "CP", "거래소 승인·상장", "Stock exchange approval", (r"stock exchange.{0,40}(?:approval|listing)", r"Nasdaq.{0,40}(?:approval|listing)", r"거래소.{0,30}(?:승인|상장)")),
    Candidate("CP.DATA_ROOM_DELIVERY", "CP", "CP", "데이터룸 자료 인도", "Data room delivery", (r"data room.{0,50}(?:deliver|download|copy)", r"데이터룸.{0,30}(?:인도|교부|저장)")),
    # COV
    Candidate("COV.LITIGATION_COOPERATION", "COV", "COV", "소송·분쟁 협조", "Litigation cooperation", (r"cooperat.{0,50}(?:litigation|proceeding|claim)", r"소송.{0,30}(?:협조|협력)", r"분쟁.{0,30}(?:협조|협력)")),
    Candidate("COV.NON_DISPARAGEMENT", "COV", "COV", "비방금지", "Non-disparagement", (r"non-disparagement", r"not disparage", r"비방.{0,20}(?:금지|하지)")),
    Candidate("COV.STANDSTILL", "COV", "COV", "스탠드스틸", "Standstill", (r"\bstandstill\b", r"stand-still", r"추가.{0,20}주식.{0,20}(?:취득|매수).{0,20}금지")),
    Candidate("COV.IT_MIGRATION", "COV", "COV.TRANSITION", "IT·데이터 이전", "IT and data migration", (r"data migration", r"IT migration", r"system migration", r"(?:정보시스템|데이터).{0,30}(?:이전|이관)")),
    Candidate("COV.SHARED_SERVICES_SEPARATION", "COV", "COV.TRANSITION", "공유서비스·혼재자산 분리", "Shared services separation", (r"shared services?.{0,40}(?:separat|transition)", r"commingled assets?", r"공유서비스.{0,30}분리", r"혼재.{0,20}(?:자산|계약).{0,20}분리")),
    Candidate("COV.TAX_ELECTION_338", "COV", "COV.TAX", "미국 세법 338(h)(10) 선택", "Section 338(h)(10) election", (r"338\\(h\\)\\(10\\)", r"section 338 election")),
    Candidate("COV.TAX_REFUND", "COV", "COV.TAX", "조세환급 귀속", "Tax refund allocation", (r"tax refunds?", r"refund of taxes", r"조세환급", r"세금환급")),
    Candidate("COV.SHA.REGISTRATION_RIGHTS", "COV", "COV.SHA", "등록청구권", "Registration rights", (r"registration rights?", r"demand registration", r"piggyback registration", r"등록청구권")),
    Candidate("COV.SHA.VOTING_PROXY", "COV", "COV.SHA", "의결권 위임·의결권계약", "Voting proxy", (r"voting agreement", r"irrevocable proxy", r"의결권.{0,20}(?:위임|대리행사|계약)")),
    Candidate("COV.SHA.QUORUM", "COV", "COV.SHA", "이사회·주주총회 정족수", "Board and shareholder quorum", (r"\bquorum\b", r"정족수", r"성립요건.{0,20}(?:이사회|주주총회)")),
    Candidate("COV.SHA.CASTING_VOTE", "COV", "COV.SHA", "의장 결정권", "Chair casting vote", (r"casting vote", r"chairman.{0,30}tie", r"의장.{0,20}(?:결정권|캐스팅보트)")),
    # DEF
    Candidate("DEF.ACCOUNTING_PRINCIPLES", "DEF", "DEF", "회계원칙", "Accounting principles", (r'"Accounting Principles"', r"Accounting Principles means", r"[“\"]회계원칙[”\"](?:이라 함은|이란)")),
    Candidate("DEF.DISCLOSURE_SCHEDULE", "DEF", "DEF", "공개목록", "Disclosure schedule", (r'"Disclosure Schedules?" means', r"Disclosure Schedule.{0,20}means", r"[“\"]공개목록[”\"](?:이라 함은|이란)")),
    Candidate("DEF.DATA_ROOM", "DEF", "DEF", "데이터룸", "Data room", (r'"Data Room" means', r"Data Room.{0,20}means", r"[“\"]데이터룸[”\"](?:이라 함은|이란)")),
    Candidate("DEF.CLOSING_NET_DEBT", "DEF", "DEF.DEBT", "종결 순차입금", "Closing net debt", (r"Closing Net Debt", r"종결.{0,10}순차입금")),
    Candidate("DEF.TARGET_WORKING_CAPITAL", "DEF", "DEF.WORKING_CAPITAL", "목표운전자본", "Target working capital", (r"Target Working Capital", r"목표.{0,10}운전자본")),
    Candidate("DEF.TRANSACTION_TAX_DEDUCTION", "DEF", "DEF.TAXES", "거래 조세공제", "Transaction tax deduction", (r"Transaction Tax Deduction", r"거래.{0,10}조세.{0,10}공제")),
    # PAY
    Candidate("PAY.MILESTONE", "PAY", "PAY", "마일스톤 지급", "Milestone payment", (r"milestone payment", r"development milestone", r"regulatory milestone", r"마일스톤.{0,20}(?:지급|대금)")),
    Candidate("PAY.EARNOUT_ACCELERATION", "PAY", "PAY.EARNOUT", "언아웃 가속", "Earn-out acceleration", (r"accelerat.{0,30}earn-?out", r"earn-?out.{0,30}accelerat", r"언아웃.{0,30}가속")),
    Candidate("PAY.EARNOUT_SECURITY", "PAY", "PAY.EARNOUT", "언아웃 담보·보장", "Earn-out security", (r"security for.{0,30}earn-?out", r"guarantee.{0,30}earn-?out", r"언아웃.{0,30}(?:담보|보증)")),
    Candidate("PAY.PRICE_ADJUSTMENT_COLLAR", "PAY", "PAY.COMPLETION_ACCOUNTS", "가격조정 상·하한", "Price adjustment collar", (r"adjustment.{0,40}(?:cap|floor|collar)", r"(?:cap|floor|collar).{0,40}adjustment", r"가격조정.{0,30}(?:상한|하한)")),
    Candidate("PAY.TRUE_UP_DEADLINE", "PAY", "PAY.COMPLETION_ACCOUNTS", "정산금 지급기한", "True-up payment deadline", (r"(?:true-up|adjustment amount).{0,50}(?:business days?|pay)", r"정산금.{0,30}(?:영업일|지급기한)")),
    Candidate("PAY.EQUITY_CONSIDERATION", "PAY", "PAY", "주식·지분 대가", "Equity consideration", (r"stock consideration", r"share consideration", r"consideration shares", r"(?:주식|지분).{0,20}(?:대가|교부)")),
    # REM
    Candidate("REM.BASKET.DEDUCTIBLE", "REM", "REM.BASKET", "공제형 basket", "Deductible basket", (r"only to the extent.{0,80}(?:basket|threshold)", r"excess over.{0,40}(?:basket|threshold)", r"초과하는 부분에 한하여")),
    Candidate("REM.BASKET.TIPPING", "REM", "REM.BASKET", "소급형 basket", "Tipping basket", (r"first dollar", r"from the first dollar", r"entire amount.{0,40}(?:loss|claim)", r"전액.{0,20}(?:배상|책임)")),
    Candidate("REM.PUNITIVE_DAMAGES", "REM", "REM.CONSEQUENTIAL", "징벌적 손해 배제", "Punitive damages exclusion", (r"punitive damages", r"exemplary damages", r"징벌적.{0,10}손해")),
    Candidate("REM.RESCISSION_WAIVER", "REM", "REM.EXCLUSIVE_REMEDY", "취소·해제권 포기", "Rescission waiver", (r"waive.{0,40}(?:rescission|rescind)", r"no right to rescind", r"(?:취소권|해제권).{0,20}포기")),
    Candidate("REM.ESCROW_SOLE_RECOURSE", "REM", "REM.EXCLUSIVE_REMEDY", "에스크로 한정구제", "Escrow as sole recourse", (r"sole recourse.{0,40}escrow", r"escrow.{0,40}exclusive remedy", r"에스크로.{0,30}(?:유일|한정).{0,20}(?:구제|배상)")),
    Candidate("REM.CLAIMS_REPRESENTATIVE", "REM", "REM.DIRECT_CLAIMS", "청구대표자 절차", "Claims representative procedure", (r"(?:seller|shareholder) representative.{0,60}(?:claim|indemn)", r"청구.{0,20}대표자", r"매도인대표.{0,40}손해배상")),
    Candidate("REM.RECOVERY_PRIORITY", "REM", "REM.INDEMNITY", "배상재원 청구순서", "Recovery waterfall", (r"order of recovery", r"recovery waterfall", r"first seek recovery.{0,50}(?:escrow|insurance)", r"배상.{0,20}(?:청구순서|우선순위)")),
)


def reviewed_keys(paths: list[Path]) -> set[str]:
    keys = set(EXISTING_REVIEW_KEYS)
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        keys.update(
            str(row["file_key"])
            for row in payload.get("documents", [])
            if row.get("file_key")
        )
    return keys


def stable(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def read_text(out: Path, value: str) -> str:
    path = Path(value)
    if not path.is_absolute():
        path = out / path
    return path.read_text(encoding="utf-8", errors="replace")


def paragraph_rows(text: str) -> list[tuple[int, str]]:
    rows = []
    for line in text.splitlines():
        match = re.match(r"^\[¶(\d+)\]\s*(.*)$", line)
        if match:
            rows.append((int(match.group(1)), match.group(2).strip()))
    return rows


def legal_evidence_score(family: str, text: str) -> int:
    compact = " ".join(text.split())
    lower = compact.lower()
    score = 0
    if family == "DEF":
        score += 6 if re.search(r"\bmeans\b|이라\s*함은|이란", compact, re.I) else 0
    else:
        score -= 5 if re.search(r"\bmeans\b|이라\s*함은|이란", compact, re.I) else 0
    anchors = {
        "RW": (
            r"represent|warrant|no |not |compli|준수|위반|존재하지|없(?:다|으며|고)",
        ),
        "CP": (
            r"condition|closing|deliver|execute|선행조건|종결|인도|교부|체결",
        ),
        "COV": (
            r"\bshall\b|\bmust\b|covenant|agree|의무|하여야|하기로|협력|금지",
        ),
        "PAY": (
            r"purchase price|consideration|payment|pay |매매대금|지급|대가|정산",
        ),
        "REM": (
            r"indemn|damages|liable|claim|recovery|배상|책임|손해|청구|구제",
        ),
    }
    for pattern in anchors.get(family, ()):
        if re.search(pattern, lower, re.I):
            score += 4
    if len(compact) >= 80:
        score += 1
    if re.search(r"목차|table of contents", compact, re.I):
        score -= 8
    return score


def proportional_half_quotas(populations: dict[tuple[str, str], int]) -> dict[tuple[str, str], int]:
    target = (sum(populations.values()) + 1) // 2
    quotas = {key: count // 2 for key, count in populations.items()}
    extra = target - sum(quotas.values())
    odd = sorted(
        (key for key, count in populations.items() if count % 2),
        key=lambda key: (-populations[key], key),
    )
    for key in odd[:extra]:
        quotas[key] += 1
    return quotas


def select_half(conn: sqlite3.Connection, out: Path, excluded: set[str]) -> tuple[list[dict], dict]:
    conn.row_factory = sqlite3.Row
    rows = [
        dict(row)
        for row in conn.execute(
            """
            SELECT f.file_key,f.path,f.txt_path,f.ctype,f.lang,f.is_draft,
                   f.version_hint,f.dup_group,dm.confidence
            FROM files f JOIN doc_meta dm USING(file_key)
            WHERE f.status='ok' AND f.ctype IN ('SPA','SSA','SHA','ATA/BTA')
              AND f.txt_path IS NOT NULL
            """
        )
        if row["file_key"] not in excluded
    ]
    strata: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        row["project_key"] = _project_key(row["path"])
        strata[(row["ctype"], row["lang"])].append(row)
    populations = {key: len(value) for key, value in strata.items()}
    quotas = proportional_half_quotas(populations)
    selected: list[dict] = []
    for key in sorted(strata):
        by_project: dict[str, list[dict]] = defaultdict(list)
        for row in strata[key]:
            by_project[row["project_key"]].append(row)
        for bucket in by_project.values():
            bucket.sort(
                key=lambda row: (
                    {False: 0, None: 1, True: 2}[row["is_draft"]],
                    stable(row["file_key"]),
                )
            )
        ordered: list[dict] = []
        projects = sorted(by_project, key=stable)
        depth = 0
        while True:
            added = False
            for project in projects:
                bucket = by_project[project]
                if depth < len(bucket):
                    ordered.append(bucket[depth])
                    added = True
            if not added:
                break
            depth += 1
        selected.extend(ordered[: quotas[key]])
    summary = {
        "eligible_unreviewed_count": len(rows),
        "selected_count": len(selected),
        "selection_fraction": len(selected) / len(rows) if rows else 0,
        "population_by_stratum": {
            f"{ctype}|{lang}": populations[(ctype, lang)]
            for ctype, lang in sorted(populations)
        },
        "selected_by_stratum": {
            f"{ctype}|{lang}": quotas[(ctype, lang)]
            for ctype, lang in sorted(quotas)
        },
    }
    return selected, summary


def analyze(selected: list[dict], out: Path) -> tuple[list[dict], list[dict]]:
    compiled = {
        candidate.candidate_id: tuple(
            re.compile(pattern, re.IGNORECASE) for pattern in candidate.patterns
        )
        for candidate in CANDIDATES
    }
    evidence: dict[str, list[dict]] = defaultdict(list)
    documents = []
    for row in selected:
        text = read_text(out, row["txt_path"])
        paragraphs = paragraph_rows(text)
        hits = []
        for candidate in CANDIDATES:
            matches = [
                (legal_evidence_score(candidate.family, value), para, value)
                for para, value in paragraphs
                if any(
                    pattern.search(value)
                    for pattern in compiled[candidate.candidate_id]
                )
            ]
            found = max(matches, default=None, key=lambda row: (row[0], -row[1]))
            if found:
                score, para, value = found
                hits.append(candidate.candidate_id)
                evidence[candidate.candidate_id].append(
                    {
                        "file_key": row["file_key"],
                        "para": para,
                        "verbatim": " ".join(value.split())[:500],
                        "ctype": row["ctype"],
                        "lang": row["lang"],
                        "path": row["path"],
                        "is_draft": row["is_draft"],
                        "legal_score": score,
                    }
                )
        documents.append(
            {
                "file_key": row["file_key"],
                "path": row["path"],
                "ctype": row["ctype"],
                "lang": row["lang"],
                "is_draft": row["is_draft"],
                "version_hint": row["version_hint"],
                "confidence": row["confidence"],
                "project_key": row["project_key"],
                "candidate_hits": hits,
            }
        )
    candidates = [
        {
            "candidate_id": candidate.candidate_id,
            "family": candidate.family,
            "recommended_parent_id": candidate.recommended_parent_id,
            "label_ko": candidate.label_ko,
            "label_en": candidate.label_en,
            "document_count": len(evidence[candidate.candidate_id]),
            "evidence": sorted(
                evidence[candidate.candidate_id],
                key=lambda row: (
                    -int(row["legal_score"]),
                    {False: 0, None: 1, True: 2}[row["is_draft"]],
                    row["file_key"],
                ),
            )[:10],
        }
        for candidate in CANDIDATES
    ]
    return documents, candidates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--exclude-json", type=Path, action="append", default=[])
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    excluded = reviewed_keys(args.exclude_json)
    with sqlite3.connect(args.out / "catalog.sqlite") as conn:
        selected, selection = select_half(conn, args.out, excluded)
    documents, candidates = analyze(selected, args.out)
    payload = {
        "review_version": "v4-remaining-half-1",
        "excluded_reviewed_count": len(excluded),
        "selection": selection,
        "documents": documents,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "excluded_reviewed_count": len(excluded),
                **selection,
                "candidate_nonzero": sum(
                    row["document_count"] > 0 for row in candidates
                ),
                "json": str(args.json),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
