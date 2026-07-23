"""Mine bounded evidence for detailed RW leaf taxonomy across reviewed samples."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from lib.console import configure_utf8_stdio
from review_v4_scope_sample import EXISTING_REVIEW_KEYS


@dataclass(frozen=True)
class Leaf:
    taxonomy_id: str
    parent_id: str
    ko: str
    en: str
    definition: str
    patterns: tuple[str, ...]


LEAVES = (
    Leaf("RW.AUTHORITY.ORGANIZATION", "RW.AUTHORITY", "설립·존속", "Organization and good standing", "적법한 설립·유효한 존속·법인격", (r"duly (?:organized|incorporated).{0,80}(?:validly existing|good standing)", r"적법하게 설립.{0,40}(?:존속|유효)")),
    Leaf("RW.AUTHORITY.POWER", "RW.AUTHORITY", "권리능력·행위능력", "Power and capacity", "계약체결·사업영위·자산보유 권한과 능력", (r"(?:power|capacity).{0,80}(?:enter into|execute|perform)", r"(?:권한|능력).{0,40}(?:체결|이행|사업)")),
    Leaf("RW.AUTHORITY.AUTHORIZATION", "RW.AUTHORITY", "내부승인·수권", "Authorization", "이사회·주주 등 필요한 내부승인과 수권", (r"(?:corporate|internal) action.{0,80}(?:authorized|approval)", r"(?:이사회|주주총회|내부).{0,40}(?:승인|결의|수권)")),
    Leaf("RW.AUTHORITY.ENFORCEABILITY", "RW.AUTHORITY", "유효성·구속력", "Enforceability", "계약의 적법·유효한 구속력과 집행가능성", (r"valid and binding obligation", r"enforceable against", r"(?:유효|적법).{0,30}(?:구속|집행)")),
    Leaf("RW.AUTHORITY.NO_CONFLICT", "RW.AUTHORITY", "충돌·위반 부재", "No conflict", "계약·법령·조직문서와의 충돌·위반 부재", (r"(?:does not|will not).{0,100}(?:conflict|violate|breach)", r"(?:충돌|위반|저촉).{0,30}(?:아니|않)")),
    Leaf("RW.AUTHORITY.NO_CONSENT", "RW.AUTHORITY", "추가 동의·승인 불요", "No additional consent", "계약체결·이행에 필요한 정부·제3자 동의·신고의 부재", (r"no (?:consent|approval|authorization).{0,100}(?:required|necessary)", r"(?:동의|승인|신고).{0,40}(?:필요하지|요하지)")),
    Leaf("RW.CAPITALIZATION.AUTHORIZED_ISSUED", "RW.CAPITALIZATION", "수권·발행주식", "Authorized and issued shares", "수권주식·발행주식의 종류와 수량", (r"authorized capital stock", r"issued and outstanding shares", r"(?:발행할 주식|발행주식).{0,40}(?:총수|수)")),
    Leaf("RW.CAPITALIZATION.OWNERSHIP", "RW.CAPITALIZATION", "주식·지분 소유권", "Share ownership", "주주별 대상주식의 적법·유효한 소유권", (r"(?:record|beneficial) owner.{0,60}(?:shares|stock)", r"(?:주식|지분).{0,30}(?:적법|유효).{0,20}소유")),
    Leaf("RW.CAPITALIZATION.FULLY_PAID", "RW.CAPITALIZATION", "완전납입·추가납입의무 부재", "Fully paid and non-assessable", "발행주식의 완전납입과 추가납입의무 부재", (r"fully paid and non.?assessable", r"(?:전액|완전).{0,20}납입")),
    Leaf("RW.CAPITALIZATION.NO_DILUTIVE_SECURITIES", "RW.CAPITALIZATION", "잠재주식·희석증권 부재", "No dilutive securities", "옵션·전환증권·신주인수권 등 잠재주식 부재", (r"no outstanding.{0,100}(?:option|warrant|convertible)", r"(?:옵션|전환사채|신주인수권).{0,50}(?:없|존재하지)")),
    Leaf("RW.CAPITALIZATION.NO_PREEMPTIVE_RIGHTS", "RW.CAPITALIZATION", "우선인수권 등 부재", "No pre-emptive rights", "신주인수권·우선매수권 등 주식 관련 제3자 권리 부재", (r"no.{0,80}(?:preemptive|pre-emption|first refusal) rights?", r"(?:신주인수권|우선매수권).{0,40}(?:없|존재하지)")),
    Leaf("RW.CAPITALIZATION.NO_ENCUMBRANCE", "RW.CAPITALIZATION", "주식 제한부담 부재", "No share encumbrance", "대상주식에 대한 담보·질권·양도제한 등 부담 부재", (r"(?:shares|stock).{0,80}free and clear.{0,40}(?:lien|encumbrance)", r"(?:대상주식|주식).{0,40}(?:제한부담|담보권).{0,30}(?:없|없이)")),
    Leaf("RW.CAPITALIZATION.SUBSIDIARIES", "RW.CAPITALIZATION", "자회사·투자지분", "Subsidiaries and equity interests", "자회사·관계회사 및 타 법인 지분 보유 현황", (r"(?:subsidiaries|equity interests in other)", r"(?:자회사|타 법인).{0,40}(?:지분|주식)")),
    Leaf("RW.FINANCIAL.GAAP", "RW.FINANCIAL", "회계기준 준수", "GAAP compliance", "재무제표의 적용 회계기준 준수", (r"prepared in accordance with.{0,40}(?:GAAP|IFRS)", r"(?:기업회계기준|회계기준).{0,30}(?:따라|준수)")),
    Leaf("RW.FINANCIAL.FAIR_PRESENTATION", "RW.FINANCIAL", "재무상태 적정표시", "Fair presentation", "재무제표의 재무상태·경영성과·현금흐름 적정표시", (r"fairly present.{0,100}(?:financial position|results of operations|cash flows)", r"(?:재무상태|경영성과|현금흐름).{0,40}(?:적정|공정).{0,20}표시")),
    Leaf("RW.FINANCIAL.CONSISTENCY", "RW.FINANCIAL", "회계정책 계속성", "Consistent accounting policies", "회계원칙·정책의 기간 간 일관된 적용", (r"consistently applied", r"(?:회계정책|회계원칙).{0,30}(?:일관|계속)")),
    Leaf("RW.ASSETS.TITLE", "RW.ASSETS", "자산 소유권", "Title to assets", "사업용 자산의 적법·유효한 소유권 또는 사용권", (r"(?:good|valid|marketable) title to.{0,60}assets", r"(?:자산|재산).{0,30}(?:소유권|권원)")),
    Leaf("RW.ASSETS.SUFFICIENCY", "RW.ASSETS", "자산 충분성", "Sufficiency of assets", "현재 사업 영위에 필요한 자산의 완전성·충분성", (r"assets.{0,80}(?:sufficient|adequate).{0,80}(?:conduct|operation).{0,30}business", r"(?:사업|영업).{0,30}(?:필요|영위).{0,30}(?:자산|재산).{0,30}(?:충분|모두)")),
    Leaf("RW.ASSETS.CONDITION", "RW.ASSETS", "자산 상태", "Condition of assets", "유형자산의 작동상태·유지보수·통상 마모", (r"(?:assets|equipment).{0,80}(?:good operating condition|good repair)", r"(?:자산|설비).{0,30}(?:상태|작동|유지보수)")),
    Leaf("RW.ASSETS.NO_ENCUMBRANCE", "RW.ASSETS", "자산 제한부담 부재", "No asset encumbrance", "자산에 대한 담보권·제한부담 부재", (r"assets.{0,80}free and clear.{0,40}(?:lien|encumbrance)", r"(?:자산|재산).{0,40}(?:제한부담|담보권).{0,30}(?:없|없이)")),
    Leaf("RW.CONTRACTS.COMPLETE_LIST", "RW.CONTRACTS", "중요계약 목록 완전성", "Complete material contract list", "중요계약 목록·사본의 완전성과 정확성", (r"(?:complete|correct) list.{0,80}material contracts?", r"중요계약.{0,40}(?:목록|내역).{0,30}(?:완전|정확)")),
    Leaf("RW.CONTRACTS.VALID_BINDING", "RW.CONTRACTS", "계약 유효성·구속력", "Contract validity", "중요계약의 유효성·구속력·집행가능성", (r"material contracts?.{0,80}(?:valid|binding|enforceable)", r"중요계약.{0,40}(?:유효|구속|집행)")),
    Leaf("RW.CONTRACTS.NO_DEFAULT", "RW.CONTRACTS", "계약 위반·채무불이행 부재", "No contract default", "당사자와 상대방의 중요계약 위반·채무불이행 부재", (r"no.{0,60}(?:breach|default).{0,80}material contract", r"중요계약.{0,40}(?:위반|채무불이행).{0,30}(?:없|아니)")),
    Leaf("RW.CONTRACTS.NO_TERMINATION_NOTICE", "RW.CONTRACTS", "해지·변경통지 부재", "No termination notice", "중요계약의 해지·갱신거절·중요변경 통지 부재", (r"no (?:notice|threat).{0,80}(?:terminat|cancel|not renew)", r"(?:해지|종료|갱신거절).{0,40}(?:통지|의사).{0,30}(?:없|받지)")),
    Leaf("RW.CONTRACTS.NO_CHANGE_CONTROL_EFFECT", "RW.CONTRACTS", "거래로 인한 계약상 불이익 부재", "No change-of-control effect", "본건 거래로 인한 해지권·동의권·기한이익상실 등 부재", (r"(?:change of control|transactions contemplated).{0,100}(?:termination|consent|default)", r"본건 거래.{0,50}(?:해지|동의|기한의 이익|불이익)")),
    Leaf("RW.LITIGATION.NO_PENDING", "RW.LITIGATION", "계류 중 소송 부재", "No pending proceedings", "계류 중인 소송·중재·행정절차의 부재", (r"no.{0,60}(?:action|suit|proceeding).{0,40}pending", r"(?:계류|진행) 중.{0,30}(?:소송|분쟁).{0,20}(?:없|존재하지)")),
    Leaf("RW.LITIGATION.NO_THREATENED", "RW.LITIGATION", "제기 우려 소송 부재", "No threatened proceedings", "서면 위협·합리적으로 예상되는 소송의 부재", (r"no.{0,60}(?:action|proceeding).{0,40}threatened", r"(?:제기|발생).{0,30}(?:우려|예정).{0,30}(?:소송|분쟁).{0,20}(?:없|아니)")),
    Leaf("RW.LITIGATION.NO_ORDER", "RW.LITIGATION", "명령·판결 부재", "No orders or judgments", "적용되는 판결·명령·금지명령·처분의 부재", (r"not subject to.{0,60}(?:order|judgment|injunction)", r"(?:판결|명령|처분|금지명령).{0,40}(?:없|적용되지)")),
    Leaf("RW.LITIGATION.NO_INVESTIGATION", "RW.LITIGATION", "정부조사 부재", "No governmental investigation", "정부기관의 조사·수사·감사 부재", (r"no.{0,60}(?:governmental|regulatory).{0,40}(?:investigation|inquiry)", r"(?:정부|관계기관).{0,30}(?:조사|수사|감사).{0,30}(?:없|받지)")),
    Leaf("RW.TAX.RETURNS_FILED", "RW.TAX", "조세신고", "Tax returns filed", "필요한 조세신고서의 적법·정확·기한 내 제출", (r"tax returns?.{0,80}(?:timely filed|duly filed|true and correct)", r"(?:세무|조세)신고.{0,40}(?:기한|적법|정확)")),
    Leaf("RW.TAX.PAID", "RW.TAX", "조세납부", "Taxes paid", "납기 도래 조세의 전액·기한 내 납부", (r"taxes.{0,80}(?:due and payable|have been paid)", r"(?:납기|기한).{0,30}(?:도래|내).{0,30}조세.{0,30}납부")),
    Leaf("RW.TAX.WITHHOLDING", "RW.TAX", "원천징수", "Tax withholding", "원천징수·공제 및 과세관청 납부의 이행", (r"(?:withheld|withholding).{0,80}(?:tax|paid)", r"원천징수.{0,50}(?:납부|공제)")),
    Leaf("RW.TAX.NO_AUDIT", "RW.TAX", "세무조사 부재", "No tax audit", "진행·예정 세무조사·검증의 부재", (r"no.{0,60}(?:tax audit|examination)", r"세무조사.{0,40}(?:없|진행되지|받지)")),
    Leaf("RW.TAX.NO_DISPUTE", "RW.TAX", "조세분쟁 부재", "No tax dispute", "과세처분·이의·심판·소송 등 조세분쟁 부재", (r"no.{0,60}(?:tax claim|tax dispute|tax proceeding)", r"(?:조세|세무).{0,30}(?:분쟁|소송|심판|이의).{0,30}(?:없|아니)")),
    Leaf("RW.TAX.NO_LIEN", "RW.TAX", "조세담보권 부재", "No tax lien", "자산에 설정된 조세담보권·압류 부재", (r"no liens? for taxes", r"(?:조세|세금).{0,30}(?:담보권|압류).{0,30}(?:없|아니)")),
    Leaf("RW.TAX.NO_EXTENSION", "RW.TAX", "부과제척·신고기한 연장 부재", "No tax extension or waiver", "조세 신고기한·부과제척기간의 연장·포기 부재", (r"no.{0,50}(?:extension|waiver).{0,60}(?:tax|statute of limitations)", r"(?:신고기한|부과제척기간).{0,30}(?:연장|포기).{0,30}(?:없|아니)")),
    Leaf("RW.TAX.NO_TAX_SHARING", "RW.TAX", "조세배분계약 부재", "No tax sharing agreement", "조세배분·분담·면책계약상 의무 부재", (r"no.{0,60}(?:tax sharing|tax allocation|tax indemnity) agreement", r"(?:조세|세금).{0,30}(?:배분|분담|면책)계약.{0,30}(?:없|아니)")),
    Leaf("RW.TAX.NO_OTHER_JURISDICTION", "RW.TAX", "타 관할 과세의무 부재", "No other taxing jurisdiction", "미신고 관할의 납세·신고 의무 또는 고정사업장 부재", (r"no claim.{0,100}tax return.{0,80}jurisdiction", r"(?:고정사업장|다른 관할).{0,40}(?:납세|신고).{0,30}(?:없|아니)")),
    Leaf("RW.TAX.TRANSFER_PRICING", "RW.TAX", "이전가격 준수", "Transfer pricing", "특수관계인 거래의 정상가격·이전가격 문서 준수", (r"transfer pricing", r"(?:이전가격|정상가격)")),
    Leaf("RW.IP.OWNERSHIP", "RW.IP", "지식재산권 소유권", "IP ownership", "등록·미등록 지식재산권의 단독 소유권", (r"(?:owns|sole owner).{0,80}intellectual property", r"지식재산권.{0,40}(?:소유|권리자)")),
    Leaf("RW.IP.VALIDITY", "RW.IP", "지식재산권 유효성", "IP validity", "등록·출원 지식재산권의 유효성·존속과 수수료 납부", (r"intellectual property.{0,80}(?:valid|subsisting|in force)", r"지식재산권.{0,40}(?:유효|존속)")),
    Leaf("RW.IP.SUFFICIENCY", "RW.IP", "지식재산권 충분성", "IP sufficiency", "사업 영위에 필요한 지식재산권의 보유·사용가능성", (r"intellectual property.{0,100}(?:sufficient|necessary).{0,60}(?:business|operation)", r"사업.{0,30}필요.{0,30}지식재산권")),
    Leaf("RW.IP.NO_INFRINGEMENT", "RW.IP", "제3자 권리 비침해", "No infringement by company", "대상회사의 사업·제품이 제3자 지식재산권을 침해하지 않음", (r"(?:company|business).{0,80}(?:does not|has not).{0,30}infring", r"(?:대상회사|사업|제품).{0,30}제3자.{0,30}지식재산권.{0,30}(?:침해하지|침해한 사실 없)")),
    Leaf("RW.IP.NO_THIRD_PARTY_INFRINGEMENT", "RW.IP", "제3자의 권리침해 부재", "No third-party infringement", "제3자가 대상회사 지식재산권을 침해·도용하지 않음", (r"no third party.{0,80}(?:infring|misappropriat).{0,60}(?:company|owned) intellectual property", r"제3자.{0,30}대상회사.{0,30}지식재산권.{0,30}(?:침해|도용).{0,20}(?:없|아니)")),
    Leaf("RW.IP.LICENSES", "RW.IP", "지식재산 라이선스", "IP licenses", "인바운드·아웃바운드 라이선스의 목록·유효성·위반", (r"(?:inbound|outbound|intellectual property) licenses?", r"지식재산.{0,30}(?:라이선스|사용허락)")),
    Leaf("RW.IP.EMPLOYEE_ASSIGNMENT", "RW.IP", "임직원 발명·권리양도", "Employee IP assignment", "임직원·개발자의 비밀유지·발명·저작물 권리양도", (r"(?:employee|contractor).{0,100}(?:assign|assignment).{0,60}intellectual property", r"(?:임직원|개발자).{0,40}(?:직무발명|권리양도|저작권)")),
    Leaf("RW.IP.OPEN_SOURCE", "RW.IP", "오픈소스", "Open-source software", "오픈소스 사용·고지·소스공개 의무와 라이선스 준수", (r"open.?source software", r"오픈소스")),
    Leaf("RW.IP.TRADE_SECRETS", "RW.IP", "영업비밀 보호", "Trade secrets", "영업비밀의 비밀성 유지와 유출·부정사용 부재", (r"trade secrets?.{0,80}(?:confidential|protect|misappropriat)", r"영업비밀.{0,40}(?:보호|유출|비밀)")),
    Leaf("RW.ENVIRONMENT.COMPLIANCE", "RW.ENVIRONMENT", "환경법 준수", "Environmental compliance", "환경법령·기준 준수", (r"in compliance with.{0,50}environmental laws?", r"환경법령.{0,30}(?:준수|위반하지)")),
    Leaf("RW.ENVIRONMENT.PERMITS", "RW.ENVIRONMENT", "환경 인허가", "Environmental permits", "필요한 환경 인허가의 보유·유효성·준수", (r"environmental permits?", r"환경.{0,20}인허가")),
    Leaf("RW.ENVIRONMENT.NO_CONTAMINATION", "RW.ENVIRONMENT", "오염 부재", "No contamination", "토양·지하수·시설의 오염 부재", (r"no.{0,50}(?:contamination|contaminated)", r"(?:토양|지하수|시설).{0,30}오염.{0,30}(?:없|아니)")),
    Leaf("RW.ENVIRONMENT.HAZARDOUS_MATERIALS", "RW.ENVIRONMENT", "유해물질", "Hazardous materials", "유해·위험물질의 제조·사용·보관·배출·처리", (r"hazardous (?:substances|materials|waste)", r"(?:유해|위험)물질")),
    Leaf("RW.ENVIRONMENT.NO_CLAIMS", "RW.ENVIRONMENT", "환경청구·조사 부재", "No environmental claims", "환경 관련 청구·통지·조사·책임 부재", (r"no.{0,60}environmental (?:claim|notice|investigation|liability)", r"환경.{0,30}(?:청구|통지|조사|책임).{0,30}(?:없|아니)")),
    Leaf("RW.ENVIRONMENT.NO_REMEDIATION", "RW.ENVIRONMENT", "정화의무 부재", "No remediation obligation", "환경오염 조사·정화·복원 의무 부재", (r"no.{0,60}(?:remediation|cleanup) obligation", r"(?:정화|복원).{0,30}(?:의무|책임).{0,30}(?:없|아니)")),
    Leaf("RW.INSURANCE.IN_FORCE", "RW.INSURANCE", "보험 유효성", "Insurance in force", "보험계약의 유효한 존속과 보장", (r"insurance policies?.{0,80}(?:in force|valid|effective)", r"보험계약.{0,30}(?:유효|존속)")),
    Leaf("RW.INSURANCE.PREMIUMS_PAID", "RW.INSURANCE", "보험료 납부", "Insurance premiums paid", "납기 도래 보험료의 납부", (r"insurance premiums?.{0,50}(?:paid|due)", r"보험료.{0,30}(?:납부|미납)")),
    Leaf("RW.INSURANCE.NO_CANCELLATION_NOTICE", "RW.INSURANCE", "해지·갱신거절 통지 부재", "No insurance cancellation notice", "보험 해지·취소·갱신거절 통지 부재", (r"no.{0,60}(?:notice|threat).{0,50}(?:cancel|terminat|nonrenew).{0,50}insurance", r"보험.{0,30}(?:해지|취소|갱신거절).{0,30}통지.{0,20}(?:없|받지)")),
    Leaf("RW.INSURANCE.NO_CLAIMS", "RW.INSURANCE", "미결 보험청구 부재", "No outstanding insurance claims", "거절·분쟁·미결 상태의 보험청구 부재", (r"no.{0,60}(?:outstanding|pending|denied).{0,40}insurance claim", r"보험금.{0,30}(?:청구|분쟁|거절).{0,30}(?:없|아니)")),
    Leaf("RW.INSURANCE.ADEQUACY", "RW.INSURANCE", "보험보장 적정성", "Adequacy of insurance", "동종 사업상 통상적이고 충분한 보험보장", (r"insurance.{0,80}(?:adequate|sufficient|customary)", r"보험.{0,30}(?:충분|적정|통상)")),
    Leaf("RW.PERMITS.ALL_REQUIRED", "RW.PERMITS", "필수 인허가 보유", "All required permits", "사업 영위에 필요한 모든 인허가의 보유", (r"all (?:permits|licenses).{0,80}(?:necessary|required)", r"사업.{0,30}필요.{0,30}(?:인허가|허가).{0,20}(?:모두|전부)")),
    Leaf("RW.PERMITS.VALID", "RW.PERMITS", "인허가 유효성", "Permit validity", "인허가의 유효한 존속", (r"(?:permits|licenses).{0,80}(?:valid|in force|effective)", r"인허가.{0,30}(?:유효|존속)")),
    Leaf("RW.PERMITS.COMPLIANCE", "RW.PERMITS", "인허가 조건 준수", "Permit compliance", "인허가 조건·제한의 준수와 위반 부재", (r"in compliance with.{0,60}(?:permits|licenses)", r"인허가.{0,30}(?:조건|내용).{0,30}(?:준수|위반하지)")),
    Leaf("RW.PERMITS.NO_REVOCATION", "RW.PERMITS", "취소·정지 우려 부재", "No permit revocation", "인허가 취소·철회·정지·갱신거절 통지 부재", (r"no.{0,60}(?:revocation|suspension|withdrawal|nonrenewal).{0,60}(?:permit|license)", r"인허가.{0,30}(?:취소|정지|철회|갱신거절).{0,30}(?:없|통지받지)")),
    Leaf("RW.REAL_ESTATE.OWNED", "RW.REAL_ESTATE", "소유 부동산", "Owned real property", "소유 부동산 목록·권원·부담", (r"owned real propert", r"소유 부동산")),
    Leaf("RW.REAL_ESTATE.LEASED", "RW.REAL_ESTATE", "임차 부동산", "Leased real property", "임차 부동산과 임대차계약 현황", (r"leased real propert", r"임차 부동산")),
    Leaf("RW.REAL_ESTATE.LEASE_VALID", "RW.REAL_ESTATE", "임대차 유효성", "Lease validity", "부동산 임대차계약의 유효성·구속력", (r"(?:real property )?leases?.{0,80}(?:valid|binding|in force)", r"임대차계약.{0,30}(?:유효|구속)")),
    Leaf("RW.REAL_ESTATE.NO_DEFAULT", "RW.REAL_ESTATE", "임대차 위반 부재", "No lease default", "임대차계약상 위반·채무불이행 부재", (r"no.{0,60}(?:default|breach).{0,60}(?:lease|leased real property)", r"임대차.{0,30}(?:위반|채무불이행).{0,30}(?:없|아니)")),
    Leaf("RW.BENEFITS.PLAN_LIST", "RW.BENEFITS", "복리후생제도 목록", "Benefit plan list", "적용되는 복리후생·연금·보상제도의 완전한 목록", (r"(?:complete|correct) list.{0,80}(?:benefit|pension) plans?", r"(?:복리후생|퇴직연금).{0,30}(?:목록|내역).{0,30}(?:완전|정확)")),
    Leaf("RW.BENEFITS.COMPLIANCE", "RW.BENEFITS", "복리후생제도 준수", "Benefit plan compliance", "복리후생·연금제도의 법령·문서 준수", (r"benefit plans?.{0,80}in compliance", r"(?:복리후생|퇴직연금).{0,30}(?:법령|규정).{0,30}준수")),
    Leaf("RW.BENEFITS.FUNDING", "RW.BENEFITS", "적립·부담금 납부", "Benefit plan funding", "연금·급여제도의 적립 및 사용자 부담금 납부", (r"(?:contributions|funding).{0,80}(?:benefit|pension) plans?.{0,30}(?:paid|made)", r"(?:퇴직연금|복리후생).{0,30}(?:부담금|적립금).{0,30}(?:납부|적립)")),
    Leaf("RW.BENEFITS.NO_ACCELERATION", "RW.BENEFITS", "거래로 인한 급여 가속 부재", "No benefit acceleration", "거래로 인한 보상·급여 지급·가득 가속 또는 증액 부재", (r"transactions contemplated.{0,120}(?:accelerat|increase).{0,80}(?:benefit|compensation|vesting)", r"본건 거래.{0,50}(?:보상|급여|가득).{0,30}(?:가속|증가)")),
    Leaf("RW.BENEFITS.NO_280G_GROSSUP", "RW.BENEFITS", "280G·세금보전의무 부재", "No 280G or tax gross-up", "낙하산 지급과 임직원 세금 gross-up 의무 부재", (r"(?:280G|parachute payment|gross.up payment).{0,100}(?:benefit|service provider|employee)", r"(?:낙하산 지급|세금 보전).{0,40}(?:임직원|급여)")),
    Leaf("RW.PRODUCTS.NO_DEFECT", "RW.PRODUCTS", "제품결함 부재", "No product defects", "제품의 설계·제조·표시상 중요 결함 부재", (r"no.{0,60}(?:defect|defective).{0,40}(?:product|goods)", r"제품.{0,30}(?:결함|하자).{0,30}(?:없|아니)")),
    Leaf("RW.PRODUCTS.NO_RECALL", "RW.PRODUCTS", "리콜 부재", "No product recall", "제품 리콜·회수·안전통지의 부재", (r"no.{0,60}(?:recall|withdrawal).{0,40}products?", r"제품.{0,30}(?:리콜|회수).{0,30}(?:없|아니)")),
    Leaf("RW.PRODUCTS.WARRANTY", "RW.PRODUCTS", "제품보증", "Product warranty", "표준 제품보증과 비표준 보증·예상책임", (r"product warrant", r"제품보증")),
    Leaf("RW.PRODUCTS.NO_LIABILITY_CLAIM", "RW.PRODUCTS", "제품책임청구 부재", "No product liability claim", "제품책임·안전·하자 관련 청구 부재", (r"no.{0,60}product liability (?:claim|action)", r"제품책임.{0,30}(?:청구|소송).{0,30}(?:없|아니)")),
    Leaf("RW.CUSTOMERS_SUPPLIERS.NO_TERMINATION", "RW.CUSTOMERS_SUPPLIERS", "주요 거래처 이탈 부재", "No key counterparty termination", "주요 고객·공급업체의 거래중단·축소·조건변경 의사 부재", (r"(?:customer|supplier).{0,100}(?:terminate|cease|reduce).{0,60}business", r"주요 (?:고객|공급업체).{0,40}(?:중단|축소|종료).{0,30}(?:의사|통지|없)")),
    Leaf("RW.CUSTOMERS_SUPPLIERS.NO_DISPUTE", "RW.CUSTOMERS_SUPPLIERS", "주요 거래처 분쟁 부재", "No key counterparty dispute", "주요 고객·공급업체와의 중요 분쟁 부재", (r"no.{0,60}(?:dispute|controversy).{0,60}(?:customer|supplier)", r"주요 (?:고객|공급업체).{0,30}분쟁.{0,30}(?:없|아니)")),
    Leaf("RW.RELATED_PARTY.NO_TRANSACTION", "RW.RELATED_PARTY", "미공개 특수관계인 거래 부재", "No undisclosed related-party transaction", "공개된 것 외 특수관계인 거래·계약·채권채무 부재", (r"no.{0,60}(?:related party|affiliate) transaction", r"(?:특수관계인|관계회사).{0,30}거래.{0,30}(?:없|아니)")),
    Leaf("RW.RELATED_PARTY.NO_INTEREST", "RW.RELATED_PARTY", "특수관계인의 자산·거래처 이해관계 부재", "No related-party interest", "특수관계인의 회사 자산·고객·공급업체에 대한 이해관계 부재", (r"no.{0,60}(?:director|officer|affiliate).{0,80}(?:interest in|owns).{0,60}(?:asset|customer|supplier)", r"특수관계인.{0,30}(?:자산|고객|공급업체).{0,30}(?:이해관계|지분).{0,30}(?:없|아니)")),
    Leaf("RW.BROKERS.NO_FEE", "RW.BROKERS", "중개·자문수수료 의무 부재", "No broker or finder fee", "당사자 부담 브로커·파인더·투자은행 수수료 의무 부재", (r"no.{0,60}(?:broker|finder|investment bank).{0,60}(?:fee|commission)", r"(?:중개|자문)수수료.{0,30}(?:없|발생하지)")),
    Leaf("RW.PRIVACY.NO_BREACH", "RW.PRIVACY", "개인정보 침해사고 부재", "No privacy breach", "개인정보 유출·무단접근·침해사고 및 통지의무 부재", (r"no.{0,60}(?:data breach|security incident|unauthorized access)", r"(?:개인정보|데이터).{0,30}(?:유출|침해|무단접근).{0,30}(?:없|아니)")),
)


def _paragraphs(text: str):
    for line in text.splitlines():
        match = re.match(r"^\[¶(\d+)\]\s*(.*)$", line)
        if match:
            yield int(match.group(1)), match.group(2).strip()


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--review-json", type=Path, action="append", default=[])
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()

    keys = set(EXISTING_REVIEW_KEYS)
    selected_meta: dict[str, dict] = {}
    for path in args.review_json:
        data = json.loads(path.read_text(encoding="utf-8"))
        for row in data.get("documents", []):
            key = str(row["file_key"])
            keys.add(key)
            selected_meta[key] = row

    compiled = {
        leaf.taxonomy_id: tuple(re.compile(pattern, re.IGNORECASE) for pattern in leaf.patterns)
        for leaf in LEAVES
    }
    evidence: dict[str, list[dict]] = defaultdict(list)
    doc_hits: Counter[str] = Counter()
    with sqlite3.connect(args.out / "catalog.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        placeholders = ",".join("?" for _ in keys)
        rows = conn.execute(
            f"SELECT file_key,txt_path,ctype,lang,is_draft,path FROM files WHERE file_key IN ({placeholders})",
            tuple(sorted(keys)),
        )
        for row in rows:
            path = Path(row["txt_path"])
            if not path.is_absolute():
                path = args.out / path
            paras = list(_paragraphs(path.read_text(encoding="utf-8", errors="replace")))
            for leaf in LEAVES:
                for para, text in paras:
                    if any(pattern.search(text) for pattern in compiled[leaf.taxonomy_id]):
                        evidence[leaf.taxonomy_id].append(
                            {
                                "file_key": row["file_key"],
                                "para": para,
                                "ctype": row["ctype"],
                                "lang": row["lang"],
                                "is_draft": row["is_draft"],
                                "path": row["path"],
                                "verbatim": " ".join(text.split())[:320],
                            }
                        )
                        doc_hits[row["file_key"]] += 1
                        break

    payload = {
        "review_version": "rw-leaf-gap-320-1",
        "reviewed_document_count": len(keys),
        "candidate_count": len(LEAVES),
        "candidates": [
            {
                "taxonomy_id": leaf.taxonomy_id,
                "parent_id": leaf.parent_id,
                "canonical_ko": leaf.ko,
                "canonical_en": leaf.en,
                "definition": leaf.definition,
                "document_count": len(evidence[leaf.taxonomy_id]),
                "evidence": evidence[leaf.taxonomy_id][:5],
            }
            for leaf in LEAVES
        ],
        "representative_ranking": [
            {
                "file_key": key,
                "hit_count": count,
                **(selected_meta.get(key) or {}),
            }
            for key, count in doc_hits.most_common()
        ],
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "reviewed_document_count": len(keys),
                "candidate_count": len(LEAVES),
                "detected": sum(bool(evidence[leaf.taxonomy_id]) for leaf in LEAVES),
                "json": str(args.json),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
