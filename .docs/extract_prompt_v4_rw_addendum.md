# extract_prompt_v4 — RW 진술보장 완전성 부록 (2026-07-28)

_근거: `.docs/V4_RW_COVERAGE_DEFECT_20260727.md`. 기존 추출이 앞부분 boilerplate 진술
(권한·공시·자본·소송·조세)만 잡고 실질 사업진술(IP 1.8%·보험 0.2%·노무 15.7%·부동산 14.6% 등)을
조직적으로 누락해 부재판정이 대량 오답이 됐다. 이 부록은 그 결함을 교정한다._

## 핵심 규칙: 진술보장 조항(RW)은 **하위영역 전수 처리**

매도인/대상회사 진술보장 조항(통상 Article 3~5 또는 "진술 및 보장")을 추출할 때, 아래
**핵심 하위영역 체크리스트를 하나씩 확인**한다. 각 하위영역에 대해 **둘 중 하나**를 반드시 한다:

1. 해당 진술이 계약에 **있으면** → 그 조항의 원자 명제를 `RW.<DOMAIN>.*` taxonomy_id로 item 추출
   (원문 verbatim + ¶ 좌표 포함). 여러 명제면 여러 item으로 분리한다.
2. 해당 진술이 계약에 **없으면** → coverage에 그 하위영역을 `present=false`로 명시(근거: 확인한 조항
   범위). 그냥 생략하지 않는다.

**어느 쪽도 하지 않은 하위영역이 있으면 RW `body_status=complete`를 부여하지 않는다**(→ `partial`).

## 핵심 RW 하위영역 체크리스트

| 하위영역 | taxonomy 접두 | 확인 포인트 |
|---|---|---|
| 조직·권한 | RW.AUTHORITY | 설립·존속·권한·구속력·상충없음·동의불요 |
| 자본구성 | RW.CAPITALIZATION | 발행주식·소유권·부담없음 |
| 재무제표 | RW.FINANCIAL | 재무제표 정확성·부외부채 |
| 변경부존재 | RW.ABSENCE_OF_CHANGES | 기준일 후 중대변경 없음 |
| 조세 | RW.TAX | 신고·납부·미납없음·원천징수 |
| **노무·인사** | **RW.LABOR** | 근로조건 준수·미지급임금 없음·쟁의·불법파견 |
| **지식재산** | **RW.IP** | 소유·유효·비침해·라이선스·직무발명·오픈소스·영업비밀 |
| **환경** | **RW.ENVIRONMENT** | 환경법 준수·인허가·오염·청구없음 |
| 소송·분쟁 | RW.LITIGATION | 계류소송 없음·판결 없음 |
| 준법 | RW.COMPLIANCE | 법령준수·부패방지·제재 |
| 인허가 | RW.PERMITS | 사업 인허가 보유·유효 |
| 중요계약 | RW.CONTRACTS | 유효·불이행 없음·CoC 조항 |
| **부동산** | **RW.REAL_ESTATE** | 소유·임대차·부담 |
| 자산 | RW.ASSETS | 소유·상태·충분성 |
| **보험** | **RW.INSURANCE** | 보험 유지·유효 |
| **개인정보** | **RW.PRIVACY** | 개인정보보호법 준수 |
| 복리후생·연금 | RW.BENEFITS | 퇴직·연금·복리후생 |
| 특수관계자거래 | RW.RELATED_PARTY | 특수관계인 거래 |
| 고객·공급업체 | RW.CUSTOMERS_SUPPLIERS | 주요 고객·공급 관계 |
| 제품책임 | RW.PRODUCTS | 제품하자·리콜 |

(굵은 항목이 기존 추출에서 특히 대량 누락된 영역이다. 매수인 진술은 RW.BUYER로 별도.)

## rep vs covenant 구분 (분류 정밀도)

"중요계약 중 **경업금지/비밀유지 조항을 포함한 계약**"을 열거하는 문장은 **RW.CONTRACTS 진술**이지
`COV.NON_COMPETE` 확약이 아니다. 매도인이 스스로 "경쟁하지 않는다"고 약속하는 문장만 COV 확약이다.
(Gate B E03에서 rep를 COV 확약으로 오분류한 사례 다수 확인됨 → 재추출 시 시정.)

## 재추출 실행 (런북)

1. `python plan_rw_reextraction.py --out cs_index` → `cs_index/rw_reextraction_manifest.json`
   (733개 대상, ctype 우선순위, 문서별 `missing_subdomains`).
2. manifest 순서대로(SPA→SSA→SHA→ATA/BTA→CB/BW/EB) 문서의 진술 조항 전문을 입력으로 준비
   (기존 `plan_v4_batch.py` 입력 패턴 재사용; 진술 Article 전체 + 관련 별지).
3. AI 클라이언트가 위 체크리스트대로 `cs_index/enrich_results_v4/<file_key>.json` 재작성
   (누락 영역 item 추출 또는 present=false). 유료 API 없이 파일 하네스로.
4. `audit_t3_v4.py`로 하위영역 완전성 감사 → 통과분만 `replace_v4_result`로 교체 저장.
5. 배치 후 `python eval_v4_gate.py --pooled`로 RW 부재정밀도 재측정. 개선 확인 시
   `ABSENCE_UNVERIFIED_FAMILIES`에서 RW 해제를 검토(교정된 coverage에 한해).
6. 재추출로 coverage가 실제 complete가 된 문서는 `rw_subdomain_audit_pending` 사유를 제거한다.

## 규모·비용
733개(SPA 525 우선). 유료 API 자동호출 금지 원칙 유지 — 구독형 AI 클라이언트가 파일 하네스로 수행.
전량 확장은 이 재추출·재측정이 끝나고 RW 부재정밀도가 회복된 뒤에만 재개한다.
