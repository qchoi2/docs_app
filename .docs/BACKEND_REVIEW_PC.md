# BACKEND_REVIEW_PC — PC 로컬 실행 기준 백엔드 개선사항
_2026-07-09 · 기준 환경: Windows PC 로컬 실행. NAS/서버 상시운영을 기본값으로 보지 않는다._

## 1. 기준 환경 재정의

이 프로젝트의 기본 실행 환경은 **개인 Windows PC 로컬 실행**이다.

- 계약서 원본: PC 로컬 폴더 또는 네트워크 드라이브에서 **읽기 전용**으로 접근
- 색인 산출물: 반드시 PC 로컬 디스크의 `cs_index/`에 저장
- 웹앱 바인딩: 기본값 `127.0.0.1` 전용
- 외부 접속/공유/상시 서버 운영: 기본 범위 아님
- Docker, NAS, DSM, tmux, cron, inotify: 기본 구현 경로에서 제외하고 v2/고급 운영 메모로만 취급

## 2. 최우선 백엔드 개선 권고

### 2.1 설정/시크릿 저장소를 PC 로컬 기준으로 분리

현재 문서에는 `ANTHROPIC_API_KEY`를 UI에서 받는다는 원칙이 있으므로, 백엔드는 다음 저장 경계를 가져야 한다.

```text
%APPDATA%/contract-search/config.json
%APPDATA%/contract-search/secrets.json
%LOCALAPPDATA%/contract-search/logs/
<프로젝트 또는 사용자가 지정한 로컬 경로>/cs_index/
```

원칙:

- API key는 프론트엔드 저장소에 저장하지 않는다.
- API key는 git 저장소, `cs_index/txt`, `api_ledger.jsonl`, `agent_log.jsonl`에 기록하지 않는다.
- UI에는 저장 후 마지막 4자리만 표시한다.
- `.env`는 개발자용 백업 경로로만 둔다. 일반 사용자의 기본 경로는 UI 입력이다.
- 설정 우선순위는 `UI 저장 secret > 환경변수 > 미설정`으로 한다.
- `secrets.json`의 API key는 평문 저장 대신 **Windows DPAPI**(`CryptProtectData`,
  ctypes로 호출 — 추가 의존성 불필요)로 사용자 계정 단위 암호화 저장을 기본으로 한다.
  DPAPI를 쓸 수 없는 환경에서는 최소한 파일 ACL을 현재 사용자 전용으로 제한한다.

### 2.2 관리자 보호는 로컬 앱이어도 필요

웹앱이 로컬 PC에서만 열린다고 해도, API key 저장·파일 열기·색인 실행 기능이 있으므로 최소 보호가 필요하다.

MVP 권장:

- 기본 바인딩은 `127.0.0.1`만 허용
- 최초 실행 시 관리자 비밀번호 생성 또는 로컬 전용 토큰 생성
- 설정/색인/API 호출 엔드포인트는 관리자 인증 필요
- 상태 조회와 검색은 read-only로 분리
- CSRF 방어: 상태 변경 요청은 POST + CSRF 토큰 또는 same-site 쿠키 사용

### 2.3 장시간 작업은 Job Queue로 분리

색인, 재색인, 평가, API 답변 생성은 요청-응답 안에서 직접 오래 실행하지 않는다.

필수 엔드포인트:

```text
POST /api/jobs/index
POST /api/jobs/eval
POST /api/jobs/answer
GET  /api/jobs/{job_id}
POST /api/jobs/{job_id}/cancel
GET  /api/jobs/{job_id}/log
POST /api/settings/root-path/validate
GET  /api/catalog/facets
```

MVP는 별도 Celery 없이 표준 라이브러리 `queue.Queue` + worker thread 1개로 충분하다. 원칙은 **one writer**다. SQLite 쓰기 작업은 동시에 여러 개 실행하지 않는다.

추가 원칙 (2026-07-09 보강):

- **Job 영속화**: job 상태를 메모리 큐에만 두지 않고 SQLite `jobs` 테이블
  (`id, type, status, progress_done, progress_total, current_item, started_at, finished_at, error_code`)에
  기록한다. 앱 재시작 시 running으로 남은 job은 `failed(중단됨)`로 정리한다.
- **진행률 계약**: `GET /api/jobs/{job_id}`는 progress_done/progress_total/current_item을
  반환한다. UI_REVIEW_PC의 "423 / 1,204 files · 현재 파일" 표시가 이 필드에 대응한다.
- **협조적 취소**: worker는 파일 단위 체크포인트마다 취소 플래그를 확인한다.
  이미 커밋된 파일은 유지하고, 취소 시점까지의 부분 결과는 정상 증분으로 남는다.

### 2.4 SQLite 운영 규칙 강화

PC 로컬 디스크에 둘 때도 SQLite 동시성 규칙을 정해야 한다.

- `catalog.sqlite`는 PC 로컬 `cs_index/`에만 둔다.
- `PRAGMA journal_mode=WAL` 유지
- `PRAGMA busy_timeout=5000` 설정
- 색인 writer는 단일 worker에서만 실행
- 검색은 read-only connection을 짧게 열고 닫기
- 백업은 `sqlite3.Connection.backup()` 사용. 파일 복사만으로 WAL 누락이 생기지 않게 한다.
- 네트워크 드라이브에 SQLite를 두는 것은 금지한다.
- 대량 색인 종료 시 `PRAGMA wal_checkpoint(TRUNCATE)`를 1회 실행해 -wal 비대를 정리한다.
- 사용자 상태(북마크·저장된 검색·리서치 세션 등)는 `catalog.sqlite`가 아니라
  별도 `ui_state.sqlite`에 둔다. catalog는 재색인/`--full`로 언제든 재구축 가능한
  산출물이므로, 재생성 불가능한 사용자 데이터와 파일을 분리한다.

### 2.5 파일 접근 보안

웹 UI에서 원문 열기/내보내기를 제공할 때는 사용자가 임의 경로를 직접 넘기게 하지 않는다.

- 모든 파일 열기는 `file_key` 기준으로만 수행
- 실제 경로는 catalog에서 조회
- root allowlist 밖의 파일은 열지 않음
- `..`, 절대경로, URL, UNC 직접 입력은 API에서 거부
- `open_text.py`는 txt 캐시만 읽고, 원문 파일 직접 열기는 별도 관리자 기능으로 분리

### 2.6 API 호출 경로의 비용·레저·캐시를 중앙화

Haiku/Sonnet/Opus 호출은 반드시 `lib/budget.py`만 통과한다.

추가 권고:

- `api_ledger.jsonl` 기록은 atomic append로 처리
- jsonl 한 줄은 4KB 미만으로 유지하고(원자적 append 보장 범위), 웹앱 경로의 jsonl 기록은 job worker 경유 단일 writer로 수렴
- cache key는 `model + prompt_version + selected_chunks_hash + budget_version` 기준 (IMPLEMENTATION_BRIEF §2.7과 동일 기준으로 통일, 2026-07-09)
- API 요청/응답 로그에는 키와 원문 전체를 남기지 않음
- 사용자 확인 전에는 실제 호출하지 않음
- 연결 테스트는 최소 토큰/저비용 요청 또는 가능하면 모델 목록/경량 검증으로 제한
- `per_call_limit_usd`, `per_run_limit_usd` 중 하나라도 null이면 disabled

### 2.7 Agent Setup Wizard는 subprocess allowlist만 사용

PC 환경에서도 Agent Setup Wizard는 임의 명령 실행기가 되면 안 된다.

허용:

```text
claude --version
codex --version
node --version
npm --version
git --version
python --version
```

원칙:

- `shell=True` 금지
- timeout 필수
- stdout/stderr 길이 제한
- 환경변수 출력 금지
- 설치 명령 자동 실행은 MVP 제외
- 안내 문구는 Windows PowerShell / VS Code 터미널 기준으로 표시

### 2.8 백엔드 API 경계 정리

권장 API 그룹:

```text
GET  /api/health
GET  /api/corpus/status
POST /api/search
GET  /api/files/{file_key}/context
GET  /api/files/{file_key}/duplicates
POST /api/export/markdown
POST /api/export/csv
GET  /api/settings/runtime-api
POST /api/settings/anthropic-key
POST /api/settings/anthropic-key/test
DELETE /api/settings/anthropic-key
POST /api/settings/budget
GET  /api/admin/agents/status
POST /api/jobs/index
GET  /api/jobs/{job_id}
```

모든 POST 입력은 Pydantic 등으로 검증한다. Phase 1의 의존성 제한 때문에 FastAPI/Pydantic 도입 전 CLI MVP에서는 argparse 검증으로 충분하지만, 웹앱 단계에서는 요청 스키마를 명시해야 한다.

추가 계약 (2026-07-09 보강):

- `POST /api/search`는 처음부터 `limit`/`offset`(또는 cursor) 페이지네이션 파라미터를 받는다.
  UI-1의 "더 보기/페이지네이션" 요구가 확정돼 있으므로 나중에 스키마를 바꾸지 않는다.
  응답에는 `total`(dedup 그룹 수)과 `total_files`를 포함한다.
- `GET /api/catalog/facets`는 UI 고급 필터용으로 `ctype`, `lang`, `batch_label`의
  distinct 값과 건수를 반환한다. UI가 `type_rules.yaml`의 값을 하드코딩하지 않도록 한다.
- `POST /api/settings/root-path/validate`는 원본 계약서 루트 경로의 존재 여부,
  읽기 권한, 허용 확장자별 대략 파일 수, 네트워크 드라이브 여부를 반환한다.
  브라우저 폴더 피커의 절대경로 취득에 의존하지 않는다.
- `GET /api/jobs/{job_id}`는 UI가 1~2초 폴링할 수 있도록 `progress_done`,
  `progress_total`, `current_item`, `status`, `error_code`를 안정적으로 반환한다.
- FTS 질의어 이스케이프와 3자 미만 질의어 LIKE 폴백은 IMPLEMENTATION_BRIEF §2.6을 따른다.
  웹 API 계층에서도 사용자 입력을 원문 그대로 FTS MATCH 식에 넣지 않는다.

### 2.9 오류 메시지 표준화

프론트엔드에 raw exception을 그대로 노출하지 않는다.

권장 오류 코드:

```text
CONFIG_MISSING_API_KEY
CONFIG_BUDGET_NOT_SET
CONFIG_MISSING_KEY_AND_BUDGET
CONFIG_INDEX_PATH_NOT_LOCAL
INDEX_JOB_ALREADY_RUNNING
INDEX_ROOT_NOT_READABLE
SQLITE_BUSY
FTS_TRIGRAM_UNAVAILABLE
FILE_NOT_FOUND_IN_CATALOG
API_BUDGET_EXCEEDED
API_PROVIDER_ERROR
AGENT_NOT_INSTALLED
AGENT_LOGIN_UNKNOWN
```

각 오류는 사용자 메시지와 개발자 로그를 분리한다.

## 3. PC 기준으로 문서에서 걷어낼 표현

다음 표현은 기본 경로에서 제거하거나 고급 운영 메모로 내려야 한다.

- "개인 NAS의 계약서" → "개인 PC 또는 읽기 전용 원본 폴더의 계약서"
- "DSM 터미널/SSH" → "Windows PowerShell 또는 VS Code 터미널"
- "NAS tmux/Docker" → "고급/선택 운영"
- "cron/inotify" → "수동 재색인 또는 v2 파일 감시"
- "Synology NAS 기본 파이썬 고려" → "Python 3.10+ 권장, 3.9 호환 유지"

## 4. 백엔드 구현 우선순위 조정

PC 로컬 웹앱 기준으로는 아래 순서가 가장 안전하다.

1. CLI MVP 색인/검색 안정화
2. `cs_index` 로컬 경로 강제와 SQLite 백업 루틴
3. 검색 read-only API
4. Runtime API Settings와 Anthropic key 저장/마스킹/삭제
5. 예산·캐시·레저 중앙화
6. Job Queue 기반 색인 실행 UI
7. Agent Setup Wizard read-only 진단
8. AI 답변 UI
9. v2에서 파일 감시/자동 설치/원문 직접 열기 검토

## 5. 즉시 반영할 DoD

- [ ] 기본 실행 환경이 Windows PC 로컬로 설명되어 있다.
- [ ] `cs_index`는 PC 로컬 디스크에 두도록 강제되어 있다.
- [ ] NAS/Docker/DSM/tmux는 기본 경로가 아니라 선택/고급 메모로 내려갔다.
- [ ] `ANTHROPIC_API_KEY`는 UI 입력으로 저장하되 프론트엔드 저장소와 로그에 남지 않는다.
- [ ] Codex용 OpenAI API key 입력란은 없다.
- [ ] 색인/평가/API 호출은 job queue를 통해 실행된다.
- [ ] 임의 shell 명령 실행 기능이 없다.
- [ ] 백엔드는 raw exception을 사용자에게 노출하지 않는다.
- [ ] API key는 DPAPI 암호화(불가 시 ACL 제한)로 저장된다.
- [ ] job 상태가 SQLite에 영속화되고 진행률·협조적 취소를 지원한다.
- [ ] `/api/search`가 limit/offset 페이지네이션과 total/total_files를 포함한다.
- [ ] UI 상태 테이블은 `ui_state.sqlite`로 분리되어 `--full` 재색인에서 보호된다.
- [ ] 3자 미만 질의어(2음절 국문 용어, CP/DD/IP/RW 등)가 LIKE 폴백으로 검색된다.
- [ ] 대량 색인 후 WAL checkpoint가 실행된다.


## 6. UI 접점 추가 계약 — 2026-07-09

프론트엔드 hardening 반영을 위해 백엔드는 다음 사용자 화면 계약을 지킨다.

```text
- 필터 facets: catalog의 ctype/lang/batch_label 값을 동적으로 제공한다.
- 원본 루트 검증: 경로 문자열을 받아 존재/읽기권한/파일수 미리보기만 수행하고 원본을 수정하지 않는다.
- job 진행률: MVP는 GET /api/jobs/{job_id} 폴링을 기준으로 한다.
- warnings: search 응답의 warnings를 그대로 내려주어 UI가 short_term_fallback 등을 표시하게 한다.
- AI 상태: enabled boolean만 반환하지 말고 disabled_reason을 함께 반환한다.
- CSV: 서버가 CSV를 생성하는 경우 utf-8-sig로 응답한다.
```

AI disabled reason 우선값:

```text
missing_key
budget_not_set
missing_key_and_budget
no_selection
budget_exceeded
provider_error
```
