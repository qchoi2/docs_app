# NOW — 지금 무엇을 하는가 / 다음은 무엇인가

_최종 갱신: 2026-07-30. **다음 할 일의 단일 원천(single source of truth)은 이 파일이다.**
다른 문서(progress.md·V4_PLAN·PLAN_REVIEW·NEXT_STEPS)는 근거와 이력을 갖고, 여기는 상태와 포인터만 갖는다._

**현재 상태 한 줄**: 전량 확장(V4-6)은 [V4_PLAN §9](.docs/V4_PLAN.md) 결정으로 **중단**돼 있고,
블로킹 게이트는 **RW 부재 게이트 해제 체크리스트 5개 항목([V4_PLAN §9.1](.docs/V4_PLAN.md))** —
**#3 환경 선해제 완료·개방(2026-07-30, 89건 전량 정독검증 correct 89/incorrect 0)**, **#4 조세 완료**,
**#1 RW 정독 거의 완료**(잔여는 소유자 지시로 후순위), **#2·#5 남음**(#2 IP/보험/노무/소송 재추출 후, #5 존재·비교형 정밀도 미측정).

**2026-07-30 추가 정독 40건 완료** ([RW_REEXTRACT_NEXT40](.docs/RW_REEXTRACT_NEXT40_20260730.md)) —
39건 저장·오류 0·integrity ok. 이 배치에서 **자동추출 결함의 단일 뿌리**가 특정됐다: 추출기가 진술 조항 범위를
경계하지 않아 (a) 별지 편입형 과소추출, (b) 범위 밖 긁어오기 → **false-present**, (c) 무내용 템플릿 proposition
**17,255건(29.6%, 390문서)** 이 동시에 발생한다. 소유자 결정 대기 3건:
**⛳6 환경 false-present 15건 정정** · **⛳7 부재 저장 경로 설계** · **다음 배치 표적 = RW.BUYER 과다추출 16건**.

**실측 스냅샷(2026-07-29, `cs_index/catalog.sqlite` 읽기전용 조회)**: V4 item **124,396** /
coverage 기록 문서 **968**(item 보유 문서는 **960** — 차이 8건은 평가했으나 해당 family item이 0인 문서다. 감소가 아니다) /
taxonomy **v19·414 노드** / pending 후보 **29,807**(그중 부재 질의를 실제로 막는 것 **17,818** → 차단 문서 **835**) /
RW 재추출 반영 문서 **676**(대상 733) / PAY 재추출 반영 문서 **8**(타깃 392) /
대상유형 진행률 **793/1,623 = 48.9%**(SPA 99.6% · SSA 28.3% · ATA/BTA 5.7% · SHA 2.1%) /
부재 질의 (문서×family) **가능 1,594 · 차단 9,206**(RW은 게이트로 0).

_이 수치를 손으로 베끼지 말 것 — `python burndown.py --out cs_index` 또는 UI-2 대시보드 번다운 패널에서 매번 뽑는다._

---

## 🧭 추출 로드맵 (2026-07-30 합의안, Fable 검증 반영) — 이 순서가 아래 Next 표를 지배한다

**목표**: 모든 유형 × 모든 질의형(존재·부재·비교). 병목은 검색 엔진이 아니라 추출·데이터 축.
두 전선 병행 — (A) 이미 가진 코퍼스의 개념 공백 정리, (B) 유형 커버리지 확장 준비.
단일 writer 규율 유지(정독 병렬·store만 직렬). **운영 원칙**: "키워드 미검출≠부재"의 쌍둥이
**"키워드 검출≠존재"** — 센서스·스윕 전 과정에 적용(2026-07-30 실증: RWI 790·TERMINATION_FEE 92 정확구문 히트가 정독 결과 거의 허수).

> **소유권·정책 변경(2026-07-31 소유자 결정)**: **추출 파이프라인을 조율자(Claude Code)가 직접 소유**한다 —
> 정독·추출·result JSON 작성·store·게이트를 조율자와 그 **서브에이전트**가 직접 수행하고, 외부 GPT/Codex 샤드에
> 위임하지 않는다. **유료 API는 전면 미사용**(enrich 자동추출기·`answer_quick.py` 등 API 경로 도구 보류) —
> 추출은 구독형 에이전트의 **직접 정독**으로만 한다. 이로써 RW/PAY 완결·T-C·스윕·부재검증이 모두 조율자
> 실행 가능해진다(이전의 "샤드 배정 대기" 병목 해소). 단일 writer(store=조율자 1명)·과대추출 게이트는 그대로.
> **모델 티어링(2026-07-31)**: **정독 작업은 Sonnet 5 서브에이전트**가 수행한다(`Agent model:sonnet`).
> 조율자(Opus)는 오케스트레이션·store·게이트·측정만 맡고 대량 정독을 직접 하지 않는다.

> **문서 클래스 구분(2026-07-31 소유자 지적)**: 현재 taxonomy 6-family(RW·CP·PAY·REM·COV·DEF)는 **매매/인수계약
> 해부구조**다. **SHA는 독립 도메인이 아니라 `COV.SHA` 하위로 욱여넣어져 있고**(26노드·1,784 item), SHA엔
> CP/PAY/REM이 SPA와 같은 의미로 거의 없다. 따라서: **(A) 매매/인수(SPA·ATA/BTA)** = taxonomy 적합, 병목은 추출
> → CP·COV·REM 재검증(Phase 0-④)은 **이 클래스 한정**. **(B) 주주간(SHA)** = COV.SHA 미스핏 → **T-C의 SHA 정독은
> 결함측정이 아니라 "도메인 적합성 평가"**(SHA를 1급 도메인으로 승격할지 taxonomy 권고 산출; 재설계는 소유자 결정).
> **(C) 투자(SSA·CB/BW/EB)** = 하이브리드 추정, T-C에서 어느 클래스에 가까운지 확인.

> **taxonomy v20 적용(2026-07-31, 소유자 승인)**: family CHECK 제약이 신규 최상위 family를 막아, 기존 family 하위에
> **additive +25 노드**(item 불변·integrity ok). 신설: `PAY.ISSUANCE.*`(신주·전환사채·BW·우선주 발행조건·전환·상환·리픽싱,
> SSA/CBSA/BWSA용) · `COV.SECURITY.*`(질권·저당·보증·유지·실행·해지) · `COV.SHA.{청산우선권·상환권·전환권}`(ROFR/ROFO/CALL/
> PUT/TAG/DRAG는 기존) · `COV.FINANCIAL_MAINTENANCE`·`COV.IP_TRANSFER`·`COV.CORPORATE_ACTION`·`REM.{통지·부본·준거언어}`.
> 최상위 `ISS`/`SEC` 승격은 향후 124k-item controlled migration 옵션. 상세 [TAXONOMY_EXTENSION_RECOMMENDATION](.docs/TAXONOMY_EXTENSION_RECOMMENDATION.md).
> **재추출 store 확정(소유자)**: full-replace·정독 RW 신뢰. 단 `replace_v4_result`는 `coverage`+`source_coverage` 필수 →
> 브리프 스키마 보강함(정독 6건은 store 전 coverage 백필 필요, 캠페인에서 처리).

> **재추출 캠페인 = 발견 패스 (Fable 2차 검토 2026-07-31, 조건 3개 반영)**: 재추출은 재분류만이 아니라
> **신규 조항유형 발견**을 겸해야 한다 — 안 그러면 소수 계약의 마이너 유형이 캐치올에 묻혀 구조화(존재·부재·비교)
> 검색에서 빠진다. 정독이 기존 leaf에 안 맞는 조항마다 `taxonomy_candidates` emit(브리프 반영). **실행 제약**:
> ① **재발증거 소거 주의** — `replace_v4_result`는 저장 시 그 문서의 `v4_candidate_recurrence`+pending 후보를 삭제한다
> (`clear_document_recurrence`). 따라서 후보는 **같은 full_read 저장 패스에서 emit**돼야 하고 옛 재발증거에 의존 못 한다.
> ② **저장 경로 통일** — 후보 처리는 `replace_v4_result`(=`store_v4_results.py`) 경로에만 있다. 수술적 저장기
> (`store_rw_reextraction`·`store_pay_reextraction`)는 taxonomy_candidates를 **안 읽어 무음 폐기**(참조 0 확인) →
> 후보 담긴 정독은 반드시 전체교체 경로로 store. ③ **승격+재태깅은 한 묶음** — 캠페인 후 재발후보 노드 승격(v21)
> 시 흡수돼 있던 item **재태깅 동반 필수**. 승격만 하면 신노드가 half-populated → "형제흡수→부재질의 오답"(센서스 v2에서
> 본 병리)을 신설한다. **정정**: 앞서 cpcovrem 6건은 store되지 **않았다**(coverage 누락 실패, extractor_version 원본 유지).

- **Phase 0 (즉시·병렬)**: ① RW 잔여~58 + PAY 잔여 재추출 **완결**(반쯤 끝난 상태가 최대 리스크; Next #2) ·
  ② **T-C 비-SPA 소표본 정독**(SHA·SSA·ATA/BTA·CB류 각 5~10건 full_read — RW/PAY 뒤 직렬 금지, **병렬**;
  산출물은 결함'프로파일'이 아니라 스멜테스트+**유형별 절대-recall 정답지**(SPA 89% 편중 해소)+게이트 요건; Next #8.
  **단 SHA 정독은 "도메인 적합성 평가"** — 위 문서-클래스 구분 참조, taxonomy 권고 산출) ·
  ③ **죽은-노드 센서스 v2**(정확구문·distinct-doc; 노드당 4분류=추출누락/형제흡수/키워드오탐/소싱공백; **분류는 히트문서~10건 AI 정독 실재율로 확정**; 지금 진행 중 표 참조) ·
  ④ **CP·COV·REM 정독 재검증 트랙 — 측정 우선**(2026-07-31 소유자 결정, **매매/인수 클래스=SPA·ATA/BTA 한정**; SHA엔 이 계열 구성이 없어 부적용). **CP·COV·REM·DEF는 전량 원본 자동추출(`codex-context-review-1`) 그대로**이고 RW/PAY만 정독 재추출됐다 → 같은 자동추출기의 "범위 미경계" 결함이 이들에도 있을 개연성이 큰데 미검증. **SPA 소표본(~24문서, `cs_index/cpcovrem_measure_manifest.json`) full_read로 CP·COV·REM 결함률(범위미경계·오분류·과대추출)을 먼저 정량화** → 수치로 전면 재추출 여부 결정. T-C(비-SPA)와 이 SPA-CP/COV/REM 표본은 같은 정독의 두 축. 이미 측정된 증상: COV.NON_COMPETE ≈51%·DEF 83% 캐치올·REM/CP 죽은노드. §9.1 #5·§9.4(Next #6·#16)와 연결.
- **Phase 1 (센서스 v2 결과 기반)** — 스윕 매니페스트 준비 완료(`cs_index/deadnode_sweep_manifest.json`: ①스윕 6노드 339문서+SHA거버넌스 4·②흡수 alias제안 5·④소싱공백 27, 정밀구문 모집단·per-doc 극성검증 명시): ① **추출-누락 확정 노드만** 표적 재추출 스윕(모집단=정확구문 히트집합, v1 느슨키워드 모집단 금지; 프롬프트 극성 규율 필수—"있으면 추출·없으면 명시적 없음", "찾아라" 단독 금지; extraction_gate+store전 표본정밀도 통과조건; RW/PAY 인프라 재사용) ·
  ② **형제 흡수 노드는 재추출 안 함** — 기존 item 소급 재분류 또는 질의측 alias/인접노드 고지(DEF #20 계열); 형제흡수+coverage complete가 만드는 오(誤)confirmed_absent 경로 동시 점검 ·
  ④ **소싱 공백 노드**(FIRPTA·materiality scrape 등)는 소유자 이관·기대치 문서화; ③ 오탐은 제외.
- **Phase 2 (측정·게이트)**: 존재·비교형 정밀도 측정(§9.1 #5, SPA 먼저→T-C 유형마다 표준절차화; Next #6·#16) · 하이브리드 합집합 실측(T4 선행; Next #17 완료).
- **Phase 3 (확장 재개)**: V4-6 재개는 기존 게이트(§9.1+T-C) 그대로, 단 **순서는 물량이 아니라 v4_query_log 수요+센서스 v2 죽은-노드 지도+희소가치**로 재조정(SHA 상향—거버넌스류는 소싱 필요가 센서스로 확인; Next #14) · 하위영역 부재 선해제 사이클 정례화(환경 모델 반복, 조세 근접; Next #3).
- **병행**: 18a RTF 5건(승인·즉시)·18b OCR(승인)·18c 별지(소유자). **연기(명시)**: boilerplate 전파는 §9.3-3(경계 필드) 이후 · 검색측 백로그(윈도우 dedup·resolve_taxonomy 근사후보). **금지**: v1 센서스 수치로 스윕 착수 · v1 42종 목록 무수정 기록 · "찾아라" 단독 프롬프트 표적 재추출.

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
| 6 | **RW.ENVIRONMENT false-present 15건 정정** | 미구현 — 대상 목록은 [RW_REEXTRACT_NEXT40 §3](.docs/RW_REEXTRACT_NEXT40_20260730.md) | **대기** — 원문 전체에 환경 어휘 0건이라 판단 여지 없는 기계적 정정. 환경 게이트는 부재 풀 89건만 검증했고 **present 쪽은 미검증**이었다(모집단 18건 중 3건은 이번 정독으로 이미 정정) |
| 7 | **정독 확정 부재를 DB에 기록할 경로** | 미구현 — store가 `items: []`를 `skipped_no_items`로 버린다 | **대기** — 부재 질의 목표와 직결된 설계 공백. 이번 1건 + 150건 배치 11건이 "평가 후 부재"로 기록되지 못하고 "미평가"로 남아 있다 |

_2026-07-29 추가 반영(조율자 단일 writer): (a) `v4_clause_item` **exact-dup 7,244건 병합**(삭제 전 export 백업, quick_check ok), (b) **재추출 store에 과/미추출 게이트**(`lib/extraction_gate.py`, RW·PAY 배선; shingle-coverage grounding), (c) **PAY 재추출 121문서 반영**(과소추출 결함 대응, 0 오류). RW 부재/존재 게이트 상태는 재측정 필요._

---

## 지금 진행 중 (In flight)

| 작업 | 담당 | 상태 | 근거문서 |
|---|---|---|---|
| RW 재추출 정독 → result JSON → store | **조율자(Claude Code)+서브에이전트 직접 정독**, store는 조율자 1명(단일 writer) | 진행 중 — 675/733 문서 반영(DB 실측). 잔여 ~58 + full_read 마커 소급 대기 ~27항목. 소유권 변경(2026-07-31)으로 외부 샤드 대신 조율자가 직접 완결 | [RW_REEXTRACTION_AGENT_BRIEF](.docs/RW_REEXTRACTION_AGENT_BRIEF.md), [progress.md 2026-07-29 세션](progress.md) |
| PAY 재추출(과소추출 시스템 결함 대응) | **조율자+서브에이전트 직접 정독**, store는 조율자 | 착수 — 매니페스트 392 타깃(tier1 61/tier2 24/tier3 307) 중 **8문서 반영**. 이하 조율자 직접 정독 | [PAY_REEXTRACTION_AGENT_BRIEF](.docs/PAY_REEXTRACTION_AGENT_BRIEF.md), `cs_index/pay_reextraction_manifest.json` |
| ~~번다운 지표 도구 + 웹 대시보드 패널~~ | — | **완료(2026-07-29)** — `burndown.py` + UI-2 대시보드 번다운 패널(`/api/ops/burndown`). 절대 drift하지 않도록 `v4_search`의 부재 판정 로직을 직접 import해 재사용 | [PLAN_REVIEW 권고 5](.docs/PLAN_REVIEW_20260727.md), `burndown.py` |
| 존재형(과대추출) 축 방지장치 | 미배정(1번은 구현 완료) | 부분 — 감사기 과다분절·중복 탐지 구현(advisory, `audit_t3_v4.py`). 나머지 2~5는 미착수 | [V4_PLAN §9.3](.docs/V4_PLAN.md) |
| ~~**죽은-노드 센서스 v2** (Phase 0-③)~~ | 조율자(읽기전용) | **완료(2026-07-31)** — 정확구문·`COUNT(DISTINCT file_key)`로 truly-dead subtree **42노드** 재산출 → mid-range 20노드 실재율 정독(6히트/노드) + loc-커버리지 흡수테스트로 4분류 확정. **핵심: 기계 카운트 상위는 전부 허수·흡수**(VOTING_PROXY 201=제한부담 정의·PERMITTED_LIEN 147=RW reps 흡수·ANTI_DILUTION 106=RW.CAPITALIZATION·TERMINATION_FEE 92=위약금 정의·RWI 790=부모구문). **Phase-1 스윕 대상(①추출누락) = 소수**: RWI.PROCUREMENT·LIEN_RELEASE·COV.PERSONNEL·COV.D_AND_O·SANDBAGGING·PRIVILEGE + SHA거버넌스 4(QUORUM·DIVIDEND_POLICY·DEADLOCK·BUSINESS_PLAN_BUDGET, 유형확장과 겹침). ②흡수 5·③오탐 5·④소싱공백 22. 상세 [[dead-node-census-v2]] | [V4_PLAN §9.2](.docs/V4_PLAN.md) 로드맵 Phase 0 |
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
| 6 | **존재형·비교형 정밀도 ≥90% 측정** — family별(RW·COV·PAY) 사람 원문대조 표본 + COV.NON_COMPETE 오분류 수정 재측정 | 미배정 (표본 검증은 소유자) | **COV 엄밀 실측·게이트 미달(2026-07-30)** — AI-정독 60표본: 정답 33%·공시진술 25%·타family 18%·헤딩 23%. **정밀도 ≈51%**(≥90% 크게 미달). 정리: 헤딩 60삭제 + 공시진술 151(138+13)→RW.CONTRACTS + 분류기 3차 확장(매수측·frame·중요계약rep·TOC). COV 425→**211**. **규칙 정리는 ~50%에서 정체 — 잔여(타family 오분류·다양표현 공시진술)는 재추출(§9.3-3)이 답**. RW·PAY 표본+소유자 검증 미착수. **CP·COV·REM 측정 완료(2026-07-31, 6문서 SPA full_read vs codex auto)**: **정밀도 CP 0.55·COV 0.21·REM 0.44 / 오분류율 CP 0.37·COV 0.73·REM 0.49** → **세 계열 전면 재추출 정당, COV 파국적으로 최우선**. 근본: 표제기반 CP↔COV↔REM 오분류·형제노드 혼동·죽은노드 stub 붕괴. 이 6건 full_read는 폐기 아니라 **재추출 1차분**(cs_index/cpcovrem_results/). **미결정(소유자)**: 전 SPA 코퍼스 확대 + store 전략(RW 보존 per-family store 신설 vs full-replace). 상세 [[cpcovrem-measurement-result]]. 도구 `measure_cpcovrem.py`(계통매칭) | [V4_PLAN §9.1 #5·§9.3·§9.4](.docs/V4_PLAN.md), `lib/classification_audit.py` |
| 7 | **번다운 수치 정기 확인** — `python burndown.py --out cs_index` 또는 UI-2 대시보드 번다운 패널 | 각 세션 | 도구 완료, 운영 습관화 필요 | 상태 수치를 이 파일에 손으로 베껴두지 말고 매번 도구로 뽑아라. 문서마다 다른 수치(950/968/960)가 나오던 원인 | `burndown.py`, [PLAN_REVIEW 권고 5](.docs/PLAN_REVIEW_20260727.md) |
| 8 | **T-C 비-SPA 소표본 진단** — SHA·CB류 등 각 5~10건에서 동일 결함/수정 적용가능성 확인 | **조율자+서브에이전트 직접 정독** | **브리프·표본 준비 완료·정독 착수(2026-07-31)** — 브리프 [TC_PILOT_BRIEF](.docs/TC_PILOT_BRIEF.md), 표본 `cs_index/tc_pilot_manifest.json`(SHA8·SSA5·ATA/BTA5·CB5=23건, 유형×언어×크기 분산, **SHA 8건 전부 기존item 0=greenfield**). 전 계열 full_read + `review_method:full_read` + `defect_notes` 스멜테스트. 소유권 변경으로 **조율자가 직접 정독**(유료API 미사용, 구독형 직접 정독); store·게이트·정답지 편입도 조율자. **SHA 파일럿 1건 완료(2026-07-31)** → taxonomy 공백 3종 확인, **[TAXONOMY_EXTENSION_RECOMMENDATION](.docs/TAXONOMY_EXTENSION_RECOMMENDATION.md)** 작성(SEC 담보 family·SHA 경제권·재무약정 등), SHA store는 신설 전까지 보류 | [V4_PLAN §9.2 T-C](.docs/V4_PLAN.md) |
| 9 | **T-D (2) 후보 생성기 조이기 + 기존 backlog 재분류** — 도구 완성(`lib/v4_candidate_policy.py`·`backfill_v4_candidate_recurrence.py`·`reclassify_v4_candidate_backlog.py`) | 조율자(DB 쓰기) | **재분류 moot 확인(2026-07-30)** — dry-run: pending **13,222**(29,807에서 감소) 전부 정당(재발≥2문서 11,255 + 구체 sub-node 1,967), **문서특정 일회성 = 0** → 적용해도 0건 변경. 옛 +159는 29,807 기준. 남은 13,222는 실제 taxonomy 제안이라 pending 유지가 맞고 그 부재차단은 결함 아님 | [V4_PLAN §9.2 T-D](.docs/V4_PLAN.md), [PLAN_REVIEW 권고 3·항목 2 심화 + 2026-07-29 정정](.docs/PLAN_REVIEW_20260727.md) |
| 10 | **DEF 표적 재실행** — 매니페스트 206 타깃(items=0 100 + 1~3 106) | 미배정 | 미착수 | PAY와 달리 집중 tail 결함이라 **값싼 표적 재실행**으로 회수 가능. PAY 후행/병행 | [progress.md 2026-07-29 PAY/DEF 진단 세션](progress.md), `cs_index/def_reextraction_manifest.json` |
| 11 | ~~**§9.3-2 후퇴가드 대칭화** — item 수 급증 시 store 전 표본확인 WARN~~ | — | **완료(2026-07-30)** — item-surge WARN + 과대추출 게이트 및 회귀 테스트 반영 | 과대추출 축의 방지장치 | [V4_PLAN §9.3](.docs/V4_PLAN.md), `lib/extraction_gate.py` |
| 12 | **§9.3-3 경계 자기설명 필드**(REP vs COV 근거 기재 강제) | 미배정 | **대기(시점 고정)** — RW20·PAY tier1 정독 배치 종료 후 도입(소유자 결정) | 진행 중 배치 방해·부분 재작업 방지를 위해 시점이 결정돼 있음 | [V4_PLAN §9.3-3·§11](.docs/V4_PLAN.md) |
| 13 | **권고 6 — T4 로드맵 강등 문서화** | 미배정 | **미이행** — `docs_progress_v2.md`는 아직 "T4는 구현 확정"으로 기술 | 문서 간 모순(진행 계획은 보류, 설계문서는 확정) 해소 | [PLAN_REVIEW 권고 6](.docs/PLAN_REVIEW_20260727.md), [docs_progress_v2 T4](.docs/docs_progress_v2.md) |
| 14 | **권고 4 — 유형 균형 재조정**(SPA 98% vs SHA 1.9%) | 미배정 | 확장 재개 시점까지 보류 | 확장이 멈춰 있는 동안은 실행 대상 아님. 재개 시 계획 순서를 실제로 지킬 것 | [PLAN_REVIEW 권고 4](.docs/PLAN_REVIEW_20260727.md) |
| 15 | **업종(제조업 등) 메타 분류** → **#19에 흡수** | — | #19로 통합(2026-07-29) | 버전 필터는 구현 완료됐고 남은 공백이 업종 축. 연도·규모·준거법과 같은 계열이라 함께 다룬다 | [progress.md 2026-07-29 버전 분류 세션](progress.md) |
| 16 | **비교형 셀 정확도 검증** — V4C01~06 비교표의 모든 셀을 원문 대조해 correct/wrong_value/wrong_clause/false_empty/incomparable 라벨링 | 미배정 (라벨링은 소유자) | 미착수 — **검증 계획 자체가 없던 공백** | §0에서 비교·집계를 **"필수"**로 분류해놓고 한 번도 정확도를 잰 적이 없다. 부재형=전수·존재형=§9.3 표본인데 비교형만 무측정. **빈 셀이 자동 정답이 아니라는 점**이 핵심 | [V4_PLAN §9.4](.docs/V4_PLAN.md) |
| 17 | **절대 recall 측정** — `eval_absolute_recall.py` | 조율자 | **하이브리드 합집합 완료(2026-07-30)** — 정답지 29,767 item/806 저장. within-depth(1000): structured 0.576 → **하이브리드(structured∪item_text) 0.673 → +paragraph 0.678**(paragraph 거의 무기여, doc-depth30·1term). **recall@10 = 4.6%가 진짜 gap**(within은 68%인데 top10엔 없음 = §9.6 개념질의 랭킹 병목). **이 0.678/@10 4.6%가 V4-7 ablation 비교 arm** | 풀링은 **상대** 재현율만 준다. 정독 부산물 정답지. depth 1000·doc30 예산이라 within-depth는 **하한**(더 깊으면↑) | [V4_PLAN §9.5](.docs/V4_PLAN.md) |
| 18a | **`.doc` 확장자 RTF 5건 변환** — `detect_doc_kind()`가 RTF를 거부해 실패. Word는 RTF를 정상 처리 | 미배정 | 실측 완료·미착수 | **보고서 전체에서 가장 값싼 recall 회수.** 5건 전부 ATA/BTA 국문인데 그 유형 V4 커버리지가 5.6%다 | [CORPUS_BLIND_SPOTS](.docs/CORPUS_BLIND_SPOTS_20260729.md) |
| 18b | **스캔 PDF OCR** — 48건/1,931쪽. Windows.Media.Ocr(`ko` 설치됨) + Windows.Data.Pdf, **새 의존성 0·비용 ₩0·약 1시간** | **소유자 결정 필요**(스키마 변경 + OCR 텍스트 정책) | 실측 완료·승인 대기 | **recall의 하드 상한** — 추출 품질을 아무리 올려도 이 48건의 recall은 영원히 0. SHA 10건이 급소(SHA V4 커버리지 2.1%인데 2025년 체결본 포함) | [CORPUS_BLIND_SPOTS](.docs/CORPUS_BLIND_SPOTS_20260729.md) |
| 18c | **미수집 별지 502건(148문서) 수집** — 읽기 실패가 아니라 **애초에 안 받은 것** | 소유자(원본 수집) | 실측 완료 | OCR로 **하나도 복구 안 된다**. `annex_partial`이 부재 차단 2위 사유(3,863)인데 그 뿌리의 일부가 여기다 — 추출 문제가 아니라 소싱 문제 | [CORPUS_BLIND_SPOTS](.docs/CORPUS_BLIND_SPOTS_20260729.md), `색인 업데이트 설명서.md` §3.2 |
| 19 | **거래 메타데이터 확장** — **준거법(70.1%)·관할법원(51.3%)·중재합의(95.7%)·거래연도(체결일 420건)** 채택. **규모 구간·업종은 반대** | 미배정 | 실측·도구·테스트 완료(`derive_deal_meta.py`, 53 tests). DB 적용 대기 | 조항 추출 품질로는 **영원히 답할 수 없는 질의 계급**을 연다. 단 제안의 "v3 대금으로 규모 구간 파생 가능"은 **사실이 아님** — doc_meta 1,999행 중 v3 스키마 60행, 밴딩 안전한 건 **8건** | [DEAL_METADATA](.docs/DEAL_METADATA_FEASIBILITY_20260729.md) |
| 20 | **DEF 구조화 검색** — 용어명 정규화를 기존 item에 **소급 적용** | 미배정 | **규모 재측정(2026-07-30)**: DEF **22,180 중 캐치올 DEF.CONTRACT_TERM = 18,404 = 83.0%**(78%에서↑). 캐치올은 전부 개별 정의용어(Drag-Along/ROFR/Put Option/Damages/Subsidiary 등)로 다수가 한국어 canonical 프리픽스 보유하나 노드 미승격 → 정의검색 사실상 FTS 전용. 명명 노드 ~15개뿐 | 18k 정규화는 후보 도구+대형 DB쓰기(별건) | [V4_PLAN §11](.docs/V4_PLAN.md) |
| 21 | **T4 = V4-7 예약 실험** — 골든셋 ablation으로 채택/폐기 | 미배정 | **결정됨(2026-07-29): V4-7 편입**(§10 표 반영 완료) | 강등 근거는 비용·복잡도였는데 **목표가 품질 최우선으로 바뀌면 계산이 달라진다**. 잔여 gap이 표현 변이이고 V4 원자 명제는 임베딩 단위로 이상적. "날짜 없는 언젠가"를 순서 있는 항목으로 | [V4_PLAN §10.1](.docs/V4_PLAN.md) |
| 22 | **랭킹 품질** — FTS+bm25 전환 완료·나머지 T4 | 부분완료→T4(V4-7) | **진단 확정·FTS 배선·공정 베이스라인(2026-07-30)** | 462위·1.5%는 **질의 신호 부재**. **최대 발견: `v4_item_fts`(137,865 동기)가 미배선**이었음 → text 경로를 FTS MATCH+bm25 하이브리드로 전환(연속구문 우선→bm25 IDF, <3자 LIKE 폴백). verbatim recall@10 **0.93**(다중정답 채점 후), paraphrase **0.609**(noise정리 후 공정 베이스라인, 단발; **ablation은 어휘+재질의루프 vs T4+루프**로 비교). **채점 아티팩트 수정(2026-07-30, Fable §9.6)**: verbatim @1은 이전에 소스 file_key 항목만 정답으로 쳐서 동일-verbatim 형제가 @1에 나와도 미스 처리→@1 0.48로 억눌림(예전 0.63→0.44 "표본차이" 설명이 부정확했음). **동일 전체-verbatim 형제(문서 무관)를 정답으로 치는 다중정답 채점**으로 전환→@1 **0.48→0.70**(40자 prefix만 겹치는 다른 조항은 불인정→1.0 동어반복 아님). 착수: #1 다중키워드·#5 MCP docstring(+하이브리드 지침)·#6 low_query_signal·#7 v4_query_log·0건힌트·coverage IN-filter. 488 pass. **T4 선행조건 승격**: #9(a) 하이브리드 합집합 실측(#17). 보류: #4 정적prior·#8 교차언어 사전확장·#10 다양화·**#2 개념-only 열거 윈도우함수 dedup(백로그)** | [V4_PLAN §9.6](.docs/V4_PLAN.md) |

| 23 | **딜/프로젝트 그룹핑** — 같은 거래의 문서(SPA+SHA+투자+담보 등)를 묶어 검색/조회 | 미배정(조율자 설계) | **계획·구현가능성 확인(2026-07-31 소유자 요청)** — 최상위 폴더는 **문서유형별**이라 딜 미묶임. **파일명 규칙 `<코드명>_<대상>_<유형>_<단계>(id.v1)`의 선두 접두어가 deal_id**(Broccoli_Kurly SSA+SHA, Numero_무신사 SSA+SHA 등 깔끔히 페어링). `parties_json`은 스텁이라 당사자그룹핑은 2단계. **P1**: 파일명 접두어+하위폴더→`deal`·`deal_membership(file_key,deal_id,role,version_phase,confidence,basis)` 테이블(role=인수/거버넌스/투자/부속, ctype→doc-class 맵). **P2**: full_read 부산물로 전문(preamble) 당사자 추출→겹침 병합. 검색: MCP·웹 `--deal` 필터+딜별 그룹. 상세 [[deal-project-grouping-feature]] | 문서-클래스 구분(로드맵) 연계 |

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
