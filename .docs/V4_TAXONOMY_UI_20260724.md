# V4-4 UI-5 taxonomy 관리 화면

_기준일: 2026-07-24. 로컬 `catalog.sqlite` 전용이며 외부 API를 호출하지 않는다._

## 구현 결과

V4-3에서 운영 후보 큐에 저장한 190개 명제를 브라우저 버튼으로 처리할 수 있는
관리 화면과 트랜잭션 서비스를 구현했다.

- 화면: `/taxonomy`
- 후보 요약: `GET /api/v4/taxonomy/summary`
- 후보 묶음: `GET /api/v4/taxonomy/candidates`
- taxonomy 노드: `GET /api/v4/taxonomy/nodes`
- 일괄 처리: `POST /api/v4/taxonomy/candidates/resolve`

현재 190개 후보는 공백·구두점 정규화 문구, family, 근접 taxonomy를 기준으로
179개 묶음으로 표시된다. 목록에서 여러 묶음을 선택하더라도 동일 family일 때만
처리 버튼이 활성화된다.

## 처리 동작

### 기존 노드 귀속

- 활성 leaf 중 하나를 선택한다.
- 대상 노드와 후보 family가 다르면 거부한다.
- 후보 상태를 `merged`로 바꾸고 target taxonomy와 판단 사유를
  `resolution_json`에 저장한다.

### 신규 노드 승격

- canonical ID, 부모, 국·영문 이름, 정의, alias, 승격 근거를 입력한다.
- ID는 후보 family prefix를 가져야 하고 활성 부모도 같은 family여야 한다.
- 이미 조항 item이 직접 귀속된 leaf는 부모로 바꿀 수 없다. 기존 item을 남긴
  채 비말단 노드로 만드는 taxonomy 파손을 막기 위한 제한이다.
- canonical·alias가 다른 노드에 이미 분류되어 있으면 충돌로 거부한다.
- 성공하면 `origin=promoted` 노드를 만들고 taxonomy version을 1 증가시킨 뒤
  후보 상태를 `approved`로 바꾼다.

### 기각

- 기각 사유를 필수로 받는다.
- 후보 상태를 `rejected`로 바꾸되 원문, file_key, ¶좌표는 삭제하지 않는다.

세 동작 모두 `BEGIN IMMEDIATE` 단일 트랜잭션으로 실행된다. 이미 처리된 후보를
다시 처리하면 HTTP 409를 반환한다.

## 감사 추적

`v4_taxonomy_action_log`를 additive table로 추가했다.

- action: `merge|promote|reject`
- 처리 candidate ID 목록
- target taxonomy ID
- 입력 payload와 판단 사유
- UTC 처리시각

원문 후보는 삭제하지 않으므로 action log와 후보의 `resolution_json`을 함께
사용해 누가 어떤 의미로 분류했는지 재구성할 수 있다.

## 안전장치

- 로컬 앱의 기존 `127.0.0.1` 범위 안에서만 사용한다.
- 한 번에 최대 500개 후보만 처리한다.
- 복수 family 일괄처리, 다른 family 노드 귀속, 중복 ID, alias 충돌,
  이미 처리된 후보, 사유 없는 기각을 거부한다.
- 운영 화면을 확인하는 동안에는 실제 후보 처리 API를 호출하지 않았다.
  운영 DB는 taxonomy v12, pending 후보 190개, action log 0건 그대로다.

## 검증

- 서비스 단위 테스트:
  - 동일 문구 묶음과 문서 수 집계
  - 기존 노드 귀속과 action log
  - 신규 노드·alias 생성 및 version 증가
  - 기각 사유 필수
  - alias 충돌 전체 rollback
- 웹 통합 테스트:
  - `/taxonomy`와 세 읽기 API
  - 일괄 귀속 API
  - 이미 처리된 후보 409
- 실제 로컬 서버 읽기 확인:
  - `/taxonomy` HTTP 200
  - taxonomy v12
  - pending 190
  - 179 clusters / 190 candidates
- `node --check static/taxonomy.js` 통과
- 전체 테스트: 192 passed, 1 skipped

연결 가능한 브라우저 인스턴스가 현재 환경에 없어 실제 화면 캡처 기반 시각 QA는
수행하지 못했다. HTML 응답, JavaScript 구문, 임시 DB 기반 API/통합 테스트로
기능 경로를 검증했다.

## 산출물

- `taxonomy_admin.py`
- `static/taxonomy.html`
- `static/taxonomy.css`
- `static/taxonomy.js`
- `tests/test_taxonomy_admin.py`
- `tests/test_taxonomy_web.py`
- `v4_schema.py`의 `v4_taxonomy_action_log`

다음 단계 V4-5에서는 확정 V4 item을 CLI·웹·MCP 검색 조건으로 노출하고,
세부 골든 질의로 v3+정독 대비 recall과 정독량을 비교한다.
