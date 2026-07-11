# UI 구현 격차 분석 (현재 → UI-3)
_2026-07-11 작성. `.docs/UI_ROADMAP.md`, `.docs/IMPLEMENTATION_BRIEF.md`(§2.11, §2.12),
`.docs/BACKEND_REVIEW_PC.md`, `.docs/UI_PRODUCT_SPEC.md`를 기준으로 현재 코드와 대조._

## 요약

`UI_ROADMAP.md`의 구현 우선순위는 UI-0 → UI-0.2 → UI-0.3 → UI-1 → UI-2 → UI-3 → UI-4 이다.
현재까지 **UI-0**과 **UI-1**은 완성되었고, UI-3의 일부(최근 검색 영속화)만 앞당겨 구현되었다.
그 사이의 **UI-0.2, UI-0.3, UI-2**와 **UI-3 본체**는 미구현이다. 핵심 원인은
현재 `webapp.py`가 **읽기 전용**이라 색인/작업(job)을 실행할 **write 백엔드**가 없다는 점이다.

## 단계별 격차표

| 단계 | 목표 | 현재 상태 | 미구현 항목 |
|---|---|---|---|
| UI-0 | 디자인 인수 | ✅ 완료 | `DESIGN_AUDIT.md`, `STACK_DECISION.md` 존재 |
| UI-1 | 읽기 전용 검색 | ✅ 완료 | 검색/필터/칩/URL상태/IME가드/문단·중복 패널/내보내기/최근검색/경고배지 모두 동작 |
| UI-0.2 | 첫 실행 온보딩 | ❌ 미구현 | 루트 경로 입력, `POST /api/settings/root-path/validate`, 색인 저장 위치 표시, 최초 색인 시작 |
| UI-0.3 | 작업 진행률 UX | ❌ 미구현 | job 상태(idle/running/failed/completed), 진행률·현재 파일, `GET /api/jobs/{id}` 폴링, 취소/재시도, aria-live |
| UI-2 | 운영 대시보드 | ❌ 미구현 | 색인 상태 대시보드, 실패 파일 목록, batch별 통계, saved searches, result feedback, manual_overrides 후보 export |
| UI-3 | 리서치 UI | 🟡 부분 | (완료) 최근 검색 영속화 · (미구현) 기본 비교 목록, 북마크/메모, 리서치 세션, 선택 문단 export |

## 미구현의 근본 원인: write 백엔드 부재

- `webapp.py`는 `connect_search_db(read_only=True)`로 catalog를 열고, 파일 접근은 file_key 기준으로만 한다(읽기 전용).
- UI-0.2(최초 색인)와 UI-0.3(진행률)은 **색인 실행**이라는 write 작업을 전제로 한다.
- `BACKEND_REVIEW_PC.md §2.3`은 장시간 작업을 **job queue(표준 `queue.Queue` + worker 1개, one-writer)**로
  분리하고, job 상태를 SQLite `jobs` 테이블에 **영속화**하며, 앱 재시작 시 running job은
  `failed(중단됨)`로 정리하고, 파일 단위 **협조적 취소**를 요구한다.
- 따라서 UI 화면보다 **job/indexing write 계층을 먼저** 만들어야 한다. 검색 read 경로에
  영향을 주지 않도록 별도 계층(`lib/jobs.py` + `jobs.sqlite`)으로 추가한다.

## API 계약 (구현 대상)

`IMPLEMENTATION_BRIEF §2.12` / `BACKEND_REVIEW_PC §2.3`:

```text
POST /api/settings/root-path/validate   # 존재·읽기권한·예상 파일 수·확장자 수·네트워크 드라이브 여부
POST /api/jobs/index                     # 색인 job 생성 → {job_id}
GET  /api/jobs                           # 대시보드용 목록 (확장)
GET  /api/jobs/{job_id}                  # status/progress_done/progress_total/current_item/started_at/finished_at/error_code
POST /api/jobs/{job_id}/cancel           # 협조적 취소
```

`jobs` 테이블 필드(§2.3): `id, type, status, progress_done, progress_total, current_item,
started_at, finished_at, error_code`.

## UI-3용 사용자 상태 스키마 (§2.11)

`ui_state.sqlite`에 이미 `search_history`, `saved_searches`, `user_marks`, `result_feedback`가
예약 생성되어 있다. UI-3 본체 구현 시 §2.11의 `research_sessions`, `compare_lists`,
`compare_items`를 추가한다. **catalog.sqlite에는 사용자 상태를 절대 넣지 않는다**(재색인/`--full`로
재구축되는 산출물이므로). jobs는 사용자 상태가 아니라 운영 상태이므로 별도 `jobs.sqlite`에 둔다.

## 구현 순서 (본 세션 계획)

1. 본 문서(격차 정리) — 완료.
2. `lib/jobs.py` + `index_contracts.py` 진행률/취소 훅 — 백엔드 최소 동작 + 테스트.
3. `webapp.py` job/settings 엔드포인트 — WSGI 테스트.
4. UI-0.2 온보딩 + UI-0.3 진행률 화면(실제 엔드포인트 연결).
5. UI-2 운영 대시보드.
6. UI-3 리서치 UI.

각 단계 종료 시 `python -m pytest` 통과 확인 후 `progress.md`를 갱신한다.
