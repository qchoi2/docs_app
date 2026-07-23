"""Select and inspect a stratified local sample for V4 taxonomy coverage.

This is a corpus-review aid, not an extractor.  It reads the local paragraph
cache, records only bounded keyword evidence, and never calls an external API.
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
from typing import Iterable

from lib.console import configure_utf8_stdio


EXISTING_REVIEW_KEYS = {
    "0ddde0e62bd84e41",
    "ac3103e193f693ed",
    "3c86175c4821fa83",
    "2a08ef8b2699dca5",
    "b324cb8bdf00015a",
    "613cba772f0f4b93",
    "660fc9d64566ba0e",
    "a5da55951cfdabfb",
    "3b35ef6d54cdb6e1",
    "f4fe4022e47b4f21",
    "b6fd6ff14e51e05f",
    "753aeef4b323e391",
    "a51842fc51010f69",
    "dbccf24bc86783f4",
    "5acc3ac91d0f354b",
    "82832addae042265",
    "0df5e9d7e1e7c893",
    "5853fe0540a72d6c",
    "1776e6208de13ba7",
    "973d43e89040fb57",
}

PRINCIPAL_TYPES = ("SPA", "SSA", "SHA", "ATA/BTA")


def balanced_quotas(total: int) -> dict[tuple[str, str], int]:
    """Spread a sample across agreement types, then Korean/English strata."""
    if total < len(PRINCIPAL_TYPES) * 2:
        raise ValueError("sample count must be at least 8")
    per_type, type_remainder = divmod(total, len(PRINCIPAL_TYPES))
    quotas: dict[tuple[str, str], int] = {}
    for index, ctype in enumerate(PRINCIPAL_TYPES):
        type_total = per_type + (1 if index < type_remainder else 0)
        quotas[(ctype, "국문")] = (type_total + 1) // 2
        quotas[(ctype, "영문")] = type_total // 2
    return quotas


@dataclass(frozen=True)
class Concept:
    taxonomy_id: str
    family: str
    label: str
    patterns: tuple[str, ...]


CONCEPTS = (
    # RW
    Concept("RW.BENEFITS", "RW", "복리후생·연금제도", (r"employee benefit plan", r"pension plan", r"퇴직연금", r"복리후생")),
    Concept("RW.LABOR.CLASSIFICATION", "RW", "근로자·도급인 분류", (r"properly classified", r"misclassif", r"classification.{0,40}(?:employee|contractor)", r"independent contractor.{0,80}(?:classif|employee)", r"근로자성", r"위장도급")),
    Concept("RW.LABOR.COLLECTIVE", "RW", "노조·단체협약·쟁의", (r"collective bargaining", r"labor union", r"단체협약", r"노동조합", r"쟁의행위")),
    Concept("RW.LABOR.WARN", "RW", "집단해고·WARN", (r"\bWARN Act\b", r"mass layoff", r"집단해고", r"경영상 해고")),
    Concept("RW.CYBERSECURITY", "RW", "사이버보안·침해사고", (r"cybersecurity", r"data breach", r"security incident", r"정보보안", r"침해사고")),
    Concept("RW.SANCTIONS", "RW", "경제제재·수출통제", (r"economic sanctions", r"sanctioned person", r"export control", r"경제제재", r"수출통제")),
    Concept("RW.ANTI_BRIBERY", "RW", "반부패·뇌물방지", (r"Foreign Corrupt Practices Act", r"anti-bribery", r"anti-corruption", r"부패방지", r"뇌물")),
    Concept("RW.AML", "RW", "자금세탁방지", (r"anti-money laundering", r"money laundering", r"자금세탁")),
    Concept("RW.CUSTOMERS_SUPPLIERS", "RW", "주요 고객·공급업체", (r"top customers?", r"material suppliers?", r"major customers?", r"주요 고객", r"주요 공급")),
    Concept("RW.PRODUCTS", "RW", "제품책임·리콜·보증", (r"product liability", r"product recall", r"product warrant", r"제품책임", r"리콜", r"품질보증")),
    Concept("RW.RELATED_PARTY", "RW", "특수관계인 거래", (r"related party transaction", r"affiliate transaction", r"특수관계인 거래", r"관계회사 거래")),
    Concept("RW.BROKERS", "RW", "브로커·자문수수료", (r"brokerage fee", r"finder.?s fee", r"investment banker", r"중개수수료", r"자문수수료")),
    Concept("RW.GOVERNMENT_CONTRACTS", "RW", "정부계약", (r"government contract", r"government bid", r"정부계약", r"공공입찰")),
    Concept("RW.BOOKS_RECORDS", "RW", "장부·기록 정확성", (r"books and records", r"corporate records", r"장부와 기록", r"회계장부")),
    Concept("RW.INTERNAL_CONTROLS", "RW", "내부회계통제", (r"internal controls?", r"disclosure controls?", r"내부회계관리", r"내부통제")),
    Concept("RW.NO_UNDISCLOSED_LIABILITIES", "RW", "미공개 채무 부재", (r"undisclosed liabilities", r"no liabilities", r"우발채무", r"미공개 채무")),
    # COV
    Concept("COV.EFFORTS.STANDARD", "COV", "노력의무 기준", (r"reasonable best efforts", r"commercially reasonable efforts", r"best efforts", r"최선의 노력", r"합리적인 노력")),
    Concept("COV.D_AND_O", "COV", "임원 면책·D&O tail", (r"D&O tail", r"directors.? and officers. insurance", r"indemnification of directors", r"임원배상책임보험", r"이사.*면책")),
    Concept("COV.TAX", "COV", "조세신고·협력·선택", (r"tax return", r"tax cooperation", r"tax election", r"조세신고", r"세무.*협조", r"조세.*선택")),
    Concept("COV.TRANSITION", "COV", "전환·분리 서비스", (r"transition services?", r"transitional services?", r"전환서비스", r"분리.*지원")),
    Concept("COV.INSURANCE", "COV", "보험 유지", (r"maintain.*insurance", r"insurance coverage", r"보험.*유지")),
    Concept("COV.DEBT_RELEASE", "COV", "채무상환·담보해제", (r"payoff letter", r"release of liens", r"repay.*indebtedness", r"채무.*상환", r"담보.*해지")),
    Concept("COV.NOTICE_UPDATE", "COV", "변경·위반 통지", (r"promptly notify.{0,100}(?:breach|change|condition)", r"notice of.{0,60}breach", r"(?:변경|위반|부정확).{0,60}통지", r"통지.{0,60}(?:변경|위반|부정확)")),
    Concept("COV.DISCLOSURE_UPDATE", "COV", "공개목록 갱신", (r"supplement.*disclosure schedule", r"update.*disclosure schedule", r"공개.*갱신", r"공개목록.*수정")),
    Concept("COV.RELEASE", "COV", "상호·당사자 면책", (r"mutual release", r"release and discharge", r"청구.*포기", r"면제.*면책")),
    Concept("COV.RWI", "COV", "진술보장보험 협력", (r"representation.*warranty insurance", r"\bRWI\b", r"진술보장보험")),
    Concept("COV.SHA.TRANSFER", "COV", "주식양도 제한", (r"transfer restriction", r"shall not transfer", r"주식.*양도.*제한")),
    Concept("COV.SHA.PREEMPTIVE", "COV", "신주인수·희석방지", (r"preemptive right", r"pre-emption right", r"신주인수권", r"희석방지")),
    Concept("COV.SHA.DEADLOCK", "COV", "교착상태", (r"\bdeadlock\b", r"교착상태")),
    Concept("COV.SHA.EXIT", "COV", "IPO·매각 출구", (r"initial public offering", r"\bIPO\b", r"exit sale", r"기업공개", r"동반매도", r"강제매도")),
    # CP
    Concept("CP.ANCILLARY", "CP", "부속계약 체결", (r"ancillary agreement", r"transaction documents? shall", r"부속계약", r"거래문서.*체결")),
    Concept("CP.DEBT_RELEASE", "CP", "채무상환·담보말소", (r"payoff letter", r"lien release", r"담보권.*말소", r"채무.*상환.*완료")),
    Concept("CP.RESIGNATION", "CP", "임원 사임", (r"resignation letters?", r"director.*resign", r"임원.*사임", r"이사.*사임")),
    Concept("CP.LEGAL_OPINION", "CP", "법률의견서", (r"(?:deliver|receive|closing).{0,100}legal opinion", r"opinion of counsel.{0,100}(?:closing|deliver)", r"(?:종결|인도).{0,50}법률의견서", r"법률의견서.{0,50}(?:제공|인도)")),
    Concept("CP.CLOSING_CERTIFICATE", "CP", "종결증명서", (r"closing certificate", r"officer.?s certificate", r"종결.*확인서", r"이행.*확인서")),
    Concept("CP.FINANCIAL_STATEMENTS", "CP", "재무제표 제공", (r"(?:deliver|provide).{0,100}audited financial statements", r"audited financial statements.{0,100}(?:deliver|provide)", r"감사받은 재무제표.{0,50}(?:제공|인도)", r"재무제표.{0,50}(?:제공|인도)")),
    Concept("CP.TAX_RULING", "CP", "세무확인·예규", (r"tax ruling", r"tax clearance", r"납세증명", r"세무.*확인")),
    # DEF
    Concept("DEF.MAE", "DEF", "중대한 부정적 영향", (r"material adverse (?:effect|change)", r"중대한 부정적 (?:영향|변경)")),
    Concept("DEF.KNOWLEDGE", "DEF", "인식·지식", (r"knowledge of (?:the )?(?:seller|company)", r"actual knowledge", r"합리적.*조사", r"알고 있는 한", r"인식")),
    Concept("DEF.PERMITTED_LIEN", "DEF", "허용된 담보권", (r"permitted liens?", r"permitted encumbrances?", r"허용된 담보", r"허용된 부담")),
    Concept("DEF.DEBT", "DEF", "순차입금·채무", (r"indebtedness means", r"net debt", r"순차입금", r"차입금.*의미")),
    Concept("DEF.WORKING_CAPITAL", "DEF", "운전자본", (r"working capital", r"운전자본")),
    Concept("DEF.TRANSACTION_EXPENSES", "DEF", "거래비용", (r"transaction expenses?", r"seller expenses?", r"거래비용")),
    Concept("DEF.FUNDAMENTAL_REPS", "DEF", "기본 진술보장", (r"fundamental representations?", r"fundamental warranties", r"기본 진술", r"핵심 진술")),
    Concept("DEF.FRAUD", "DEF", "사기", (r"\bfraud\b", r"사기")),
    Concept("DEF.LEAKAGE", "DEF", "가치유출·Leakage", (r"permitted leakage", r"\bleakage\b", r"가치유출")),
    Concept("DEF.EARNOUT_METRIC", "DEF", "언아웃 성과지표", (r"earnout revenue", r"earnout EBITDA", r"earn-out period", r"성과지표", r"언아웃 기간")),
    # PAY
    Concept("PAY.LOCKED_BOX", "PAY", "Locked-box·leakage", (r"locked.box", r"permitted leakage", r"leakage amount", r"락트박스", r"가치유출")),
    Concept("PAY.COMPLETION_ACCOUNTS", "PAY", "종결계정·사후조정", (r"completion accounts?", r"closing statement", r"final purchase price", r"종결재무제표", r"사후정산", r"매매대금.*조정")),
    Concept("PAY.ESCROW", "PAY", "에스크로·유보", (r"\bescrow\b", r"\bholdback\b", r"예치금", r"유보금")),
    Concept("PAY.EARNOUT", "PAY", "언아웃·조건부대금", (r"earn.?out", r"contingent consideration", r"조건부.*대금", r"추가.*매매대금")),
    Concept("PAY.ROLLOVER", "PAY", "재투자·롤오버", (r"rollover", r"reinvestment", r"재투자")),
    Concept("PAY.SELLER_NOTE", "PAY", "매도인 대여금·어음", (r"seller note", r"promissory note.{0,100}(?:issued by Buyer|purchase price|consideration)", r"(?:매수인|대상회사).{0,50}매도인.{0,50}(?:대여|어음)", r"매도인.*대여")),
    Concept("PAY.WITHHOLDING", "PAY", "원천징수·공제", (r"(?:payment|purchase price|consideration|amount payable).{0,100}(?:withhold|deduct)", r"(?:withhold|deduct).{0,100}(?:payment|purchase price|consideration|amount payable)", r"(?:대금|지급액).{0,50}원천징수", r"원천징수.{0,50}(?:대금|지급액)")),
    Concept("PAY.INTEREST", "PAY", "지연·할부 이자", (r"default interest", r"interest rate", r"지연이자", r"연체이자")),
    Concept("PAY.ALLOCATION", "PAY", "대금배분", (r"purchase price allocation", r"allocation schedule", r"매매대금.*배분", r"양도가액.*배분")),
    Concept("PAY.FX", "PAY", "환율·통화환산", (r"exchange rate", r"currency conversion", r"환율", r"통화.*환산")),
    Concept("PAY.PAYING_AGENT", "PAY", "지급대리인", (r"paying agent", r"payment agent", r"지급대리인")),
    Concept("PAY.DISPUTE_ACCOUNTANT", "PAY", "독립회계인 조정", (r"independent accountant", r"accounting referee", r"독립.*회계", r"회계법인.*결정")),
    Concept("PAY.DEPOSIT", "PAY", "계약금·중도금·잔금", (r"deposit amount", r"down payment", r"계약금", r"중도금", r"잔금")),
    # REM
    Concept("REM.BASKET", "REM", "basket·공제기준", (r"\bbasket\b", r"deductible basket", r"tipping basket", r"공제액", r"최저청구")),
    Concept("REM.DE_MINIMIS", "REM", "de minimis", (r"de minimis", r"개별.*최저", r"건별.*기준")),
    Concept("REM.CONSEQUENTIAL", "REM", "간접·결과손해 배제", (r"consequential damages?", r"indirect damages?", r"punitive damages?", r"간접손해", r"특별손해")),
    Concept("REM.TAX_BENEFIT", "REM", "세금효과 차감", (r"tax benefit", r"tax savings?", r"세금효과", r"절세효과")),
    Concept("REM.INSURANCE_RECOVERY", "REM", "보험금·제3자 회수 차감", (r"insurance proceeds?", r"third.party recover", r"보험금.*공제", r"제3자.*회수")),
    Concept("REM.SUBROGATION", "REM", "대위권", (r"\bsubrogation\b", r"대위권")),
    Concept("REM.SANDBAGGING", "REM", "sandbagging·인지효과", (r"pro.sandbag", r"anti.sandbag", r"knowledge.{0,120}(?:shall not affect|no effect).{0,80}(?:indemnif|remed)", r"알고.{0,100}(?:손해배상|배상책임)", r"인지.{0,100}(?:손해배상|배상책임)")),
    Concept("REM.THIRD_PARTY_CLAIMS", "REM", "제3자 청구절차", (r"third.party claim", r"제3자.*청구")),
    Concept("REM.DIRECT_CLAIMS", "REM", "직접청구절차", (r"direct claim", r"직접.*청구")),
    Concept("REM.EXCLUSIVE_REMEDY", "REM", "배타적 구제", (r"exclusive remedy", r"sole and exclusive remedy", r"유일한 구제", r"배타적.*구제")),
    Concept("REM.SPECIFIC_PERFORMANCE", "REM", "특정이행·강제이행", (r"specific performance", r"injunctive relief", r"강제이행", r"특정이행")),
    Concept("REM.MITIGATION", "REM", "손해경감", (r"mitigat.*loss", r"duty to mitigate", r"손해.*경감")),
    Concept("REM.NO_DOUBLE_RECOVERY", "REM", "이중배상 금지", (r"double recovery", r"duplicative recovery", r"이중.*배상", r"중복.*보상")),
    Concept("REM.FRAUD_CARVEOUT", "REM", "사기 carve-out", (r"except.*fraud", r"fraud.*shall not", r"사기.*제외", r"사기.*제한.*적용")),
    Concept("REM.DEPOSIT_FORFEITURE", "REM", "계약금 몰취·배액상환", (r"forfeit.*deposit", r"retain.*deposit", r"계약금.*몰취", r"배액.*상환", r"배액.*배상")),
    Concept("REM.LIQUIDATED_DAMAGES", "REM", "위약벌·손해배상액 예정", (r"liquidated damages", r"penalty payment", r"위약벌", r"손해배상액의 예정", r"위약금")),
    Concept("REM.TERMINATION_FEE", "REM", "해제·break fee", (r"termination fee", r"break.?up fee", r"reverse termination fee", r"해제.*수수료", r"종료.*수수료")),
)


US_MARKERS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"Delaware General Corporation Law",
        r"Hart.Scott.Rodino",
        r"Securities Act of 1933",
        r"Securities Exchange Act of 1934",
        r"Internal Revenue Code",
        r"New York law",
        r"Delaware law",
        r"\bSEC\b",
        r"\bCFIUS\b",
    )
)


def _read_text(out: Path, txt_path: str) -> str:
    path = Path(txt_path)
    if not path.is_absolute():
        path = out / path
    return path.read_text(encoding="utf-8", errors="replace")


def _project_key(path: str) -> str:
    name = Path(path).stem.casefold()
    for marker in (
        "buyer",
        "seller",
        "draft",
        "markup",
        "execution",
        "executed",
        "final",
        "clean",
        "signed",
        "auction",
        "redline",
        "comments",
        "copy",
        "초안",
        "체결본",
        "양수인",
        "양도인",
        "매수인",
        "매도인",
        "검토본",
        "수정본",
        "입찰",
    ):
        name = name.replace(marker, " ")
    name = re.sub(
        r"\b(?:v?\d+(?:\.\d+)*|20\d{2}[01]\d[0-3]\d|"
        r"\d+(?:st|nd|rd|th)|near|bkl|version)\b",
        " ",
        name,
    )
    name = re.sub(r"[^0-9a-z가-힣]+", " ", name)
    tokens = [token for token in name.split() if len(token) > 1]
    agreement_tokens = {
        "spa",
        "ssa",
        "sha",
        "bta",
        "ata",
        "rra",
        "주식매매계약",
        "주식매매계약서",
        "신주인수계약",
        "신주인수계약서",
        "영업양수도계약",
        "자산양수도계약",
        "sharepurchaseagreement",
        "sharesubscriptionagreement",
        "shareholdersagreement",
        "masterpurchaseagreement",
    }
    for index, token in enumerate(tokens):
        if token in agreement_tokens:
            return " ".join(tokens[: index + 1])
    return " ".join(tokens[:3]) or hashlib.sha1(path.encode("utf-8")).hexdigest()


def _stable_key(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def _us_score(text: str) -> int:
    return sum(bool(pattern.search(text)) for pattern in US_MARKERS)


def select_sample(
    conn: sqlite3.Connection,
    out: Path,
    *,
    count: int = 100,
    excluded_keys: set[str] | None = None,
) -> list[dict]:
    conn.row_factory = sqlite3.Row
    quotas = balanced_quotas(count)
    excluded = set(EXISTING_REVIEW_KEYS)
    excluded.update(excluded_keys or ())
    selected: list[dict] = []
    used_projects: set[tuple[str, str, str]] = set()
    for (ctype, lang), quota in quotas.items():
        candidates = []
        for row in conn.execute(
            """
            SELECT f.file_key,f.path,f.txt_path,f.ctype,f.lang,f.is_draft,
                   f.version_hint,f.dup_group,dm.confidence
            FROM files f
            JOIN doc_meta dm USING(file_key)
            WHERE f.status='ok' AND f.ctype=? AND f.lang=?
              AND f.txt_path IS NOT NULL
            """,
            (ctype, lang),
        ):
            if row["file_key"] in excluded:
                continue
            text = _read_text(out, row["txt_path"])
            candidate = dict(row)
            candidate["project_key"] = _project_key(row["path"])
            candidate["us_marker_score"] = _us_score(text)
            candidate["_text"] = text
            candidates.append(candidate)
        # Prefer actual US-law markers in the English strata, then interleave
        # draft/executed/unknown status using a stable pseudo-random order.
        buckets: dict[object, list[dict]] = defaultdict(list)
        for candidate in candidates:
            buckets[candidate["is_draft"]].append(candidate)
        for bucket in buckets.values():
            bucket.sort(
                key=lambda row: (
                    -row["us_marker_score"] if lang == "영문" else 0,
                    _stable_key(row["file_key"]),
                )
            )
        bucket_order = [False, True, None]
        cursor = 0
        while len([row for row in selected if row["ctype"] == ctype and row["lang"] == lang]) < quota:
            progress = False
            bucket_key = bucket_order[cursor % len(bucket_order)]
            cursor += 1
            bucket = buckets.get(bucket_key, [])
            while bucket:
                candidate = bucket.pop(0)
                project = (ctype, lang, candidate["project_key"])
                if project in used_projects:
                    continue
                used_projects.add(project)
                selected.append(candidate)
                progress = True
                break
            if not progress and all(not buckets.get(key) for key in bucket_order):
                raise RuntimeError(f"not enough candidates for {ctype}/{lang}")
    if len(selected) != count:
        raise RuntimeError(f"expected {count} documents, selected {len(selected)}")
    return selected


def _paragraphs(text: str) -> list[tuple[int, str]]:
    rows = []
    for line in text.splitlines():
        match = re.match(r"^\[¶(\d+)\]\s*(.*)$", line)
        if match:
            rows.append((int(match.group(1)), match.group(2).strip()))
    return rows


def analyze(selected: Iterable[dict]) -> tuple[list[dict], dict[str, list[dict]]]:
    compiled = {
        concept.taxonomy_id: tuple(
            re.compile(pattern, re.IGNORECASE) for pattern in concept.patterns
        )
        for concept in CONCEPTS
    }
    per_document = []
    evidence: dict[str, list[dict]] = defaultdict(list)
    for row in selected:
        paragraphs = _paragraphs(row["_text"])
        hits = []
        for concept in CONCEPTS:
            found = None
            for para, text in paragraphs:
                if any(pattern.search(text) for pattern in compiled[concept.taxonomy_id]):
                    found = {
                        "file_key": row["file_key"],
                        "para": para,
                        "verbatim": " ".join(text.split())[:240],
                        "ctype": row["ctype"],
                        "lang": row["lang"],
                    }
                    break
            if found:
                hits.append(concept.taxonomy_id)
                evidence[concept.taxonomy_id].append(found)
        per_document.append(
            {
                key: row[key]
                for key in (
                    "file_key",
                    "path",
                    "ctype",
                    "lang",
                    "is_draft",
                    "version_hint",
                    "confidence",
                    "project_key",
                    "us_marker_score",
                )
            }
            | {"concepts": hits}
        )
    return per_document, evidence


def _examples(rows: list[dict], limit: int = 3) -> str:
    return ", ".join(f"[{row['file_key']}] ¶{row['para']}" for row in rows[:limit])


def render_report(
    documents: list[dict],
    evidence: dict[str, list[dict]],
    *,
    excluded_prior_count: int,
) -> str:
    strata = Counter((row["ctype"], row["lang"]) for row in documents)
    status = Counter(
        "초안" if row["is_draft"] == 1 else "체결/비초안" if row["is_draft"] == 0 else "판별불가"
        for row in documents
    )
    family_counts = Counter()
    for concept in CONCEPTS:
        if evidence.get(concept.taxonomy_id):
            family_counts[concept.family] += 1
    lines = [
        f"# V4 색인범위 추가 검토 — M&A 계약 {len(documents)}건",
        "",
        f"_검토일: 2026-07-23. 기존 검토 {excluded_prior_count}건과 중복되지 않는 로컬 코퍼스 {len(documents)}건을",
        "유형·언어별 층화 선정하고, 관련 문단의 제한된 키워드 근거를 점검했다.",
        "유료 API는 사용하지 않았다._",
        "",
        "## 표본 구성",
        "",
        "| 계약유형 | 국문 | 영문 | 합계 |",
        "|---|---:|---:|---:|",
    ]
    for ctype in ("SPA", "SSA", "SHA", "ATA/BTA"):
        ko = strata[(ctype, "국문")]
        en = strata[(ctype, "영문")]
        lines.append(f"| {ctype} | {ko} | {en} | {ko + en} |")
    lines.extend(
        [
            f"| 합계 | {sum(strata[(ctype, '국문')] for ctype in PRINCIPAL_TYPES)} | "
            f"{sum(strata[(ctype, '영문')] for ctype in PRINCIPAL_TYPES)} | {len(documents)} |",
            "",
            f"- 문서 상태: 체결/비초안 {status['체결/비초안']}건, 초안 {status['초안']}건, 판별불가 {status['판별불가']}건.",
            f"- 영문 표본 중 미국 법·규제 표지가 직접 검출된 문서: {sum(row['us_marker_score'] > 0 for row in documents)}건.",
            "- 영문은 모두 미국 계약으로 단정하지 않고, 미국형 drafting 요소의 관찰 표본으로 사용했다.",
            "",
            "## 개념 검출 요약",
            "",
            "| family | 검출된 세부 개념 수 |",
            "|---|---:|",
        ]
    )
    for family in ("RW", "CP", "COV", "DEF", "PAY", "REM"):
        lines.append(f"| {family} | {family_counts[family]} |")
    lines.extend(
        [
            "",
            "아래 건수는 해당 표현이 한 번 이상 검출된 문서 수다. 법률효과의 최종 분류는",
            "V4 원자 추출 단계에서 문맥을 확인해야 하며, 이 검토만으로 조항의 부재를 판정하지 않는다.",
            "",
        ]
    )
    for family in ("RW", "CP", "COV", "DEF", "PAY", "REM"):
        lines.extend([f"### {family}", "", "| 제안 taxonomy | 개념 | 문서 수 | 근거 예시 |", "|---|---|---:|---|"])
        for concept in (item for item in CONCEPTS if item.family == family):
            rows = evidence.get(concept.taxonomy_id, [])
            if rows:
                lines.append(
                    f"| `{concept.taxonomy_id}` | {concept.label} | {len(rows)} | {_examples(rows)} |"
                )
        lines.append("")
    lines.extend(
        [
            "자동 집계는 위 개념을 포함할 가능성이 있는 문구의 문서 수이며 조항 존재 확정치가",
            "아니다. 목차·정의·다른 family에서 발견된 표현은 V4 추출 시 운영문구와 문맥을",
            "다시 확인하고, 완전성은 body와 참조자료 coverage로 별도 판정한다.",
            "",
            "## V4 보강 결론",
            "",
            "1. RW는 종전 도메인 외에 복리후생·연금, 근로자 분류, 노조·단체협약,",
            "   사이버보안, 제재·수출통제, AML, 고객·공급업체, 제품책임, 특수관계인,",
            "   브로커, 정부계약, 장부·내부통제·미공개채무를 독립 원자 항목으로 둔다.",
            "2. COV는 노력의무의 강도, D&O tail, 조세협력, 전환서비스, 보험유지,",
            "   채무상환·담보해제, 변경통지, 공개목록 갱신, RWI, release와 SHA의",
            "   양도제한·신주인수권·deadlock·exit를 세분화한다.",
            "3. CP는 부속계약, payoff·담보해제, 임원사임, 법률의견서, 종결증명서,",
            "   재무제표, 세무확인을 별도 항목으로 둔다.",
            "4. DEF는 MAE·Knowledge의 구성요소뿐 아니라 Debt·Working Capital·",
            "   Transaction Expenses·Leakage·Earn-out metric 등의 계약별 산식과",
            "   포함·제외·threshold를 원자화한다.",
            "5. PAY는 completion accounts와 locked-box를 구분하고 escrow, earn-out,",
            "   rollover, seller note, withholding, interest, allocation, FX, paying agent,",
            "   독립회계인 분쟁절차 및 한국형 계약금·중도금·잔금을 분리한다.",
            "6. REM은 basket/de minimis, 간접손해 배제, tax benefit·보험금 차감,",
            "   subrogation, sandbagging, 직접·제3자 청구, fraud carve-out, 계약금 몰취,",
            "   위약벌·손해배상액 예정 및 termination fee를 독립 항목으로 둔다.",
            "7. 동일 문구가 여러 기능을 가지면 복수 family item으로 저장하되",
            "   `related_item_ref`로 연결한다. 특히 payoff(PAY/COV/CP), 계약금",
            "   (PAY/REM), Fraud(DEF/REM), RWI(COV/REM)가 이에 해당한다.",
            "",
            f"## 표본 {len(documents)}건",
            "",
            "| # | file_key | 유형 | 언어 | 초안 | 경로 |",
            "|---:|---|---|---|---|---|",
        ]
    )
    for index, row in enumerate(documents, 1):
        draft = "Y" if row["is_draft"] == 1 else "N" if row["is_draft"] == 0 else "?"
        path = str(row["path"]).replace("|", "\\|")
        lines.append(
            f"| {index} | {row['file_key']} | {row['ctype']} | {row['lang']} | {draft} | {path} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument(
        "--exclude-json",
        type=Path,
        action="append",
        default=[],
        help="Prior review JSON whose document file_keys must be excluded",
    )
    parser.add_argument("--review-version")
    args = parser.parse_args()
    excluded_keys = set(EXISTING_REVIEW_KEYS)
    for path in args.exclude_json:
        prior = json.loads(path.read_text(encoding="utf-8"))
        excluded_keys.update(
            str(row["file_key"])
            for row in prior.get("documents", [])
            if row.get("file_key")
        )
    with sqlite3.connect(args.out / "catalog.sqlite") as conn:
        selected = select_sample(
            conn,
            args.out,
            count=args.count,
            excluded_keys=excluded_keys,
        )
    documents, evidence = analyze(selected)
    payload = {
        "review_version": args.review_version or f"v4-scope-{args.count}-1",
        "count": len(documents),
        "excluded_prior_count": len(excluded_keys),
        "documents": documents,
        "concepts": [
            {
                "taxonomy_id": concept.taxonomy_id,
                "family": concept.family,
                "label": concept.label,
                "document_count": len(evidence.get(concept.taxonomy_id, [])),
                "evidence": evidence.get(concept.taxonomy_id, [])[:5],
            }
            for concept in CONCEPTS
        ],
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    args.report.write_text(
        render_report(
            documents,
            evidence,
            excluded_prior_count=len(excluded_keys),
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "count": len(documents),
                "json": str(args.json),
                "report": str(args.report),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
