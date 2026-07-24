# V4 별지 물리 문단 완전성 교정

작성일: 2026-07-24

## 발견된 문제

기존 final review는 사전 alias에 잡힌 별지 item만 검수한 뒤, 실제로 읽지 않은
Schedule·Annex·Exhibit·Disclosure Schedule의 `source_coverage`도 complete로
바꾸고 있었다. 그 결과 별지 원문은 txt 캐시에 있어도 V4 item이나 pending
후보로 남지 않는 조용한 누락이 발생했다.

두 300건 확장 배치 감사:

- 배치 01: 별지 물리 문단 15,160개 중 기존 표현 436개, 비원자·공백 8,370개,
  표현되지 않은 실질 문단 6,354개
- 배치 02: 별지 물리 문단 17,231개 중 기존 표현 565개, 비원자·공백 9,424개,
  표현되지 않은 실질 문단 7,242개

source inventory가 동일한 물리 별지를 여러 family에 반복 연결하는 구조여서,
family row를 그대로 순회하면 같은 별지 문단이 최대 6번 중복될 수도 있었다.

## 교정

`finalize_v4_remaining_nine.py`를 다음과 같이 변경했다.

- `(storage_file_key, ¶, 원문)` 기준으로 물리 별지 문단을 정확히 한 번 검수
- 기존 규칙으로 분류 가능한 문단은 실제 법적 family의 source item으로 생성
- 분류되지 않는 실질 문단·표 행·`None/없음`은 source 좌표가 있는 pending
  taxonomy 후보로 보존
- 동일 물리 source와 연결된 모든 family의 source coverage는 후보가 남는 동안
  partial로 유지
- 순수 Schedule 제목·공백·비원자 리드인은 후보로 만들지 않음
- 같은 원문이 다른 source나 좌표에 있는 경우를 잘못 제거하지 않도록
  item/candidate dedupe를 source 좌표 기준으로 변경
- `refinalize_v4_batch.py`를 추가해 기존 코호트를 재선정하지 않고 raw/pre
  artifact에서 개선된 final result를 다시 생성

v13에서 `RW.SOLVENCY.FRAUDULENT_TRANSFER`를 추가한 뒤 기존 broad
`RW.SOLVENCY` item이 non-leaf가 된 22건을 발견했다. 이를
`RW.SOLVENCY.GENERAL` leaf로 분리해 taxonomy v14, active node 409개로
교정했다.

문서 재저장 때 taxonomy 관리로 해결된 item이 지워지는 문제도 함께 막았다.
해결 item을 보존하거나 동일한 새 추출 item에 action log의 item ID를 다시
연결하며, 반복 재저장에도 동일하게 동작한다.

## 600건 재생성·운영 교정

배치 01:

- item 21,047개
- source item 7,708개
- pending 후보 4,914개
- source pending 후보 3,847개
- partial source 1,126개
- 감사 pass 57, review 243, pending/error 0

배치 02:

- item 22,574개
- source item 9,520개
- pending 후보 5,314개
- source pending 후보 4,114개
- partial source 1,293개
- 감사 pass 52, review 248, pending/error 0

운영 반영 전 WAL-safe 백업:

- `.backups/v4_annex_completeness_pre_store_20260724/cs_index_backup_20260724_135349/`

운영 DB:

- taxonomy v14 / schema revision 1R3 / active node 409개
- V4 item 47,139개 / source item 17,712개
- 평가 문서 669개
- source coverage: complete 851, partial 2,419, missing 291
- 후보 상태: merged 294, rejected 16, pending 10,401
- source pending 후보 7,961개
- FTS row 47,139개로 item 수와 일치
- SQLite integrity `ok`, foreign-key violation 0
- taxonomy resolution item reference 294개 중 missing 0

## 완전성 검증

source item 17,712개와 source pending 후보 7,961개, 총 25,673개의 원문을
현재 txt 캐시와 대조했다.

- 좌표 일치: 25,673/25,673
- 좌표 missing/mismatch: 0
- partial source coverage가 없는 source pending 후보: 0
- source coverage 연결이 없는 source item: 0
- incomplete source를 둔 complete annex coverage: 0
- source pending 후보를 둔 complete annex coverage: 0

`available_source_not_complete` audit issue는 이제 오류가 아니라 미해결 후보가
있어 의도적으로 partial을 유지한다는 review 신호다.

## 회귀

- Gate B 36/36 scored
- V4 recall 1.0000
- legacy 정확구문 recall 0.3343
- 원문 정독 필요 문서 24,647→10,675, 56.69% 감소
- T1/T2 fail 0
- 전체 테스트 214 passed, 1 skipped

데이터가 47,139 item으로 증가하면서 Gate V4 측정시간 합계가 약 95초가
되었다. 현 pagination이 매 페이지마다 전체 결과를 재구성하는 것이 원인이므로
다음 단계에서 SQL count/page query로 교체한다.
