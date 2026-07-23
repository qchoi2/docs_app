"""Create a local, reviewable V4-1R2 test extraction for one Korean SPA.

The extraction is deliberately evidence-bound and deterministic.  It is a
quality-gate artifact for the representative document, not a general-purpose
production extractor and it does not call an external API.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


FILE_KEY = "0ddde0e62bd84e41"


# family, taxonomy_id, start, end, proposition, polarity
SPECS = (
    # Representations and warranties — sellers, target company and buyer.
    ("RW", "RW.AUTHORITY", 623, 626, "법인 매도인은 준거법에 따라 설립되어 유효하게 존속하고 계약상 의무 이행능력이 있다.", "affirmative"),
    ("RW", "RW.AUTHORITY", 627, 632, "개인 매도인은 성년자로 계약 체결·이행능력이 있고 도산상태에 있지 않다.", "affirmative"),
    ("RW", "RW.AUTHORITY", 633, 639, "매도인은 계약 체결·이행 권한이 있고 계약은 적법·유효하며 구속력과 집행가능성이 있다.", "affirmative"),
    ("RW", "RW.AUTHORITY", 636, 640, "계약 체결·이행은 매도인에게 적용되는 법률과 계약을 위반하지 않는다.", "negative"),
    ("RW", "RW.AUTHORITY", 640, 643, "매도인은 필요한 내부수권절차를 완료하였다.", "affirmative"),
    ("RW", "RW.CAPITALIZATION", 644, 648, "대상주식은 적법·유효하게 전액 납입·발행·전환되었다.", "affirmative"),
    ("RW", "RW.CAPITALIZATION", 644, 648, "매도인은 대상주식을 적법·유효하게 소유한다.", "affirmative"),
    ("RW", "RW.CAPITALIZATION", 644, 648, "대상주식에는 제한부담이 설정되어 있지 않다.", "none_exist"),
    ("RW", "RW.CAPITALIZATION", 644, 649, "대상주식 소유권은 종결 시 제한부담 없이 매수인에게 이전된다.", "affirmative"),
    ("RW", "RW.AUTHORITY", 649, 660, "본건 거래를 위하여 매도인이 취득할 필수 정부기관·제3자 승인 또는 신고가 없다.", "none_exist"),
    ("RW", "RW.LITIGATION", 649, 661, "본건 거래를 금지·제한하는 매도인 상대 소송이 없고 제기 우려도 없다.", "none_exist"),
    ("RW", "RW.AUTHORITY", 685, 691, "대상회사는 적법하게 존속하며 사업·자산 보유에 필요한 능력과 권한이 있다.", "affirmative"),
    ("RW", "RW.AUTHORITY", 685, 691, "대상회사에는 해산·청산·파산·회생절차 사유가 없다.", "none_exist"),
    ("RW", "RW.AUTHORITY", 688, 692, "대상회사는 계약 체결·이행 권한과 내부수권을 갖추었고 계약은 구속력·집행가능성이 있다.", "affirmative"),
    ("RW", "RW.AUTHORITY", 692, 699, "계약 체결·이행은 대상회사의 조직서류·결의·법령·인허가·계약을 위반하지 않는다.", "negative"),
    ("RW", "RW.ASSETS", 692, 699, "계약 체결·이행은 대상회사 주식 또는 자산에 담보권 설정을 초래하지 않는다.", "none_exist"),
    ("RW", "RW.CAPITALIZATION", 699, 707, "대상회사의 수권·발행주식과 종류별 주식수가 진술된 수량과 같다.", "affirmative"),
    ("RW", "RW.CAPITALIZATION", 699, 707, "공개된 주식매수선택권 외에 신주발행의무를 발생시키는 증권·권리가 없다.", "none_exist"),
    ("RW", "RW.CAPITALIZATION", 707, 710, "대상회사에는 자회사가 없다.", "none_exist"),
    ("RW", "RW.CONTRACTS", 707, 712, "대상회사 또는 매도인이 당사자인 대상회사 관련 주주간계약·투자계약이 없다.", "none_exist"),
    ("RW", "RW.FINANCIAL", 713, 719, "기준재무제표는 회계장부에 기초하여 K-GAAP에 따라 작성되었다.", "affirmative"),
    ("RW", "RW.FINANCIAL", 713, 724, "기준재무제표는 재무상태·경영성과·현금흐름 등을 중요성 관점에서 적정하게 표시한다.", "affirmative"),
    ("RW", "RW.FINANCIAL.NO_UNDISCLOSED_LIABILITIES", 719, 734, "허용된 예외 외에 재무제표 기재가 요구되는 부외·우발채무가 없다.", "none_exist"),
    ("RW", "RW.FINANCIAL", 725, 738, "재무제표 기준일 이후 대상회사는 통상영업을 하였고 중대한 부정적 영향이 발생하지 않았다.", "none_exist"),
    ("RW", "RW.COMPLIANCE", 735, 743, "대상회사는 적용 법령·정부기관 명령·인허가 조건을 중요한 측면에서 준수한다.", "affirmative"),
    ("RW", "RW.COMPLIANCE", 739, 743, "대상회사는 법령 위반 통지·고지를 받은 사실이 없다.", "none_exist"),
    ("RW", "RW.AUTHORITY", 744, 749, "대상회사는 계약 체결·이행에 필요한 정부기관·제3자 동의와 승인을 취득하였다.", "affirmative"),
    ("RW", "RW.PERMITS", 744, 753, "대상회사는 중요한 영업 인허가를 적법하게 보유하고 조건을 준수한다.", "affirmative"),
    ("RW", "RW.PERMITS", 744, 753, "인허가 정지·취소·무효 또는 갱신거절 사유가 없다.", "none_exist"),
    ("RW", "RW.CONTRACTS", 751, 763, "중요계약은 적법·유효하고 상대방의 구속력 있는 의무를 구성한다.", "affirmative"),
    ("RW", "RW.CONTRACTS", 754, 763, "대상회사와 상대방의 중요계약 채무불이행 사유가 없다.", "none_exist"),
    ("RW", "RW.CONTRACTS", 754, 763, "대상회사는 중요계약상 의무를 준수했고 해제·해지·취소 통지를 받지 않았다.", "affirmative"),
    ("RW", "RW.CONTRACTS", 754, 765, "대상회사는 이례적으로 부담되는 계약이나 사업제한·경업금지 제한을 받지 않는다.", "none_exist"),
    ("RW", "RW.RELATED_PARTY", 766, 773, "특수관계인 계약은 공정한 조건으로 체결되고 필요한 내부수권을 거쳤다.", "affirmative"),
    ("RW", "RW.RELATED_PARTY", 766, 776, "재무제표 기재 외에 주주·임직원과의 거래관계가 없다.", "none_exist"),
    ("RW", "RW.LITIGATION", 773, 777, "공개된 예외 외에 대상회사·임직원 관련 중요 소송과 제기 우려가 없다.", "none_exist"),
    ("RW", "RW.LABOR.NO_VIOLATION", 777, 789, "대상회사는 인사노무 법령·단체협약·취업규칙·근로계약을 중요한 측면에서 위반하지 않았다.", "none_exist"),
    ("RW", "RW.LABOR.WORKING_CONDITIONS", 777, 789, "대상회사는 임금·수당·상여·퇴직금·근로시간·휴일·휴가·복리후생 조건을 준수한다.", "affirmative"),
    ("RW", "RW.LABOR.NO_OFF_BOOK_WAGES", 777, 789, "내부규정 등에 없는 임금·이익 제공을 임직원에게 약속·합의한 사실이 없다.", "none_exist"),
    ("RW", "RW.LABOR.UNPAID_COMPENSATION", 789, 795, "지급기가 도래하였으나 미지급된 임직원 보수가 없다.", "none_exist"),
    ("RW", "RW.BENEFITS", 789, 795, "대상회사는 적법한 퇴직금제도를 유지하고 퇴직급여충당금을 적립하였다.", "affirmative"),
    ("RW", "RW.LABOR.COLLECTIVE", 789, 795, "노동 관련 소송과 그 제기 우려가 없다.", "none_exist"),
    ("RW", "RW.LABOR.CLASSIFICATION", 789, 799, "계약직·독립계약자 또는 정규직으로 간주될 수 있는 자가 없다.", "none_exist"),
    ("RW", "RW.BENEFITS", 796, 801, "임직원 보수·퇴직금은 법령·정관에 따라 적법하게 지급되었다.", "affirmative"),
    ("RW", "RW.TAX", 802, 807, "대상회사는 조세 신고·보고를 기한 내 적법하게 이행하였다.", "affirmative"),
    ("RW", "RW.TAX", 802, 807, "납기가 도래한 조세를 모두 납부하였다.", "affirmative"),
    ("RW", "RW.TAX", 802, 807, "원천징수 대상 세금을 원천징수하여 기한 내 납부하였다.", "affirmative"),
    ("RW", "RW.TAX", 808, 812, "진행 중인 조세 조사·감사·절차·소송과 그 통지·우려가 없다.", "none_exist"),
    ("RW", "RW.IP", 813, 820, "대상회사의 등록·출원·라이선스 지식재산권 목록이 공개되어 있다.", "affirmative"),
    ("RW", "RW.IP", 813, 827, "대상회사는 사업에 필요한 지식재산권을 제한부담 없이 적법·유효하게 보유·사용한다.", "affirmative"),
    ("RW", "RW.IP", 820, 827, "지식재산 등록·출원은 유효하고 무효·취소 사유나 임직원 보상청구권이 없다.", "none_exist"),
    ("RW", "RW.IP", 820, 833, "공유특허 관련 합의·법령을 준수하고 타인의 지식재산권을 침해하지 않는다.", "negative"),
    ("RW", "RW.IP", 828, 834, "지식재산권 침해·남용 주장이나 통지를 제3자로부터 받은 사실이 없다.", "none_exist"),
    ("RW", "RW.IP", 834, 842, "제3자의 대상회사 지식재산권 침해 사실과 우려가 없고 라이선스 계약은 유효하다.", "none_exist"),
    ("RW", "RW.IP", 842, 842, "직무발명자에게 정당한 보상을 지급했고 추가 보상의무가 없다.", "none_exist"),
    ("RW", "RW.IP", 843, 848, "대상회사는 영업비밀 보호조치를 취하였다.", "affirmative"),
    ("RW", "RW.ENVIRONMENT", 843, 855, "대상회사는 환경 인허가를 취득하고 환경법령·명령·약정을 준수한다.", "affirmative"),
    ("RW", "RW.ENVIRONMENT", 849, 855, "환경 위반 관련 소송·제재·시정·배상 요구와 통지·우려가 없다.", "none_exist"),
    ("RW", "RW.ENVIRONMENT", 856, 858, "소유·임차 부동산에서 환경법령에 저촉되는 유해물질 배출·방출이 없다.", "none_exist"),
    ("RW", "RW.REAL_ESTATE", 856, 874, "대상회사는 부동산·차량 등 유형자산의 적법한 소유권 또는 사용권을 보유한다.", "affirmative"),
    ("RW", "RW.ASSETS", 859, 874, "유형자산에는 제한부담이나 제3자 처분약정이 없다.", "none_exist"),
    ("RW", "RW.ASSETS", 859, 874, "보유·사용 자산은 현재 방식의 사업 수행에 필요한 자산을 구성한다.", "affirmative"),
    ("RW", "RW.ASSETS", 859, 874, "유형자산은 정상 운영상태로 유지·보수되어 의도된 용도로 사용할 수 있다.", "affirmative"),
    ("RW", "RW.ASSETS", 859, 874, "재고자산은 판매·사용 가능한 합리적 수준이며 장부에 적정하게 기재되어 있다.", "affirmative"),
    ("RW", "RW.REAL_ESTATE", 859, 875, "대상회사는 임대차계약을 준수하고 차임을 지급했으며 중대한 불이행이 없다.", "affirmative"),
    ("RW", "RW.INSURANCE", 875, 882, "대상회사는 법률상 요구되는 보험에 가입하였다.", "affirmative"),
    ("RW", "RW.INSURANCE", 875, 882, "보험계약은 적법·유효하고 보험료가 완납되었다.", "affirmative"),
    ("RW", "RW.INSURANCE", 875, 882, "보험은 사업 수행에 필요한 자산을 보험목적물로 한다.", "affirmative"),
    ("RW", "RW", 883, 891, "지적재산권 진술보장은 해당 전용 조항에 포함된 사항으로 한정된다.", "not_applicable"),
    ("RW", "RW", 892, 923, "환경·조세 진술보장과 대상회사 관련 진술보장의 범위 및 배타성이 별도로 제한된다.", "not_applicable"),
    ("RW", "RW.AUTHORITY", 929, 937, "매수인은 적법하게 존속하고 계약 체결·이행 능력과 권한을 보유한다.", "affirmative"),
    ("RW", "RW.AUTHORITY", 934, 941, "매수인은 계약 체결·이행에 필요한 내부수권절차를 완료하였다.", "affirmative"),
    ("RW", "RW.AUTHORITY", 938, 945, "필요적 정부승인 외에 매수인이 거래 전 취득할 정부승인이 없다.", "none_exist"),
    ("RW", "RW.AUTHORITY", 942, 949, "매수인은 매매대금·비용 지급에 충분한 자금 또는 조달능력이 있다.", "affirmative"),
    ("RW", "RW.LITIGATION", 946, 953, "매수인의 계약 이행을 중대하게 제한·지연할 소송과 제기 우려가 없다.", "none_exist"),
    ("RW", "RW.COMPLIANCE", 950, 964, "매수인은 중대하지 않은 예외 외에 관련 법령·명령을 준수한다.", "affirmative"),
    ("RW", "RW", 970, 976, "매수인은 실사자료·예측자료에 관하여 별도 진술보장이 제공되지 않음을 인정한다.", "not_applicable"),
    ("RW", "RW", 977, 980, "매수인의 진술보장은 계약에 명시된 내용으로 배타적으로 한정된다.", "not_applicable"),
    # Covenants.
    ("COV", "COV.CONFIDENTIALITY", 1004, 1012, "각 당사자는 계약·협상·대상회사 정보를 사전 서면동의 없이 제3자에게 공개하지 않는다.", "negative"),
    ("COV", "COV.CONFIDENTIALITY", 1004, 1013, "법령상 공개는 요구되는 최소 범위로 제한하고 공개 문서 사본을 상대방에게 제공한다.", "affirmative"),
    ("COV", "COV.CONFIDENTIALITY", 1013, 1039, "법령·정부기관·조세절차·기공개·사전동의·독자생성 정보에는 비밀유지 예외가 적용된다.", "not_applicable"),
    ("COV", "COV.CONFIDENTIALITY", 1020, 1039, "매도인은 종결 후 대상회사 정보를 비밀로 유지하고 승인 없이 공개·목적외 사용하지 않는다.", "negative"),
    ("COV", "COV.ORDINARY_COURSE", 1040, 1060, "매도인은 체결일부터 종결·해제 중 이른 날까지 대상회사가 통상영업을 유지하도록 한다.", "affirmative"),
    ("COV", "COV.RESTRICTED_ACTIONS", 1061, 1089, "매도인은 사전동의 없이 정관을 개정하지 않도록 한다.", "negative"),
    ("COV", "COV.RESTRICTED_ACTIONS", 1061, 1089, "매도인은 사전동의 없이 주식·전환증권 발행, 주식권리 변경 또는 감자를 하지 않도록 한다.", "negative"),
    ("COV", "COV.RESTRICTED_ACTIONS", 1061, 1089, "매도인은 사전동의 없이 합병·분할·사업양수도·해산·도산절차를 하지 않도록 한다.", "negative"),
    ("COV", "COV.RESTRICTED_ACTIONS", 1061, 1089, "매도인은 기준금액을 넘는 자산 처분·임대·라이선스를 하지 않도록 한다.", "negative"),
    ("COV", "COV.RESTRICTED_ACTIONS", 1061, 1089, "매도인은 중요계약의 체결·갱신거절·변경·종료와 중요 위반을 제한한다.", "negative"),
    ("COV", "COV.RESTRICTED_ACTIONS", 1090, 1096, "매도인은 기준금액 초과 채무 발생·변경·면제와 제3자 대여를 제한한다.", "negative"),
    ("COV", "COV.PERSONNEL", 1097, 1131, "매도인은 임직원 보상·복지의 중대한 증액·신설·개정·조기지급을 제한한다.", "negative"),
    ("COV", "COV.PERSONNEL", 1097, 1131, "매도인은 근로·퇴직·change-of-control 계약과 단체협약 변경을 제한한다.", "negative"),
    ("COV", "COV.PERSONNEL", 1097, 1131, "매도인은 특별상여 지급과 일정 보수 이상 임직원의 채용·해지를 제한한다.", "negative"),
    ("COV", "COV.RESTRICTED_ACTIONS", 1097, 1131, "대상회사의 중요 회계정책·기준·관행 변경을 제한한다.", "negative"),
    ("COV", "COV.RESTRICTED_ACTIONS", 1097, 1131, "주식 상환·매입과 배당·배분·자기주식 취득을 제한한다.", "negative"),
    ("COV", "COV.RESTRICTED_ACTIONS", 1097, 1132, "중요 소송·세무조사 합의, 세무신고·과세연도·세무원칙 변경과 조세환급권 포기를 제한한다.", "negative"),
    ("COV", "COV.RESTRICTED_ACTIONS", 1132, 1172, "특수관계인 계약·청구포기·채무인수·보증·신용공여를 제한한다.", "negative"),
    ("COV", "COV.RESTRICTED_ACTIONS", 1132, 1172, "신규사업·사업중단·자회사·합작회사·타법인 투자와 중대한 부정적 영향 행위를 제한한다.", "negative"),
    ("COV", "COV.PERSONNEL", 1132, 1172, "매도인은 핵심인력의 3년 계속근무·전직금지 확인서를 징구한다.", "affirmative"),
    ("COV", "COV.GOVERNANCE", 1173, 1183, "매도인은 기존 임원의 사임·청구포기 서류를 징구하고 매수인 지명 임원을 선임한다.", "affirmative"),
    ("COV", "COV.GOVERNANCE", 1184, 1187, "매도인은 종결을 조건으로 매수인 지정 내용의 정관변경을 완료한다.", "affirmative"),
    ("COV", "COV.EFFORTS_STANDARD", 1188, 1198, "각 당사자는 거래종결을 위해 합리적인 노력과 협력을 제공한다.", "affirmative"),
    ("COV", "COV.REGULATORY", 1188, 1199, "각 당사자는 정부기관·제3자 통지와 허가·동의·승인 취득에 최선의 노력을 다한다.", "affirmative"),
    ("COV", "COV.NOTICE_UPDATE", 1199, 1207, "당사자는 중대한 조치 또는 선행조건 불충족 예상 사실을 인지하면 즉시 통지하도록 합리적으로 노력한다.", "affirmative"),
    ("COV", "COV.INFORMATION", 1208, 1226, "매수인은 종결 후 3년 또는 법정기간 동안 회사·회계·법률·세무 등 장부와 기록을 보관한다.", "affirmative"),
    ("COV", "COV.INFORMATION", 1217, 1228, "매수인은 보험청구·조사·법령준수·재무제표 작성 등에 필요한 기록열람과 방어협력을 제공한다.", "affirmative"),
    ("COV", "COV.NON_COMPETE", 1229, 1242, "샘텍측 매도인은 종결 후 정해진 기간 동안 국내외 경쟁사업 영위·투자·자금지원을 하지 않는다.", "negative"),
    ("COV", "COV.NON_SOLICIT", 1229, 1243, "매도인은 종결 후 5년간 고객·공급자·거래처와 공개 예외 외 임직원을 유인·고용하지 않는다.", "negative"),
    ("COV", "COV.EXCLUSIVITY", 1243, 1249, "계약 존속 중 매도인은 제3자와 거래 협상·논의를 하거나 관련 자료를 제공하지 않는다.", "negative"),
    # Conditions precedent.
    ("CP", "CP.REPRESENTATIONS", 1256, 1264, "매도인 진술·보장은 체결일과 종결일 현재 중요한 면에서 진실·정확하여야 한다.", "affirmative"),
    ("CP", "CP.COVENANTS", 1261, 1267, "매도인은 종결일까지 이행할 확약과 의무를 중요한 면에서 모두 이행하여야 한다.", "affirmative"),
    ("CP", "CP.GOVERNMENT_APPROVAL", 1265, 1272, "매도인·대상회사에게 요구되는 정부 인허가를 취득하여야 한다.", "affirmative"),
    ("CP", "CP.THIRD_PARTY_CONSENT", 1265, 1272, "거래 전 요구되는 제3자 동의·승인·통지 절차를 완료하여야 한다.", "affirmative"),
    ("CP", "CP.NO_PROHIBITION", 1268, 1275, "거래를 지체·불법화·제한·금지하는 법률·명령·보전처분·소송이 없어야 한다.", "none_exist"),
    ("CP", "CP.NO_MAC", 1273, 1277, "체결일 이후 대상회사에 중대한 부정적 영향이 발생·발견되지 않아야 한다.", "none_exist"),
    ("CP", "CP.DELIVERABLE", 1278, 1285, "종결 의무를 이행하는 매도인들의 주식 합계가 완전희석 기준 총발행주식수의 95%를 초과해야 한다.", "affirmative"),
    ("CP", "CP.RESIGNATION", 1278, 1290, "대상회사 임원 전원의 사임·면제·포기서가 제공되고 매수인 지명 임원이 선임되어야 한다.", "affirmative"),
    ("CP", "CP.DELIVERABLE", 1286, 1290, "정관변경과 핵심인력 계속근무확인서 제공이 완료되어야 한다.", "affirmative"),
    ("CP", "CP.FINANCING", 1286, 1296, "매수인의 매매대금 조달과 투자심의위원회 승인이 완료되어야 한다.", "affirmative"),
    ("CP", "CP.REPRESENTATIONS", 1299, 1305, "매수인 진술·보장은 체결일과 종결일 현재 중요한 면에서 진실·정확하여야 한다.", "affirmative"),
    ("CP", "CP.COVENANTS", 1302, 1307, "매수인은 종결일까지 이행할 확약과 의무를 중요한 면에서 모두 이행하여야 한다.", "affirmative"),
    ("CP", "CP.GOVERNMENT_APPROVAL", 1306, 1311, "매수인에게 요구되는 정부 인허가를 취득하여야 한다.", "affirmative"),
    ("CP", "CP.THIRD_PARTY_CONSENT", 1306, 1311, "매수인에게 요구되는 제3자 동의·승인·통지 절차를 완료하여야 한다.", "affirmative"),
    ("CP", "CP.NO_PROHIBITION", 1308, 1317, "거래를 지체·불법화·제한·금지하는 법률·정부조치가 없어야 한다.", "none_exist"),
    ("CP", "CP.COVENANTS", 1318, 1319, "자신의 귀책·의무불이행·합리적 노력 부족으로 선행조건이 미충족된 당사자는 그 미충족을 주장할 수 없다.", "not_applicable"),
    # Payment and consideration.
    ("PAY", "PAY.BASE_PRICE", 532, 536, "대상주식 총 매매대금과 매도인별 대금은 별지 1에 따라 정해진다.", "affirmative"),
    ("PAY", "PAY.DEPOSIT", 537, 547, "매수인은 계약 체결 직후 매도인들을 위하여 계약금을 계약금계좌에 예치한다.", "affirmative"),
    ("PAY", "PAY.DEPOSIT", 537, 547, "계약금 반환의무를 담보하기 위하여 계좌 예금채권에 질권을 설정한다.", "affirmative"),
    ("PAY", "PAY.CLOSING_PAYMENT", 548, 559, "선행조건 충족·포기를 전제로 지정 거래종결일과 장소에서 거래를 종결한다.", "affirmative"),
    ("PAY", "PAY.CLOSING_PAYMENT", 592, 612, "거래종결 시 매수인은 매도인들에게 계약상 교부물과 지급의무를 이행한다.", "affirmative"),
    # Remedies and termination.
    ("REM", "REM.INDEMNITY", 1377, 1387, "대상회사 진술보장 위반 손해는 회사 손해에 해당 매도인측 지분율을 곱하여 산정한다.", "affirmative"),
    ("REM", "REM.INDEMNITY", 1383, 1387, "매도인 자체 진술보장 위반 손해는 개별 산정하고 확약위반 손해는 위반 매도인측 지분율로 산정한다.", "affirmative"),
    ("REM", "REM.INDEMNITY", 1410, 1416, "매수인은 자신의 진술보장 위반·확약 불이행으로 인한 매도인측 손해를 배상한다.", "affirmative"),
    ("REM", "REM.DE_MINIMIS", 1423, 1430, "회사 손해가 건별 0.5억원 미만이면 매도인의 배상의무가 발생하지 않는다.", "not_applicable"),
    ("REM", "REM.BASKET", 1423, 1430, "회사 손해 총액이 2억원 미만이면 배상의무가 발생하지 않고 초과 시 초과분을 배상한다.", "not_applicable"),
    ("REM", "REM.CAP", 1430, 1434, "매도인측 손해배상책임은 미확정 금액에 지분비율을 곱한 금액을 한도로 한다.", "affirmative"),
    ("REM", "REM.INDEMNITY", 1435, 1442, "종결 전 충당금 적립 손해와 종결 후 매수인측 행위·회계변경으로 발생한 손해는 배상대상에서 제외된다.", "not_applicable"),
    ("REM", "REM.SANDBAGGING", 1443, 1452, "매수인측이 종결 전 인지한 위반은 청구권을 포기한 것으로 보아 손해배상을 청구할 수 없다.", "not_applicable"),
    ("REM", "REM.MITIGATION", 1456, 1460, "매수인은 매도인 비용으로 손해 경감·최소화에 합리적인 노력을 다한다.", "affirmative"),
    ("REM", "REM.NO_DOUBLE_RECOVERY", 1461, 1463, "동일 손해에 대하여 중복 배상 또는 권리구제를 받을 수 없다.", "negative"),
    ("REM", "REM.INSURANCE_RECOVERY", 1466, 1480, "보험자·제3자로부터 실제 회수한 순액만큼 손해배상액을 감액하고 초과회수액을 반환한다.", "affirmative"),
    ("REM", "REM.SUBROGATION", 1481, 1491, "매도인이 지급의무를 전부 이행하면 보험자·제3자에 대한 권리를 지급범위 내에서 대위한다.", "affirmative"),
    ("REM", "REM.CONSEQUENTIAL", 1492, 1497, "우연·간접·결과·특별·징벌손해, 일실이익·가치감소·배수손해는 배상대상에서 제외된다.", "not_applicable"),
    ("REM", "REM.INSURANCE_RECOVERY", 1498, 1504, "매도인은 진술보장보험 보험료·자기부담금·보험자 부지급에 책임을 부담하지 않는다.", "negative"),
    ("REM", "REM.THIRD_PARTY_CLAIMS", 1509, 1526, "배상권리자는 청구 사실·근거·증거·예상액과 계산방법을 지체 없이 서면 통지한다.", "affirmative"),
    ("REM", "REM.THIRD_PARTY_CLAIMS", 1527, 1536, "배상의무자는 통지 수령 후 20영업일 내 통지하여 제3자 청구 방어를 승계·통제할 수 있다.", "affirmative"),
    ("REM", "REM.THIRD_PARTY_CLAIMS", 1533, 1544, "배상권리자는 제3자 청구 방어에 참여하고 배상의무자에게 협력·증인·자료를 제공한다.", "affirmative"),
    ("REM", "REM.THIRD_PARTY_CLAIMS", 1544, 1558, "배상의무자와 배상권리자는 상대방 동의 없이 제3자 청구를 합의·화해·인낙할 수 없다.", "negative"),
    ("REM", "REM.EXCLUSIVE_REMEDY", 1559, 1563, "종결 후 기망행위 예외를 제외하면 제8조 손해배상이 계약위반의 유일·배타적 구제이다.", "affirmative"),
    ("REM", "REM.TERMINATION", 1567, 1574, "당사자 서면합의 또는 최종 정부 금지조치가 있으면 귀책 없는 당사자가 계약을 해제할 수 있다.", "affirmative"),
    ("REM", "REM.TERMINATION", 1575, 1577, "장기종료일까지 종결되지 않으면 귀책 없는 당사자가 서면 통지로 해제할 수 있다.", "affirmative"),
    ("REM", "REM.TERMINATION", 1578, 1582, "선행조건 충족 후 매수인이 10영업일 내 종결하지 않으면 매도인이 해제할 수 있다.", "affirmative"),
    ("REM", "REM.TERMINATION", 1583, 1590, "계약금 미납 또는 매도인 미종결이 10영업일 지속되면 상대방이 해제할 수 있다.", "affirmative"),
    ("REM", "REM.CURE", 1591, 1596, "중요 위반이 시정불능이거나 요구 후 10영업일 내 시정되지 않으면 귀책 없는 당사자가 해제할 수 있다.", "affirmative"),
    ("REM", "REM.DEPOSIT_FORFEITURE", 1597, 1629, "해제 사유에 따라 계약금은 매도인에게 귀속되거나 매수인에게 반환된다.", "affirmative"),
)


DEF_SPECS = (
    ("계약", "DEF", 227, 228, "계약·약정·증서·양해·합의 및 변경사항의 정의"),
    ("계열회사", "DEF.AFFILIATE", 230, 238, "직접·간접 지배, 피지배 또는 공통지배 관계"),
    ("회계기준", "DEF", 240, 244, "대한민국 비상장회사 적용 일반기업회계기준"),
    ("기준재무제표", "DEF", 246, 249, "기준일 현재 재무상태표와 손익·자본·현금흐름 자료"),
    ("대리인", "DEF", 251, 253, "이사·경영자·임원·파트너·주주·구성원 및 수권대리인"),
    ("대상주식", "DEF", 255, 255, "전문에서 정한 대상주식"),
    ("대상회사", "DEF", 259, 259, "전문에서 정한 대상회사"),
    ("대상회사에 대한 중대한 부정적 영향", "DEF.MAE", 261, 275, "대상회사·사업·자산 등에 중대한 부정적 영향"),
    ("데이터룸", "DEF", 277, 284, "지정 온라인 데이터룸"),
    ("매도인간의 지분비율", "DEF", 290, 291, "별지 1 기재 대상주식 기준 매도인 지분비율"),
    ("매도인 공개사항", "DEF", 293, 299, "체결일 매수인에게 제공되는 진술보장 예외 공개사항"),
    ("매도인별 대상주식", "DEF", 300, 301, "별지 1 기재 각 매도인의 매도주식"),
    ("배상권리자", "DEF", 303, 305, "매수인측 또는 매도인측 배상권리자"),
    ("배상의무자", "DEF", 308, 313, "계약상 손해배상 청구를 받는 당사자"),
    ("명령", "DEF", 314, 314, "정부기관의 판결·명령·지침·중재판정·처분"),
    ("법령", "DEF", 316, 318, "유효한 헌법·법률·명령·규칙·조례 등"),
    ("법적절차", "DEF", 319, 320, "민형사·행정소송, 보전·중재·조정·조사절차"),
    ("부담", "DEF.ENCUMBRANCE", 322, 325, "소유·사용·의결·처분권 등에 대한 모든 제한"),
    ("세금·조세", "DEF.TAXES", 327, 329, "정부기관 부과 국세·지방세와 부대비용"),
    ("소송 등", "DEF", 331, 333, "소송·청구·보전·집행·중재·청문·조정 등"),
    ("영업일", "DEF.BUSINESS_DAY", 335, 335, "대한민국 시중은행의 영업일"),
    ("인·자", "DEF", 337, 338, "자연인·회사·조합·법인·단체·정부기관"),
    ("인허가", "DEF", 340, 342, "정부기관의 등록·보고·신고·통지"),
    ("재무상태표 기준일", "DEF", 344, 344, "2018년 6월 30일"),
    ("정부기관", "DEF", 346, 350, "국내외 정부·지방자치단체·부처·관청 등"),
    ("조세절차", "DEF", 352, 354, "조세 질의·감사·조사·다툼·불복절차"),
    ("주주간계약", "DEF", 356, 362, "주식 소유·의결·양도·신주인수 등에 관한 계약"),
    ("중요계약", "DEF", 364, 414, "금액·기간·사업영향 기준을 충족하는 중요 계약"),
    ("지적재산권", "DEF", 415, 420, "등록 여부와 무관한 산업재산·저작·노하우 등 권리"),
    ("통상적인 영업과정", "DEF.ORDINARY_COURSE", 421, 428, "과거 관행과 정상 영업범위에 부합하는 사업과정"),
    ("특수관계인", "DEF", 430, 431, "자본시장법 시행령상 특수관계인"),
    ("환경법령", "DEF", 433, 438, "대기·토양·수질·폐기물·안전·환경 관련 법령"),
    ("인지", "DEF.KNOWLEDGE", 512, 516, "지정 임직원의 실제 인식과 합리적 주의 시 알 수 있는 사항"),
)


KNOWN_DEF_IDS = {
    "DEF.AFFILIATE",
    "DEF.MAE",
    "DEF.ENCUMBRANCE",
    "DEF.TAXES",
    "DEF.BUSINESS_DAY",
    "DEF.ORDINARY_COURSE",
    "DEF.KNOWLEDGE",
}


def _paragraph_maps(payload: dict) -> tuple[dict[int, str], dict[str, dict[int, str]]]:
    body: dict[int, str] = {}
    for section in payload["family_sections"].values():
        for row in section["paragraphs"]:
            body[int(row["para"])] = str(row["text"])
    sources = {
        source["source_id"]: {
            int(row["para"]): str(row["text"]) for row in source["paragraphs"]
        }
        for source in payload["source_inventory"]
    }
    return body, sources


def _verbatim(rows: dict[int, str], start: int, end: int) -> str:
    return " ".join(rows[number] for number in range(start, end + 1) if number in rows)


def build_result(payload: dict) -> dict:
    body, source_maps = _paragraph_maps(payload)
    items = []
    candidates = []
    counters: dict[str, int] = {}

    def add(
        family: str,
        taxonomy_id: str,
        start: int,
        end: int,
        proposition: str,
        polarity: str,
        *,
        confidence: str = "high",
        review_status: str = "pending",
        source_kind: str = "body",
        source_id: str | None = None,
        related_item_ref: str | None = None,
        qualifier: dict | None = None,
        normalized: dict | None = None,
    ) -> str:
        counters[family] = counters.get(family, 0) + 1
        item_ref = f"{family}-{counters[family]:03d}"
        rows = body if source_kind == "body" else source_maps[source_id or ""]
        items.append(
            {
                "item_ref": item_ref,
                "family": family,
                "taxonomy_id": taxonomy_id,
                "proposition": proposition,
                "statement_polarity": polarity,
                "subject_role": None,
                "counterparty_role": None,
                "action": None,
                "object_type": None,
                "effective_time": None,
                "source_kind": source_kind,
                "source_id": source_id,
                "source_name": "계약서 본문" if source_kind == "body" else "별지 1",
                "source_ref": f"¶{start}" if start == end else f"¶{start}-¶{end}",
                "parent_clause_ref": None,
                "related_item_ref": related_item_ref,
                "qualifier": qualifier or {},
                "verbatim": _verbatim(rows, start, end),
                "loc_start": start,
                "loc_end": end,
                "normalized": normalized or {},
                "confidence": confidence,
                "review_status": review_status,
            }
        )
        return item_ref

    for spec in SPECS:
        add(*spec)

    candidates.extend(
        [
            {
                "proposed_ko": "진술보장 범위·배타성",
                "proposed_en": "Scope and exclusivity of representations",
                "family": "RW",
                "recommended_parent_id": "RW",
                "distinction_reason": "개별 사실 진술과 구별되는 진술보장 범위 제한·비의존·배타성 명제",
                "loc_start": 883,
                "loc_end": 923,
                "verbatim": _verbatim(body, 883, 923),
                "nearest_taxonomy_id": "RW",
            },
            {
                "proposed_ko": "재무제표 작성·적정표시",
                "proposed_en": "Financial statement preparation and fair presentation",
                "family": "RW",
                "recommended_parent_id": "RW.FINANCIAL",
                "distinction_reason": "장부 정확성·미공개채무와 구별되는 재무제표 작성기준 및 적정표시 명제",
                "loc_start": 713,
                "loc_end": 724,
                "verbatim": _verbatim(body, 713, 724),
                "nearest_taxonomy_id": "RW.FINANCIAL",
            },
            {
                "proposed_ko": "일반 법규준수",
                "proposed_en": "General compliance with laws",
                "family": "RW",
                "recommended_parent_id": "RW.COMPLIANCE",
                "distinction_reason": "반부패·제재·AML이 아닌 일반 영업 법령과 정부명령 준수 명제",
                "loc_start": 735,
                "loc_end": 743,
                "verbatim": _verbatim(body, 735, 743),
                "nearest_taxonomy_id": "RW.COMPLIANCE",
            },
        ]
    )

    for term, taxonomy_id, start, end, gist in DEF_SPECS:
        review = "pending"
        if taxonomy_id not in KNOWN_DEF_IDS:
            review = "needs_review"
            candidates.append(
                {
                    "proposed_ko": f"{term} 정의",
                    "proposed_en": None,
                    "family": "DEF",
                    "recommended_parent_id": "DEF",
                    "distinction_reason": "계약별로 독립 검색·비교할 정의 용어이나 현재 DEF taxonomy에 전용 노드가 없음",
                    "loc_start": start,
                    "loc_end": end,
                    "verbatim": _verbatim(body, start, end),
                    "nearest_taxonomy_id": "DEF",
                }
            )
        add(
            "DEF",
            taxonomy_id,
            start,
            end,
            f'본 계약은 "{term}"을 {gist}로 정의한다.',
            "affirmative",
            review_status=review,
            qualifier={"defined_term": term, "gist": gist},
        )

    for start, end, proposition in (
        (440, 482, "정의표에 열거된 용어는 각 지정 조항에서 정한 의미를 갖는다."),
        (483, 485, "본 계약의 해석에는 문맥상 달리 요구되지 않는 한 열거된 해석기준이 적용된다."),
        (486, 494, "서면에는 통지조항을 준수한 이메일이 포함되고 제공에는 데이터룸 게시가 포함된다."),
        (495, 498, "단수 표현은 복수를 포함하고 표제·제목은 계약 해석에 영향을 주지 않는다."),
        (499, 502, "일은 역일을 뜻하며 기한일이 비영업일이면 다음 영업일에 이행할 수 있다."),
        (503, 505, "계약·문서 참조는 수시로 개정되어 효력을 갖는 문서를 의미한다."),
        (506, 509, "별지·별첨·공개사항은 계약과 일체를 이루며 별도 계약이면 독립 효력을 갖는다."),
    ):
        add(
            "DEF",
            "DEF",
            start,
            end,
            proposition,
            "affirmative",
            review_status="needs_review",
        )

    # The available annex is a mixed table. Every row was evaluated; entries
    # whose OCR column alignment remains ambiguous are marked needs_review.
    rw_source = "ca087897b9a11b10"
    pay_source = "f76183c6043a9459"
    rw_schedule_ref = add(
        "RW",
        "RW.CAPITALIZATION",
        1811,
        1815,
        "별지 1은 CEP의 우선주 272,297주·보통주 648,102주와 지분율 36.69%를 기재한다.",
        "affirmative",
        source_kind="annex",
        source_id=rw_source,
        review_status="needs_review",
    )
    add(
        "RW",
        "RW.CAPITALIZATION",
        1812,
        1816,
        "별지 1은 Thiel의 우선주 68,634주·보통주 161,612주와 지분율 9.18%를 기재한다.",
        "affirmative",
        source_kind="annex",
        source_id=rw_source,
        review_status="needs_review",
    )
    for start, end, proposition in (
        (1817, 1819, "별지 1은 김재영의 보통주 27,044주와 지분율 1.08%를 기재한다."),
        (1820, 1822, "별지 1은 샘텍의 우선주 343,169주·보통주 471,817주와 지분율 32.49%를 기재한다."),
        (1823, 1825, "별지 1은 DHK의 보통주 260,196주와 지분율 10.37%를 기재한다."),
        (1826, 1828, "별지 1은 조윤희의 보통주 94,213주와 지분율 3.76%를 기재한다."),
        (1829, 1831, "별지 1은 황도원의 보통주 125,417주와 지분율 5.00%를 기재한다."),
        (1832, 1839, "별지 1은 조용석·문일권의 보통주 수와 지분율을 각각 기재한다."),
        (1834, 1850, "별지 1의 매도인간 지분비율 합계는 100%로 기재되어 있다."),
        (1851, 1854, "별지 1은 우선주 684,100주와 보통주 1,805,769주를 합계로 기재한다."),
    ):
        add(
            "RW",
            "RW.CAPITALIZATION",
            start,
            end,
            proposition,
            "affirmative",
            source_kind="annex",
            source_id=rw_source,
            review_status="needs_review",
        )
    pay_schedule_ref = add(
        "PAY",
        "PAY.ALLOCATION",
        1808,
        1810,
        "별지 1은 매도인별 대상주식·지분율·매매대금·계좌번호를 배분표 형식으로 정한다.",
        "affirmative",
        source_kind="annex",
        source_id=pay_source,
        review_status="needs_review",
    )
    for item in items:
        if item["item_ref"] == rw_schedule_ref:
            item["related_item_ref"] = pay_schedule_ref
        elif item["item_ref"] == pay_schedule_ref:
            item["related_item_ref"] = rw_schedule_ref
    pay_deposit = next(
        item for item in items if item["taxonomy_id"] == "PAY.DEPOSIT"
    )
    rem_deposit = next(
        item for item in items if item["taxonomy_id"] == "REM.DEPOSIT_FORFEITURE"
    )
    pay_deposit["related_item_ref"] = rem_deposit["item_ref"]
    rem_deposit["related_item_ref"] = pay_deposit["item_ref"]

    source_coverage = []
    for source in payload["source_inventory"]:
        status = "complete" if source["status_hint"] == "available" else "missing"
        source_coverage.append(
            {
                "family": source["family"],
                "source_id": source["source_id"],
                "source_kind": source["source_kind"],
                "source_name": source["source_name"],
                "source_ref": source["source_ref"],
                "storage_file_key": source.get("storage_file_key"),
                "status": status,
                "reason": (
                    "별지 1 전체 행을 평가·색인했으며 OCR 열 정렬이 모호한 개별 item은 needs_review로 표시"
                    if status == "complete"
                    else "본문이 참조하나 입력 코퍼스에 해당 공개사항이 없음"
                ),
            }
        )
    return {
        "file_key": FILE_KEY,
        "meta_schema_version": 4,
        "taxonomy_version": payload["taxonomy_version"],
        "extractor_version": "local-curated-ko-representative-1",
        "prompt_version": "v4-prompt-3",
        "items": items,
        "coverage": {
            "RW": {"body_status": "complete", "annex_status": "partial", "reason": "본문 전수 원자화; 공개사항 누락 및 별지 표 일부 OCR 확인 필요"},
            "CP": {"body_status": "complete", "annex_status": "no_annex", "reason": "선행조건 평가 범위에서 별도 참조자료 없음"},
            "COV": {"body_status": "complete", "annex_status": "partial", "reason": "확약 본문 전수 원자화; 매도인 공개사항 입력 누락"},
            "DEF": {"body_status": "complete", "annex_status": "partial", "reason": "정의 Article과 인지 정의 평가; 정의가 참조한 별지·공개사항은 입력 누락"},
            "PAY": {"body_status": "partial", "annex_status": "complete", "reason": "가격·계약금·종결지급 색인; 별지 1 전체 평가"},
            "REM": {"body_status": "complete", "annex_status": "partial", "reason": "손해배상 제한·청구절차·해제 및 계약금 효과 평가; 공개사항 입력 누락"},
        },
        "source_coverage": source_coverage,
        "taxonomy_candidates": candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if payload["file_key"] != FILE_KEY:
        raise SystemExit(f"expected {FILE_KEY}, got {payload['file_key']}")
    result = build_result(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "file_key": FILE_KEY,
                "items": len(result["items"]),
                "candidates": len(result["taxonomy_candidates"]),
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
