# NOW — 지금 무엇을 하는가 / 다음은 무엇인가

_최종 갱신: 2026-07-29. **다음 할 일의 단일 원천(single source of truth)은 이 파일이다.**
다른 문서(progress.md·V4_PLAN·PLAN_REVIEW·NEXT_STEPS)는 근거와 이력을 갖고, 여기는 상태와 포인터만 갖는다._

**현재 상태 한 줄**: 전량 확장(V4-6)은 [V4_PLAN §9](.docs/V4_PLAN.md) 결정으로 **중단**돼 있고,
블로킹 게이트는 **RW 부재 게이트 해제 체크리스트 5개 항목([V4_PLAN §9.1](.docs/V4_PLAN.md))** — 1~5 전부 미완이다.
지금 흐르고 있는 일은 **RW/PAY 재추출(정독)과 그 저장**, 그리고 **번다운 지표 상설화**다.

**실측 스냅샷(2026-07-29, `cs_index/catalog.sqlite` 읽기전용 조회)**: V4 item **124,396** /
coverage 기록 문서 **968**(item 보유 문서는 **960** — 차이 8건은 평가했으나 해당 family item이 0인 문서다. 감소가 아니다) /
taxonomy **v19·414 노드** / pending 후보 **29,807**(그중 부재 질의를 실제로 막는 것 **17,818** → 차단 문서 **835**) /
RW 재추출 반영 문서 **676**(대상 733) / PAY 재추출 반영 문서 **8**(타깃 392) /
대상유형 진행률 **793/1,623 = 48.9%**(SPA 99.6% · SSA 28.3% · ATA/BTA 5.7% · SHA 2.1%) /
부재 질의 (문서×family) **가능 1,594 · 차단 9,206**(RW은 게이트로 0).

_이 수치를 손으로 베끼지 말 것 — `python burndown.py --out cs_index` 또는 UI-2 대시보드 번다운 패널에서 매번 뽑는다._

---

## ⛳ 소유자 승인 대기 (DB 쓰기 — 조율자가 단일 writer로 실행)

다른 세션이 DB를 만지고 있지 않을 때 실행한다. 2026-07-29 세션 종료 시점에 다른 세션의
`v4_clause_item` dedup 흔적(`scratchpad/dedup_removed_*.jsonl`)이 있었다.

| # | 작업 | 명령 | 승인 |
|---|---|---|---|
| 1 | 버전 분류 백필(additive·백업·멱등) — 실행 전까지 버전 신뢰도가 "미백필"로 표시됨 | `python classify_version.py --out cs_index --dry-run` → `--apply` | 대기 |
| 2 | T-D backfill + 재분류 — **두 단계를 반드시 함께**(백필 단독은 22쌍 감소) | `backfill_v4_candidate_recurrence.py` → `reclassify_v4_candidate_backlog.py` (각각 dry-run 후 `--apply`) | dry-run 리포트 검토 후 |

---

## 지금 진행 중 (In flight)

| 작업 | 담당 | 상태 | 근거문서 |
|---|---|---|---|
| RW 재추출 정독 → result JSON → store | GPT/Codex 샤드 + 서브에이전트 정독, **store는 조율자 1명(단일 writer)** | 진행 중 — 675/733 문서 반영(DB 실측). 잔여 ~58 + full_read 마커 소급 대기 ~27항목 | [RW_REEXTRACTION_AGENT_BRIEF](.docs/RW_REEXTRACTION_AGENT_BRIEF.md), [progress.md 2026-07-29 세션](progress.md) |
| PAY 재추출(과소추출 시스템 결함 대응) | GPT/Codex(정독 배정), store는 조율자 | 착수 — 매니페스트 392 타깃(tier1 61/tier2 24/tier3 307) 중 **8문서 반영** | [PAY_REEXTRACTION_AGENT_BRIEF](.docs/PAY_REEXTRACTION_AGENT_BRIEF.md), `cs_index/pay_reextraction_manifest.json` |
| ~~번다운 지표 도구 + 웹 대시보드 패널~~ | — | **완료(2026-07-29)** — `burndown.py` + UI-2 대시보드 번다운 패널(`/api/ops/burndown`). 절대 drift하지 않도록 `v4_search`의 부재 판정 로직을 직접 import해 재사용 | [PLAN_REVIEW 권고 5](.docs/PLAN_REVIEW_20260727.md), `burndown.py` |
| 존재형(과대추출) 축 방지장치 | 미배정(1번은 구현 완료) | 부분 — 감사기 과다분절·중복 탐지 구현(advisory, `audit_t3_v4.py`). 나머지 2~5는 미착수 | [V4_PLAN §9.3](.docs/V4_PLAN.md) |

---

## 다음 (Next, 우선순위 순)

| # | 작업 | 담당 | 상태 | 왜 지금 | 근거문서 |
|---|---|---|---|---|---|
| 1 | **T-A 환경 선(先)해제** — `ABSENCE_UNVERIFIED_FAMILIES`를 하위영역 예외 목록으로 확장(sub-domain 게이팅) + 환경 풀(79) 재검증 | 미배정 | 미착수 (`v4_search.py`는 여전히 family 단위 플래그) | 환경은 이미 100% 수렴 — family 전체를 기다리지 않고 얻는 값싼 승리. **§9.1 #3의 필수 구현물**이고, 그간 progress에 한 줄로만 스쳐 실행에서 누락됨 | [V4_PLAN §9.2 T-A](.docs/V4_PLAN.md) |
| 2 | **RW 잔여 재추출 완결** — 잔여 ~58문서 + full_read 마커 소급 ~27항목 재저장 | GPT/Codex + 조율자 | 진행 중 | **§9.1 #1**(체크리스트 1번). 이게 끝나야 풀 재검증이 유효 | [V4_PLAN §9.1](.docs/V4_PLAN.md), [progress.md](progress.md) |
| 3 | **부재 풀 전량 재검증(소유자 라벨링)** — 재추출 후 `confirmed_absent` 풀 전량(조세 32·환경 79 + 신설 IP/보험/노무/소송) | **소유자** | 대기 | **§9.1 #2**. stale subset(조세 7·환경 8)으로 90%를 주장하면 안 됨 — 방법이 §9.1에 고정돼 있음 | [V4_PLAN §9.1](.docs/V4_PLAN.md) |
| 4 | **조세 잔여 false-absence 2건 정정** | 미배정 | 미착수 | **§9.1 #4**. 건수가 적어 즉시 처리 가능 | [V4_PLAN §9.1](.docs/V4_PLAN.md) |
| 5 | **T-B 측정** — IP·보험·노무·소송 부재쿼리(V4A09~A12) `pool_verified` 채우기 | 소유자(검증) + 조율자(pool 생성) | **작성 완료·측정 대기**(`data/golden_queries_v4_independent.seed.yaml`에 4개 존재) | 작성은 끝났고 재추출 착지 후에만 유효한 신호. **작성≠측정** — 지금 낮은 정밀도를 해제 신호로 읽지 말 것 | [V4_PLAN §9.2 T-B](.docs/V4_PLAN.md) |
| 6 | **존재형·비교형 정밀도 ≥90% 측정** — family별(RW·COV·PAY) 사람 원문대조 표본 + COV.NON_COMPETE 오분류 수정 재측정 | 미배정 (표본 검증은 소유자) | 미착수 | **§9.1 #5**(2026-07-29 추가된 블로킹 조건). 현재 유일한 표본이 E03 14건(50% 오분류) | [V4_PLAN §9.1 #5·§9.3](.docs/V4_PLAN.md) |
| 7 | **번다운 수치 정기 확인** — `python burndown.py --out cs_index` 또는 UI-2 대시보드 번다운 패널 | 각 세션 | 도구 완료, 운영 습관화 필요 | 상태 수치를 이 파일에 손으로 베껴두지 말고 매번 도구로 뽑아라. 문서마다 다른 수치(950/968/960)가 나오던 원인 | `burndown.py`, [PLAN_REVIEW 권고 5](.docs/PLAN_REVIEW_20260727.md) |
| 8 | **T-C 비-SPA 소표본 진단** — SHA·CB류 등 각 5~10건에서 동일 결함/수정 적용가능성 확인 | 미배정 | 미착수 | **V4-6 재개의 필수 진입 게이트**([V4_PLAN §10](.docs/V4_PLAN.md) 표에 명시). "SPA만 검증하고 확장 시작" 방지 | [V4_PLAN §9.2 T-C](.docs/V4_PLAN.md) |
| 9 | **T-D (2) 후보 생성기 조이기 + 기존 backlog 재분류** — 도구 완성(`lib/v4_candidate_policy.py`·`backfill_v4_candidate_recurrence.py`·`reclassify_v4_candidate_backlog.py`) | 조율자(DB 쓰기) | **도구·dry-run 완료. DB 쓰기 = 소유자 승인 대기**(2026-07-29 결정) | 질의시점 decouple만으로 부족함이 실측됨. 재분류 시 **부재 적격 쌍 +159**(비-RW 1,599→1,758)이고, **원칙 5 공백(pending 93.9%가 FTS 미검색)까지 함께 닫힌다** | [V4_PLAN §9.2 T-D](.docs/V4_PLAN.md), [PLAN_REVIEW 권고 3·항목 2 심화 + 2026-07-29 정정](.docs/PLAN_REVIEW_20260727.md) |
| 10 | **DEF 표적 재실행** — 매니페스트 206 타깃(items=0 100 + 1~3 106) | 미배정 | 미착수 | PAY와 달리 집중 tail 결함이라 **값싼 표적 재실행**으로 회수 가능. PAY 후행/병행 | [progress.md 2026-07-29 PAY/DEF 진단 세션](progress.md), `cs_index/def_reextraction_manifest.json` |
| 11 | **§9.3-2 후퇴가드 대칭화** — item 수 급증 시 store 전 표본확인 WARN | 미배정 | 미착수 (store 가드는 여전히 도메인 감소 차단만) | 과대추출 축의 방지장치. 하드 블록 아닌 WARN으로 시작 | [V4_PLAN §9.3](.docs/V4_PLAN.md) |
| 12 | **§9.3-3 경계 자기설명 필드**(REP vs COV 근거 기재 강제) | 미배정 | **대기(시점 고정)** — RW20·PAY tier1 정독 배치 종료 후 도입(소유자 결정) | 진행 중 배치 방해·부분 재작업 방지를 위해 시점이 결정돼 있음 | [V4_PLAN §9.3-3·§11](.docs/V4_PLAN.md) |
| 13 | **권고 6 — T4 로드맵 강등 문서화** | 미배정 | **미이행** — `docs_progress_v2.md`는 아직 "T4는 구현 확정"으로 기술 | 문서 간 모순(진행 계획은 보류, 설계문서는 확정) 해소 | [PLAN_REVIEW 권고 6](.docs/PLAN_REVIEW_20260727.md), [docs_progress_v2 T4](.docs/docs_progress_v2.md) |
| 14 | **권고 4 — 유형 균형 재조정**(SPA 98% vs SHA 1.9%) | 미배정 | 확장 재개 시점까지 보류 | 확장이 멈춰 있는 동안은 실행 대상 아님. 재개 시 계획 순서를 실제로 지킬 것 | [PLAN_REVIEW 권고 4](.docs/PLAN_REVIEW_20260727.md) |
| 15 | **업종(제조업 등) 메타 분류** — 버전별 검색 예시 질의에 필요하나 코퍼스에 메타 없음 | 미배정 | 큐잉(별도 과제) | 버전 필터는 구현 완료됐고, 남은 공백이 업종 축 | [progress.md 2026-07-29 버전 분류 세션](progress.md) |

**이미 끝난 것(중복 착수 방지)**: 권고 1 확장 일시 정지(§9 결정으로 이행), 권고 2 pooled 독립 Gate B **도구 구현 완료**
(`eval_v4_gate.py --pooled`) + 부재형 재측정(RW 부재정밀도 47.2%→86.7%), T-B 부재쿼리 **작성** 완료,
T-D (1) 부재 적격성 decouple 구현, §9.3-1 감사기 과다분절·중복 탐지(advisory), 버전 분류·`--version` 필터 CLI/웹/MCP 전파.

---

## 차단 / 보류 (Blocked / Deferred)

| 항목 | 상태 | 해제 조건 | 근거문서 |
|---|---|---|---|
| **V4-6 전량 확장** | 중단 | RW 게이트 해제(§9.1 1~5) → Gate B 재측정에서 V4 우위 확인 → **T-C 비-SPA 소표본 통과** | [V4_PLAN §9·§10](.docs/V4_PLAN.md) |
| **RW confirmed_absent(부재 질의)** | 게이트 중 — needs_review로 강등 | §9.1 5개 항목 충족, 또는 T-A 구현 후 **환경 하위영역만** 선해제 | [V4_PLAN §9.1·§9.2](.docs/V4_PLAN.md) |
| **T4(벡터 하이브리드)** | 보류 | V4 안정화 + 게이트 B 종료 후 재평가(권고 6대로 "구현 확정" → "재평가 대기"로 강등 문서화 선행) | [V4_PLAN §10.1](.docs/V4_PLAN.md), [PLAN_REVIEW 권고 6](.docs/PLAN_REVIEW_20260727.md) |
| **RW 비표적 잔여(약 601문서) 전수 정독** | 유예(중단 아님) | 표적 정독 수렴 확인 후 프로젝트 후반에 완주 | [progress.md 2026-07-28~29 세션](progress.md) |
| **버전 중복분(tier2 330문서) 정독** | 유예 | 체결본 우선 tier1(403) 완주 후 — 최종적으로는 전 버전 정독이 목표 | [progress.md 2026-07-29 버전 분류 세션](progress.md) |
| **taxonomy 후보 29,807건 사람 처리** | 사실상 불가 → 우회 확정 | 처리로 풀지 않고 생성기 교정(Next #9)으로 해소. 부재 질의 차단은 decouple로 이미 완화 | [V4_PLAN §9.2 T-D](.docs/V4_PLAN.md), [PLAN_REVIEW 항목 2 심화](.docs/PLAN_REVIEW_20260727.md) |

---

## 갱신 규칙

이 파일은 **다음 할 일이 사는 유일한 장소**다. progress.md는 이력·현재 상태를, V4_PLAN·PLAN_REVIEW는 근거와 설계를,
[.docs/NEXT_STEPS_ARCHIVE_20260724.md](.docs/NEXT_STEPS_ARCHIVE_20260724.md)는 과거 실행안을 보관한다
(2026-07-29에 루트 `NEXT_STEPS.md`에서 옮김 — 이름이 계속 권위 있는 문서로 오독됐다).
그 문서들에 앞으로 할 일 목록을 새로 만들지 말고 여기를 링크하라.
모든 세션은 **끝내기 전에 이 파일을 갱신**한다(진행 중/다음/차단 표의 상태·담당·완료 항목 이동, 상단 갱신일 수정).
각 행은 반드시 권위 있는 상세 문서로의 링크를 갖고, 이유·경위는 그 문서에 쓴다 — 여기는 포인터와 상태만 유지해 짧게 둔다.
담당이 정해지지 않았으면 추측하지 말고 `미배정`이라고 적는다.
