# V4 색인범위 검토 — 한국·미국형 M&A 계약 20건

_검토일: 2026-07-23. V3 승인 메타와 해당 조항·별지 범위만 부분 정독했으며 유료 API는 사용하지 않았다._

## 표본

| 구분 | file_key | 유형·상태 | 관찰 포인트 |
|---|---|---|---|
| 한국 | 0ddde0e62bd84e41 | SPA, 매수인 markup | 계약금 10%·잔금, 공개사항, 선행조건·확약 [0ddde0e62bd84e41] |
| 한국 | ac3103e193f693ed | SPA, 체결본 | 계약금 5%·잔금, 사후정산, 사외유출 감액, 정량 MAE [ac3103e193f693ed] |
| 한국 | 3c86175c4821fa83 | SPA, 체결본 | 종결일 계좌이체, 동의취득, 배상·해제 [3c86175c4821fa83] |
| 한국 | 2a08ef8b2699dca5 | SPA, 초안 | 계약금 10%·잔금, 필요적 승인, 공개사항 [2a08ef8b2699dca5] |
| 한국 | b324cb8bdf00015a | SSA, 체결본 | 신주수·주당가격·납입총액, MAE, extensive covenants [b324cb8bdf00015a] |
| 한국 | 613cba772f0f4b93 | SSA, 체결본 | 신주인수대금 현금납입, 종결조건 [613cba772f0f4b93] |
| 한국 | 660fc9d64566ba0e | SSA, markup | SSA 체결본 대비 협상 변이, 별지 참조 [660fc9d64566ba0e] |
| 한국 | a5da55951cfdabfb | SHA, 초안 | 별도 SSA 투자금액 참조, 배당·이사지명·양도제한 [a5da55951cfdabfb] |
| 한국 | 3b35ef6d54cdb6e1 | SHA, 체결본 | reserved matters, ROFR, tag/drag, put, 이사지명 [3b35ef6d54cdb6e1] |
| 한국 | f4fe4022e47b4f21 | SHA, 체결본 | 기존 SHA·신규 SSA 연결, 가입·이행 확약 [f4fe4022e47b4f21] |
| 한국 | b6fd6ff14e51e05f | BTA, 체결본 | 사업/지분 대금 배분, 계약금·잔금, 자산·부채·임직원 승계 [b6fd6ff14e51e05f] |
| 한국 | 753aeef4b323e391 | SHA, 초안 | drag/put/call, 정보권, 동의사항, 강한 exit 구조 [753aeef4b323e391] |
| 미국형 | a51842fc51010f69 | SPA, 체결본 | base price·post-closing adjustment·escrow·tax indemnity·disclosure schedules [a51842fc51010f69] |
| 미국형 | dbccf24bc86783f4 | SPA, buyer markup | estimated/final price, NWC·debt·cash·expenses adjustment, rollover, special indemnity [dbccf24bc86783f4] |
| 미국형 | 5acc3ac91d0f354b | Seller Disclosure Letter | 본계약과 분리된 disclosure schedule 자체가 독립 파일 [5acc3ac91d0f354b] |
| 미국형 | 82832addae042265 | SHA, markup | tag/drag·ROFR·put·정보권·reserved matters [82832addae042265] |
| 미국형 | 0df5e9d7e1e7c893 | SHA, 체결본 | drag threshold·현금대가·OIP/수익률 조건 [0df5e9d7e1e7c893] |
| 미국형 | 5853fe0540a72d6c | SHA, 체결본 | Schedule A 주주, 별도 SSA, governance/exit covenants [5853fe0540a72d6c] |
| 미국형 | 1776e6208de13ba7 | Company Disclosure Letter | SSA 본문과 분리된 회사 공개서한 [1776e6208de13ba7] |
| 혼합 | 973d43e89040fb57 | BTA, 국영문 | 자산·채무 정의, 달러 지급 참조, 부록 중심 구조 [973d43e89040fb57] |

## 반복적으로 확인된 색인축

### DEF — 계약별 정의

- MAE/MAC: 정성 정의와 순자산·매출 등 정량 threshold를 분리한다.
- Knowledge: 실제 인식/합리적 조사/지정인의 인식 범위를 분리한다.
- Permitted Lien·Encumbrance, Ordinary Course, Affiliate, Business Day.
- Losses, Taxes, Debt, Cash, Working Capital, Transaction Expenses.
- Fundamental Representations, Fraud, Transaction Documents.
- 정의는 같은 개념 taxonomy 아래 계약별 정의문·포함·제외·수치·참조조항을 별도 item으로 보존한다.

### PAY — 대금·지급구조

- 한국형: 계약금·중도금·잔금, 종결일 계좌이체, 계약금 반환/귀속, 부가세, 자산별 대금배분.
- 미국형: Base/Estimated/Final Purchase Price, closing payment, NWC·debt·cash·expense adjustment,
  escrow, holdback, deferred payment, rollover, earn-out.
- 지급 단계마다 payer/payee, 금액·비율, 통화, 지급시점, 조건, 계좌/지급수단, 환율, 상계 가능성을 원자화한다.

### REM — 위반·구제

- indemnity 대상, cap, basket/tipping/deductible, de minimis, survival, special indemnity.
- 위약벌, 위약금/손해배상액의 예정, break/termination fee, 계약금 몰취·배액상환·반환.
- exclusive remedy, specific performance, mitigation, no double recovery, set-off, third-party claims.
- 동일 계약금 문구가 지급과 구제 기능을 함께 가지면 PAY와 REM item을 각각 만들고 연결한다.

### COV — 확약

- SPA/SSA: ordinary course, restricted actions(자산처분·차입·배당·인사·계약·소송합의·조세선택),
  access/information, approvals/consents, confidentiality/publicity, employee transfer,
  non-compete/non-solicit, further assurances, records/tax cooperation.
- SHA: board nomination, reserved matters, information rights, funding, transfer restrictions,
  ROFR/tag/drag, exit/IPO cooperation, put/call 이행.
- 하나의 조항에 여러 작위·부작위가 열거되면 각각 별도 item으로 저장한다.

### CP — 선행조건

- R&W bring-down은 fundamental/general과 정확성 기준(all respects/material respects/MAE)을 분리한다.
- covenant performance, government approval/filing, third-party consent, no injunction/no MAE,
  financing, restructuring, ancillary agreement execution, deliverables를 각각 원자화한다.

## V4 범위 결정

1. V4 family를 `RW|CP|COV|DEF|PAY|REM`으로 확장한다.
2. Disclosure Letter/Schedule은 독립 계약으로 오분류하지 않고 본계약 source로 연결한다.
3. 정의·지급·구제도 `source_coverage`와 원문 좌표를 필수로 한다.
4. 한국어·영어 표현 변이는 alias로 합치고, 법적 효과가 다른 경우에만 신규 taxonomy를 만든다.
5. V4-2는 위 20건 중 국문 SPA 1건을 먼저 전수 추출해 새 범위의 누락 여부를 검증한 뒤 진행한다.
