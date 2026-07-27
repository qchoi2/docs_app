# V4 taxonomy 후보 군집 검수·운영 반영 — 2026-07-27

## 결론

운영 DB의 pending taxonomy 후보 31,083건을 문구 정규화 기준으로 군집화하고,
원문 좌표 표본을 검수해 기존 leaf 병합과 신규 leaf 승격을 수행했다. 외부·유료
API는 사용하지 않았다.

- 정규화된 고유 군집: 21,794개
- 2건 이상 반복 군집: 4,837개, 후보 14,126건
- 신규 taxonomy leaf: 5개
- 신규 leaf 승격 시 직접 해결한 후보: 31건, item 31개
- 기존·신규 leaf로 추가 병합한 후보: 1,245건, 원자 item 1,272개
- 실제 family 기능이 달라 명시적으로 재분류한 body 후보: 55건
- 보수적으로 pending 유지: 29,807건

## 신규 leaf

| taxonomy_id | 의미 | 최종 item |
|---|---|---:|
| `REM.SEVERABILITY` | 일부 무효·집행불능과 나머지 조항의 효력 유지 | 5 |
| `REM.WAIVER` | 권리 불행사·지연·일부 행사의 비포기 효과 | 14 |
| `REM.NO_THIRD_PARTY_BENEFICIARY` | 비당사자 제3자의 권리·구제수단 배제 | 11 |
| `REM.BINDING_EFFECT` | 당사자·승계인·허용 양수인에 대한 구속효·이익귀속 | 15 |
| `REM.INDEMNITY.VOLUNTARY_ACT_EXCLUSION` | 배상권리자 측 자발행위가 원인인 손해의 배상 제외 | 38 |

taxonomy는 v14에서 v19로 올라갔고 활성 노드는 409개에서 414개가 되었다.
승격 계획과 결과는 각각
`cs_index/v4_taxonomy_promotions_20260727.json`,
`cs_index/v4_taxonomy_promotions_applied_20260727.json`에 보존했다.

## 기존 leaf 병합 보강

반복 문구를 다음과 같이 기존 canonical leaf로 통일했다.

- 정의·해석: `DEF.CONTRACT_TERM` 867, `DEF.AFFILIATE` 89,
  `DEF.LOSSES` 14
- 배상 제한·예외: `REM.NO_DOUBLE_RECOVERY` 63,
  `REM.FRAUD_CARVEOUT` 32, `REM.CONSEQUENTIAL.PUNITIVE` 29,
  `REM.CONSEQUENTIAL.LOST_PROFITS` 24
- 일반조항·구제: `REM.TERMINATION` 49,
  `REM.SPECIFIC_PERFORMANCE` 37, `REM.GOVERNING_LAW` 8,
  `REM.AMENDMENT` 7
- 그 밖에 `REM.INDEMNITY.PURCHASE_PRICE_ADJUSTMENT` 1

한 후보 문단이 복수 독립 명제를 포함하면 복수 item으로 원자화했다. 예를 들어
수정+권리포기 문단은 `REM.AMENDMENT`와 `REM.WAIVER`, 구속효+제3자 권리배제
문단은 `REM.BINDING_EFFECT`와 `REM.NO_THIRD_PARTY_BENEFICIARY`로 각각
물질화한다.

## 안전장치와 오탐 교정

- 교차 family 병합·승격은 호출자가 명시적으로 허용해야 하고 body 후보에만
  가능하다. Annex·Schedule 후보는 연결 family의 의미가 불명확하므로 자동
  재분류하지 않고 pending으로 유지했다.
- 분리가능성은 `provision/term`의 무효와 나머지 조항의 효력 유지가 함께 있는
  문형만 허용해, “거래를 불법으로 만드는 법령이 없음” 선행조건을 배제했다.
- 제3자 수익자 배제는 `third-party beneficiary`, 비당사자에게 권리를
  부여하지 않는 문형으로 좁혀, 지적재산권·주주권의 일반 제3자 언급을 배제했다.
- 사기 예외는 전액배상 또는 책임제한 미적용 문형으로 좁혀 D&O 보험상 사기
  면책 같은 다른 기능을 배제했다.
- 특정이행을 요구하지 않는 명시적 부정문과, 자발적으로 거래했다는 일반
  확인문은 각각 특정이행권·자발행위 손해 제외로 분류하지 않는다.
- UTF-8 승격 계획은 적용 전에 taxonomy id·parent·alias·candidate 상태를 모두
  preflight한다. 한 action의 alias 오류 때문에 앞 action만 부분 반영되는 것을
  방지하는 테스트도 추가했다.

## 운영 DB 결과

- `v4_clause_item`: 100,207
- `v4_item_fts`: 100,207
- 후보 상태: approved 31, merged 1,540, rejected 16, pending 29,807
- resolution item reference: 1,598, missing 0
- taxonomy 미등록 또는 family 불일치 item: 0
- stale item: 0
- 적용 후 동일 결정 규칙 재실행: merge 0, materialized item 0
- `PRAGMA integrity_check`: ok
- foreign key violation: 0

적용 전 백업:

- `.backups/v4_taxonomy_candidate_resolution_pre_20260727_1645/catalog.sqlite`
- `.backups/v4_taxonomy_v19_pre_candidate_merge_20260727_1702/catalog.sqlite`

국문 인자를 콘솔로 직접 전달한 초기 시도에서 2개 action만 인코딩이 손상된
상태로 커밋된 것을 즉시 발견했다. 해당 상태는 별도 백업한 뒤 첫 사전 백업으로
복원했고, UTF-8 JSON 계획 파일을 읽는 경로로 재적용했다. 최종 DB에는 손상된
label·alias가 남아 있지 않다.

## 검증

- 후보·분류·taxonomy 관리 집중 테스트: 30 passed
- 전체 회귀: 238 passed, 1 skipped
- T1/T2 `eval_search.py`: fail 0
- V4 Gate B: 36/36 scored, V4 recall 1.0000, 정독 문서 수 58.76% 감소

Gate B의 V4 측정시간은 100,207 item 기준 약 20.3초로 두 차례 반복 측정됐다.
정확도 회귀는 없지만, 47,139 item 시점의 과거 약 2.0초 기록과 직접 비교하면
코퍼스 규모 증가 이후 성능 재점검이 필요하다.

## 다음 단계

1. pending 29,807건 중 반복 군집의 다음 tranche를 family별로 검수한다.
2. source kind가 Annex·Schedule인데 일반조항으로 보이는 후보는 source inventory
   경계 오류인지 먼저 확인한 뒤에만 family를 교정한다.
3. Gate B present 검색의 SQL 실행계획과 인덱스를 점검해 100k item 성능을
   안정화한다.
4. 이후 남은 SSA → ATA/BTA → SHA 및 미처리 증권계약의 확장 배치를 계속한다.
