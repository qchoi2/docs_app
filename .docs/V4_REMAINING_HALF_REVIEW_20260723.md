# V4 미검토 잔여 계약 절반 검토 및 taxonomy v7 보강

기준일: 2026-07-23

## 범위와 방식

- 기존 검토 320건을 제외한 검색가능 주요 M&A 계약
  `SPA|SSA|SHA|ATA/BTA`는 1,303건이다.
- 그 절반(올림)인 **652건, 50.04%**를 유형·언어 비율에 따라 결정적으로
  선정했다. 동일 거래 프로젝트는 먼저 한 버전씩 순환하고, 필요한 경우에만
  추가 버전을 포함했다.
- 각 문서의 추출 문단 전체를 49개 미보유 원자개념 패턴으로 스캔하고,
  정의·목차·단순 열거보다 실제 진술·의무·조건·지급·구제 문맥을 우선했다.
- 키워드 검출만으로 승격하지 않고 대표 문단을 부분 정독해 기존 taxonomy와
  겹치는지 확인했다. 따라서 이는 652건의 **범위보강 검토**이며, 각 계약의
  모든 조항을 완전색인했다는 의미는 아니다.

| 유형 / 언어 | 미검토 모집단 | 이번 검토 |
|---|---:|---:|
| ATA/BTA / 국문 | 83 | 42 |
| ATA/BTA / 국영문 | 14 | 7 |
| ATA/BTA / 영문 | 37 | 18 |
| SHA / 국문 | 214 | 107 |
| SHA / 영문 | 71 | 36 |
| SPA / 국문 | 392 | 196 |
| SPA / 영문 | 198 | 99 |
| SSA / 국문 | 154 | 77 |
| SSA / 영문 | 140 | 70 |

선정 문서는 SPA 295건, SSA 147건,
SHA 143건, ATA/BTA 67건이다.
언어는 국문 422건, 영문 223건,
국영문 7건이며, 체결/비초안 177건,
초안 228건, 판별불가 247건이다.

## 결과

- 검토 후보 49개 중 42개가 1건 이상 검출되었다.
- 문맥 검토 후 **36개 독립 원자노드**를 taxonomy version 7로 승격했다.
- taxonomy는 290노드·1,002 aliases에서
  **326노드·1,171 aliases**로 증가했다.
- 명확한 대표 근거가 있는 **36개 item/33개 문서**를
  `review_status=approved`, `body_status=partial`,
  `annex_status=not_evaluated`로 운영 DB에 적재했다.
- 감사 결과는 pass 33, review 0, error 0, issues 0이고 저장은
  stored 33, skipped 0이다.

| family | 추가 노드 | 운영 적재 item |
|---|---:|---:|
| RW | 9 | 9 |
| CP | 3 | 3 |
| COV | 8 | 8 |
| DEF | 5 | 5 |
| PAY | 4 | 4 |
| REM | 7 | 7 |

## 추가 노드

| taxonomy_id | parent | 국문명 | 영문명 |
|---|---|---|---|
| `COV.NON_DISPARAGEMENT` | `COV` | 비방금지 | Non-disparagement |
| `COV.PRIVACY_REMEDIATION` | `COV` | 개인정보 위반 시정 | Privacy compliance remediation |
| `COV.SHA.CASTING_VOTE` | `COV.SHA` | 의장 결정권 | Chair casting vote |
| `COV.SHA.QUORUM` | `COV.SHA` | 이사회·주주총회 정족수 | Board and shareholder quorum |
| `COV.SHA.REGISTRATION_RIGHTS` | `COV.SHA` | 등록청구권 | Registration rights |
| `COV.SHA.VOTING_PROXY` | `COV.SHA` | 의결권 위임·의결권계약 | Voting proxy and voting agreement |
| `COV.STANDSTILL` | `COV` | 스탠드스틸 | Standstill |
| `COV.TAX.REFUND` | `COV.TAX` | 조세환급 귀속·협력 | Tax refund allocation and cooperation |
| `CP.DISSENTERS_RIGHTS` | `CP` | 주식매수청구권 제한 | Dissenters' rights condition |
| `CP.ESCROW_AGREEMENT` | `CP` | 에스크로계약 체결·교부 | Escrow agreement delivery |
| `CP.KEY_EMPLOYEE` | `CP` | 핵심인력 재직·계약 | Key employee condition |
| `DEF.ACCOUNTING_PRINCIPLES` | `DEF` | 회계원칙 | Accounting principles |
| `DEF.DATA_ROOM` | `DEF` | 데이터룸 | Data room |
| `DEF.DEBT.CLOSING_NET_DEBT` | `DEF.DEBT` | 종결 순차입금 | Closing net debt |
| `DEF.DISCLOSURE_SCHEDULE` | `DEF` | 공개목록 | Disclosure schedule |
| `DEF.WORKING_CAPITAL.TARGET` | `DEF.WORKING_CAPITAL` | 목표운전자본 | Target working capital |
| `PAY.EARNOUT.GUARANTEE` | `PAY.EARNOUT` | 언아웃 지급보증 | Earn-out payment guarantee |
| `PAY.EQUITY_CONSIDERATION` | `PAY` | 주식·지분 대가 | Equity consideration |
| `PAY.MILESTONE` | `PAY` | 마일스톤 지급 | Milestone payment |
| `PAY.TRUE_UP_DEADLINE` | `PAY.COMPLETION_ACCOUNTS` | 정산금 지급기한 | True-up payment deadline |
| `REM.BASKET.DEDUCTIBLE` | `REM.BASKET` | 공제형 basket | Deductible basket |
| `REM.BASKET.TIPPING` | `REM.BASKET` | 소급형 basket | Tipping basket |
| `REM.CONSEQUENTIAL.PUNITIVE` | `REM.CONSEQUENTIAL` | 징벌적·제재적 손해 배제 | Punitive and exemplary damages exclusion |
| `REM.DIRECT_CLAIMS.CLAIMS_REPRESENTATIVE` | `REM.DIRECT_CLAIMS` | 청구대표자 절차 | Claims representative procedure |
| `REM.EXCLUSIVE_REMEDY.ESCROW_SOLE_RECOURSE` | `REM.EXCLUSIVE_REMEDY` | 에스크로 한정구제 | Escrow as sole recourse |
| `REM.EXCLUSIVE_REMEDY.RESCISSION_WAIVER` | `REM.EXCLUSIVE_REMEDY` | 취소·해제권 포기 | Rescission waiver |
| `REM.INDEMNITY.RECOVERY_PRIORITY` | `REM.INDEMNITY` | 배상재원 청구순서 | Recovery waterfall |
| `RW.COMPLIANCE.COMPETITION` | `RW.COMPLIANCE` | 경쟁법 준수 | Competition law compliance |
| `RW.COMPLIANCE.CUSTOMS` | `RW.COMPLIANCE` | 관세·수출입 준수 | Customs and trade compliance |
| `RW.FINANCIAL.DEBT_COMPLIANCE` | `RW.FINANCIAL` | 금융약정 준수 | Debt covenant compliance |
| `RW.FINANCIAL.NO_GOVERNMENT_GRANT_CLAWBACK` | `RW.FINANCIAL` | 보조금 환수의무 부재 | No government grant clawback |
| `RW.GOVERNMENT_CONTRACTS.COMPLIANCE` | `RW.GOVERNMENT_CONTRACTS` | 정부계약 준수 | Government contract compliance |
| `RW.IP.DOMAIN_NAMES` | `RW.IP` | 도메인명·온라인 계정 | Domain names and online accounts |
| `RW.LABOR.IMMIGRATION` | `RW.LABOR` | 외국인근로자·이민법 준수 | Immigration and work authorization compliance |
| `RW.REAL_ESTATE.NO_CONDEMNATION` | `RW.REAL_ESTATE` | 수용·철거 절차 부재 | No condemnation |
| `RW.REAL_ESTATE.ZONING` | `RW.REAL_ESTATE` | 용도지역·건축법 준수 | Zoning and building compliance |

## 승격하지 않은 검출 후보

| 후보 | 판단 |
|---|---|
| `RW.CORPORATE_GOVERNANCE.NO_POWER_OF_ATTORNEY` | 의결권 위임·종결서류·세무대리 위임이 혼재하여 독립 RW로 승격하지 않음 |
| `CP.STOCK_EXCHANGE_APPROVAL` | 대부분 IPO 추진확약·정의·reserved matter로서 CP 승인조건이 아님 |
| `CP.DATA_ROOM_DELIVERY` | 정의 또는 체결 후 자료제공으로, DEF.DATA_ROOM/COV.INFORMATION으로 처리 |
| `COV.LITIGATION_COOPERATION` | 대부분 제3자청구 방어절차로 REM.THIRD_PARTY_CLAIMS와 중복 |
| `COV.IT_MIGRATION` | 계약이전 동의·일반 전환지원 검출이 주로 발생하여 독립 IT migration 근거 부족 |
| `PAY.PRICE_ADJUSTMENT_COLLAR` | working capital의 문자열 cap을 상한으로 오인한 검출이어서 승격하지 않음 |

## 운영 DB에 적재한 근거 item

- `COV.NON_DISPARAGEMENT` — 매도인은 기본합의서에 따른 비방금지의무를 부담한다. `[e7ce3f8a57347935] ¶193`
- `COV.PRIVACY_REMEDIATION` — 회사들은 개인정보처리방침·동의·처리위탁계약·파기·안전성조치 등 개인정보 위반사항을 시정하여야 한다. `[789c633a97d092a7] ¶398`
- `COV.SHA.CASTING_VOTE` — 의장 또는 지정 이사는 이사회 가부동수 시 결정표를 가진다. `[797e7859fd1b93ab] ¶145`
- `COV.SHA.QUORUM` — 재직 이사 과반수의 출석이 이사회 정족수를 구성한다. `[167299b34d606e60] ¶231`
- `COV.SHA.REGISTRATION_RIGHTS` — 우선주주는 piggyback 등록권과 일정 시점 이후의 demand registration 권리를 가진다. `[329b70754c8bde87] ¶18`
- `COV.SHA.VOTING_PROXY` — 매도인은 2차 대상주식의 의결권 행사를 매수인에게 위임하고 필요한 위임장을 제공한다. `[068120c8242fcf70] ¶60`
- `COV.STANDSTILL` — 투자자와 관계인은 상대방 동의 없이 회사증권 취득·공개매수 등 지배권 행위를 하지 않는다. `[53503385c86ef92b] ¶274`
- `COV.TAX.REFUND` — 매수인은 원천징수세 환급을 매도인이 수령하도록 환급청구·수령·지급에 협력한다. `[ab02d34ba6746929] ¶237`
- `CP.DISSENTERS_RIGHTS` — 반대주주의 주식매수청구권 행사규모가 기준금액을 초과하지 않는 것이 종결조건이다. `[4f52b5c6f70ad5d0] ¶278`
- `CP.ESCROW_AGREEMENT` — 각 매도인이 서명한 에스크로계약 사본을 매수인에게 교부하여야 한다. `[1422d84ab8d3309f] ¶1376`
- `CP.KEY_EMPLOYEE` — 핵심인력은 거래종결일 현재 대상회사에 재직하여야 한다. `[abe00bf57680df34] ¶372`
- `DEF.ACCOUNTING_PRINCIPLES` — 회계원칙은 별첨에 기재된 회계정책·관행·방법론을 의미한다. `[7ea64578b32dc4d5] ¶845`
- `DEF.DATA_ROOM` — 데이터룸은 지정 가상 데이터룸에서 기준일 현재 제공되고 저장매체로 교부된 문서·정보의 범위이다. `[b9ca268b0dba03d3] ¶24`
- `DEF.DEBT.CLOSING_NET_DEBT` — 종결 순차입금은 거래종결일 현재의 순차입금을 의미한다. `[0b086d458c144b1f] ¶183`
- `DEF.DISCLOSURE_SCHEDULE` — 공개목록은 계약 별지에 첨부되고 종결 전 서면통지로 수정된 공개목록을 포함한다. `[4596477fe5af5444] ¶16`
- `DEF.WORKING_CAPITAL.TARGET` — 목표운전자본은 별지에 기재된 기준금액을 의미한다. `[0b086d458c144b1f] ¶229`
- `PAY.EARNOUT.GUARANTEE` — 매수인과 모회사는 유동성 사건별 언아웃 대금을 연대하여 지급한다. `[2e46d615d7904477] ¶81`
- `PAY.EQUITY_CONSIDERATION` — 거래종결 대가의 일부는 매수인 관계회사의 자기주식으로 지급된다. `[4dc2df305c7f400e] ¶343`
- `PAY.MILESTONE` — 사업가치 증대 마일스톤 달성 시 각 마일스톤별 추가 매매대금을 지급한다. `[38b1634bea851dbd] ¶66`
- `PAY.TRUE_UP_DEADLINE` — 사후 정산금은 정산금액 확정일부터 정해진 영업일 이내 지급한다. `[1f037d5d2639a0ca] ¶15`
- `REM.BASKET.DEDUCTIBLE` — 누적 손해가 기준액을 초과하면 그 초과분에 한하여 배상한다. `[4523d65ec8836daa] ¶175`
- `REM.BASKET.TIPPING` — 누적 손해가 기준액을 초과하면 기준액 이하를 포함한 손해 전액을 배상한다. `[2fc326c9c86d3acd] ¶152`
- `REM.CONSEQUENTIAL.PUNITIVE` — 각 당사자는 제재적 또는 징벌적 손해에 대한 배상책임을 부담하지 않는다. `[04abaca09c3aec13] ¶150`
- `REM.DIRECT_CLAIMS.CLAIMS_REPRESENTATIVE` — 복수 매수인의 손해배상 청구는 매수인대표자를 통하여 통지·행사한다. `[ceccbf5dd0817e5e] ¶188`
- `REM.EXCLUSIVE_REMEDY.ESCROW_SOLE_RECOURSE` — 가격조정 부족액에 대한 유일한 구제와 회수재원은 에스크로 자금으로 제한된다. `[d313b345e29510e8] ¶548`
- `REM.EXCLUSIVE_REMEDY.RESCISSION_WAIVER` — 매수인은 위반을 이유로 계약취소·대가감액·해지 취급을 할 권리를 포기한다. `[3c993d206977a606] ¶313`
- `REM.INDEMNITY.RECOVERY_PRIORITY` — 매수인측은 매도인에게 직접 청구하기 전에 에스크로계좌에서 먼저 회수하여야 한다. `[75d01740842662b3] ¶531`
- `RW.COMPLIANCE.COMPETITION` — 대상회사는 독점규제 및 공정거래법을 포함한 경쟁법을 중요한 측면에서 준수하였다. `[20f705c6cb680f13] ¶449`
- `RW.COMPLIANCE.CUSTOMS` — 대상회사는 관세 및 수출통제 관련 법령을 중요한 측면에서 준수하였다. `[14f9e70a3cc2d65a] ¶534`
- `RW.FINANCIAL.DEBT_COMPLIANCE` — 대상회사와 자회사는 차입·대출·신용공여의 재무약정을 준수한다. `[8de77a0a1239e26a] ¶77`
- `RW.FINANCIAL.NO_GOVERNMENT_GRANT_CLAWBACK` — 정부 지원금 조건을 준수하였고 그 반환의무가 없다. `[69f5e7b0be9164f4] ¶709`
- `RW.GOVERNMENT_CONTRACTS.COMPLIANCE` — 매도인과 자회사는 정부 원도급·하도급·입찰계약의 조건을 중요한 측면에서 준수하였다. `[7ea64578b32dc4d5] ¶407`
- `RW.IP.DOMAIN_NAMES` — 대상회사 등은 인터넷 도메인을 포함한 중요 지식재산권 내역을 제공하고 적법한 소유·사용권을 보유한다. `[bf0d051b54bbd083] ¶247`
- `RW.LABOR.IMMIGRATION` — 모든 근로자의 취업허가 서류가 구비되었고 적용 이민법을 준수하였다. `[7ea64578b32dc4d5] ¶391`
- `RW.REAL_ESTATE.NO_CONDEMNATION` — 소유 부동산에 예정된 수용·협의취득 등 유사 절차나 관련 서면통지가 없다. `[62f355e124ff00df] ¶386`
- `RW.REAL_ESTATE.ZONING` — 해당 부동산은 현재 용도·점유·건축과 관련된 환경·용도지역·토지이용 요건을 준수한다. `[1b8c393f95eea771] ¶155`

## 검증 및 한계

- 전체 V4 item은 기존 대표계약 131개를 포함해 167개,
  34개 문서이며 전부 approved 상태다.
- 이번 33개 문서는 확인된 문단만 `partial`로 저장했다. 따라서 해당 family의
  다른 item이 없다는 부재검색 근거로 사용할 수 없다.
- 본문 추출이 불가능한 전체 코퍼스의 empty 48건·error 1건과 unsupported
  41건은 이번 모집단에 포함하지 않았다.
- `eval_search.py` T1/T2 골든 평가: fail 0.
- 전체 회귀 테스트: 172 passed, 1 skipped.
