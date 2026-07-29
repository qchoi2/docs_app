# PAY 재추출 — 병렬 작업 에이전트 지시서 (2026-07-29)

_다른 코딩 에이전트(GPT/Codex 등)에게 이 파일을 그대로 주면 자기완결적으로 작업할 수 있다.
프로젝트 루트: `docs_app/`. 배경: PAY 과소추출 진단(2026-07-29) — PAY는 RW와 동일한
"coverage=complete인데 하위영역 대량 누락" 결함이며, 계약당 대금 요소(기준대금·종결지급·
정산·에스크로·언아웃 등)를 구조적으로 누락한다._

## 목표
V4 대금(PAY) 추출이 매매대금 구조를 대량 누락한다(complete인데 leaf 중앙값 2, 723건 중 85건은
complete인데 PAY 항목 0). 배정된 계약서들의 **대금 조항 전체를 읽어 누락된 PAY 항목을 원자
항목으로 추출**해 `result JSON`으로 저장한다. **RW 작업과 동일한 방식**이나 대상 family가 PAY다.

## ★★ 가장 중요한 규칙: 결과 JSON은 그 문서의 PAY **전체**를 담아라
조율자 store는 문서 단위로 PAY를 **통째로 교체(replace)**한다. 따라서 문서마다 대금 관련
조항(제N조 매매대금/대금의 지급/정산/조정, "Purchase Price", "Consideration", "Closing
Payment", "Adjustment", "Earn-out", "Escrow", "Locked Box", "Withholding" 등)을 **전부
재정독**해, result JSON의 `items`에 **그 문서의 모든 PAY 요소를 빠짐없이** 담아라.

## ★★★ 정독 마커: `"review_method": "full_read"` (필수)
**대금 조항을 처음부터 끝까지 직접 정독해 그 문서 PAY 전체를 재구성한 결과에는 반드시
result JSON 최상위에 `"review_method": "full_read"`를 넣어라.** 조율자 store에는 후퇴 가드가
있어(새 결과가 기존 PAY 하위영역을 하나라도 떨어뜨리면 저장 스킵) 정독분에는 이 마커로
가드를 해제한다. 자동추출·부분검토분에는 넣지 마라.

## PAY 하위영역 체크리스트 (하나씩 확인해, 있으면 항목으로 추출)
원문에 있는 것만 추출한다(없는 영역은 항목을 만들지 마라 = 진짜 부재).
- **기준대금·지급**: `PAY.BASE_PRICE`(기준/총 매매대금 정의·산식), `PAY.CLOSING_PAYMENT`
  (종결일 지급액·송금), `PAY.CLOSING_MECHANICS`(지급 방법·계좌·시점), `PAY.ALLOCATION`
  (대금 배분), `PAY.EQUITY_CONSIDERATION`(주식·현물 대가), `PAY.PAYING_AGENT`(지급대리인).
- **가격 조정**: `PAY.COMPLETION_ACCOUNTS`(종결정산·운전자본/NWC·순차입금 조정),
  `PAY.LOCKED_BOX`(락스박스·leakage/permitted leakage), `PAY.TRUE_UP_DEADLINE`(정산 기한),
  `PAY.DISPUTE_ACCOUNTANT`(정산 분쟁 회계사), `PAY.INTEREST`(이자).
- **이연·조건부 대가**: `PAY.DEFERRED`(이연대금), `PAY.EARNOUT`(언아웃; 세부는
  `PAY.EARNOUT.PAYMENT`/`.GUARANTEE`/`.DISPUTE`), `PAY.MILESTONE`(마일스톤),
  `PAY.HOLDBACK`(홀드백), `PAY.SELLER_NOTE`(매도인 어음), `PAY.ROLLOVER`(롤오버 지분).
- **보전·담보**: `PAY.ESCROW`(에스크로; 해제는 `PAY.ESCROW.RELEASE`), `PAY.DEPOSIT`
  (계약금/보증금), `PAY.SETOFF`(상계).
- **세금·기타**: `PAY.WITHHOLDING`(원천징수), `PAY.VAT`(부가세), `PAY.FX`(환율),
  `PAY.TRANSACTION_COSTS`(거래비용 분담).

leaf가 불확실하면 **도메인 노드**(예: `PAY.ESCROW`)를 써라. 존재하지 않는 leaf를 지어내지 마라.

## 진술(RW) vs 대금(PAY) 구분
- "매매대금은 ~로 한다", "매수인은 종결일에 ~를 지급한다", "~를 정산한다"는 PAY다.
- 대금과 무관한 진술·확약·조건은 이 작업 범위 밖(PAY만 추출).

## result JSON 스키마
`cs_index/pay_reextract_results/<file_key>.json`:
```json
{
  "file_key": "<key>",
  "reason": "PAY 하위영역 재추출",
  "review_method": "full_read",
  "items": [
    {
      "taxonomy_id": "PAY.BASE_PRICE",
      "proposition": "매매대금은 1주당 X원, 총 Y원으로 한다.",
      "verbatim": "<원문 그대로 발췌>",
      "loc_start": 120,
      "loc_end": 121,
      "statement_polarity": "affirmative",
      "subject_role": "매수인",
      "parent_clause_ref": "제2조",
      "confidence": "high"
    }
  ]
}
```
- PAY 항목은 대개 규정(provision)이라 `statement_polarity`는 통상 `affirmative`. 특정 대금
  요소의 **부존재를 명시**하는 경우(예: "에스크로를 두지 아니한다")만 `none_exist`.
- `verbatim`·`loc_start`(¶번호)는 원문 실제 조항으로 채운다.
- **얇은 계약 주의**: 주식양수도(SSA)·CB/BW 인수 등은 "대가=주식인수대금"만 있는 경우가
  많다 — 그때는 `PAY.BASE_PRICE`/`PAY.EQUITY_CONSIDERATION`만 담고 억지로 늘리지 마라.

## 표적 우선순위 (조율자 제공 매니페스트: `cs_index/pay_reextraction_manifest.json`)
392건. `pay_tier`로 정렬됨:
1. **tier 1 (61건)** — complete인데 PAY 항목 **0인 SPA**. 최우선(대형 문서부터, lines 내림차순).
2. **tier 2 (24건)** — PAY 항목 0인 비-SPA(SSA/CB 등). 얇은 계약 다수 — 근본 대금만 담아라.
3. **tier 3 (307건)** — PAY leaf ≤2인 SPA. 과소추출 잔존.
각 항목에 `file_key`·`ctype`·`pay_leaf_count`·`present_pay_leaves`(이미 든 leaf)·`lines`.

## ★ 절대 규칙 (병렬 안전)
1. **catalog.sqlite에 절대 쓰지 마라.** result JSON만 쓴다. store는 조율자가 중앙에서 순차 실행.
2. **유료 API 자동 호출 금지.** 구독형 에이전트로 원문을 읽고 판단해 작성한다.
3. 배정된 file_key 범위만 처리한다.
4. 원문(`cs_index/txt/<file_key>.txt`, 문단마다 `[¶N]\t본문`)을 읽고 판단하라.

## 절차
1. `cs_index/pay_reextraction_manifest.json`에서 배정 샤드(조율자가 k/N 지정)를 받는다.
2. `cs_index/txt/<file_key>.txt`에서 대금 조항을 찾아 정독한다.
3. 위 체크리스트로 PAY 요소를 하나씩 확인해 `items`에 담는다.
4. `cs_index/pay_reextract_results/<file_key>.json`에 저장한다(위 스키마, 마커 포함).
5. 다 끝내면 조율자에게 알린다. **store는 실행하지 마라.**
