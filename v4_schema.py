"""Schema, seed taxonomy, and result validation for V4 clause items."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from review_rw_leaf_gaps import LEAVES as RW_REFINEMENT_LEAVES


V4_SCHEMA_VERSION = 4
V4_SCHEMA_REVISION = "1R2"
DEFAULT_TAXONOMY_VERSION = 12
FAMILIES = ("RW", "CP", "COV", "DEF", "PAY", "REM")
CONFIDENCE_VALUES = ("low", "med", "high")
POLARITY_VALUES = ("affirmative", "negative", "none_exist", "not_applicable")
BODY_STATUS_VALUES = ("complete", "partial", "not_evaluated", "unreadable")
ANNEX_STATUS_VALUES = ("complete", "partial", "not_evaluated", "unreadable", "no_annex")
REVIEW_STATUS_VALUES = ("pending", "approved", "needs_review", "rejected")
SOURCE_KIND_VALUES = ("body", "schedule", "disclosure_schedule", "annex", "exhibit")
SOURCE_STATUS_VALUES = ("complete", "partial", "not_evaluated", "unreadable", "missing")


@dataclass(frozen=True)
class TaxonomySeed:
    taxonomy_id: str
    parent_id: Optional[str]
    family: str
    canonical_ko: str
    canonical_en: str
    definition: str
    depth: int
    aliases: Tuple[str, ...] = ()


SEED_TAXONOMY: Tuple[TaxonomySeed, ...] = (
    TaxonomySeed("RW", None, "RW", "진술보장", "Representations and warranties", "사실·상태에 관한 진술과 보장", 0, ("진술 및 보장", "R&W")),
    TaxonomySeed("CP", None, "CP", "선행조건", "Conditions precedent", "거래종결 의무의 발생 조건", 0, ("종결조건", "closing conditions")),
    TaxonomySeed("COV", None, "COV", "확약", "Covenants", "체결 전후 당사자의 작위·부작위 의무", 0, ("서약", "undertakings")),
    TaxonomySeed("RW.AUTHORITY", "RW", "RW", "권한·구속력", "Authority and enforceability", "설립·존속·권한·내부승인·구속력", 1, ("적법한 설립", "내부수권", "binding obligation")),
    TaxonomySeed("RW.CAPITALIZATION", "RW", "RW", "자본구조", "Capitalization", "발행주식·지분·증권·소유권", 1, ("capital structure", "발행주식총수")),
    TaxonomySeed("RW.FINANCIAL", "RW", "RW", "재무", "Financial statements", "재무제표·채무·재무상태", 1, ("재무제표", "financial statements")),
    TaxonomySeed("RW.ASSETS", "RW", "RW", "자산", "Assets", "자산의 소유권·충분성·담보", 1, ("title to assets", "자산 소유권")),
    TaxonomySeed("RW.CONTRACTS", "RW", "RW", "중요계약", "Material contracts", "중요계약의 존재·효력·위반", 1, ("material contracts", "중요한 계약")),
    TaxonomySeed("RW.LABOR", "RW", "RW", "인사·노무", "Labor and employment", "임직원·노동관계·임금·퇴직급여", 1, ("인사노무", "employment")),
    TaxonomySeed(
        "RW.LABOR.NO_VIOLATION",
        "RW.LABOR",
        "RW",
        "노무 관련 위반사항 없음",
        "No labor violation",
        "노동·고용 관련 법령, 단체협약 또는 근로계약 위반의 부재",
        2,
        ("노동법 위반 없음", "근로관계법령 위반 없음", "no violation of labor laws"),
    ),
    TaxonomySeed(
        "RW.LABOR.WORKING_CONDITIONS",
        "RW.LABOR",
        "RW",
        "근로조건 준수",
        "Compliance with working conditions",
        "근로시간·휴일·휴가·복리후생 등 근로조건 준수",
        2,
        ("근로조건 준수", "근로기준 준수", "compliance with terms of employment"),
    ),
    TaxonomySeed(
        "RW.LABOR.NO_OFF_BOOK_WAGES",
        "RW.LABOR",
        "RW",
        "규정 외 임금 없음",
        "No off-book wages",
        "취업규칙·급여규정·근로계약 등에 드러나지 않은 별도 임금·수당 약정의 부재",
        2,
        ("장부 외 임금 없음", "별도 임금 약정 없음", "no off-book compensation"),
    ),
    TaxonomySeed(
        "RW.LABOR.UNPAID_COMPENSATION",
        "RW.LABOR",
        "RW",
        "미지급 보수 없음",
        "No unpaid compensation",
        "임금·수당·상여·퇴직급여 등 지급기일이 도래한 보수의 미지급 부재",
        2,
        ("미지급 임금 없음", "체불임금 없음", "미불임금 없음", "no unpaid wages"),
    ),
    TaxonomySeed("RW.TAX", "RW", "RW", "조세", "Tax", "세금 신고·납부·조사·분쟁", 1, ("세무", "tax matters")),
    TaxonomySeed("RW.ENVIRONMENT", "RW", "RW", "환경", "Environmental", "환경법·오염·인허가", 1, ("environmental matters", "환경법")),
    TaxonomySeed("RW.IP", "RW", "RW", "지식재산", "Intellectual property", "지식재산권 소유·사용·침해", 1, ("IP", "intellectual property")),
    TaxonomySeed("RW.PRIVACY", "RW", "RW", "개인정보", "Privacy and data", "개인정보·데이터 보호·보안", 1, ("data privacy", "개인정보보호")),
    TaxonomySeed("RW.INSURANCE", "RW", "RW", "보험", "Insurance", "보험계약·보장범위·청구", 1, ("insurance policies", "보험계약")),
    TaxonomySeed("RW.COMPLIANCE", "RW", "RW", "법규준수·반부패", "Compliance and anti-corruption", "법령 준수·부패방지·제재", 1, ("compliance with laws", "anti-corruption")),
    TaxonomySeed("RW.LITIGATION", "RW", "RW", "소송·분쟁", "Litigation", "소송·중재·행정절차·조사", 1, ("legal proceedings", "분쟁")),
    TaxonomySeed("RW.PERMITS", "RW", "RW", "인허가", "Permits", "영업에 필요한 인허가의 보유·유효성", 1, ("licenses and permits", "정부 인허가")),
    TaxonomySeed("RW.REAL_ESTATE", "RW", "RW", "부동산", "Real estate", "소유·임차 부동산과 권원", 1, ("real property", "임대차")),
    TaxonomySeed("CP.APPROVAL", "CP", "CP", "내부승인", "Corporate approval", "이사회 등 당사자 내부승인", 1, ("board approval", "이사회 승인")),
    TaxonomySeed("CP.FILING", "CP", "CP", "정부신고", "Government filing", "정부기관 신고·대기기간 경과", 1, ("regulatory filing", "신고 수리")),
    TaxonomySeed("CP.GOVERNMENT_APPROVAL", "CP", "CP", "정부승인", "Government approval", "정부기관의 허가·승인·인가", 1, ("regulatory approval", "관계기관 승인")),
    TaxonomySeed("CP.THIRD_PARTY_CONSENT", "CP", "CP", "제3자동의", "Third-party consent", "계약상대방 등 제3자의 동의·면제", 1, ("third party consent", "계약이전동의")),
    TaxonomySeed("CP.DELIVERABLE", "CP", "CP", "종결서류", "Closing deliverables", "증명서·사임서·양도서류 등 종결 인도물", 1, ("closing documents", "종결 인도물")),
    TaxonomySeed("CP.REPRESENTATIONS", "CP", "CP", "진술보장 정확성", "Accuracy of representations", "종결 시 진술보장의 정확성", 1, ("bring-down", "진술보장 진실성")),
    TaxonomySeed("CP.COVENANTS", "CP", "CP", "확약 이행", "Covenant performance", "종결 전 확약·의무의 이행", 1, ("covenant compliance", "의무 이행")),
    TaxonomySeed("CP.NO_PROHIBITION", "CP", "CP", "금지조치 부재", "No prohibition", "금지명령·법령상 장애 부재", 1, ("no injunction", "금지명령 부재")),
    TaxonomySeed("CP.NO_MAC", "CP", "CP", "MAC 부재", "No material adverse effect", "중대한 부정적 영향의 부재", 1, ("no MAE", "중대한 부정적 변경 부재")),
    TaxonomySeed("CP.FINANCING", "CP", "CP", "자금조달", "Financing", "인수금융·투자금 조달", 1, ("financing condition", "자금조달 완료")),
    TaxonomySeed("CP.REORGANIZATION", "CP", "CP", "사전 구조개편", "Pre-closing reorganization", "분할·합병·현물출자 등 사전 구조개편", 1, ("pre-closing reorganization", "사전개편")),
    TaxonomySeed("COV.ORDINARY_COURSE", "COV", "COV", "통상영업", "Ordinary course", "종결 전 통상적인 사업과정 유지", 1, ("ordinary course of business", "통상적인 영업")),
    TaxonomySeed("COV.RESTRICTED_ACTIONS", "COV", "COV", "행위제한", "Restricted actions", "상대방 동의 없는 중요행위 금지", 1, ("negative covenants", "사전동의사항")),
    TaxonomySeed("COV.REGULATORY", "COV", "COV", "신고·승인 협력", "Regulatory cooperation", "신고·승인 취득과 규제기관 대응 협력", 1, ("regulatory efforts", "정부승인 협력")),
    TaxonomySeed("COV.THIRD_PARTY_CONSENT", "COV", "COV", "제3자동의 취득", "Third-party consent efforts", "제3자동의·계약승계 동의 취득 노력", 1, ("consent efforts", "동의 취득")),
    TaxonomySeed("COV.INFORMATION", "COV", "COV", "정보·접근", "Information and access", "자료제공·실사·장부 접근", 1, ("access to information", "자료 제공")),
    TaxonomySeed("COV.PERSONNEL", "COV", "COV", "인사", "Personnel", "임직원 유지·승계·보상·퇴직", 1, ("employee matters", "임직원 승계")),
    TaxonomySeed("COV.CONFIDENTIALITY", "COV", "COV", "비밀유지", "Confidentiality", "거래·당사자·영업정보 비공개", 1, ("NDA", "비밀정보")),
    TaxonomySeed("COV.NON_COMPETE", "COV", "COV", "경업금지", "Non-compete", "경쟁사업 영위·투자 제한", 1, ("noncompetition", "경쟁금지")),
    TaxonomySeed("COV.NON_SOLICIT", "COV", "COV", "유인금지", "Non-solicitation", "임직원·고객·거래처 유인 제한", 1, ("non-solicitation", "채용금지")),
    TaxonomySeed("COV.EXCLUSIVITY", "COV", "COV", "배타적협상", "Exclusivity", "제3자 거래제안·협상 금지", 1, ("no-shop", "독점협상")),
    TaxonomySeed("COV.PUBLICITY", "COV", "COV", "공표·공시", "Publicity", "보도자료·공시·대외발표 제한", 1, ("announcement", "보도자료")),
    TaxonomySeed("COV.FURTHER_ASSURANCES", "COV", "COV", "추가조치", "Further assurances", "거래완수를 위한 추가 문서·행위", 1, ("further actions", "추가 협조")),
    TaxonomySeed("COV.GOVERNANCE", "COV", "COV", "지배구조", "Governance", "이사회·주주총회 운영과 의결권 행사", 1, ("board governance", "지배구조 확약")),
    TaxonomySeed("COV.FINANCING", "COV", "COV", "자금조달·출자", "Financing and contribution", "출자·대출·추가자금 조달 의무", 1, ("funding obligation", "출자의무")),
)

# V4-1R2: definitions, consideration and remedies plus the additional
# Korean/US-style concepts confirmed in the 100-document scope review.
SEED_TAXONOMY += (
    TaxonomySeed("RW.BENEFITS", "RW", "RW", "복리후생·연금", "Benefits and pensions", "임직원 복리후생·퇴직연금·보상제도", 1, ("employee benefit plans", "pension plans", "퇴직연금")),
    TaxonomySeed("RW.LABOR.CLASSIFICATION", "RW.LABOR", "RW", "근로자 분류", "Worker classification", "근로자·독립계약자·도급인의 적정 분류", 2, ("independent contractor classification", "근로자성")),
    TaxonomySeed("RW.LABOR.COLLECTIVE", "RW.LABOR", "RW", "노조·단체협약·쟁의", "Unions and collective bargaining", "노동조합·단체협약·파업과 노동쟁의", 2, ("labor union", "collective bargaining", "단체협약")),
    TaxonomySeed("RW.LABOR.WARN", "RW.LABOR", "RW", "집단해고", "Mass layoff and WARN", "집단해고·사업장 폐쇄·WARN 관련 준수", 2, ("WARN Act", "mass layoff", "집단해고")),
    TaxonomySeed("RW.PRIVACY.CYBERSECURITY", "RW.PRIVACY", "RW", "사이버보안", "Cybersecurity", "정보보안 통제·시스템 취약점·보안사고", 2, ("security incident", "data breach", "침해사고")),
    TaxonomySeed("RW.COMPLIANCE.SANCTIONS", "RW.COMPLIANCE", "RW", "경제제재·수출통제", "Sanctions and export controls", "경제제재·수출통제 법령 준수", 2, ("economic sanctions", "export controls", "경제제재")),
    TaxonomySeed("RW.COMPLIANCE.ANTI_BRIBERY", "RW.COMPLIANCE", "RW", "반부패·뇌물방지", "Anti-bribery", "부패방지·뇌물금지 법령 준수", 2, ("FCPA", "anti-bribery", "부패방지")),
    TaxonomySeed("RW.COMPLIANCE.AML", "RW.COMPLIANCE", "RW", "자금세탁방지", "Anti-money laundering", "자금세탁방지 법령과 통제 준수", 2, ("AML", "money laundering", "자금세탁")),
    TaxonomySeed("RW.CUSTOMERS_SUPPLIERS", "RW", "RW", "주요 고객·공급업체", "Key customers and suppliers", "주요 고객·공급업체 관계와 이탈·변경", 1, ("material customers", "material suppliers", "주요 고객")),
    TaxonomySeed("RW.PRODUCTS", "RW", "RW", "제품책임·리콜·보증", "Products", "제품책임·리콜·제품보증·품질", 1, ("product liability", "product recall", "품질보증")),
    TaxonomySeed("RW.RELATED_PARTY", "RW", "RW", "특수관계인 거래", "Related-party transactions", "계열회사·주주·임직원 등 특수관계인과의 거래", 1, ("affiliate transactions", "특수관계인")),
    TaxonomySeed("RW.BROKERS", "RW", "RW", "브로커·자문수수료", "Brokers and finders", "거래 중개인·투자은행·자문인의 수수료", 1, ("finder's fee", "brokerage fee", "중개수수료")),
    TaxonomySeed("RW.GOVERNMENT_CONTRACTS", "RW", "RW", "정부계약", "Government contracts", "정부기관 계약·입찰·보조금", 1, ("government contracts", "공공입찰")),
    TaxonomySeed("RW.FINANCIAL.BOOKS_RECORDS", "RW.FINANCIAL", "RW", "장부·기록 정확성", "Books and records", "회계장부·기업기록의 정확성과 완전성", 2, ("books and records", "회계장부")),
    TaxonomySeed("RW.FINANCIAL.INTERNAL_CONTROLS", "RW.FINANCIAL", "RW", "내부통제", "Internal controls", "내부회계·공시 통제의 설계와 운영", 2, ("internal controls", "내부회계관리")),
    TaxonomySeed("RW.FINANCIAL.NO_UNDISCLOSED_LIABILITIES", "RW.FINANCIAL", "RW", "미공개 채무 부재", "No undisclosed liabilities", "재무제표 등에 드러나지 않은 채무·우발채무의 부재", 2, ("undisclosed liabilities", "우발채무")),
    TaxonomySeed("CP.ANCILLARY", "CP", "CP", "부속계약 체결", "Ancillary agreements", "거래 관련 부속계약의 체결·인도", 1, ("transaction documents", "부속계약")),
    TaxonomySeed("CP.DEBT_RELEASE", "CP", "CP", "채무상환·담보말소", "Debt payoff and lien release", "채무상환 확인과 담보권 해제·말소", 1, ("payoff letter", "lien release", "담보말소")),
    TaxonomySeed("CP.RESIGNATION", "CP", "CP", "임원 사임", "Officer resignations", "이사·감사·임원의 사임서 인도", 1, ("resignation letter", "임원 사임")),
    TaxonomySeed("CP.LEGAL_OPINION", "CP", "CP", "법률의견서", "Legal opinion", "법률자문인의 종결 법률의견서", 1, ("opinion of counsel", "법률의견서")),
    TaxonomySeed("CP.CLOSING_CERTIFICATE", "CP", "CP", "종결증명서", "Closing certificate", "임원·당사자의 선행조건 충족 증명서", 1, ("officer's certificate", "종결확인서")),
    TaxonomySeed("CP.FINANCIAL_STATEMENTS", "CP", "CP", "재무제표 제공", "Delivery of financial statements", "감사·검토 재무제표의 제공", 1, ("audited financial statements", "재무제표 제공")),
    TaxonomySeed("CP.TAX_RULING", "CP", "CP", "세무확인·예규", "Tax ruling and clearance", "납세증명·세무확인·과세관청 예규", 1, ("tax clearance", "tax ruling", "납세증명")),
    TaxonomySeed("COV.EFFORTS_STANDARD", "COV", "COV", "노력의무 기준", "Efforts standard", "best/reasonable best/commercially reasonable 등 이행노력 강도", 1, ("reasonable best efforts", "commercially reasonable efforts", "최선의 노력")),
    TaxonomySeed("COV.D_AND_O", "COV", "COV", "임원 면책·D&O 보험", "D&O indemnification and tail", "과거 임원의 면책과 D&O tail 보험 유지", 1, ("D&O tail", "임원배상책임보험", "이사 면책")),
    TaxonomySeed("COV.TAX", "COV", "COV", "조세신고·협력", "Tax covenants", "조세신고·조사 대응·선택·협력 의무", 1, ("tax cooperation", "조세신고")),
    TaxonomySeed("COV.TRANSITION", "COV", "COV", "전환·분리 서비스", "Transition services", "종결 후 사업 전환·분리 지원 서비스", 1, ("transition services agreement", "TSA", "전환서비스")),
    TaxonomySeed("COV.INSURANCE", "COV", "COV", "보험 유지", "Maintenance of insurance", "종결 전후 보험의 유지·갱신", 1, ("maintain insurance", "보험 유지")),
    TaxonomySeed("COV.DEBT_RELEASE", "COV", "COV", "채무상환·담보해제 협력", "Debt payoff cooperation", "채무상환과 담보해제 문서 취득·협력", 1, ("payoff cooperation", "담보해제")),
    TaxonomySeed("COV.NOTICE_UPDATE", "COV", "COV", "변경·위반 통지", "Notice of changes or breach", "진술 위반·중요 변경·조건 불충족의 통지", 1, ("notice of breach", "변경 통지")),
    TaxonomySeed("COV.DISCLOSURE_UPDATE", "COV", "COV", "공개목록 갱신", "Disclosure schedule update", "공개목록·Disclosure Schedule의 보충·수정", 1, ("supplement disclosure schedules", "공개목록 갱신")),
    TaxonomySeed("COV.RELEASE", "COV", "COV", "면책·청구포기", "Release", "당사자·계열회사·임직원에 대한 청구 포기와 면책", 1, ("release and discharge", "청구 포기")),
    TaxonomySeed("COV.RWI", "COV", "COV", "진술보장보험", "R&W insurance covenant", "진술보장보험 가입·유지·대위권 포기 관련 의무", 1, ("RWI", "representation and warranty insurance", "진술보장보험")),
    TaxonomySeed("COV.SHA", "COV", "COV", "주주간 권리·의무", "Shareholders' agreement rights", "주주간계약상 지배구조·양도·회수 권리", 1, ("shareholder rights",)),
    TaxonomySeed("COV.SHA.TRANSFER", "COV.SHA", "COV", "주식양도 제한", "Transfer restrictions", "주식·지분의 양도 금지·허용 조건", 2, ("transfer restrictions", "양도제한")),
    TaxonomySeed("COV.SHA.PREEMPTIVE", "COV.SHA", "COV", "신주인수·희석방지", "Pre-emptive rights", "신주 발행 시 우선인수·희석방지 권리", 2, ("preemptive rights", "신주인수권")),
    TaxonomySeed("COV.SHA.DEADLOCK", "COV.SHA", "COV", "교착상태", "Deadlock", "주주·이사회 교착의 발생과 해결절차", 2, ("deadlock", "교착상태")),
    TaxonomySeed("COV.SHA.EXIT", "COV.SHA", "COV", "회수·Exit", "Exit", "IPO·회사매각·tag/drag 등 투자회수 협력", 2, ("IPO", "exit sale", "투자회수")),
    TaxonomySeed("DEF", None, "DEF", "용어의 정의", "Definitions", "계약에서 정의된 용어와 산식·포함·제외 범위", 0, ("definitions", "정의")),
    TaxonomySeed("DEF.MAE", "DEF", "DEF", "중대한 부정적 영향", "Material adverse effect", "MAE/MAC의 포함·제외·재포함 구조", 1, ("MAE", "MAC", "중대한 부정적 영향")),
    TaxonomySeed("DEF.KNOWLEDGE", "DEF", "DEF", "인식", "Knowledge", "실제 인식·합리적 조사·지정인 범위", 1, ("seller knowledge", "actual knowledge", "알고 있는 한")),
    TaxonomySeed("DEF.PERMITTED_LIEN", "DEF", "DEF", "허용된 담보권", "Permitted liens", "허용되는 담보·부담의 범위", 1, ("permitted encumbrances", "허용된 부담")),
    TaxonomySeed("DEF.DEBT", "DEF", "DEF", "차입금·Debt", "Indebtedness", "가격조정상 차입금의 포함·제외 항목", 1, ("net debt", "순차입금")),
    TaxonomySeed("DEF.CASH", "DEF", "DEF", "현금·Cash", "Cash", "가격조정상 현금·현금성자산의 범위", 1, ("cash equivalents", "현금성자산")),
    TaxonomySeed("DEF.WORKING_CAPITAL", "DEF", "DEF", "운전자본", "Working capital", "운전자본 구성계정·목표액·회계원칙", 1, ("net working capital", "운전자본")),
    TaxonomySeed("DEF.TRANSACTION_EXPENSES", "DEF", "DEF", "거래비용", "Transaction expenses", "매도인·대상회사가 부담하는 미지급 거래비용", 1, ("seller expenses", "거래비용")),
    TaxonomySeed("DEF.FUNDAMENTAL_REPS", "DEF", "DEF", "기본 진술보장", "Fundamental representations", "별도 책임제한이 적용되는 기본 진술보장의 범위", 1, ("fundamental warranties", "핵심 진술")),
    TaxonomySeed("DEF.FRAUD", "DEF", "DEF", "사기", "Fraud", "계약상 Fraud의 행위자·고의·의존요건 범위", 1, ("actual fraud", "사기")),
    TaxonomySeed("DEF.LEAKAGE", "DEF", "DEF", "Leakage", "Leakage", "locked-box 이후 금지·허용되는 가치유출", 1, ("permitted leakage", "가치유출")),
    TaxonomySeed("DEF.LOSSES", "DEF", "DEF", "손해", "Losses", "배상 가능한 손실·비용·책임의 포함·제외", 1, ("damages", "손실")),
    TaxonomySeed("DEF.TAXES", "DEF", "DEF", "조세", "Taxes", "세금·부담금·가산세 등의 정의 범위", 1, ("tax", "세금")),
    TaxonomySeed("DEF.ORDINARY_COURSE", "DEF", "DEF", "통상영업", "Ordinary course", "과거 관행·COVID 조치 등을 포함한 통상영업 기준", 1, ("ordinary course of business", "통상적인 영업")),
    TaxonomySeed("DEF.PURCHASE_PRICE", "DEF", "DEF", "매매대금", "Purchase price", "기본대금과 조정·가산·차감 요소", 1, ("consideration", "매매대금")),
    TaxonomySeed("DEF.EARNOUT_METRIC", "DEF", "DEF", "언아웃 성과지표", "Earn-out metric", "언아웃 기간·매출·EBITDA 등 성과산식", 1, ("earnout EBITDA", "성과지표")),
    TaxonomySeed("DEF.BUSINESS_DAY", "DEF", "DEF", "영업일", "Business day", "영업일의 지역·금융기관·휴일 기준", 1, ("business day", "영업일")),
    TaxonomySeed("DEF.AFFILIATE", "DEF", "DEF", "계열회사", "Affiliate", "지배·피지배·공통지배의 범위", 1, ("affiliate", "계열회사")),
    TaxonomySeed("DEF.ENCUMBRANCE", "DEF", "DEF", "부담", "Encumbrance", "담보권·우선권·양도제한 등 부담의 범위", 1, ("lien", "담보권")),
    TaxonomySeed("PAY", None, "PAY", "대금·지급구조", "Consideration and payment", "거래대금의 산정·지급·조정 구조", 0, ("purchase price", "매매대금")),
    TaxonomySeed("PAY.BASE_PRICE", "PAY", "PAY", "기본 매매대금", "Base purchase price", "조정 전 기본·고정 매매대금", 1, ("base consideration", "기본대금")),
    TaxonomySeed("PAY.CLOSING_PAYMENT", "PAY", "PAY", "종결 지급", "Closing payment", "종결 시 현금·계좌이체 지급", 1, ("closing payment", "잔금")),
    TaxonomySeed("PAY.DEPOSIT", "PAY", "PAY", "계약금·중도금", "Deposit and interim payment", "계약금·중도금의 금액·시기·성격", 1, ("down payment", "계약금", "중도금")),
    TaxonomySeed("PAY.COMPLETION_ACCOUNTS", "PAY", "PAY", "종결계정 조정", "Completion accounts", "예상대금·종결재무제표·최종대금 사후조정", 1, ("closing statement", "사후정산")),
    TaxonomySeed("PAY.LOCKED_BOX", "PAY", "PAY", "Locked-box", "Locked box", "기준일 고정가격과 leakage 조정", 1, ("locked-box", "leakage amount")),
    TaxonomySeed("PAY.ESCROW", "PAY", "PAY", "에스크로·유보", "Escrow and holdback", "대금 일부의 예치·유보와 해제", 1, ("holdback", "유보금")),
    TaxonomySeed("PAY.EARNOUT", "PAY", "PAY", "언아웃", "Earn-out", "성과조건부 추가대금", 1, ("contingent consideration", "조건부 대금")),
    TaxonomySeed("PAY.ROLLOVER", "PAY", "PAY", "재투자·롤오버", "Rollover", "매도대금 일부의 인수법인·대상회사 재투자", 1, ("reinvestment", "재투자")),
    TaxonomySeed("PAY.SELLER_NOTE", "PAY", "PAY", "매도인 금융", "Seller financing", "매도인 대여금·약속어음·후순위 지급", 1, ("seller note", "promissory note")),
    TaxonomySeed("PAY.DEFERRED", "PAY", "PAY", "지급유예·분할지급", "Deferred payment", "종결 후 분할·유예 지급", 1, ("deferred consideration", "분할지급")),
    TaxonomySeed("PAY.WITHHOLDING", "PAY", "PAY", "원천징수·공제", "Withholding", "대금 지급 시 세금 원천징수·공제", 1, ("deduction and withholding", "원천징수")),
    TaxonomySeed("PAY.INTEREST", "PAY", "PAY", "이자", "Interest", "유예·연체·정산금에 대한 이자", 1, ("default interest", "지연이자")),
    TaxonomySeed("PAY.ALLOCATION", "PAY", "PAY", "대금배분", "Purchase price allocation", "자산·주식·당사자별 대금 배분", 1, ("allocation schedule", "양도가액 배분")),
    TaxonomySeed("PAY.FX", "PAY", "PAY", "환율·통화환산", "Foreign exchange", "통화·기준환율·환산시점", 1, ("exchange rate", "환율")),
    TaxonomySeed("PAY.PAYING_AGENT", "PAY", "PAY", "지급대리인", "Paying agent", "지급대리인을 통한 대금 배분", 1, ("payment agent", "지급대리인")),
    TaxonomySeed("PAY.DISPUTE_ACCOUNTANT", "PAY", "PAY", "독립회계인 결정", "Independent accountant", "가격조정 이견의 독립회계인 결정절차", 1, ("accounting referee", "독립회계법인")),
    TaxonomySeed("PAY.VAT", "PAY", "PAY", "부가가치세", "VAT", "대금과 별도 또는 포함되는 부가가치세", 1, ("value added tax", "부가세")),
    TaxonomySeed("PAY.SETOFF", "PAY", "PAY", "상계", "Set-off", "대금과 배상채권 등의 상계 가능성", 1, ("setoff", "상계")),
    TaxonomySeed("REM", None, "REM", "위반·구제", "Breach and remedies", "계약위반의 책임·손해배상·해제·강제이행", 0, ("remedies", "손해배상")),
    TaxonomySeed("REM.INDEMNITY", "REM", "REM", "손해배상·면책", "Indemnification", "진술·확약 위반과 특정 손실의 배상", 1, ("indemnification", "배상")),
    TaxonomySeed("REM.CAP", "REM", "REM", "책임한도", "Cap", "손해배상책임의 총액 한도", 1, ("liability cap", "책임한도")),
    TaxonomySeed("REM.BASKET", "REM", "REM", "Basket", "Basket", "총손해 기준과 deductible/tipping 방식", 1, ("deductible basket", "공제액")),
    TaxonomySeed("REM.DE_MINIMIS", "REM", "REM", "개별청구 최소액", "De minimis", "개별 손해배상청구의 최소금액", 1, ("de minimis", "건별 기준")),
    TaxonomySeed("REM.SURVIVAL", "REM", "REM", "존속기간", "Survival", "진술·확약·배상청구권의 존속기간", 1, ("survival period", "존속기간")),
    TaxonomySeed("REM.SPECIAL_INDEMNITY", "REM", "REM", "특별배상", "Special indemnity", "세무·소송 등 특정 사안에 대한 별도 배상", 1, ("specific indemnity", "특별손해배상")),
    TaxonomySeed("REM.CONSEQUENTIAL", "REM", "REM", "간접·결과손해 배제", "Consequential damages exclusion", "간접·특별·결과·징벌적 손해의 제외", 1, ("indirect damages", "특별손해")),
    TaxonomySeed("REM.TAX_BENEFIT", "REM", "REM", "조세혜택 차감", "Tax benefit offset", "손해액에서 조세·경제적 혜택을 차감", 1, ("tax savings", "세금효과")),
    TaxonomySeed("REM.INSURANCE_RECOVERY", "REM", "REM", "보험·제3자 회수 차감", "Insurance recovery", "보험금·제3자 보상액의 손해 차감", 1, ("insurance proceeds", "보험금 공제")),
    TaxonomySeed("REM.SUBROGATION", "REM", "REM", "대위권", "Subrogation", "배상·보험 지급 후 대위와 그 포기", 1, ("subrogation waiver", "대위권")),
    TaxonomySeed("REM.SANDBAGGING", "REM", "REM", "인지효과·Sandbagging", "Sandbagging", "매수인의 사전 인지가 배상청구에 미치는 효과", 1, ("anti-sandbagging", "pro-sandbagging")),
    TaxonomySeed("REM.THIRD_PARTY_CLAIMS", "REM", "REM", "제3자 청구절차", "Third-party claims", "제3자 청구 통지·방어·합의 통제", 1, ("third-party claim", "제3자 청구")),
    TaxonomySeed("REM.DIRECT_CLAIMS", "REM", "REM", "직접청구절차", "Direct claims", "당사자 간 직접 손해청구 절차", 1, ("direct claim", "직접청구")),
    TaxonomySeed("REM.EXCLUSIVE_REMEDY", "REM", "REM", "배타적 구제", "Exclusive remedy", "계약상 배상을 유일·배타적 구제로 정하는 조항", 1, ("sole and exclusive remedy", "유일한 구제")),
    TaxonomySeed("REM.SPECIFIC_PERFORMANCE", "REM", "REM", "특정·강제이행", "Specific performance", "금전배상 외 의무이행·가처분 구제", 1, ("injunctive relief", "강제이행")),
    TaxonomySeed("REM.MITIGATION", "REM", "REM", "손해경감", "Mitigation", "배상권리자의 합리적 손해경감 의무", 1, ("duty to mitigate", "손해경감")),
    TaxonomySeed("REM.NO_DOUBLE_RECOVERY", "REM", "REM", "이중배상 금지", "No double recovery", "동일 사실·손해에 대한 중복 회수 금지", 1, ("duplicative recovery", "중복배상")),
    TaxonomySeed("REM.FRAUD_CARVEOUT", "REM", "REM", "사기 예외", "Fraud carve-out", "사기에 대해 책임제한·배타적 구제를 배제", 1, ("fraud exception", "사기 제외")),
    TaxonomySeed("REM.DEPOSIT_FORFEITURE", "REM", "REM", "계약금 몰취·배액상환", "Deposit forfeiture", "계약금 포기·몰취·배액상환의 허용 또는 배제", 1, ("forfeiture of deposit", "배액상환")),
    TaxonomySeed("REM.LIQUIDATED_DAMAGES", "REM", "REM", "위약벌·손해배상액 예정", "Liquidated damages", "위약벌·위약금·손해배상액의 예정", 1, ("penalty", "위약금")),
    TaxonomySeed("REM.TERMINATION_FEE", "REM", "REM", "해제·종료 수수료", "Termination fee", "break-up/reverse termination fee", 1, ("break fee", "reverse termination fee")),
    TaxonomySeed("REM.TERMINATION", "REM", "REM", "해제·해지권", "Termination rights", "위반·장기종료일 등 해제·해지 사유", 1, ("termination right", "계약해제")),
    TaxonomySeed("REM.CURE", "REM", "REM", "시정기간", "Cure period", "위반 통지 후 해제 전 시정기간", 1, ("cure period", "시정기간")),
    TaxonomySeed("REM.SETOFF", "REM", "REM", "상계권", "Set-off remedy", "손해배상채권과 지급채무의 상계", 1, ("set-off", "상계권")),
)

# Taxonomy version 4: concepts confirmed in an additional non-overlapping
# 200-document review. The new leaves separate SHA operating rights, asset-deal
# perimeter terms and remedy mechanics that were previously grouped under
# broad parents.
SEED_TAXONOMY += (
    TaxonomySeed("RW.ABSENCE_OF_CHANGES", "RW", "RW", "중요 변경·변동 부재", "Absence of changes", "기준일 이후 사업·재무·자산·인사 등 중요 변경의 부재", 1, ("absence of certain changes", "중요 변동 없음")),
    TaxonomySeed("RW.ACCOUNTS_RECEIVABLE", "RW.FINANCIAL", "RW", "매출채권", "Accounts receivable", "매출채권의 실재·회수가능성·충당금·통상영업 발생", 2, ("trade receivables", "매출채권 회수")),
    TaxonomySeed("RW.INVENTORY", "RW.ASSETS", "RW", "재고", "Inventory", "재고의 수량·상태·평가·진부화와 판매가능성", 2, ("inventories", "재고자산")),
    TaxonomySeed("RW.SOLVENCY", "RW.FINANCIAL", "RW", "지급능력·도산 부재", "Solvency", "지급능력·채무초과·지급불능과 도산절차 부재", 2, ("solvent", "insolvency", "지급불능", "채무초과")),
    TaxonomySeed("RW.PRIVACY.COMPLIANCE", "RW.PRIVACY", "RW", "개인정보 처리 법규준수", "Privacy compliance", "개인정보 수집·이용·보관·이전·파기 관련 법규와 고지·동의 준수", 2, ("privacy law compliance", "personal data compliance", "개인정보보호법 준수")),
    TaxonomySeed("COV.RECORDS_RETENTION", "COV", "COV", "장부·기록 보존", "Records retention", "종결 후 장부·기록의 보존과 열람·사본 제공", 1, ("preservation of books and records", "장부 보존")),
    TaxonomySeed("COV.PRIVILEGE", "COV", "COV", "법률상 비밀유지특권", "Attorney-client privilege", "거래 관련 변호사 의뢰인 특권·업무산출물의 귀속과 포기 방지", 1, ("privileged communications", "법률상 비밀유지특권")),
    TaxonomySeed("COV.GUARANTEE_RELEASE", "COV", "COV", "보증 해제·면제", "Guarantee release", "매도인·계열회사의 보증·신용지원 해제와 대체", 1, ("release of guarantees", "보증 해제")),
    TaxonomySeed("COV.POST_CLOSING_COOPERATION", "COV", "COV", "종결 후 협조", "Post-closing cooperation", "종결 후 권리이전·신고·청구·자료제공 등을 위한 협력", 1, ("post-closing cooperation", "종결 후 협력")),
    TaxonomySeed("COV.SHA.TAG_ALONG", "COV.SHA", "COV", "동반매도참여권", "Tag-along right", "주요주주의 매각 시 다른 주주가 동일 조건으로 참여할 권리", 2, ("tag-along", "co-sale right", "공동매도참여권", "동반매각참여권")),
    TaxonomySeed("COV.SHA.DRAG_ALONG", "COV.SHA", "COV", "동반매도요구권", "Drag-along right", "정해진 매각 시 다른 주주에게 동일 조건의 매도를 요구할 권리", 2, ("drag-along", "공동매도요구권", "강제매도권")),
    TaxonomySeed("COV.SHA.ROFR", "COV.SHA", "COV", "우선매수권", "Right of first refusal", "제3자 양도조건에 따라 대상주식을 우선 매수할 권리", 2, ("ROFR", "first refusal right", "우선매수청구권")),
    TaxonomySeed("COV.SHA.ROFO", "COV.SHA", "COV", "우선제안권", "Right of first offer", "제3자 제안 전 또는 매각 전 우선 제안을 받을 권리", 2, ("ROFO", "first offer right", "우선협상제안권")),
    TaxonomySeed("COV.SHA.PUT_OPTION", "COV.SHA", "COV", "풋옵션·주식매수청구권", "Put option", "보유주식의 매수를 상대방에게 청구할 권리와 행사조건", 2, ("put right", "풋옵션", "주식매수청구권")),
    TaxonomySeed("COV.SHA.CALL_OPTION", "COV.SHA", "COV", "콜옵션·주식매도청구권", "Call option", "상대방 보유주식의 매도를 청구할 권리와 행사조건", 2, ("call right", "콜옵션", "주식매도청구권")),
    TaxonomySeed("COV.SHA.RESERVED_MATTERS", "COV.SHA", "COV", "주요사항 사전동의권", "Reserved matters", "정관·자본·차입·투자·인사 등 주요사항에 대한 주주 사전동의권", 2, ("reserved matters", "affirmative vote matters", "사전동의사항")),
    TaxonomySeed("COV.SHA.BOARD_NOMINATION", "COV.SHA", "COV", "이사 지명·선임권", "Board nomination right", "주주별 이사·감사 지명, 선임·해임 및 의결협력 권리", 2, ("board nomination", "director appointment right", "이사추천권")),
    TaxonomySeed("COV.SHA.INFORMATION_RIGHTS", "COV.SHA", "COV", "정보·검사권", "Information and inspection rights", "주주에 대한 재무·경영정보 제공과 장부·시설 검사권", 2, ("information rights", "inspection rights", "경영정보 제공권")),
    TaxonomySeed("COV.SHA.DIVIDEND_POLICY", "COV.SHA", "COV", "배당정책", "Dividend policy", "배당가능이익의 배당비율·시기·우선순위", 2, ("dividend policy", "배당방침")),
    TaxonomySeed("COV.SHA.LOCKUP", "COV.SHA", "COV", "의무보유·처분제한기간", "Lock-up", "일정 기간 주식 양도·처분을 제한하는 의무보유", 2, ("lock-up period", "의무보유기간", "처분제한기간")),
    TaxonomySeed("COV.SHA.FOUNDER_COMMITMENT", "COV.SHA", "COV", "창업자 전념·재직", "Founder commitment", "창업자의 재직·전념·근속 및 퇴사 시 효과", 2, ("founder service commitment", "창업자 전념의무", "창업자 재직의무")),
    TaxonomySeed("CP.ANTITRUST_CLEARANCE", "CP", "CP", "기업결합·경쟁법 승인", "Antitrust clearance", "기업결합신고·HSR 대기기간 종료와 경쟁당국 승인", 1, ("HSR clearance", "Hart-Scott-Rodino approval", "기업결합승인")),
    TaxonomySeed("CP.SHAREHOLDER_APPROVAL", "CP", "CP", "주주승인", "Shareholder approval", "거래승인을 위한 주주총회·주주 서면결의", 1, ("stockholder approval", "주주총회 승인")),
    TaxonomySeed("CP.FIRPTA", "CP", "CP", "FIRPTA 증명", "FIRPTA certificate", "미국 부동산보유법인 해당 여부와 원천징수 예외 증명", 1, ("FIRPTA affidavit", "FIRPTA certificate")),
    TaxonomySeed("CP.GOOD_STANDING", "CP", "CP", "존속·적격 증명서", "Good standing certificate", "설립지 등의 법인 존속·적격 증명서 인도", 1, ("certificate of good standing", "존속증명서")),
    TaxonomySeed("DEF.EBITDA", "DEF", "DEF", "EBITDA", "EBITDA", "EBITDA의 회계기준·가감항목·일회성 항목과 계산기간", 1, ("adjusted EBITDA", "상각전영업이익")),
    TaxonomySeed("DEF.ASSUMED_LIABILITIES", "DEF", "DEF", "승계채무", "Assumed liabilities", "자산양수도에서 양수인이 인수·이행하는 채무의 범위", 1, ("assumed obligations", "인수채무", "승계대상채무")),
    TaxonomySeed("DEF.EXCLUDED_LIABILITIES", "DEF", "DEF", "제외채무", "Excluded liabilities", "매도인이 부담하고 양수인이 인수하지 않는 채무의 범위", 1, ("retained liabilities", "비승계채무", "양수도 제외채무")),
    TaxonomySeed("DEF.PURCHASED_ASSETS", "DEF", "DEF", "양수대상자산", "Purchased assets", "자산양수도에서 이전·인수되는 자산과 권리의 범위", 1, ("acquired assets", "transferred assets", "인수대상자산")),
    TaxonomySeed("DEF.EXCLUDED_ASSETS", "DEF", "DEF", "제외자산", "Excluded assets", "매도인에게 유보되고 양수대상에서 제외되는 자산", 1, ("retained assets", "비양수자산", "양수도 제외자산")),
    TaxonomySeed("REM.MATERIALITY_SCRAPE", "REM", "REM", "중요성 scrape", "Materiality scrape", "위반판정 또는 손해액 산정에서 중요성·MAE 한정을 무시하는 범위", 1, ("materiality scrape", "disregard materiality", "중요성 한정 무시")),
    TaxonomySeed("REM.JOINT_SEVERAL", "REM", "REM", "연대·개별책임", "Joint and several liability", "복수 의무자의 연대책임·개별책임과 배분기준", 1, ("jointly and severally", "several liability", "연대책임")),
    TaxonomySeed("REM.CONTRIBUTION", "REM", "REM", "구상·분담", "Contribution", "공동 책임자 사이의 구상권·분담청구와 포기", 1, ("right of contribution", "구상권")),
    TaxonomySeed("REM.FUNDAMENTAL_CAP", "REM", "REM", "기본 진술 별도 책임한도", "Fundamental representation cap", "기본 진술보장에 적용되는 별도 cap 또는 무제한 책임", 1, ("fundamental representations cap", "기본 진술 책임한도")),
    TaxonomySeed("REM.CLAIM_NOTICE_DEADLINE", "REM", "REM", "청구통지 기한", "Claim notice deadline", "배상청구 통지의 기한·내용과 지연통지의 권리상실·손해 효과", 1, ("claim notice period", "청구통지기간")),
    TaxonomySeed("REM.TAX_GROSS_UP", "REM", "REM", "배상금 조세 gross-up", "Indemnity tax gross-up", "손해배상금에 부과되는 조세·원천징수의 추가 보전", 1, ("tax gross up on indemnity", "배상금 세금보전")),
)

ALIAS_REASSIGNMENTS = {
    "board nomination": "COV.SHA.BOARD_NOMINATION",
    "주주총회 승인": "CP.SHAREHOLDER_APPROVAL",
}

# Taxonomy version 5: systematic RW leaf refinement from the cumulative
# 320-document review. Canonical Korean/English names are inserted as aliases
# by initialize_v4_schema; additional drafting variants remain governed by the
# candidate/alias workflow.
SEED_TAXONOMY += tuple(
    TaxonomySeed(
        leaf.taxonomy_id,
        leaf.parent_id,
        "RW",
        leaf.ko,
        leaf.en,
        leaf.definition,
        2,
    )
    for leaf in RW_REFINEMENT_LEAVES
)

# Taxonomy version 6: leaves first confirmed while reading the V4-2 Korean
# representative and its disclosure schedule.  These are distinct searchable
# propositions rather than drafting variants of the version-5 leaves.
SEED_TAXONOMY += (
    TaxonomySeed(
        "RW.TAX.RESIDENCY",
        "RW.TAX",
        "RW",
        "세법상 거주자 지위",
        "Tax residency",
        "당사자 또는 대상회사의 세법상 거주자·비거주자 지위",
        2,
        ("tax resident", "세무상 거주자", "대한민국 거주자"),
    ),
    TaxonomySeed(
        "RW.TAX.NO_TRANSACTION_TAX",
        "RW.TAX",
        "RW",
        "거래로 인한 추가 조세 부재",
        "No transaction-triggered tax",
        "본건 거래 자체로 대상회사 등에 추가 조세가 부과되지 않는다는 진술",
        2,
        ("no tax arising from the transaction", "거래 관련 추가 조세 없음"),
    ),
    TaxonomySeed(
        "RW.COMPLIANCE.GENERAL",
        "RW.COMPLIANCE",
        "RW",
        "일반 법규준수",
        "General compliance with laws",
        "특정 규제영역에 한정되지 않은 적용 법령·명령의 일반적 준수",
        2,
        ("compliance with applicable laws", "제반 법령 준수", "일반 법률 준수"),
    ),
    TaxonomySeed(
        "RW.COMPLIANCE.NO_VIOLATION_NOTICE",
        "RW.COMPLIANCE",
        "RW",
        "법규위반 통지 부재",
        "No notice of legal violation",
        "법령 위반 또는 위반 우려에 관한 통지·경고를 받지 않았다는 진술",
        2,
        ("no notice of violation", "법령 위반 통지 없음", "위반 우려 통지 없음"),
    ),
    TaxonomySeed(
        "RW.IP.NO_DISPUTE",
        "RW.IP",
        "RW",
        "지식재산 분쟁 부재",
        "No IP dispute",
        "지식재산권의 소유·유효성·사용 또는 침해에 관한 분쟁의 부재",
        2,
        ("no intellectual property dispute", "지식재산권 분쟁 없음"),
    ),
    TaxonomySeed(
        "RW.INSURANCE.NO_COVERAGE_LIMITATION",
        "RW.INSURANCE",
        "RW",
        "보험보장 제한사유 부재",
        "No insurance coverage limitation",
        "보험금 청구권이나 보장범위를 제한·상실시키는 사유의 부재",
        2,
        ("no limitation of insurance coverage", "보험금 청구 제한 없음"),
    ),
    TaxonomySeed(
        "RW.CAPITALIZATION.NO_SHAREHOLDER_AGREEMENT",
        "RW.CAPITALIZATION",
        "RW",
        "주주간계약 등 부재",
        "No shareholders' agreement",
        "대상회사 또는 자회사 지분에 관한 주주간계약·투자계약 등 별도 약정의 부재",
        2,
        ("no shareholders agreement", "주주간계약 없음", "투자계약 없음"),
    ),
    TaxonomySeed(
        "RW.PERMITS.NO_DISPUTE",
        "RW.PERMITS",
        "RW",
        "인허가 분쟁 부재",
        "No permit dispute",
        "정부기관 인허가의 취득·유지·유효성에 관한 소송 또는 분쟁의 부재",
        2,
        ("no permit dispute", "인허가 관련 소송 없음"),
    ),
    TaxonomySeed(
        "RW.REAL_ESTATE.RENT_PAID",
        "RW.REAL_ESTATE",
        "RW",
        "차임 등 지급",
        "Rent and lease payments paid",
        "임대차계약상 차임과 기타 지급금이 기한 내 지급되었다는 진술",
        2,
        ("rent paid", "차임 지급", "임대료 연체 없음"),
    ),
    TaxonomySeed(
        "RW.REAL_ESTATE.DEPOSIT_RECOVERABLE",
        "RW.REAL_ESTATE",
        "RW",
        "임대차보증금 회수가능성",
        "Lease deposit recoverability",
        "임대차보증금의 반환청구권을 제한하거나 회수를 저해할 사유의 부재",
        2,
        ("lease deposit recoverability", "임대차보증금 반환", "보증금 회수"),
    ),
    TaxonomySeed(
        "RW.ACCOUNTS_RECEIVABLE.VALIDITY",
        "RW.ACCOUNTS_RECEIVABLE",
        "RW",
        "매출채권 발생·소유의 유효성",
        "Validity of accounts receivable",
        "매출채권이 실제 거래에서 적법하게 발생하고 대상회사가 유효하게 소유한다는 진술",
        3,
        ("valid receivables", "매출채권 적법 발생", "매출채권 소유권"),
    ),
    TaxonomySeed(
        "RW.ACCOUNTS_RECEIVABLE.COLLECTIBILITY",
        "RW.ACCOUNTS_RECEIVABLE",
        "RW",
        "매출채권 회수가능성",
        "Collectibility of accounts receivable",
        "매출채권이 통상적으로 회수 가능하다는 진술",
        3,
        ("collectible receivables", "매출채권 회수 가능"),
    ),
    TaxonomySeed(
        "RW.ACCOUNTS_RECEIVABLE.ALLOWANCE",
        "RW.ACCOUNTS_RECEIVABLE",
        "RW",
        "대손충당금 적정성",
        "Adequacy of bad-debt allowance",
        "매출채권 관련 대손충당금이 과거 관행 등에 따라 적정하게 설정되었다는 진술",
        3,
        ("bad debt allowance", "대손충당금 적정"),
    ),
    TaxonomySeed(
        "RW.ACCOUNTS_RECEIVABLE.NO_ENCUMBRANCE",
        "RW.ACCOUNTS_RECEIVABLE",
        "RW",
        "매출채권 제한부담 부재",
        "No receivables encumbrance",
        "매출채권에 상계·공제·금액조정 또는 제한부담이 없다는 진술",
        3,
        ("unencumbered receivables", "매출채권 담보 없음", "매출채권 상계 없음"),
    ),
    TaxonomySeed(
        "RW.INVENTORY.MARKETABILITY",
        "RW.INVENTORY",
        "RW",
        "재고 판매가능성",
        "Inventory marketability",
        "재고가 정상 영업과정에서 판매 가능한 상태라는 진술",
        3,
        ("saleable inventory", "재고 판매 가능"),
    ),
    TaxonomySeed(
        "RW.INVENTORY.ADEQUACY",
        "RW.INVENTORY",
        "RW",
        "재고 수량·구성 적정성",
        "Inventory quantity and mix",
        "재고의 수량과 구성이 사업수요에 비추어 적정하다는 진술",
        3,
        ("adequate inventory", "재고 수량 적정"),
    ),
    TaxonomySeed(
        "RW.INVENTORY.VALUATION",
        "RW.INVENTORY",
        "RW",
        "재고 평가 적정성",
        "Inventory valuation",
        "재고가 적용 회계기준과 일관된 방법으로 적정하게 평가되었다는 진술",
        3,
        ("inventory valuation", "재고 평가", "재고자산 장부가액"),
    ),
    TaxonomySeed(
        "RW.TAX.BOOKS_RECORDS",
        "RW.TAX",
        "RW",
        "세무장부·증빙 유지",
        "Tax books and records",
        "조세 관련 장부·기록·세금계산서가 적법하고 정확하게 작성·보관되었다는 진술",
        2,
        ("tax books and records", "세무장부", "세금계산서"),
    ),
    TaxonomySeed(
        "RW.CORPORATE_GOVERNANCE",
        "RW",
        "RW",
        "회사기관·지배구조 절차",
        "Corporate governance formalities",
        "주주총회·이사회·등기 등 회사기관의 결의와 운영절차 준수",
        1,
        ("corporate formalities", "회사기관 운영", "주주총회 절차"),
    ),
    TaxonomySeed(
        "RW.CORPORATE_GOVERNANCE.APPROVALS",
        "RW.CORPORATE_GOVERNANCE",
        "RW",
        "주주총회·이사회 승인",
        "Shareholder and board approvals",
        "재무제표·임원보수 등 법정 사항에 필요한 주주총회 또는 이사회 승인의 이행",
        2,
        ("shareholder meeting approvals", "주주총회 승인", "이사회 승인"),
    ),
    TaxonomySeed(
        "RW.LABOR.SHARED_PERSONNEL",
        "RW.LABOR",
        "RW",
        "겸직·공동인력",
        "Shared personnel and dual employment",
        "대상회사 임직원의 계열회사 겸직·업무수행 또는 공동인력 운용",
        2,
        ("shared employees", "dual employment", "계열회사 겸직", "공동인력"),
    ),
    TaxonomySeed(
        "RW.DISCLOSURE",
        "RW",
        "RW",
        "제공정보의 진실성",
        "Disclosure and information accuracy",
        "계약 및 제공자료의 허위·부정확 기재와 중요사실 누락 여부",
        1,
        ("full disclosure representation", "제공자료 진실성"),
    ),
    TaxonomySeed(
        "RW.DISCLOSURE.ACCURACY",
        "RW.DISCLOSURE",
        "RW",
        "허위·부정확 기재 부재",
        "Accuracy of disclosed information",
        "계약상 진술과 제공자료에 허위 또는 중요하게 부정확한 기재가 없다는 진술",
        2,
        ("no false statement", "허위 기재 없음", "부정확한 기재 없음"),
    ),
    TaxonomySeed(
        "RW.DISCLOSURE.NO_OMISSION",
        "RW.DISCLOSURE",
        "RW",
        "중요사실 누락 부재",
        "No material omission",
        "진술이나 제공자료에서 오인을 일으키는 중요사실이 누락되지 않았다는 진술",
        2,
        ("no material omission", "중요 사실 누락 없음", "오인 유발 내용 없음"),
    ),
)

# Taxonomy version 7: atomic concepts confirmed in the deterministic review of
# 652 previously unreviewed contracts (half of the 1,303-document remainder).
SEED_TAXONOMY += (
    TaxonomySeed("RW.REAL_ESTATE.ZONING", "RW.REAL_ESTATE", "RW", "용도지역·건축법 준수", "Zoning and building compliance", "부동산의 현재 용도·점유·건축이 용도지역, 도시계획 및 건축 관련 법령에 부합한다는 진술", 2, ("zoning compliance", "building code compliance", "용도지역 준수", "건축법 준수")),
    TaxonomySeed("RW.REAL_ESTATE.NO_CONDEMNATION", "RW.REAL_ESTATE", "RW", "수용·철거 절차 부재", "No condemnation", "부동산에 관한 수용·협의취득·철거 또는 유사 절차와 통지의 부재", 2, ("no condemnation", "eminent domain", "토지수용 없음", "수용절차 부재")),
    TaxonomySeed("RW.LABOR.IMMIGRATION", "RW.LABOR", "RW", "외국인근로자·이민법 준수", "Immigration and work authorization compliance", "외국인근로자의 체류·취업자격, I-9 등 근로허가와 이민법 준수", 2, ("immigration compliance", "work authorization", "I-9 compliance", "외국인근로자 적법 고용", "체류자격")),
    TaxonomySeed("RW.FINANCIAL.DEBT_COMPLIANCE", "RW.FINANCIAL", "RW", "금융약정 준수", "Debt covenant compliance", "대출·신용공여의 재무약정과 기타 의무 준수 및 기한이익상실 부재", 2, ("financial covenant compliance", "debt covenant compliance", "재무약정 준수")),
    TaxonomySeed("RW.FINANCIAL.NO_GOVERNMENT_GRANT_CLAWBACK", "RW.FINANCIAL", "RW", "보조금 환수의무 부재", "No government grant clawback", "정부 보조금·지원금의 조건 준수와 반환·환수의무 부재", 2, ("no grant clawback", "subsidy repayment", "보조금 환수 없음", "지원금 반환의무 없음")),
    TaxonomySeed("RW.COMPLIANCE.COMPETITION", "RW.COMPLIANCE", "RW", "경쟁법 준수", "Competition law compliance", "독점규제·공정거래·경쟁법상 담합, 불공정거래 등 규제의 준수", 2, ("antitrust compliance", "competition law compliance", "공정거래법 준수")),
    TaxonomySeed("RW.COMPLIANCE.CUSTOMS", "RW.COMPLIANCE", "RW", "관세·수출입 준수", "Customs and trade compliance", "관세, 통관, 수출입 및 무역통제 관련 법령 준수", 2, ("customs compliance", "import export compliance", "관세법 준수", "수출입 법규준수")),
    TaxonomySeed("RW.GOVERNMENT_CONTRACTS.COMPLIANCE", "RW.GOVERNMENT_CONTRACTS", "RW", "정부계약 준수", "Government contract compliance", "정부·공공기관 원도급·하도급·입찰계약의 조건과 관련 법령 준수", 2, ("government contract compliance", "public procurement compliance", "정부계약 준수", "공공조달 준수")),
    TaxonomySeed("RW.IP.DOMAIN_NAMES", "RW.IP", "RW", "도메인명·온라인 계정", "Domain names and online accounts", "사업에 사용하는 인터넷 도메인명과 소셜미디어 등 온라인 계정의 소유·사용 권리", 2, ("domain names", "internet domains", "social media accounts", "인터넷 도메인")),
    TaxonomySeed("CP.ESCROW_AGREEMENT", "CP", "CP", "에스크로계약 체결·교부", "Escrow agreement delivery", "종결 또는 지급의 조건으로 에스크로계약을 체결하거나 서명본을 교부하는 사항", 1, ("escrow agreement delivery", "executed escrow agreement", "에스크로계약 체결", "에스크로계약 교부")),
    TaxonomySeed("CP.KEY_EMPLOYEE", "CP", "CP", "핵심인력 재직·계약", "Key employee condition", "핵심인력의 재직, 근로계약·비밀유지계약 체결 또는 이탈 부재를 요구하는 조건", 1, ("key employee condition", "key employees remain", "핵심인력 재직", "핵심인력 근로계약")),
    TaxonomySeed("CP.DISSENTERS_RIGHTS", "CP", "CP", "주식매수청구권 제한", "Dissenters' rights condition", "반대주주의 주식매수청구권·appraisal rights 행사 규모가 기준을 넘지 않을 것을 요구하는 조건", 1, ("dissenters rights condition", "appraisal rights threshold", "반대주주 주식매수청구권")),
    TaxonomySeed("COV.NON_DISPARAGEMENT", "COV", "COV", "비방금지", "Non-disparagement", "당사자·대상회사·임직원에 관한 비방 또는 평판 훼손 행위 금지", 1, ("non-disparagement", "not disparage", "비방 금지")),
    TaxonomySeed("COV.STANDSTILL", "COV", "COV", "스탠드스틸", "Standstill", "일정 기간 상대방 동의 없이 주식 추가취득, 공개매수, 지배권 행사 등을 하지 않을 의무", 1, ("standstill", "stand-still", "추가 주식취득 금지")),
    TaxonomySeed("COV.PRIVACY_REMEDIATION", "COV", "COV", "개인정보 위반 시정", "Privacy compliance remediation", "개인정보 동의·파기·처리위탁계약·보호조치 등 위반사항의 시정 의무", 1, ("privacy remediation", "data protection remediation", "개인정보 위반 시정", "개인정보 처리위탁계약 체결")),
    TaxonomySeed("COV.TAX.REFUND", "COV.TAX", "COV", "조세환급 귀속·협력", "Tax refund allocation and cooperation", "거래 전후 조세환급의 귀속, 청구·수령·지급 및 관련 협력 의무", 2, ("tax refund allocation", "tax refund cooperation", "조세환급 귀속", "세금환급 협력")),
    TaxonomySeed("COV.SHA.REGISTRATION_RIGHTS", "COV.SHA", "COV", "등록청구권", "Registration rights", "증권 등록을 요구하거나 piggyback 방식으로 등록에 참여할 권리", 2, ("registration rights", "demand registration", "piggyback registration", "등록청구권")),
    TaxonomySeed("COV.SHA.VOTING_PROXY", "COV.SHA", "COV", "의결권 위임·의결권계약", "Voting proxy and voting agreement", "주식 의결권의 위임, 대리행사 또는 특정 방식의 의결권 행사 약정", 2, ("voting proxy", "voting agreement", "irrevocable proxy", "의결권 위임", "의결권계약")),
    TaxonomySeed("COV.SHA.QUORUM", "COV.SHA", "COV", "이사회·주주총회 정족수", "Board and shareholder quorum", "이사회·위원회·주주총회의 성립에 필요한 출석 정족수와 재소집 규칙", 2, ("quorum", "board quorum", "정족수", "이사회 성립요건")),
    TaxonomySeed("COV.SHA.CASTING_VOTE", "COV.SHA", "COV", "의장 결정권", "Chair casting vote", "가부동수 등 교착 시 의장 또는 특정 지명 이사에게 부여되는 결정표", 2, ("casting vote", "deciding vote", "캐스팅보트", "의장 결정권")),
    TaxonomySeed("DEF.ACCOUNTING_PRINCIPLES", "DEF", "DEF", "회계원칙", "Accounting principles", "가격조정·재무계산에 적용되는 회계정책, 관행, 방법론 및 우선순위", 1, ("Accounting Principles", "회계원칙")),
    TaxonomySeed("DEF.DISCLOSURE_SCHEDULE", "DEF", "DEF", "공개목록", "Disclosure schedule", "진술보장의 예외·공개사항을 기재한 disclosure schedule의 정의와 갱신 범위", 1, ("Disclosure Schedule", "Disclosure Schedules", "공개목록")),
    TaxonomySeed("DEF.DATA_ROOM", "DEF", "DEF", "데이터룸", "Data room", "실사 과정에서 제공된 전자 데이터룸의 주소·기준시점·포함 자료 범위", 1, ("Data Room", "Virtual Data Room", "데이터룸", "가상 데이터룸")),
    TaxonomySeed("DEF.DEBT.CLOSING_NET_DEBT", "DEF.DEBT", "DEF", "종결 순차입금", "Closing net debt", "종결시점 차입금에서 현금 등 공제항목을 반영한 순차입금", 2, ("Closing Net Debt", "종결 순차입금")),
    TaxonomySeed("DEF.WORKING_CAPITAL.TARGET", "DEF.WORKING_CAPITAL", "DEF", "목표운전자본", "Target working capital", "종결 운전자본 조정의 비교기준이 되는 목표·기준 운전자본", 2, ("Target Working Capital", "목표운전자본", "기준운전자본")),
    TaxonomySeed("PAY.MILESTONE", "PAY", "PAY", "마일스톤 지급", "Milestone payment", "사업·개발·인허가 등 특정 마일스톤 달성에 따라 발생하는 추가 대금", 1, ("milestone payment", "development milestone", "마일스톤 지급", "마일스톤 대금")),
    TaxonomySeed("PAY.EQUITY_CONSIDERATION", "PAY", "PAY", "주식·지분 대가", "Equity consideration", "현금 대신 또는 현금과 함께 매수인·관계회사 주식으로 지급하는 거래대가", 1, ("share consideration", "stock consideration", "consideration shares", "주식 대가")),
    TaxonomySeed("PAY.TRUE_UP_DEADLINE", "PAY.COMPLETION_ACCOUNTS", "PAY", "정산금 지급기한", "True-up payment deadline", "종결계정·가격조정 확정 후 정산금의 지급기한과 방법", 2, ("true-up payment deadline", "adjustment payment deadline", "정산금 지급기한")),
    TaxonomySeed("PAY.EARNOUT.GUARANTEE", "PAY.EARNOUT", "PAY", "언아웃 지급보증", "Earn-out payment guarantee", "모회사·펀드 등 제3자의 언아웃 지급보증 또는 연대지급의무", 2, ("earnout guarantee", "guarantee of earnout payment", "언아웃 지급보증")),
    TaxonomySeed("REM.BASKET.DEDUCTIBLE", "REM.BASKET", "REM", "공제형 basket", "Deductible basket", "누적손해가 기준액을 넘은 경우 그 초과분만 배상하는 구조", 2, ("deductible basket", "excess over the basket", "초과분만 배상")),
    TaxonomySeed("REM.BASKET.TIPPING", "REM.BASKET", "REM", "소급형 basket", "Tipping basket", "누적손해가 기준액을 넘으면 기준액 이하를 포함한 전액을 배상하는 구조", 2, ("tipping basket", "first dollar basket", "손해 전액 배상")),
    TaxonomySeed("REM.CONSEQUENTIAL.PUNITIVE", "REM.CONSEQUENTIAL", "REM", "징벌적·제재적 손해 배제", "Punitive and exemplary damages exclusion", "징벌적·제재적·exemplary damages에 대한 책임 배제", 2, ("punitive damages exclusion", "exemplary damages exclusion", "징벌적 손해 배제", "제재적 손해")),
    TaxonomySeed("REM.EXCLUSIVE_REMEDY.RESCISSION_WAIVER", "REM.EXCLUSIVE_REMEDY", "REM", "취소·해제권 포기", "Rescission waiver", "위반을 이유로 한 계약취소·해제·대금감액 등 구제수단의 포기", 2, ("rescission waiver", "waiver of rescission", "취소권 포기", "해제권 포기")),
    TaxonomySeed("REM.EXCLUSIVE_REMEDY.ESCROW_SOLE_RECOURSE", "REM.EXCLUSIVE_REMEDY", "REM", "에스크로 한정구제", "Escrow as sole recourse", "특정 손해·정산부족액의 유일한 회수재원을 에스크로로 제한하는 조항", 2, ("escrow sole recourse", "escrow exclusive remedy", "에스크로 한정구제")),
    TaxonomySeed("REM.DIRECT_CLAIMS.CLAIMS_REPRESENTATIVE", "REM.DIRECT_CLAIMS", "REM", "청구대표자 절차", "Claims representative procedure", "복수 당사자의 손해배상 통지·청구·합의 권한을 대표자에게 집중하는 절차", 2, ("claims representative", "seller representative claims", "매도인대표 청구", "청구대표자")),
    TaxonomySeed("REM.INDEMNITY.RECOVERY_PRIORITY", "REM.INDEMNITY", "REM", "배상재원 청구순서", "Recovery waterfall", "에스크로·보험·직접청구 등 배상재원별 선후순위와 청구 순서", 2, ("recovery waterfall", "order of recovery", "first seek recovery from escrow", "배상 청구순서")),
)

# Taxonomy version 8: atomic concepts confirmed in the complementary review
# of the other 651 previously unreviewed principal agreements. The review was
# executed as fixed, non-overlapping 300- and 351-document batches.
SEED_TAXONOMY += (
    TaxonomySeed("RW.LABOR.NO_STRIKE", "RW.LABOR", "RW", "파업·쟁의행위 없음", "No strike or work stoppage", "파업, 태업, 직장폐쇄, 작업중단 또는 유사한 쟁의행위가 진행 중이거나 예고·위협되지 않았다는 진술", 2, ("no strike", "no work stoppage", "no lockout", "파업 없음", "쟁의행위 없음")),
    TaxonomySeed("RW.LABOR.NO_UNION_ORGANIZING", "RW.LABOR", "RW", "노동조합 조직화 없음", "No union organizing activity", "노동조합 결성·조직화·대표권 취득을 위한 활동이나 청원이 없다는 진술", 2, ("no union organizing", "no organizing campaign", "노조 조직화 없음", "노동조합 설립 움직임 없음")),
    TaxonomySeed("RW.FINANCIAL.NO_OFF_BALANCE_SHEET", "RW.FINANCIAL", "RW", "부외부채 없음", "No off-balance-sheet liabilities", "재무제표와 장부에 반영되지 않은 부외부채 또는 부외약정이 없다는 진술", 2, ("no off-balance-sheet liabilities", "off balance sheet arrangement", "부외부채 없음", "장부외 채무 없음")),
    TaxonomySeed("RW.IT", "RW", "RW", "IT 시스템", "Information technology systems", "사업 운영에 사용되는 정보기술 시스템, 인프라, 복구 및 연속성에 관한 진술보장", 1, ("IT systems", "information systems", "정보시스템", "전산시스템")),
    TaxonomySeed("RW.IT.SYSTEMS_SUFFICIENCY", "RW.IT", "RW", "IT 시스템 충분성", "IT systems sufficiency", "IT 시스템이 현재 사업을 독립적으로 운영하기에 충분하고 요구되는 방식으로 작동한다는 진술", 2, ("IT systems sufficiency", "adequate IT systems", "정보시스템 충분성", "전산시스템 적정성")),
    TaxonomySeed("RW.IT.DISASTER_RECOVERY", "RW.IT", "RW", "재해복구·업무연속성", "IT disaster recovery and business continuity", "IT 장애·재해 발생 시 데이터와 사업을 복구·계속할 수 있는 백업, 재해복구 또는 업무연속성 체계를 갖추었다는 진술", 2, ("disaster recovery plan", "business continuity plan", "data backup and recovery", "재해복구계획", "업무연속성계획")),
    TaxonomySeed("RW.ENVIRONMENT.NO_UNDERGROUND_STORAGE_TANKS", "RW.ENVIRONMENT", "RW", "지하저장탱크 없음", "No underground storage tanks", "소유·임차 부동산의 지상 또는 지하에 환경위험을 수반하는 지하저장탱크가 존재하지 않는다는 진술", 2, ("no underground storage tanks", "underground storage tank", "지하저장탱크 없음")),
    TaxonomySeed("RW.TAX.NO_PERMANENT_ESTABLISHMENT", "RW.TAX", "RW", "해외 고정사업장 없음", "No foreign permanent establishment", "설립지 외 관할에서 고정사업장, 과세상 존재 또는 사업장으로 인해 납세의무를 부담하지 않는다는 진술", 2, ("no permanent establishment", "no taxable presence", "고정사업장 없음", "과세상 존재 없음")),
    TaxonomySeed("CP.DEBT_RELEASE.PAYOFF_LETTER", "CP.DEBT_RELEASE", "CP", "채무상환 확인서", "Payoff letter", "종결 시 상환할 채무·거래비용의 금액과 송금정보 및 상환 후 소멸을 확인하는 payoff letter의 교부 조건", 2, ("payoff letter", "pay-off letter", "채무상환 확인서", "변제 확인서")),
    TaxonomySeed("CP.DEBT_RELEASE.LIEN_RELEASE", "CP.DEBT_RELEASE", "CP", "담보권 해지서류", "Lien release documents", "종결 시 대상자산의 담보권·질권·근저당 기타 제한부담을 해지·말소하는 동의서와 서류의 교부 조건", 2, ("lien release", "security interest release", "담보권 해지서류", "담보말소계약서")),
    TaxonomySeed("CP.ANCILLARY.RESTRICTIVE_COVENANT_AGREEMENT", "CP.ANCILLARY", "CP", "경업금지 등 제한약정 체결", "Restrictive covenant agreement execution", "경업금지, 유인금지 또는 퇴사제한 약정의 서명·교부를 종결조건이나 종결서류로 요구하는 조항", 2, ("restrictive covenant agreement", "noncompetition agreement delivery", "경업금지 약정 체결", "퇴사제한 약정 교부")),
    TaxonomySeed("CP.GOVERNMENT_APPROVAL.FOREIGN_INVESTMENT", "CP.GOVERNMENT_APPROVAL", "CP", "외국인투자 승인·신고", "Foreign-investment clearance", "CFIUS 또는 외국인투자 관련 법령에 따른 승인, 신고수리 또는 심사종결을 거래종결 조건으로 요구하는 조항", 2, ("foreign investment clearance", "CFIUS clearance", "외국인투자 승인", "외국인투자신고 수리")),
    TaxonomySeed("COV.EMPLOYEE_BENEFITS_CONTINUATION", "COV.PERSONNEL", "COV", "종업원 보상·복리후생 유지", "Employee compensation and benefits continuation", "종결 후 일정 기간 승계·계속근로자의 고용, 보수 또는 복리후생을 유지하거나 불리하지 않게 제공하는 확약", 2, ("employee benefits continuation", "no less favorable benefits", "복리후생 유지", "고용조건 유지")),
    TaxonomySeed("COV.TAX.CONSISTENT_REPORTING", "COV.TAX", "COV", "조세신고상 일관된 처리", "Consistent tax reporting", "손해배상금이나 거래대금을 조세 목적상 특정 방식으로 취급하고 각 당사자가 그 처리와 일치하는 세금신고를 하도록 하는 확약", 2, ("consistent tax reporting", "file tax returns consistently", "일관된 세금신고", "조세처리 일치")),
    TaxonomySeed("COV.TAX.AUDIT_CONTROL", "COV.TAX", "COV", "세무조사 대응 통제", "Tax audit control", "거래 전 기간 관련 세무조사의 통지, 방어·주도권, 비용, 협의 및 협조를 배분하는 확약", 2, ("tax audit control", "control of tax contest", "세무조사 대응", "세무조사 방어권")),
    TaxonomySeed("COV.TAX.TRANSFER_TAX", "COV.TAX", "COV", "거래세 부담·신고", "Transfer-tax allocation and filing", "거래로 발생하는 양도세, 취득세, 등록세, 인지세 기타 이전세의 부담·납부·신고 주체를 정하는 확약", 2, ("transfer tax allocation", "transfer tax filing", "거래세 부담", "이전세 신고")),
    TaxonomySeed("COV.REGULATORY.DIVESTITURE", "COV.REGULATORY", "COV", "경쟁당국 시정조치·자산매각", "Antitrust divestiture commitment", "기업결합 승인을 얻기 위해 자산·사업을 매각하거나 구조적 시정조치를 수용할 의무 또는 그 한계를 정하는 확약", 2, ("antitrust divestiture", "structural remedy", "기업결합 시정조치", "자산매각 의무")),
    TaxonomySeed("COV.REGULATORY.HOLD_SEPARATE", "COV.REGULATORY", "COV", "경쟁법상 분리운영", "Antitrust hold-separate commitment", "경쟁당국의 요구에 따라 특정 자산·사업을 분리 보유·운영하는 조치를 수용하거나 그 범위를 제한하는 확약", 2, ("hold separate", "hold-separate commitment", "분리운영 의무", "분리보유 조치")),
    TaxonomySeed("COV.RWI.PROCUREMENT", "COV.RWI", "COV", "진술보장보험 가입·증권 교부", "RWI procurement and policy delivery", "매수인이 진술보장보험을 가입하고 증권 또는 바인더를 체결·교부하도록 하는 확약", 2, ("RWI procurement", "RWI binder", "representation warranty insurance policy delivery", "진술보장보험 가입", "보험증권 교부")),
    TaxonomySeed("COV.RWI.MAINTENANCE", "COV.RWI", "COV", "진술보장보험 유지", "RWI policy maintenance", "진술보장보험의 조건을 충족하고 보험증권을 유효하게 유지하며 불리하게 변경·해지하지 않도록 하는 확약", 2, ("RWI policy maintenance", "maintain warranty insurance", "진술보장보험 유지", "보험증권 변경 제한")),
    TaxonomySeed("COV.RWI.SUBROGATION_WAIVER", "COV.RWI", "COV", "진술보장보험 대위권 제한", "RWI subrogation waiver", "보험자가 매도인에게 구상권·대위권을 행사하지 못하도록 보험조건을 정하고 이를 불리하게 변경하지 않는 확약", 2, ("RWI subrogation waiver", "waiver of subrogation", "진술보장보험 대위권 제한", "보험자 구상권 제한")),
    TaxonomySeed("COV.SHA.ANTI_DILUTION", "COV.SHA", "COV", "희석방지권", "Anti-dilution protection", "기존 전환가격보다 낮은 가격의 신주·주식연계증권 발행 시 전환가격 또는 지분을 조정하는 권리", 2, ("anti-dilution", "weighted average anti-dilution", "희석방지", "전환가액 조정")),
    TaxonomySeed("COV.SHA.BUSINESS_PLAN_BUDGET", "COV.SHA", "COV", "사업계획·예산 승인", "Business plan and budget approval", "연간 사업계획과 예산의 작성, 이사회·주주 승인 및 변경 절차를 정하는 지배구조 조항", 2, ("business plan approval", "annual budget approval", "사업계획 승인", "예산 승인")),
    TaxonomySeed("COV.SHA.AFFILIATE_TRANSFER", "COV.SHA.TRANSFER", "COV", "계열회사 허용양도", "Permitted affiliate transfer", "계열회사 등 허용된 양수인에게 동의나 우선권 절차 없이 주식을 양도할 수 있는 예외와 승계조건", 3, ("permitted affiliate transfer", "transfer to affiliate", "계열회사 허용양도", "관계회사 양도 예외")),
    TaxonomySeed("DEF.WORKING_CAPITAL.NET", "DEF.WORKING_CAPITAL", "DEF", "순운전자본", "Net working capital", "매출채권, 재고, 매입채무 및 기타 유동항목을 포함·제외하여 가격조정에 쓰는 순운전자본의 정의", 2, ("Net Working Capital", "NWC", "순운전자본")),
    TaxonomySeed("DEF.LEAKAGE.PERMITTED", "DEF.LEAKAGE", "DEF", "허용누출", "Permitted leakage", "locked-box 기준일 이후에도 대금조정 또는 누출금지 위반으로 보지 않기로 한 허용 지급·거래의 정의", 2, ("Permitted Leakage", "허용누출", "허용 Leakage")),
    TaxonomySeed("PAY.HOLDBACK", "PAY", "PAY", "대금 유보", "Purchase-price holdback", "사후 가격조정이나 특정 위험을 담보하기 위해 종결대금의 일부를 일정 기간 지급하지 않고 유보하는 구조", 1, ("purchase price holdback", "holdback amount", "대금 유보", "매매대금 보류")),
    TaxonomySeed("PAY.EARNOUT.DISPUTE", "PAY.EARNOUT", "PAY", "언아웃 산정 분쟁절차", "Earn-out dispute procedure", "언아웃 명세서에 대한 이의제기 기간·내용과 독립 회계사 등 분쟁해결 절차", 2, ("earnout dispute", "earn-out objection", "언아웃 이의제기", "언아웃 분쟁")),
    TaxonomySeed("PAY.ESCROW.RELEASE", "PAY.ESCROW", "PAY", "에스크로 해제·분배", "Escrow release mechanics", "에스크로 기간 만료 또는 청구 확정 시 예치금을 매도인·매수인에게 해제·분배·지급하는 구조", 2, ("escrow release", "escrow distribution", "에스크로 해제", "에스크로 인출")),
    TaxonomySeed("REM.CONSEQUENTIAL.LOST_PROFITS", "REM.CONSEQUENTIAL", "REM", "일실이익 배제", "Lost-profits exclusion", "손해 범위에서 일실이익 또는 수익 상실을 배제하는 제한", 2, ("lost profits exclusion", "loss of profits exclusion", "일실이익 배제", "상실이익 배제")),
    TaxonomySeed("REM.CONSEQUENTIAL.DIMINUTION_IN_VALUE", "REM.CONSEQUENTIAL", "REM", "가치감소 손해 배제", "Diminution-in-value exclusion", "대상회사·주식·자산의 가치감소를 기준으로 산정한 손해를 배제하는 제한", 2, ("diminution in value exclusion", "diminished value damages", "가치감소 손해 배제")),
    TaxonomySeed("REM.CONSEQUENTIAL.MULTIPLE_BASED", "REM.CONSEQUENTIAL", "REM", "배수기준 손해 배제", "Multiple-based damages exclusion", "이익·매출·성과지표의 valuation multiple을 적용해 산정한 손해를 배제하는 제한", 2, ("multiple-based damages exclusion", "valuation multiple damages", "배수기준 손해 배제", "멀티플 손해 배제")),
    TaxonomySeed("REM.THIRD_PARTY_CLAIMS.DEFENSE_CONTROL", "REM.THIRD_PARTY_CLAIMS", "REM", "제3자청구 방어권", "Control of third-party claim defense", "배상의무자와 배상권리자 중 누가 제3자청구의 방어를 인수·주도할 수 있는지와 그 예외를 정하는 절차", 2, ("third party claim defense control", "assume control of defense", "제3자청구 방어권", "방어 주도권")),
    TaxonomySeed("REM.THIRD_PARTY_CLAIMS.SETTLEMENT_CONSENT", "REM.THIRD_PARTY_CLAIMS", "REM", "제3자청구 합의 동의", "Third-party claim settlement consent", "제3자청구의 화해·조정·판결 승낙에 필요한 상대방 동의와 완전면책 등 합의조건", 2, ("third party claim settlement consent", "consent to settlement", "제3자청구 합의 동의", "화해 승인")),
    TaxonomySeed("REM.THIRD_PARTY_CLAIMS.COOPERATION", "REM.THIRD_PARTY_CLAIMS", "REM", "제3자청구 방어 협조", "Third-party claim defense cooperation", "제3자청구 방어를 위한 문서보존·열람·증언·정보제공 기타 합리적 협조 의무", 2, ("third party claim cooperation", "cooperate in defense", "제3자청구 방어 협조", "방어 협력")),
    TaxonomySeed("REM.DIRECT_CLAIMS.NOTICE_CONTENT", "REM.DIRECT_CLAIMS", "REM", "직접청구 통지 기재사항", "Direct-claim notice contents", "직접 손해배상청구 통지에 위반 사실, 법적·사실적 근거, 손해액 또는 산식 등을 기재하도록 하는 절차", 2, ("claim notice contents", "reasonable detail of claim", "직접청구 통지 내용", "손해배상청구 통지 기재사항")),
    TaxonomySeed("REM.EXCLUSIVE_REMEDY.FRAUD_CARVEOUT", "REM.EXCLUSIVE_REMEDY", "REM", "사기 구제 예외", "Fraud carve-out from exclusive remedy", "유일·배타적 구제 조항이 사기, 고의적 허위진술 또는 고의적 위법행위에는 적용되지 않는다는 예외", 2, ("fraud carve-out exclusive remedy", "fraud exception to sole remedy", "사기 구제 예외")),
    TaxonomySeed("REM.EXCLUSIVE_REMEDY.SPECIFIC_PERFORMANCE_CARVEOUT", "REM.EXCLUSIVE_REMEDY", "REM", "특정이행 구제 예외", "Specific-performance carve-out", "유일·배타적 구제 조항에도 불구하고 특정이행, 가처분 또는 형평법상 구제를 청구할 수 있다는 예외", 2, ("specific performance carve-out", "equitable relief exception", "특정이행 구제 예외", "가처분 예외")),
    TaxonomySeed("REM.SURVIVAL.STATUTE_OF_LIMITATIONS", "REM.SURVIVAL", "REM", "법정 시효까지 존속", "Survival through statute of limitations", "조세·기본진술 등 특정 진술보장이나 청구권이 적용 법정 소멸시효·제척기간까지 존속한다는 규칙", 2, ("survival through statute of limitations", "applicable limitation period", "소멸시효까지 존속", "법정기간 존속")),
    TaxonomySeed("REM.INDEMNITY.TAX", "REM.INDEMNITY", "REM", "조세 손해배상", "Tax indemnity", "종결 전 과세기간 또는 straddle period에 귀속되는 조세채무를 별도 손해배상 대상으로 정하는 조항", 2, ("tax indemnity", "pre-closing tax indemnity", "조세 손해배상", "종결 전 세금 보상")),
    TaxonomySeed("REM.INDEMNITY.COVENANT_BREACH", "REM.INDEMNITY", "REM", "확약 위반 손해배상", "Covenant-breach indemnity", "계약상 확약, 약속, 합의 또는 기타 의무의 위반으로 발생한 손해를 배상 대상으로 정하는 trigger", 2, ("covenant breach indemnity", "breach of obligations indemnity", "확약 위반 손해배상", "의무 위반 보상")),
    TaxonomySeed("REM.INDEMNITY.RW_BREACH", "REM.INDEMNITY", "REM", "진술보장 위반 손해배상", "Representation-and-warranty breach indemnity", "진술보장의 부정확, 불완전 또는 위반으로 발생한 손해를 배상 대상으로 정하는 trigger", 2, ("R&W breach indemnity", "representation warranty breach indemnity", "진술보장 위반 손해배상")),
    TaxonomySeed("REM.INDEMNITY.EXCLUDED_LIABILITIES", "REM.INDEMNITY", "REM", "제외채무 손해배상", "Excluded-liabilities indemnity", "자산양수도에서 매수인이 인수하지 않은 제외채무로 인한 손해를 매도인의 배상 대상으로 정하는 조항", 2, ("excluded liabilities indemnity", "indemnity for excluded liabilities", "제외채무 손해배상", "비승계채무 보상")),
)

# Taxonomy version 9: generic but search-relevant leaves needed to finish the
# nine-document V4-2 review without misusing a non-leaf parent. Contract-specific
# defined terms remain individually searchable through object_type/proposition.
SEED_TAXONOMY += (
    TaxonomySeed("DEF.CONTRACT_TERM", "DEF", "DEF", "기타 계약상 정의용어", "Other defined contract term", "독립 검색가치는 있으나 별도 표준 정의 노드가 없는 계약별 정의용어", 1, ("other defined term", "contract-specific definition", "기타 정의용어")),
    TaxonomySeed("COV.ASSIGNMENT", "COV", "COV", "계약상 지위·권리의 양도제한", "Assignment restriction", "계약상 지위·권리·의무를 상대방 동의 없이 양도하거나 이전하지 않을 의무", 1, ("assignment restriction", "no assignment without consent", "계약상 지위 양도금지", "권리의무 양도제한")),
    TaxonomySeed("COV.SHA.TRANSFER.RESTRICTION", "COV.SHA.TRANSFER", "COV", "일반 주식양도 제한", "General share transfer restriction", "주식·지분의 양도를 금지하거나 사전동의·절차 준수를 조건으로 하는 일반 제한", 3, ("general transfer restriction", "restriction on transfer of shares", "주식양도 제한", "지분 처분 제한")),
    TaxonomySeed("COV.REGULATORY.COMPLIANCE", "COV.REGULATORY", "COV", "종결 후 인허가·규제준수", "Post-closing regulatory compliance", "거래종결 후 사업 인허가를 취득·유지하고 관련 규제를 준수할 의무", 2, ("post-closing permit compliance", "maintain regulatory approvals", "인허가 취득·유지 의무", "규제준수 확약")),
    TaxonomySeed("REM.SURVIVAL.GENERAL", "REM.SURVIVAL", "REM", "일반 존속기간", "General contractual survival period", "진술보장·확약·청구권의 계약상 존속기간과 종료시점을 정하는 일반 규칙", 2, ("general survival period", "survival of representations", "진술보장 존속기간", "계약상 존속기간")),
    TaxonomySeed("REM.DIRECT_CLAIMS.GENERAL", "REM.DIRECT_CLAIMS", "REM", "일반 직접청구 절차", "General direct-claim procedure", "제3자청구가 아닌 당사자 간 직접 손해배상청구의 제기·검토·이의 절차", 2, ("direct claim procedure", "claims between the parties", "직접청구 절차", "당사자간 손해배상청구")),
)

# v10 gaps confirmed while context-reviewing the remaining nine documents.
# These are recurring, independently searchable propositions that could not be
# represented faithfully by the v9 leaves.
SEED_TAXONOMY += (
    TaxonomySeed("PAY.TRANSACTION_COSTS", "PAY", "PAY", "거래 관련 세금·비용 부담", "Transaction taxes and expenses allocation", "계약 체결·이행 및 거래와 관련된 세금·비용을 어느 당사자가 부담하는지 정하는 지급구조", 1, ("each party bears its own costs", "transaction expense allocation", "각자 비용 부담", "세금 및 비용 부담")),
    TaxonomySeed("PAY.CLOSING_MECHANICS", "PAY", "PAY", "거래종결 시기·장소·절차", "Closing time, place and mechanics", "거래종결의 일시·장소와 종결 실행방식을 정하는 절차", 1, ("closing time and place", "closing mechanics", "거래종결 일시", "종결 장소")),
    TaxonomySeed("RW.CONTRACTS.ARM_LENGTH", "RW.CONTRACTS", "RW", "중요계약의 독립당사자 간 정상조건", "Material contracts on arm's-length terms", "중요계약이 통상적 사업과정에서 독립당사자 간 공정한 조건으로 체결되었다는 진술", 2, ("arm's-length contracts", "ordinary course fair terms", "독립된 제3자 간 공정한 거래조건", "정상가격 계약")),
    TaxonomySeed("RW.FINANCIAL.NO_GUARANTEE_SECURITY", "RW.FINANCIAL", "RW", "제3자 채무 보증·담보 제공 없음", "No guarantee or security for third-party obligations", "대상회사가 제3자의 채무 또는 이행을 위해 보증이나 담보를 제공하지 않았다는 진술", 2, ("no third-party guarantee", "no security for another's debt", "타인 채무 보증 없음", "제3자 담보 제공 없음")),
    TaxonomySeed("REM.GOVERNING_LAW", "REM", "REM", "준거법", "Governing law", "계약과 관련 분쟁에 적용될 준거법을 정하는 조항", 1, ("governing law", "laws governing the agreement", "준거법", "법률에 따라 해석")),
    TaxonomySeed("REM.DISPUTE_RESOLUTION", "REM", "REM", "분쟁해결·관할", "Dispute resolution and jurisdiction", "계약상 분쟁의 법원 관할·중재 또는 기타 해결절차를 정하는 조항", 1, ("exclusive jurisdiction", "dispute resolution", "전속관할", "합의관할", "중재")),
    TaxonomySeed("REM.ENTIRE_AGREEMENT", "REM", "REM", "완전합의", "Entire agreement", "계약이 당사자 간 최종적·완전한 합의이며 종전 합의를 대체한다는 조항", 1, ("entire agreement", "supersedes prior agreements", "완전한 합의", "종전 합의를 대체")),
    TaxonomySeed("REM.AMENDMENT", "REM", "REM", "계약 변경 방식", "Amendment requirements", "계약의 수정·개정·변경에 필요한 서면·서명 등 형식요건", 1, ("amendment in writing", "written modification", "서면 변경", "수정 또는 개정")),
    TaxonomySeed("REM.CUMULATIVE_REMEDIES", "REM", "REM", "구제수단의 누적성", "Cumulative remedies", "계약상 권리·구제수단이 법률상 다른 구제수단을 배제하지 않고 누적 적용된다는 조항", 1, ("cumulative remedies", "rights and remedies are cumulative", "구제수단 중첩", "다른 구제수단을 배제하지 않음")),
    TaxonomySeed("REM.EFFECTIVE_DATE", "REM", "REM", "계약 효력발생일", "Effective date", "계약의 효력이 발생하는 날짜 또는 시점을 정하는 조항", 1, ("effective date", "agreement becomes effective", "효력발생일", "효력이 발생")),
    TaxonomySeed("COV.SHA.PERMITTED_TRANSFER", "COV.SHA.TRANSFER", "COV", "허용되는 주식양도", "Permitted share transfer", "일반 양도제한의 예외로 계열회사·핵심인력 등 특정 수령인에게 허용되는 주식양도", 3, ("permitted transfer", "transfer to key personnel", "허용양도", "핵심인력에게 양도")),
)

# v11 closes the two non-leaf catches exposed by the final audit.
SEED_TAXONOMY += (
    TaxonomySeed("CP.GOVERNMENT_APPROVAL.GENERAL", "CP.GOVERNMENT_APPROVAL", "CP", "일반 정부승인·인가", "General governmental approval", "특정 규제유형으로 더 세분되지 않는 정부기관 승인·인가·허가의 취득 조건", 2, ("governmental approval", "regulatory approval", "정부기관 승인", "정부승인 취득")),
    TaxonomySeed("DEF.DEBT.GENERAL", "DEF.DEBT", "DEF", "차입금·금융부채 일반 정의", "General debt or indebtedness definition", "특정 순차입금 계산요소가 아닌 계약상 Debt·Indebtedness의 일반 정의", 2, ("debt definition", "indebtedness definition", "차입금 정의", "금융부채 정의")),
)

# v12 recurring propositions confirmed by the sixty-document pilot.
SEED_TAXONOMY += (
    TaxonomySeed("RW.BUYER", "RW", "RW", "매수인 관련 진술보장", "Buyer representations", "매수인의 자금·조사·의존 등에 관한 진술보장", 1, ("buyer representations", "purchaser representations", "매수인 진술보장")),
    TaxonomySeed("RW.BUYER.SUFFICIENT_FUNDS", "RW.BUYER", "RW", "매수인 자금충분성", "Sufficiency of buyer funds", "매수인이 매매대금과 거래비용을 지급할 충분한 자금 또는 확정된 자금조달원을 보유한다는 진술", 2, ("sufficient funds", "available funds", "funds to pay the purchase price", "매수인 충분한 자금", "매매대금 지급 자금")),
    TaxonomySeed("RW.BUYER.INDEPENDENT_INVESTIGATION", "RW.BUYER", "RW", "매수인의 독자 조사·판단", "Independent buyer investigation", "매수인이 독자적인 실사·조사·평가에 기초하여 거래를 결정하였다는 진술", 2, ("independent investigation", "independent evaluation", "own assessment", "독자적인 평가", "독자적 조사")),
    TaxonomySeed("RW.BUYER.NO_RELIANCE", "RW.BUYER", "RW", "매수인의 비의존", "Buyer no-reliance", "매수인이 계약에 명시된 진술보장 외의 진술·자료·예측 등에 의존하지 않았다는 진술", 2, ("no reliance", "has not relied", "not induced by", "비의존", "의존하지 아니")),
    TaxonomySeed("CP.WAIVER", "CP", "CP", "선행조건 면제", "Waiver of conditions precedent", "선행조건의 전부 또는 일부를 수익 당사자가 서면 등 합의된 방식으로 면제할 수 있는지와 그 절차", 1, ("waiver of condition", "condition precedent waiver", "선행조건 면제", "조건 면제")),
    TaxonomySeed("CP.SELF_CAUSED_FAILURE", "CP", "CP", "자초한 선행조건 미충족 원용 제한", "No reliance on self-caused condition failure", "자신의 위반 또는 방해로 선행조건이 미충족된 당사자가 그 미충족을 거래종결 거절 사유로 원용하지 못한다는 규정", 1, ("self-caused failure", "may not rely on failure of a condition", "prevention principle", "선행조건 충족 방해", "자초한 미충족")),
    TaxonomySeed("CP.ANCILLARY.TRANSACTION_CLOSING", "CP.ANCILLARY", "CP", "연계거래 계약 체결·종결", "Ancillary transaction execution and closing", "다른 주식매매·투자·조직재편 등 연계거래의 계약이 유효하게 체결되거나 동시 또는 선행 종결될 것을 요구하는 조건", 2, ("ancillary transaction closing", "simultaneous closing", "related agreement execution", "연계거래 종결", "동시 종결")),
    TaxonomySeed("CP.PURCHASE_PRICE_ADJUSTMENT", "CP", "CP", "대금조정 절차 완료", "Completion of purchase-price adjustment", "거래종결 전에 매매대금 조정절차가 완료되고 최종 대금 또는 가격조정 합의서가 확정될 것을 요구하는 조건", 1, ("purchase price adjustment completed", "final purchase price determined", "대금조정 완료", "최종 매매대금 확정")),
    TaxonomySeed("PAY.EARNOUT.PAYMENT", "PAY.EARNOUT", "PAY", "언아웃 지급구조", "Earn-out payment mechanics", "언아웃 금액의 지급시기·지급방법·수령인·분배 등 지급구조", 2, ("earn-out payment", "earnout payment mechanics", "additional consideration payment", "언아웃 지급", "추가대금 지급")),
    TaxonomySeed("RW.DISCLOSURE.NO_OTHER_REPRESENTATIONS", "RW.DISCLOSURE", "RW", "명시된 것 외 진술보장 부인", "No other representations", "계약에 명시된 진술보장이 전부이고 그 밖의 명시적·묵시적 진술보장은 제공되지 않는다는 진술", 2, ("no other representations", "exclusive representations and warranties", "no implied representation", "다른 진술 및 보장 없음", "명시된 진술보장 외에는")),
)


DDL = """
CREATE TABLE IF NOT EXISTS v4_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS v4_taxonomy_node (
  taxonomy_id TEXT PRIMARY KEY,
  parent_id TEXT REFERENCES v4_taxonomy_node(taxonomy_id),
  family TEXT NOT NULL CHECK (family IN ('RW','CP','COV','DEF','PAY','REM')),
  canonical_ko TEXT NOT NULL,
  canonical_en TEXT NOT NULL,
  definition TEXT NOT NULL,
  include_criteria TEXT,
  exclude_criteria TEXT,
  depth INTEGER NOT NULL CHECK (depth >= 0),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','deprecated')),
  taxonomy_version INTEGER NOT NULL,
  origin TEXT NOT NULL CHECK (origin IN ('seed','promoted'))
);
CREATE TABLE IF NOT EXISTS v4_taxonomy_alias (
  alias_id INTEGER PRIMARY KEY AUTOINCREMENT,
  taxonomy_id TEXT NOT NULL REFERENCES v4_taxonomy_node(taxonomy_id),
  alias TEXT NOT NULL,
  lang TEXT NOT NULL DEFAULT 'auto',
  normalized_alias TEXT NOT NULL,
  UNIQUE(taxonomy_id, normalized_alias)
);
CREATE TABLE IF NOT EXISTS v4_clause_item (
  item_id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_key TEXT NOT NULL REFERENCES files(file_key),
  item_ref TEXT NOT NULL,
  family TEXT NOT NULL CHECK (family IN ('RW','CP','COV','DEF','PAY','REM')),
  taxonomy_id TEXT NOT NULL REFERENCES v4_taxonomy_node(taxonomy_id),
  proposition TEXT NOT NULL,
  statement_polarity TEXT NOT NULL CHECK (statement_polarity IN ('affirmative','negative','none_exist','not_applicable')),
  subject_role TEXT,
  counterparty_role TEXT,
  action TEXT,
  object_type TEXT,
  effective_time TEXT,
  source_kind TEXT NOT NULL DEFAULT 'body'
    CHECK (source_kind IN ('body','schedule','disclosure_schedule','annex','exhibit')),
  source_id TEXT,
  source_name TEXT,
  source_ref TEXT,
  parent_clause_ref TEXT,
  related_item_ref TEXT,
  qualifier_json TEXT NOT NULL DEFAULT '{}',
  verbatim TEXT NOT NULL,
  loc_start INTEGER NOT NULL,
  loc_end INTEGER NOT NULL,
  normalized_json TEXT NOT NULL DEFAULT '{}',
  confidence TEXT NOT NULL CHECK (confidence IN ('low','med','high')),
  txt_hash TEXT NOT NULL,
  taxonomy_version INTEGER NOT NULL,
  extractor_version TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  review_status TEXT NOT NULL CHECK (review_status IN ('pending','approved','needs_review','rejected')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK (loc_start > 0 AND loc_end >= loc_start)
);
CREATE INDEX IF NOT EXISTS idx_v4_item_file_family ON v4_clause_item(file_key, family);
CREATE INDEX IF NOT EXISTS idx_v4_item_taxonomy ON v4_clause_item(taxonomy_id, statement_polarity);
CREATE VIRTUAL TABLE IF NOT EXISTS v4_item_fts USING fts5(
  proposition, verbatim, content='v4_clause_item', content_rowid='item_id', tokenize='trigram'
);
CREATE TRIGGER IF NOT EXISTS v4_item_ai AFTER INSERT ON v4_clause_item BEGIN
  INSERT INTO v4_item_fts(rowid, proposition, verbatim) VALUES (new.item_id, new.proposition, new.verbatim);
END;
CREATE TRIGGER IF NOT EXISTS v4_item_ad AFTER DELETE ON v4_clause_item BEGIN
  INSERT INTO v4_item_fts(v4_item_fts, rowid, proposition, verbatim) VALUES ('delete', old.item_id, old.proposition, old.verbatim);
END;
CREATE TRIGGER IF NOT EXISTS v4_item_au AFTER UPDATE ON v4_clause_item BEGIN
  INSERT INTO v4_item_fts(v4_item_fts, rowid, proposition, verbatim) VALUES ('delete', old.item_id, old.proposition, old.verbatim);
  INSERT INTO v4_item_fts(rowid, proposition, verbatim) VALUES (new.item_id, new.proposition, new.verbatim);
END;
CREATE TABLE IF NOT EXISTS v4_document_coverage (
  file_key TEXT NOT NULL REFERENCES files(file_key),
  family TEXT NOT NULL CHECK (family IN ('RW','CP','COV','DEF','PAY','REM')),
  body_status TEXT NOT NULL CHECK (body_status IN ('complete','partial','not_evaluated','unreadable')),
  annex_status TEXT NOT NULL CHECK (annex_status IN ('complete','partial','not_evaluated','unreadable','no_annex')),
  reason TEXT,
  txt_hash TEXT NOT NULL,
  taxonomy_version INTEGER NOT NULL,
  extractor_version TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  reviewed_at TEXT,
  PRIMARY KEY(file_key, family)
);
CREATE TABLE IF NOT EXISTS v4_source_coverage (
  file_key TEXT NOT NULL REFERENCES files(file_key),
  family TEXT NOT NULL CHECK (family IN ('RW','CP','COV','DEF','PAY','REM')),
  source_id TEXT NOT NULL,
  source_kind TEXT NOT NULL
    CHECK (source_kind IN ('body','schedule','disclosure_schedule','annex','exhibit')),
  source_name TEXT NOT NULL,
  source_ref TEXT,
  storage_file_key TEXT REFERENCES files(file_key),
  status TEXT NOT NULL
    CHECK (status IN ('complete','partial','not_evaluated','unreadable','missing')),
  reason TEXT,
  txt_hash TEXT NOT NULL,
  taxonomy_version INTEGER NOT NULL,
  extractor_version TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  reviewed_at TEXT,
  PRIMARY KEY(file_key, family, source_id)
);
CREATE INDEX IF NOT EXISTS idx_v4_source_coverage_status
  ON v4_source_coverage(file_key, family, status);
CREATE TABLE IF NOT EXISTS v4_taxonomy_candidate (
  candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
  proposed_ko TEXT NOT NULL,
  proposed_en TEXT,
  family TEXT NOT NULL CHECK (family IN ('RW','CP','COV','DEF','PAY','REM')),
  recommended_parent_id TEXT NOT NULL REFERENCES v4_taxonomy_node(taxonomy_id),
  distinction_reason TEXT NOT NULL,
  evidence_file_key TEXT NOT NULL REFERENCES files(file_key),
  loc_start INTEGER NOT NULL,
  loc_end INTEGER NOT NULL,
  verbatim TEXT NOT NULL,
  document_count INTEGER NOT NULL DEFAULT 1,
  nearest_taxonomy_id TEXT REFERENCES v4_taxonomy_node(taxonomy_id),
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','merged','rejected')),
  resolution_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK (loc_start > 0 AND loc_end >= loc_start)
);
CREATE INDEX IF NOT EXISTS idx_v4_candidate_status ON v4_taxonomy_candidate(status, family);
"""


class V4SchemaError(ValueError):
    pass


def normalize_alias(value: str) -> str:
    return " ".join(value.casefold().split())


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def _ensure_column(conn: sqlite3.Connection, table: str, name: str, ddl: str) -> None:
    if name not in _table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def _migrate_family_constraints(conn: sqlite3.Connection) -> None:
    """Rebuild the empty pre-1R2 V4 layer so SQLite CHECKs allow six families.

    SQLite cannot alter CHECK constraints in place.  Refuse to reset a V4
    layer containing extracted items, coverage, candidates or promoted nodes.
    The current project has no such rows, so this preserves all T1-T3 data
    while safely reseeding V4.
    """

    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='v4_taxonomy_node'"
    ).fetchone()
    if row is None or "'DEF'" in str(row[0] or ""):
        return
    protected_counts = {}
    for table in (
        "v4_clause_item",
        "v4_document_coverage",
        "v4_source_coverage",
        "v4_taxonomy_candidate",
    ):
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        protected_counts[table] = (
            conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if exists
            else 0
        )
    promoted = conn.execute(
        "SELECT COUNT(*) FROM v4_taxonomy_node WHERE origin='promoted'"
    ).fetchone()[0]
    if any(protected_counts.values()) or promoted:
        detail = ", ".join(
            f"{name}={count}" for name, count in protected_counts.items() if count
        )
        if promoted:
            detail = f"{detail}, promoted={promoted}".strip(", ")
        raise V4SchemaError(
            "cannot migrate V4 family constraints with generated/promoted data; "
            f"export and perform a controlled migration first ({detail})"
        )
    conn.executescript(
        """
        DROP TRIGGER IF EXISTS v4_item_ai;
        DROP TRIGGER IF EXISTS v4_item_ad;
        DROP TRIGGER IF EXISTS v4_item_au;
        DROP TABLE IF EXISTS v4_item_fts;
        DROP TABLE IF EXISTS v4_taxonomy_candidate;
        DROP TABLE IF EXISTS v4_source_coverage;
        DROP TABLE IF EXISTS v4_document_coverage;
        DROP TABLE IF EXISTS v4_clause_item;
        DROP TABLE IF EXISTS v4_taxonomy_alias;
        DROP TABLE IF EXISTS v4_taxonomy_node;
        """
    )


def initialize_v4_schema(
    conn: sqlite3.Connection,
    taxonomy_version: int = DEFAULT_TAXONOMY_VERSION,
) -> None:
    conn.execute("PRAGMA foreign_keys=ON")
    _migrate_family_constraints(conn)
    conn.executescript(DDL)
    # Existing V4 databases predate the source-link columns. Keep migration additive.
    _ensure_column(
        conn,
        "v4_clause_item",
        "source_kind",
        "TEXT NOT NULL DEFAULT 'body' CHECK (source_kind IN ('body','schedule','disclosure_schedule','annex','exhibit'))",
    )
    for name in ("source_id", "source_name", "source_ref", "parent_clause_ref"):
        _ensure_column(conn, "v4_clause_item", name, "TEXT")
    _ensure_column(conn, "v4_clause_item", "related_item_ref", "TEXT")
    _ensure_column(conn, "v4_clause_item", "item_ref", "TEXT")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_v4_item_ref "
        "ON v4_clause_item(file_key,item_ref)"
    )
    conn.execute(
        "INSERT INTO v4_meta(key,value) VALUES ('schema_version',?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(V4_SCHEMA_VERSION),),
    )
    conn.execute(
        "INSERT INTO v4_meta(key,value) VALUES ('schema_revision',?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (V4_SCHEMA_REVISION,),
    )
    conn.execute(
        "INSERT INTO v4_meta(key,value) VALUES ('taxonomy_version',?) "
        "ON CONFLICT(key) DO UPDATE SET value=CASE "
        "WHEN CAST(value AS INTEGER) < CAST(excluded.value AS INTEGER) THEN excluded.value ELSE value END",
        (str(taxonomy_version),),
    )
    for seed in SEED_TAXONOMY:
        conn.execute(
            """
            INSERT OR IGNORE INTO v4_taxonomy_node(
              taxonomy_id,parent_id,family,canonical_ko,canonical_en,definition,
              depth,status,taxonomy_version,origin
            ) VALUES (?,?,?,?,?,?,?,'active',?,'seed')
            """,
            (seed.taxonomy_id, seed.parent_id, seed.family, seed.canonical_ko, seed.canonical_en, seed.definition, seed.depth, taxonomy_version),
        )
        for alias in (seed.canonical_ko, seed.canonical_en, *seed.aliases):
            conn.execute(
                "INSERT OR IGNORE INTO v4_taxonomy_alias(taxonomy_id,alias,normalized_alias) VALUES (?,?,?)",
                (seed.taxonomy_id, alias, normalize_alias(alias)),
            )
    # A small number of broad v3 aliases now have a confirmed, more specific
    # v4 leaf. Reassign only those explicit aliases; canonical node names and
    # promoted/user-managed aliases are otherwise preserved.
    for alias, taxonomy_id in ALIAS_REASSIGNMENTS.items():
        conn.execute(
            """
            DELETE FROM v4_taxonomy_alias
            WHERE normalized_alias=? AND taxonomy_id<>?
            """,
            (normalize_alias(alias), taxonomy_id),
        )


def taxonomy_ids(conn: sqlite3.Connection) -> Dict[str, str]:
    return {row[0]: row[1] for row in conn.execute("SELECT taxonomy_id,family FROM v4_taxonomy_node WHERE status='active'")}


def taxonomy_parents(conn: sqlite3.Connection) -> Dict[str, Optional[str]]:
    return {
        str(row[0]): (str(row[1]) if row[1] is not None else None)
        for row in conn.execute(
            "SELECT taxonomy_id,parent_id FROM v4_taxonomy_node WHERE status='active'"
        )
    }


def taxonomy_aliases(conn: sqlite3.Connection) -> Dict[str, str]:
    return {
        str(row[0]): str(row[1])
        for row in conn.execute(
            """
            SELECT normalized_alias,taxonomy_id
            FROM v4_taxonomy_alias a
            JOIN v4_taxonomy_node n USING(taxonomy_id)
            WHERE n.status='active'
            """
        )
    }


def _location(item: Mapping[str, object], path: str) -> None:
    start, end = item.get("loc_start"), item.get("loc_end")
    if isinstance(start, bool) or not isinstance(start, int) or start < 1:
        raise V4SchemaError(f"{path}.loc_start must be a positive integer")
    if isinstance(end, bool) or not isinstance(end, int) or end < start:
        raise V4SchemaError(f"{path}.loc_end must be an integer >= loc_start")


def validate_v4_result(data: Mapping[str, object], *, file_key: str, known_taxonomy: Mapping[str, str]) -> Mapping[str, object]:
    required = (
        "file_key",
        "meta_schema_version",
        "items",
        "coverage",
        "source_coverage",
        "extractor_version",
        "prompt_version",
        "taxonomy_version",
    )
    for key in required:
        if key not in data:
            raise V4SchemaError(f"missing result key: {key}")
    if data["file_key"] != file_key:
        raise V4SchemaError("result file_key does not match input")
    if data["meta_schema_version"] != V4_SCHEMA_VERSION:
        raise V4SchemaError("meta_schema_version must be 4")
    if not isinstance(data["items"], list):
        raise V4SchemaError("items must be an array")
    if not isinstance(data["coverage"], dict):
        raise V4SchemaError("coverage must be an object")
    if not isinstance(data["source_coverage"], list):
        raise V4SchemaError("source_coverage must be an array")
    for field in ("extractor_version", "prompt_version"):
        if not isinstance(data[field], str) or not str(data[field]).strip():
            raise V4SchemaError(f"{field} must be a non-empty string")
    if isinstance(data["taxonomy_version"], bool) or not isinstance(data["taxonomy_version"], int) or data["taxonomy_version"] < 1:
        raise V4SchemaError("taxonomy_version must be a positive integer")

    for family in FAMILIES:
        raw = data["coverage"].get(family)
        if not isinstance(raw, dict):
            raise V4SchemaError(f"coverage.{family} must be an object")
        if raw.get("body_status") not in BODY_STATUS_VALUES:
            raise V4SchemaError(f"coverage.{family}.body_status is invalid")
        if raw.get("annex_status") not in ANNEX_STATUS_VALUES:
            raise V4SchemaError(f"coverage.{family}.annex_status is invalid")
        reason = raw.get("reason")
        if reason is not None and not isinstance(reason, str):
            raise V4SchemaError(f"coverage.{family}.reason must be string or null")

    seen_sources: set[tuple[str, str]] = set()
    annex_statuses: Dict[str, List[str]] = {family: [] for family in FAMILIES}
    for index, raw in enumerate(data["source_coverage"]):
        path = f"source_coverage[{index}]"
        if not isinstance(raw, dict):
            raise V4SchemaError(f"{path} must be an object")
        family = raw.get("family")
        if family not in FAMILIES:
            raise V4SchemaError(f"{path}.family is invalid")
        for field in ("source_id", "source_name"):
            if not isinstance(raw.get(field), str) or not str(raw[field]).strip():
                raise V4SchemaError(f"{path}.{field} must be a non-empty string")
        if raw.get("source_kind") not in SOURCE_KIND_VALUES:
            raise V4SchemaError(f"{path}.source_kind is invalid")
        if raw.get("status") not in SOURCE_STATUS_VALUES:
            raise V4SchemaError(f"{path}.status is invalid")
        for field in ("source_ref", "storage_file_key", "reason"):
            if raw.get(field) is not None and not isinstance(raw.get(field), str):
                raise V4SchemaError(f"{path}.{field} must be string or null")
        key = (str(family), str(raw["source_id"]))
        if key in seen_sources:
            raise V4SchemaError(f"{path} duplicates source_id within family")
        seen_sources.add(key)
        if raw["source_kind"] != "body":
            annex_statuses[str(family)].append(str(raw["status"]))

    for family in FAMILIES:
        aggregate = data["coverage"][family]["annex_status"]
        statuses = annex_statuses[family]
        if not statuses:
            if aggregate not in ("no_annex", "not_evaluated"):
                raise V4SchemaError(
                    f"coverage.{family}.annex_status requires source_coverage rows"
                )
            continue
        if aggregate == "complete" and any(status != "complete" for status in statuses):
            raise V4SchemaError(
                f"coverage.{family}.annex_status cannot be complete while a source is incomplete"
            )
        if aggregate == "no_annex":
            raise V4SchemaError(
                f"coverage.{family}.annex_status cannot be no_annex when annex sources exist"
            )

    item_refs: set[str] = set()
    for index, raw in enumerate(data["items"]):
        path = f"items[{index}]"
        if not isinstance(raw, dict):
            raise V4SchemaError(f"{path} must be an object")
        item_ref = raw.get("item_ref")
        if not isinstance(item_ref, str) or not item_ref.strip():
            raise V4SchemaError(f"{path}.item_ref must be a non-empty string")
        if item_ref in item_refs:
            raise V4SchemaError(f"{path}.item_ref must be unique within result")
        item_refs.add(item_ref)

    for index, raw in enumerate(data["items"]):
        path = f"items[{index}]"
        family = raw.get("family")
        taxonomy_id = raw.get("taxonomy_id")
        if family not in FAMILIES:
            raise V4SchemaError(f"{path}.family is invalid")
        if taxonomy_id not in known_taxonomy:
            raise V4SchemaError(f"{path}.taxonomy_id is unknown: {taxonomy_id}")
        if known_taxonomy[taxonomy_id] != family:
            raise V4SchemaError(f"{path}.taxonomy_id belongs to another family")
        for field in ("proposition", "verbatim"):
            if not isinstance(raw.get(field), str) or not str(raw[field]).strip():
                raise V4SchemaError(f"{path}.{field} must be a non-empty string")
        if raw.get("statement_polarity") not in POLARITY_VALUES:
            raise V4SchemaError(f"{path}.statement_polarity is invalid")
        if raw.get("confidence") not in CONFIDENCE_VALUES:
            raise V4SchemaError(f"{path}.confidence is invalid")
        if raw.get("review_status") not in REVIEW_STATUS_VALUES:
            raise V4SchemaError(f"{path}.review_status is invalid")
        for field in ("qualifier", "normalized"):
            if not isinstance(raw.get(field), dict):
                raise V4SchemaError(f"{path}.{field} must be an object")
        for field in (
            "subject_role",
            "counterparty_role",
            "action",
            "object_type",
            "effective_time",
            "source_id",
            "source_name",
            "source_ref",
            "parent_clause_ref",
            "related_item_ref",
        ):
            if raw.get(field) is not None and not isinstance(raw.get(field), str):
                raise V4SchemaError(f"{path}.{field} must be string or null")
        if raw.get("source_kind") not in SOURCE_KIND_VALUES:
            raise V4SchemaError(f"{path}.source_kind is invalid")
        if raw["source_kind"] != "body":
            source_id = raw.get("source_id")
            if not source_id or (str(family), str(source_id)) not in seen_sources:
                raise V4SchemaError(
                    f"{path}.source_id must reference source_coverage for annex items"
                )
        related = raw.get("related_item_ref")
        if related is not None:
            if related == raw["item_ref"]:
                raise V4SchemaError(f"{path}.related_item_ref cannot reference itself")
            if related not in item_refs:
                raise V4SchemaError(
                    f"{path}.related_item_ref must reference another result item"
                )
        _location(raw, path)
        if (
            raw["source_kind"] == "body"
            and data["coverage"][family]["body_status"]
            in ("not_evaluated", "unreadable")
        ):
            raise V4SchemaError(f"{path} cannot exist when {family} body is not evaluated")
    return data


def absence_is_provable(coverage: Mapping[str, object]) -> bool:
    return coverage.get("body_status") == "complete" and coverage.get("annex_status") in ("complete", "no_annex")


def replace_v4_result(
    conn: sqlite3.Connection,
    *,
    file_key: str,
    txt_hash: str,
    data: Mapping[str, object],
) -> None:
    """Replace one document's verified V4 rows without touching doc_meta."""

    known = taxonomy_ids(conn)
    validate_v4_result(data, file_key=file_key, known_taxonomy=known)
    now = datetime.now(timezone.utc).isoformat()
    taxonomy_version = int(data["taxonomy_version"])
    extractor_version = str(data["extractor_version"])
    prompt_version = str(data["prompt_version"])

    conn.execute("DELETE FROM v4_clause_item WHERE file_key=?", (file_key,))
    conn.execute("DELETE FROM v4_document_coverage WHERE file_key=?", (file_key,))
    conn.execute("DELETE FROM v4_source_coverage WHERE file_key=?", (file_key,))
    conn.execute(
        "DELETE FROM v4_taxonomy_candidate WHERE evidence_file_key=? AND status='pending'",
        (file_key,),
    )

    for item in data["items"]:
        conn.execute(
            """
            INSERT INTO v4_clause_item(
              file_key,item_ref,family,taxonomy_id,proposition,statement_polarity,
              subject_role,counterparty_role,action,object_type,effective_time,
              source_kind,source_id,source_name,source_ref,parent_clause_ref,
              related_item_ref,qualifier_json,verbatim,loc_start,loc_end,normalized_json,confidence,
              txt_hash,taxonomy_version,extractor_version,prompt_version,review_status,
              created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                file_key,
                item["item_ref"],
                item["family"],
                item["taxonomy_id"],
                item["proposition"],
                item["statement_polarity"],
                item.get("subject_role"),
                item.get("counterparty_role"),
                item.get("action"),
                item.get("object_type"),
                item.get("effective_time"),
                item["source_kind"],
                item.get("source_id"),
                item.get("source_name"),
                item.get("source_ref"),
                item.get("parent_clause_ref"),
                item.get("related_item_ref"),
                json.dumps(item["qualifier"], ensure_ascii=False, sort_keys=True),
                item["verbatim"],
                item["loc_start"],
                item["loc_end"],
                json.dumps(item["normalized"], ensure_ascii=False, sort_keys=True),
                item["confidence"],
                txt_hash,
                taxonomy_version,
                extractor_version,
                prompt_version,
                item["review_status"],
                now,
                now,
            ),
        )

    for family in FAMILIES:
        row = data["coverage"][family]
        conn.execute(
            """
            INSERT INTO v4_document_coverage(
              file_key,family,body_status,annex_status,reason,txt_hash,
              taxonomy_version,extractor_version,prompt_version,reviewed_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                file_key,
                family,
                row["body_status"],
                row["annex_status"],
                row.get("reason"),
                txt_hash,
                taxonomy_version,
                extractor_version,
                prompt_version,
                now,
            ),
        )

    for row in data["source_coverage"]:
        conn.execute(
            """
            INSERT INTO v4_source_coverage(
              file_key,family,source_id,source_kind,source_name,source_ref,
              storage_file_key,status,reason,txt_hash,taxonomy_version,
              extractor_version,prompt_version,reviewed_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                file_key,
                row["family"],
                row["source_id"],
                row["source_kind"],
                row["source_name"],
                row.get("source_ref"),
                row.get("storage_file_key"),
                row["status"],
                row.get("reason"),
                txt_hash,
                taxonomy_version,
                extractor_version,
                prompt_version,
                now,
            ),
        )

    for candidate in data.get("taxonomy_candidates") or []:
        conn.execute(
            """
            INSERT INTO v4_taxonomy_candidate(
              proposed_ko,proposed_en,family,recommended_parent_id,
              distinction_reason,evidence_file_key,loc_start,loc_end,verbatim,
              document_count,nearest_taxonomy_id,status,resolution_json,
              created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,1,?,'pending','{}',?,?)
            """,
            (
                candidate["proposed_ko"],
                candidate.get("proposed_en"),
                candidate["family"],
                candidate["recommended_parent_id"],
                candidate["distinction_reason"],
                file_key,
                candidate["loc_start"],
                candidate["loc_end"],
                candidate["verbatim"],
                candidate["nearest_taxonomy_id"],
                now,
                now,
            ),
        )
