"""Deterministic V4-2 RW extraction for the selected Korean SPA.

This is a review artifact for one representative contract.  It atomizes the
body representations, the referenced company-RW annex, and the annex's
disclosure schedule without calling an external API.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


FILE_KEY = "0ba3a1b8246c5dd5"


def spec(
    taxonomy_id: str,
    para: int,
    proposition: str,
    polarity: str = "affirmative",
    *,
    source: str = "annex",
    subject: str = "대상회사",
    key: str | None = None,
    related_to: str | None = None,
) -> dict:
    return {
        "taxonomy_id": taxonomy_id,
        "para": para,
        "proposition": proposition,
        "polarity": polarity,
        "source": source,
        "subject": subject,
        "key": key,
        "related_to": related_to,
    }


SPECS = [
    # Body — seller, target-company incorporation by reference, and buyer.
    spec("RW.DISCLOSURE.ACCURACY", 57, "매도인의 진술 및 보장은 계약체결일과 거래종결일 현재 진실하고 정확하다.", source="body", subject="매도인"),
    spec("RW.TAX.RESIDENCY", 58, "각 매도인은 대한민국에 거주하는 소득세법상 거주자이다.", source="body", subject="매도인"),
    spec("RW.AUTHORITY.POWER", 59, "각 매도인은 계약 체결과 의무 이행에 필요한 권한과 능력을 보유한다.", source="body", subject="매도인"),
    spec("RW.AUTHORITY.NO_CONFLICT", 60, "계약 체결과 이행은 매도인에게 적용되는 법률·계약을 위반하거나 기한의 이익을 상실시키지 않는다.", "none_exist", source="body", subject="매도인"),
    spec("RW.AUTHORITY.NO_CONSENT", 61, "계약 체결과 이행에 정부기관 인허가나 제3자 동의·승인이 요구되지 않는다.", "none_exist", source="body", subject="매도인"),
    spec("RW.LITIGATION.NO_PENDING", 61, "본건 거래를 금지하거나 제한하는 매도인 또는 대상회사 관련 소송이 제기되지 않았다.", "none_exist", source="body", subject="매도인·대상회사"),
    spec("RW.AUTHORITY.ENFORCEABILITY", 62, "계약은 매도인에 의해 적법하게 체결되어 구속력이 있고 조건에 따라 집행 가능하다.", source="body", subject="매도인"),
    spec("RW.SOLVENCY", 63, "매도인은 채무초과 상태가 아니고 본건 거래 후에도 변제자력을 보유한다.", source="body", subject="매도인"),
    spec("RW.CAPITALIZATION.OWNERSHIP", 64, "매도인은 대상주식을 적법하고 유효하게 소유한다.", source="body", subject="매도인"),
    spec("RW.CAPITALIZATION.FULLY_PAID", 64, "대상주식은 적법하게 발행되고 인수가액이 전액 납입되어 추가 출자의무가 없다.", source="body", subject="대상주식"),
    spec("RW.CAPITALIZATION.NO_ENCUMBRANCE", 64, "대상주식은 제한부담 없이 거래종결일에 매수인에게 이전된다.", "none_exist", source="body", subject="대상주식"),
    spec("RW.DISCLOSURE.ACCURACY", 65, "대상회사에 관한 진술 및 보장은 별지 5.1(8)의 내용으로 제공된다.", source="body", subject="매도인", key="body_annex_reference"),
    spec("RW.DISCLOSURE.ACCURACY", 67, "매수인의 진술 및 보장은 계약체결일과 거래종결일 현재 진실하고 정확하다.", source="body", subject="매수인"),
    spec("RW.AUTHORITY.ORGANIZATION", 68, "매수인은 대한민국 법률에 따라 적법하게 설립되어 유효하게 존속한다.", source="body", subject="매수인"),
    spec("RW.AUTHORITY.POWER", 69, "매수인은 계약 체결과 의무 이행에 필요한 권한과 능력을 보유한다.", source="body", subject="매수인"),
    spec("RW.AUTHORITY.AUTHORIZATION", 70, "매수인은 계약 체결과 이행에 필요한 내부수권절차를 모두 마쳤다.", source="body", subject="매수인"),
    spec("RW.AUTHORITY.NO_CONFLICT", 71, "계약 체결과 이행은 매수인의 조직서류·결의·법률·계약을 위반하지 않는다.", "none_exist", source="body", subject="매수인"),
    spec("RW.AUTHORITY.NO_CONSENT", 72, "매수인의 계약 체결과 이행에 정부기관 인허가나 제3자 동의·승인이 요구되지 않는다.", "none_exist", source="body", subject="매수인"),
    spec("RW.LITIGATION.NO_PENDING", 72, "본건 거래를 금지하거나 제한하는 매수인 관련 소송이 제기되지 않았다.", "none_exist", source="body", subject="매수인"),

    # Annex 5.1(8) — one item for each independently searchable proposition.
    spec("RW.DISCLOSURE.ACCURACY", 260, "공개목록에 공개된 사항을 제외한 대상회사 진술 및 보장은 계약체결일과 거래종결일 현재 진실하고 정확하다.", key="annex_scope", related_to="body_annex_reference"),
    spec("RW.AUTHORITY.ORGANIZATION", 261, "대상회사는 적법하게 설립되어 유효하게 존속한다."),
    spec("RW.AUTHORITY.POWER", 261, "대상회사는 사업 영위와 자산 소유·사용에 필요한 권한과 능력을 가진다."),
    spec("RW.PERMITS.ALL_REQUIRED", 261, "대상회사는 사업 영위와 자산 소유·사용에 필요한 정부기관 인허가를 취득하였다."),
    spec("RW.SOLVENCY", 261, "대상회사에는 해산·청산·파산·회생·워크아웃 또는 발행어음 부도 사유가 없다.", "none_exist"),
    spec("RW.AUTHORITY.NO_CONFLICT", 262, "본 계약의 체결과 이행은 대상회사의 조직서류·결의·법률·인허가·계약을 위반하지 않는다.", "none_exist"),
    spec("RW.ASSETS.NO_ENCUMBRANCE", 262, "본 계약의 체결과 이행은 대상회사 주식 또는 자산에 제한부담을 설정하지 않는다.", "none_exist"),
    spec("RW.CONTRACTS.NO_CHANGE_CONTROL_EFFECT", 262, "본 계약의 체결과 이행은 대상회사 계약의 해지·해제·실효 또는 기한이익 상실을 초래하지 않는다.", "none_exist"),
    spec("RW.ABSENCE_OF_CHANGES", 262, "본 계약의 체결과 이행은 대상회사에 중대하게 부정적인 영향을 초래하지 않는다.", "none_exist"),
    spec("RW.CAPITALIZATION.AUTHORIZED_ISSUED", 263, "대상회사의 수권주식·발행주식·액면금 및 완전희석 기준 대상주식 비율이 기재 내용과 같다."),
    spec("RW.CAPITALIZATION.FULLY_PAID", 263, "대상회사 발행주식은 적법하고 유효하게 발행되었고 추가 납입의무가 없다."),
    spec("RW.CAPITALIZATION.NO_DILUTIVE_SECURITIES", 263, "전환사채·신주인수권부사채·주식매수선택권 등 희석증권이나 신주발행 의무가 없다.", "none_exist"),
    spec("RW.CAPITALIZATION.SUBSIDIARIES", 264, "공개목록의 자회사·계열회사 목록과 지분정보는 완전하고 정확하다.", key="subsidiary_rep"),
    spec("RW.CAPITALIZATION.OWNERSHIP", 264, "대상회사 또는 자회사는 공개목록 기재 자회사 지분을 제한부담 없이 적법하고 유효하게 소유한다."),
    spec("RW.CAPITALIZATION.SUBSIDIARIES", 264, "공개목록 기재 외 자회사나 다른 회사 지분은 존재하지 않는다.", "none_exist"),
    spec("RW.CAPITALIZATION.NO_SHAREHOLDER_AGREEMENT", 265, "대상회사 및 자회사에 관한 주주간계약·투자계약 등 유사 약정은 존재하지 않는다.", "none_exist"),
    spec("RW.FINANCIAL.GAAP", 266, "기준 재무제표는 회계장부에 근거하여 관련 법률과 일반기업회계기준에 따라 작성되었다."),
    spec("RW.FINANCIAL.FAIR_PRESENTATION", 266, "기준 재무제표는 재무상태·영업결과·자본·이익잉여금·현금흐름을 적정하게 표시한다."),
    spec("RW.FINANCIAL.CONSISTENCY", 266, "기준일 이후 회계방법·회계기준·회계관행을 임의로 변경하지 않았다.", "none_exist"),
    spec("RW.ACCOUNTS_RECEIVABLE.VALIDITY", 266, "매출채권은 통상 영업에서 실제·적법하게 발생했고 대상회사가 유효하게 소유한다."),
    spec("RW.ACCOUNTS_RECEIVABLE.COLLECTIBILITY", 266, "매출채권은 일반적으로 회수 가능하다."),
    spec("RW.ACCOUNTS_RECEIVABLE.ALLOWANCE", 266, "대손충당금은 과거 관행에 따라 적정하게 산정되었다."),
    spec("RW.ACCOUNTS_RECEIVABLE.NO_ENCUMBRANCE", 266, "매출채권은 상계·공제·금액조정 대상이 아니고 제한부담이 없다.", "none_exist"),
    spec("RW.FINANCIAL.NO_UNDISCLOSED_LIABILITIES", 267, "재무제표 반영 채무와 기준일 후 통상 영업상 채무 외 부외·우발채무 등이 없다.", "none_exist"),
    spec("RW.ABSENCE_OF_CHANGES", 268, "기준일 이후 대상회사는 통상적인 사업과정에 따라 영업하였다."),
    spec("RW.ABSENCE_OF_CHANGES", 268, "기준일 이후 중대하게 부정적인 영향의 원인이 되는 사건·사유·사정이 발생하지 않았다.", "none_exist"),
    spec("RW.ABSENCE_OF_CHANGES", 268, "기준일 이후 매수인 동의를 요할 사건·사유·사정이 발생하지 않았다.", "none_exist"),
    spec("RW.COMPLIANCE.GENERAL", 269, "대상회사는 공개목록 기재 예외 외에는 적용 법률과 정부기관 명령·처분을 준수하였다.", key="compliance_rep"),
    spec("RW.COMPLIANCE.GENERAL", 269, "관련 법률의 계속 준수를 위해 중대한 자본적 지출이 요구되지 않는다."),
    spec("RW.COMPLIANCE.NO_VIOLATION_NOTICE", 269, "법률·명령·처분 위반 사유나 우려가 없고 정부기관의 위반 통지·고지를 받지 않았다.", "none_exist"),
    spec("RW.PRIVACY.COMPLIANCE", 270, "대상회사는 공개목록 예외 외 개인정보 관련 법률을 준수하였다.", key="privacy_rep"),
    spec("RW.PRIVACY.CYBERSECURITY", 270, "대상회사는 개인정보 법률상 요구되는 안전성 확보 조치를 이행하였다."),
    spec("RW.PRIVACY.NO_BREACH", 270, "개인정보 법률의 중대한 위반을 초래할 사유나 사정이 없다.", "none_exist"),
    spec("RW.PERMITS.ALL_REQUIRED", 271, "대상회사는 사업에 필요한 모든 정부기관 인허가를 적법하게 취득하였다."),
    spec("RW.PERMITS.VALID", 271, "대상회사는 필요한 정부기관 인허가를 유효하게 보유한다."),
    spec("RW.PERMITS.COMPLIANCE", 271, "대상회사는 정부기관 인허가의 조건을 준수하였다."),
    spec("RW.PERMITS.NO_REVOCATION", 271, "인허가의 위반·무효·취소·철회·정지·갱신거절 사유가 없다.", "none_exist"),
    spec("RW.PERMITS.NO_DISPUTE", 271, "정부기관 인허가 관련 소송 또는 분쟁은 존재하지 않는다.", "none_exist"),
    spec("RW.ASSETS.TITLE", 272, "대상회사는 모든 자산에 적법한 소유권 또는 사용권을 가진다."),
    spec("RW.ASSETS.NO_ENCUMBRANCE", 272, "대상회사 소유 자산에는 제한부담이나 제3자 처분약정이 없다.", "none_exist"),
    spec("RW.ASSETS.SUFFICIENCY", 272, "대상회사의 모든 자산은 현재 방식의 사업 수행에 필요하고 충분하다."),
    spec("RW.REAL_ESTATE.LEASE_VALID", 272, "대상회사는 임대차계약을 중요한 면에서 준수하고 있다."),
    spec("RW.REAL_ESTATE.RENT_PAID", 272, "임대차계약상 차임과 기타 금원은 지급기일 내 지급되었다."),
    spec("RW.REAL_ESTATE.NO_DEFAULT", 272, "대상회사는 임대차계약을 중대하게 위반하거나 불이행하지 않았다.", "none_exist"),
    spec("RW.REAL_ESTATE.DEPOSIT_RECOVERABLE", 272, "임대차보증금 반환을 저해하는 사유가 없다.", "none_exist"),
    spec("RW.ASSETS.CONDITION", 272, "유형자산은 정상적인 작동상태로 적절히 유지·보수되었다."),
    spec("RW.INVENTORY.MARKETABILITY", 272, "재고는 정상 영업과정에서 판매 가능한 상태이다."),
    spec("RW.INVENTORY.ADEQUACY", 272, "재고의 수량과 구성은 사업수요에 비추어 합리적이다."),
    spec("RW.INVENTORY.VALUATION", 272, "재고는 적정한 장부가액으로 평가되고 주기적으로 점검된다."),
    spec("RW.IP.SUFFICIENCY", 273, "대상회사의 지식재산권은 현재 및 향후 사업 수행에 필요하고 충분하다."),
    spec("RW.IP.OWNERSHIP", 273, "대상회사는 필요한 지식재산권을 제한부담 없이 적법하고 유효하게 소유하거나 사용할 권리가 있다."),
    spec("RW.IP.VALIDITY", 273, "지식재산권 등록·출원은 유효하고 무효·취소 사유가 없다."),
    spec("RW.IP.EMPLOYEE_ASSIGNMENT", 273, "대상회사는 임직원 직무발명을 적법하게 승계하고 필요한 보상을 하였다."),
    spec("RW.IP.NO_INFRINGEMENT", 273, "대상회사의 사업과 지식재산 사용은 제3자의 권리를 침해하지 않는다.", "none_exist"),
    spec("RW.IP.NO_THIRD_PARTY_INFRINGEMENT", 273, "제3자가 대상회사의 지식재산권을 침해한 사실이나 우려가 없다.", "none_exist"),
    spec("RW.IP.NO_DISPUTE", 273, "지식재산권 관련 분쟁이나 청구가 없다.", "none_exist"),
    spec("RW.IP.LICENSES", 273, "지식재산권 라이선스 계약은 적법하고 유효하다."),
    spec("RW.IP.TRADE_SECRETS", 273, "대상회사는 영업비밀 보호에 필요한 조치를 취하였다."),
    spec("RW.CONTRACTS.COMPLETE_LIST", 274, "중요계약의 완전하고 정확한 사본 또는 서면 요약본이 모두 제공되었다."),
    spec("RW.CONTRACTS.VALID_BINDING", 274, "중요계약은 적법·유효하고 대상회사와 상대방을 구속한다."),
    spec("RW.CONTRACTS.NO_DEFAULT", 274, "대상회사나 상대방의 중요계약상 채무불이행 또는 위반 사유가 없다.", "none_exist"),
    spec("RW.CONTRACTS.NO_TERMINATION_NOTICE", 274, "중요계약의 위반·해제·해지·취소 통지나 그 사유가 없다.", "none_exist"),
    spec("RW.CONTRACTS.NO_CHANGE_CONTROL_EFFECT", 274, "본건 거래로 중요계약상 불이익·변경·해지 권리가 발생하지 않는다.", "none_exist"),
    spec("RW.RELATED_PARTY.NO_TRANSACTION", 275, "특수관계인 거래는 공정한 거래조건으로 체결되고 필요한 내부승인을 거쳤다."),
    spec("RW.RELATED_PARTY.NO_INTEREST", 275, "특수관계인 거래로 법률 위반이나 추가 조세 부담 사유가 없다.", "none_exist"),
    spec("RW.RELATED_PARTY.NO_TRANSACTION", 275, "재무제표 기재 외 특수관계인 계약·거래관계가 없다.", "none_exist"),
    spec("RW.LABOR.NO_VIOLATION", 276, "대상회사는 공개목록 예외 외 노무 법률·내부규정·단체협약·근로계약을 위반하지 않았다.", "none_exist", key="labor_rep"),
    spec("RW.LABOR.WORKING_CONDITIONS", 276, "대상회사는 임금·수당·상여금·퇴직금·근로시간·휴일·휴가·복리후생 등 근로조건을 준수하였다."),
    spec("RW.LABOR.NO_OFF_BOOK_WAGES", 276, "규정에 없는 임금·이익 제공을 약속·협의·합의한 사실이 없다.", "none_exist"),
    spec("RW.BENEFITS.NO_ACCELERATION", 276, "본건 거래와 관련해 임직원에게 지급할 특별 상여금 등 보수가 없다.", "none_exist"),
    spec("RW.LABOR.UNPAID_COMPENSATION", 276, "지급기일이 도래한 임직원 보수와 급여가 미지급 상태가 아니다.", "none_exist"),
    spec("RW.BENEFITS.FUNDING", 276, "퇴직급여·연금 등 임직원 급여채무는 적립·지급되거나 적정하게 충당되었다."),
    spec("RW.LITIGATION.NO_PENDING", 276, "노무 관련 소송·분쟁이 제기되어 있지 않다.", "none_exist"),
    spec("RW.LITIGATION.NO_THREATENED", 276, "노무 관련 소송·분쟁의 제기 우려가 없다.", "none_exist"),
    spec("RW.LABOR.COLLECTIVE", 276, "대상회사에는 노동조합이나 단체협약이 없다.", "none_exist"),
    spec("RW.ENVIRONMENT.COMPLIANCE", 277, "대상회사는 공개목록 예외 외 환경·안전·보건 법률과 명령·약정을 준수하였다.", key="environment_rep"),
    spec("RW.ENVIRONMENT.NO_CLAIMS", 277, "환경·안전·보건 위반 관련 통지·처벌·제재·시정·배상요구가 없고 예상 사정도 없다.", "none_exist"),
    spec("RW.ENVIRONMENT.PERMITS", 277, "필요한 환경·안전·보건 인허가를 적법하게 취득·유지하고 조건을 준수하였다."),
    spec("RW.LITIGATION.NO_PENDING", 277, "환경·안전·보건 관련 소송·분쟁이 제기되어 있지 않다.", "none_exist"),
    spec("RW.ENVIRONMENT.NO_CONTAMINATION", 277, "환경오염이나 유해물질의 배출·누출이 없다.", "none_exist"),
    spec("RW.ENVIRONMENT.NO_REMEDIATION", 277, "환경 조사·정화·시정조치 의무나 관련 책임이 없다.", "none_exist"),
    spec("RW.INSURANCE.ADEQUACY", 278, "대상회사는 공개목록 예외 외 법률상·업종상 필요한 보험에 모두 가입하였다.", key="insurance_rep"),
    spec("RW.INSURANCE.IN_FORCE", 278, "보험계약과 보험증권은 적법하고 완전한 효력이 있다."),
    spec("RW.INSURANCE.PREMIUMS_PAID", 278, "대상회사는 보험료를 완납하였다."),
    spec("RW.INSURANCE.ADEQUACY", 278, "보험은 사업 수행에 필요한 모든 자산을 보험목적물로 한다."),
    spec("RW.INSURANCE.NO_CANCELLATION_NOTICE", 278, "보험의 해제·해지·취소 사유가 없다.", "none_exist"),
    spec("RW.INSURANCE.NO_COVERAGE_LIMITATION", 278, "보험사고 발생 시 보험금 지급 제한 사유가 없다.", "none_exist"),
    spec("RW.TAX.RETURNS_FILED", 279, "모든 조세 신고·보고를 적법하게 기한 내 이행하였다."),
    spec("RW.TAX.RETURNS_FILED", 279, "조세 신고·보고 내용은 정확하고 완전하다."),
    spec("RW.TAX.PAID", 279, "법률상 납부기한이 도래한 조세를 모두 납부하였다."),
    spec("RW.TAX.WITHHOLDING", 279, "원천징수 대상 세금을 원천징수하여 기한 내 납부하였다."),
    spec("RW.TAX.NO_TAX_SHARING", 279, "제3자 조세를 대신 또는 공동 부담하는 계약이나 의무가 없다.", "none_exist"),
    spec("RW.TAX.NO_TRANSACTION_TAX", 279, "본건 거래로 대상회사에 추가 조세가 발생하지 않는다.", "none_exist"),
    spec("RW.TAX.NO_DISPUTE", 279, "조세 관련 분쟁·심판·소송이 없다.", "none_exist"),
    spec("RW.TAX.NO_AUDIT", 279, "조세 조사·감사·절차나 통지가 없고 제기 우려도 없다.", "none_exist"),
    spec("RW.TAX.BOOKS_RECORDS", 279, "조세 장부·기록과 세금계산서는 적법하고 정확하게 작성·유지되었다."),
    spec("RW.LITIGATION.NO_PENDING", 280, "대상회사 또는 직무관련 임직원에 관한 소송·분쟁이 존재하지 않는다.", "none_exist"),
    spec("RW.LITIGATION.NO_THREATENED", 280, "대상회사 또는 직무관련 임직원에 관한 소송·분쟁의 제기 우려가 없다.", "none_exist"),
    spec("RW.FINANCIAL.BOOKS_RECORDS", 281, "회사 장부·기록·의사록 등은 정확하고 일관되게 작성·유지되어 공식 업무를 반영한다."),
    spec("RW.BROKERS.NO_FEE", 282, "본건 거래 관련 대리인·브로커·투자은행·자문인 등의 수수료 지급의무가 없다.", "none_exist"),
    spec("RW.DISCLOSURE.ACCURACY", 283, "매도인의 진술 및 보장과 제공자료에는 허위 또는 중요한 부정확 기재가 없다.", "none_exist"),
    spec("RW.DISCLOSURE.NO_OMISSION", 283, "진술 및 제공자료에는 오인을 초래할 정보나 중요 사실의 누락이 없다.", "none_exist"),

    # Disclosure schedule — exceptions are indexed with opposite polarity and
    # linked back to the corresponding annex representation.
    spec("RW.CAPITALIZATION.SUBSIDIARIES", 289, "공개목록은 대한라이프보증의 주식수와 대상회사 지분율 및 기타 주주 현황을 기재한다.", source="disclosure_schedule", key="subsidiary_disclosure", related_to="subsidiary_rep"),
    spec("RW.CAPITALIZATION.SUBSIDIARIES", 293, "공개목록은 영등포중앙기업의 주식수와 계열회사 지분율 및 기타 주주 현황을 기재한다.", source="disclosure_schedule", related_to="subsidiary_rep"),
    spec("RW.CORPORATE_GOVERNANCE.APPROVALS", 295, "대상회사는 정기주주총회를 개최하거나 재무제표·임원보수에 관해 주주총회 승인을 받지 않았다.", "negative", source="disclosure_schedule", key="governance_exception", related_to="compliance_rep"),
    spec("RW.PRIVACY.COMPLIANCE", 297, "대상회사는 임직원 개인정보 수집·이용 동의를 받지 않고 퇴직자 개인정보를 파기하지 않았다.", "negative", source="disclosure_schedule", key="privacy_exception", related_to="privacy_rep"),
    spec("RW.PRIVACY.CYBERSECURITY", 297, "대상회사는 개인정보 처리방침·내부관리계획·보호책임자 지정 등 보호조치를 하지 않았다.", "negative", source="disclosure_schedule", related_to="privacy_rep"),
    spec("RW.LABOR.SHARED_PERSONNEL", 299, "대상회사 일부 임직원과 생산직 전원은 강원에너지 업무도 수행한다.", source="disclosure_schedule", key="shared_personnel_exception", related_to="labor_rep"),
    spec("RW.LABOR.NO_VIOLATION", 300, "대상회사는 외국인 근로자 임금체불 대비 보증보험에 가입하지 않았다.", "negative", source="disclosure_schedule", related_to="labor_rep"),
    spec("RW.LABOR.NO_VIOLATION", 300, "외국인 근로자는 법정 상해보험·귀국비용보험에 가입하지 않았다.", "negative", source="disclosure_schedule", related_to="labor_rep"),
    spec("RW.ENVIRONMENT.COMPLIANCE", 302, "대상회사는 공정안전보고서·작업환경측정·안전검사·물질안전보건자료 제출 조치를 이행하지 않았다.", "negative", source="disclosure_schedule", key="environment_exception", related_to="environment_rep"),
    spec("RW.INSURANCE.ADEQUACY", 304, "대상회사는 법률상 요구되는 환경책임보험에 가입하지 않았다.", "negative", source="disclosure_schedule", key="insurance_exception", related_to="insurance_rep"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument(
        "--review-status",
        choices=("pending", "approved", "needs_review", "rejected"),
        default="pending",
        help="Apply the owner's review decision to every generated item",
    )
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if payload["file_key"] != FILE_KEY:
        raise SystemExit(f"expected representative {FILE_KEY}")

    body = {
        int(row["para"]): str(row["text"])
        for row in payload["family_sections"]["RW"]["paragraphs"]
    }
    sources = {
        str(row["source_kind"]): row
        for row in payload["source_inventory"]
        if row["family"] == "RW"
    }
    source_maps = {
        kind: {
            int(row["para"]): str(row["text"])
            for row in source["paragraphs"]
        }
        for kind, source in sources.items()
    }

    items: list[dict] = []
    key_to_ref: dict[str, str] = {}
    pending_related: list[tuple[dict, str]] = []
    for number, row in enumerate(SPECS, start=1):
        item_ref = f"RW-{number:03d}"
        source_kind = row["source"]
        source = None if source_kind == "body" else sources[source_kind]
        paragraphs = body if source_kind == "body" else source_maps[source_kind]
        para = int(row["para"])
        verbatim = paragraphs[para]
        qualifier = {
            "temporal_scope": "계약체결일 및 거래종결일 현재",
        }
        if source_kind == "annex":
            qualifier.update(
                {
                    "subject_scope": "대상회사",
                    "disclosure_schedule_carveout": True,
                }
            )
        elif source_kind == "disclosure_schedule":
            qualifier.update(
                {
                    "disclosure_exception": True,
                    "exception_to_taxonomy_id": row["taxonomy_id"],
                }
            )
        item = {
            "item_ref": item_ref,
            "family": "RW",
            "taxonomy_id": row["taxonomy_id"],
            "proposition": row["proposition"],
            "statement_polarity": row["polarity"],
            "subject_role": row["subject"],
            "counterparty_role": "매수인",
            "action": None,
            "object_type": None,
            "effective_time": "계약체결일 및 거래종결일 현재",
            "source_kind": source_kind,
            "source_id": None if source is None else source["source_id"],
            "source_name": None if source is None else source["source_name"],
            "source_ref": f"¶{para}",
            "parent_clause_ref": "제5.1조" if source_kind == "body" else "제5.1조 제8항",
            "related_item_ref": None,
            "qualifier": qualifier,
            "verbatim": verbatim,
            "loc_start": para,
            "loc_end": para,
            "normalized": {},
            "confidence": "high",
            "review_status": args.review_status,
        }
        items.append(item)
        if row["key"]:
            key_to_ref[row["key"]] = item_ref
        if row["related_to"]:
            pending_related.append((item, row["related_to"]))
    for item, related_key in pending_related:
        item["related_item_ref"] = key_to_ref[related_key]

    source_coverage = [
        {
            "family": row["family"],
            "source_id": row["source_id"],
            "source_kind": row["source_kind"],
            "source_name": row["source_name"],
            "source_ref": row["source_ref"],
            "storage_file_key": row["storage_file_key"],
            "status": "complete",
            "reason": None,
        }
        for row in payload["source_inventory"]
    ]
    coverage = {
        family: {
            "body_status": "complete" if family == "RW" else "not_evaluated",
            "annex_status": "complete" if family == "RW" else "no_annex",
            "reason": (
                "V4-2 대표시험 범위: RW 본문·참조별지·공개목록 전수 검토"
                if family == "RW"
                else "V4-2 RW 원자화 시험 범위 외"
            ),
        }
        for family in ("RW", "CP", "COV", "DEF", "PAY", "REM")
    }
    result = {
        "file_key": FILE_KEY,
        "meta_schema_version": 4,
        "taxonomy_version": int(payload["taxonomy_version"]),
        "extractor_version": "local-reviewed-v4-2-trial-1",
        "prompt_version": "v4-prompt-6",
        "items": items,
        "coverage": coverage,
        "source_coverage": source_coverage,
        "taxonomy_candidates": [],
    }
    args.result_dir.mkdir(parents=True, exist_ok=True)
    path = args.result_dir / f"{FILE_KEY}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "file_key": FILE_KEY,
                "items": len(items),
                "body_items": sum(item["source_kind"] == "body" for item in items),
                "annex_items": sum(item["source_kind"] == "annex" for item in items),
                "disclosure_items": sum(
                    item["source_kind"] == "disclosure_schedule" for item in items
                ),
                "result": str(path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
