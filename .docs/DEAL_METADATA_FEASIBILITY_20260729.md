# 거래 메타데이터 확장 — 타당성·커버리지 실측 (2026-07-29)

_대상: 리뷰어 "Fable"(2026-07-29)의 「거래 메타데이터 확장 — 새로운 질의 계급」 제안._
_방법: `derive_deal_meta.py`(신규, 읽기 전용 dry-run)로 색인 전량 2,106건을 파생 시도하고
축별 커버리지·신뢰도·미채움 사유를 계수했다. **DB 쓰기 없음. 유료 API 호출 없음.**
DB는 `file:cs_index/catalog.sqlite?mode=ro` URI로만 열었다._

## 0. 결론 요약

| 축 | 채움률 | high/med 채움률 | 권고 |
|---|---:|---:|---|
| 준거법 `governing_law` | 70.1% (1,477) | **70.1%** | **채택** |
| 관할법원 `forum_court` | 51.3% (1,081) | **51.1%** | **채택** |
| 중재합의 `arbitration` | 95.7% (2,016) | 15.4% (true 324) | **채택**(불리언), 단 false는 "미검출" |
| 중재기관 `arbitration_institution` | 13.2% (278) | 13.2% | 부수 필드로만 채택 |
| 중재지 `arbitration_seat` | 5.0% (105) | **0%** | **보류** — 전량 low |
| 거래 연도 `deal_year` | 81.1% (1,708) | 35.2% (742) | **조건부 채택** — 체결일은 420건(19.9%)뿐 |
| 거래 규모 구간 `size_band` | **0.4% (8건)** | 0.4% | **반대** |
| 업종 `industry` | **0%** | 0% | **반대** — 로컬 파생 불가 |

한 줄 요약: **제안의 절반은 맞고 절반은 틀렸다.** 준거법·관할은 리뷰어의 예상보다도
잘 나오는 저비용 고수익 축이다. 반면 **거래 규모 구간은 "v3 대금 정보가 있으니 파생
가능"이라는 전제가 사실과 다르다** — v3 정규화 대금이 있는 문서는 코퍼스의 2.8%(60건)이고,
그중 안전하게 구간화할 수 있는 것은 **8건(0.4%)**이다. 업종은 로컬 파생이 불가능하다.

---

## 1. 측정 방법과 이 문서가 신뢰할 만한 이유

초기 측정(전문 키워드 검색)은 **심하게 과탐지했다**. 그 수치를 그대로 보고했다면
제안이 실제보다 훨씬 좋아 보였을 것이다. 실제로 일어난 일:

| 항목 | 전문 키워드 검색(1차) | 조항 위치 특정 후(최종) | 배수 |
|---|---:|---:|---|
| 준거법에 "Hong Kong" 언급 | 379건 | 3건 | 126배 과대 |
| 준거법에 "Singapore" 언급 | 323건 | 8건 | 40배 과대 |
| 중재 관련 토큰 검출 | 1,398건 | 중재**합의** 324건 | 4.3배 과대 |

과탐지 원인은 자회사 목록·당사자 주소·진술보장 정의조항("소송"의 정의에 "중재절차"가
열거된다)이다. 최종 수치는 아래 규율을 적용한 뒤의 값이다.

**적용한 판정 규율 (각각 실측으로 필요성이 확인됨)**

1. **목차(TOC) 앵커 배제** — "10.10 준거법 및 분쟁해결 19"처럼 페이지 번호가 붙은
   목차 줄이 본문 조항보다 먼저 나온다. 첫 매치를 쓰면 조항을 못 읽는다.
2. **서술어 문장 안에서만 판독** — "shall be governed by" / "준거법은 …로 한다"가
   있는 문장에서만 관할지 이름을 읽는다.
3. **공란·괄호 선택지는 unknown** — `the internal laws of ___`, `[Hong Kong; the
   United Kingdom]`은 미확정이다(실측 69건).
4. **준거법 ≠ 중재지 ≠ 관할법원** — 세 값을 별도 필드로 낸다.
5. **중재는 '언급'과 '합의'를 구분** — 구속 문구(`shall be finally settled` 등) 필요.
6. **체결일 ≠ 작성일 ≠ 배포일 ≠ 버전일자** — 출처를 `basis.date_kind`에 명시한다.

### 정밀도 표본 검수 (원문 대조)

| 축 | 표본 | 결과 |
|---|---|---|
| `governing_law` | 무작위 20건 | 20/20 정확 |
| `governing_law` (비-대한민국) | **전수 53건** | 53/53 원문 verbatim과 일치 |
| `deal_year` (confidence=high) | 무작위 15건 | 15/15 정확 |
| `forum_court` | 무작위 10건 | 10/10 정확 |
| `size_band` | **전수 8건** | 8/8 금액 일치 |

---

## 2. 축별 실측

### 2.1 준거법 — **채택 권고**

```
채움 1,477 / 2,106 (70.1%)  — 전량 confidence=med
```

| 값 | 건수 |
|---|---:|
| 대한민국 | 1,424 |
| Delaware | 18 |
| New York | 16 |
| Singapore | 8 |
| Hong Kong / Japan / England | 각 3 |
| Indonesia | 2 |

**미채움 629건의 사유 (전부 "부재"가 아니라 "미판정"이다)**

| 사유 | 건수 | 의미 |
|---|---:|---|
| `no_governing_law_clause_found` | 246 | 조항 앵커 미탐지(별지·단편 문서 다수) |
| `clause_not_localized` | 167 | 목차 줄만 발견 — 본문 조항 특정 실패 |
| `no_text_cache` | 90 | 본문 검색 불가(스캔 PDF 등) |
| `jurisdiction_not_named` | 55 | 조항은 있으나 관할지 판독 실패 |
| `unresolved_bracket_options` | 54 | 초안의 미확정 괄호 선택지 |
| `placeholder_in_clause` | 15 | 양식의 공란 |
| `multiple_jurisdictions_in_operative_sentence` | 2 | 한 문장에 복수 관할지 |

언어별 채움률: 국문 68.8%(926/1,345), 영문 73.0%(542/742), 국영문 47.4%(9/19).

**평가**: 실무 질의 "영문 준거법 계약 중"은 이 축으로 바로 열린다. 값 분포가 극도로
편향(대한민국 96.4%)돼 있어 층화 검색의 실익은 **비-대한민국 53건을 정확히 찾는 것**에
있고, 그 53건은 전수 검수에서 100% 정확했다. 비용 대비 수익이 가장 좋은 축이다.

**주의 사항 (필터 설계에 반영 필요)**: 배타적 관할과 비전속적 관할을 구분하지 않는다
(예: `17e9334ad8e25842`는 "서울중앙지방법원을 **비전속적** 관할법원으로 한다").
`forum_court`는 "그 법원이 언급됐다"이지 "전속관할이다"가 아니다.

### 2.2 관할 / 중재 — **채택 권고(단, 세 필드를 절대 합치지 말 것)**

```
forum_court              1,081 / 2,106 (51.3%)   med 1,076 · low 5
forum_type               1,397 / 2,106 (66.3%)   court 1,076 · arbitration 320
arbitration              2,016 / 2,106 (95.7%)   true 324 · false 1,692(전부 low)
arbitration_institution    278 / 2,106 (13.2%)   ICC 144 · SIAC 75 · KCAB 45 · HKIAC 14
arbitration_seat           105 / 2,106 ( 5.0%)   전량 low
```

관할법원 값: 서울중앙지방법원 1,062 · 수원 6 · 서울 4 · 창원 3 · 인천 1 · 기타 영문 5.

**반드시 지켜야 할 구분** — 이 축의 대표적 오류는 셋을 하나로 합치는 것이다.
실측에서 준거법이 인도네시아법인데 중재지가 싱가포르인 계약(`ec7cee7b9c85c5a1`)을
1차 측정이 "싱가포르 준거법"으로 오판했다. 준거법·관할법원·중재지가 각각 다른
계약이 정상이다. 또 법원 관할과 중재합의가 **함께** 읽히는 문서 4건은 단계적
분쟁해결 조항일 수 있어 `forum_type`을 자동 판정하지 않고 unknown으로 남겼다.

**`arbitration=false`는 부재 증명이 아니다.** 1,692건의 false는 전부
`confidence=low`이며 근거는 `no_arbitration_anchor` 또는
`arbitration_mentioned_without_agreement`다. CLAUDE.md 답변 원칙 4(부재 증명은
신중히)에 따라 "중재 없는 계약"을 이 값으로 단정해선 안 된다.

**`arbitration_seat`는 보류 권고** — 105건 전량 low이고 한국어 표기가
"서울로"/"대한민국"처럼 정규화되지 않는다. 값으로 쓰지 말고 근거 표시용으로만 남긴다.

### 2.3 거래 연도 — **조건부 채택 (단일 `deal_year` 필터는 반대)**

```
채움 1,708 / 2,106 (81.1%)   high 386 · med 356 · low 966
high/med  742 / 2,106 (35.2%)
```

**채움률 81%는 오해를 부르는 숫자다.** 무엇의 연도인지가 문서마다 다르다:

| `date_kind` | 건수 | 이것은 무슨 날짜인가 |
|---|---:|---|
| 체결일 | **420** | 체결본 전문/서명란의 체결 문장 날짜 — 진짜 거래 연도 |
| 작성일/체결예정일 | 567 | 초안·mark-up의 전문 날짜 |
| 작성 연도(체결일 공란) | 233 | `2024. [*]. [*].` — 미체결 문서 |
| 체결일(파일명) | 147 | 체결본 파일명의 YYYYMMDD |
| 버전 일자(파일명) | 109 | 초안 파일명의 YYYYMMDD |
| 버전 일자 추정(6자리) | 124 | `220518` — 버전번호와 구별 불가 |
| 문서 배포·수정일 | 72 | 머리글 "매수인 수정안 / 2024. 11. 26" |
| 체결예정일(미체결본) | 36 | |
| (미채움) | 398 | |

**체결일이 high/med로 확인되는 문서는 420건(19.9%)이고, 전부 `version_role=execution`이다.**
초안·mark-up 1,416건에서는 체결일이 하나도 나오지 않는다(구조적으로 존재하지 않는다).

**출처별 신뢰도 근거 (실측)**

- **파일 mtime은 신호가 아니다.** 2,106건 **전부** mtime 연도가 2026이다(전량 재색인
  시각). 이 도구는 mtime 경로를 아예 만들지 않았고, 그 사실을 테스트로 고정했다.
- **파일명 vs 본문 불일치율 4.5%** (본문 파생 404건 중 18건). 그리고 불일치가 곧
  본문이 틀렸다는 뜻이 아니다 — `1672a994a13f2323`은 파일명이 `20140527`이지만 본문
  ¶2가 "2015년 4월 30일(본 계약 체결일)"이라 **본문이 맞다**.

**개발 중 발견하고 고친 정밀도 결함 (기록)**: 초기 구현은 전문 40문단의 최대 연도를
썼고, 그 결과 기준일("기준일은 2023년 12월 31일")·확약 기한("2017년 12월 31일까지")·
선행 계약 체결일("주식매매계약을 2014년 11월 26일 체결하였다")을 거래 연도로 집었다.
원문 대조로 2건을 확인하고 **'체결' 서술 문장에 붙은 날짜만 채택**하도록 고쳤다.
교차출처 불일치율이 10.9% → 4.5%로 떨어졌다. 두 사례는 회귀 테스트로 고정했다.

**권고**: `deal_year` 하나짜리 필터는 만들지 마라. "최근 대형 거래에서"라는 질의에
81% 채움률을 그대로 쓰면 초안 작성일과 체결일이 섞인 답이 나온다. `deal_year` +
`deal_year_kind` + `deal_year_confidence`를 **함께** 노출하고, 기본 필터는
`date_kind=체결일`로 한정하되 제외 모집단을 고지해야 한다(§4 참조).

### 2.4 거래 규모 구간 — **반대**

```
채움 8 / 2,106 (0.4%)
```

리뷰어의 전제 "v3 대금 정보가 있으니 규모 구간은 파생 가능"은 **사실과 다르다.**

| 사유 | 건수 |
|---|---:|
| `meta_schema_v2_not_normalized` | **1,939** |
| `no_consideration_section` | 107 |
| `amount_value_null_after_review` | 31 |
| `consideration_not_evaluated` | 12 |
| `draft_amount_not_final` | 4 |
| `non_krw_requires_fx` | 3 |
| `non_binding_instrument` | 2 |
| **구간화 가능** | **8** |

**깔때기를 그대로 적으면:**

1. `doc_meta` 1,999건 중 **schema v3는 60건**(사람 승인 파일럿), 나머지 1,939건은
   v2다. v2의 `consideration_json`은 `{"candidates": [{"para": 37, "text": "매매대금"}…]}`
   — **후보 문단 목록이지 정규화 금액이 아니다.** 구간화할 수 있는 숫자가 없다.
2. v3 60건 중 대금 섹션 `evaluated=true`는 48건.
3. 그 48건 중 `amount_value`가 숫자인 것은 **17건**. 나머지 31건은 사람이 원문을
   읽고 **일부러 null로 둔 것**이다.
4. 17건에서 비구속 MOU 2건·초안 4건·비원화 3건을 제외하면 **8건**.

**"일부러 null"이 이 축의 핵심 위험이다.** progress.md 세션 24~26의 기록:

- `a5da55951cfdabfb` — SHA 본문의 300억원은 **별도 신주인수계약의 RCPS 투자금**이었다.
  사람이 원문 재대조 후 `amount_value=null`로 바꾸고 300억원은 `definitions_json`의
  "관련 신주인수계약 투자금액"으로 옮겼다. 자동 파생은 이 구분을 못 한다.
- `d52f0cbc2a9171bb` — 800억원은 현재 변경계약의 신규 대금이 아니라 **원 교환사채
  인수계약의 전자등록총액**이었다. null 처리.
- `30fae2c6d27a9f8c` — MOU 500억원은 **비구속 별첨 조건**이다.
- 영문 BTA 양식·`c28dbecbb5bac628` 초안 — 당사자·가액 **공란**을 null로 유지.

즉 **잘못된 금액을 걸러낸 것은 자동 규칙이 아니라 문서별 사람 정독이었다.** 브리프가
경고한 세 함정(타 계약 참조금액 / 비구속 MOU / 공란 초안)은 전부 v3 파일럿 60건 안에서
실제로 발생했고, 전부 사람이 잡았다. 남은 2,046건에 같은 함정이 같은 비율로 있다고
보는 것이 합리적이다.

부수 문제도 있다. 통화가 KRW/USD로 섞여 있어 구간화에는 환산이 필요하고, 환산에는
거래일 환율이 필요하며, 거래일(=`deal_year`)의 신뢰도는 위에서 본 대로 낮다. 불확실성이
곱해진다. 그리고 `01da7f58dfd94a49`는 `amount_value=41,750,000,000`인데 verbatim은
"합계 금 367.5억원"이다 — **사람 승인 데이터 안에도 금액과 근거가 어긋나는 건이 있다.**

**대안**: v4 `PAY` family가 753개 문서에 4,255개 항목을 갖고 있고 `PAY.BASE_PRICE`가
250개 문서에 있다. 다만 `normalized_json`은 **PAY 4,255건 전부 비어 있어** 숫자가
구조화돼 있지 않다. verbatim 정규식 파싱은 가능하나, 그것은 위의 세 함정을 그대로
다시 밟는 길이다(어느 금액이 *이 계약의* 대가인지는 문맥 판단이다). 진행 중인 PAY
재추출이 `PAY.BASE_PRICE`를 문서당 1건으로 정착시킨 **이후에** 재평가할 것을 권한다.

**따라서 지금 이 축을 만드는 것은 반대한다.** 0.4% 채움률의 필터는 "대형 거래" 질의에
8건을 돌려주고 나머지 2,098건을 조용히 감춘다 — `--version` 하드 필터 결함과 정확히
같은 실패 양식이다.

### 2.5 업종 — **반대 (로컬 파생 불가)**

이미 큐잉된 갭이지만, **로컬에서는 파생할 수 없다**는 것이 실측 결론이다.

업종 힌트 어휘(제조/금융/IT/바이오/건설/유통)로 전 코퍼스를 훑은 결과:

- 1,395건이 하나 이상의 업종에 걸렸다.
- 그중 **778건이 2개 이상**, 223건이 3개 이상, 71건이 4개 이상에 동시에 걸렸다.
- "제조" 단독 히트가 742건인데, 상당수는 **진술보장 보일러플레이트**다 —
  "제조물책임", "생산물배상책임", "product liability"는 거의 모든 SPA에 있는 문구이지
  대상회사가 제조업이라는 뜻이 아니다.
- `한국표준산업분류`/`KSIC` 코드를 본문에 명시한 문서는 사실상 없다.

근본 문제는 **업종이 계약서 문구의 사실이 아니라 대상회사의 사실**이라는 점이다.
계약서는 대상회사를 상호와 법인등록번호로 특정할 뿐 업종을 서술하지 않는 것이 정상이다.

**필요한 것**: (a) 외부 기업정보(사업자등록번호 → 표준산업분류) 결합, 또는
(b) 문서별 정독. (a)는 이 코퍼스 밖의 데이터 소스가 필요하고, (b)는 리뷰어가
"재추출만큼 무겁지 않다"고 한 전제를 깨뜨린다. `derive_deal_meta.derive_industry()`는
값을 만들지 않고 이 사유를 돌려주도록 구현했다.

---

## 3. 도구 — `derive_deal_meta.py`

읽기 전용 dry-run. **DB에 쓰지 않는다.** 마이그레이션은 소유자 검토 후 조율자가 수행한다.

```
python derive_deal_meta.py --out cs_index --report cs_index/deal_meta_dryrun.json
python derive_deal_meta.py --out cs_index --file-key <KEY>     # 1건 근거 확인
```

### 근거·신뢰도 형태 — `classify_version.py`와 동일

모든 파생값은 `{"value", "confidence", "basis"}` 3종 세트이고, `confidence` 어휘는
`classify_version.CONFIDENCE_LEVELS`(high/med/low)를 **그대로 import해서 공유**한다.
`normalize_confidence()`도 공유하므로 미상 값은 `None`으로 degrade한다.

```json
{
  "value": "대한민국",
  "confidence": "med",
  "basis": {
    "rule": "governing_law_clause",
    "para": 143,
    "matched": ["대한민국 법"],
    "verbatim": "본 계약의 준거법은 대한민국 법률로 한다.",
    "source": "body",
    "conflicts": ["Singapore"],
    "deriver": "deal_meta_v1_20260729"
  }
}
```

**unknown은 1급 값이다.** `is_draft=null` / `version_confidence` 철학의 연장으로,
모르는 것은 `value=None, confidence=None`이고 `basis.rule`에 **왜** 모르는지를 남긴다.
`confidence=None`은 "저신뢰"가 아니라 "미평가"다 — 이 구분이 §4 필터 설계의 근거다.

미채움 사유는 전부 사유별로 계수되어 리포트 `summary[축].unknown_reasons`에 남는다.
"조항이 없다"와 "조항을 못 찾았다"를 구분하는 것이 목적이다.

---

## 4. 저장·검색 설계 (구현하지 않음 — 명세만)

### 4.1 저장

**`files`에 가산 컬럼**을 권한다. `classify_version.ensure_version_meta_columns()`와
같은 가산적 마이그레이션 패턴을 따르고, 백필 전 NULL은 "확인 필요"로 degrade한다.

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `deal_year` | INTEGER | |
| `deal_year_kind` | TEXT | 체결일 / 작성일·체결예정일 / 버전 일자 / 배포일 |
| `deal_year_basis` | TEXT(JSON) | rule·para·verbatim·matched |
| `deal_year_confidence` | TEXT | high/med/low, NULL=미백필 |
| `governing_law` / `_basis` / `_confidence` | TEXT | |
| `forum_court` / `_basis` / `_confidence` | TEXT | |
| `forum_type` / `_basis` / `_confidence` | TEXT | court / arbitration, NULL=미판정 |
| `arbitration` / `_basis` / `_confidence` | INTEGER | 0/1, NULL=미판정 |
| `arbitration_institution` | TEXT | 부수 필드 |

- **`size_band`·`industry` 컬럼은 만들지 않는다** (§2.4, §2.5).
- **`arbitration_seat`는 `arbitration_basis` JSON 안에만** 둔다. 정규화되지 않은
  전량 low 값을 필터 가능한 컬럼으로 승격하지 않는다.
- v4처럼 별도 테이블로 뺄 이유는 없다 — 파일당 1레코드이고 `files`가 이미 그 단위다.

### 4.2 필터 — 조용한 누락을 구조적으로 막는 규칙

`--version` 하드 필터 결함(오늘 수정)의 교훈을 그대로 적용한다.

**규칙 1 — 저신뢰·미상은 결과에서 지우지 않고 "확인 필요"로 드러낸다.**
`version_review_required`와 같은 형태로 축마다
`<axis>_review_required = (value is None) or (confidence in (None, "low"))`.

**규칙 2 — 필터가 걸린 모든 응답에 `<axis>_filter_notice`를 싣는다.**
`build_version_filter_notice()`와 같은 구조체:

```json
{
  "requested": ["대한민국"],
  "classification_basis": "clause_localized_body_read",
  "classification_recorded": true,
  "matched_documents": 1424,
  "matched_low_confidence": 0,
  "excluded_total": 682,
  "excluded_unknown": 629,
  "excluded_by_reason": {
    "no_governing_law_clause_found": 246,
    "clause_not_localized": 167,
    "no_text_cache": 90,
    "unresolved_bracket_options": 54
  },
  "warnings": ["governing_law_filter_excluded_unknown:629"],
  "warning": "준거법 필터는 조항 위치를 특정해 읽은 결과다. 미판정 629건은 …"
}
```

`excluded_by_reason`을 `excluded_by_role` 자리에 두는 것이 이 축의 차이다 —
버전은 라벨이 배타적이지만 여기서는 **왜 못 읽었는지**가 사용자 판단의 근거다.
특히 `no_text_cache` 90건은 CLAUDE.md 답변 원칙 5(검색 불가 문서 고지) 대상이다.

**규칙 3 — 연도 필터는 `deal_year_kind`를 강제로 함께 받는다.**
`--deal-year 2024`는 단독으로 받지 않는다. 기본값을 `--deal-year-kind 체결일`로 두고,
사용자가 넓히면 `deal_year_kind`별 내역을 notice에 싣는다. 이렇게 하지 않으면
초안 작성일과 체결일이 한 결과에 섞이고, 그 사실이 응답 어디에도 나타나지 않는다.

```
--deal-year 2024                 → 체결일 기준 n건 (+ 작성일 기준 m건이 제외됐다고 고지)
--deal-year 2024 --deal-year-kind any → n+m건, 행마다 deal_year_kind 표시
```

**규칙 4 — `arbitration=false`로 부재를 단정하지 않는다.**
`--arbitration false`는 `confidence=low`인 1,692건을 그대로 통과시키되
`needs_review`로 분리한다(v4 부재 판정 규칙과 동일).

**규칙 5 — 준거법·관할법원·중재지를 하나의 "관할" 필터로 묶지 않는다.**
CLI/웹/MCP 어디에서도 별도 파라미터로 노출한다.

### 4.3 인터페이스별

- **CLI** (`search_contracts.py` / `v4_search.py`):
  `--governing-law 대한민국` / `--forum-court 서울중앙지방법원` / `--arbitration`
  / `--deal-year 2024 [--deal-year-kind 체결일|any]`.
  결과 행에 `<axis>` · `<axis>_confidence` · `<axis>_basis_summary` ·
  `<axis>_review_required`. `annotate_version_row()`에 대응하는
  `annotate_deal_meta_row()` 하나로 처리한다.
- **웹** (`webapp.py`): 준거법·관할법원 셀렉트는 **DB 실제 값에서 동적 생성**한다
  (하드코딩 금지 — v4 taxonomy 셀렉트와 같은 규칙). 연도는 슬라이더가 아니라
  `deal_year_kind` 라디오와 함께 놓는다. 결과 카드에 근거 배지와 "확인 필요" 표시.
- **MCP** (`mcp_server.py`): **새 도구를 추가하지 않는다.** 기존
  `search_contracts`의 파라미터로만 추가하고, 도구 설명에 `version_filter_notice`와
  같은 문구로 "이 값은 조항 위치를 특정해 읽은 결과이며 미판정 모집단이 있다"를
  명시한다. V4_PLAN §8의 "기존 7개 도구 계약은 불변" 원칙을 지킨다.

### 4.4 재추출 연동

`doc_meta.txt_hash != files.content_hash`인 문서는 파생값도 낡았다.
`<axis>_basis`에 파생 시점의 `txt_hash`를 남겨 CLAUDE.md 답변 원칙 10과 같은
"재추출 전" 표시가 가능하게 한다.

---

## 5. 권고 정리

**지금 하라 (1차)**
1. `governing_law` — 70.1% 채움, 표본 정밀도 100%. 비-대한민국 53건 전수 검수 완료.
2. `forum_court` / `forum_type` / `arbitration` — 51~96% 채움, 세 필드 분리 필수.
3. §4.2의 5개 필터 규칙을 **저장과 동시에** 구현한다. 나중에 붙이면
   `--version`과 같은 결함을 한 번 더 만든다.

**조건부 (2차)**
4. `deal_year` — `deal_year_kind` 동반 노출과 규칙 3을 전제로만. 단독 연도 필터는 반대.

**하지 마라**
5. `size_band` — 0.4% 채움. 전제("v3 대금이 있다")가 사실과 다르다. PAY 재추출이
   `PAY.BASE_PRICE`를 정착시킨 뒤 재평가.
6. `industry` — 로컬 파생 불가. 외부 기업정보 결합 또는 문서별 정독이 필요하며,
   후자는 "재추출만큼 무겁지 않다"는 제안의 전제를 깨뜨린다.
7. `arbitration_seat`를 필터 컬럼으로 승격하지 마라 — 전량 low, 미정규화.

**리뷰어 제안에 대한 총평**: "새로운 질의 계급을 연다"는 판단은 준거법·관할에 대해
옳다. 다만 "v3 대금이 있으니 규모 구간은 파생 가능하고, 연도는 상당 부분 추출 가능"이라는
근거는 실측과 다르다 — 규모는 0.4%, 연도는 체결일 기준 19.9%다. 제안 4개 축 중
**2개는 채택, 1개는 조건부, 1개는 반대**가 실측에 부합하는 결론이다.

---

## 6. 검증

- `python -m pytest -q tests/test_derive_deal_meta.py` → **53 passed**
- `python -m pytest -q` (전체) → **460 passed, 1 skipped** (회귀 없음)
- `python derive_deal_meta.py --out cs_index --report <경로>` → 2,106건 처리,
  `writes_performed: 0`
- DB 쓰기 0건 (`mode=ro` URI 전용), git 커밋 0건, 유료 API 호출 0건

테스트가 고정한 계약(53건 중 주요):
- 기준일·확약 기한·선행 계약 체결일을 거래 연도로 집지 않는다 (실측 결함 2건 재현)
- 파일 mtime을 연도 출처로 쓰지 않는다
- v2 메타·사람 검수 null·비구속 MOU·초안·비원화·저신뢰 금액을 구간화하지 않는다
- 목차 줄을 준거법 조항으로 삼지 않는다
- 공란·괄호 선택지를 값으로 승격하지 않는다
- 중재지를 준거법으로 오인하지 않는다 (실측 오판 재현)
- 정의조항의 "중재절차" 언급을 중재합의로 세지 않는다
- 법원 관할과 중재합의가 함께 있으면 `forum_type`을 자동 판정하지 않는다
- 업종은 어떤 입력에서도 값을 만들지 않는다
- `build_report()`가 DB 파일을 수정하지 않는다
