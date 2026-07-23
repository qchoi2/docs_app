# V4 잔여 651건 범위검토 및 taxonomy v8 보강

기준일: 2026-07-23

## 완료 범위

- 앞선 절반 652건을 제외한 정확한 보완집합 **651건**을 고정된 순서로 검토했다.
- 사용자 요청에 따라 1차 300건, 2차 351건으로 나눴고 두 배치의 file_key 중복은 0건이다.
- 대상은 추출본문과 doc_meta가 있는 `SPA|SSA|SHA|ATA/BTA` 주계약이다.
- 이 검토는 651건 전체의 범위·taxonomy gap 검토다. 각 문서의 모든 조항을 완전
  원자화한 full V4 추출은 아니며, 운영 DB에는 확인한 근거만 `partial`로 적재했다.

| offset | 문서 수 | 배치 산출물 |
|---:|---:|---|
| 0 | 300 | `cs_index\v4_remaining_rest_batch1_300_review.json` |
| 300 | 351 | `cs_index\v4_remaining_rest_batch2_351_review.json` |

분포는 SPA 295건, SSA 147건,
SHA 142건, ATA/BTA 67건이며,
국문 421건, 영문 223건,
국영문 7건이다. 체결·비초안 26건,
초안 521건, 판별불가 104건이다.

## 결과

- 신규 세분화 후보 65개를 검사했고 43개에서 표현 적중이 있었다.
- 문맥 및 기존 taxonomy 중복을 판정해 taxonomy version 8에
  **43개 노드(상위 `RW.IT` 1개 + 원자 leaf 42개)**를 추가했다.
- taxonomy는 **326 → 369 노드**,
  aliases는 **1,171 → 1390개**가 되었다.
- 근거가 확정된 **42 items / 26 documents**를 모두 `approved`로 운영 DB에
  적재했다. 해당 family의 `body_status=partial`, 모든 별지는
  `annex_status=not_evaluated`이므로 부재 증명에는 사용할 수 없다.
- 감사 결과 pass 26, review 0,
  error 0; 적재 stored 26,
  skipped 0이다.

| family | 추가 노드 | 운영 적재 item |
|---|---:|---:|
| RW | 8 | 7 |
| CP | 4 | 4 |
| COV | 12 | 12 |
| DEF | 2 | 2 |
| PAY | 3 | 3 |
| REM | 14 | 14 |

## 주요 중복·재분류 판정

| 후보 | 판정 | 최종 taxonomy | 사유 |
|---|---|---|---|
| `RW.CUSTOMERS_SUPPLIERS.CONCENTRATION` | rejected | - | 1건 적중 문단은 고객집중도 수치가 아니라 주요 거래관계 악화사유 부재 진술이어서 후보명과 불일치 |
| `RW.PRODUCTS.COMPLIANCE` | merged_existing | `RW.COMPLIANCE.GENERAL` | 제품만의 별도 규제준수보다 회사·사업·제품을 포괄하는 일반 준법진술 문맥 |
| `CP.RWI_BINDER` | split_reclassified | `COV.RWI.PROCUREMENT`, `COV.RWI.MAINTENANCE`, `COV.RWI.SUBROGATION_WAIVER` | 종결조건 하나가 아니라 보험 가입·유지·대위권 제한의 독립 확약으로 분해 |
| `CP.EMPLOYMENT_AGREEMENT` | merged_existing | `CP.KEY_EMPLOYEE` | 핵심인력 고용계약 체결은 기존 CP.KEY_EMPLOYEE의 명시적 포함범위 |
| `CP.NO_LITIGATION` | merged_existing | `CP.NO_PROHIBITION` | 주요 적중은 거래금지 명령·소송 또는 해제조항으로 기존 금지 부재 조건과 중복 |
| `COV.TAX.RETURNS` | reclassified | `COV.TAX.CONSISTENT_REPORTING` | 일반 세금신고 작성의무가 아니라 손해배상금 세무처리와 일치하는 신고의무 |
| `COV.ANTITRUST.DIVESTITURE` | reclassified | `COV.REGULATORY.DIVESTITURE` | 경쟁법상 인허가 노력의 구조적 시정조치 범위로 정규화 |
| `COV.ANTITRUST.HOLD_SEPARATE` | reclassified | `COV.REGULATORY.HOLD_SEPARATE` | 규제승인 노력 확약 하위의 분리운영 조치로 정규화 |
| `PAY.PRICE_ADJUSTMENT.COLLAR` | rejected | - | 2건 모두 중복계상 금지 또는 정의 문맥이고 실제 가격조정 상·하한이 아님 |
| `REM.ESCROW_RELEASE` | reclassified | `PAY.ESCROW.RELEASE` | 손해배상 원인보다 예치대금의 해제·분배 구조가 검색 핵심 |

## 추가 노드

| taxonomy_id | parent | 국문명 | 영문명 |
|---|---|---|---|
| `COV.EMPLOYEE_BENEFITS_CONTINUATION` | `COV.PERSONNEL` | 종업원 보상·복리후생 유지 | Employee compensation and benefits continuation |
| `COV.REGULATORY.DIVESTITURE` | `COV.REGULATORY` | 경쟁당국 시정조치·자산매각 | Antitrust divestiture commitment |
| `COV.REGULATORY.HOLD_SEPARATE` | `COV.REGULATORY` | 경쟁법상 분리운영 | Antitrust hold-separate commitment |
| `COV.RWI.MAINTENANCE` | `COV.RWI` | 진술보장보험 유지 | RWI policy maintenance |
| `COV.RWI.PROCUREMENT` | `COV.RWI` | 진술보장보험 가입·증권 교부 | RWI procurement and policy delivery |
| `COV.RWI.SUBROGATION_WAIVER` | `COV.RWI` | 진술보장보험 대위권 제한 | RWI subrogation waiver |
| `COV.SHA.AFFILIATE_TRANSFER` | `COV.SHA.TRANSFER` | 계열회사 허용양도 | Permitted affiliate transfer |
| `COV.SHA.ANTI_DILUTION` | `COV.SHA` | 희석방지권 | Anti-dilution protection |
| `COV.SHA.BUSINESS_PLAN_BUDGET` | `COV.SHA` | 사업계획·예산 승인 | Business plan and budget approval |
| `COV.TAX.AUDIT_CONTROL` | `COV.TAX` | 세무조사 대응 통제 | Tax audit control |
| `COV.TAX.CONSISTENT_REPORTING` | `COV.TAX` | 조세신고상 일관된 처리 | Consistent tax reporting |
| `COV.TAX.TRANSFER_TAX` | `COV.TAX` | 거래세 부담·신고 | Transfer-tax allocation and filing |
| `CP.ANCILLARY.RESTRICTIVE_COVENANT_AGREEMENT` | `CP.ANCILLARY` | 경업금지 등 제한약정 체결 | Restrictive covenant agreement execution |
| `CP.DEBT_RELEASE.LIEN_RELEASE` | `CP.DEBT_RELEASE` | 담보권 해지서류 | Lien release documents |
| `CP.DEBT_RELEASE.PAYOFF_LETTER` | `CP.DEBT_RELEASE` | 채무상환 확인서 | Payoff letter |
| `CP.GOVERNMENT_APPROVAL.FOREIGN_INVESTMENT` | `CP.GOVERNMENT_APPROVAL` | 외국인투자 승인·신고 | Foreign-investment clearance |
| `DEF.LEAKAGE.PERMITTED` | `DEF.LEAKAGE` | 허용누출 | Permitted leakage |
| `DEF.WORKING_CAPITAL.NET` | `DEF.WORKING_CAPITAL` | 순운전자본 | Net working capital |
| `PAY.EARNOUT.DISPUTE` | `PAY.EARNOUT` | 언아웃 산정 분쟁절차 | Earn-out dispute procedure |
| `PAY.ESCROW.RELEASE` | `PAY.ESCROW` | 에스크로 해제·분배 | Escrow release mechanics |
| `PAY.HOLDBACK` | `PAY` | 대금 유보 | Purchase-price holdback |
| `REM.CONSEQUENTIAL.DIMINUTION_IN_VALUE` | `REM.CONSEQUENTIAL` | 가치감소 손해 배제 | Diminution-in-value exclusion |
| `REM.CONSEQUENTIAL.LOST_PROFITS` | `REM.CONSEQUENTIAL` | 일실이익 배제 | Lost-profits exclusion |
| `REM.CONSEQUENTIAL.MULTIPLE_BASED` | `REM.CONSEQUENTIAL` | 배수기준 손해 배제 | Multiple-based damages exclusion |
| `REM.DIRECT_CLAIMS.NOTICE_CONTENT` | `REM.DIRECT_CLAIMS` | 직접청구 통지 기재사항 | Direct-claim notice contents |
| `REM.EXCLUSIVE_REMEDY.FRAUD_CARVEOUT` | `REM.EXCLUSIVE_REMEDY` | 사기 구제 예외 | Fraud carve-out from exclusive remedy |
| `REM.EXCLUSIVE_REMEDY.SPECIFIC_PERFORMANCE_CARVEOUT` | `REM.EXCLUSIVE_REMEDY` | 특정이행 구제 예외 | Specific-performance carve-out |
| `REM.INDEMNITY.COVENANT_BREACH` | `REM.INDEMNITY` | 확약 위반 손해배상 | Covenant-breach indemnity |
| `REM.INDEMNITY.EXCLUDED_LIABILITIES` | `REM.INDEMNITY` | 제외채무 손해배상 | Excluded-liabilities indemnity |
| `REM.INDEMNITY.RW_BREACH` | `REM.INDEMNITY` | 진술보장 위반 손해배상 | Representation-and-warranty breach indemnity |
| `REM.INDEMNITY.TAX` | `REM.INDEMNITY` | 조세 손해배상 | Tax indemnity |
| `REM.SURVIVAL.STATUTE_OF_LIMITATIONS` | `REM.SURVIVAL` | 법정 시효까지 존속 | Survival through statute of limitations |
| `REM.THIRD_PARTY_CLAIMS.COOPERATION` | `REM.THIRD_PARTY_CLAIMS` | 제3자청구 방어 협조 | Third-party claim defense cooperation |
| `REM.THIRD_PARTY_CLAIMS.DEFENSE_CONTROL` | `REM.THIRD_PARTY_CLAIMS` | 제3자청구 방어권 | Control of third-party claim defense |
| `REM.THIRD_PARTY_CLAIMS.SETTLEMENT_CONSENT` | `REM.THIRD_PARTY_CLAIMS` | 제3자청구 합의 동의 | Third-party claim settlement consent |
| `RW.ENVIRONMENT.NO_UNDERGROUND_STORAGE_TANKS` | `RW.ENVIRONMENT` | 지하저장탱크 없음 | No underground storage tanks |
| `RW.FINANCIAL.NO_OFF_BALANCE_SHEET` | `RW.FINANCIAL` | 부외부채 없음 | No off-balance-sheet liabilities |
| `RW.IT` | `RW` | IT 시스템 | Information technology systems |
| `RW.IT.DISASTER_RECOVERY` | `RW.IT` | 재해복구·업무연속성 | IT disaster recovery and business continuity |
| `RW.IT.SYSTEMS_SUFFICIENCY` | `RW.IT` | IT 시스템 충분성 | IT systems sufficiency |
| `RW.LABOR.NO_STRIKE` | `RW.LABOR` | 파업·쟁의행위 없음 | No strike or work stoppage |
| `RW.LABOR.NO_UNION_ORGANIZING` | `RW.LABOR` | 노동조합 조직화 없음 | No union organizing activity |
| `RW.TAX.NO_PERMANENT_ESTABLISHMENT` | `RW.TAX` | 해외 고정사업장 없음 | No foreign permanent establishment |

## 운영 DB 적재 근거

- `COV.EMPLOYEE_BENEFITS_CONTINUATION` — 매수인은 종결 후 일정 기간 대상회사 직원의 고용과 보상·복리후생을 유지하도록 하여야 한다. `[1289f43bbd364dcd] ¶235`
- `COV.REGULATORY.DIVESTITURE` — 매수인은 기업결합승인을 위해 구조적 시정조치가 아닌 승인조건을 제안·협상·약속하고 이행하여야 한다. `[e0e9acb2e97d2878] ¶205`
- `COV.REGULATORY.HOLD_SEPARATE` — 당사자는 거래금지 장애를 제거하기 위해 자산매각·분리보유 등 경쟁법상 조치를 제안하고 수용하여야 한다. `[127844bc34157180] ¶151`
- `COV.RWI.MAINTENANCE` — 매수인은 조건부 바인더의 조건을 충족하여 진술보장보험을 유효하게 유지하여야 한다. `[0df3b7a8cf1ba31f] ¶528`
- `COV.RWI.PROCUREMENT` — 매수인은 종결 전 진술보장보험에 가입하고 종결일에 보험증권 사본을 매도인에게 교부하여야 한다. `[5b77c491f91848c7] ¶168`
- `COV.RWI.SUBROGATION_WAIVER` — 매수인은 보험자가 매도인·대상회사에 구상권이나 대위권을 행사하지 못하는 조건으로 진술보장보험에 가입하여야 한다. `[ad00e647fb73f30c] ¶157`
- `COV.SHA.AFFILIATE_TRANSFER` — 투자자와 지배주주는 계열회사에 주식을 양도할 수 있고 양수인은 계약에 서면으로 구속되어야 한다. `[1eb4538a9df9abbb] ¶114`
- `COV.SHA.ANTI_DILUTION` — 우선주 전환 전 더 낮은 발행가의 신주·주식연계사채가 발행되면 가중평균 방식으로 전환가액을 조정한다. `[7101ea75c598ac35] ¶107`
- `COV.SHA.BUSINESS_PLAN_BUDGET` — 연간 시설운영예산과 사업계획은 이사회 특별다수결 승인을 받아야 한다. `[5c011a0e170a38c7] ¶213`
- `COV.TAX.AUDIT_CONTROL` — 배상권리자는 관련 세무조사를 통지하고 배상의무자는 비용을 부담하여 그 방어를 단독으로 통제한다. `[927a0d97d97af639] ¶504`
- `COV.TAX.CONSISTENT_REPORTING` — 당사자들은 손해배상금을 세무상 인수가격 조정으로 취급하고 그와 일치하는 세금신고를 하여야 한다. `[127844bc34157180] ¶209`
- `COV.TAX.TRANSFER_TAX` — 양도세는 매도인이, 취득세·자산등록세는 매수인이 납부하고 기타 거래세는 법률상 부과받는 당사자가 부담한다. `[ced966fb03a5de65] ¶187`
- `CP.ANCILLARY.RESTRICTIVE_COVENANT_AGREEMENT` — 회사는 경업금지의무자들로부터 퇴사제한·경업금지 약정서에 서명을 받아 투자자에게 교부하여야 한다. `[0b73c004dc993cbd] ¶44`
- `CP.DEBT_RELEASE.LIEN_RELEASE` — 양도인은 대상자산의 제한부담을 해소하는 담보권자 동의서·담보말소계약서 등 서류를 교부하여야 한다. `[c163e7d36d6264df] ¶134`
- `CP.DEBT_RELEASE.PAYOFF_LETTER` — 매도인은 종결일 지급대상 거래비용의 금액과 송금정보를 확인하는 payoff letter를 교부하여야 한다. `[8a88d300b2815935] ¶215`
- `CP.GOVERNMENT_APPROVAL.FOREIGN_INVESTMENT` — 외국인투자촉진법상 외국인투자신고 수리가 추가출자 거래종결의 선행조건이다. `[8b1417ad848b3bb2] ¶40`
- `DEF.LEAKAGE.PERMITTED` — 허용누출은 locked-box 기준일 직후부터 종결일까지 허용되는 특정 지급·거래를 의미한다. `[6056f50af3ee0a9f] ¶157`
- `DEF.WORKING_CAPITAL.NET` — 순운전자본은 매출채권과 재고 등을 더하고 매입채무와 기타 유동부채 등을 차감하여 K-GAAP에 따라 계산한다. `[6b490cb70a9e2d62] ¶163`
- `PAY.EARNOUT.DISPUTE` — 기관매도인이 언아웃 명세서에 이의가 있으면 15영업일 내 분쟁금액·성격·근거를 서면 통지하여야 한다. `[73613d49cf1d8b27] ¶444`
- `PAY.ESCROW.RELEASE` — 에스크로기간 만료 후 미확정 청구금액을 제외한 잔액과 이자를 매도인이 인출할 수 있다. `[5b7dbce4644ff76d] ¶196`
- `PAY.HOLDBACK` — 종결 시 기본대금에서 사후조정 holdback 금액을 차감한 순대금을 지급한다. `[608947db630584c4] ¶81`
- `REM.CONSEQUENTIAL.DIMINUTION_IN_VALUE` — 배상의무자는 가치감소 방식으로 산정한 손해를 부담하지 않는다. `[2d4a3a3f9ad4c7bf] ¶408`
- `REM.CONSEQUENTIAL.LOST_PROFITS` — 배상의무자는 장래 수익·이익·소득의 상실에 대한 손해를 부담하지 않는다. `[2d4a3a3f9ad4c7bf] ¶408`
- `REM.CONSEQUENTIAL.MULTIPLE_BASED` — 배상의무자는 이익·매출 기타 성과지표의 배수를 적용해 산정한 손해를 부담하지 않는다. `[2d4a3a3f9ad4c7bf] ¶408`
- `REM.DIRECT_CLAIMS.NOTICE_CONTENT` — 손해배상청구 통지에는 이용 가능한 정보에 기초한 청구 근거와 세부사항 및 중요 제3자 통지를 포함하여야 한다. `[2a85f1dd1f73b0e2] ¶200`
- `REM.EXCLUSIVE_REMEDY.FRAUD_CARVEOUT` — 배타적 구제 제한은 사기·중과실·고의적 위법행위·고의적 허위진술에는 적용되지 않는다. `[127844bc34157180] ¶202`
- `REM.EXCLUSIVE_REMEDY.SPECIFIC_PERFORMANCE_CARVEOUT` — 배타적 구제 조항은 당사자가 계약상 확약의 특정이행을 청구하는 것을 제한하지 않는다. `[127844bc34157180] ¶202`
- `REM.INDEMNITY.COVENANT_BREACH` — 매도인은 계약상 의무·약속·확약의 위반으로 발생한 손해를 매수인에게 배상한다. `[2a85f1dd1f73b0e2] ¶182`
- `REM.INDEMNITY.EXCLUDED_LIABILITIES` — 매도인은 제외채무로 발생한 손해를 매수인에게 배상한다. `[2a85f1dd1f73b0e2] ¶182`
- `REM.INDEMNITY.RW_BREACH` — 매도인은 자신의 진술보장의 부정확·불완전·위반으로 발생한 손해를 매수인에게 배상한다. `[2a85f1dd1f73b0e2] ¶182`
- `REM.INDEMNITY.TAX` — 매도인은 종결 전 과세기간과 straddle period의 종결 전 부분에 귀속되는 미납세금으로부터 매수인을 면책한다. `[8a88d300b2815935] ¶427`
- `REM.SURVIVAL.STATUTE_OF_LIMITATIONS` — 특정 진술보장은 적용되는 법정 소멸시효 기간 동안 존속한다. `[2a85f1dd1f73b0e2] ¶184`
- `REM.THIRD_PARTY_CLAIMS.COOPERATION` — 배상권리자는 제3자청구 방어를 위해 관련 문서를 보존하고 합리적 열람·복사 요청에 협조하여야 한다. `[127844bc34157180] ¶207`
- `REM.THIRD_PARTY_CLAIMS.DEFENSE_CONTROL` — 배상의무자는 통지 수령 후 제3자청구의 방어에 참여하거나 이를 인수·통제할 수 있다. `[127844bc34157180] ¶206`
- `REM.THIRD_PARTY_CLAIMS.SETTLEMENT_CONSENT` — 배상의무자는 완전면책 조건을 충족하거나 배상권리자의 서면동의를 받아야 제3자청구를 합의할 수 있다. `[127844bc34157180] ¶206`
- `RW.ENVIRONMENT.NO_UNDERGROUND_STORAGE_TANKS` — 대상 부동산의 지상 또는 지하에 지하저장탱크가 존재하지 않는다고 진술한다. `[7f60095f191b3e04] ¶47`
- `RW.FINANCIAL.NO_OFF_BALANCE_SHEET` — 재무제표와 통상과정 장부에 반영된 채무 외 부외부채·우발채무가 없다고 진술한다. `[3d6e2bcbe565f412] ¶236`
- `RW.IT.DISASTER_RECOVERY` — 중대한 IT 손상 시 사업을 계속할 수 있는 문서화된 재해복구계획을 갖추었다고 진술한다. `[198595774b9d19ed] ¶327`
- `RW.IT.SYSTEMS_SUFFICIENCY` — IT 시스템이 현재 사업을 독립적으로 운영하기에 충분하고 요구되는 방식으로 작동한다고 진술한다. `[6b490cb70a9e2d62] ¶357`
- `RW.LABOR.NO_STRIKE` — 대상회사에 중대한 영향을 미치는 파업·태업·작업중단 등이 진행 중이거나 위협되지 않았다고 진술한다. `[a3cad0bc63f7fa08] ¶226`
- `RW.LABOR.NO_UNION_ORGANIZING` — 사업의 직원과 관련한 노동조합 조직화 노력이 현재 또는 최근 2년 내 없었다고 진술한다. `[ced966fb03a5de65] ¶152`
- `RW.TAX.NO_PERMANENT_ESTABLISHMENT` — 설립지 외 관할의 고정사업장·과세상 존재로 인한 납세의무가 없다고 진술한다. `[198595774b9d19ed] ¶301`

## 운영 DB 누적 상태

- 총 V4 item 209개 / 60개 문서.
- approved item 209개.
- 이번 26개 문서는 부분 정독 근거만 저장했으므로, 같은 family의 다른 item이
  없다는 부재 근거로 사용할 수 없다.
