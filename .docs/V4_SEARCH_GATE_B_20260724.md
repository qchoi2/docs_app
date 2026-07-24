# V4-5 원자 명제 검색 및 Gate B 예비 평가

작성일: 2026-07-24
대상: 현재 V4 운영 DB(taxonomy v12, 승인 item 3,502개, 69개 문서)

## 구현 결과

하나의 읽기 전용 서비스(`v4_search.py`)를 CLI·웹·MCP 어댑터가 같이 사용한다.

- 존재 검색: taxonomy ID 또는 canonical/alias를 active 노드로 정규화하고 하위
  노드를 포함해 승인된 원자 item을 찾는다. 결과에는 `file_key`, `item_ref`,
  taxonomy, proposition, polarity, 주체·시점, 원문, ¶ 좌표, 본문/별지 출처,
  원문 최신성 및 coverage를 포함한다.
- 부재 검색: 본문 coverage가 complete이고, 별지가 complete/no_annex이며,
  coverage와 source의 해시가 현재 원문과 일치하고, 해당 family의 pending
  taxonomy 후보가 없을 때만 `confirmed_absent`로 반환한다. 그 외 미검출 문서는
  사유를 붙여 `needs_review`로 분리한다.
- 비교: 2~10개 file_key를 동일 taxonomy 기준으로
  `confirmed_present | confirmed_absent | needs_review` 중 하나로 분류하고
  원문·좌표·coverage를 함께 반환한다.
- 중복 제거 시 같은 dup_group의 대표 문서 하나를 선택하되, 그 대표 문서 안의
  복수 원자 item은 모두 보존한다.

### 인터페이스

- 기존 CLI:
  `python search_contracts.py --out cs_index --item RW.LABOR.NO_VIOLATION --polarity none_exist --json`
- 부재 CLI:
  `python search_contracts.py --out cs_index --item PAY.EARNOUT.PAYMENT --item-absent --json`
- 독립 CLI/비교:
  `python v4_search.py --out cs_index compare --item REM.CAP --file-key ... --file-key ... --json`
- 웹: `/v4-search`
- API:
  `POST /api/v4/items/search`, `POST /api/v4/items/compare`
- MCP 등록 모듈: `register_v4_tools(...)`가 기존 도구를 변경하지 않고
  `search_clause_items`, `compare_clause_items` 두 도구를 추가한다.

## Gate B 예비 평가

`data/v4_gate_b_golden.json`에 family별 존재 24개, 부재 6개, 비교 6개,
총 36개 질의를 고정했다. `eval_v4_gate.py`는 다음 두 경로를 비교한다.

- legacy: 현재 본문 FTS에서 taxonomy canonical/alias 정확구문으로 후보 문서를
  찾고, 해당 후보를 정독해야 한다고 계산
- V4: 승인 원자 item과 coverage를 직접 조회하고, stale/미평가 문서만 원문
  정독 대상으로 계산

2026-07-24 실행 결과:

| 항목 | legacy | V4 |
|---|---:|---:|
| 존재 질의 평균 recall | 0.3748 | 1.0000 |
| 누적 원문 정독 필요 문서 수 | 24,647 | 12,422 |
| 측정된 조회시간 합계 | 1,163.073 ms | 466.066 ms |

- 36개 모두 채점되었고 unscored는 0개였다.
- 여섯 부재 질의에서 각각 24~36개 문서만 `confirmed_absent`가 되었으며,
  V4 미평가 문서 2,061~2,075개는 모두 `needs_review`로 남았다.
- 여섯 비교 질의는 각각 present/absent/needs_review 3개 상태를 모두
  재현했다.
- 누적 원문 정독 필요량은 49.6% 감소했다. 아직 전체 코퍼스의 V4 평가가
  끝나지 않아 부재 질의에서 needs_review가 큰 것이 주된 잔여 비용이다.

## 판정과 한계

Gate B의 기능 경로와 비교 도구는 통과했다. V4 구조화 경로가 이 예비 집합에서
legacy 정확구문 후보 경로보다 낮지 않으므로 V4-6 제한 확장을 진행할 수 있다.

다만 이 결과의 reference는 독립적인 사람 검수 골드가 아니라 현재
`review_status=approved`인 V4 item이다. 따라서 1.000 recall은 “승인된 item을
구조화 검색이 누락하지 않았다”는 회귀 검증이며, 실제 계약서의 모든 명제를
사람이 독립 검수했다는 뜻은 아니다. 또한 pending taxonomy 후보 190개와
missing source 59개가 남아 있으므로 Gate A(완전성)는 미통과 상태다.

## 검증

- V4-5 관련 테스트: 13 passed
- 전체 회귀: 205 passed, 1 skipped
- `node --check static/v4-search.js`: 통과
- 실제 로컬 HTTP: `/v4-search` 200,
  `RW.LABOR.NO_VIOLATION + none_exist + 국문` 검색 1개 item/1개 문서 반환
