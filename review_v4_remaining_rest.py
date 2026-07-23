"""Review the complement of the V4 remaining-half selection.

The first pass selected 652 of 1,303 previously unreviewed principal M&A
agreements.  This script reviews the other 651 agreements with the same
deterministic, local-only paragraph scan and adds a second set of candidate
atomic concepts that are not represented by taxonomy v7.

Keyword hits are candidate evidence only.  Promotion still requires bounded
context review, and this script never calls an external API.
"""

from __future__ import annotations

import argparse
import bisect
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

from review_v4_remaining_half import (
    CANDIDATES as PRIOR_CANDIDATES,
    Candidate,
    legal_evidence_score,
    paragraph_rows,
    read_text,
    reviewed_keys,
)
from review_v4_scope_sample import _project_key


NEW_CANDIDATES = (
    # RW
    Candidate("RW.LABOR.NO_STRIKE", "RW", "RW.LABOR", "파업 없음", "No strike or work stoppage", (
        r"\bno (?:strike|work stoppage|lockout)\b",
        r"\b(?:strike|work stoppage|lockout).{0,50}(?:pending|threatened)\b",
        r"파업.{0,30}(?:없|발생하지|예정)",
        r"쟁의행위.{0,30}(?:없|발생하지|예정)",
    )),
    Candidate("RW.LABOR.NO_UNION_ORGANIZING", "RW", "RW.LABOR", "노동조합 조직화 없음", "No union organizing activity", (
        r"\bunion organi[sz](?:ation|ing).{0,60}(?:no|not|none|pending)\b",
        r"\bno .{0,30}(?:union representation|organizing campaign)\b",
        r"노동조합.{0,40}(?:조직|설립).{0,30}(?:없|진행되지)",
    )),
    Candidate("RW.LABOR.NO_PLANT_CLOSING", "RW", "RW.LABOR", "사업장 폐쇄·대량해고 없음", "No plant closing or mass layoff", (
        r"\bno .{0,40}(?:plant closing|mass layoff)\b",
        r"\b(?:plant closing|mass layoff).{0,50}(?:has not|have not|none)\b",
        r"사업장.{0,20}폐쇄.{0,30}(?:없|하지)",
        r"대량해고.{0,30}(?:없|하지)",
    )),
    Candidate("RW.BENEFITS.NO_WITHDRAWAL_LIABILITY", "RW", "RW.BENEFITS", "다수사용자 연금 인출책임 없음", "No multiemployer withdrawal liability", (
        r"\bwithdrawal liability\b",
        r"\bmultiemployer plan.{0,80}(?:liability|withdraw)\b",
    )),
    Candidate("RW.FINANCIAL.NO_OFF_BALANCE_SHEET", "RW", "RW.FINANCIAL", "부외부채 없음", "No off-balance-sheet arrangement", (
        r"\boff[- ]balance[- ]sheet (?:arrangement|liabilit)\b",
        r"부외부채",
        r"장부외.{0,20}(?:채무|부채|약정)",
    )),
    Candidate("RW.CUSTOMERS_SUPPLIERS.CONCENTRATION", "RW", "RW.CUSTOMERS_SUPPLIERS", "주요 고객·공급자 집중도", "Customer and supplier concentration", (
        r"\b(?:top|largest|major|material) (?:customers?|suppliers?).{0,80}(?:percent|%|revenue|purchases?)\b",
        r"\b(?:customer|supplier) concentration\b",
        r"주요.{0,10}(?:고객|공급업체).{0,60}(?:매출|매입|비율|의존)",
    )),
    Candidate("RW.CUSTOMERS_SUPPLIERS.NO_PRICE_CHANGE", "RW", "RW.CUSTOMERS_SUPPLIERS", "주요 거래처 가격변경 통지 없음", "No customer or supplier price-change notice", (
        r"\b(?:customer|supplier).{0,80}(?:price increase|price decrease|change in price).{0,40}(?:notice|notif)\b",
        r"주요.{0,10}(?:고객|공급업체).{0,60}가격.{0,20}(?:변경|인상|인하).{0,20}통지",
    )),
    Candidate("RW.IT.SYSTEMS_SUFFICIENCY", "RW", "RW", "IT 시스템 충분성", "IT systems sufficiency", (
        r"\bIT systems?.{0,80}(?:sufficient|adequate|operate the business)\b",
        r"\binformation systems?.{0,80}(?:sufficient|adequate|operate the business)\b",
        r"정보시스템.{0,40}(?:충분|적정|사업.{0,10}운영)",
    )),
    Candidate("RW.IT.DISASTER_RECOVERY", "RW", "RW", "IT 재해복구·백업", "IT disaster recovery and backup", (
        r"\bdisaster recovery (?:plan|procedure|system)\b",
        r"\bbusiness continuity (?:plan|procedure)\b",
        r"\bbackup (?:plan|procedure|system).{0,50}(?:IT|data|information)\b",
        r"(?:재해복구|업무연속성).{0,20}(?:계획|절차|시스템)",
    )),
    Candidate("RW.PRODUCTS.COMPLIANCE", "RW", "RW.PRODUCTS", "제품 법규·규격 준수", "Product regulatory compliance", (
        r"\bproducts?.{0,80}(?:comply|compliance).{0,50}(?:law|regulation|standard)\b",
        r"제품.{0,50}(?:법령|규정|규격|표준).{0,30}(?:준수|위반)",
    )),
    Candidate("RW.PRODUCTS.BACKLOG", "RW", "RW.PRODUCTS", "수주잔고 정확성", "Backlog accuracy", (
        r"\bbacklog.{0,80}(?:accurate|cancel|binding|firm order)\b",
        r"수주잔고.{0,30}(?:정확|취소|확정)",
    )),
    Candidate("RW.GOVERNMENT_CONTRACTS.NO_DEBARMENT", "RW", "RW.GOVERNMENT_CONTRACTS", "정부계약 입찰제한 없음", "No suspension or debarment", (
        r"\b(?:suspended|debarred|excluded).{0,80}(?:government contract|government program|procurement)\b",
        r"\bno .{0,30}(?:suspension|debarment).{0,50}(?:government|procurement)\b",
        r"(?:입찰참가자격|정부계약).{0,30}(?:제한|정지|배제).{0,20}(?:없|아니)",
    )),
    Candidate("RW.ENVIRONMENT.NO_UNDERGROUND_STORAGE_TANKS", "RW", "RW.ENVIRONMENT", "지하저장탱크 없음", "No underground storage tanks", (
        r"\bunderground storage tanks?\b",
        r"지하저장탱크",
    )),
    Candidate("RW.TAX.S_CORPORATION", "RW", "RW.TAX", "S corporation 지위", "S corporation status", (
        r"\bS corporation\b",
        r"\bS-corporation\b",
        r"\bsubchapter S\b",
    )),
    Candidate("RW.TAX.NO_PERMANENT_ESTABLISHMENT", "RW", "RW.TAX", "해외 고정사업장 없음", "No permanent establishment", (
        r"\bno permanent establishment\b",
        r"\bpermanent establishment.{0,60}(?:not|none|without)\b",
        r"고정사업장.{0,30}(?:없|보유하지|구성하지)",
    )),
    Candidate("RW.REAL_ESTATE.NO_VIOLATION_NOTICE", "RW", "RW.REAL_ESTATE", "부동산 위반통지 없음", "No real-estate violation notice", (
        r"\bno .{0,30}(?:notice|citation).{0,50}(?:zoning|building code|real property|premises)\b",
        r"\b(?:zoning|building code).{0,50}(?:violation notice|citation)\b",
        r"부동산.{0,40}(?:위반|시정).{0,20}통지.{0,20}(?:없|받지)",
    )),
    # CP
    Candidate("CP.BRINGDOWN_CERTIFICATE", "CP", "CP.CLOSING_CERTIFICATE", "진술보장 확인서", "Representations bring-down certificate", (
        r"\bbring[- ]down certificate\b",
        r"\bofficer'?s certificate.{0,100}(?:representations|warranties).{0,60}(?:true|correct)\b",
        r"진술.{0,10}보장.{0,40}(?:확인서|증명서)",
    )),
    Candidate("CP.SECRETARY_CERTIFICATE", "CP", "CP.CLOSING_CERTIFICATE", "비서·법인서기 증명서", "Secretary certificate", (
        r"\bsecretary'?s certificate\b",
        r"\bcertificate of the secretary\b",
    )),
    Candidate("CP.PAYOFF_LETTER", "CP", "CP.DEBT_RELEASE", "채무상환 확인서", "Payoff letter", (
        r"\bpayoff letters?\b",
        r"\bpay-off letters?\b",
        r"(?:대출|채무).{0,20}(?:상환|변제).{0,20}(?:확인서|증명서)",
    )),
    Candidate("CP.LIEN_RELEASE", "CP", "CP.DEBT_RELEASE", "담보권 해지서류", "Lien release documents", (
        r"\b(?:release|termination|discharge).{0,60}(?:lien|security interest|encumbrance)\b",
        r"\b(?:lien|security interest).{0,60}(?:release|termination|discharge)\b",
        r"(?:담보권|질권|근저당).{0,30}(?:해지|말소|소멸).{0,20}(?:서류|증서|신청)",
    )),
    Candidate("CP.FUNDS_FLOW", "CP", "CP.DELIVERABLE", "자금흐름표", "Funds-flow memorandum", (
        r"\bfunds flow (?:memorandum|statement|schedule)\b",
        r"\bfunds-flow (?:memorandum|statement|schedule)\b",
        r"자금흐름표",
    )),
    Candidate("CP.RWI_BINDER", "CP", "CP.INSURANCE", "진술보장보험 바인더", "RWI binder", (
        r"\bRWI binder\b",
        r"\brepresentation(?:s)? and warrant(?:y|ies) insurance.{0,80}(?:binder|policy)\b",
        r"진술.{0,10}보장.{0,10}보험.{0,30}(?:바인더|증권)",
    )),
    Candidate("CP.EMPLOYMENT_AGREEMENT", "CP", "CP.ANCILLARY", "고용계약 체결", "Employment agreement execution", (
        r"\bexecution.{0,50}(?:employment|retention) agreement\b",
        r"\bdeliver.{0,50}(?:employment|retention) agreement\b",
        r"(?:고용|근로).{0,10}계약.{0,30}(?:체결|교부).{0,20}(?:선행조건|종결)",
    )),
    Candidate("CP.RESTRICTIVE_COVENANT_AGREEMENT", "CP", "CP.ANCILLARY", "경업금지 등 제한약정 체결", "Restrictive covenant agreement execution", (
        r"\bexecution.{0,50}(?:noncompetition|non-competition|restrictive covenant) agreement\b",
        r"\bdeliver.{0,50}(?:noncompetition|non-competition|restrictive covenant) agreement\b",
        r"(?:경업금지|경쟁금지).{0,20}약정.{0,30}(?:체결|교부)",
    )),
    Candidate("CP.NO_LITIGATION", "CP", "CP.NO_PROHIBITION", "거래금지 소송 없음", "No transaction-challenging litigation", (
        r"\bno (?:action|suit|proceeding).{0,100}(?:restrain|enjoin|prohibit).{0,60}(?:transaction|closing|consummation)\b",
        r"(?:거래|종결).{0,30}(?:금지|제한|저지).{0,30}(?:소송|절차).{0,20}(?:없|제기되지)",
    )),
    Candidate("CP.FOREIGN_INVESTMENT_CLEARANCE", "CP", "CP.GOVERNMENT_APPROVAL", "외국인투자·CFIUS 승인", "Foreign-investment clearance", (
        r"\bCFIUS\b",
        r"\bforeign investment (?:approval|clearance|review)\b",
        r"외국인투자.{0,20}(?:승인|신고|허가)",
    )),
    Candidate("CP.MINIMUM_CASH", "CP", "CP", "최소 현금 보유", "Minimum cash condition", (
        r"\bminimum cash\b",
        r"\bcash balance.{0,50}(?:closing condition|condition to closing|at closing)\b",
        r"최소.{0,10}현금.{0,30}(?:선행조건|종결조건|보유)",
    )),
    # COV
    Candidate("COV.EMPLOYEE_BENEFITS_CONTINUATION", "COV", "COV.PERSONNEL", "종업원 보상·복리후생 유지", "Employee compensation and benefits continuation", (
        r"\b(?:employees?|continuing employees?).{0,100}(?:compensation|benefits).{0,100}(?:continue|maintain|no less favorable)\b",
        r"종업원.{0,40}(?:보상|복리후생).{0,40}(?:유지|계속|불리하지)",
    )),
    Candidate("COV.EMPLOYEE_COMMUNICATIONS", "COV", "COV.PERSONNEL", "종업원 커뮤니케이션 사전협의", "Employee communications coordination", (
        r"\b(?:employee|worker) communications?.{0,80}(?:consult|coordinate|approval|consent)\b",
        r"임직원.{0,30}(?:통지|안내|의사소통).{0,30}(?:협의|동의|승인)",
    )),
    Candidate("COV.TAX.RETURNS", "COV", "COV.TAX", "종결 전후 세금신고", "Pre- and post-closing tax returns", (
        r"\bprepare and file.{0,80}tax returns?\b",
        r"\btax returns?.{0,80}(?:prepare|file).{0,80}(?:pre-closing|post-closing|straddle)\b",
        r"세금신고서.{0,30}(?:작성|제출|신고)",
    )),
    Candidate("COV.TAX.AUDIT_CONTROL", "COV", "COV.TAX", "세무조사 대응 통제", "Tax audit control", (
        r"\b(?:control|conduct|defend).{0,80}(?:tax audit|tax contest|tax proceeding)\b",
        r"\b(?:tax audit|tax contest).{0,80}(?:control|conduct|defend)\b",
        r"세무조사.{0,40}(?:대응|방어|주도|통제)",
    )),
    Candidate("COV.TAX.TRANSFER_TAX", "COV", "COV.TAX", "거래세·이전세 부담 및 신고", "Transfer-tax allocation and filing", (
        r"\btransfer taxes?.{0,100}(?:pay|bear|file|return|responsib)\b",
        r"(?:거래세|이전세|등록세|취득세).{0,40}(?:부담|납부|신고)",
    )),
    Candidate("COV.TAX.TAX_SHARING_TERMINATION", "COV", "COV.TAX", "세금분담계약 종료", "Tax-sharing agreement termination", (
        r"\bterminat.{0,60}tax sharing agreement\b",
        r"\btax sharing agreement.{0,60}terminat\b",
        r"세금분담.{0,20}계약.{0,30}(?:종료|해지)",
    )),
    Candidate("COV.ANTITRUST.DIVESTITURE", "COV", "COV.REGULATORY", "경쟁당국 시정조치·자산매각 의무", "Antitrust divestiture commitment", (
        r"\b(?:divest|divestiture|dispose).{0,100}(?:antitrust|competition|regulatory approval)\b",
        r"\b(?:antitrust|competition).{0,100}(?:divest|divestiture|dispose)\b",
        r"기업결합.{0,40}(?:시정조치|자산매각|사업매각)",
    )),
    Candidate("COV.ANTITRUST.HOLD_SEPARATE", "COV", "COV.REGULATORY", "경쟁법상 분리운영 의무", "Antitrust hold-separate commitment", (
        r"\bhold separate\b",
        r"\bholding separate\b",
        r"분리운영.{0,30}(?:의무|명령|조치)",
    )),
    Candidate("COV.EARNOUT.OPERATING_COVENANT", "COV", "COV", "언아웃 기간 사업운영 의무", "Earn-out operating covenant", (
        r"\bearn[- ]?out period.{0,120}(?:operate|conduct|business)\b",
        r"\boperate.{0,100}(?:business).{0,100}earn[- ]?out\b",
        r"언아웃.{0,40}(?:기간|산정기간).{0,80}(?:사업|영업).{0,30}(?:운영|수행)",
    )),
    Candidate("COV.EARNOUT.INFORMATION_RIGHTS", "COV", "COV", "언아웃 정보·보고권", "Earn-out information and reporting rights", (
        r"\bearn[- ]?out.{0,120}(?:books|records|information|report)\b",
        r"\b(?:books|records|information|report).{0,120}earn[- ]?out\b",
        r"언아웃.{0,50}(?:자료|장부|정보|보고).{0,30}(?:제공|열람)",
    )),
    Candidate("COV.SHA.ANTI_DILUTION", "COV", "COV.SHA", "희석방지권", "Anti-dilution right", (
        r"\banti[- ]dilution\b",
        r"\bdilution protection\b",
        r"희석방지",
    )),
    Candidate("COV.SHA.GOOD_BAD_LEAVER", "COV", "COV.SHA", "Good/Bad leaver", "Good-leaver and bad-leaver provisions", (
        r"\bgood leaver\b",
        r"\bbad leaver\b",
        r"good leaver.{0,60}bad leaver",
    )),
    Candidate("COV.SHA.VESTING", "COV", "COV.SHA", "주식 베스팅·리버스 베스팅", "Share vesting and reverse vesting", (
        r"\breverse vesting\b",
        r"\bvesting schedule\b",
        r"\bunvested shares?\b",
        r"주식.{0,20}(?:베스팅|가득)",
    )),
    Candidate("COV.SHA.BUSINESS_PLAN_BUDGET", "COV", "COV.SHA", "사업계획·예산 승인", "Business plan and budget approval", (
        r"\bannual (?:business plan|budget).{0,80}(?:approve|approval|adopt)\b",
        r"\b(?:business plan|budget).{0,80}(?:board|shareholder).{0,40}(?:approve|approval)\b",
        r"(?:사업계획|예산).{0,30}(?:승인|의결)",
    )),
    Candidate("COV.SHA.AFFILIATE_TRANSFER", "COV", "COV.SHA.TRANSFER", "계열회사 허용양도", "Permitted affiliate transfer", (
        r"\bpermitted transfer.{0,80}(?:affiliate|family|trust)\b",
        r"\btransfer.{0,80}(?:affiliate).{0,50}(?:permitted|without consent)\b",
        r"계열회사.{0,30}(?:양도|이전).{0,30}(?:허용|동의 없이)",
    )),
    # DEF / PAY
    Candidate("DEF.WORKING_CAPITAL.NET", "DEF", "DEF.WORKING_CAPITAL", "순운전자본", "Net working capital", (
        r'"Net Working Capital".{0,30}(?:means|shall mean)\b',
        r"\bNet Working Capital means\b",
        r"[\"“]순운전자본[\"”].{0,20}(?:이란|이라 함은|의미)",
    )),
    Candidate("DEF.LEAKAGE.PERMITTED", "DEF", "DEF.LEAKAGE", "허용누출", "Permitted leakage", (
        r'"Permitted Leakage".{0,30}(?:means|shall mean)\b',
        r"\bPermitted Leakage means\b",
        r"[\"“]허용누출[\"”].{0,20}(?:이란|이라 함은|의미)",
    )),
    Candidate("DEF.WILLFUL_BREACH", "DEF", "DEF", "고의적 위반", "Willful breach", (
        r'"Willful Breach".{0,30}(?:means|shall mean)\b',
        r"\bWillful Breach means\b",
        r"[\"“]고의적 위반[\"”].{0,20}(?:이란|이라 함은|의미)",
    )),
    Candidate("DEF.TAXES.TRANSACTION_TAX_DEDUCTION", "DEF", "DEF.TAXES", "거래 조세공제", "Transaction tax deduction", (
        r'"Transaction Tax Deduction".{0,30}(?:means|shall mean)\b',
        r"\bTransaction Tax Deduction means\b",
        r"[\"“]거래조세공제[\"”].{0,20}(?:이란|이라 함은|의미)",
    )),
    Candidate("PAY.HOLDBACK", "PAY", "PAY", "대금 유보", "Purchase-price holdback", (
        r"\bholdback amount\b",
        r"\bpurchase price holdback\b",
        r"\bhold back.{0,60}(?:purchase price|consideration)\b",
        r"(?:매매대금|거래대금).{0,30}(?:유보|보류)",
    )),
    Candidate("PAY.EARNOUT.ACCELERATION", "PAY", "PAY.EARNOUT", "언아웃 가속", "Earn-out acceleration", (
        r"\baccelerat(?:e|ed|ion).{0,50}earn[- ]?out\b",
        r"\bearn[- ]?out.{0,50}accelerat(?:e|ed|ion)\b",
        r"언아웃.{0,30}(?:가속|즉시지급)",
    )),
    Candidate("PAY.EARNOUT.DISPUTE", "PAY", "PAY.EARNOUT", "언아웃 산정 분쟁절차", "Earn-out dispute procedure", (
        r"\bearn[- ]?out.{0,120}(?:dispute|object|independent accountant)\b",
        r"\b(?:dispute|object|independent accountant).{0,120}earn[- ]?out\b",
        r"언아웃.{0,50}(?:이의|분쟁|독립회계사)",
    )),
    Candidate("PAY.COMPLETION_ACCOUNTS.ACCOUNTING_HIERARCHY", "PAY", "PAY.COMPLETION_ACCOUNTS", "정산계정 회계기준 우선순위", "Completion-accounts accounting hierarchy", (
        r"\b(?:closing|completion) accounts?.{0,150}(?:accounting hierarchy|order of precedence|consistent with)\b",
        r"\baccounting principles?.{0,150}(?:closing|completion) accounts?\b",
        r"종결계정.{0,80}(?:회계기준|우선순위|계속성)",
    )),
    Candidate("PAY.PRICE_ADJUSTMENT.COLLAR", "PAY", "PAY.COMPLETION_ACCOUNTS", "가격조정 상·하한", "Price-adjustment collar", (
        r"\b(?:purchase price|price) adjustment.{0,100}(?:shall not exceed|maximum|minimum|cap of|floor of)\b",
        r"\b(?:cap|floor|collar).{0,80}(?:purchase price|price) adjustment\b",
        r"가격조정.{0,40}(?:상한|하한|최대|최소)",
    )),
    # REM
    Candidate("REM.CONSEQUENTIAL.LOST_PROFITS", "REM", "REM.CONSEQUENTIAL", "일실이익 배제", "Lost-profits exclusion", (
        r"\blost profits?\b",
        r"\bloss of profits?\b",
        r"(?:일실이익|상실이익)",
    )),
    Candidate("REM.CONSEQUENTIAL.DIMINUTION_IN_VALUE", "REM", "REM.CONSEQUENTIAL", "가치감소 손해 배제", "Diminution-in-value exclusion", (
        r"\bdiminution in value\b",
        r"\bdiminished value\b",
        r"가치감소.{0,10}손해",
    )),
    Candidate("REM.CONSEQUENTIAL.MULTIPLE_BASED", "REM", "REM.CONSEQUENTIAL", "배수기준 손해 배제", "Multiple-based damages exclusion", (
        r"\bmultiple[- ]based damages?\b",
        r"\bdamages?.{0,50}(?:multiple of earnings|valuation multiple)\b",
        r"(?:배수|멀티플).{0,20}(?:기준|방식).{0,20}손해",
    )),
    Candidate("REM.THIRD_PARTY_CLAIMS.DEFENSE_CONTROL", "REM", "REM.THIRD_PARTY_CLAIMS", "제3자 청구 방어권", "Control of third-party claim defense", (
        r"\b(?:assume|control).{0,80}(?:defense|defence).{0,80}(?:third party claim|third-party claim)\b",
        r"\b(?:third party claim|third-party claim).{0,100}(?:assume|control).{0,60}(?:defense|defence)\b",
        r"제3자.{0,10}청구.{0,50}(?:방어|대응).{0,20}(?:주도|통제|수행)",
    )),
    Candidate("REM.THIRD_PARTY_CLAIMS.SETTLEMENT_CONSENT", "REM", "REM.THIRD_PARTY_CLAIMS", "제3자 청구 합의 동의", "Third-party claim settlement consent", (
        r"\b(?:settle|settlement|compromise).{0,100}(?:third party claim|third-party claim).{0,80}(?:consent|approval)\b",
        r"\b(?:third party claim|third-party claim).{0,120}(?:settle|settlement|compromise).{0,80}(?:consent|approval)\b",
        r"제3자.{0,10}청구.{0,50}(?:합의|화해).{0,30}(?:동의|승인)",
    )),
    Candidate("REM.THIRD_PARTY_CLAIMS.COOPERATION", "REM", "REM.THIRD_PARTY_CLAIMS", "제3자 청구 방어 협조", "Third-party claim defense cooperation", (
        r"\bcooperat.{0,100}(?:defense|defence).{0,80}(?:third party claim|third-party claim)\b",
        r"\b(?:third party claim|third-party claim).{0,120}cooperat\b",
        r"제3자.{0,10}청구.{0,50}(?:방어|대응).{0,30}(?:협조|협력)",
    )),
    Candidate("REM.DIRECT_CLAIMS.NOTICE_CONTENT", "REM", "REM.DIRECT_CLAIMS", "직접청구 통지 기재사항", "Direct-claim notice contents", (
        r"\bdirect claim.{0,100}(?:notice).{0,100}(?:reasonable detail|describe|amount|basis)\b",
        r"\bclaim notice.{0,100}(?:reasonable detail|describe|amount|basis)\b",
        r"직접청구.{0,40}통지.{0,30}(?:내용|근거|금액|상세)",
    )),
    Candidate("REM.EXCLUSIVE_REMEDY.SPECIFIC_PERFORMANCE_CARVEOUT", "REM", "REM.EXCLUSIVE_REMEDY", "특정이행 구제 예외", "Specific-performance carve-out", (
        r"\bexclusive remed(?:y|ies).{0,150}(?:specific performance|equitable relief|injunctive relief)\b",
        r"\bsole remed(?:y|ies).{0,150}(?:specific performance|equitable relief|injunctive relief)\b",
        r"유일.{0,20}구제.{0,80}(?:특정이행|가처분|형평법상 구제).{0,20}(?:제외|예외)",
    )),
    Candidate("REM.EXCLUSIVE_REMEDY.FRAUD_CARVEOUT", "REM", "REM.EXCLUSIVE_REMEDY", "사기 구제 예외", "Fraud carve-out from exclusive remedy", (
        r"\bexclusive remed(?:y|ies).{0,150}\bfraud\b",
        r"\bsole remed(?:y|ies).{0,150}\bfraud\b",
        r"유일.{0,20}구제.{0,80}사기.{0,20}(?:제외|예외)",
    )),
    Candidate("REM.SURVIVAL.STATUTE_OF_LIMITATIONS", "REM", "REM.SURVIVAL", "법정 시효까지 존속", "Survival through statute of limitations", (
        r"\bsurviv.{0,100}(?:statute of limitations|applicable limitation period)\b",
        r"\bstatute of limitations.{0,100}surviv\b",
        r"(?:진술|보장|배상의무).{0,40}(?:소멸시효|제척기간).{0,30}(?:존속|만료)",
    )),
    Candidate("REM.ESCROW_RELEASE", "REM", "REM", "에스크로 해제·분배", "Escrow release mechanics", (
        r"\bescrow (?:fund|amount|property).{0,100}(?:release|distribut)\b",
        r"\b(?:release|distribut).{0,100}escrow (?:fund|amount|property)\b",
        r"에스크로.{0,30}(?:해제|반환|분배|지급)",
    )),
    Candidate("REM.INDEMNITY.TAX", "REM", "REM.INDEMNITY", "조세 손해배상", "Tax indemnity", (
        r"\bindemnif.{0,100}(?:pre-closing taxes|tax liabilities|taxes of)\b",
        r"\b(?:pre-closing taxes|tax liabilities).{0,100}indemnif\b",
        r"(?:종결 전|거래 이전).{0,20}조세.{0,40}(?:손해배상|보상)",
    )),
    Candidate("REM.INDEMNITY.COVENANT_BREACH", "REM", "REM.INDEMNITY", "확약 위반 손해배상", "Covenant-breach indemnity", (
        r"\bindemnif.{0,100}(?:breach|violation).{0,80}(?:covenant|agreement|obligation)\b",
        r"\bbreach of (?:any )?(?:covenant|agreement|obligation).{0,100}indemnif\b",
        r"(?:확약|의무).{0,20}위반.{0,40}(?:손해배상|보상)",
    )),
    Candidate("REM.INDEMNITY.RW_BREACH", "REM", "REM.INDEMNITY", "진술보장 위반 손해배상", "Representation-and-warranty breach indemnity", (
        r"\bindemnif.{0,100}(?:breach|inaccuracy).{0,80}(?:representation|warranty)\b",
        r"\b(?:breach|inaccuracy).{0,80}(?:representation|warranty).{0,100}indemnif\b",
        r"진술.{0,10}보장.{0,20}(?:위반|부정확).{0,40}(?:손해배상|보상)",
    )),
)


ALL_CANDIDATES = PRIOR_CANDIDATES + NEW_CANDIDATES


def select_complement(
    conn: sqlite3.Connection,
    excluded: set[str],
    prior_selected: set[str],
) -> tuple[list[dict], dict]:
    conn.row_factory = sqlite3.Row
    eligible = [
        dict(row)
        for row in conn.execute(
            """
            SELECT f.file_key,f.path,f.txt_path,f.ctype,f.lang,f.is_draft,
                   f.version_hint,f.dup_group,dm.confidence
            FROM files f JOIN doc_meta dm USING(file_key)
            WHERE f.status='ok' AND f.ctype IN ('SPA','SSA','SHA','ATA/BTA')
              AND f.txt_path IS NOT NULL
            ORDER BY f.file_key
            """
        )
        if row["file_key"] not in excluded
    ]
    selected = []
    populations: dict[str, int] = defaultdict(int)
    selected_counts: dict[str, int] = defaultdict(int)
    for row in eligible:
        stratum = f"{row['ctype']}|{row['lang']}"
        populations[stratum] += 1
        if row["file_key"] in prior_selected:
            continue
        row["project_key"] = _project_key(row["path"])
        selected.append(row)
        selected_counts[stratum] += 1
    summary = {
        "eligible_unreviewed_count": len(eligible),
        "prior_selected_count": len(prior_selected & {row["file_key"] for row in eligible}),
        "selected_count": len(selected),
        "selection_fraction": len(selected) / len(eligible) if eligible else 0,
        "population_by_stratum": dict(sorted(populations.items())),
        "selected_by_stratum": dict(sorted(selected_counts.items())),
    }
    return selected, summary


def analyze(selected: list[dict], out: Path) -> tuple[list[dict], list[dict]]:
    # First identify candidate paragraphs with literal tokens.  Only then run
    # expressions containing bounded wildcards.  This avoids pathological
    # backtracking when large extracted paragraphs are scanned by a mega-regex.
    by_id = {candidate.candidate_id: candidate for candidate in ALL_CANDIDATES}
    compiled = {
        candidate.candidate_id: re.compile(
            "|".join(f"(?:{pattern})" for pattern in candidate.patterns),
            re.IGNORECASE,
        )
        for candidate in ALL_CANDIDATES
    }
    candidate_tokens: dict[str, tuple[str, ...]] = {}
    stop_tokens = {
        "the", "and", "any", "all", "not", "none", "without", "with",
        "shall", "means", "mean", "within", "from", "only", "each",
        "this", "that", "have", "has", "been", "being", "agreement",
        "closing", "transaction", "business", "amount", "notice",
        "days", "period", "right", "rights", "claim", "claims",
        "없음", "아니", "하지", "대한", "관련", "경우", "계약",
    }
    for candidate in ALL_CANDIDATES:
        tokens: set[str] = set()
        for pattern in candidate.patterns:
            found = {
                token.casefold()
                for token in re.findall(
                    r"[A-Za-z][A-Za-z-]{2,}|[0-9]{3,}|[가-힣]{2,}",
                    pattern,
                )
            } - stop_tokens
            tokens.update(
                sorted(found, key=lambda token: (-len(token), token))[:3]
            )
        candidate_tokens[candidate.candidate_id] = tuple(
            sorted(tokens, key=lambda token: (-len(token), token))
        )
    evidence: dict[str, list[dict]] = defaultdict(list)
    documents = []
    for row in selected:
        text = read_text(out, row["txt_path"])
        folded = text.casefold()
        line_starts: list[int] = []
        line_paras: list[int | None] = []
        line_values: list[str] = []
        offset = 0
        for line in text.splitlines(keepends=True):
            line_starts.append(offset)
            match = re.match(r"^\[¶(\d+)\]\s*(.*?)(?:\r?\n)?$", line)
            line_paras.append(int(match.group(1)) if match else None)
            line_values.append(match.group(2).strip() if match else "")
            offset += len(line)
        best: dict[str, tuple[int, int, str]] = {}
        for candidate in ALL_CANDIDATES:
            candidate_id = candidate.candidate_id
            tokens = candidate_tokens[candidate_id]
            if tokens and not any(token in folded for token in tokens):
                continue
            for found_match in compiled[candidate_id].finditer(text):
                line_index = bisect.bisect_right(line_starts, found_match.start()) - 1
                if line_index < 0 or line_paras[line_index] is None:
                    continue
                para = int(line_paras[line_index])
                value = line_values[line_index]
                score = legal_evidence_score(candidate.family, value)
                current = best.get(candidate_id)
                found = (score, para, value)
                if current is None or (score, -para) > (current[0], -current[1]):
                    best[candidate_id] = found
        hits = sorted(best)
        for candidate_id, (score, para, value) in best.items():
            candidate = by_id[candidate_id]
            evidence[candidate.candidate_id].append(
                {
                    "file_key": row["file_key"],
                    "para": para,
                    "verbatim": " ".join(value.split())[:700],
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
    candidates = []
    for candidate in ALL_CANDIDATES:
        rows = sorted(
            evidence[candidate.candidate_id],
            key=lambda row: (
                -int(row["legal_score"]),
                {False: 0, None: 1, True: 2}[row["is_draft"]],
                row["file_key"],
            ),
        )
        candidates.append(
            {
                "candidate_id": candidate.candidate_id,
                "candidate_generation": (
                    "prior" if candidate in PRIOR_CANDIDATES else "remaining-rest"
                ),
                "family": candidate.family,
                "recommended_parent_id": candidate.recommended_parent_id,
                "label_ko": candidate.label_ko,
                "label_en": candidate.label_en,
                "document_count": len(rows),
                "evidence": rows[:12],
            }
        )
    return documents, candidates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--prior-review-json", type=Path, required=True)
    parser.add_argument("--exclude-json", type=Path, action="append", default=[])
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()

    prior_review = json.loads(args.prior_review_json.read_text(encoding="utf-8"))
    prior_selected = {
        str(row["file_key"]) for row in prior_review.get("documents", [])
    }
    excluded = reviewed_keys(args.exclude_json)
    with sqlite3.connect(args.out / "catalog.sqlite") as conn:
        all_remaining, selection = select_complement(conn, excluded, prior_selected)
    if args.offset < 0:
        raise SystemExit("--offset must be non-negative")
    stop = None if args.limit is None else args.offset + args.limit
    selected = all_remaining[args.offset:stop]
    batch_counts: dict[str, int] = defaultdict(int)
    for row in selected:
        batch_counts[f"{row['ctype']}|{row['lang']}"] += 1
    selection["remaining_total_count"] = len(all_remaining)
    selection["batch_offset"] = args.offset
    selection["batch_limit"] = args.limit
    selection["batch_selected_count"] = len(selected)
    selection["batch_by_stratum"] = dict(sorted(batch_counts.items()))
    documents, candidates = analyze(selected, args.out)
    payload = {
        "review_version": "v4-remaining-rest-1",
        "excluded_reviewed_count": len(excluded),
        "selection": selection,
        "documents": documents,
        "candidate_count": len(candidates),
        "new_candidate_count": len(NEW_CANDIDATES),
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
                "candidate_count": len(candidates),
                "new_candidate_count": len(NEW_CANDIDATES),
                "candidate_nonzero": sum(row["document_count"] > 0 for row in candidates),
                "new_candidate_nonzero": sum(
                    row["candidate_generation"] == "remaining-rest"
                    and row["document_count"] > 0
                    for row in candidates
                ),
                "json": str(args.json),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
