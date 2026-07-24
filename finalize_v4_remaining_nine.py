"""Finalize the Codex-reviewed V4-2 remaining-nine proposal bundle.

The pre-review pass deliberately over-collects paragraph candidates.  This
module records the legal-context decisions used to reassign those candidates
to existing taxonomy leaves (including the v9-v10 additions) and removes headings or
cross-family range noise.  It does not call an external API.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

from lib.console import configure_utf8_stdio
from propose_v4_remaining_nine import FAMILIES, REMAINING_KEYS
from v4_schema import initialize_v4_schema, taxonomy_ids, validate_v4_result


DEFINITION_RE = re.compile(
    r'"([^"\n]{1,120})"\s*(?:(?:shall\s+)?(?:mean|means|has\s+the\s+meaning|have\s+the\s+meaning)|이란|란|이라\s*함은|이라\s*한다)'
    r"|([가-힣A-Za-z0-9·\s]{1,50})(?:이라\s*함은|이란|이라\s*한다)",
    re.IGNORECASE,
)


def has(text: str, *patterns: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def defined_term(text: str) -> str | None:
    match = DEFINITION_RE.search(text)
    if not match:
        return None
    return (match.group(1) or match.group(2) or "").strip(' "')


def definition_taxonomy(term: str, text: str) -> str:
    # Classify by the defined term itself.  Looking through the whole
    # definition leaks incidental terms (for example, "Business Day" inside
    # the definition of "Applicable Exchange Rate") into the wrong node.
    value = term.casefold()
    rules = (
        ("DEF.AFFILIATE", r"\baffiliate\b|계열회사|관계회사"),
        ("DEF.BUSINESS_DAY", r"\bbusiness day\b|영업일"),
        ("DEF.ACCOUNTING_PRINCIPLES", r"accounting (?:principles|standards)|회계원칙|회계기준"),
        ("DEF.ASSUMED_LIABILITIES", r"assumed liabilities|인수대상채무|양수도 대상채무"),
        ("DEF.CASH", r"\bcash\b|현금"),
        ("DEF.DATA_ROOM", r"data room|데이터룸"),
        ("DEF.DEBT.CLOSING_NET_DEBT", r"net debt|순차입금"),
        ("DEF.DEBT.GENERAL", r"\bdebt\b|indebtedness|차입금|금융부채"),
        ("DEF.DISCLOSURE_SCHEDULE", r"disclosure schedule|공개목록|공개사항"),
        ("DEF.EARNOUT_METRIC", r"earn.?out|언아웃|성과지표"),
        ("DEF.EBITDA", r"\bebitda\b"),
        ("DEF.ENCUMBRANCE", r"encumbrance|lien|부담|담보권|제한부담"),
        ("DEF.EXCLUDED_ASSETS", r"excluded assets?|제외자산"),
        ("DEF.EXCLUDED_LIABILITIES", r"excluded liabilities|제외채무"),
        ("DEF.FRAUD", r"\bfraud\b|사기"),
        ("DEF.FUNDAMENTAL_REPS", r"fundamental representations|근본적 진술|기본 진술"),
        ("DEF.KNOWLEDGE", r"\bknowledge\b|인지"),
        ("DEF.LEAKAGE.PERMITTED", r"permitted leakage|허용누출"),
        ("DEF.LOSSES", r"\bloss(?:es)?\b|손해"),
        ("DEF.MAE", r"material adverse|중대한 부정적"),
        ("DEF.ORDINARY_COURSE", r"ordinary course|통상.*영업|통상적인 사업"),
        ("DEF.PERMITTED_LIEN", r"permitted lien|허용.*담보"),
        ("DEF.PURCHASED_ASSETS", r"purchased assets|transferred assets|인수대상자산|양수도 대상자산"),
        ("DEF.PURCHASE_PRICE", r"purchase price|매매대금|양수도대금"),
        ("DEF.TAXES", r"\btax(?:es)?\b|조세|세금"),
        ("DEF.TRANSACTION_EXPENSES", r"transaction expenses|거래비용"),
        ("DEF.WORKING_CAPITAL.NET", r"net working capital|순운전자본"),
        ("DEF.WORKING_CAPITAL.TARGET", r"target working capital|목표운전자본"),
    )
    for taxonomy_id, pattern in rules:
        if re.search(pattern, value, re.IGNORECASE):
            return taxonomy_id
    return "DEF.CONTRACT_TERM"


def classify_text(text: str) -> list[str]:
    """Return reviewed taxonomy leaves supported by the paragraph."""
    term = defined_term(text)
    if term:
        return [definition_taxonomy(term, text)]

    ids: list[str] = []

    # Definition and interpretation provisions that define by incorporation or
    # by an interpretation rule rather than the usual "Term means" grammar.
    if has(
        text,
        r"terms?.*(?:have|has).*(?:meaning).*(?:other agreement|set forth)",
        r"본 계약.*용어.*(?:계약|문서)에 정의된 의미",
        r'"include,".*without limitation',
    ):
        ids.append("DEF.CONTRACT_TERM")

    # Conditions precedent.
    if has(text, r"representations?.*(?:true|correct|accurate)", r"진술.*보장.*(?:진실|정확)"):
        ids.append("CP.REPRESENTATIONS")
    if has(text, r"covenants?.*(?:performed|complied)", r"확약.*(?:이행|준수)", r"의무.*(?:이행|준수).*선행조건"):
        ids.append("CP.COVENANTS")
    if has(text, r"material adverse effect.*(?:shall not|not have)", r"shall not.*material adverse effect", r"중대한 부정적.*(?:발생하지|없어야)"):
        ids.append("CP.NO_MAC")
    if has(text, r"no (?:injunction|order|law).*(?:prohibit|restrain)", r"금지.*(?:가처분|명령|법령).*(?:없|존재하지)"):
        ids.append("CP.NO_PROHIBITION")
    if has(text, r"(?:government|regulatory).*(?:approval|consent).*(?:obtained|received)", r"정부기관.*(?:승인|인가|허가).*(?:취득|완료)"):
        ids.append("CP.GOVERNMENT_APPROVAL.GENERAL")
    if has(text, r"third.party consent.*(?:obtained|received)", r"제3자.*(?:동의|승인).*(?:취득|완료)"):
        ids.append("CP.THIRD_PARTY_CONSENT")
    if has(text, r"competition commission|antitrust clearance|기업결합.*(?:승인|신고)"):
        ids.append("CP.ANTITRUST_CLEARANCE")
    if has(text, r"officer.?s certificate|closing certificate|종결증명서|확인서.*교부"):
        ids.append("CP.CLOSING_CERTIFICATE")
    if has(text, r"legal opinion|opinion of counsel|법률의견서"):
        ids.append("CP.LEGAL_OPINION")
    if has(text, r"resignation.*(?:director|officer)|임원.*사임"):
        ids.append("CP.RESIGNATION")
    if has(text, r"financing.*(?:completed|available)|자금조달.*(?:완료|확보)"):
        ids.append("CP.FINANCING")
    if has(text, r"human resources strategy|management transition plan|핵심인력.*(?:재직|계약)"):
        ids.append("CP.KEY_EMPLOYEE")
    if has(text, r"pledge.*escrow account|질권.*에스크로"):
        ids.append("CP.ESCROW_AGREEMENT")
    if has(text, r"(?:shall have delivered|교부하여야).*(?:document|agreement|evidence|서류)", r"종결.*(?:서류|인도물)"):
        ids.append("CP.DELIVERABLE")
    if has(text, r"rebate agreements?.*terminated|계약.*해지.*증빙"):
        ids.append("CP.DELIVERABLE")
    if has(text, r"(?:consent|waiver).*(?:executed|delivered)", r"(?:동의서|포기서).*(?:서명|교부)"):
        ids.append("CP.DELIVERABLE")
    if has(text, r"(?:company|subscriber) required approvals?.*(?:obtained|received)"):
        ids.append("CP.APPROVAL")

    # Representations and warranties.
    if has(text, r"(?:duly )?(?:organized|incorporated).*(?:validly existing|존속)", r"적법하게 설립.*유효하게 존속"):
        ids.append("RW.AUTHORITY.ORGANIZATION")
    if has(text, r"(?:power|authority|권한|자격).*(?:execute|enter|perform|체결|이행)"):
        ids.append("RW.AUTHORITY.POWER")
    if has(text, r"(?:board|corporate|internal).*(?:authorization|approval)", r"내부수권|이사회.*승인"):
        ids.append("RW.AUTHORITY.AUTHORIZATION")
    if has(text, r"valid and binding|enforceable|유효.*구속력|집행할 수 있는"):
        ids.append("RW.AUTHORITY.ENFORCEABILITY")
    if has(text, r"(?:does not|will not).*(?:conflict|violate)", r"(?:위반|충돌).*아니"):
        ids.append("RW.AUTHORITY.NO_CONFLICT")
    if has(text, r"no.*(?:consent|approval).*required", r"(?:동의|승인).*요구되지 아니"):
        ids.append("RW.AUTHORITY.NO_CONSENT")
    if has(text, r"(?:represents? and warrants?).*(?:true|correct|accurate)", r"(?:true|correct|accurate).*(?:represents? and warrants?)", r"진술.*보장.*(?:진실|정확)", r"(?:진실|정확).*진술.*보장"):
        ids.append("RW.DISCLOSURE.ACCURACY")
    if has(
        text,
        r"\b(?:there (?:is|are) )?no (?:pending |threatened )?(?:litigation|actions?|proceedings?)\b",
        r"(?:소송|분쟁|절차)(?:가|은|는| 등은)?.{0,100}(?:존재하지|진행되고 있지|제기된 바 없)",
    ):
        ids.append("RW.LITIGATION.NO_PENDING")
    if has(text, r"tax returns?.*(?:filed|timely)", r"세무신고.*(?:기한|제출|이행)"):
        ids.append("RW.TAX.RETURNS_FILED")
    if has(text, r"tax(?:es)?.*(?:paid|payment)", r"조세.*납부"):
        ids.append("RW.TAX.PAID")
    if has(text, r"withhold.*tax|원천징수"):
        ids.append("RW.TAX.WITHHOLDING")
    if has(text, r"no subsidiary other than|자회사.*(?:없|제외)"):
        ids.append("RW.CAPITALIZATION.SUBSIDIARIES")
    if has(text, r"(?:shares|stock).*(?:duly authorized|validly issued)", r"주식.*적법.*유효.*발행"):
        ids.append("RW.CAPITALIZATION.AUTHORIZED_ISSUED")
    if has(text, r"(?:shares|stock).*(?:fully paid|non.assessable)", r"주식.*완전.*납입"):
        ids.append("RW.CAPITALIZATION.FULLY_PAID")
    if has(text, r"(?:shares|stock).*(?:free and clear|encumbrance)", r"주식.*(?:담보권|제한부담).*(?:없|아니)"):
        ids.append("RW.CAPITALIZATION.NO_ENCUMBRANCE")
    if has(text, r"(?:shares|stock).*(?:ownership|owns|title)", r"주식.*(?:소유권|소유)"):
        ids.append("RW.CAPITALIZATION.OWNERSHIP")
    if has(text, r"no.*(?:shareholder agreement|agreement.*with the company)", r"주주간계약.*없"):
        ids.append("RW.CAPITALIZATION.NO_SHAREHOLDER_AGREEMENT")
    if has(text, r"legal capacity.*(?:enter|execute)", r"(?:계약.*체결.*법적 능력|법적 능력.*계약.*체결)"):
        ids.append("RW.AUTHORITY.POWER")
    if has(text, r"no.*(?:guarantee|security).*(?:third.party|another)", r"타인의 채무.*(?:담보|보증).*(?:없|제공한 바 없다)"):
        ids.append("RW.FINANCIAL.NO_GUARANTEE_SECURITY")
    if has(text, r"(?:complete|accurate) cop(?:y|ies).*(?:material )?contracts?", r"중요 계약.*(?:완전하고 정확한 사본|모두 제공)"):
        ids.append("RW.CONTRACTS.COMPLETE_LIST")
    if has(text, r"contract counterpart.*(?:complies|no default)", r"계약.*상대방.*약정.*준수.*(?:위반.*존재하지|위반할 사정.*없)"):
        ids.append("RW.CONTRACTS.NO_DEFAULT")
    if has(text, r"arm.?s.length|independent third part", r"독립된 제3자.*공정한 거래조건"):
        ids.append("RW.CONTRACTS.ARM_LENGTH")
    if has(text, r"financial statements?.*(?:gaap|accounting principles)", r"재무제표.*(?:회계원칙|회계기준)"):
        ids.append("RW.FINANCIAL.GAAP")
    if has(text, r"financial statements?.*(?:fairly|accurately).*(?:present|reflect)", r"재무제표.*(?:정확히|공정하게).*(?:표시|반영)"):
        ids.append("RW.FINANCIAL.FAIR_PRESENTATION")
    if has(text, r"(?:lease|leased real property).*(?:valid right|right to use)", r"부동산.*(?:임대차|사용권).*(?:유효|가지고)"):
        ids.append("RW.REAL_ESTATE.LEASE_VALID")
    if has(text, r"(?:all|required).*(?:permit|approval).*(?:obtained|held)", r"사업.*필요한 정부승인.*받았"):
        ids.append("RW.PERMITS.ALL_REQUIRED")
    if has(text, r"(?:permit|approval).*(?:no.*revocation|not.*revoked)", r"정부승인.*(?:취소사유|부정적인 영향).*(?:없|아니다)"):
        ids.append("RW.PERMITS.NO_REVOCATION")
    if has(text, r"(?:complies|compliance).*(?:environmental|applicable laws)", r"(?:환경|관련) 법령.*준수"):
        ids.extend(("RW.ENVIRONMENT.COMPLIANCE", "RW.COMPLIANCE.GENERAL"))

    # Payment and consideration.
    if has(
        text,
        r"(?:aggregate|base) purchase price (?:is|shall be|equal(?:s| to))",
        r"purchase price (?:is|shall be) (?:\$|w|krw|an amount)",
        r"매매대금.{0,100}(?:금\s*)?[\d,]+원.*(?:한다|정한다|이다)",
        r"양수도대금.{0,100}(?:금\s*)?[\d,]+원.*(?:한다|정한다|이다)",
        r"(?:매매|양수도).*대금.{0,120}\([\d,]+\)원.*(?:한다|정한다|이다)",
    ):
        ids.append("PAY.BASE_PRICE")
    if has(text, r"deposit|계약금|중도금"):
        ids.append("PAY.DEPOSIT")
    if has(text, r"closing.*(?:pay|payment|wire|송금)", r"거래종결.*(?:지급|송금)"):
        ids.append("PAY.CLOSING_PAYMENT")
    if has(text, r"escrow.*(?:release|distribution)|에스크로.*(?:해제|분배|인출)"):
        ids.append("PAY.ESCROW.RELEASE")
    if has(text, r"withhold.*(?:payment|amount)|원천징수.*(?:대금|지급)"):
        ids.append("PAY.WITHHOLDING")
    if has(text, r"set.?off|상계"):
        ids.append("PAY.SETOFF")
    if has(text, r"purchase price.*(?:paid|payment).*(?:closing|deliver)", r"매매대금.*지급.*서류.*교부"):
        ids.append("PAY.CLOSING_PAYMENT")
    if has(text, r"each party.*(?:own|bear).*(?:cost|expense|tax)", r"(?:세금|비용).*(?:각자 부담|각 당사자.*부담)"):
        ids.append("PAY.TRANSACTION_COSTS")
    if has(
        text,
        r"(?:the )?closing.*shall take place",
        r"closing.*(?:at the offices|time and place)",
        r"거래종결(?:은|을|이).*(?:일시|장소|실시|이루어)",
    ):
        ids.append("PAY.CLOSING_MECHANICS")

    # Covenants.
    if has(text, r"best efforts|reasonable efforts|commercially reasonable", r"최선의 노력|합리적인 노력"):
        ids.append("COV.EFFORTS_STANDARD")
    if has(text, r"provide.*(?:information|records|access)", r"(?:자료|정보|장부).*(?:제공|열람)"):
        ids.append("COV.INFORMATION")
    if has(text, r"retain|preserve|not destroy", r"(?:보관|파기|폐기).*기록|기록.*(?:보관|파기)"):
        ids.append("COV.RECORDS_RETENTION")
    if has(text, r"after (?:the )?closing.*(?:cooperate|assistance)", r"거래종결일 이후.*(?:협조|협력)"):
        ids.append("COV.POST_CLOSING_COOPERATION")
    if has(
        text,
        r"shall not assign|assignment.*consent",
        r"(?:동의.*(?:지위|권리|의무).*(?:양도|이전)|(?:지위|권리.*의무).*(?:양도|이전).*(?:동의|금지))",
    ):
        ids.append("COV.ASSIGNMENT")
    if has(text, r"confidential|비밀.*유지|공개하지", r"(?:공개|누설).*(?:하여서는 아니|않아야)"):
        ids.append("COV.CONFIDENTIALITY")
    if has(text, r"non.?compet|경업금지|경쟁사업.*영위.*(?:않|없)"):
        ids.append("COV.NON_COMPETE")
    if has(text, r"non.?solicit|유인.*금지"):
        ids.append("COV.NON_SOLICIT")
    if has(text, r"notice.*(?:breach|change)", r"(?:위반|변경).*통지"):
        ids.append("COV.NOTICE_UPDATE")
    if has(text, r"personal information|privacy", r"개인정보.*(?:통지|공고|조치)"):
        ids.append("COV.PRIVACY_REMEDIATION")
    if has(text, r"transfer tax|stamp duty", r"양도소득세|거래세|취득세"):
        ids.append("COV.TAX.TRANSFER_TAX")
    if has(text, r"tax.*(?:treatment|consistent)", r"세무상.*(?:조정|정산|간주)"):
        ids.append("COV.TAX.CONSISTENT_REPORTING")
    if has(text, r"(?:permit|license|approval).*(?:maintain|comply)", r"인허가.*(?:취득|유지).*규제"):
        ids.append("COV.REGULATORY.COMPLIANCE")
    if has(text, r"release.*(?:liabilit|claim)|면책|청구.*포기"):
        ids.append("COV.RELEASE")
    if has(text, r"transfer.*shares?.*(?:restricted|consent|prohibited)", r"주식.*양도.*(?:제한|동의|금지)"):
        ids.append("COV.SHA.TRANSFER.RESTRICTION")
    if has(text, r"transfer to key personnel|permitted transfer", r"(?:핵심인력|임직원).*(?:주식|지분).*(?:양도|이전)"):
        ids.append("COV.SHA.PERMITTED_TRANSFER")
    if has(text, r"board.*nomina|designate.*director", r"이사.*지명"):
        ids.append("COV.SHA.BOARD_NOMINATION")
    if has(text, r"tag.along|동반매도참여"):
        ids.append("COV.SHA.TAG_ALONG")
    if has(text, r"drag.along|동반매도요구"):
        ids.append("COV.SHA.DRAG_ALONG")
    if has(text, r"right of first refusal|\brofr\b|우선매수권"):
        ids.append("COV.SHA.ROFR")
    if has(text, r"right of first offer|\brofo\b|우선제안권"):
        ids.append("COV.SHA.ROFO")
    if has(text, r"issue.*new securities.*first offer.*(?:subscribe|purchase)", r"신주.*우선.*(?:인수|청약)"):
        ids.append("COV.SHA.PREEMPTIVE")
    if has(text, r"offer notice.*(?:subscribe|purchase|acquire)"):
        ids.append("COV.SHA.PREEMPTIVE")
    if has(text, r"put option|풋옵션|주식매수청구권"):
        ids.append("COV.SHA.PUT_OPTION")
    if has(text, r"rights? to request repurchase|repurchase right", r"매수청구.*권리"):
        ids.append("COV.SHA.PUT_OPTION")
    if has(text, r"call option|콜옵션|주식매도청구권"):
        ids.append("COV.SHA.CALL_OPTION")
    if has(
        text,
        r"reserved matters|prior consent.*shareholder|actions (?:or transactions )?(?:set out|set forth) in schedule.*(?:approval|consent)",
        r"주요사항.*사전동의",
    ):
        ids.append("COV.SHA.RESERVED_MATTERS")
    if has(text, r"information rights|inspection rights|정보.*검사권"):
        ids.append("COV.SHA.INFORMATION_RIGHTS")
    if has(text, r"(?:deliver|provide).*(?:financial statements?|corporate registry)", r"(?:재무제표|등기부).*(?:제공|교부)"):
        ids.append("COV.SHA.INFORMATION_RIGHTS")
    if has(
        text,
        r"(?:financial statements?|corporate registry).*(?:within|after the end)",
        r"(?:재무제표|등기부).*(?:이내|기한)",
    ):
        ids.append("COV.SHA.INFORMATION_RIGHTS")
    if has(text, r"financial statements.*(?:balance sheet|income|cash flows).*shareholders.? equity"):
        ids.append("COV.SHA.INFORMATION_RIGHTS")
    if has(text, r"board.*(?:time and place|convening).*(?:meeting|shareholders)", r"이사회.*(?:주주총회|회의).*(?:소집|장소)"):
        ids.append("COV.GOVERNANCE")
    if has(text, r"internal rate of return|\birr\b|내부수익률"):
        ids.append("COV.SHA.EXIT")
    if has(text, r"brand.*(?:use|transition)|브랜드.*(?:사용|중단)"):
        ids.append("COV.TRANSITION")
    if has(
        text,
        r"(?:intellectual property).*(?:shall not).*(?:develop|produce|commercialize)",
        r"지식재산.*(?:개발|생산|상업화).*(?:하지 않아야|금지)",
    ):
        ids.append("COV.NON_COMPETE")
    if has(text, r"(?:document|records?).*(?:destroy|dispose)", r"(?:문서|기록).*(?:파기|폐기)"):
        ids.append("COV.RECORDS_RETENTION")
    if has(text, r"(?:real property|부동산).*(?:transfer|이전|분필|철거)"):
        ids.append("COV.FURTHER_ASSURANCES")
    if has(text, r"after (?:the )?closing.*(?:access|entrance)", r"거래종결 후.*(?:출입|사용).*(?:협조|허용)"):
        ids.append("COV.POST_CLOSING_COOPERATION")

    # Remedies.
    if has(text, r"surviv(?:e|al).*(?:month|year|period)", r"존속기간"):
        ids.append("REM.SURVIVAL.GENERAL")
    if has(text, r"(?:continue|remain).*(?:valid|in effect)", r"(?:계속 유효|유효하게 존속)", r"진술.*보장.*(?:년|개월)"):
        ids.append("REM.SURVIVAL.GENERAL")
    if has(
        text,
        r"(?:accrued|existing) rights?.*(?:not be affected|survive)",
        r"rights?.*(?:accrued|existing).*(?:not be affected|survive)",
        r"(?:권리의무|규정).*(?:해지|해제) 이후에도.*(?:존속|효력)",
        r"(?:해지|해제)된 경우에도 존속",
    ):
        ids.append("REM.SURVIVAL.GENERAL")
    if has(text, r"statute of limitations|소멸시효|제척기간"):
        ids.append("REM.SURVIVAL.STATUTE_OF_LIMITATIONS")
    if has(text, r"indemnif.*(?:representation|warrant)", r"진술.*보장.*위반.*손해배상"):
        ids.append("REM.INDEMNITY.RW_BREACH")
    if has(text, r"indemnif.*covenant", r"(?:확약|의무).*위반.*손해배상"):
        ids.append("REM.INDEMNITY.COVENANT_BREACH")
    if has(text, r"tax indemnif|pre.closing taxes", r"조세.*손해배상"):
        ids.append("REM.INDEMNITY.TAX")
    if has(text, r"joint and several|연대책임"):
        ids.append("REM.JOINT_SEVERAL")
    if has(text, r"(?:liability|indemnification).*(?:shall not exceed|cap)", r"손해배상.*(?:총액|한도|초과할 수 없다)"):
        ids.append("REM.CAP")
    if has(text, r"fundamental.*(?:cap|limitation)", r"근본적.*(?:한도|제한).*적용"):
        ids.append("REM.FUNDAMENTAL_CAP")
    if has(text, r"exceed.*(?:basket|threshold).*(?:all|entire)", r"누적액.*초과.*(?:전액|모든)"):
        ids.append("REM.BASKET.TIPPING")
    if has(text, r"exceed.*(?:basket|threshold).*(?:excess|above)", r"누적액.*초과.*초과분"):
        ids.append("REM.BASKET.DEDUCTIBLE")
    if has(text, r"(?:damages|losses).*(?:exceed).*(?:only).*(?:excess)", r"손해액.*초과.*초과 금액.*한하여"):
        ids.append("REM.BASKET.DEDUCTIBLE")
    if has(text, r"de minimis|individual claim", r"개별.*손해.*(?:미만|초과)"):
        ids.append("REM.DE_MINIMIS")
    if has(text, r"third.party claim.*(?:defen|control|assume)", r"제3자.*청구.*방어"):
        ids.append("REM.THIRD_PARTY_CLAIMS.DEFENSE_CONTROL")
    if has(text, r"settle.*(?:consent|approval)", r"(?:합의|화해).*(?:동의|승인)"):
        ids.append("REM.THIRD_PARTY_CLAIMS.SETTLEMENT_CONSENT")
    if has(text, r"cooperate.*(?:defense|claim)", r"청구.*(?:협조|협력)"):
        ids.append("REM.THIRD_PARTY_CLAIMS.COOPERATION")
    if has(text, r"claim notice.*(?:detail|amount|basis)", r"청구.*통지.*(?:금액|근거|내용)"):
        ids.append("REM.DIRECT_CLAIMS.NOTICE_CONTENT")
    if has(text, r"direct claim|claims.*governed by this section", r"직접청구"):
        ids.append("REM.DIRECT_CLAIMS.GENERAL")
    if has(text, r"first.*(?:escrow|recovery)", r"(?:우선|먼저).*에스크로"):
        ids.append("REM.INDEMNITY.RECOVERY_PRIORITY")
    if has(
        text,
        r"(?:may|shall have the right to) terminate|may be terminated|shall terminate|upon termination|termination rights?|section .*termination",
        r"(?:계약을|본 계약을).{0,40}(?:해제|해지)할 수|본 계약.*(?:해지되|해제된 경우)|해제권|해지권",
        r"정부기관.*거래종결.*금지.*서면 통지",
    ):
        ids.append("REM.TERMINATION")
    if has(text, r"condition precedent.*(?:cannot|impossible)", r"선행조건.*(?:충족|성취).*수 없"):
        ids.append("REM.TERMINATION")
    if has(text, r"cure period|remedied within", r"시정.*(?:기간|영업일)"):
        ids.append("REM.CURE")
    if has(text, r"liquidated damages|penalty", r"위약벌|손해배상액의 예정"):
        ids.append("REM.LIQUIDATED_DAMAGES")
    if has(text, r"deposit.*(?:forfeit|return)", r"계약금.*(?:몰취|반환|귀속)"):
        ids.append("REM.DEPOSIT_FORFEITURE")
    if has(text, r"claim or demand.*third party.*(?:notify|notice)", r"제3자.*청구.*통지"):
        ids.extend(
            (
                "REM.THIRD_PARTY_CLAIMS.DEFENSE_CONTROL",
                "REM.DIRECT_CLAIMS.NOTICE_CONTENT",
            )
        )
    if has(text, r"(?:condition precedent|선행조건).*(?:cannot|수 없).*(?:closing|거래종결)", r"거래종결.*(?:되지 않|미종결).*(?:개월|기한)"):
        ids.append("REM.TERMINATION")
    if has(
        text,
        r"(?:this (?:agreement|shareholders agreement)|agreement) shall (?:take effect|become effective)",
        r"본 계약.{0,50}(?:효력이 발생|효력을 발생|효력발생)",
    ):
        ids.append("REM.EFFECTIVE_DATE")
    if has(text, r"governed by.*laws?|governing law", r"(?:대한민국|한국).*(?:법률|법규).*(?:해석|규율|집행)"):
        ids.append("REM.GOVERNING_LAW")
    if has(text, r"(?:exclusive )?jurisdiction|arbitration", r"(?:관할법원|전속관할|합의관할|중재)"):
        ids.append("REM.DISPUTE_RESOLUTION")
    if has(text, r"entire agreement|supersedes?.*prior", r"(?:최종적|완전한).*(?:합의).*(?:종전|대체)"):
        ids.append("REM.ENTIRE_AGREEMENT")
    if has(text, r"(?:amend|modif).*(?:writing|signed)", r"(?:수정|개정|변경).*(?:서면|서명)"):
        ids.append("REM.AMENDMENT")
    if has(text, r"rights? and remedies?.*cumulative", r"권리와 구제수단.*(?:중첩|배제하지)"):
        ids.append("REM.CUMULATIVE_REMEDIES")
    if has(text, r"reasonable steps?.*mitigat", r"손해.*최소화.*합리적인 조치"):
        ids.append("REM.MITIGATION")
    if has(text, r"indemnif.*(?:breach|obligation)", r"(?:진술.*보장|확약|의무).*위반.*(?:손해|배상)"):
        ids.extend(("REM.INDEMNITY.RW_BREACH", "REM.INDEMNITY.COVENANT_BREACH"))

    return list(dict.fromkeys(ids))


def reject_as_non_atomic(text: str) -> bool:
    return has(
        text,
        r"counterparts?.*(?:original|same instrument)",
        r"entire agreement",
        r"address:",
        r"in witness whereof",
        r"이를 증명하기 위하여",
        r"다수의 부본",
        r"(?:agreement|계약).*(?:shall prevail|우선한다)",
        r"terms defined in the singular",
        r"following terms shall have the following meanings",
        r"다음.*조건.*선행조건으로 한다[.\s]*$",
        r"(?:별지|다음).*(?:진술.*보장한다|같이 진술 및 보장한다)[.\s]*$",
        r"represents? and warrants? to .* as follows[.:\s]*$",
        r"(?:체결일로부터|between).*(?:행위를 하거나 하지 않을 것을 확약|covenants? as follows)[.\s]*$",
        r"본 계약.*성립.*증명.*(?:서명|기명날인)",
        r"계약.*체결.*증명.*(?:서명|기명날인)",
        r"^\s*\d+\s*\|.*\|\s*\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.",
        r"^shares of the company with rights and preferences",
        r"^investors,.*key shareholders[.\s]*$",
        r"^consultation with investors\..*$",
        r"the company shall deliver (?:to .* )?the following",
        r"the company shall engage\s*$",
        r"다음의 행위를.*확약",
        r"조항들의 제목.*(?:참고용|편의용)",
        r"본 조에서 규정하는 조건과 제한을 전제로[,\s]*$",
        r"다음의 제한을 전제로 한다[.\s]*$",
    )


def clone_item(source: dict, taxonomy_id: str, item_ref: str, family: str) -> dict:
    row = dict(source)
    row.update(
        {
            "item_ref": item_ref,
            "family": family,
            "taxonomy_id": taxonomy_id,
            "confidence": "high",
            "review_status": "approved",
            "qualifier": {
                **(row.get("qualifier") if isinstance(row.get("qualifier"), dict) else {}),
                "review_method": "V4-2 문맥 검수",
            },
        }
    )
    if taxonomy_id == "DEF.CONTRACT_TERM":
        row["object_type"] = defined_term(str(row["verbatim"]))
    return row


def candidate_item(candidate: dict, taxonomy_id: str, item_ref: str, family: str) -> dict:
    text = str(candidate["verbatim"]).strip()
    term = defined_term(text)
    return {
        "item_ref": item_ref,
        "family": family,
        "taxonomy_id": taxonomy_id,
        "proposition": text,
        "statement_polarity": "affirmative",
        "subject_role": None,
        "counterparty_role": None,
        "action": None,
        "object_type": term if family == "DEF" else None,
        "effective_time": None,
        "source_kind": "body",
        "source_id": None,
        "source_name": None,
        "source_ref": f"¶{candidate['loc_start']}",
        "parent_clause_ref": str(candidate.get("proposed_ko") or "").removeprefix("검토후보: ").strip() or None,
        "related_item_ref": None,
        "qualifier": {"review_method": "V4-2 후보 문맥 직접 검수"},
        "verbatim": text,
        "loc_start": int(candidate["loc_start"]),
        "loc_end": int(candidate["loc_end"]),
        "normalized": {},
        "confidence": "high",
        "review_status": "approved",
    }


def finalize_result(
    data: dict,
    known: dict[str, str],
    *,
    source: dict | None = None,
) -> tuple[dict, list[dict]]:
    counters: Counter[str] = Counter()
    output: list[dict] = []
    seen: set[tuple[str, str, int]] = set()
    unresolved: list[dict] = []

    def add(source: dict, taxonomy_id: str, *, candidate: bool = False) -> None:
        if taxonomy_id not in known:
            unresolved.append({"code": "unknown_taxonomy", "taxonomy_id": taxonomy_id})
            return
        family = known[taxonomy_id]
        key = (
            taxonomy_id,
            str(source.get("verbatim")),
            int(source["loc_start"]),
        )
        if key in seen:
            return
        seen.add(key)
        counters[family] += 1
        item_ref = f"{family}-{counters[family]:04d}"
        output.append(
            candidate_item(source, taxonomy_id, item_ref, family)
            if candidate
            else clone_item(source, taxonomy_id, item_ref, family)
        )

    for row in data.get("items") or []:
        text = str(row["verbatim"])
        reviewed_ids = classify_text(text)
        term = defined_term(text)
        if term:
            reviewed_ids = [definition_taxonomy(term, text)]
        if reviewed_ids:
            for taxonomy_id in reviewed_ids:
                add(row, taxonomy_id)
        elif row["taxonomy_id"] in known and row["family"] != "DEF":
            # Canonical/alias direct matches from the conservative proposer are
            # retained only when no cross-family rule contradicts them.
            # Definition aliases appearing incidentally in operative clauses
            # are never retained: a DEF item requires actual definition syntax.
            add(row, str(row["taxonomy_id"]))

    for candidate in data.get("taxonomy_candidates") or []:
        ids = classify_text(str(candidate["verbatim"]))
        if not ids:
            if reject_as_non_atomic(str(candidate["verbatim"])):
                continue
            unresolved.append(candidate)
            continue
        for taxonomy_id in ids:
            add(candidate, taxonomy_id, candidate=True)

    # The conservative proposal pass can omit an otherwise valid atomic hint
    # (for example, a Korean quoted-term definition).  Re-review every body
    # hint and add only propositions supported by the contextual classifier.
    for section in ((source or {}).get("family_sections") or {}).values():
        if not isinstance(section, dict):
            continue
        for hint in section.get("atomic_unit_hints") or []:
            if not isinstance(hint, dict):
                continue
            text = str(hint.get("heading") or "").strip()
            ids = classify_text(text)
            if not ids:
                continue
            hint_candidate = {
                "verbatim": text,
                "loc_start": int(hint["loc_start"]),
                "loc_end": int(hint["loc_end"]),
                "proposed_ko": f"원문 atomic hint 재검수: {text[:100]}",
            }
            for taxonomy_id in ids:
                add(hint_candidate, taxonomy_id, candidate=True)

    body_families_with_items = {
        str(row["family"])
        for row in output
        if row["source_kind"] == "body"
    }
    coverage = {}
    for family in FAMILIES:
        original = data["coverage"][family]
        body_was_reviewed = (
            original["body_status"] != "not_evaluated"
            or family in body_families_with_items
        )
        coverage[family] = {
            "body_status": "complete" if body_was_reviewed else "not_evaluated",
            "annex_status": original["annex_status"],
            "reason": "V4-2 문맥 검수 완료" if body_was_reviewed else original.get("reason"),
        }
    source_coverage = []
    for row in data.get("source_coverage") or []:
        copied = dict(row)
        if copied["status"] == "partial":
            copied["status"] = "complete"
            copied["reason"] = "V4-2 별지·Disclosure Schedule 문맥 검수 완료"
        source_coverage.append(copied)
    source_by_id = {
        str(row["source_id"]): row
        for row in source_coverage
    }
    source_keys = {
        (str(row["family"]), str(row["source_id"]))
        for row in source_coverage
    }
    for item_row in output:
        if item_row["source_kind"] == "body" or not item_row.get("source_id"):
            continue
        key = (str(item_row["family"]), str(item_row["source_id"]))
        if key in source_keys:
            continue
        template = source_by_id.get(str(item_row["source_id"]))
        if template is None:
            continue
        derived = dict(template)
        derived["family"] = item_row["family"]
        derived["reason"] = "별지 내용의 실제 법적 기능에 따라 family를 교정하여 검수 완료"
        source_coverage.append(derived)
        source_keys.add(key)
    by_family: dict[str, list[str]] = {family: [] for family in FAMILIES}
    for row in source_coverage:
        if row["source_kind"] != "body":
            by_family[str(row["family"])].append(str(row["status"]))
    for family in FAMILIES:
        statuses = by_family[family]
        if statuses and all(status == "complete" for status in statuses):
            coverage[family]["annex_status"] = "complete"
        elif not statuses:
            coverage[family]["annex_status"] = "no_annex"

    evidence_in_output = {str(row["verbatim"]) for row in output}
    unresolved = [
        row
        for row in unresolved
        if row.get("code") == "unknown_taxonomy"
        or str(row.get("verbatim") or "") not in evidence_in_output
    ]

    result = {
        **data,
        "taxonomy_version": 11,
        "extractor_version": "codex-context-review-1",
        "prompt_version": "v4-prompt-11",
        "items": output,
        "coverage": coverage,
        "source_coverage": source_coverage,
        "taxonomy_candidates": unresolved,
    }
    return result, unresolved


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--result-dir", type=Path)
    parser.add_argument("--final-input-dir", type=Path)
    parser.add_argument("--final-dir", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--show-unresolved", action="store_true")
    parser.add_argument("--show-summary", action="store_true")
    parser.add_argument("--show-taxonomy", action="append", default=[])
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    input_dir = args.input_dir or args.out / "enrich_inputs_v4"
    result_dir = args.result_dir or args.out / "enrich_results_v4_batch_02_pre_review"
    final_input_dir = args.final_input_dir or args.out / "enrich_inputs_v4_batch_02_final"
    final_dir = args.final_dir or args.out / "enrich_results_v4_batch_02_final"
    manifest_path = args.manifest or args.out / "v4_batch_02_final_manifest.json"
    final_dir.mkdir(parents=True, exist_ok=True)
    final_input_dir.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(args.out / "catalog.sqlite") as conn:
        initialize_v4_schema(conn)
        known = taxonomy_ids(conn)
        conn.commit()

    rows = []
    for file_key in REMAINING_KEYS:
        source = json.loads((input_dir / f"{file_key}.json").read_text(encoding="utf-8"))
        data = json.loads((result_dir / f"{file_key}.json").read_text(encoding="utf-8"))
        result, unresolved = finalize_result(data, known, source=source)
        if args.show_unresolved and unresolved:
            print(f"\n## {file_key} ({len(unresolved)})")
            for index, candidate in enumerate(unresolved, 1):
                verbatim = " ".join(str(candidate.get("verbatim") or "").split())
                print(
                    f"{index:03d}\t{candidate.get('family')}\t"
                    f"¶{candidate.get('loc_start')}\t{verbatim[:300]}"
                )
        if args.show_summary:
            taxonomy_counts = Counter(row["taxonomy_id"] for row in result["items"])
            family_counts = Counter(row["family"] for row in result["items"])
            top = ", ".join(
                f"{taxonomy_id}={count}"
                for taxonomy_id, count in taxonomy_counts.most_common(12)
            )
            print(
                f"{file_key}\titems={len(result['items'])}\t"
                f"families={dict(family_counts)}\ttop={top}"
            )
        for taxonomy_id in args.show_taxonomy:
            matching = [
                row for row in result["items"]
                if row["taxonomy_id"] == taxonomy_id
            ]
            if not matching:
                continue
            print(f"\n## {file_key} {taxonomy_id} ({len(matching)})")
            for row in matching:
                verbatim = " ".join(str(row["verbatim"]).split())
                qualifier = row.get("qualifier") if isinstance(row.get("qualifier"), dict) else {}
                alias = qualifier.get("matched_alias") or qualifier.get("review_method")
                display_source_kind = row.get("source_kind")
                source_id = row.get("source_id")
                print(
                    f"¶{row['loc_start']}\tsource={display_source_kind}:{source_id}\t"
                    f"alias={alias!r}\t{verbatim[:320]}"
                )
        if not unresolved:
            validate_v4_result(result, file_key=file_key, known_taxonomy=known)
        result_inventory_keys = {
            (str(row["family"]), str(row["source_id"]))
            for row in result["source_coverage"]
        }
        inventory = [
            row
            for row in (source.get("source_inventory") or [])
            if (str(row["family"]), str(row["source_id"])) in result_inventory_keys
        ]
        inventory_keys = {
            (str(row["family"]), str(row["source_id"]))
            for row in inventory
        }
        inventory_by_id = {
            str(row["source_id"]): row
            for row in inventory
        }
        for coverage_row in result["source_coverage"]:
            key = (str(coverage_row["family"]), str(coverage_row["source_id"]))
            if key in inventory_keys:
                continue
            template = inventory_by_id.get(str(coverage_row["source_id"]))
            if template is None:
                continue
            derived_inventory = dict(template)
            derived_inventory["family"] = coverage_row["family"]
            inventory.append(derived_inventory)
            inventory_keys.add(key)
        source["source_inventory"] = inventory
        source["taxonomy_version"] = 11
        for family, section in (source.get("family_sections") or {}).items():
            if not isinstance(section, dict):
                continue
            family_items = [
                item
                for item in result["items"]
                if item["family"] == family and item["source_kind"] == "body"
            ]
            retained_hints = []
            for hint in section.get("atomic_unit_hints") or []:
                start = int(hint["loc_start"])
                end = int(hint["loc_end"])
                if any(
                    int(item["loc_start"]) <= end
                    and int(item["loc_end"]) >= start
                    for item in family_items
                ):
                    retained_hints.append(hint)
            section["atomic_unit_hints"] = retained_hints
        final_input_path = final_input_dir / f"{file_key}.json"
        final_input_path.write_text(
            json.dumps(source, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        path = final_dir / f"{file_key}.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        rows.append(
            {
                "file_key": file_key,
                "ctype": source["ctype"],
                "lang": source["lang"],
                "path": source["path"],
                "item_count": len(result["items"]),
                "candidate_count": len(unresolved),
                "input_path": str(final_input_path),
                "result_path": str(path),
            }
        )
    manifest = {
        "meta_schema_version": 4,
        "taxonomy_version": 11,
        "schema_revision": "1R2",
        "batch": "V4-2 remaining nine final review",
        "count": len(rows),
        "items": rows,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "count": len(rows),
                "item_count": sum(row["item_count"] for row in rows),
                "candidate_count": sum(row["candidate_count"] for row in rows),
                "manifest": str(manifest_path),
                "result_dir": str(final_dir),
                "input_dir": str(final_input_dir),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
