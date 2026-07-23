# V4-2 나머지 9건 사전분류 보고서

- taxonomy version: 8
- 문서: 9건
- 사람 검수 대기 item: 528개
- taxonomy·문맥 검토 후보: 451개
- 운영 DB 적재: 하지 않음

이 결과는 canonical·alias 직접 일치에 기반한 보수적 사전분류다. 모든 item은
`needs_review`, 모든 평가범위는 `partial`로 유지한다. 사람 검수와 원자성 확인 전에는
V4 완료 또는 조항 부재의 근거로 사용할 수 없다.

| file_key | 유형 | 언어 | item | 후보 | 별지 source |
|---|---:|---:|---:|---:|---:|
| `a51842fc51010f69` | SPA | 영문 | 170 | 16 | 25 |
| `3c86175c4821fa83` | SPA | 국문 | 7 | 70 | 4 |
| `b324cb8bdf00015a` | SSA | 국문 | 206 | 47 | 13 |
| `660fc9d64566ba0e` | SSA | 국문 | 6 | 68 | 3 |
| `a5da55951cfdabfb` | SHA | 국문 | 0 | 4 | 0 |
| `0df5e9d7e1e7c893` | SHA | 영문 | 25 | 96 | 6 |
| `5853fe0540a72d6c` | SHA | 영문 | 104 | 104 | 19 |
| `b6fd6ff14e51e05f` | ATA/BTA | 국문 | 10 | 40 | 6 |
| `973d43e89040fb57` | ATA/BTA | 국영문 | 0 | 6 | 0 |

## 감사 결과

- 결과: `review` 9건, `error` 0건
- 감사 이슈: `available_source_not_complete` 75건
- 후보 원문·좌표 불일치: 0건
- 운영 DB: 기존 209 item·60문서 유지
- 감사 파일: `cs_index/v4_batch_02_pre_review_audit.json`

75건의 이슈는 입력에 존재하는 별지·Disclosure Schedule을 아직 사람이 전수검토하지
않았기 때문에 의도적으로 `partial`로 둔 결과다. 오류나 부재 판정이 아니다.

## 다음 검수 순서

1. 후보가 많은 문서부터 문단 문맥으로 기존 노드 병합·alias 추가·신규 leaf 여부를 판정한다.
2. 각 atomic unit의 독립 명제 누락과 복수 명제 뭉침을 수정한다.
3. 별지·Disclosure Schedule별 coverage를 complete/missing/unreadable로 확정한다.
4. 감사 pass 및 소유자 승인 결과만 운영 DB에 적재한다.
