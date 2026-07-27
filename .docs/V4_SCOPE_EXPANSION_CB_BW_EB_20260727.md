# V4 코퍼스 범위 확장·본문 완전성 교정 (2026-07-27)

## 목적

V4 전 항목 추출 대상이 SPA·SSA·ATA/BTA·SHA에 머물지 않도록 아래 증권계약
유형을 정식 코퍼스 범위에 포함했다.

- CB 인수계약: CBSA 포함
- CB 매수계약: Note Purchase Agreement/NPA 포함
- BW 인수계약: BWSA 포함
- W 매수계약: Warrant Purchase Agreement/WPA 포함
- EB 인수계약: EBSA 포함

## 선정·유형 규칙

- 처리 우선순위는 `SPA → CB인수 → CB매수 → BW인수 → W매수 → EB인수 →
  SSA → ATA/BTA → SHA`로 변경했다. 증권계약이 기존 SSA 잔여분 뒤로 밀리지
  않게 하기 위한 순서다.
- 폴더와 파일명 신호를 함께 사용해 `CB인수|CB매수|BW인수|W매수|EB인수`를
  canonical 유형으로 정규화했다.
- SHA·RFR/co-sale 파일이 SSA 폴더에 있어도 SHA로 바로잡는다.
- Exhibit, Schedule, Disclosure Letter, legal opinion, closing checklist,
  schedule of exceptions, term sheet/TS, CPS·CB terms, series certificate,
  발행결정 공시 등은 계약 본체 표본 수에서 제외한다.

## 추출·감사 교정

- 뒤쪽 Schedule의 `Article` 표제가 앞쪽 본 계약의 조항 범위를 덮어쓰던 문제를
  수정했다.
- 짧은 atomic hint가 없는 장문 본문도 물리 문단 단위로 전수 검토한다.
- 표준 조항 제목을 쓰지 않는 계약은 `unscoped_body_paragraphs`에 원문 좌표를
  보존하고, 확정 leaf 또는 pending taxonomy 후보로 분류한다.
- “계류 중인 소송·중재 없음”과 중재합의/분쟁해결 조항을 분리했다.
- 별지 중복 제거 키에 `storage_file_key`를 포함해, 서로 다른 별지 파일의 동일
  문단 번호·문구가 하나로 합쳐지지 않게 했다.
- 모든 본문 family가 `not_evaluated`인 문서는 감사 issue가 되며, 실질 문단이
  item이나 후보 어느 쪽에도 없으면 `body_paragraph_unrepresented`가 된다.
- 후보 검토로 확정된 기존 item을 재추출 시 보존하면서 `item_ref`가 충돌하면
  고유한 `TC` 참조로 재번호화한다.

## 처리 결과

기존 600건은 새 본문 범위·별지 규칙으로 재처리하고, 범위 교정된 새 300건을
추가 적재했다.

최종 세 번째 300건 구성:

| 유형 | 문서 수 |
|---|---:|
| SPA | 35 |
| CB 인수 | 121 |
| CB 매수 | 3 |
| BW 인수 | 34 |
| W 매수 | 1 |
| EB 인수 | 15 |
| SSA | 91 |
| 합계 | 300 |

세 번째 배치는 기존 교정 산출물 290건을 재사용하고, 강화된 유형·부속문서
필터에 따라 10건만 계약 본체로 교체했다. 생성 결과는 원자 item 25,939개,
pending 후보 10,403개다.

운영 DB 최종 상태:

- V4 원자 item 98,904개; FTS 98,904개 일치
- V4 coverage 문서 968건
- taxonomy 후보: pending 31,083개, merged 295개, rejected 16개
- `RW.SOLVENCY` 비말단 item 0개
- 전체 본문 미평가 문서 0건
- stale item 0개
- resolution item 참조 295개 중 누락 0개
- SQLite integrity `ok`, FK violation 0

구조 감사에서는 세 배치 모두 error 0, 본문 미평가 0, 좌표 누락 0이었다.
review 상태는 별지·본문의 미확정 명제를 pending 후보로 보존한 결과다.

## 검증

- 전체 테스트: 228 passed, 1 skipped
- V4 Gate B: 36/36 scored, V4 recall 1.0000
- 정독 문서 수 감소율: 58.31%
- T1/T2 골든 검색: fail 0
- 자동 후보 검토 dry-run: 31,083개 중 안전한 자동 병합·기각 0개

후보는 근거 없이 자동 병합하지 않았다. 다음 taxonomy 보강 단계에서는 후보를
문구·가장 가까운 leaf·유형별로 묶어 반복 명제를 우선 검수해야 한다.

## 복구점과 주요 산출물

- 운영 적재 전 백업:
  `.backups/v4_scope_body_corrections_pre_store_20260727/cs_index_backup_20260727_155517`
- 최종 300건 manifest:
  `cs_index/v4_expansion_03_scope300_final_manifest.json`
- 최종 감사:
  `cs_index/v4_expansion_03_scope300_final_audit.json`
- 저장 보고:
  `cs_index/v4_expansion_03_scope300_final_store.json`
- 범위·비말단 보정 보고:
  `cs_index/v4_scope_corrections_applied.json`
- 후보 dry-run:
  `cs_index/v4_candidate_review_scope300_dry_run.json`
