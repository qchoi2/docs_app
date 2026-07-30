# RW 재추출 정독 40건 (배치 1·2) — 실행 보고 (2026-07-30)

_대상: `cs_index/rw_reextract_next20_20260730.json`(배치 1, 20건) + `cs_index/rw_reextract_batch2_20260730.json`(배치 2, 20건).
지시서: [RW_REEXTRACTION_AGENT_BRIEF](RW_REEXTRACTION_AGENT_BRIEF.md) · [extract_prompt_v4_rw_addendum](extract_prompt_v4_rw_addendum.md) ·
[extract_prompt_v4_subdomain_checklist](extract_prompt_v4_subdomain_checklist.md). 직전 배치: [RW_REEXTRACT_150_20260730](RW_REEXTRACT_150_20260730.md).
소유자 검토용 원자료: `.docs/rw_reextract_next40_owner_review_20260730.json`._

## 결과

| 항목 | 값 |
|---|---|
| 정독 완료(`review_method=full_read`) | **40 / 40** |
| 정독 결과 item | **2,645** (자동추출 3,025 → 정독 2,645) |
| 신규 매수인 진술 `RW.BUYER` | **251** |
| 파생 항목 `confidence=med` 표시 | 133 |
| DB 저장 | **39** |
| 진술 조항 부재로 저장 스킵 | 1 (`9d650005bcadc556`, §5 참조) |
| 저장 오류 · 후퇴 스킵 · 과다분절 스킵 | **0 · 0 · 0** |
| `regress_overridden` | 30 |
| `PRAGMA integrity_check` | ok |
| 검증(taxonomy 실재·¶좌표·verbatim 원문 substring·polarity/confidence·bare RW·무내용 템플릿) | **오류 0건** |
| 백업 | `catalog.pre_rw_reextract_20260730T135942.sqlite` |

배정: 점수순(absence-net 고가치 하위영역 누락 + ctype + partial coverage + bare RW 비율) 상위 40건 →
문자수 균형(LPT) 5샤드 × 2배치 → 서브에이전트 정독(result JSON만 쓰기), **store·DB·git은 조율자 단독**.
세션 한도로 배치 2가 중단됐으나 문서 단위 체크포인트로 유실 없이 잔여 11건을 재배정해 완료했다.

### 선정에서 제외한 3건 (알려진 결손·퇴화 대상)

점수 1·2위였으나 [RW_REEXTRACT_150 §3](RW_REEXTRACT_150_20260730.md)이 원문·캐시 결손으로 판정한 문서다.
`full_read` 마커가 없어 후보 풀에 계속 재등장하지만 실제로는 재변환·별지 수집 대기 상태다.

| file_key | 사유 |
|---|---|
| `289475b069d75d1c` | Schedule 7.1(매도인 진술) 본문이 txt에 없음 — 별지 원본 수집 대기 |
| `00c09fbabb422f6c` | txt 캐시 문장 중간 유실 — 재변환 대기 |
| `44461a70c728b848` | SPA Exhibit C-2(환경보험 agreed form) 3문단 — 진술 조항 자체가 없는 별첨 |

**선정 로직에 반영할 것**: 후보 선정이 `full_read` 마커 부재를 기준으로 하므로, 결손으로 마커를 못 받은 문서가
영구히 상위에 재등장한다. 결손 대기 목록을 선정 단계에서 제외하는 편이 낫다.

### 하위영역 커버리지 (`audit_rw_coverage.py`, RW complete 913문서 기준)

| 하위영역 | 150건 배치 직후 | 이번 배치 후 |
|---|---|---|
| RW.IP | 61.4% | **62.5%** |
| RW.LABOR | 71.7% | **72.0%** |
| RW.REAL_ESTATE | 57.0% | **58.4%** |
| RW.INSURANCE | 55.4% | **55.9%** |
| RW.ENVIRONMENT | 61.9% | 61.9% (false-present 4건 제거와 신규 3건이 상쇄) |

문서 단위 신규 유입은 훨씬 크다 — BENEFITS 21문서 · SOLVENCY 18 · CORPORATE_GOVERNANCE 17 ·
REAL_ESTATE 15 · INVENTORY 15 · BROKERS 13 · DISCLOSURE 13 · ACCOUNTS_RECEIVABLE 13 · RELATED_PARTY 11 · IP 11.

## 1. 항목 수가 줄었으나 전부 정정이다 — 하락 도메인 전건 검증

항목 총계는 3,025 → 2,645로 줄었다. 하락 도메인을 **전건 원문 대조**했고, 모두 자동추출의 오류 제거였다.

| 하락 도메인 | 문서수 | 성격 |
|---|---|---|
| bare `RW` | 18 | 하위영역 없이 뭉갠 것을 구체 노드로 치환 — **개선** |
| `RW.CUSTOMERS_SUPPLIERS` | 6 | **전건 false-present** (아래 검증) |
| `RW.DISCLOSURE` | 6 | 선행조건(CP) 문장 오분류 제거 |
| `RW.ENVIRONMENT` | 4 | **전건 false-present** (아래 검증) |
| PERMITS·CONTRACTS 각 4, REAL_ESTATE·CAPITALIZATION·ABSENCE_OF_CHANGES 각 3 | | 범위 밖 긁어오기·중복 제거 |

### RW.ENVIRONMENT 하락 4건 — 전건 false-present 확정

이 프로젝트의 발단이 환경 false-absence였으므로 최우선 확인 대상이다. 결과는 **반대 방향 오염**이었다.

| file_key | 기존 DB 노드 | 원문 환경 어휘(전문 grep) | 판정 |
|---|---|---|---|
| `1c3db4ca335c4f39` | `RW.ENVIRONMENT.COMPLIANCE` | **0건** | false-present |
| `d1696613b9214743` | `RW.ENVIRONMENT.COMPLIANCE` | **0건** | false-present |
| `7bb588f0c1637a71` | `RW.ENVIRONMENT.COMPLIANCE` | **0건** | false-present |
| `167299b34d606e60` | `RW.ENVIRONMENT` | 1건(¶137 **정의조항** UN Global Compact·OECD 가이드라인 인용) | false-present (진술 조항은 ¶383–390뿐) |

grep 어휘: `환경|수질|폐기물|유해|오염|토양|화학물질|environment|hazardous|pollut|contaminat`.

**기전이 특정됐다.** 자동추출은 포괄적 법령준수 진술 한 문장을 여러 하위 도메인으로 **복제**한다.
`7bb588f0c1637a71` ¶21(법령준수) 한 문장이 `AUTHORITY.NO_CONFLICT` · `COMPLIANCE.GENERAL` ·
`ENVIRONMENT.COMPLIANCE` · `LITIGATION.NO_PENDING` 4개 도메인으로 들어가 있었고, `1c3db4ca335c4f39`도 동형이다.

### RW.CUSTOMERS_SUPPLIERS 하락 6건 — 전건 false-present 확정

전부 **진술 조항 범위 밖 문단에 '고객/customer' 어휘가 우연히 등장**한 경우다.

| file_key | 기존 근거 위치 |
|---|---|
| `c9fabb4ac4ba7eea` | 반부패·독점규제 준수정책 **부속서** ¶779–785 |
| `953488d0ea9cabd1` | Seller Disclosure Letter 해석 **boilerplate** ¶671 |
| `44fe31b52107c3c9` | ¶154 **"정보에 대한 접근" 확약(COV)** — "매수인이 대상회사의 임직원, **고객** 기타 계약 상대방을 접촉하지 않도록 한다" |
| `e45d3402878d30f6` | ¶152 (위와 동일 조항) |
| `e7ce3f8a57347935` | 양도대상계약 **정의조항** ¶65 + 확약 ¶176 |
| `167299b34d606e60` | Schedule B/C **특별승인사항(확약 목록)** |

## 2. 자동추출 결함의 단일 뿌리 — 추출기가 진술 조항 범위를 경계하지 않는다

40건 정독으로 확인된 결함은 세 갈래지만 원인은 하나다.

### (1) 별지 편입형 과소추출 — 범위를 너무 좁게 잡는다

본문 진술 조항이 별지·별첨·Schedule·공개목록을 **인용만** 하고 실질 진술은 별지에 있는 형태다.
[RW_REEXTRACT_150 §4](RW_REEXTRACT_150_20260730.md)가 9건을 보고했는데, 이번 40건에서는 **과반**이 이 형태였고
국문 계약에서는 예외가 아니라 **지배적 형태**다. 대표 사례:

- `5059bb5bca958b21`(CB인수): 본문 제3조는 "별지 3.1·3.2 기재 사항" 인용만, 실질 진술 전부가 별지(별지 3.2에 발행회사 진술 19개 항) → **44→80항목**, IP·LABOR·REAL_ESTATE·ENVIRONMENT·INSURANCE·BENEFITS 신규
- `ead5102fdaeb9104`: ¶126이 편입 한 줄. **83항목 중 66항목이 별지 5.1(8)(¶355–408)에서** 나왔다
- `4997e306e66695ec`: REAL_ESTATE 10항목이 **전부** 편입된 공개목록(¶438–1331)에서만 나왔다 — 본문만 읽는 추출기는 이 문서의 부동산 진술을 구조적으로 0건으로 본다
- **이중 편입**: `6d9ee0f13c0d7155`(제4조→별첨 2→공개목록), `18951fc609380244`, `4e95c9b4b7181e1b`, `e7ce3f8a57347935`
- `3a8f1f6844464a84`: 별지 6.1(7) **주식근질권설정계약서 제4조**에 별도 근질권설정자 진술 8건이 중첩

### (2) 범위 밖 긁어오기 → false-present — 범위를 너무 넓게 잡는다

진술 조항 밖 문서에서 도메인 어휘를 긁어 present로 만든다. 정량 사례:

| file_key | 자동추출 | 진술 조항 범위 내 | 긁어온 출처 |
|---|---|---|---|
| `167299b34d606e60` (영문 SHA) | 57항목 | **1항목**(¶389) | 정의조항, Schedule B/C 확약목록, Severability·Release of Liability boilerplate, **Schedule E 임직원 발명양도·기밀유지 서식** |
| `e7ce3f8a57347935` (ATA/BTA) | 209항목 (`RW.BUYER` **75**) | 진술 ¶123–169, 매수인 진술은 **4문단** | ¶59 자산 정의, 별첨 A 자산목록, **별첨 C/D 양도증서·매도증서 서식** |
| `c9fabb4ac4ba7eea` | 76항목 | **28항목** | 정의조항, 공시목록, **반부패 준수정책 부속서 ¶733–800** |
| `830df8ae07fc25d7` | 108항목 | 40항목 | 선행조건 ¶75, 면책 ¶107, 우선주 발행조건 ¶335 |
| `b98ed3a7aa24d41d` | 136항목 | 111항목 | **Article VI 선행조건 ¶290–310에서 18항목** |
| `953488d0ea9cabd1` | 228항목 | — | closing deliverable ¶165, Disclosure Letter boilerplate ¶670–671, Non-Recourse boilerplate ¶673, Schedule A 취득세 계산표 ¶701 |

### (3) 무내용 템플릿 proposition — 내용을 읽지 않는다

`"The seller or company makes the representation set out in the quoted paragraph."` 형태다.
`953488d0ea9cabd1`은 228항목 중 **173건(76%)**이 이것이었다. **코퍼스 전체 정량**:

```
RW 항목 총계                          58,318
  무내용 템플릿 proposition           17,255  (29.6%)
RW 항목을 가진 문서                      946
  그런 항목을 1건 이상 포함하는 문서       390  (41.2%)
```

이는 검색 랭킹에 직접 영향이 있다. [ranking-bottleneck 판단](V4_PLAN.md)대로 개념 질의의 의미 랭킹은 T4로 넘겼으나,
**랭킹이 읽을 문서 측 신호도 30%가 비어 있다** — 위 문장은 어떤 임베딩·BM25에도 판별 정보를 주지 않는다.
T4 baseline 측정 시 이 항목들을 분리하지 않으면 결과가 해석 불가능하다.

## 3. RW.ENVIRONMENT 게이트 재검토 필요 — 오염 모집단 18건 특정

[env 게이트 개방](../MEMORY.md)은 부재 풀 89건 검증(precision 100%)에 근거했으나 **present 쪽은 검증하지 않았다.**
이번에 기전이 특정됐으므로 코퍼스 전체를 스캔했다:

```
RW.ENVIRONMENT* 항목을 가진 문서                                573
  유일한 환경 노드가 RW.ENVIRONMENT.COMPLIANCE 인 문서            132
    그중 원문 전체에 환경 어휘가 0건인 문서                        18   ← 확정 오염
```

이번 배치가 정독으로 잡은 3건(`1c3db4ca335c4f39`·`d1696613b9214743`·`7bb588f0c1637a71`)이 **모두 이 18건 안에 있다** —
표본이 아니라 모집단을 특정한 것이다. 잔여 15건은 원문에 환경 어휘가 0건이므로 판단 여지 없이 기계적 정정이 가능하다.

**소유자 판단 필요**: (a) 15건 정정을 승인할지, (b) "환경 진술이 있는 계약" 질의의 정밀도가 그만큼 과대평가돼 있었다는
점을 게이트 결정에 반영할지. 정정은 이번 정독 범위 밖이므로 DB를 건드리지 않았다.

## 4. 다음 배치 표적 제안 — RW.BUYER 과다추출 코호트 16건

브리프 표적 우선순위 1번은 "매수인 진술 **누락**"이었으나, 반대 방향인 **과다추출**도 동등하게 강한 선별자다.

```
RW.BUYER 항목을 가진 문서 776 · 문서당 중위값 6 · p90 15
  30건 이상인 문서 18 (최대 145)
```

이 코호트에서 이번 배치에 포함된 2건은 **둘 다 과다추출로 확인**됐다:

| file_key | DB buyer | 정독 후 | 확인 내용 |
|---|---|---|---|
| `e7ce3f8a57347935` | 75 | **6** | 실제 매수인 진술은 4문단(¶166–169) |
| `3d2730d9c2c6accb` | 55 | **6** | — |

표본 2/2가 결함이므로 **잔여 16건**(최상위 `9c1528aef1b30170` 145건, `3dfdf6186cf88ebe` 83건=전체의 73%,
`7bb126868c4a94b2` 53건, `eb084b4ee0566915` 51건 등)을 다음 배치 표적으로 제안한다.

## 5. 설계 공백 — 확정된 부재를 DB에 기록할 경로가 없다

`9d650005bcadc556`(SPA **수정계약**, 67문단)은 전문 정독으로 "원계약을 인용만 하고 자체 진술 조항이 없음"을 확정하고
브리프대로 `items: []` + `reason`을 남겼다. 그러나 store는 이를 `skipped_no_items`로 **스킵**한다 —
150건 배치에서도 같은 이유로 11건이 스킵됐다.

**부재 질의가 목표인 프로젝트에서 정독으로 확정한 부재를 저장할 수 없다.** 이 문서들은 DB상 여전히 "미평가"로 남아,
`present=false`(평가 후 부재)와 구분되지 않는다. 부재 질의 정밀도를 올리려면 이 경로가 필요하다.
(예: `items: []` + `full_read` 마커를 `body_status=complete` + 전 하위영역 `present=false`로 기록)

## 6. 정독이 후퇴 가드를 override한 30건

`full_read` 마커가 설계대로 가드를 해제했다. 문서별 하락·상승 도메인과 `reason`은
`.docs/rw_reextract_next40_owner_review_20260730.json`의 `regress_overridden` · `domain_drop_detail`에 있다.
§1에서 하락 도메인을 전건 원문 대조했으므로 **이번 배치는 사후 검토 부담이 없다** — 민감 도메인(환경·고객공급업체)은
위 표로 근거를 제시했고, 나머지는 bare RW 치환과 CP/COV/정의조항 오분류 제거다.

## 7. [RW_REEXTRACT_150 §4] 기재 정정 — "창작 leaf"는 결함이 아니었다

150건 배치 보고서가 `RW.DISCLOSURE.ACCURACY`를 "실재하지 않는 leaf 창작"으로 기록했으나 **사실이 아니다.**
이 노드는 `RW.DISCLOSURE`와 함께 taxonomy_version 6에 `origin=seed`로 들어온 실재 노드이고(`status=active`),
사후 승격 이력도 없다(`v4_taxonomy_action_log` 0건). 기계 검증 결과:

- DB의 RW 항목 중 실재하지 않는 `taxonomy_id`: **0건**
- 자동추출 result 파일에서 실재하지 않는 `taxonomy_id`: **0건**

150건 보고서 §4에 정정을 반영했다. 자동추출 결함 목록은 §2의 세 갈래로 확정된다.

**조율자 오류 기록**: 이 잘못된 정보를 배치 2 resume 샤드 프롬프트에 "이 leaf는 실재하지 않으니 쓰지 마라"로 넣었다.
브리프가 원래 "확실한 leaf를 모르면 도메인 노드를 써라"이고 에이전트들이 도메인 노드를 주로 사용했으므로
결과는 한 단계 거친 유효 분류이며 무효 값은 없다(검증 오류 0건). 재작업은 불필요하다고 판단했다.

## 8. 회귀 측정

- `eval_search.py`: total 12 · pass 6 · fail 0 · unscored 6 — **회귀 없음**(직전과 동일)
- `eval_v4_gate.py --pooled`: 26 질의 중 scored 16 · pending_verification 4, **unjudged pool item 493**.
  `present_mean_relative_recall` legacy 0.9412 / v4 0.0982. 부재·존재·비교 전 질의의 precision 셀은 여전히 비어 있다 —
  소유자 판정 없이는 산출되지 않는 구조다.
- `burndown.py`: RW 부재 질의 **가능 0 · 차단 1,800**, `family_gated=Y` — 변동 없음.

따라서 **이 재추출로 RW 부재정밀도가 회복됐다고 주장할 수 없다.** 게이트 해제는 §9.1 체크리스트 2·5
(소유자 라벨링·표본 원문대조)가 남아 있고, 이번 배치는 그중 "표본 원문대조" 재료를 40건 추가했을 뿐이다.

## 9. 확보한 부재 확정 사례 (골든 세트 부재 질의 후보)

정독 전문 + 어휘 grep 교차확인으로 확정한 것들이다. Gate B 라벨링이 유일한 병목인 상황에서 정답 재료가 된다.

- `167299b34d606e60`(영문 SHA): 회사 진술이 통째로 없음 — TAX·LABOR·IP·ENVIRONMENT·REAL_ESTATE·INSURANCE·PRIVACY·BENEFITS·PRODUCTS·CUSTOMERS_SUPPLIERS·RELATED_PARTY·CONTRACTS·FINANCIAL·CAPITALIZATION·ABSENCE_OF_CHANGES·LITIGATION·PERMITS·COMPLIANCE 전부 부재
- `49a2e1b07786778c`(37.36% 소수지분): LABOR·IP·ENVIRONMENT·PRIVACY·INSURANCE·REAL_ESTATE·BENEFITS·CONTRACTS·RELATED_PARTY·PRODUCTS·ABSENCE_OF_CHANGES·**COMPLIANCE** 부재
- `1c3db4ca335c4f39`: TAX·ENVIRONMENT·INSURANCE·PRODUCTS / `87fe350276303377`: PRIVACY·INSURANCE·PRODUCTS·CUSTOMERS_SUPPLIERS
- `6b490cb70a9e2d62`: BENEFITS·SOLVENCY / `b98ed3a7aa24d41d`: PRIVACY·PRODUCTS·IT·INVENTORY·GOVERNMENT_CONTRACTS
- `830df8ae07fc25d7`: **RW.BUYER 부재**(회사·이해관계인 → 투자자 일방향 계약) / `7bb588f0c1637a71`: LABOR 및 매수인 진술 부재
- `2a85f1dd1f73b0e2`(ATA/BTA): 부동산이 **Excluded Asset**이라 REAL_ESTATE 부재, 개인정보는 §8.4 **확약**이라 PRIVACY 부재

## 10. 원문·캐시 이상 (재변환 후보)

- `830df8ae07fc25d7`: 별지1 제8조① 담보제공·입보 **표가 헤더 행만 있고 데이터 행 없음**(¶594–603) — 해당 항목만 `confidence: low`.
  테두리 없는 표에 대한 변환기 약점 가능성. 전환사채/신주인수권부사채 표(¶507–518)도 무데이터지만 ¶479("그 이외의 발행 주식은 존재하지 아니한다")와 정합
- `e7ce3f8a57347935`: 부록 헤더가 앞 문단에 병합(`...입니다.부록 4.6`, `해당사항 없음부록 4.9`) — 내용 유실 아님
- `c97356967ef00c57`: 별지 5.1(8) **항 번호만** 유실(본문 교차참조로 역산 확인, 본문 온전) → 마커 유지
- `953488d0ea9cabd1`: Seller Disclosure Letter 원문이 txt에 없음(외부 문서). 본문 진술 자체는 완결 → 마커 유지
- 미첨부 공개목록/별첨: `49a2e1b07786778c`·`ead5102fdaeb9104`·`bb0f559e346407cf`(협상 초안, ¶270에 미작성 명기)·`e7ce3f8a57347935`(부록 4.4).
  모두 진술을 **차감**하는 예외 목록이므로 진술 본문 온전 → 마커 유지

## 다음

1. **§3의 환경 오염 15건 정정 승인** — 판단 여지 없는 기계적 정정, 소유자 결정 대기
2. **§5의 부재 저장 경로 설계** — 부재 질의 목표와 직결된 공백
3. **§4의 RW.BUYER 과다추출 코호트 16건**을 다음 정독 배치 표적으로
4. §2(2)를 추출 프롬프트에 반영 — "진술 조항 범위 밖(정의조항·확약·선행조건·boilerplate·별첨 서식)에서 항목을 만들지 않는다"
5. §2(3) 무내용 템플릿 17,255건(390문서) — T4 baseline 측정 전 분리 또는 재생성
6. Gate B 소유자 라벨링(unjudged 493건) — RW 게이트 해제의 유일한 남은 경로
7. 선정 로직에서 결손 대기 문서 제외(위 "선정에서 제외한 3건")
