# V4 검색 성능 보강 (2026-07-24)

## 변경 사항

- 중복 포함(`show_duplicates=true`) 원자 명제 검색은 전체 결과를 Python으로
  읽은 뒤 잘라내지 않고, SQL에서 전체 건수·문서 수·stale 건수를 집계하고
  `LIMIT/OFFSET`으로 해당 페이지만 읽도록 변경했다.
- 검색 결과의 body/annex/source/taxonomy 후보 커버리지는 문서마다 반복 질의하지
  않고 family 단위로 한 번에 읽어 계산한다.
- 부재 검색도 문서마다 원자 명제 존재 여부를 조회하지 않고, 대상 taxonomy
  subtree의 문서별 존재 건수를 한 번의 그룹 질의로 계산한다.
- 응답의 `total_items`, `total_documents`, `stale_items`, `coverage`,
  `confirmed_absent`, `needs_review` 의미는 유지했다.

## 검증 결과

- Gate B: 36/36 scored
- V4 현재 색인 기준 recall: 1.0000
- legacy recall: 0.3343
- 정독 대상 문서 감소: 56.69%
- V4 게이트 누적 검색 시간:
  - 별지 완전성 교정 직후: 약 95,064 ms
  - SQL 페이지네이션만 적용: 약 45,156 ms
  - 커버리지/부재 일괄 조회 적용: 2,043 ms
  - 최초 대비 약 97.9% 감소
- 전체 테스트: 214 passed, 1 skipped

측정 결과는 `cs_index/v4_search_performance_gate.json`에 보존했다.

## 다음 단계

검색 병목과 정확도 회귀가 없으므로, 미처리 taxonomy 후보를 고신뢰 규칙으로
정리한 다음 아직 평가하지 않은 SPA 300건을 다음 확장 배치로 진행한다.
