# V4-1R2 국문 대표 계약 1건 색인 테스트

- file_key: `0ddde0e62bd84e41`
- 문서: `01-1_SPA_국문/Apex_알파플러스_SPA_매수인 1st markup_181010.pdf`
- 유형/언어: SPA / 국문
- 문서 상태: 본문 추출 가능(`ok`), 드래프트
- 색인 버전: meta schema 4 / schema revision 1R2 / taxonomy version 3
- 추출 방식: 로컬 결정론적 대표문서 테스트(유료·외부 API 미사용)

## 테스트 결론

6개 family에서 총 205개의 원자 항목을 추출했다. 감사 결과는 `review`이고
구조·근거·source coverage·원자성 관련 `issues`는 0건이다. `review`인 이유는
기존 taxonomy에 전용 leaf가 없는 정의 등 29개의 taxonomy 후보와, PDF 표 OCR
때문에 사람 확인이 필요한 44개 항목이 있기 때문이다.

명시적 검토 승인 전에는 운영 DB에 저장하지 않는 가드를 적용했다. 따라서 이번
결과는 검토 가능한 테스트 산출물이며 운영 색인에는 아직 반영하지 않았다.

## family별 결과

| family | 의미 | 원자 항목 수 | 본문 coverage | 별지·첨부 coverage |
|---|---|---:|---|---|
| RW | 진술 및 보장 | 88 | complete | partial |
| COV | 확약 | 30 | complete | partial |
| CP | 선행조건 | 16 | complete | no_annex |
| DEF | 정의 | 40 | complete | partial |
| PAY | 대금·지급구조 | 6 | partial | complete |
| REM | 손해배상·구제·해제 | 25 | complete | partial |
| 합계 |  | **205** |  |  |

`PAY.body_status=partial`은 이번 대표 테스트가 매매대금, 계약금, 종결지급 및
별지 1 배분표를 우선 색인했기 때문이다. 별지 1은 전체 평가했다.

## 요청 수준의 원자화 예시

| taxonomy_id | 정규화된 색인 내용 | 근거 |
|---|---|---|
| `RW.LABOR.NO_VIOLATION` | 인사노무 법령·단체협약·취업규칙·근로계약의 중요 위반 없음 | ¶777–¶789 |
| `RW.LABOR.WORKING_CONDITIONS` | 임금·수당·상여·퇴직금·근로시간·휴일·휴가·복리후생 조건 준수 | ¶777–¶789 |
| `RW.LABOR.NO_OFF_BOOK_WAGES` | 내부규정 등에 없는 임금·이익 제공 약속·합의 없음 | ¶777–¶789 |
| `RW.LABOR.UNPAID_COMPENSATION` | 지급기가 도래한 미지급 임직원 보수 없음 | ¶789–¶795 |
| `RW.FINANCIAL.NO_UNDISCLOSED_LIABILITIES` | 허용된 예외 외 재무제표 기재 대상 부외·우발채무 없음 | ¶719–¶734 |
| `RW.LITIGATION` | 공개된 예외 외 대상회사·임직원 관련 중요 소송 및 제기 우려 없음 | ¶773–¶777 |
| `RW.TAX` | 조세 신고·보고의 기한 내 적법한 이행 | ¶802–¶807 |
| `RW.TAX` | 납기가 도래한 조세의 전액 납부 | ¶802–¶807 |
| `RW.TAX` | 원천징수 및 기한 내 납부 | ¶802–¶807 |
| `RW.IP` | 사업에 필요한 지식재산권의 적법·유효한 보유·사용 | ¶813–¶827 |
| `COV.RESTRICTED_ACTIONS` | 사전동의 없는 정관 개정 금지 | ¶1061–¶1089 |
| `COV.RESTRICTED_ACTIONS` | 사전동의 없는 주식·전환증권 발행, 권리변경, 감자 금지 | ¶1061–¶1089 |
| `COV.RESTRICTED_ACTIONS` | 사전동의 없는 합병·분할·사업양수도·해산·도산절차 금지 | ¶1061–¶1089 |
| `CP.NO_MAC` | 체결일 이후 중대한 부정적 영향의 미발생·미발견 | ¶1273–¶1277 |
| `PAY.BASE_PRICE` | 총 매매대금 및 매도인별 대금은 별지 1에 따름 | ¶532–¶536 |
| `PAY.DEPOSIT` | 계약 체결 직후 계약금계좌에 계약금 예치 | ¶537–¶547 |
| `PAY.DEPOSIT` | 계약금 반환의무 담보를 위한 예금채권 질권 설정 | ¶537–¶547 |
| `REM.DE_MINIMIS` | 건별 회사 손해 0.5억원 미만 청구 제외 | ¶1423–¶1430 |
| `REM.BASKET` | 총 회사 손해 2억원 미만 청구 제외, 초과분 배상 | ¶1423–¶1430 |
| `REM.CAP` | 매도인측 책임의 지분비율 연동 한도 | ¶1430–¶1434 |
| `REM.SANDBAGGING` | 종결 전 인지한 위반에 대한 청구권 포기 | ¶1443–¶1452 |
| `REM.NO_DOUBLE_RECOVERY` | 동일 손해에 대한 중복 배상·권리구제 금지 | ¶1461–¶1463 |
| `REM.DEPOSIT_FORFEITURE` | 해제 사유에 따른 계약금 귀속 또는 반환 | ¶1597–¶1629 |

위 항목은 모두 `[0ddde0e62bd84e41]`의 원문 위치와 verbatim을 가진다. 같은
문단 안에서도 서로 독립적으로 검색할 가치가 있는 명제는 별도 item으로 분리했다.

## 별지 및 누락 자료 처리

실제 파일에 포함된 `별지 1`(¶1807–¶1864)은 전체 행을 평가했다. 별지의
매도인별 대상주식·지분율·매매대금·계좌번호 배분 구조를 `PAY.ALLOCATION`으로,
주주별 주식·지분 정보를 `RW.CAPITALIZATION`으로 색인했다. 같은 별지 내용을
두 기능이 참조하므로 `related_item_ref`로 연결했다.

다만 PDF 표의 열 정렬이 일부 모호하여 별지 관련 11개 item은
`needs_review`로 두었다. 문서가 참조하지만 현재 코퍼스에 실제 내용이 없는
다음 자료는 `missing`으로 표시했다.

- 매도인 공개사항: RW, COV, DEF, REM 관련 참조
- 별지 1의 3: 매도인별 대상주식 지분비율 정의 관련 참조

따라서 `annex_status=partial`은 별지를 보지 않았다는 뜻이 아니라, 포함된 별지는
평가했지만 외부 참조 자료가 코퍼스에 없다는 뜻이다.

## 검토가 필요한 항목

- taxonomy 후보 29개: RW 3개, DEF 26개
- `needs_review` 44개: DEF 33개, RW.CAPITALIZATION 10개,
  PAY.ALLOCATION 1개
- 주요 원인: 계약별 정의어에 대한 전용 leaf 부재, 표 OCR 열 정렬

정의 항목은 누락하지 않고 우선 `DEF` 아래 원자 item으로 보존했으며, 기존
taxonomy와 구별되는 정의어는 후보로 별도 제출했다. 후보 승인을 거쳐 canonical
taxonomy를 추가한 뒤 동일 의미 정의는 같은 항목으로 재분류할 수 있다.

## 검증

- V4 감사: 1건 `review`, 205 items, issues 0
- 저장 가드: `allow_review=false`에서 0건 저장, 1건 안전하게 skip
- 전체 회귀 테스트: 170 passed, 1 skipped

## 산출물

- 입력: `cs_index/enrich_inputs_v4/0ddde0e62bd84e41.json`
- 전체 색인 결과: `cs_index/enrich_results_v4_1r2_test/0ddde0e62bd84e41.json`
- 감사 보고서: `cs_index/v4_ko_representative_test_audit.json`
- 1건 manifest: `cs_index/v4_ko_representative_test_manifest.json`
