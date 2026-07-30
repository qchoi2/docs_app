# NOW — 지금 무엇을 하는가 / 다음은 무엇인가

_최종 갱신: 2026-07-30. **다음 할 일의 단일 원천(single source of truth)은 이 파일이다.**
다른 문서(progress.md·V4_PLAN·PLAN_REVIEW·NEXT_STEPS)는 근거와 이력을 갖고, 여기는 상태와 포인터만 갖는다._

**현재 상태 한 줄**: 전량 확장(V4-6)은 [V4_PLAN §9](.docs/V4_PLAN.md) 결정으로 **중단**돼 있고,
블로킹 게이트는 **RW 부재 게이트 해제 체크리스트 5개 항목([V4_PLAN §9.1](.docs/V4_PLAN.md))** —
**#3 환경 선해제 완료·개방(2026-07-30, 89건 전량 정독검증 correct 89/incorrect 0)**, **#4 조세 완료**,
**#1 RW 정독 거의 완료**(잔여 ~99건은 소유자 지시로 후순위), **#2·#5 남음**(#2 IP/보험/노무/소송 재추출 후, #5 존재·비교형 정밀도 미측정).
지금 흐르고 있는 일은 **진행 중 RW 정독 마무리 대기**이고, 나머지 RW 정독은 후순위다.

**실측 스냅샷(2026-07-29, `cs_index/catalog.sqlite` 읽기전용 조회)**: V4 item **124,396** /
coverage 기록 문서 **968**(item 보유 문서는 **960** — 차이 8건은 평가했으나 해당 family item이 0인 문서다. 감소가 아니다) /
taxonomy **v19·414 노드** / pending 후보 **29,807**(그중 부재 질의를 실제로 막는 것 **17,818** → 차단 문서 **835**) /
RW 재추출 반영 문서 **676**(대상 733) / PAY 재추출 반영 문서 **8**(타깃 392) /
대상유형 진행률 **793/1,623 = 48.9%**(SPA 99.6% · SSA 28.3% · ATA/BTA 5.7% · SHA 2.1%) /
부재 질의 (문서×family) **가능 1,594 · 차단 9,206**(RW은 게이트로 0).

_이 수치를 손으로 베끼지 말 것 — `python burndown.py --out cs_index` 또는 UI-2 대시보드 번다운 패널에서 매번 뽑는다._

---

## ⛳ 소유자 승인 대기 (DB 쓰기 — 조율자가 단일 writer로 실행)

다른 세션이 DB를 만지고 있지 않을 때 실행한다.

**소유자 일괄 승인(2026-07-29): 아래 대기 항목 및 §11의 미결정 사항은 전부 권고안대로 채택.**

| # | 작업 | 명령 | 승인 |
|---|---|---|---|
| 1 | 버전 분류 백필(additive·백업·멱등) | `python classify_version.py --out cs_index --apply` | ✅ **적용됨(2026-07-29)** — 2,106행 version_role + version_basis/confidence 컬럼 신설, 백업·integrity ok |
| 2 | T-D backfill + 재분류 | `backfill_v4_candidate_recurrence.py` → `reclassify_v4_candidate_backlog.py` | ✅ **적용 완료(2026-07-29)** — backfill(recurrence_key 31,394행·document_count 13,473행 교정) + reclassify(one-off 16,585 흡수). pending **29,807→13,222**, merged 1,540→18,125, 사람결정(31/16) 불변, quick_check ok. 리포트 `.docs/v4_backlog_reclassify_applied.json` |
| 3 | `.doc` 확장자 RTF 5건 변환 + 손상 `.docx` 1건 복구 | `detect_doc_kind()` 보정 후 `convert_doc.py` 재실행 | **승인됨** — 보고서 전체에서 가장 값싼 recall 회수(5건 전부 ATA/BTA 국문, 해당 유형 커버리지 5.6%) |
| 4 | 스캔 PDF OCR 48건(1,931쪽) + provenance 스키마 | 미구현 — 파이프라인 구축 필요(`Windows.Media.Ocr`+`ko`, 새 의존성 0·₩0·약 1시간) | **승인됨**, 단 **OCR 텍스트는 `confirmed_absent` 불가(항상 needs_review)·V4 추출 제외(FTS 전용)·`source_sha256`로 dedup 키 이전** |
| 5 | 미수집 별지 502건(148문서) 원본 수집 | DB 작업 아님 — **소유자 원본 수집** | 이관됨 — 읽기 실패가 아니라 **애초에 안 받은 것**이라 OCR로 복구 불가 |

_2026-07-29 추가 반영(조율자 단일 writer): (a) `v4_clause_item` **exact-dup 7,244건 병합**(삭제 전 export 백업, quick_check ok), (b) **재추출 store에 과/미추출 게이트**(`lib/extraction_gate.py`, RW·PAY 배선; shingle-coverage grounding), (c) **PAY 재추출 121문서 반영**(과소추출 결함 대응, 0 오류). RW 부재/존재 게이트 상태는 재측정 필요._

---

## 지금 진행 중 (In flight)

| 작업 | 담당 | 상태 | 근거문서 |
|---|---|---|---|
| RW 재추출 정독 → result JSON → store | GPT/Codex 샤드 + 서브에이전트 정독, **store는 조율자 1명(단일 writer)** | 진행 중 — 675/733 문서 반영(DB 실측). 잔여 ~58 + full_read 마커 소급 대기 ~27항목 | [RW_REEXTRACTION_AGENT_BRIEF](.docs/RW_REEXTRACTION_AGENT_BRIEF.md), [progress.md 2026-07-29 세션](progress.md) |
| PAY 재추출(과소추출 시스템 결함 대응) | GPT/Codex(정독 배정), store는 조율자 | 착수 — 매니페스트 392 타깃(tier1 61/tier2 24/tier3 307) 중 **8문서 반영** | [PAY_REEXTRACTION_AGENT_BRIEF](.docs/PAY_REEXTRACTION_AGENT_BRIEF.md), `cs_index/pay_reextraction_manifest.json` |
| ~~번다운 지표 도구 + 웹 대시보드 패널~~ | — | **완료(2026-07-29)** — `burndown.py` + UI-2 대시보드 번다운 패널(`/api/ops/burndown`). 절대 drift하지 않도록 `v4_search`의 부재 판정 로직을 직접 import해 재사용 | [PLAN_REVIEW 권고 5](.docs/PLAN_REVIEW_20260727.md), `burndown.py` |
| 존재형(과대추출) 축 방지장치 | 미배정(1번은 구현 완료) | 부분 — 감사기 과다분절·중복 탐지 구현(advisory, `audit_t3_v4.py`). 나머지 2~5는 미착수 | [V4_PLAN §9.3](.docs/V4_PLAN.md) |
| ~~`full_read` 누락 소급감사 + 저장시 강등~~ | — | **완료(2026-07-30)** — 390건 backfill, 명확한 목차/조항표지↔sub-domain 불일치 39건 확인. 기존 `complete` 위험 36건을 `partial`로 강등했고 재감사 `complete_rows_at_risk=0`. `partial`은 기존 item은 유지하되 부재형에서는 `needs_review`로 제외하며, 환경 소유자 판정 89건 풀과 별개다. 이후 full-read 저장도 동일 검사 후 누락 시 자동 partial | [full-read 감사 결과](.docs/full_read_omission_backfill_20260730_postapply.json), `audit_full_read_omissions.py`, `lib/full_read_guard.py` |

---

## 다음 (Next, 우선순위 순)

| # | 작업 | 담당 | 상태 | 왜 지금 | 근거문서 |
|---|---|---|---|---|---|
| 1 | ~~**T-A 환경 선(先)해제**~~ | 조율자(AI 정독 대행) | **완료·개방됨(2026-07-30)** — 89건 전량 AI 정독 검증(전문 환경어휘 스캔→강한rep어휘 6건만 정독; correct **89** / incorrect **0**, 정밀도 100%). `ABSENCE_VERIFIED_SUBDOMAINS={"RW.ENVIRONMENT"}` 플립, seed V4A07 `pool_verified` 기록(version 1). env 부재 질의가 **confirmed_absent 89건** 활성(needs_review 1,424·present 576 분리). 폐기물처리업 인허가 진술 1건은 소유자 지시로 PERMITS 분류 | [환경 워크시트](cs_index/environment_absence_full_pool_20260730.md), `data/v4_gate_b_verdicts.json`, [V4_PLAN §9.2 T-A](.docs/V4_PLAN.md) |
| 2 | **RW 잔여 재추출 완결** — 잔여 ~58문서 + full_read 마커 소급 ~27항목 재저장 | GPT/Codex + 조율자 | 진행 중 | **§9.1 #1**(체크리스트 1번). 이게 끝나야 풀 재검증이 유효 | [V4_PLAN §9.1](.docs/V4_PLAN.md), [progress.md](progress.md) |
| 3 | **부재 풀 전량 재검증** — 현재 `confirmed_absent` 풀 전량(조세·환경 + 신설 IP/보험/노무/소송) | 조율자(AI 정독) / 소유자 | **환경 89건 완료(2026-07-30, correct 89/0)**. IP·보험·노무·소송은 **재추출 후**(그 재추출이 후순위라 함께 대기) | **§9.1 #2**. stale subset으로 90%를 주장하지 않고 현재 검색 적격 풀을 매번 재산출 | [환경 워크시트](cs_index/environment_absence_full_pool_20260730.md), [V4_PLAN §9.1](.docs/V4_PLAN.md) |
| 4 | ~~**조세 잔여 false-absence 2건 정정**~~ | — | **완료(2026-07-30)** — `[1d5383…]` Tax Matters ¶411–415 추출 누락 6항목 표적 추가, `[1f0dc2…]` 결과 JSON의 조세 ¶55 DB 미착지 재저장. integrity ok | **§9.1 #4** 완료. 현재 조세 풀의 별도 소유자 전량 라벨링은 #3에 남음 | [V4_PLAN §9.1](.docs/V4_PLAN.md), `cs_index/rw_tax_false_absence_fixes/` |
| 5 | **T-B 측정** — IP·보험·노무·소송 부재쿼리(V4A09~A12) `pool_verified` 채우기 | 소유자(검증) + 조율자(pool 생성) | **작성 완료·측정 대기**(`data/golden_queries_v4_independent.seed.yaml`에 4개 존재) | 작성은 끝났고 재추출 착지 후에만 유효한 신호. **작성≠측정** — 지금 낮은 정밀도를 해제 신호로 읽지 말 것 | [V4_PLAN §9.2 T-B](.docs/V4_PLAN.md) |
| 6 | **존재형·비교형 정밀도 ≥90% 측정** — family별(RW·COV·PAY) 사람 원문대조 표본 + COV.NON_COMPETE 오분류 수정 재측정 | 미배정 (표본 검증은 소유자) | 미착수 | **§9.1 #5**(2026-07-29 추가된 블로킹 조건). 현재 유일한 표본이 E03 14건(50% 오분류) | [V4_PLAN §9.1 #5·§9.3](.docs/V4_PLAN.md) |
| 7 | **번다운 수치 정기 확인** — `python burndown.py --out cs_index` 또는 UI-2 대시보드 번다운 패널 | 각 세션 | 도구 완료, 운영 습관화 필요 | 상태 수치를 이 파일에 손으로 베껴두지 말고 매번 도구로 뽑아라. 문서마다 다른 수치(950/968/960)가 나오던 원인 | `burndown.py`, [PLAN_REVIEW 권고 5](.docs/PLAN_REVIEW_20260727.md) |
| 8 | **T-C 비-SPA 소표본 진단** — SHA·CB류 등 각 5~10건에서 동일 결함/수정 적용가능성 확인 | 미배정 | 미착수 | **V4-6 재개의 필수 진입 게이트**([V4_PLAN §10](.docs/V4_PLAN.md) 표에 명시). "SPA만 검증하고 확장 시작" 방지 | [V4_PLAN §9.2 T-C](.docs/V4_PLAN.md) |
| 9 | **T-D (2) 후보 생성기 조이기 + 기존 backlog 재분류** — 도구 완성(`lib/v4_candidate_policy.py`·`backfill_v4_candidate_recurrence.py`·`reclassify_v4_candidate_backlog.py`) | 조율자(DB 쓰기) | **도구·dry-run 완료. DB 쓰기 = 소유자 승인 대기**(2026-07-29 결정) | 질의시점 decouple만으로 부족함이 실측됨. 재분류 시 **부재 적격 쌍 +159**(비-RW 1,599→1,758)이고, **원칙 5 공백(pending 93.9%가 FTS 미검색)까지 함께 닫힌다** | [V4_PLAN §9.2 T-D](.docs/V4_PLAN.md), [PLAN_REVIEW 권고 3·항목 2 심화 + 2026-07-29 정정](.docs/PLAN_REVIEW_20260727.md) |
| 10 | **DEF 표적 재실행** — 매니페스트 206 타깃(items=0 100 + 1~3 106) | 미배정 | 미착수 | PAY와 달리 집중 tail 결함이라 **값싼 표적 재실행**으로 회수 가능. PAY 후행/병행 | [progress.md 2026-07-29 PAY/DEF 진단 세션](progress.md), `cs_index/def_reextraction_manifest.json` |
| 11 | ~~**§9.3-2 후퇴가드 대칭화** — item 수 급증 시 store 전 표본확인 WARN~~ | — | **완료(2026-07-30)** — item-surge WARN + 과대추출 게이트 및 회귀 테스트 반영 | 과대추출 축의 방지장치 | [V4_PLAN §9.3](.docs/V4_PLAN.md), `lib/extraction_gate.py` |
| 12 | **§9.3-3 경계 자기설명 필드**(REP vs COV 근거 기재 강제) | 미배정 | **대기(시점 고정)** — RW20·PAY tier1 정독 배치 종료 후 도입(소유자 결정) | 진행 중 배치 방해·부분 재작업 방지를 위해 시점이 결정돼 있음 | [V4_PLAN §9.3-3·§11](.docs/V4_PLAN.md) |
| 13 | **권고 6 — T4 로드맵 강등 문서화** | 미배정 | **미이행** — `docs_progress_v2.md`는 아직 "T4는 구현 확정"으로 기술 | 문서 간 모순(진행 계획은 보류, 설계문서는 확정) 해소 | [PLAN_REVIEW 권고 6](.docs/PLAN_REVIEW_20260727.md), [docs_progress_v2 T4](.docs/docs_progress_v2.md) |
| 14 | **권고 4 — 유형 균형 재조정**(SPA 98% vs SHA 1.9%) | 미배정 | 확장 재개 시점까지 보류 | 확장이 멈춰 있는 동안은 실행 대상 아님. 재개 시 계획 순서를 실제로 지킬 것 | [PLAN_REVIEW 권고 4](.docs/PLAN_REVIEW_20260727.md) |
| 15 | **업종(제조업 등) 메타 분류** → **#19에 흡수** | — | #19로 통합(2026-07-29) | 버전 필터는 구현 완료됐고 남은 공백이 업종 축. 연도·규모·준거법과 같은 계열이라 함께 다룬다 | [progress.md 2026-07-29 버전 분류 세션](progress.md) |
| 16 | **비교형 셀 정확도 검증** — V4C01~06 비교표의 모든 셀을 원문 대조해 correct/wrong_value/wrong_clause/false_empty/incomparable 라벨링 | 미배정 (라벨링은 소유자) | 미착수 — **검증 계획 자체가 없던 공백** | §0에서 비교·집계를 **"필수"**로 분류해놓고 한 번도 정확도를 잰 적이 없다. 부재형=전수·존재형=§9.3 표본인데 비교형만 무측정. **빈 셀이 자동 정답이 아니라는 점**이 핵심 | [V4_PLAN §9.4](.docs/V4_PLAN.md) |
| 17 | **절대 recall 측정** — `eval_absolute_recall.py` | 조율자 | **1차 실측 완료**(structured 경로). 하이브리드 합집합 미측정 | 풀링은 **상대** 재현율만 준다 — 둘 다 못 찾은 문서는 영원히 안 보임. 정독 부산물로 정답지가 **이미 공짜로 쌓여 있다**. 이 프로젝트 최초의 절대 recall 수치 | [V4_PLAN §9.5](.docs/V4_PLAN.md) |
| 18a | **`.doc` 확장자 RTF 5건 변환** — `detect_doc_kind()`가 RTF를 거부해 실패. Word는 RTF를 정상 처리 | 미배정 | 실측 완료·미착수 | **보고서 전체에서 가장 값싼 recall 회수.** 5건 전부 ATA/BTA 국문인데 그 유형 V4 커버리지가 5.6%다 | [CORPUS_BLIND_SPOTS](.docs/CORPUS_BLIND_SPOTS_20260729.md) |
| 18b | **스캔 PDF OCR** — 48건/1,931쪽. Windows.Media.Ocr(`ko` 설치됨) + Windows.Data.Pdf, **새 의존성 0·비용 ₩0·약 1시간** | **소유자 결정 필요**(스키마 변경 + OCR 텍스트 정책) | 실측 완료·승인 대기 | **recall의 하드 상한** — 추출 품질을 아무리 올려도 이 48건의 recall은 영원히 0. SHA 10건이 급소(SHA V4 커버리지 2.1%인데 2025년 체결본 포함) | [CORPUS_BLIND_SPOTS](.docs/CORPUS_BLIND_SPOTS_20260729.md) |
| 18c | **미수집 별지 502건(148문서) 수집** — 읽기 실패가 아니라 **애초에 안 받은 것** | 소유자(원본 수집) | 실측 완료 | OCR로 **하나도 복구 안 된다**. `annex_partial`이 부재 차단 2위 사유(3,863)인데 그 뿌리의 일부가 여기다 — 추출 문제가 아니라 소싱 문제 | [CORPUS_BLIND_SPOTS](.docs/CORPUS_BLIND_SPOTS_20260729.md), `색인 업데이트 설명서.md` §3.2 |
| 19 | **거래 메타데이터 확장** — **준거법(70.1%)·관할법원(51.3%)·중재합의(95.7%)·거래연도(체결일 420건)** 채택. **규모 구간·업종은 반대** | 미배정 | 실측·도구·테스트 완료(`derive_deal_meta.py`, 53 tests). DB 적용 대기 | 조항 추출 품질로는 **영원히 답할 수 없는 질의 계급**을 연다. 단 제안의 "v3 대금으로 규모 구간 파생 가능"은 **사실이 아님** — doc_meta 1,999행 중 v3 스키마 60행, 밴딩 안전한 건 **8건** | [DEAL_METADATA](.docs/DEAL_METADATA_FEASIBILITY_20260729.md) |
| 20 | **DEF 구조화 검색** — 용어명 정규화를 기존 item에 **소급 적용** | 미배정 | **결정됨(2026-07-29): 완료 범위 포함** | DEF item의 **78%(16,077/20,600)가 캐치올에 흡수**돼 정의조항 검색은 사실상 FTS 전용. T-D는 이걸 못 푼다. 도구 기반은 이미 있음(`lib/v4_candidate_policy`) | [V4_PLAN §11](.docs/V4_PLAN.md) |
| 21 | **T4 = V4-7 예약 실험** — 골든셋 ablation으로 채택/폐기 | 미배정 | **결정됨(2026-07-29): V4-7 편입**(§10 표 반영 완료) | 강등 근거는 비용·복잡도였는데 **목표가 품질 최우선으로 바뀌면 계산이 달라진다**. 잔여 gap이 표현 변이이고 V4 원자 명제는 임베딩 단위로 이상적. "날짜 없는 언젠가"를 순서 있는 항목으로 | [V4_PLAN §10.1](.docs/V4_PLAN.md) |
| 22 | **랭킹 품질** — 나머지는 T4로 이관 | 미배정→T4(V4-7) | **진단 확정·부분 착수(2026-07-30)** | 462위·1.5%는 **랭킹 결함이 아니라 질의 신호 부재**로 판명(`ORDER BY file_key`, 개념 질의가 노드 전체 2.9k~18k를 무순위 열거). `eval_ranking_signal.py`로 확증: 변별 문구 주면 recall@10 90.5%·중앙 1위. text 경로 관련도 정렬 착수 → 변별 recall@1 0.536→0.623(+8.6pp), 484 pass. **잔여(개념 질의 의미 랭킹)는 T4 임베딩 영역** | [V4_PLAN §9.6](.docs/V4_PLAN.md) |

**이미 끝난 것(중복 착수 방지)**: 권고 1 확장 일시 정지(§9 결정으로 이행), 권고 2 pooled 독립 Gate B **도구 구현 완료**
(`eval_v4_gate.py --pooled`) + 부재형 재측정(RW 부재정밀도 47.2%→86.7%), T-B 부재쿼리 **작성** 완료,
T-D (1) 부재 적격성 decouple 구현, §9.3-1 감사기 과다분절·중복 탐지(advisory), 버전 분류·`--version` 필터 CLI/웹/MCP 전파.

---

## 차단 / 보류 (Blocked / Deferred)

| 항목 | 상태 | 해제 조건 | 근거문서 |
|---|---|---|---|
| **V4-6 전량 확장** | 중단 | RW 게이트 해제(§9.1 1~5) → Gate B 재측정에서 V4 우위 확인 → **T-C 비-SPA 소표본 통과** | [V4_PLAN §9·§10](.docs/V4_PLAN.md) |
| **RW confirmed_absent(부재 질의)** | **환경 하위영역 선해제 완료(2026-07-30)** — 그 외 RW 하위영역은 게이트 중(needs_review) | 나머지 하위영역: §9.1 1~5 충족 또는 하위영역별 재추출+풀검증(환경과 동일 절차) | [V4_PLAN §9.1·§9.2](.docs/V4_PLAN.md) |
| **T4(벡터 하이브리드)** | 보류 | V4 안정화 + 게이트 B 종료 후 재평가(권고 6대로 "구현 확정" → "재평가 대기"로 강등 문서화 선행) | [V4_PLAN §10.1](.docs/V4_PLAN.md), [PLAN_REVIEW 권고 6](.docs/PLAN_REVIEW_20260727.md) |
| **RW 비표적 잔여(약 601문서) 전수 정독** | 유예(중단 아님) | 표적 정독 수렴 확인 후 프로젝트 후반에 완주 | [progress.md 2026-07-28~29 세션](progress.md) |
| **버전 중복분(tier2 330문서) 정독** | 유예 | 체결본 우선 tier1(403) 완주 후 — 최종적으로는 전 버전 정독이 목표 | [progress.md 2026-07-29 버전 분류 세션](progress.md) |
| **taxonomy 후보 29,807건 사람 처리** | 사실상 불가 → 우회 확정 | 처리로 풀지 않고 생성기 교정(Next #9)으로 해소. 부재 질의 차단은 decouple로 이미 완화 | [V4_PLAN §9.2 T-D](.docs/V4_PLAN.md), [PLAN_REVIEW 항목 2 심화](.docs/PLAN_REVIEW_20260727.md) |
| **`RUNBOOK.md` — 새 문서 n건 추가 시 운영 런북** | **프로젝트 완료 조건**(마지막에 수행) | 파이프라인이 확정된 뒤 작성. 명령 순서 + 품질 게이트 + 예상 공수 + 부분적용 표시 규칙 4가지를 담아야 한다. **"마지막에 한다"와 "잊는다"는 다르므로 여기 상설 표기한다** — 없으면 완성 시점 코퍼스로 화석화되거나 신규분만 품질 낮은 이중 코퍼스가 된다. `색인 업데이트 설명서.md`가 있으나 (a)전달용 프레이밍이고 (b)07-28~29 변경분이 빠져 낡았다 | [V4_PLAN §10.2](.docs/V4_PLAN.md) |

---

## 갱신 규칙

이 파일은 **다음 할 일이 사는 유일한 장소**다. progress.md는 이력·현재 상태를, V4_PLAN·PLAN_REVIEW는 근거와 설계를,
[.docs/NEXT_STEPS_ARCHIVE_20260724.md](.docs/NEXT_STEPS_ARCHIVE_20260724.md)는 과거 실행안을 보관한다
(2026-07-29에 루트 `NEXT_STEPS.md`에서 옮김 — 이름이 계속 권위 있는 문서로 오독됐다).
그 문서들에 앞으로 할 일 목록을 새로 만들지 말고 여기를 링크하라.
모든 세션은 **끝내기 전에 이 파일을 갱신**한다(진행 중/다음/차단 표의 상태·담당·완료 항목 이동, 상단 갱신일 수정).
각 행은 반드시 권위 있는 상세 문서로의 링크를 갖고, 이유·경위는 그 문서에 쓴다 — 여기는 포인터와 상태만 유지해 짧게 둔다.
담당이 정해지지 않았으면 추측하지 말고 `미배정`이라고 적는다.
