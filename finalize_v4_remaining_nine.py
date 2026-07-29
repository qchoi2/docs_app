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
from lib.v4_candidate_policy import candidate_name, strip_candidate_prefix
from propose_v4_remaining_nine import FAMILIES, REMAINING_KEYS, substantive
from v4_schema import initialize_v4_schema, taxonomy_ids, validate_v4_result


DEFINITION_RE = re.compile(
    r'"([^"\n]{1,120})"\s*(?:(?:shall\s+)?(?:mean|means|has\s+the\s+meaning|have\s+the\s+meaning)|이란|란|(?:이)?라\s*함은|이라\s*한다)'
    r"|([가-힣A-Za-z0-9·\s]{1,50})(?:(?:이)?라\s*함은|이란|이라\s*한다)",
    re.IGNORECASE,
)


def has(text: str, *patterns: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def defined_term(text: str) -> str | None:
    match = DEFINITION_RE.search(text)
    if match:
        return (match.group(1) or match.group(2) or "").strip(' "')
    # Korean drafting usually places the topic marker after the quoted term
    # and the definitional verb at the end of the sentence:
    #   "영업일"은 ... 날을 의미한다.
    quoted = re.match(r'^\s*"([^"\n]{1,120})"\s*(?:은|는|이란|란)', text)
    if quoted and re.search(
        r"(?:의미한다|뜻한다|말한다|정의한다|의미를\s+가진다)",
        text,
    ):
        return quoted.group(1).strip()
    return None


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
        r"본 계약.*(?:용어|다음의 용어).*(?:별지|아래).*(?:정한|규정된)\s*의미",
        r"unless otherwise defined.*following terms.*(?:meanings?|ascribed)",
        r'"include,".*without limitation',
        r"\binclude\b.*\bincluding\b.*without limitation",
        r"singular noun.*plural|singular.*include.*plural",
        r"references? to this agreement.*(?:amended|modified|supplemented)",
    ):
        ids.append("DEF.CONTRACT_TERM")

    # Conditions precedent.
    if has(text, r"representations?.*(?:true|correct|accurate)", r"진술.*보장.*(?:진실|정확)"):
        ids.append("CP.REPRESENTATIONS")
    if has(text, r"covenants?.*(?:performed|complied)", r"확약.*(?:이행|준수)", r"의무.*(?:이행|준수).*선행조건"):
        ids.append("CP.COVENANTS")
    if has(
        text,
        r"material adverse effect.*(?:shall not|not have|has not)",
        r"shall not.*material adverse effect",
        r"중대(?:하게|한)\s*부정적(?:인)?\s*영향.*(?:발생하지|발견되지|없어야|없을)",
    ):
        ids.append("CP.NO_MAC")
    if has(
        text,
        r"no (?:injunction|order|law).*(?:prohibit|restrain)",
        r"(?:법령|명령|판결|가처분|금지령).*(?:거래|종결).*(?:금지|제한|방해).*(?:없|아니)",
        r"(?:거래|종결).*(?:금지|제한|방해).*(?:법령|명령|판결|가처분|금지령).*(?:없|아니)",
    ):
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
    if has(
        text,
        r"(?:organizational documents?|board|shareholders?).*(?:approval|resolution).*(?:completed|obtained)",
        r"(?:조직문서|이사회|주주총회).*(?:결의|승인|절차).*(?:완료|이행)",
    ):
        ids.append("CP.APPROVAL")
    if has(
        text,
        r"(?:condition precedent|condition to (?:closing|completion)).*(?:waiv|waiver)",
        r"(?:waiv|waiver).*(?:condition precedent|condition to (?:closing|completion))",
        r"선행조건.*면제",
        r"(?:면제|포기).*(?:선행조건|조건)",
    ):
        ids.append("CP.WAIVER")
    if has(
        text,
        r"(?:may|must|shall)\s+not\s+rely\s+on.*failure.*condition",
        r"failure.*condition.*caused by.*(?:breach|failure)",
        r"선행조건.*(?:충족|성취).*(?:방해|귀책).*(?:원용|주장).*(?:못|아니)",
        r"자신의 의무불이행.*(?:종결|거래종결).*(?:거부|주장).*(?:수 없다|못)",
    ):
        ids.append("CP.SELF_CAUSED_FAILURE")
    if has(
        text,
        r"(?:governmental|required) approvals?.*(?:obtained|completed)",
        r"필요적 (?:정부)?승인.*(?:완료|취득)|(?:정부승인|필요적 승인).*(?:받거나|완료)",
        r"(?:필요적 )?(?:인허가|정부 인허가).*(?:취득|이행|완료)",
    ):
        ids.append("CP.GOVERNMENT_APPROVAL.GENERAL")
    if has(
        text,
        r"(?:acquisition|buyer) fund.*(?:formed|established).*(?:exist|subsist)",
        r"매수펀드.*(?:설립|존속)",
    ):
        ids.append("CP.FINANCING")
    if has(
        text,
        r"(?:ancillary|related).*(?:agreement|transaction).*(?:executed|closed|completion)",
        r"(?:소수지분|다수지분|연계|관련).*(?:매매계약|거래).*(?:체결|종결)",
        r"(?:share purchase agreement|investment agreement).*(?:executed|closed)",
        r"기존 투자자.*(?:동시에|전부).*(?:종결|완료)",
        r"(?:주식매매계약|지분인수계약|연계거래).{0,120}(?:동시에|이전).{0,80}(?:종결|완료)",
    ):
        ids.append("CP.ANCILLARY.TRANSACTION_CLOSING")
    if has(
        text,
        r"(?:all sellers?|all of the shares).*(?:simultaneously|all).*(?:close|closing|completion)",
        r"(?:모든 매도인|대상주식 전부).*(?:동시에|전부).*(?:종결|완료)",
    ):
        ids.append("CP.ALL_OR_NOTHING_CLOSING")
    if has(
        text,
        r"purchase price adjustment.*(?:completed|final)",
        r"매매대금 조정.*(?:완료|최종|확정)|최종 매매대금.*확정",
    ):
        ids.append("CP.PURCHASE_PRICE_ADJUSTMENT")
    if has(
        text,
        r"(?:buyer|purchaser).*(?:nominee|designat).*(?:director|officer).*(?:appointed|elected)",
        r"매수인.*지명.*(?:이사|감사|임원).*(?:선임|취임)",
    ):
        ids.append("CP.MANAGEMENT_APPOINTMENT")
    if has(
        text,
        r"(?:representation|warranty).{0,20}insurance.*(?:effective|in effect|bound)",
        r"진술보장\s*보험.*(?:체결|발효|효력)",
    ):
        ids.append("CP.RWI_POLICY_EFFECTIVE")

    # Representations and warranties.
    if has(text, r"(?:duly )?(?:organized|incorporated).*(?:validly existing|존속)", r"적법하게 설립.*유효하게 존속"):
        ids.append("RW.AUTHORITY.ORGANIZATION")
    if has(
        text,
        r"(?:power|authority|capacity|권한|자격|능력).*(?:execute|enter|perform|체결|이행)",
        r"(?:execute|enter|perform|체결|이행).*(?:power|authority|capacity|권한|자격|능력)",
    ):
        ids.append("RW.AUTHORITY.POWER")
    if has(text, r"(?:board|corporate|internal).*(?:authorization|approval)", r"내부수권|이사회.*승인"):
        ids.append("RW.AUTHORITY.AUTHORIZATION")
    if has(
        text,
        r"valid and binding|binding.*enforceable|enforceable",
        r"유효.*구속력|구속력.*집행\s*가능|집행할 수 있는",
    ):
        ids.append("RW.AUTHORITY.ENFORCEABILITY")
    if has(text, r"(?:does not|will not).*(?:conflict|violate)", r"(?:위반|충돌).*아니"):
        ids.append("RW.AUTHORITY.NO_CONFLICT")
    if has(
        text,
        r"no.*(?:consent|approval).*required",
        r"(?:동의|승인).*요구되지 아니",
        r"요구되는.*(?:승인|동의).*(?:존재하지|없)",
    ):
        ids.append("RW.AUTHORITY.NO_CONSENT")
    if has(text, r"(?:represents? and warrants?).*(?:true|correct|accurate)", r"(?:true|correct|accurate).*(?:represents? and warrants?)", r"진술.*보장.*(?:진실|정확)", r"(?:진실|정확).*진술.*보장"):
        ids.append("RW.DISCLOSURE.ACCURACY")
    if has(
        text,
        r"\b(?:there (?:is|are) )?no (?:pending |threatened )?(?:litigation|lawsuits?|actions?|arbitrations?|administrative proceedings?|proceedings?|investigations?)\b",
        r"(?:소송|쟁송|분쟁|절차|금지소송등)(?:가|은|는| 등은)?.{0,140}(?:존재하지|진행되고 있지|계류 중이지|제기된 바 없|제기되지 아니)",
    ):
        ids.append("RW.LITIGATION.NO_PENDING")
    if has(text, r"tax returns?.*(?:filed|timely)", r"세무신고.*(?:기한|제출|이행)"):
        ids.append("RW.TAX.RETURNS_FILED")
    if has(text, r"tax(?:es)?.*(?:paid|payment)", r"조세.*납부"):
        ids.append("RW.TAX.PAID")
    if has(text, r"withhold.*tax|원천징수"):
        ids.append("RW.TAX.WITHHOLDING")
    if has(
        text,
        r"(?:tax|income tax).*(?:resident|residency)",
        r"(?:소득세법|세법)상\s*거주자|대한민국.*(?:국민|거주).*(?:소득세법|세법)상",
    ):
        ids.append("RW.TAX.RESIDENCY")
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
    if has(
        text,
        r"sufficient (?:available )?funds|funds (?:sufficient|available).*purchase price",
        r"매매대금.*지급.*충분한 자금|충분한 자금.*매매대금.*지급",
        r"매매대금.*(?:지급|의무).*(?:자금을 보유|동원할 수 있는 능력)",
    ):
        ids.append("RW.BUYER.SUFFICIENT_FUNDS")
    if has(
        text,
        r"financing.*(?:is not|shall not be).*(?:condition|condition to closing)",
        r"(?:condition|condition to closing).*(?:not subject to|not conditioned on).*financing",
        r"자금조달.*(?:종결|거래종결).*(?:조건이 아니|조건으로 하지)",
    ):
        ids.append("RW.BUYER.NO_FINANCING_CONDITION")
    if has(
        text,
        r"independent (?:investigation|review|evaluation)|own (?:investigation|assessment)",
        r"독자적인 (?:조사|평가|판단)|독자적 (?:조사|평가|판단)",
    ):
        ids.append("RW.BUYER.INDEPENDENT_INVESTIGATION")
    if has(
        text,
        r"(?:has|have|had)\s+not\s+relied|no reliance|not been induced by",
        r"의존하지 아니|의존하지 않|유인되지 아니",
    ):
        ids.append("RW.BUYER.NO_RELIANCE")
    if has(
        text,
        r"no other (?:express or implied )?representations?",
        r"(?:representations? and warranties?).*(?:are|constitute).*(?:all|entire)",
        r"다른 진술.*보장.*없|진술.*보장.*전부.*이외.*(?:하지|없)",
    ):
        ids.append("RW.DISCLOSURE.NO_OTHER_REPRESENTATIONS")
    if has(
        text,
        r"(?:books|records).*(?:accurate|correct|consisten).*(?:accounting|law)",
        r"(?:장부|기록).*(?:법령|회계원칙|회계기준).*(?:정확|일관).*(?:작성|유지)",
    ):
        ids.append("RW.FINANCIAL.BOOKS_RECORDS")
    if has(
        text,
        r"fraudulent (?:transfer|conveyance)|creditor.*avoid",
        r"(?:채권자취소권|사해행위|부인권).*(?:대상|사정).*(?:아니|없|존재하지)",
    ):
        ids.append("RW.SOLVENCY.FRAUDULENT_TRANSFER")
    if has(
        text,
        r"\bsolven(?:t|cy)\b|\binsolven(?:t|cy)\b|bankrupt(?:cy)?",
        r"지급능력|지급불능|채무초과|도산절차|파산절차",
    ):
        ids.append("RW.SOLVENCY.GENERAL")
    if has(
        text,
        r"material adverse change",
        r"(?:declaration|payment) of .*dividend",
        r"(?:adoption|modification|termination) of .*employee plan",
        r"change in any method of accounting",
        r"(?:incur|commitment to incur).*capital expenditure",
        r"acquire any assets other than in the ordinary course",
    ):
        ids.append("RW.ABSENCE_OF_CHANGES")

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
    if has(
        text,
        r"consideration for the sale.*(?:purchase price|payment)",
        r"(?:purchase price|매매대금).*(?:consideration|대가)",
    ):
        ids.append("PAY.BASE_PRICE")
    if has(
        text,
        r"(?:earn.?out|additional consideration).*(?:pay|payment|paid)",
        r"(?:pay|payment|paid).*(?:earn.?out|additional consideration)",
        r"언아웃.*지급|추가대금.*지급",
    ):
        ids.append("PAY.EARNOUT.PAYMENT")
    if has(text, r"(?:default|delay) interest|interest.*late payment", r"지연이자"):
        ids.append("PAY.INTEREST")
    if has(text, r"deposit|계약금|중도금"):
        ids.append("PAY.DEPOSIT")
    if has(
        text,
        r"closing.*(?:pay|payment|wire|송금)",
        r"(?:funds?|amount).*(?:bank account|wire transfer instructions)",
        r"거래종결.*(?:지급|송금)",
    ):
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
    if has(
        text,
        r"(?:shall not|may not).*(?:solicit|initiate|enter into|negotiate).*(?:acquisition|competing transaction)",
        r"(?:제3자|매수인 이외).*(?:유사|배치되는) 거래.*(?:협상|제안|협의|약정|논의|체결).*(?:하지|않)",
    ):
        ids.append("COV.EXCLUSIVITY")
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
    if has(
        text,
        r"(?:notify|file).{0,40}\bwith (?:a |the )?(?:government|authority|municipal)",
        r"(?:정부기관(?:에|에게)|서울특별시(?:에|에게)|지방자치단체(?:에|에게)).*(?:경영권 변동|거래).*(?:통지|신고)",
    ):
        ids.append("COV.REGULATORY.NOTIFICATION")
    if has(text, r"release.*(?:liabilit|claim)|면책|청구.*포기"):
        ids.append("COV.RELEASE")
    if has(text, r"transfer.*shares?.*(?:restricted|consent|prohibited)", r"주식.*양도.*(?:제한|동의|금지)"):
        ids.append("COV.SHA.TRANSFER.RESTRICTION")
    if has(text, r"transfer to key personnel|permitted transfer", r"(?:핵심인력|임직원).*(?:주식|지분).*(?:양도|이전)"):
        ids.append("COV.SHA.PERMITTED_TRANSFER")
    if has(
        text,
        r"board.*nomina|designate.*director",
        r"(?:이사|감사).*지명.*(?:권리|하여야|할 수)",
    ):
        ids.append("COV.SHA.BOARD_NOMINATION")
    if has(
        text,
        r"(?:shareholders? meeting).*(?:buyer|purchaser).*(?:nominee|designat).*(?:director|officer).*(?:appoint|elect)",
        r"주주총회.*매수인.*지명.*(?:이사|감사|임원).*(?:선임|결의).*(?:하여야|되도록|교부하여야)",
    ):
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
        r"(?:employee|employment).*(?:maintain|continue|not terminate).*(?:closing|year|period)",
        r"거래종결일 이후.*(?:근로관계|근로조건).*(?:해지|변경|중단|유지)",
    ):
        ids.append("COV.EMPLOYEE_BENEFITS_CONTINUATION")
    if has(
        text,
        r"(?:chairman|shareholder|affiliate).*(?:guarantee|guaranty).*(?:obligations?|performance)",
        r"(?:회장|주주|계열회사).*(?:의무|채무).*(?:보증|연대보증)",
    ):
        ids.append("COV.PERSONAL_GUARANTEE")
    if has(
        text,
        r"(?:cleanup|settle|eliminate).*(?:liabilit|provision)",
        r"(?:충당부채|특정 채무).*(?:정리|상환|제거).*(?:완료|하여야)",
    ):
        ids.append("COV.LIABILITY_CLEANUP")
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
    if has(
        text,
        r"(?:extend|make).*(?:loan|advance|contribution)",
        r"change.*accounting (?:method|polic|practice)",
        r"(?:merge|consolidate|liquidate|dissolve|wind up)",
        r"enter into any contract.*foregoing",
        r"(?:사전 서면 동의|prior written consent).*(?:하지|shall not|must not)",
        r"주식의 (?:병합|분할|종류의 변경|감자|소각)",
        r"(?:합병|분할|분할합병|주식의 포괄적 교환|영업 전부.*양도)",
    ):
        ids.append("COV.RESTRICTED_ACTIONS")

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
        r"(?:계약을|본 계약을|본 계약은).{0,60}(?:해제|해지)(?:할 수|될 수)|본 계약.*(?:해지되|해제된 경우)|해제권|해지권",
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
    if has(
        text,
        r"governed by.*laws?|governing law",
        r"(?:대한민국|한국).*(?:법률|법규).*(?:해석|규율|집행)",
        r"준거법.*(?:대한민국|한국).*(?:법률|법규)",
    ):
        ids.append("REM.GOVERNING_LAW")
    if has(
        text,
        r"(?:exclusive )?jurisdiction",
        r"\b(?:shall|must|will)\b.{0,80}\barbitration\b",
        r"\b(?:submitted to|settled by|resolved by)\s+arbitration\b",
        r"(?:관할법원|전속관할|합의관할)",
        r"(?:분쟁|분쟁사항).{0,80}(?:중재)",
        r"(?:중재).{0,80}(?:해결|회부|신청)",
    ):
        ids.append("REM.DISPUTE_RESOLUTION")
    if has(text, r"entire agreement|supersedes?.*prior", r"(?:최종적|완전한).*(?:합의).*(?:종전|대체)"):
        ids.append("REM.ENTIRE_AGREEMENT")
    if has(
        text,
        r"(?:this agreement|this instrument|provision|term).{0,100}(?:amend|modif).{0,100}(?:writing|signed)",
        r"(?:writing|signed).{0,100}(?:amend|modif).{0,100}(?:this agreement|this instrument|provision|term)",
        r"(?:본 계약|계약의 조항).{0,80}(?:수정|개정|변경).{0,80}(?:서면|서명)",
        r"(?:서면 합의|서명한 서면).{0,80}(?:수정|개정|변경)",
    ):
        ids.append("REM.AMENDMENT")
    if has(
        text,
        r"(?:failure|delay|omission).*(?:exercise|exercising).*(?:not|no).*(?:waiver|operate as a waiver)",
        r"no (?:delay|omission).*(?:operate|construed).*(?:waiver)",
        r"권리.*행사하지.*포기로 간주되지",
        r"권리.*포기.*다른.*(?:권리|조항).*포기로 간주되지",
    ):
        ids.append("REM.WAIVER")
    if has(
        text,
        r"(?:invalid|illegal|unenforceable).{0,160}(?:remaining|other)\s+provisions?.{0,120}(?:valid|force|effect|enforceable)",
        r"(?:provision|term).{0,120}(?:invalid|illegal|unenforceable).{0,160}(?:remaining|other)\s+(?:provisions?|terms?)",
        r"severability",
        r"(?:무효|위법|집행이 불가능).*(?:다른|나머지).*(?:효력|집행가능성).*(?:영향을 주지|유효)",
    ):
        ids.append("REM.SEVERABILITY")
    if has(
        text,
        r"nothing.*(?:confer|create).*(?:third.party beneficiar|(?:any )?third part).*(?:rights?|remed)",
        r"nothing.*(?:confer|give).*(?:any other person|person who is not a party).*(?:rights?|remed)",
        r"(?:not intended|shall not be construed).*(?:confer|give).*(?:rights?|remed)",
        r"no third.party beneficiar",
        r"(?:agreement|instrument).{0,120}(?:solely|only) for the benefit of.{0,120}(?:no|not).{0,80}(?:benefit|claim|right|remed)",
        r"제3자에게.*(?:권리|구제수단).*(?:부여하지|부여하는 것으로 해석되지|발생시키지)",
    ):
        ids.append("REM.NO_THIRD_PARTY_BENEFICIARY")
    if has(
        text,
        r"(?:agreement|provisions?).*(?:binding (?:upon|on)|shall be binding).*(?:successors?|assigns?)",
        r"(?:inure|enure) to the benefit.*(?:successors?|assigns?)",
        r"본 계약.*당사자.*구속.*효력",
    ):
        ids.append("REM.BINDING_EFFECT")
    if has(
        text,
        r"(?:specific performance|injunctive relief|irreparable harm)",
        r"(?:회복할 수 없는 손해|가압류|가처분).*(?:이행을 강제|청구할 권리)",
    ) and not has(
        text,
        r"nothing.*(?:require|obligat).*(?:seek|pursue).*specific performance",
        r"not (?:entitled|permitted) to (?:seek|obtain).*specific performance",
    ):
        ids.append("REM.SPECIFIC_PERFORMANCE")
    if has(
        text,
        r"more than once.*(?:same loss|same damages?)",
        r"(?:same loss|same damages?).*more than once",
        r"(?:동일한|같은).*(?:손해|사실).*(?:중복|두 번 이상).*(?:배상|회수)",
    ):
        ids.append("REM.NO_DOUBLE_RECOVERY")
    if has(
        text,
        r"indemnif.{0,120}\bin full\b.*(?:fraud|willful misconduct)",
        r"(?:fraud|willful misconduct).{0,120}\bindemnif.{0,120}\bin full\b",
        r"limitations?.*(?:shall not|do not|does not).*apply.*(?:fraud|willful misconduct)",
        r"(?:fraud|willful misconduct).*(?:not subject to|excluded from).*limitations?",
        r"(?:사기|고의).*(?:책임제한).*(?:적용하지|제외)",
        r"(?:책임제한).*(?:적용하지|제외).*(?:사기|고의)",
        r"(?:사기|고의).*(?:손해배상|배상책임).*(?:전액|제한 없이)",
    ):
        ids.append("REM.FRAUD_CARVEOUT")
    if has(
        text,
        r"(?:punitive|exemplary) damages?.*(?:not liable|exclude|in no event)",
        r"in no event.*(?:punitive|exemplary) damages?",
        r"(?:징벌적|제재적) 손해.*(?:배제|책임을 지지)",
    ):
        ids.append("REM.CONSEQUENTIAL.PUNITIVE")
    if has(
        text,
        r"(?:lost profits?|loss of profits?).*(?:not liable|exclude|in no event)",
        r"in no event.*(?:lost profits?|loss of profits?)",
        r"일실이익.*(?:배제|책임을 지지)",
    ):
        ids.append("REM.CONSEQUENTIAL.LOST_PROFITS")
    if has(
        text,
        r"losses?.*would not have arisen but for.*voluntary (?:act|omission|transaction)",
        r"voluntary (?:act|omission|transaction).*(?:loss|recover|indemnif)",
        r"자발적(?:인)?\s*(?:행위|부작위|거래).*(?:손해|배상)",
    ):
        ids.append("REM.INDEMNITY.VOLUNTARY_ACT_EXCLUSION")
    if has(text, r"rights? and remedies?.*cumulative", r"권리와 구제수단.*(?:중첩|배제하지)"):
        ids.append("REM.CUMULATIVE_REMEDIES")
    if has(text, r"reasonable steps?.*mitigat", r"손해.*최소화.*합리적인 조치"):
        ids.append("REM.MITIGATION")
    if has(text, r"indemnif.*(?:breach|obligation)", r"(?:진술.*보장|확약|의무).*위반.*(?:손해|배상)"):
        ids.extend(("REM.INDEMNITY.RW_BREACH", "REM.INDEMNITY.COVENANT_BREACH"))
    if has(
        text,
        r"(?:indemnity|indemnification|damages?).*(?:tax purposes?).*(?:purchase price adjustment|adjustment to the purchase price)",
        r"(?:손해배상|배상금액).*(?:조세|세무|매매대금).*(?:매매대금의? 조정|조정되는 것으로)",
    ):
        ids.append("REM.INDEMNITY.PURCHASE_PRICE_ADJUSTMENT")
    if has(
        text,
        r"(?:change in law|change in.*interpretation).*(?:loss|damage).*(?:exclude|not liable|no liability)",
        r"(?:법률|법령|정부기관.*입장|해석).*(?:개정|변경).*(?:손해).*(?:배상책임을 지지|제외)",
    ):
        ids.append("REM.INDEMNITY.CHANGE_IN_LAW_EXCLUSION")

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
        r"(?:아래|다음)와 같이.*진술.*보장한다[.:\s]*$",
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
        r"(?:각 당사자|당사자들|매도인들과 매수인).*(?:아래|다음)와 같이.*(?:확약|의무를 부담)한다[.:\s]*$",
        r"^\s*\[note to (?:seller|buyer).*]\s*$",
        r"^[^.]{0,80}\.\s*(?:prior to|until|from).{0,120}\bshall(?:\s+not)?\s*:?\s*$",
        r"^[^.]{0,120}\.\s*(?:seller|purchaser|buyer|company)\s+shall(?:\s+not)?\s*:?\s*$",
    )


SOURCE_HEADING_RE = re.compile(
    r"^\s*(?:schedule|annex|exhibit|appendix|별지|부록)\s*"
    r"(?:[A-Z0-9가-힣]+(?:[.\-][A-Z0-9가-힣]+)*)?\s*$",
    re.IGNORECASE,
)


def source_needs_candidate(text: str) -> bool:
    """Keep substantive schedule evidence visible without queuing pure labels."""

    cleaned = " ".join(text.split()).strip()
    if not cleaned or SOURCE_HEADING_RE.fullmatch(cleaned):
        return False
    if reject_as_non_atomic(cleaned):
        return False
    if substantive(cleaned):
        return True
    if re.fullmatch(r"(?:none|nil|n/?a|없음|해당\s*없음|없다)[.\s]*", cleaned, re.IGNORECASE):
        return True
    if "|" in cleaned and len(cleaned) >= 12:
        return True
    return False


def infer_source_candidate_family(text: str, linked_families: set[str]) -> str:
    """Choose one review queue while source coverage blocks all linked families."""

    if has(text, r"indemn|damages?|liabilit|termination|remed", r"손해|배상|책임|해제|해지"):
        return "REM"
    if has(text, r"purchase price|consideration|payment|escrow", r"매매대금|지급|에스크로|대가"):
        return "PAY"
    if has(text, r"condition(?:s)? precedent|condition to closing", r"선행조건|종결조건"):
        return "CP"
    if has(text, r"represent(?:s|ed|ation)|warrant", r"진술|보장"):
        return "RW"
    if has(text, r"\bshall\b|\bundertake|\bagree", r"하여야|확약|의무"):
        return "COV"
    for family in ("RW", "COV", "CP", "PAY", "REM", "DEF"):
        if family in linked_families:
            return family
    return "COV"


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
        "source_kind": candidate.get("source_kind", "body"),
        "source_id": candidate.get("source_id"),
        "source_name": candidate.get("source_name"),
        "source_ref": candidate.get("source_ref") or f"¶{candidate['loc_start']}",
        "parent_clause_ref": candidate.get("parent_clause_ref")
        or strip_candidate_prefix(candidate.get("proposed_ko"))
        or None,
        "related_item_ref": None,
        "qualifier": {
            **(
                candidate.get("qualifier")
                if isinstance(candidate.get("qualifier"), dict)
                else {}
            ),
            "review_method": "V4-2 후보 문맥 직접 검수",
        },
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
    seen: set[tuple[str, str, int, str, str]] = set()
    unresolved: list[dict] = []
    incomplete_source_keys: set[tuple[str, str]] = set()

    def add(source: dict, taxonomy_id: str, *, candidate: bool = False) -> None:
        if taxonomy_id not in known:
            unresolved.append({"code": "unknown_taxonomy", "taxonomy_id": taxonomy_id})
            return
        family = known[taxonomy_id]
        key = (
            taxonomy_id,
            str(source.get("verbatim")),
            int(source["loc_start"]),
            str(source.get("source_kind") or "body"),
            str(source.get("source_id") or ""),
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
                # The heading itself is the reviewed evidence. Extending an
                # item across the whole hint range creates false coordinates
                # when the range crosses a later article or a sparse union.
                "loc_end": int(hint["loc_start"]),
                "proposed_ko": f"원문 atomic hint 재검수: {text[:100]}",
            }
            for taxonomy_id in ids:
                add(hint_candidate, taxonomy_id, candidate=True)

    # A family range can contain long operative paragraphs that have no short
    # heading and no direct alias match in the proposal pass. Review every
    # physical body paragraph once so such clauses cannot disappear merely
    # because ``atomic_unit_hints`` is empty.
    represented_body_evidence = {
        (int(row["loc_start"]), str(row["verbatim"]).strip())
        for row in [*output, *unresolved]
        if row.get("source_kind", "body") == "body"
        and row.get("loc_start")
        and row.get("verbatim")
    }
    for section_family, section in (
        (source or {}).get("family_sections") or {}
    ).items():
        if not isinstance(section, dict):
            continue
        for paragraph in section.get("paragraphs") or []:
            para = int(paragraph["para"])
            text = str(paragraph.get("text") or "").strip()
            evidence_key = (para, text)
            if not text or evidence_key in represented_body_evidence:
                continue
            taxonomy_ids = [
                taxonomy_id
                for taxonomy_id in classify_text(text)
                if taxonomy_id in known
            ]
            body_candidate = {
                "verbatim": text,
                "loc_start": para,
                "loc_end": para,
                "source_kind": "body",
                "source_id": None,
                "source_name": "계약서 본문",
                "source_ref": f"¶{para}",
                "parent_clause_ref": f"{section_family} 본문",
                "qualifier": {
                    "review_method": "V4-2 본문 물리 문단 전수검수",
                },
            }
            if taxonomy_ids:
                for taxonomy_id in taxonomy_ids:
                    add(body_candidate, taxonomy_id, candidate=True)
                represented_body_evidence.add(evidence_key)
                continue
            if not source_needs_candidate(text):
                continue
            family = (
                str(section_family)
                if str(section_family) in FAMILIES
                else infer_source_candidate_family(text, set())
            )
            unresolved.append(
                {
                    **body_candidate,
                    "proposed_ko": candidate_name(
                        family, text, source_name="본문", loc_start=para
                    ),
                    "proposed_en": None,
                    "family": family,
                    "recommended_parent_id": family,
                    "distinction_reason": (
                        "본문의 실질 문단이나 기존 taxonomy 규칙으로 확정 "
                        "분류되지 않아 원문 좌표를 보존한 검토가 필요함"
                    ),
                    "nearest_taxonomy_id": family,
                }
            )
            represented_body_evidence.add(evidence_key)

    # Some agreements use no recognizable family/article headings.  The
    # range repair pass preserves those physical paragraphs separately so the
    # document can still receive a conservative proposition-by-proposition
    # review instead of being silently marked wholly unevaluated.
    for paragraph in (source or {}).get("unscoped_body_paragraphs") or []:
        para = int(paragraph["para"])
        text = str(paragraph.get("text") or "").strip()
        evidence_key = (para, text)
        if not text or evidence_key in represented_body_evidence:
            continue
        taxonomy_ids = [
            taxonomy_id
            for taxonomy_id in classify_text(text)
            if taxonomy_id in known
        ]
        family = infer_source_candidate_family(text, set())
        body_candidate = {
            "verbatim": text,
            "loc_start": para,
            "loc_end": para,
            "source_kind": "body",
            "source_id": None,
            "source_name": "계약서 본문",
            "source_ref": f"¶{para}",
            "parent_clause_ref": "제목 미인식 본문",
            "qualifier": {
                "review_method": "V4-2 제목 미인식 본문 물리 문단 전수검토",
            },
        }
        if taxonomy_ids:
            for taxonomy_id in taxonomy_ids:
                add(body_candidate, taxonomy_id, candidate=True)
            represented_body_evidence.add(evidence_key)
            continue
        if not source_needs_candidate(text):
            continue
        unresolved.append(
            {
                **body_candidate,
                "proposed_ko": candidate_name(
                    family, text, source_name="본문", loc_start=para
                ),
                "proposed_en": None,
                "family": family,
                "recommended_parent_id": family,
                "distinction_reason": (
                    "표준 조항 제목이 없는 본문의 실질 문단으로, 기존 taxonomy "
                    "규칙으로 확정 분류되지 않아 원문 좌표를 보존한 검토가 필요함"
                ),
                "nearest_taxonomy_id": family,
            }
        )
        represented_body_evidence.add(evidence_key)

    # Review each physical schedule/annex paragraph exactly once. Source
    # inventory rows can repeat the same physical source for several families;
    # duplicate family links must not create duplicate clause items.
    physical_sources: dict[tuple[str, int, str], list[tuple[dict, dict]]] = {}
    for source_row in (source or {}).get("source_inventory") or []:
        if str(source_row.get("status_hint") or "").casefold() not in {
            "available",
            "partial",
        }:
            continue
        storage_key = str(
            source_row.get("storage_file_key")
            or (source or {}).get("file_key")
            or data.get("file_key")
        )
        for paragraph in source_row.get("paragraphs") or []:
            text = str(paragraph.get("text") or "").strip()
            key = (storage_key, int(paragraph["para"]), text)
            physical_sources.setdefault(key, []).append((source_row, paragraph))

    source_storage_keys = {
        str(row.get("source_id") or ""): str(
            row.get("storage_file_key")
            or (source or {}).get("file_key")
            or data.get("file_key")
        )
        for row in (source or {}).get("source_inventory") or []
    }
    represented_source_evidence = {
        (
            source_storage_keys.get(
                str(row.get("source_id") or ""),
                str((source or {}).get("file_key") or data.get("file_key")),
            ),
            int(row["loc_start"]),
            str(row["verbatim"]).strip(),
        )
        for row in output
        if row.get("source_kind") != "body"
    }
    for (_storage_key, para, text), links in physical_sources.items():
        evidence_key = (_storage_key, para, text)
        if not text or evidence_key in represented_source_evidence:
            continue
        taxonomy_ids = [
            taxonomy_id
            for taxonomy_id in classify_text(text)
            if taxonomy_id in known
        ]
        representative = links[0][0]
        linked_families = {str(row["family"]) for row, _paragraph in links}
        source_candidate = {
            "verbatim": text,
            "loc_start": para,
            "loc_end": para,
            "source_kind": representative["source_kind"],
            "source_id": representative["source_id"],
            "source_name": representative["source_name"],
            "source_ref": f"¶{para}",
            "parent_clause_ref": representative["source_name"],
            "qualifier": {
                "review_method": "V4-2 별지 물리 문단 전수검수",
                "linked_source_families": sorted(linked_families),
            },
        }
        if taxonomy_ids:
            for taxonomy_id in taxonomy_ids:
                add(source_candidate, taxonomy_id, candidate=True)
            represented_source_evidence.add(evidence_key)
            continue
        if not source_needs_candidate(text):
            continue
        candidate_family = infer_source_candidate_family(text, linked_families)
        source_candidate.update(
            {
                "proposed_ko": candidate_name(
                    candidate_family,
                    text,
                    source_name=str(representative["source_name"]),
                    loc_start=para,
                ),
                "proposed_en": None,
                "family": candidate_family,
                "recommended_parent_id": candidate_family,
                "distinction_reason": (
                    "별지의 실질 문단이나 기존 taxonomy 규칙으로 확정 분류되지 않아 "
                    "원문·source 좌표를 보존한 검토가 필요함"
                ),
                "nearest_taxonomy_id": candidate_family,
            }
        )
        unresolved.append(source_candidate)
        for linked_source, _paragraph in links:
            incomplete_source_keys.add(
                (str(linked_source["family"]), str(linked_source["source_id"]))
            )
        incomplete_source_keys.add(
            (candidate_family, str(representative["source_id"]))
        )

    body_families_with_evidence = {
        str(row["family"])
        for row in [*output, *unresolved]
        if row.get("source_kind", "body") == "body"
        and str(row.get("family")) in FAMILIES
    }
    coverage = {}
    for family in FAMILIES:
        original = data["coverage"][family]
        body_was_reviewed = (
            original["body_status"] != "not_evaluated"
            or family in body_families_with_evidence
        )
        coverage[family] = {
            "body_status": "complete" if body_was_reviewed else "not_evaluated",
            "annex_status": original["annex_status"],
            "reason": "V4-2 문맥 검수 완료" if body_was_reviewed else original.get("reason"),
        }
    source_coverage = []
    for row in data.get("source_coverage") or []:
        copied = dict(row)
        source_key = (str(copied["family"]), str(copied["source_id"]))
        if source_key in incomplete_source_keys:
            copied["status"] = "partial"
            copied["reason"] = "별지 실질 문단에 미해결 taxonomy 후보가 있어 검토 필요"
        elif copied["status"] == "partial":
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
    for item_row in [*output, *unresolved]:
        if item_row.get("source_kind", "body") == "body" or not item_row.get("source_id"):
            continue
        key = (str(item_row["family"]), str(item_row["source_id"]))
        if key in source_keys:
            continue
        template = source_by_id.get(str(item_row["source_id"]))
        if template is None:
            continue
        derived = dict(template)
        derived["family"] = item_row["family"]
        if key in incomplete_source_keys:
            derived["status"] = "partial"
            derived["reason"] = "별지 실질 문단에 미해결 taxonomy 후보가 있어 검토 필요"
        else:
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
        elif statuses and any(status == "partial" for status in statuses):
            coverage[family]["annex_status"] = "partial"
        elif statuses and any(status == "unreadable" for status in statuses):
            coverage[family]["annex_status"] = "unreadable"
        elif statuses:
            coverage[family]["annex_status"] = "not_evaluated"
        elif not statuses:
            coverage[family]["annex_status"] = "no_annex"

    evidence_in_output = {
        (
            str(row.get("source_kind") or "body"),
            str(row.get("source_id") or ""),
            int(row["loc_start"]),
            str(row["verbatim"]),
        )
        for row in output
    }
    unresolved = [
        row
        for row in unresolved
        if row.get("code") == "unknown_taxonomy"
        or (
            str(row.get("source_kind") or "body"),
            str(row.get("source_id") or ""),
            int(row.get("loc_start") or 0),
            str(row.get("verbatim") or ""),
        )
        not in evidence_in_output
    ]

    result = {
        **data,
        "taxonomy_version": int(data["taxonomy_version"]),
        "extractor_version": "codex-context-review-1",
        "prompt_version": f"v4-prompt-{int(data['taxonomy_version'])}",
        "items": output,
        "coverage": coverage,
        "source_coverage": source_coverage,
        "taxonomy_candidates": unresolved,
    }
    return result, unresolved


def prepare_reviewed_source(source: dict, result: dict) -> dict:
    """Return a reviewed input payload aligned to final coverage and items."""
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
            template = next(
                (
                    row
                    for row in (source.get("source_inventory") or [])
                    if str(row["source_id"]) == str(coverage_row["source_id"])
                ),
                None,
            )
        if template is None:
            continue
        derived_inventory = dict(template)
        derived_inventory["family"] = coverage_row["family"]
        inventory.append(derived_inventory)
        inventory_keys.add(key)
        inventory_by_id.setdefault(str(coverage_row["source_id"]), template)

    source["source_inventory"] = inventory
    source["taxonomy_version"] = int(result["taxonomy_version"])
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
    return source


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
        source = prepare_reviewed_source(source, result)
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
        "taxonomy_version": int(result["taxonomy_version"]),
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
