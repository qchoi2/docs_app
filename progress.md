# Progress

> 상세 초기 이력(Phase 0~3, 2026-07-09~07-16)은 [.docs/PROGRESS_ARCHIVE.md](.docs/PROGRESS_ARCHIVE.md)로 이동했다.
> 이 파일은 **현재 상태 요약 + V4 원자 항목 계층 이력**을 유지한다.

> **다음 할 일은 [NOW.md](NOW.md)가 단일 원천이다.** 이 파일은 이력·현재 상태 기록이다.

## 현재 상태 요약 (Current Status) — 2026-07-27 기준

**프로젝트**: M&A 계약서 샘플 코퍼스(약 2,245파일)를 자연어로 검색하는 개인용 프로그램.
구조화 메타데이터 + FTS5 + 통제 taxonomy 기반. 웹앱·MCP·CLI 3경로. 유료 API 자동 호출 금지.
설계 원칙과 로드맵은 [.docs/docs_progress_v2.md](.docs/docs_progress_v2.md), V4 계획은
[.docs/V4_PLAN.md](.docs/V4_PLAN.md), 구현 계약은 [.docs/IMPLEMENTATION_BRIEF.md](.docs/IMPLEMENTATION_BRIEF.md).

**완료된 계층**
- **T1/T2 (검색 코어)**: `index_contracts.py`(색인·중복그룹·¶마커·분류), `search_contracts.py`
  (FTS5 trigram + term_dict 동의어 확장 + RRF 랭킹 + T3 clause 필터 + v3 구조화 필터),
  `eval_search.py`(골든세트 회귀). CLI 보조도구 `inspect_file`/`open_text`/`stats_contracts`/`read_contract`.
- **T3 (조항맵 메타)**: `enrich_contracts.py` 파일 하네스(meta_schema v2), `doc_meta` 조항맵.
  전량 초벌 + 정밀 v3 파일럿 60건 전건 사람 승인 완료(**V4-0 통과**).
- **웹앱** (`webapp.py`, stdlib WSGI, 127.0.0.1): 읽기전용 검색 UI, 운영 대시보드(UI-2),
  리서치 UI(UI-3), 온보딩/진행률(UI-0.2/0.3), Runtime API Settings, one-writer job 큐,
  taxonomy 후보 관리(UI-5), 도움말 페이지.
- **MCP** (`mcp_server.py`, `v4_mcp_tools.py`): 읽기전용 도구 7개 + V4 검색/비교 도구 2개.
- **V4 (세부 원자 항목 계층)**: taxonomy **v19 / 414 nodes**, 6-family(RW·CP·COV·DEF·PAY·REM),
  본문·별지 분리 coverage, 별지 물리문단 완전성 감사, 하이브리드 검색(구조화+FTS+문단폴백),
  안전한 부재 판정. SPA·SSA·ATA/BTA·SHA뿐 아니라 CBSA·NPA·BWSA·WPA·EBSA를
  전 항목 추출 범위에 포함한다. 누적 V4 item **100,207개**, 평가 문서 **968건**,
  pending taxonomy 후보 **29,807개**.

### ▶ 재시작 시 여기부터 (Resume — 2026-07-28)

**Gate B 완료 → §9 결정: 전량 확장 중단, RW 추출 교정 선행.** 근거·경위:
`.docs/V4_GATE_B_SYNTHESIS_20260728.md`, `.docs/V4_RW_COVERAGE_DEFECT_20260727.md`,
`.docs/V4_GATE_B_ABSENCE_FINDINGS_20260727.md`, `.docs/PLAN_REVIEW_20260727.md`.

- **부재형 Gate B 전수 검증**: V4 부재정밀도 76%, RW 진술계열 취약(조세 44%·환경 50%),
  특약·조건 양호(90%대). 근본원인: RW 추출이 실질 진술(IP 1.8%·보험 0.2%·노무 16%) 누락 +
  coverage 일괄 도장. 검증값 `data/v4_gate_b_verdicts.json`.
- **적용된 안전장치**: `v4_search.search_clause_absence`에서 RW family는 confirmed_absent 금지
  → needs_review 강등(CLI/웹/MCP 전파). coverage 정직화 `audit_rw_coverage.py --apply`(733 partial).
- **진행 중 = RW 재추출** (`.docs/extract_prompt_v4_rw_addendum.md` 기준):
  도구 `plan_rw_reextraction.py`(--shard k/N)·`store_rw_reextraction.py`(--mode replace|add, DB
  단일 writer·백업)·`reextract_rw_pilot.py`. 대상 733개(SPA 525 우선). 워크플로: 진술 조항
  정독→`cs_index/rw_reextract_results/<key>.json`→store(중앙 순차)→`eval_v4_gate.py --pooled`.
  **처리 완료(tax/env false-absence 수정): 현대호텔·Apollo·Kindle·Jaguar-P (4문서)**.
  **저장 누계: RWRX 594/733 문서**(2026-07-28, 626 result 중 592 stored·27 skipped_regression·7 empty).
- **병렬화**: GPT/Codex를 샤드로 병행 가능. 지시서 `.docs/RW_REEXTRACTION_AGENT_BRIEF.md`.
  에이전트는 result JSON만 쓰고, DB 저장·commit은 조율자 1명이 직렬(단일 writer).
- **정독 마커 (2026-07-28 결정·구현)**: GPT가 방식을 "진술조항 전체 정독 재구성"으로 격상.
  정독분에는 result JSON 최상위 `"review_method":"full_read"` 필수 → store가 그 문서 한정으로
  후퇴가드 해제(정독은 그 문서 RW 전체 권위 세트라 도메인 감소=오분류 정정). 없으면 가드 유지.
  현재 27건이 마커 없어 차단됨(정독 성과 미반영, 예: 0844 16→51 스킵). GPT가 마커 소급 부여 후 재저장 필요.
  방침: **표적 정독(결함신호 문서 우선) 우선 + Gate B 수렴 확인**. 수렴 시 전수 정독은 **유예**(중단 아님) —
  비표적도 정독 효과 유의미(Δ항목 +21.7)하므로 **프로젝트 후반 궁극적 전수 정독**이 목표. 자동 잔존분은 임시값.
- **매수인 진술 포함 (2026-07-28 결정)**: 재추출이 매수인 진술도 RW.BUYER로 담는다(자금조달·
  no-reliance·독자조사·권한 등). store replace는 이제 RW.BUYER도 전체 교체 대상이고, 후퇴 가드가
  RW.BUYER 도메인 손실도 스킵으로 보호(구버전 buyer-less 결과가 기존 buyer를 지우지 못함).
  → 매수인 진술 존재·부재 검색이 신뢰성 있게 열린다.
- **다음**: → **[NOW.md](NOW.md)** 참조. 앞으로 할 일 목록은 이 절에서 유지하지 않는다(단일 원천 이관).
  위 항목들은 2026-07-28 시점의 **상태 기록**이며, 그 이후 진척·우선순위·담당은 NOW.md가 최신이다.
- **다른 계열로 일반화 (2026-07-28 결정, RW 마무리 후)**: RW를 Gate B로 개선 확인한 뒤,
  `audit_rw_coverage.py`를 CP/COV/DEF/PAY/REM용으로 일반화해 "complete인데 하위영역 누락"을
  **먼저 측정**하고, 결함이 확인된 계열만 동일 파이프라인(plan→병렬 result JSON→store→eval)으로
  재추출한다. 결함 없는 계열까지 무조건 재추출하지 않는다(낭비 방지).
- **보류**: 전량 확장(§9로 중단), T4(벡터).

**테스트**: `python -m pytest --basetemp=<쓰기가능경로>` → **253 passed, 1 skipped**.
권한: `.claude/settings.local.json`에 재추출/eval 스크립트 실행 allow 규칙 추가됨.
- ⚠️ 환경 주의: `AppData\Local\Temp\pytest-of-<user>` 폴더 권한 문제로 pytest가 대량
  `PermissionError`를 낼 수 있다. 이때는 `python -m pytest --basetemp=<쓰기가능경로>`로 우회한다.
  (과거 세션이 이를 우회하려고 repo 안에 `.tmp_pytest_*/`를 만든 흔적이 있었고, 이번에 정리·gitignore 처리했다.)

**웹앱 실행**
```
cd C:\Users\qchoi\Desktop\cowork\docs_app
python webapp.py --out cs_index      # 또는 run_webapp.bat [색인경로]
```

**저장소 위생 (2026-07-27 정리)**: `.backups/`(DB 스냅샷, 수 GB), `contract_docs/`(원본 코퍼스),
`cs_index/`·`root/`, `.tmp_pytest_*/`, `.vscode/`는 gitignore로 추적 제외. 원본 코퍼스와 DB
백업은 절대 커밋하지 않는다.

---

### V4 다음 단계 - 세부 조항 원자 항목 분류(계획 확정, 미구현)

- v3 결과가 정확하다는 전제 아래, v4는 v3를 덮어쓰지 않고 `진술보장`·`선행조건`·`확약`
  아래의 세부 의미를 검색 가능한 원자 항목으로 저장하는 계층으로 설계한다.
- 단순히 긴 세부 태그를 계속 추가하지 않고, `조항 유형 + 분야 + 세부주제 + 행위/쟁점 + 대상 +
  시점 + 주체 + 원자적 명제`를 분리한다. 예: `진술보장/노무/임금/미지급임금 없음`,
  `선행조건/종결서류/이사 사임서 제출`, `확약/정부신고/기업결합신고서 제출`.
- 조항의 부재와 부정형 진술을 구분한다. 예를 들어 “미지급임금이 없음”은 미지급임금 관련
  진술보장이 존재하는 것이며, 해당 세부 조항이 없는 것으로 저장하지 않는다.
- 예정 저장 구조는 통제 분류체계 `v4_taxonomy_node`, 표현 변이 `v4_taxonomy_alias`,
  문서별 원자 항목 `v4_clause_item`, 평가완료·부분평가·미평가를 구분하는
  `v4_document_coverage`, 신규 분류 검토 큐 `v4_taxonomy_candidate`이다.
- 신규 표현은 즉시 정식 태그로 만들지 않는다. 기존 분류와 의미가 같으면 alias, 대상만 다르면
  object/qualifier로 저장하고, 독립적인 검색 의도와 법적 의미가 있는 경우에만 후보→검토→승인 후
  정식 taxonomy로 승격한다.
- 구현 순서는 v4 스키마·초기 taxonomy·추출 프롬프트와 감사기 구축 → 현재 대표 10건 재추출 →
  기존 60건 파일럿으로 taxonomy 발견·안정화 → CLI·웹·MCP 세부 검색/비교 기능 → 골든 질의 평가 →
  전체 계약 순차 확장으로 정했다.
- 전체 확장에서도 프로젝트가 유료 API를 자동 호출하지 않는 원칙을 유지한다. AI 클라이언트가
  MCP 또는 파일 기반 작업으로 문서별 필요한 조항만 읽고 결과를 제출하며, 서버는 검증·저장만 담당한다.

### 2026-07-16 세션 20 — V4 계획 검토·확정: `.docs/V4_PLAN.md` (Claude)

- 위 V4 초안을 검토해 `.docs/V4_PLAN.md`로 확정했다. 초안 대비 변경·추가 사항:
  - **적용 범위**: 전 항목 추출 대상을 SPA·SSA·ATA/BTA에 **SHA 추가**(소유자 지시).
    나머지 유형은 v3 유지, agent_log 수요 확인 시 유형 단위 편입.
  - **taxonomy 거버넌스 UI(UI-5)**: 신규 분류 후보의 승격·alias 병합·반려를 웹앱
    `/taxonomy` 화면에서 **버튼 클릭만으로** 처리(소유자 지시 — 이후 개발 없이 운영 가능
    해야 함). 초기 seed는 family/domain 2단계까지만, 3단계는 후보 큐에서 UI로만 승격.
    DB 테이블이 taxonomy 단일 원천, yaml은 내보내기 산출물. `UI_ROADMAP.md`에 UI-5 추가.
  - **하이브리드 검색**: taxonomy 필터 ∪ 항목 텍스트 FTS(`v4_item_fts`) ∪ 문단 FTS
    합집합 — 분류 오류를 recall 손실이 아닌 순위 하락으로 강등(누락 방지의 핵심).
  - **coverage 본문/별지 분리**: 부재 판정은 body+annex 평가 완료 시에만 허용,
    스캔 별지 미평가 건수 상시 고지.
  - **term_dict 통합**: 진술보장 하위 주제 항목을 v4 노드에 1:1 매핑/alias 흡수,
    `term_dict_tools.py --validate`에 매핑 검증 추가.
  - **추출 경로 단순화**: 신규 MCP 추출 도구 대신 검증된 enrich 파일 하네스 재사용
    (`enrich_inputs_v4`/`enrich_results_v4` + `audit_t3_v4.py`). MCP는 질의 쪽
    `search_clause_items`·`compare_clause_items` 2개만 추가. 결정적 로컬 추출로
    대체 금지(v2 초벌의 한계가 v4를 하는 이유).
  - **이중 게이트**: 자체 품질 게이트 A에 더해, 세부 골든 질의 30~50개로
    (a) v3+MCP 에이전트 정독 vs (b) v4 하이브리드를 비교하는 **게이트 B**를 전량 확장
    조건으로 추가. (b)가 recall 우위가 아니면 부재 판정·비교 기능만 남기는 축소판 전환.
  - **선행 게이트**: V4-0 = v3 파일럿 60건 사람 승인. 승인 전 V4 착수 금지.
- 관련 문서 갱신: `.docs/UI_ROADMAP.md`(UI-5 + 우선순위), `.docs/T3_V3_PILOT.md`(다음
  단계 포인터), `.docs/MANIFEST.txt`. 코드 변경 없음.

### 2026-07-16 세션 21 — T3 v3 대표 10건 QA + 소유자 지시 정정 (Claude)

- 대표 10건을 원문과 독립 대조(`cs_index/qa_v3_10.py`)해 QA 리포트
  `cs_index/t3_v3_qa_10.md`를 생성했다. verbatim↔문단 위치는 10건 전부 100% 일치,
  비계약 2건도 정상 처리. present 조항 정규화 수치 1건이 원문 미근거로 확인됐다.
- 소유자 지시 반영: 753aeef4 진술보장 present=true(¶109 원용 근거, med),
  37c9a8 선행조건은 부재 유지, dc3b4d MAC 부재판정 유지 + 근거 메모.
- 37c9a8 손해배상액 예정은 제11조(주식양도제한) 위반 시 1억원 지급으로,
  거래무산 위약금이 아님을 원문(¶104) 확인 → `break_fee_amount` 매핑 제거.
- 753aeef4 풋옵션의 근거없는 `closing_days:60/interest_rate_pct:10` 제거,
  loc를 소제목→운영문단(108–111)으로 확장, verbatim 교체.
- `.docs/extract_prompt_v3.md`에 지침 11–15 추가(정규화 숫자 근거 강제, verbatim 소제목 금지,
  다문단 loc, 부재 근거메모, break_fee 오용 금지).
- `audit_t3_v3.py` 숫자-근거 검사를 3필드→전체 숫자형 필드로 확장, 콤마·억/만·대괄호 표기 인정.

검증:
- `python audit_t3_v3.py --manifest cs_index/t3_v3_pilot_manifest.json` -> pass=10, review=0, error=0
- 감사기 음성테스트: 근거없는 60/10 탐지, 콤마 5억·[1]년→12개월 정상 통과
- `python -m pytest -q tests/test_t3_v3.py tests/test_enrich_contracts.py` -> 17 passed

### 2026-07-16 세션 22 — T3 v3 국문 우선 배치 01 추출·감사·QA (Codex)

- V4-0 게이트의 남은 50건 중 국문 우선 10건을 부분 정독했다: SPA 4건, SHA 3건,
  SSA 2건, MOU 1건. `cs_index/enrich_results_v3/<file_key>.json` 10건과
  `cs_index/t3_v3_human_review_batch_01.md`를 생성했다. 유료 API와 DB 쓰기는 사용하지 않았다.
- 부속합의서·Joinder가 원 SPA/SHA를 포괄 원용해도 현재 파일에 조문이 재현되지 않으면
  해당 조항을 추측하지 않았다. MOU의 향후 본계약 진술보장, SSA의 조세 진술보장 존속기간,
  매도인 명의 계약금 계좌도 각각 현재 진술보장·독립 조세배상·에스크로로 오분류하지 않았다.
- 최초 감사에서 인용 위치·문구 불일치 4건을 원문에 맞게 정정했다. 감사기가 `0.5억원` 같은
  소수 억 단위 금액을 인식하도록 보강하고 회귀 테스트를 추가했다.
- 배치 종합 QA 리포트 `cs_index/t3_v3_qa_batch_01.md`를 생성했다. 원문 근거가 있는
  present 조항 81개는 모두 지정 문단과 일치하고 정규화 숫자도 근거 검사를 통과했다.
- 배치 결과는 pass 7, review 3이다. review 3건(`0ddde0e62bd84e41`,
  `2a08ef8b2699dca5`, `a5da55951cfdabfb`)은 오류가 아니라 당사자·대금·책임제한 등이
  공란인 초안이므로 사람 확인 대상으로 유지했다.
- V4-0 누적 상태는 결과 생성 20/60, pass 17, review 3, error 0, pending 40이다.
  사람 승인 전이므로 `catalog.sqlite`에는 v3 결과를 기록하지 않았다.

검증:
- `python audit_t3_v3.py --manifest cs_index/t3_v3_pilot_manifest.json` -> `pass=17`, `review=3`, `error=0`, `pending=40`
- `python -m pytest -q tests/test_t3_v3.py tests/test_enrich_contracts.py` -> 18 passed

### 2026-07-16 세션 23 — v3 공란 처리 기준 소유자 확인 (Codex)

- 소유자가 당사자명·매매대금·배상상한 등 원문 입력값이 공란이면 값 없음으로 반영하도록
  확인했다. 공란 당사자는 임의 생성하지 않고, 공란 금액·비율은 `null` 또는 정규화 필드
  미생성으로 유지한다.
- 배치 01 결과 JSON은 이미 이 원칙대로 작성되어 있어 수정이 필요하지 않았다.
  `cs_index/t3_v3_qa_batch_01.md`에 소유자 확인 기록을 추가하고 관련 공란 체크 항목을 승인 처리했다.
- `review` 3건은 자동감사 오류가 아니라 초안 문서의 `low` 신뢰도 표시이므로 그대로 유지한다.
  남은 사람 확인은 원문에 실제 기재된 수치·조항의 법률적 의미 판정뿐이다.

### 2026-07-16 세션 24 — 배치 01 전건 사람 승인 + SHA 참조금액 구분 (Codex)

- 소유자가 배치 01의 남은 법률적 의미 판정을 모두 승인했다. 원문 재대조 결과
  `a5da55951cfdabfb`의 300억원은 현재 SHA 자체 대금이 아니라 별도 신주인수계약의
  RCPS 투자금액이고, Drag-along은 투자대상회사 별도 SHA상 권리이며, IRR 15% 초과분의
  10% 지급은 거래대금 earn-out이 아닌 주주간 초과이익 배분이라는 판정을 확정했다.
- `a5da55951cfdabfb`의 현재 SHA 대금은 `amount_value=null`로 바꾸고, 300억원은
  `definitions_json`의 `관련 신주인수계약 투자금액`으로 보존했다. 따라서 SHA 자체 대금
  범위 검색에서 300억원으로 오인되지 않는다.
- `동반매도요구권.present=false`, `earn-out.present=false`, `has_earnout=false`는 유지했다.
  다만 별도 Drag-along의 행사 효과와 초과이익 배분 내용은 원문 위치·검토 메모에 남겼다.
- `cs_index/t3_v3_human_review_batch_01.md`의 문서별·조항별 확인란과 배치 승인란을 모두
  승인 완료로 기록했다. `cs_index/t3_v3_qa_batch_01.md`에도 사람 승인 10/10을 반영했다.
- 자동감사 결과의 `review=3`은 공란이 있는 초안의 `low` 신뢰도 표시로 유지되며,
  미승인 상태를 뜻하지 않는다. V4-0 사람 승인 누계는 배치 01의 10/60건이다.
  결과 생성 누계는 20/60건이며, 나머지 40건 추출·감사·사람 승인이 남았다.
- 전체 60건 승인 전이므로 `catalog.sqlite`에는 v3 결과를 기록하지 않았다.

검증:
- `python audit_t3_v3.py --manifest cs_index/t3_v3_pilot_manifest.json` -> `pass=17`, `review=3`, `error=0`, `pending=40`
- `python -m pytest -q tests/test_t3_v3.py tests/test_enrich_contracts.py` -> 18 passed

### 2026-07-16 세션 25 — T3 v3 국문 중심 혼합유형 배치 02 추출·감사·QA (Codex)

- V4-0 게이트에서 결과가 없던 40건 중 국문 중심 혼합유형 10건을 부분 정독했다:
  SSA 1건, ATA/BTA 2건, JVA 1건, 공동투자 1건, BW 1건, EB 2건,
  주식교환 1건, MOU 1건. `cs_index/enrich_results_v3/<file_key>.json` 10건과
  `cs_index/t3_v3_human_review_batch_02.md`를 생성했다. 유료 API와 DB 쓰기는 사용하지 않았다.
- 당사자명·대금·교환비율 등 원문 입력값이 없으면 `null` 또는 정규화 필드 미생성으로
  처리했다. 실사 후 합의할 MOU 대금, 총액 없는 공동출자, 공란인 주식교환비율을 임의 보충하지 않았다.
- `d52f0cbc2a9171bb`의 800억원은 현재 변경계약의 신규 대금이 아니라 원 교환사채인수계약의
  전자등록총액이므로 현재 대금은 `null`로 두고 정의·메모에만 참조금액으로 보존했다.
- 비구속 MOU의 별첨·거래범위 제안은 현재 확정 의무와 구분했다. `30fae2c6d27a9f8c`의
  500억원, 선행조건과 경업금지는 비구속 별첨 조건으로 표시했고, `b0a1cc03cb0baa69`의
  임직원·자산·부채 승계도 비구속 거래범위 제안으로 신뢰도를 낮췄다.
- `584a623ee466906c`와 `c06cdd8feff8b75b`는 각각 손상된 JVA 중간 조각과 BW 비교본 조각이라
  당사자·대금·조항을 추측하지 않고 `document_status=insufficient_text`로 분리했다.
- 배치 QA 리포트 `cs_index/t3_v3_qa_batch_02.md`를 생성했다. present 조항 64개는 모두
  지정 문단과 일치하고 정규화 숫자도 원문 근거 검사를 통과했다.
- 이번 배치 결과는 pass 5, review 5, error 0이다. review 5건은 초안·공란 또는 본문 추출
  불충분에 따른 낮은 문서 신뢰도이며 자동감사 오류는 없다.
- V4-0 누적 상태는 결과 생성 30/60, pass 22, review 8, error 0, pending 30이다.
  배치 02는 사람 검토 대기이며, 사람 승인 누계는 10/60건이다. 전체 승인 전이므로
  `catalog.sqlite`에는 v3 결과를 기록하지 않았다.

검증:
- `python audit_t3_v3.py --manifest cs_index/t3_v3_pilot_manifest.json --input-dir cs_index/enrich_inputs_v3 --result-dir cs_index/enrich_results_v3 --report cs_index/t3_v3_audit_report.json` -> `pass=22`, `review=8`, `error=0`, `pending=30`
- `python -m pytest -q tests/test_t3_v3.py` -> 8 passed

### 2026-07-16 세션 26 — T3 v3 최종 30건 추출·전건 승인·V4-0 통과 (Codex)

- 배치 03~05 각 10건을 원문 부분 정독해 `enrich_results_v3` 60건을 완성했다. 공란 당사자·대금·배상상한은 값 없음으로 두고, 별도 계약의 금액·권리와 비구속 제안은 현재 계약의 확정값으로 승격하지 않았다.
- `c28dbecbb5bac628` 초안은 가액·비율 공란, `7084be8d0c8a3f68` 체결본은 현물출자가액 129,605,780,224원과 분할·분할합병대금 590,426,332,130원을 서로 다른 구성가치로 보존하고 임의 총액을 만들지 않았다.
- `dbccf24bc86783f4`는 매수인명·기초가격·에스크로가 미확정인 Buyer First Markup, `a51842fc51010f69`은 1,130억원 기초대금과 5억6500만원 basket이 명시된 체결본으로 구분했다.
- Kurly·Danggeun SHA의 별도 SSA 투자금은 현재 SHA 대금으로 넣지 않았고, FnStars Term Sheet의 USD 11.1m·USD 5m는 비구속 제안값으로 표시했다. 영문 BTA 양식의 당사자·대금 공란은 `null`로 유지했다.
- 자동 감사 결과는 총 60건, pass 42, review 18, error 0, pending 0이다. review 18건에는 근거 이슈가 없으며 초안·공란·양식에 따른 low 신뢰도 표시다.
- 소유자의 원문검토 위임·나머지 승인 지시에 따라 `t3_v3_human_approval_60.json`과 `t3_v3_v4_0_gate.md`에 60/60 승인을 기록했다.
- 승인 범위를 정확히 저장하는 `store_t3_v3_manifest.py`를 추가해 manifest 60건만 `doc_meta` v3로 저장했다. 결과는 processed=60, stored=60, error=0이다.

검증:
- `python audit_t3_v3.py ...` -> pass=42, review=18, error=0, pending=0
- `python eval_search.py --out cs_index --tiers T1,T2,T3` -> pass=17, fail=1, unscored=7, skipped=8 (기존 Q28 1건 실패 유지, 신규 회귀 없음)
- T3·검색·MCP 관련 테스트 -> 41 passed

### 2026-07-16 세션 27 — V4-1 원자항목 기반·coverage·감사기 구현 (Codex)

- 기존 v3를 변경하지 않는 additive V4 스키마를 `v4_schema.py`에 구현하고 `catalog.sqlite`에 초기화했다: taxonomy node 43, alias 168, clause item 0, coverage 0.
- `v4_clause_item`과 trigram FTS, `v4_document_coverage`의 body/annex 분리 상태, `v4_taxonomy_candidate` 후보 큐와 taxonomy 버전 메타를 추가했다.
- 초기 taxonomy는 계획대로 family/domain 2단계까지만 seed하고 topic은 만들지 않았다. 신규 topic은 후보 큐와 향후 UI 승격 절차를 거친다.
- `statement_polarity=none_exist`를 지원해 “미지급임금이 없음”을 진술보장 존재로 저장하며, 부재 판정은 body complete + annex complete/no_annex일 때만 허용한다.
- `.docs/extract_prompt_v4.md`와 `audit_t3_v4.py`를 추가했다. 감사기는 taxonomy ID·family·문단 위치·verbatim·정규화 숫자 근거·coverage·후보 근거를 검사한다.
- `data/v4_term_mapping.yaml`에 term_dict의 진술보장 하위 7개 검색축을 V4 RW domain에 연결하고 `term_dict_tools.py --validate`가 누락·잘못된 taxonomy ID를 검증하도록 보강했다. `data/term_dict.yaml` 자체는 수정하지 않았다.

검증:
- `python -m pytest -q tests/test_v4_schema.py tests/test_t3_v3.py` -> 16 passed
- `python term_dict_tools.py --validate --dict data/term_dict.yaml --v4-mapping data/v4_term_mapping.yaml` -> errors=0 (기존 공유 변이 경고 3건)
- `python init_v4_schema.py --out cs_index` -> taxonomy_nodes=43, taxonomy_aliases=168, clause_items=0, coverage=0

### 2026-07-16 세션 28 — V4-2 대표 10건 입력 준비 (Codex)

- 승인된 v3 60건 중 V4 전 항목 대상인 SPA·SSA·SHA·ATA/BTA에서 초안/체결본과 high/med/low 신뢰도가 섞이도록 대표 10건을 확정했다.
- `plan_v4_batch.py`를 추가해 v3에서 승인된 진술보장·선행조건·확약의 문단 범위만 `cs_index/enrich_inputs_v4`에 생성했다. 문서 전체를 다시 입력하지 않고 관련 조항 범위만 전달한다.
- 대표 표본은 SPA 3건, SSA 2건, SHA 3건, ATA/BTA 2건이다. 별도계약 참조가 있는 SHA, 영업양도 양식, 대형 체결 SPA, 공란 초안을 함께 포함해 경계사례를 우선 검증한다.
- `cs_index/v4_batch_01_manifest.json`과 초기 `t3_v4_audit_report.json`을 생성했다. 현재 V4 결과는 아직 작성 전이므로 pending 10, error 0이며 다음 작업은 원자 항목 추출과 사람 검수표 작성이다.

검증:
- `python plan_v4_batch.py --out cs_index` -> count=10
- `python audit_t3_v4.py ...` -> total=10, pending=10, error=0
### 2026-07-23 — V4-1R 세부 원자화·별지 전수평가 기반 구현 (Codex)

- 기존 V4 테이블을 삭제하지 않는 additive migration으로 `v4_clause_item`에
  `source_kind/source_id/source_name/source_ref/parent_clause_ref`를 추가하고,
  참조자료별 평가 상태를 저장하는 `v4_source_coverage`를 구축했다.
- taxonomy version을 2로 올리고 노무 세부 노드
  `RW.LABOR.NO_VIOLATION`, `RW.LABOR.WORKING_CONDITIONS`,
  `RW.LABOR.NO_OFF_BOOK_WAGES`, `RW.LABOR.UNPAID_COMPENSATION` 및 aliases를 seed했다.
- `plan_v4_batch.py`가 활성 taxonomy 정의·alias 전체, 본문 하위 단위 힌트,
  Schedule·Disclosure Schedule·별지·부속서·첨부 인벤토리와 실제 발견 범위를 입력에 포함한다.
- V3 위치가 제목이나 첫 하위조항에서 끝나더라도 다음 V4 family 시작 직전까지 Article 범위를
  확장한다. 국문 대표 SPA는 RW 614~980(367문단·64 단위), COV 981~1249
  (269문단·26 단위), CP 1250~1376(127문단·21 단위)로 재생성되어 대상회사 세부
  진술보장과 후속 확약이 입력에서 빠지지 않는다.
- `audit_t3_v4.py`가 자료별 coverage 누락, available 별지 미완료, non-leaf taxonomy 남용,
  미커버 원자 단위, 기존 alias와 중복되는 신규 후보를 검사한다.
- `store_v4_results.py`를 추가해 감사 `pass` 결과만 V4 테이블에 저장하고 `doc_meta`는 보존한다.
  사람 검토 결과는 `--allow-review` 없이는 저장하지 않는다.
- 실제 `cs_index/catalog.sqlite`를 schema revision `1R`, taxonomy 47노드·188 aliases로
  마이그레이션하고 대표 10건 V4 입력을 새 형식으로 재생성했다.
- 기존 데모 결과 2건은 `source_coverage`가 없는 구형 결과여서 새 감사에서 error로 분리했다.
  삭제하지 않았으며 V4-2에서 재추출한다.

검증:
- `python -m pytest -q` → 169 passed, 1 skipped
- `python init_v4_schema.py --out cs_index` → schema_revision=1R,
  taxonomy_nodes=47, taxonomy_aliases=188
- `python plan_v4_batch.py --out cs_index` → 대표 입력 10건 재생성
- `git diff --check` → 오류 없음(기존 Windows LF/CRLF 경고만 출력)

### 2026-07-23 — 한국·미국형 M&A 20건 V4 범위 재검토 (Codex)

- 국문 12건, 영문·국영문 8건의 SPA·SSA·SHA·ATA/BTA 및 독립 Disclosure Letter를
  층화 표본으로 선정해 V3 메타와 관련 조항·별지 범위를 부분 정독했다.
- 한국형 계약의 계약금·중도금·잔금·위약벌·대금배분·임직원 승계와 미국형 계약의
  Estimated/Final Purchase Price, NWC/debt/cash adjustment, escrow/holdback,
  disclosure schedules, Knowledge/MAE/Permitted Lien, efforts standard를 반복 검색축으로 확인했다.
- 검토 결과를 `.docs/V4_SCOPE_REVIEW_20_20260723.md`에 file_key 근거와 함께 기록했다.
- V4 범위를 `RW|CP|COV|DEF|PAY|REM`으로 확장하고, 정의·지급구조·위반구제에도
  원자 item·source coverage·통제 taxonomy를 적용하도록 `.docs/V4_PLAN.md`를 보강했다.
- 계약금 몰취처럼 복수 기능을 가지는 문구는 PAY/REM 양쪽 item으로 저장하고 연결하며,
  독립 Disclosure Letter/Schedule은 본계약 source로 연결하는 원칙을 확정했다.

### 2026-07-23 — 추가 100건 검토 및 V4-1R2 6-family 보강 (Codex)

- 기존 20건과 겹치지 않게 SPA·SSA·SHA·ATA/BTA 각 25건, 국문 52건·영문 48건을
  층화 선정했다. 체결/비초안 34건, 초안 33건, 판별불가 33건이며 같은 유형·언어 안에서
  동일 거래 계열의 여러 버전이 중복되지 않도록 정규화한 project key로 제한했다.
- `review_v4_scope_sample.py`를 추가해 표본 선정, 관련 문구의 제한된 근거 수집,
  재현 가능한 JSON/Markdown 보고서 생성을 자동화했다. 결과는
  `cs_index/v4_scope_review_100.json`과
  `.docs/V4_SCOPE_REVIEW_100_20260723.md`에 저장했다.
- 대표 문단 부분 정독으로 사이버보안·침해사고 [847d7467e106d64f], anti-sandbagging·
  배타적 구제 [e45d3402878d30f6], 이중배상·보험·조세혜택 차감 [4b65065b177cad18],
  R&W 보험·대위권 포기 [76fc85ad82adef8e], rollover [113536aa319e1e0f],
  payoff·담보해제 [847d7467e106d64f], TSA [1f0dc2031c3e3bf9]를 확인했다.
- schema revision을 `1R2`, taxonomy version을 3으로 올리고 runtime family를
  `RW|CP|COV|DEF|PAY|REM`으로 확장했다. 정의·대금·구제와 추가 100건에서 확인된
  한미형 세부 항목을 반영해 taxonomy를 148노드·572 aliases로 보강했다.
- SQLite의 기존 3-family CHECK는 직접 변경할 수 없어, V4 생성 데이터와 promoted node가
  모두 0일 때만 V4 계층을 재구축하는 guarded migration을 구현했다. 실제 DB는 조건을
  확인한 뒤 V4 계층만 재구축했으며 T1-T3 `files`·`doc_meta`는 보존했다.
- `v4_clause_item.item_ref/related_item_ref`를 추가해 payoff(PAY/COV/CP), 계약금(PAY/REM),
  Fraud(DEF/REM), R&W 보험(COV/REM) 같은 복수 기능 문구를 연결한다.
- `plan_v4_batch.py`가 definitions_json, consideration_json과 대금조정·earn-out·
  에스크로·손해배상·조세배상·해제 범위를 이용해 DEF/PAY/REM 입력도 생성한다.
  대표 10건 입력과 manifest를 schema revision 1R2/taxonomy version 3으로 재생성했다.
- 추출 프롬프트를 `v4-prompt-3`으로 올리고 6-family coverage, DEF/PAY/REM 원자화,
  `related_item_ref` 규칙을 추가했다.

검증:
- `python init_v4_schema.py --out cs_index` → schema_revision=1R2,
  taxonomy_nodes=148, taxonomy_aliases=572, V4 생성 데이터 0
- `python plan_v4_batch.py --out cs_index` → 대표 입력 10건 재생성, 6개 family 포함
- `python -m pytest -q tests/test_v4_schema.py tests/test_v4_1r.py tests/test_store_v4_results.py`
  → 17 passed

### 2026-07-23 — V4-1R2 국문 대표 1건 색인 테스트 (Codex)

- 국문 대표 SPA `[0ddde0e62bd84e41]`에 대해 RW·COV·CP·DEF·PAY·REM 6개
  family를 현재 V4-1R2 taxonomy로 다시 평가했다.
- 조항 범위 탐지에서 정의 조항, 손해배상·해제 조항 및 대금 조항이 중간에서
  잘리던 경우를 보정하고, Seller Draft·Purchaser comments 등 편집 흔적은
  원자 단위 힌트에서 제외했다.
- 총 205개 원자 item을 추출했다: RW 88, COV 30, CP 16, DEF 40, PAY 6,
  REM 25. 노무는 위반 없음, 근로조건 준수, 규정 외 임금 없음, 미지급 보수
  없음 등을 독립 taxonomy로 분리했다.
- 파일에 포함된 별지 1(주주·지분·매매대금 표)은 전체 평가해
  RW.CAPITALIZATION과 PAY.ALLOCATION으로 색인하고 관련 item을 상호 연결했다.
  실제 내용이 없는 매도인 공개사항과 별지 1의 3은 source coverage에서
  missing으로 명시했다.
- 감사 결과는 review 1건, item 205개, issues 0건이다. review 사유는
  taxonomy 후보 29개와 OCR 표·정의어 관련 needs_review 44개이다.
- 명시적 사람 승인 전 review 결과를 저장하지 않는 가드를 확인했다:
  stored 0, skipped 1.
- 결과 보고서: `.docs/V4_KO_REPRESENTATIVE_TEST_0DDDE0E6_20260723.md`

검증:
- `python audit_t3_v4.py ...` → review=1, item_count=205, issues=0
- `python store_v4_results.py ...` → stored_count=0, skipped_count=1
- `python -m pytest -q` → 170 passed, 1 skipped

### 2026-07-23 — 신규 M&A 계약 200건 검토 및 taxonomy v4 보강 (Codex)

- 기존 범위검토 120건과 겹치지 않는 SPA·SSA·SHA·ATA/BTA 200건을 새로
  층화 선정했다. 각 유형마다 국문 25건·영문 25건이며, 동일 유형·언어 안에서
  정규화된 거래 project 중복은 0건이다.
- 표본 상태는 체결/비초안 57건, 초안 72건, 판별불가 71건이고 영문 표본 중
  미국 법·규제 표지가 직접 검출된 문서는 54건이다.
- 기존 taxonomy 개념의 표현 근거를 전수 스캔한 뒤 38개 gap 후보를 추가
  점검했다. 36개는 반복 또는 미국형 특수 개념의 근거가 확인됐고,
  `PAY.MILESTONE`, `PAY.EARNOUT_ACCELERATION`은 0건이어서 승격하지 않았다.
- 대표 5건의 관련 조항만 부분 정독해 정의 안의 단순 권리명 열거와 실제 SHA
  운영권리, CP bring-down 중요성 기준과 REM materiality scrape, 매매대금
  원천징수와 배상금 tax gross-up을 구분했다.
- taxonomy version을 4로 올리고 36개 seed를 추가했다. 주요 보강 범위는
  매출채권·재고·지급능력·개인정보 준수, 장부보존·특권·보증해제·종결후협조,
  SHA tag/drag·ROFR/ROFO·put/call·reserved matters·이사지명·정보권·배당·
  lock-up·창업자 전념, 기업결합·주주승인·FIRPTA·good standing,
  양수/제외자산·승계/제외채무, materiality scrape·연대/개별책임·구상·
  기본진술 별도 cap·청구통지기한·배상금 tax gross-up이다.
- 추출 프롬프트를 `v4-prompt-4`로 보강해 SHA 권리 구성요소, 자산양수도
  포함·제외 범위, materiality scrape scope, 청구통지 효과와 gross-up 문맥을
  원자화하도록 했다.
- term_dict의 관련 canonical 검색축을 가장 구체적인 V4 노드에 연결하도록
  `v4_term_mapping.yaml`을 version 2/taxonomy version 4로 확장했다.
- 실제 `catalog.sqlite`는 schema revision 1R2를 유지하면서 taxonomy version 4,
  184 nodes, 732 aliases로 갱신했다. 기존 V4 clause item·coverage는 0건이어서
  사용자 검토 결과를 덮어쓰지 않았다.

산출물:
- `.docs/V4_SCOPE_REVIEW_200_20260723.md`
- `.docs/V4_SCOPE_GAPS_200_20260723.md`
- `cs_index/v4_scope_review_200.json`
- `cs_index/v4_scope_gaps_200.json`

검증:
- `python term_dict_tools.py --validate ...` → errors=0
- `python init_v4_schema.py --out cs_index` → taxonomy_version=4,
  taxonomy_nodes=184, taxonomy_aliases=732
- `python -m pytest -q` → 172 passed, 1 skipped

## 2026-07-23 — V4 잔여 651건 검토·taxonomy v8·운영 적재 완료

- 앞서 검토한 20+100+200건과 절반 표본 652건을 제외한 정확한 보완집합
  651건을 확정했다.
- 사용자 요청에 따라 file_key 고정 순서로 1차 300건, 2차 351건을
  비중복 배치로 검토했다.
- 기존 49개 후보와 신규 세분화 후보 65개를 로컬 원문 캐시에서 검사하고,
  대표 문단 문맥과 기존 taxonomy 중복을 확인했다.
- 문맥 오탐과 기존 노드 중복을 제외하고 taxonomy v8에 43개 노드
  (상위 `RW.IT` 1개, 검색용 원자 leaf 42개)를 추가했다.
- taxonomy 누적은 369 nodes / 1,390 aliases다.
- 확정 근거 42 items / 26 documents를 `review_status=approved`,
  관련 family `body_status=partial`, `annex_status=not_evaluated`로
  운영 DB에 적재했다.
- 운영 V4 누적은 209 items / 60 documents이며 approved 209개다.
- 감사 결과 pass=26, review=0, error=0, stored=26, skipped=0이다.

주요 세분화:
- `RW.IT.SYSTEMS_SUFFICIENCY`, `RW.IT.DISASTER_RECOVERY`
- `COV.RWI.PROCUREMENT|MAINTENANCE|SUBROGATION_WAIVER`
- `COV.TAX.CONSISTENT_REPORTING|AUDIT_CONTROL|TRANSFER_TAX`
- `REM.THIRD_PARTY_CLAIMS.DEFENSE_CONTROL|SETTLEMENT_CONSENT|COOPERATION`
- `REM.INDEMNITY.RW_BREACH|COVENANT_BREACH|TAX|EXCLUDED_LIABILITIES`
- `REM.CONSEQUENTIAL.LOST_PROFITS|DIMINUTION_IN_VALUE|MULTIPLE_BASED`
- `PAY.HOLDBACK`, `PAY.EARNOUT.DISPUTE`, `PAY.ESCROW.RELEASE`

산출물:
- `.docs/V4_REMAINING_REST_REVIEW_20260723.md`
- `cs_index/v4_remaining_rest_review.json`
- `cs_index/v4_remaining_rest_node_update.json`
- `cs_index/v4_remaining_rest_confirmed_manifest.json`
- `cs_index/v4_remaining_rest_confirmed_audit.json`
- `cs_index/v4_remaining_rest_confirmed_store_audit.json`

검증:
- `python -m pytest -q` → 172 passed, 1 skipped
- `python eval_search.py --out cs_index --json` → fail 0, pass 6
- `python term_dict_tools.py --validate --out cs_index` → errors 0

### 2026-07-23 — 색인 업데이트 전달·운영 프로토콜 문서화

- 신규 계약서와 기존 운영 DB를 다음 세션 또는 새 환경에 전달해 현재 V4
  기준으로 증분 업데이트할 수 있도록 `색인 업데이트 설명서.md`를 작성했다.
- 계약서 본문·별지·Disclosure Schedule, 전체 `cs_index` 전달을 기본으로 하고,
  DB만 전달할 때의 한계와 SQLite WAL 복사 주의사항을 명시했다.
- 기존 taxonomy만 사용하는 방식, 신규 taxonomy 판단까지 위임하는 방식,
  후보를 먼저 검토한 뒤 적재하는 방식별 요청 문구를 제공했다.
- 패키지 무결성 확인, 백업, 증분 색인, 별지 인벤토리, V4 원자화, taxonomy
  후보 판정, 감사, 운영 DB 적재, 회귀검사 순서와 완료 보고 항목을 정리했다.
- 기준이 세션 기억에만 의존하지 않도록 `AGENTS.md`, V4 prompt, schema,
  감사기, term mapping 등 새 환경에 함께 전달할 기준 파일 목록을 포함했다.

### 2026-07-23 — V4-2 대표시험 131개 item 소유자 승인·적재 (Codex)

- 소유자 지시에 따라 `[0ba3a1b8246c5dd5]`의 V4-2 결과 131개를 모두
  `review_status=approved`로 전환했다.
- 재감사 결과 pass 1건, issues 0건을 확인한 뒤 운영
  `v4_clause_item`에 131개, `v4_document_coverage`에 6개 family,
  `v4_source_coverage`에 별지·공개목록 2개 source를 적재했다.
- 적재 분포는 body 19개, annex 102개, disclosure_schedule 10개이고,
  본문·별지·공개예외를 잇는 `related_item_ref`는 11개다.
- RW coverage는 body/annex 모두 complete이며, 이번 V4-2 범위 밖의
  CP·COV·DEF·PAY·REM은 not_evaluated로 명시해 부재와 혼동되지 않게 했다.
- `cs_index/v4_v2_trial_store_audit.json`에 저장 감사 결과를 남겼고
  `.docs/V4_V2_TRIAL_0BA3A1B8_20260723.md`도 운영 적재 상태로 갱신했다.

### 2026-07-23 — 미검토 주요 M&A 계약 절반 652건 검토·taxonomy v7 보강 (Codex)

- 기존 검토 320건을 제외한 검색가능 `SPA|SSA|SHA|ATA/BTA` 1,303건 중
  유형·언어 비율을 유지한 절반(올림) 652건(50.04%)을 선정했다.
  SPA 295건, SSA 147건, SHA 143건, ATA/BTA 67건이며 국문 422건,
  영문 223건, 국영문 7건이다.
- 652건의 추출 문단 전체를 49개 미보유 원자개념 후보로 로컬 스캔했다.
  42개 후보가 검출되었고, 대표 문단 부분 정독으로 정의·목차·단순 열거와
  기존 taxonomy 중복을 제거한 뒤 36개를 taxonomy version 7로 승격했다.
- 추가 노드는 RW 9, CP 3, COV 8, DEF 5, PAY 4, REM 7개다. 주요 예시는
  경쟁법·관세·이민법·금융약정·보조금 환수·정부계약·도메인·부동산 용도/
  수용, 핵심인력·에스크로·반대주주 주식매수청구권 조건, 개인정보 시정·
  standstill·비방금지·조세환급·SHA 등록권/의결권위임/정족수/캐스팅보트,
  회계원칙·데이터룸·공개목록·종결순차입금·목표운전자본, 마일스톤·주식대가·
  정산기한·언아웃 보증, 공제형/소급형 basket·징벌손해·취소권포기·
  에스크로 한정구제·청구대표자·배상재원 순서다.
- `CP.STOCK_EXCHANGE_APPROVAL`, `CP.DATA_ROOM_DELIVERY`,
  `COV.LITIGATION_COOPERATION`, `COV.IT_MIGRATION`,
  `PAY.PRICE_ADJUSTMENT_COLLAR`,
  `RW.CORPORATE_GOVERNANCE.NO_POWER_OF_ATTORNEY`는 오탐 또는 기존 노드
  중복으로 승격하지 않았다.
- taxonomy는 version 6의 290 nodes/1,002 aliases에서 version 7의
  326 nodes/1,171 aliases로 증가했다. 추출 프롬프트도 `v4-prompt-7`로
  올려 basket, SHA 운영규칙, 대금·정의, 구제재원 세분화 규칙을 반영했다.
- 사용자의 운영 DB 적재 요청에 따라 명확한 근거 36개 item/33개 문서를
  `review_status=approved`, 해당 family `body_status=partial`,
  `annex_status=not_evaluated`로 저장했다. 감사 pass 33, issues 0,
  stored 33, skipped 0이다.
- 전체 운영 V4 item은 대표계약 131개를 포함해 167개/34개 문서이며 전부
  approved다. partial 문서는 부재검색 근거로 사용하지 않는다.

산출물:
- `.docs/V4_REMAINING_HALF_REVIEW_20260723.md`
- `cs_index/v4_remaining_half_review.json`
- `cs_index/v4_remaining_half_node_update.json`
- `cs_index/v4_remaining_half_confirmed_manifest.json`
- `cs_index/v4_remaining_half_confirmed_audit.json`
- `cs_index/v4_remaining_half_confirmed_store_audit.json`

검증:
- `python term_dict_tools.py --validate --out cs_index` → errors=0
- `python eval_search.py --out cs_index --json` → fail=0
- `python -m pytest -q` → 172 passed, 1 skipped

### 2026-07-23 — V4-2 RW 세분화 및 신규 국문 SPA 대표시험 (Codex)

- 누적 범위검토 320건(20+100+200)의 관련 문단을 로컬 규칙으로 재점검해
  RW 표준 하위명제 82개의 실제 표현 근거를 확인했다. 권한·자본구조·재무·
  자산·계약·소송·조세·IP·환경·보험·인허가·부동산·복리후생·제품·
  고객/공급업체·특수관계인·브로커·개인정보 영역을 taxonomy version 5에
  82개 leaf로 추가했다.
- 기존 국문 대표와 다른 체결본 SPA `[0ba3a1b8246c5dd5]`를 선정했다.
  본문 제5.1조의 진술보장뿐 아니라 별지 5.1(8) 대상회사 진술보장
  (¶259~¶284)과 그 공개목록 세부자료(¶285~¶304)를 모두 V4-2 입력에 포함했다.
- 대표계약에서 매출채권 발생·회수·대손충당금·제한부담, 재고 판매가능성·
  수량 적정성·평가, 차임 지급·임대차보증금 회수, 인허가 분쟁, 세무장부,
  세법상 거주자, 거래추가조세 부재, 일반 법규준수, 제공정보의 정확성·누락,
  공동인력 등의 독립 명제를 추가 확인해 taxonomy version 6에 24개 노드
  (구조노드 2개 포함)를 더했다.
- taxonomy는 184개/732 aliases에서 누적 320건 보강 후 266개/896 aliases,
  대표시험 반영 후 290개/1,002 aliases가 되었다. RW 노드는 41개에서
  123개, 최종 147개로 확장됐다.
- 대표계약은 총 131개 RW 원자 item으로 추출했다: 본문 19개, 진술보장 별지
  102개, 공개목록 10개. 94개 서로 다른 최하위 taxonomy 노드를 사용했다.
- 공개목록의 개인정보 동의·파기·보호조치 미이행, 외국인 근로자 보험 미가입,
  공동인력, 산업안전보건 조치 미이행, 환경책임보험 미가입을 해당 본문/별지
  진술보장 item과 `related_item_ref`로 연결하고 반대 극성과
  `disclosure_exception` qualifier로 표시했다.
- 감사 결과는 pass 1건, item 131개, issues 0건이다. 소유자 검수 전이므로
  모든 item은 `review_status=pending`으로 두고 운영 `v4_clause_item`에는
  적재하지 않았다.

산출물:
- `.docs/V4_V2_TRIAL_0BA3A1B8_20260723.md`
- `cs_index/enrich_results_v4_v2_trial/0ba3a1b8246c5dd5.json`
- `cs_index/v4_v2_trial_node_update.json`
- `cs_index/v4_v2_trial_audit.json`
- `cs_index/rw_leaf_gaps_320.json`

검증:
- `python audit_t3_v4.py ...` → pass=1, item_count=131, issues=0
- `python term_dict_tools.py --validate --out cs_index` → errors=0
- `python -m pytest tests/test_v4_schema.py tests/test_v4_1r.py tests/test_store_v4_results.py -q`
  → 18 passed
- `python -m pytest -q` → 172 passed, 1 skipped

### 2026-07-23 — V4-2 나머지 9건 taxonomy v8 사전분류 (Codex)

- 승인·적재된 국문 SPA `[0ba3a1b8246c5dd5]`가 기존 대표 표본의
  `[0ddde0e62bd84e41]`를 대체하도록 하여, 전체 유형 분포 SPA 3·SSA 2·SHA 3·
  ATA/BTA 2를 유지하는 나머지 9건을 확정했다.
- `plan_v4_batch.py`로 10건 입력을 taxonomy v8·369노드 기준으로 재생성했다.
  manifest의 고정된 taxonomy v4 표기도 실제 version을 사용하도록 수정했다.
- `propose_v4_remaining_nine.py`를 추가해 canonical·alias가 원문에 직접 일치하는
  명제만 보수적으로 제안하고, 미분류 atomic unit은 문맥·taxonomy 검토 후보로
  보존하도록 했다. 유료 API와 운영 DB 쓰기는 사용하지 않는다.
- 9건에서 사전분류 item 528개와 검토 후보 451개를 만들었다. 모든 item은
  `needs_review`, 본문·별지 coverage는 `partial/not_evaluated`로 유지했다.
- 감사 결과는 review 9, error 0이며, 이슈 75건은 제공된 별지 source를 사람
  전수검토 전이므로 complete로 올리지 않은 `available_source_not_complete`뿐이다.
  후보 원문·좌표 불일치는 0건이다.
- 운영 DB는 기존 209 item·60문서, taxonomy v8 369노드로 변경하지 않았다.

산출물:
- `.docs/V4_BATCH_02_PRE_REVIEW_20260723.md`
- `cs_index/v4_batch_02_pre_review_manifest.json`
- `cs_index/enrich_results_v4_batch_02_pre_review/`
- `cs_index/v4_batch_02_pre_review_audit.json`

검증:
- `python -m pytest tests/test_propose_v4_remaining_nine.py tests/test_v4_schema.py tests/test_v4_1r.py -q`
  → 19 passed
- V4 감사 → review 9, error 0, 후보 원문·좌표 불일치 0

### 2026-07-24 — V4-2 나머지 9건 최종 문맥검수·taxonomy v11·운영 적재

- 사전분류 529개 item과 450개 후보를 원문 문맥으로 재검수했다. family 범위
  중복, 정의어 incidental match, 본문과 겹친 annex range를 제거하고 원문
  atomic hint를 다시 확인해 최종 861개 원자 item으로 확정했다.
- 최종 분포는 DEF 245, COV 222, RW 163, REM 142, CP 53, PAY 36이며
  120개 서로 다른 leaf를 사용한다. 미해결 taxonomy 후보는 0개다.
- 사전 제안에서 누락됐던 `[973d43e89040fb57]`의 `해당 인수대상자산`과
  `해당 인수대상채무` 정의를 atomic hint 재검수로 복구해
  `DEF.PURCHASED_ASSETS`, `DEF.ASSUMED_LIABILITIES`로 저장했다.
- 별지·Schedule·Exhibit 64개 고유 source를 추적했다. family-source 기준
  115행 중 제공된 114행은 complete이고, 코퍼스에 없는
  `[a51842fc51010f69]`의 Seller Disclosure Schedule 1행은 추정하지 않고
  missing으로 보존했다.
- 반복적으로 확인된 신규 검색축을 taxonomy v9-v11에 19개 leaf로 추가했다.
  주요 범위는 계약별 정의용어, 계약상 양도제한·허용양도, 거래비용 부담,
  종결절차, 제3자 보증·담보 부재, arm's-length 계약, 준거법·관할·완전합의·
  서면변경·누적구제·효력발생일, 일반 정부승인과 일반 Debt 정의다.
- taxonomy는 v8 369 nodes/1,390 aliases에서 v11 388 nodes/1,498 aliases로
  증가했다. 감사에서 확인된 비말단 `CP.GOVERNMENT_APPROVAL`, `DEF.DEBT`
  직접사용은 각각 `.GENERAL` leaf로 교정했다.
- 최종 V4 감사 결과 9건 전부 pass, review/pending/error 0이었다. 운영 DB에
  9건을 모두 저장해 누적 1,070 items/69 documents가 되었고, coverage 414행,
  source coverage 117행, taxonomy candidate 0건이다.
- 저장 전 `catalog.pre_batch02_store_20260724.sqlite`와 taxonomy v9/v10/v11
  단계별 SQLite 백업을 생성했다.

산출물:
- `.docs/V4_BATCH_02_FINAL_20260724.md`
- `finalize_v4_remaining_nine.py`
- `tests/test_finalize_v4_remaining_nine.py`
- `cs_index/v4_batch_02_final_manifest.json`
- `cs_index/enrich_inputs_v4_batch_02_final/`
- `cs_index/enrich_results_v4_batch_02_final/`
- `cs_index/v4_batch_02_final_audit.json`
- `cs_index/v4_batch_02_store_report.json`

검증:
- `python audit_t3_v4.py ...` → pass 9, review/pending/error 0
- `python term_dict_tools.py --validate --out cs_index` → errors 0, warnings 3
- `python eval_search.py --out cs_index --json` → fail 0
- `python -m pytest -q` → 179 passed, 1 skipped

### 2026-07-24 — V4-3 60건 파일럿·taxonomy v12·운영 후보 큐

- 기존 대표 10건과 부분평가 모집단 59건 중 유형·언어 비율로 선정한 50건을
  합쳐 정확히 60건의 파일럿 코호트를 구성했다. 추가 50건은 모두 현재
  `doc_meta`와 txt 캐시를 사용했으며 유료 API는 호출하지 않았다.
- 목차 좌표를 실제 조항으로 오인하던 문제를 교정했다. 영문 ARTICLE/목차 재현
  위치와 국문 6-family 실제 표제를 기준으로 본문 범위를 다시 잡고,
  Schedule·Annex·Exhibit·Disclosure Schedule을 별도 source inventory로
  추적하도록 `run_v4_pilot_60.py`를 구현했다.
- 추가 50건에서 확정 원자 item 2,500개를 생성했다. family 분포는 DEF 1,209,
  RW 528, REM 269, CP 224, COV 172, PAY 98이다.
- 사전 후보 1,583개 중 1,393개(88.0%)를 기존 taxonomy 또는 보강 규칙으로
  해소했다. 남은 190개는 승인 item과 섞지 않고 pending 후보 큐에 저장했다.
  후보 발생률은 `190 / (2,500 + 190) = 7.1%`이고 33개 문서에 남아 있다.
- 반복 명제를 근거로 매수인 자금충분성·독자조사·비의존·기타 진술보장 부인,
  선행조건 면제·자초 실패·연계거래 종결·대금조정 완료, 언아웃 지급구조를
  taxonomy v12에 추가했다. 구조 부모를 포함해 10개 노드가 늘어
  398 nodes/1,561 aliases가 되었다.
- source coverage는 complete 134행, missing 59행이다. missing 59행은 13개
  문서의 참조자료가 코퍼스에 없거나 참조만 있는 경우로, 내용을 추정하지 않고
  부재검색 근거에서도 제외했다.
- V4 감사는 total 50, pass 17, review 33, pending/error 0, 구조 issue 0이다.
  사용자의 운영 적재 지시에 따라 확정 item과 후보를 분리한 채 50건을 모두
  저장했다. 운영 DB는 3,502 items/69 documents, pending candidates 190개다.
- 저장 전 `catalog.pre_v4_pilot60_store_20260724.sqlite`를 생성했다. SQLite
  integrity check는 ok, foreign-key violation은 0이다.

산출물:
- `.docs/V4_PILOT_60_20260724.md`
- `run_v4_pilot_60.py`
- `tests/test_run_v4_pilot_60.py`
- `cs_index/v4_pilot60_cohort_manifest.json`
- `cs_index/v4_pilot60_final_manifest.json`
- `cs_index/enrich_inputs_v4_pilot60_final/`
- `cs_index/enrich_results_v4_pilot60_final/`
- `cs_index/v4_pilot60_final_audit.json`
- `cs_index/v4_pilot60_store_report.json`

검증:
- V4 감사 → pass 17, review 33, pending/error 0, 구조 issue 0
- 운영 저장 → stored 50, skipped 0, `allow_review=true`
- `python eval_search.py --out cs_index --tiers T1,T2 --json` → fail 0
- `python -m pytest -q` → 185 passed, 1 skipped

다음 단계:
- V4-4 UI-5 taxonomy 관리 화면에서 현재 후보 190개를 반복 문구·family·근접
  taxonomy별로 묶고, 기존 노드 귀속·신규 leaf 승격·기각을 일괄 처리한다.

### 2026-07-24 — V4-4 UI-5 taxonomy 후보 관리

- `/taxonomy` 관리 화면과 후보 관리 API를 구현했다. 운영 pending 후보
  190개는 정규화 문구·family·근접 노드 기준 179개 묶음으로 표시된다.
- 같은 family의 여러 묶음을 선택해 (i) 기존 leaf 귀속, (ii) 신규 leaf 승격,
  (iii) 사유를 남긴 기각을 일괄 실행할 수 있다.
- 신규 승격은 canonical ID·부모·국영문 이름·정의·alias를 검증하고 taxonomy
  version을 1 증가시킨다. 이미 item이 직접 귀속된 leaf를 부모로 바꾸거나
  다른 family에 귀속하거나 기존 alias와 충돌시키는 작업은 거부한다.
- `v4_taxonomy_action_log`를 추가해 action, candidate ID 목록, target,
  payload·사유, UTC 시각을 기록한다. 후보 원문·file_key·¶좌표는 삭제하지 않는다.
- 모든 쓰기는 `BEGIN IMMEDIATE` 트랜잭션이며 이미 처리된 후보의 재처리는
  HTTP 409로 차단한다. 운영 앱의 실제 후보는 누르지 않아 pending 190,
  action log 0건을 유지했다.
- 실제 로컬 서버에서 `/taxonomy` HTTP 200, taxonomy v12, 179 clusters /
  190 candidates를 읽기 확인했다. 연결 가능한 브라우저 인스턴스가 없어
  화면 캡처 기반 시각 QA는 수행하지 못했고, HTML 응답·JS 구문·임시 DB
  서비스/웹 통합 테스트로 처리 경로를 검증했다.

산출물:
- `.docs/V4_TAXONOMY_UI_20260724.md`
- `taxonomy_admin.py`
- `static/taxonomy.html`
- `static/taxonomy.css`
- `static/taxonomy.js`
- `tests/test_taxonomy_admin.py`
- `tests/test_taxonomy_web.py`

검증:
- taxonomy 서비스·웹·스키마 관련 테스트 → 38 passed
- `node --check static/taxonomy.js` → 통과
- 운영 DB 읽기 확인 → v12, pending 190, action log 0
- `python -m pytest -q` → 192 passed, 1 skipped

다음 단계:
- V4-5 CLI·웹·MCP 검색에서 atomic taxonomy 조건을 노출하고 세부 골든 질의로
  v3+부분정독 대비 recall·정독 문서 수를 비교하는 게이트 B를 실행한다.

### 2026-07-24 — V4-5 원자 명제 검색·Gate B 예비 평가

- `v4_search.py`를 공통 읽기 전용 서비스로 구현했다. taxonomy ID/canonical/alias
  정규화, 하위 노드 포함 검색, polarity·주체·시점·유형·언어 필터, 원문과 ¶ 좌표,
  본문·별지 source 및 최신성 표시를 지원한다.
- 부재 판정은 본문 complete + 별지 complete/no_annex + 현재 해시 + source
  complete/current + 해당 family pending 후보 없음 조건을 모두 만족한 경우만
  `confirmed_absent`로 반환한다. 그 밖의 미검출 문서는 사유가 있는
  `needs_review`로 분리한다.
- 기존 `search_contracts.py`에 `--item`, `--item-absent`, `--polarity`,
  `--subject`, `--time`, `--exact-item`을 추가했다. 독립 CLI는 2~10개 계약 비교도
  지원한다.
- `/v4-search` 화면과 `POST /api/v4/items/search`,
  `POST /api/v4/items/compare`를 추가했다. taxonomy 선택지는 DB에서 동적으로
  읽고 결과 카드에 match path·coverage·원문 좌표를 표시한다.
- `v4_mcp_tools.py`는 기존 도구를 변경하지 않고 `search_clause_items`,
  `compare_clause_items`를 등록하는 읽기 전용 어댑터다.
- family별 존재 24, 부재 6, 비교 6의 총 36개 예비 골든 질의를 만들었다.
  현재 승인 V4 item을 reference로 한 결과는 구조화 recall 1.0000, legacy
  정확구문 후보 recall 0.3748, 정독 필요 문서 누적 24,647→12,422(49.6% 감소),
  측정 조회시간 합계 1,163.073→466.066ms였다. 36개 모두 scored였다.
- 이 평가는 독립 사람 검수 골드가 아니라 승인 item 기반 회귀이므로 Gate B의
  기능 경로는 통과하되 Gate A 완전성 통과로 보지 않는다. pending 후보 190개와
  missing source 59개는 계속 부재 판정에서 제외된다.

산출물:
- `.docs/V4_SEARCH_GATE_B_20260724.md`
- `data/v4_gate_b_golden.json`
- `eval_v4_gate.py`
- `v4_search.py`, `v4_search_web.py`, `v4_mcp_tools.py`
- `static/v4-search.html`, `static/v4-search.css`, `static/v4-search.js`
- V4-5 테스트 5개 파일

검증:
- V4-5 대상 테스트 13 passed
- `node --check static/v4-search.js` 통과
- 실제 로컬 HTTP 검색 200 및 국문 원자 item 1건 확인
- `python -m pytest -q` → 205 passed, 1 skipped

다음 단계:
- V4-6에서 SPA→SSA→SHA→ATA/BTA 순으로 제한 배치를 확장한다. Gate A가 아직
  미통과이므로 missing source와 pending taxonomy 후보는 계속 `needs_review`로
  보존하고, 유형별 평가 회귀를 함께 기록한다.

### 2026-07-24 — V4-6 확장 배치 01(SPA 300건)

- 미평가 core 계약 1,554개 중 SPA 300건(국문 196, 영문 104)을 중복 대표
  기준으로 선택했다.
- 승인 원자 item 13,389개와 pending taxonomy 후보 1,396개를 생성했다.
  감사 결과 pass 62, review 238, pending/error 0, 구조 issue 0이었다.
- WAL-safe 백업 후 300건을 운영 DB에 적재했다. 누적 V4 item 16,891개,
  평가 문서 369개, pending 후보 1,586개이며 integrity ok/FK violation 0이다.
- 500건을 넘는 결과의 Gate B recall 계산 오류를 찾아 V4 검색과 MCP·웹에
  pagination을 추가했다. 전체 페이지 재평가 결과 V4 recall 1.0000,
  legacy 0.3430, 원문 정독 필요량 53.85% 감소, T1/T2 fail 0이다.
- 전체 회귀는 208 passed, 1 skipped이다.

산출물:
- `.docs/V4_EXPANSION_01_20260724.md`
- `run_v4_expansion.py`, `tests/test_run_v4_expansion.py`
- `cs_index/v4_expansion_01_spa300_*` 및 final input/result

다음 단계:
- 다음 300건 전에 pending 후보 1,586개를 반복 문구별로 묶어 기존 node
  병합/신규 leaf 승격/기각하는 taxonomy 정리 배치를 수행한다.

### 2026-07-24 — V4-6 taxonomy v13 정리 배치

- 후보 병합·승격이 상태만 바꾸고 검색 item을 생성하지 않던 누락을 수정했다.
  schema revision 1R3에서 후보의 source/hash/version을 보존하고, 해결과
  `v4_clause_item` 생성을 하나의 트랜잭션으로 처리한다. 후보 1개를 여러 원자
  node로 분해하는 경로와 stale/source 검증도 추가했다.
- 처리 전 pending 1,586개 전부가 현재 txt 캐시의 해당 ¶ 원문과 일치했다.
- 300건 확장에서 반복 확인된 동시 전부종결, 매수인 지명 임원 선임,
  R&W 보험 발효, 개인보증, 특정 부채 정리, 규제기관 통지, 자금조달 비조건성,
  사해행위 위험 부재, 배상금의 대금조정 처리, 법령변경 손해 배제의 10개
  leaf를 추가해 taxonomy v13 408 nodes가 되었다.
- dry-run 후 고신뢰 후보 294개를 병합해 approved 원자 item 294개를 만들고,
  제목·리드인·편집주석 16개를 기각했다. 1,276개는 추측하지 않고 pending으로
  유지했다.
- 운영 V4 item은 17,185개다. 새 item은 원문 좌표 294/294 일치, stale 0,
  FTS row 수 일치, integrity ok, FK violation 0이다.
- Gate B는 36/36 scored, V4 recall 1.0000, legacy 0.3425, 정독 문서 수
  54.23% 감소다. T1/T2 fail 0, 전체 회귀 212 passed, 1 skipped다.

산출물:
- `.docs/V4_TAXONOMY_V13_20260724.md`
- `review_v4_candidates.py`, `tests/test_review_v4_candidates.py`
- `cs_index/v4_candidate_review_v13_dry_run.json`
- `cs_index/v4_candidate_review_v13_applied.json`

다음 단계:
- 차단 이슈가 없으므로 남은 pending은 보존한 채 taxonomy v13과 schema 1R3로
  다음 300건 확장 배치를 진행한다.

### 2026-07-24 — V4-6 확장 배치 02(SPA 추가 300건)

- 기존 평가 문서와 중복 대표를 제외한 eligible 1,254건에서 SPA 300건을
  추가 선정했다(국문 196, 영문 104).
- taxonomy v13·schema 1R3로 approved 원자 item 13,905개와 pending 후보
  1,203개를 생성했다. 후보율은 7.96%로 직전 배치 9.44%보다 낮아졌다.
- 감사 결과 pass 74, review 226, pending/error 0, 구조 issue 0이었다.
- WAL-safe 백업 후 300건을 운영 DB에 적재했다. 누적 item 31,090개,
  평가 문서 669개, pending 후보 2,479개이며 integrity ok, FK violation 0,
  FTS row 수 일치다.
- Gate B는 36/36 scored, V4 recall 1.0000, legacy 0.3445, 정독 문서 수
  58.98% 감소다. T1/T2 fail 0, 전체 회귀 212 passed, 1 skipped다.
- `run_v4_expansion.py` manifest의 schema revision 하드코딩을 제거하고
  현재 `V4_SCHEMA_REVISION`을 기록하도록 교정했다.

산출물:
- `.docs/V4_EXPANSION_02_20260724.md`
- `cs_index/v4_expansion_02_next300_*`

다음 단계:
- 다음 계약 배치 전에 Schedule·Annex·Disclosure Schedule 실질 문단이
  item 또는 명시적 pending 후보로 모두 보존되는지 완전성 감사를 수행한다.

### 2026-07-24 — V4 별지 물리 문단 완전성 교정·taxonomy v14

- 두 300건 배치의 Schedule·Annex·Exhibit·Disclosure Schedule을 물리
  `(storage file, ¶, 원문)` 단위로 감사했다. 기존 final review가 배치별
  6,354개·7,242개의 미표현 실질 문단을 남긴 채 source를 complete로 바꾸던
  조용한 누락을 확인했다.
- 물리 문단을 한 번만 전수검수해 분류 가능한 문단은 source item으로,
  나머지 실질 문단·표 행·None/없음은 source 좌표가 있는 pending 후보로
  보존하도록 pipeline을 교정했다. 후보가 남은 source와 연결 family는 모두
  partial로 유지한다.
- 기존 600건을 재선정 없이 재생성했다. 배치 01은 item 21,047/source item
  7,708/source 후보 3,847, 배치 02는 item 22,574/source item 9,520/source
  후보 4,114다.
- broad `RW.SOLVENCY` item을 새 leaf `RW.SOLVENCY.GENERAL`로 교정해
  taxonomy v14 409 nodes가 되었다.
- 운영 DB는 item 47,139/source item 17,712, pending 10,401/source pending
  7,961이다. source evidence 25,673건은 txt 좌표와 전부 일치하고,
  incomplete source를 complete로 표시한 사례는 0건이다.
- 문서 재저장 시 taxonomy 해결 item과 action log 연결을 반복 실행에도
  보존하도록 수정했다. resolution reference 294개 중 missing 0이다.
- integrity ok, FK violation 0, FTS row 일치. Gate B V4 recall 1.0000,
  정독 문서 수 56.69% 감소, T1/T2 fail 0, 전체 회귀 214 passed, 1 skipped다.

산출물:
- `.docs/V4_ANNEX_COMPLETENESS_20260724.md`
- `refinalize_v4_batch.py`
- `cs_index/v4_expansion_01_spa300_annex_*`
- `cs_index/v4_expansion_02_next300_annex_*`

다음 단계:
- 47,139 item에서 Gate 조회가 약 95초로 증가했으므로 전체 결과를 매 페이지
  재구성하는 방식을 SQL count/page pagination으로 바꾼 뒤 다음 배치로 간다.

### 2026-07-24 — V4 검색 성능 보강

- 중복 포함 검색은 SQL에서 전체 건수와 stale 건수를 집계하고 `LIMIT/OFFSET`으로
  필요한 페이지만 읽도록 변경했다.
- body·annex·source·taxonomy 후보 커버리지는 family 단위 일괄 조회로 바꾸고,
  부재 검색의 문서별 존재 여부도 단일 그룹 질의로 계산하도록 변경했다.
- Gate B 36/36 scored, V4 recall 1.0000, legacy recall 0.3343, 정독 문서
  56.69% 감소로 결과 의미와 정확도가 유지되었다.
- V4 게이트 누적 검색 시간은 별지 교정 직후 약 95,064ms에서 2,043ms로
  약 97.9% 감소했다.
- 전체 테스트는 214 passed, 1 skipped이다.

산출물:
- `.docs/V4_SEARCH_PERFORMANCE_20260724.md`
- `cs_index/v4_search_performance_gate.json`

다음 단계:
- 고신뢰 taxonomy 후보 정리를 수행하고, 사용자 개입이 필요하지 않으면 아직
  평가하지 않은 SPA 300건을 다음 확장 배치로 진행한다.

### 2026-07-27 — 프로젝트 전반 리뷰 · 저장소 위생 · progress 정리 (Claude, opus)

소유자 요청으로 계획·진행 전반을 검토하고 안전한 개선을 반영했다.

**검토 결과 (요지)**
- 코드 baseline은 건강함: `python -m pytest --basetemp=<scratch>` → **214 passed, 1 skipped**.
  기본 `python -m pytest`가 대량 `PermissionError`를 냈던 것은 코드 결함이 아니라
  `AppData\Local\Temp\pytest-of-<user>` 폴더 권한 문제(환경)였다. `--basetemp` 우회로 전량 통과 확인.
- **저장소 위생 문제**가 가장 컸다: `.backups/`(약 3.3GB DB 스냅샷), `contract_docs/`(약 861MB
  원본 코퍼스), 미정리 `.tmp_pytest_*/` 34개, `tmp_doc_convert_probe/`, `.vscode/`가 gitignore
  누락 상태로 작업트리에 노출돼 있었다(무심코 `git add -A` 시 수 GB 오커밋 위험).
- **완성됐지만 미커밋**인 산출물 다수 확인: MCP 서버·T3-V3 파일럿 도구·v3 구조화 검색 필터·
  도움말 페이지·DOCX 변경추적 색인·`--force` 재색인·GUI 색인 모드. 모두 테스트 통과 상태였다.

**반영한 개선**
- `.gitignore` 보강: `.backups/`, `contract_docs/`, `.tmp_pytest*/`, `tmp_*/`, `*.tmp`, `.vscode/` 제외.
- 재생성 가능한 임시물 삭제: `.tmp_pytest_*/`(34개), `tmp_doc_convert_probe/`.
- `progress.md` 재구성(1357→약 857줄): 상단에 **현재 상태 요약** 신설, Phase 0~3 상세 이력은
  [.docs/PROGRESS_ARCHIVE.md](.docs/PROGRESS_ARCHIVE.md)로 분리(정보 손실 없음). V4 이력은 그대로 유지.
- 미커밋 완성 작업을 기능별로 커밋(아래).

**의도적으로 하지 않은 것 (근거)**
- **루트 `.py` 47개의 하위 폴더 이동 보류**: 이 중 약 30개가 테스트에서 최상위 이름으로
  직접 import(`from v4_search import ...`)되고, CLAUDE.md/README가 `python <script>.py` 실행을
  계약으로 문서화하며, 코드가 `.docs/`의 특정 파일(extract_prompt_v2/v3/v4, yaml fallback,
  V4_BATCH_02_PRE_REVIEW)을 경로로 참조한다. 폴더 이동은 이 import·CLI·fallback을 모두 깨뜨려
  작동 중인 214개 테스트를 위험에 빠뜨리므로, 미관상 이득 대비 위험이 커 보류했다. 재구성을
  원하면 conftest sys.path + 전 import/문서 갱신 + 회귀 검증을 묶은 별도 작업으로 진행 권장.
- `.docs/` 하위 폴더 재분류도 위 코드 참조(fallback yaml·프롬프트 경로) 때문에 보류.
- `.backups/`(3.3GB)와 `cs_index/catalog.pre_*.sqlite` 스냅샷은 **삭제하지 않고** gitignore만 했다
  (의도적 안전 스냅샷·비가역). 디스크 회수가 필요하면 소유자가 직접 삭제하면 된다.

**커밋**
- `chore(repo): ignore heavy/temp artifacts; drop stray temp dirs`
- `feat(mcp): add read-only MCP server adapter and integration doc`
- `feat(t3): add T3-v3 pilot planning and manifest tooling`
- `feat(search): add v3 structured filters, help page, indexing improvements`
- `docs(progress): restructure progress.md with status summary + archive`

검증: `python -m pytest --basetemp=<scratch> -q` → 214 passed, 1 skipped (변경 후 재확인).
### 2026-07-27 — V4 증권계약 범위 확장·900건 본문 완전성 교정

- V4 전 항목 추출 범위를 SPA·SSA·ATA/BTA·SHA에서 CB인수(CBSA),
  CB매수(NPA), BW인수(BWSA), W매수(WPA), EB인수(EBSA)까지 확장했다.
- 기존 600건을 새 본문·별지 완전성 규칙으로 재처리하고, 증권계약을 실제
  포함한 새 300건(SPA 35, CB인수 121, CB매수 3, BW인수 34, W매수 1,
  EB인수 15, SSA 91)을 추가 적재했다.
- 뒤쪽 별지 Article의 본문 범위 오염, 장문 무힌트 본문 누락, 제목 미인식
  계약의 전체 미평가, 소송 부존재/중재합의 충돌, 별도 storage 별지 중복,
  후보 검토 item_ref 충돌을 수정했다.
- Exhibit·법률의견·closing checklist·schedule of exceptions·term sheet/TS·
  CPS/CB terms·series certificate·발행결정 공시를 계약 본체 표본에서 제외하고,
  SSA 폴더의 SHA/RFR·co-sale 파일은 SHA로 정규화했다.
- 운영 DB는 item/FTS 각 98,904개, coverage 968문서, pending 후보 31,083개,
  merged 295개, rejected 16개다. 전체 본문 미평가 0, 비말단
  `RW.SOLVENCY` 0, stale 0, resolution 참조 누락 0, integrity ok, FK 0이다.
- 구조 감사 세 배치 모두 error 0·좌표 누락 0. 전체 테스트 228 passed,
  1 skipped. V4 Gate B 36/36, recall 1.0000, 정독 문서 수 58.31% 감소,
  T1/T2 fail 0.
- 자동 후보 검토 dry-run에서 안전한 자동 병합·기각은 0건이어서 31,083개
  후보를 원문 좌표와 함께 유지했다. 다음 단계는 반복 후보 군집의 taxonomy
  검수·승격이다.
- 적재 전 WAL-safe 백업:
  `.backups/v4_scope_body_corrections_pre_store_20260727/cs_index_backup_20260727_155517`
- 상세 보고: `.docs/V4_SCOPE_EXPANSION_CB_BW_EB_20260727.md`

### 2026-07-27 — V4 taxonomy 반복 후보 군집 검수·v19 운영 반영

- pending 31,083건을 21,794개 정규화 군집으로 묶었고, 2건 이상 반복되는
  4,837개 군집(후보 14,126건)을 우선 검수했다.
- `REM.SEVERABILITY`, `REM.WAIVER`,
  `REM.NO_THIRD_PARTY_BENEFICIARY`, `REM.BINDING_EFFECT`,
  `REM.INDEMNITY.VOLUNTARY_ACT_EXCLUSION` 5개 leaf를 승격해 taxonomy v19,
  활성 노드 414개가 되었다.
- 정의·계열회사·손해 정의, 종료, 이중배상, 사기 예외, 특정이행, 징벌손해,
  일실이익, 준거법, 수정 등 고신뢰 후보 1,245건을 기존·신규 leaf로 병합해
  1,272개 원자 item을 적재했다. 이 중 body 55건은 실제 법적 기능에 맞춰
  명시적 교차 family 재분류를 수행했다.
- 신규 승격 직접 item 31개를 포함해 운영 DB는 item/FTS 각 100,207개다.
  후보 상태는 approved 31, merged 1,540, rejected 16, pending 29,807이다.
- Annex·Schedule의 교차 family 후보는 자동 재분류하지 않고 pending으로
  유지했다. 오탐 표본을 통해 분리가능성·제3자 수익자 배제·사기 예외·
  특정이행·자발행위 손해 제외 규칙을 조항 고유 문형으로 좁혔다.
- integrity ok, FK 0, stale 0, taxonomy/family 불일치 0, FTS row 일치,
  resolution reference 1,598건 중 missing 0이다. 적용 후 같은 규칙을 다시
  실행한 결과 추가 merge·item이 모두 0으로 멱등성도 확인했다.
- 전체 테스트 238 passed, 1 skipped. T1/T2 fail 0, V4 Gate B 36/36,
  recall 1.0000, 정독 문서 수 58.76% 감소다.
- Gate B V4 측정시간은 100,207 item 기준 약 20.3초로 반복 측정되어,
  다음 단계에서 SQL 실행계획·인덱스 성능을 재점검한다.
- 상세 보고: `.docs/V4_TAXONOMY_CANDIDATE_REVIEW_20260727.md`

### 2026-07-27 — 계획 궤적 리뷰 · 독립 Gate B seed (Claude, opus)

실제 `cs_index/catalog.sqlite`를 읽기전용 조회해 계획(V4_PLAN §9~§11)과 대조했다.
전문은 [.docs/PLAN_REVIEW_20260727.md](.docs/PLAN_REVIEW_20260727.md).

**실측 현황**: V4 item 100,207 / 평가문서 950(coverage 기준 ~968), taxonomy v19·414노드,
대상유형 진행 **782/1,623=48%**(SPA 98%·SSA 28%·SHA 1.9%·ATA/BTA 5.7% 쏠림),
부재 질의 가능 742/차단 567, pending 후보 29,807(서로 다른 이름 13,199종·사람처리 47).

**핵심 진단**
1. **Gate B가 자기참조**: V4 승인 item으로 질의를 만들어 recall이 구조적으로 항상 1.0 →
   "확장 가치" 판정 불가. Gate A 미통과인데 확장은 950문서까지 진행됨.
2. **후보 3만 개가 부재 질의를 43% 문서에서 차단**(coverage=partial). 문구 클러스터링으로
   일괄 처리 불가(13,199종), DEF 정의항 등 문서-특정 항목 과다생성이 근본 원인.
3. 유형 쏠림(SPA만 98%), 골든 세트 노후.

**이번 세션 산출물**
- `.docs/PLAN_REVIEW_20260727.md` — 진단 + 권고 시퀀스.
- `data/golden_queries_v4_independent.seed.yaml` — V4와 무관한 독립 Gate B seed
  (존재 8·부재 8·비교 6). 기대 답안은 소유자가 채워 active 전환.

**소유자 결정 필요**: (a) 후보 생성 기준·부재 차단 규칙 교정(DEF 문서-특정 항목 제외),
(b) 진짜 Gate B 결과에 따른 확장 계속 vs 축소판 전환, (c) 계획 외 유형 편입 정식화 여부.

### 2026-07-27 — pooled 독립 Gate B 구현 + 후보결함 진단 (Claude, opus)

소유자 결정(① Gate B 먼저·병행확장 중단, ② DEF 일반용어만 후보, ③ CB/BW/EB 편입)에 따라 진행.

- **pooled Gate B 구현**: `eval_v4_gate.py --pooled` 추가. 전수 라벨링 대신 두 방식
  (legacy FTS / V4 구조화)의 상위결과를 합친 pool만 소유자가 검증 → precision·상대재현율 산출.
  `--pool-depth`(기본 25)로 검증량 제한, `--worklist`로 미검증 항목 출력. 테스트 3건 추가(241 passed).
  seed 22개 질의에 taxonomy 바인딩 완료. pool-depth 25 기준 소유자 검증 대상 **총 834건**.
  초기 gap: V4E08(R&W보험)은 V4 검색 0건 vs legacy 790건.
- **항목 2 진단**: pending 29,807개 **전량 document_count=1**(자동갱신 미작동), DEF 후보는
  용어명이 아닌 위치(제N항)로 명명돼 재사용성 판별 불가 → 후보 생성 파이프라인 결함.
  빠른 패치 불가, 병행세션 중단 후 교정 A(용어명)→B(반복수 갱신) 단독 진행. 상세: `.docs/PLAN_REVIEW_20260727.md`.
- **항목 3**: CB/BW/EB는 V4_PLAN §6에 이미 반영됨(병행 세션).

다음: 소유자가 pool_verified 채운 뒤 Gate B 판정 / 후보 생성 교정(A→B) 단독 배치.

### 2026-07-27 — Gate B 부재형 flagship 전수 검증 완료 (Claude, opus)

독립 pooled Gate B의 부재형 8개 질의를 원문 대조로 전수 사람검증했다(검증값
`data/v4_gate_b_verdicts.json`, `eval_v4_gate.py --pooled`로 재현). 결과·권고 전문:
`.docs/V4_GATE_B_ABSENCE_FINDINGS_20260727.md`.

- **V4 부재정밀도 130/171 = 76%**(false absence 41건). family별 이봉분포:
  RW 진술계열 저조(조세 44%, 환경 50% — 흔한 진술 섹션을 절반 놓침), 특약·선행조건
  양호(제3자동의 92%, no-shop 91%, sandbagging 95%, 가격조정 80%, 경업금지 77%), 손배상한 67%.
- 결론: 부재 질의를 family 무차별 신뢰 금지. RW 진술계열 confirmed_absent는 needs_review로
  강등하고, V4 추출/coverage가 "Section 4.14 Tax Matters" 등 명백한 진술을 놓치는 원인을
  전량 확장 전에 조사해야 한다(PLAN_REVIEW의 coverage 결함 진단과 일치).
- 검증 도구: `verify_gate_b.py`(cards/apply-auto/set/ingest), 원문 대조로 자동 키워드
  플래그의 오탐(진술 속 언급을 확약으로 오인 등)을 교정. 존재형·비교형은 미완.

다음: RW family coverage 결함 원인 조사 / 존재형·비교형 검증(선택).

### 2026-07-27 — RW 진술 추출·coverage 결함 근본원인 규명 (Claude, opus)

Gate B 부재형의 RW 저조(조세 44%·환경 50%) 원인을 DB 직접 조회로 규명했다.
전문·권고: `.docs/V4_RW_COVERAGE_DEFECT_20260727.md`.

- **추출 범위 결함**: RW body='complete' 934문서 중 하위영역 item 0개 비율 —
  IP 98%(전 코퍼스 IP item 29개뿐), 노무 84%, 환경 68%, 조세 36%. 잘 추출된
  문서(RW 16+)에서도 IP 97%·노무 78% 누락 → thinness 아닌 하위영역 선택적 누락.
  taxonomy엔 RW.IP.* 노드가 있으므로 분류가 아니라 추출 문제.
- **coverage 과표기**: RW coverage 962행 중 933행이 동일 "V4-2 본문 검수 완료"로
  일괄 complete. 하위영역별 완전성 검증 없음 → complete가 추출 완전성과 무관.
- 메커니즘: 부재판정이 (body complete)+(item 없음)이면 confirmed_absent인데, RW는
  전자가 항상 참(도장)·후자가 추출누락으로 참 → 진술이 있어도 "없음" 확정.
- 권고: (즉시) search_clause_absence에서 RW family는 confirmed_absent 금지·needs_review
  강등. (근본) 하위영역 체크리스트 강제 재추출 + 영역별 완전성 감사로 complete 재정의,
  전량 확장보다 우선.

다음: 즉시 안전장치(RW 부재→needs_review) 구현 여부는 소유자 승인 후. 근본 재추출은 별도 배치.

### 2026-07-28 — 즉시 안전장치: RW 부재판정 강등 구현 (Claude, opus)

`.docs/V4_RW_COVERAGE_DEFECT_20260727.md`의 즉시 권고를 구현했다(소유자 승인).
`v4_search.search_clause_absence`에서 `ABSENCE_UNVERIFIED_FAMILIES={"RW"}` family는
coverage='complete'여도 `confirmed_absent`를 반환하지 않고 전부 `needs_review`로 강등하고
사유 `rw_coverage_unverified` + 경고 `rw_absence_unverified_demoted_to_needs_review`를 붙인다.
특약·선행조건 family(COV/CP/PAY/REM)는 Gate B에서 90%대라 그대로 유지.

- 실측 확인: RW.TAX·RW.ENVIRONMENT는 confirmed_absent 0(전부 needs_review),
  CP.THIRD_PARTY_CONSENT 241·COV.NON_COMPETE 292는 정상 유지.
- CLI(`--item-absent`)·웹·MCP 모두 dict 경유로 경고 전파. 테스트 픽스처에 CP family를
  추가해 비-RW confirm 경로를 검증. 전체 248 passed, 1 skipped.
- 남음: 근본 교정(RW 하위영역 체크리스트 재추출 + 영역별 coverage 감사)은 별도 배치.

### 2026-07-28 — ②-honesty: RW coverage 감사 도구 + 재추출 대상 식별 (Claude, opus)

근본 교정 ②의 "coverage 정직화" 절반을 구현했다. `audit_rw_coverage.py`:
CORE_RW_SUBDOMAINS(조세·소송·준법·중요계약·노무·IP·환경·인허가·재무·자산·부동산·보험)
체크리스트로 RW-complete 문서를 감사. report(기본, 읽기전용) / --apply(complete→partial,
사유 rw_subdomain_audit_pending, WAL-safe 백업 후).

- 실측: RW-complete 934 중 **733(78%)이 under-extracted**(core<6), 169개는 실질진술 0개.
  도메인별 문서 커버리지: 소송 69%·조세 63%·재무 51% vs IP 1.8%·보험 0.2%·자산 0.9%·노무 16%.
  = 추출이 앞부분 boilerplate 진술만 잡고 실질 사업진술을 누락한 패턴 재확인.
- --apply(733행 partial 강등)는 쿼리 게이팅으로 이미 안전하므로 재추출 착수 시 실행하도록 보류.
- 재추출(②-2, 누락 진술 실제 추출)은 AI 클라이언트 파일 하네스 배치(유료 API 없이). 별도 진행.

다음: Gate B 존재형·비교형을 전문 확인 방식으로 마저 검증.

### 2026-07-28 — Gate B 종합 + §9 확장/축소 결정 권고 (Claude, opus)

부재형 전수 + 존재형 표본 검증 + RW 근본원인을 §9 결정으로 종합했다.
전문: `.docs/V4_GATE_B_SYNTHESIS_20260728.md`.

- 존재형 표본(E03 경업금지 V4 고유 finds 14): 7건 실제 확약(legacy 상위25 밖 → V4 실질 추가),
  7건 진술을 확약으로 오분류(정밀도 노이즈). V4E08 RWI는 V4 검색 0건(추출 전무).
- **§9 판정: 전량 확장 중단 · 축소판 전환 + 추출 교정 선행.** V4 하이브리드는 recall 일관
  우위가 없음(과소추출 RW계열은 열위, 잘 추출된 특약·대금계열만 경쟁력). 현재 파이프라인
  확장은 추출 결함을 전 코퍼스로 복제하므로 중단하고, ② 재추출·coverage 교정을 먼저 한 뒤
  Gate B 재측정. 폐기가 아니라 교정 후 재평가.
- 권고: (1)확장중단 (2)RW 재추출+coverage 감사 (3)신뢰 family만 축소 운영(RW부재 게이팅 완료)
  (4)rep→covenant 오분류 시정 (5)T4 계속 보류.

다음: ② 재추출 파일럿(누락 진술 실제 추출 시연) 또는 소유자 검토 대기. 결정 권고는 소유자 몫.

### 2026-07-28 — §9 권고 승인·착수: coverage 정직화 적용 (Claude, opus)

소유자가 §9 권고를 승인. 권고대로 진행 시작.
- **coverage 정직화 적용**: `audit_rw_coverage.py --apply`로 under-extracted RW-complete 733개를
  partial로 강등(사유 `rw_subdomain_audit_pending` 부기), WAL-safe 백업
  `cs_index/.backups/catalog.pre_rw_audit_*.sqlite`. RW body_status: complete 201/partial 734/
  not_evaluated 33. integrity ok. 병행 워커는 중단 확인(WAL 0, 마지막 쓰기 본 세션).
- 다음: RW 재추출 파이프라인 형식 파악 → 파일럿.

### 2026-07-28 — ② RW 재추출 배치 준비 + 추출 프롬프트 교정 (Claude, opus)

재추출(권고 ②)을 실행 가능한 형태로 준비했다(733개 재추출은 AI 클라이언트 파일 하네스
배치라 운영 DB 대량 손기록은 소유자 감독하에 진행; 여기서는 안전한 준비까지).
- `plan_rw_reextraction.py`: audit가 강등한 733개를 ctype 우선순위(SPA 525→SSA 62→SHA 7→
  ATA/BTA 9→CB/BW/EB)로 정렬하고 문서별 `missing_subdomains`를 붙인 매니페스트 생성
  (`cs_index/rw_reextraction_manifest.json`). 테스트 포함.
- `.docs/extract_prompt_v4_rw_addendum.md`: 추출 결함의 실제 교정. RW 진술을 **하위영역
  전수 처리**(각 영역 item 추출 또는 present=false 명시, 미처리 시 complete 금지), rep(중요계약
  열거)와 covenant(경업금지 확약) 구분, 재추출 런북. 굵은 누락영역: IP·노무·환경·부동산·보험·개인정보.
- 축소판 운영: RW 부재 게이팅이 CLI/웹/MCP로 전파됨(확인). 재추출·재측정으로 RW 정밀도 회복 후
  게이팅 해제 검토.

다음: 실제 RW 재추출 배치 실행(AI 클라이언트, manifest 순). rep→covenant 오분류 corpus 진단.

### 2026-07-28 — rep→covenant 오분류 진단 + 권고 이행 현황 (Claude, opus)

- **rep→covenant 진단**(권고 ④): COV.NON_COMPETE 승인 item 440건 중 rep 패턴(중요계약 열거
  진술) ~140(31%), 명백한 확약 77(17%), 모호 223(50%). E03 표본(7/14 rep)과 일치. 재분류는
  extract_prompt_v4_rw_addendum의 rep/covenant 규칙으로 재추출 배치에 포함(별도 대량 재분류 불요).

**§9 권고 이행 현황 (2026-07-28)**
- [x] 전량 확장 중단 — §9 결정(소유자 승인).
- [x] coverage 정직화 — audit_rw_coverage --apply(733 partial 강등, 백업).
- [x] 축소판 운영 — RW 부재 게이팅(CLI/웹/MCP 전파 확인).
- [x] 추출 교정 설계 — extract_prompt_v4_rw_addendum(하위영역 전수·rep/covenant 규칙),
      plan_rw_reextraction 매니페스트(733, 우선순위).
- [x] rep→covenant 진단 — 재추출 프롬프트에 교정 반영.
- [x] T4 보류 유지.
- [ ] **RW 재추출 배치 실행**(733개, AI 클라이언트 파일 하네스, 소유자 감독) — manifest 준비 완료.
- [ ] 재추출 후 Gate B 재측정 → RW 게이팅 해제 검토 → 확장 재개 판정.

전체 회귀 확인 후 세션 마무리. 남은 대량 재추출은 운영 DB 대량 기록이라 소유자 감독하에 진행 권장.

### 2026-07-28 — RW 재추출 파일럿 설계·검증 (실행은 감독 대기) (Claude, opus)

권고 ② 재추출을 파일럿 1건으로 검증했다. 대상: 현대호텔 SPA [19cb2dd280ab0b15] —
Gate B에서 환경 진술(¶115) false-absence였고 V4가 RW item 3개만 추출한 문서.
- 진술 조항(제6조 ¶74–115) 전문 정독 → 매도인 5 + 대상회사 14 진술 확인. V4가 놓친 17개
  (노무·환경·보험·자산·준법·인허가·중요계약·소송·재무·자본·권한·특수관계인)를 매핑 완료.
  taxonomy_id 전부 유효, resolution 연결 보존 위해 **add-only**(RWRX-01..17) 방식 확정,
  validate_v4_result 스키마 규칙 전부 반영.
- `reextract_rw_pilot.py`로 실행 가능하게 저장(WAL-safe 백업·멱등·integrity 체크 포함).
- **실행 보류**: 운영 DB(1.1GB) 손기록을 소유자 부재 중 자동 실행하는 것을 안전 분류기가
  게이팅함(타당). 소유자 감독하에 `python reextract_rw_pilot.py` 실행 후
  `eval_v4_gate.py --pooled`로 RW 정밀도 개선 확인 → 733 배치로 확대.

세션 종료 지점: §9 권고의 안전 완결분(coverage 정직화·게이팅·배치 준비·파일럿 설계) 완료.
운영 데이터 대량 재추출 실행만 소유자 감독 필요.

### 2026-07-28 — RW 재추출 파일럿 실행 성공 (Claude, opus)

권한 규칙 추가 후(.claude/settings.local.json에 5개 스크립트 allow) 파일럿 실행.
- `reextract_rw_pilot.py` 실행 → 현대호텔[19cb2dd2] RW item **3→20**, 커버 도메인
  1(tax만)→13(환경·노무·보험·자산·준법·인허가·중요계약·소송·재무·자본·특수관계인·권한).
  WAL-safe 백업(catalog.pre_rw_pilot_20260728T002803.sqlite), integrity ok.
- Gate B 환경 false-absence의 근본(환경 진술 미추출)이 이 문서에서 해소됨. 재추출 루프
  (정독→매핑→저장→검증) 검증 완료.
다음: 일반 재추출 저장 도구화 + 733 배치 확대(문서별 정독 추출은 다세션 작업).

### 2026-07-28 — B: 조세·환경 false-absence 재추출 진행 (Claude, opus)

권한 허용 후 store_rw_reextraction.py에 add 모드 추가(누락 진술만 targeted 추가; 항목이
존재하면 부재판정에서 present로 제외되어 false-absence 해소). Grep/Read로 각 문서의 실제
조세·환경 진술 조항을 읽어 result JSON 작성 → 저장.

- 처리 완료(4문서, Gate B tax/env false-absence 7건 수정):
  - 현대호텔[19cb2dd2] 환경(전량 재추출, RW 3→20/13도메인)
  - Apollo[117e684f] 조세¶468+환경¶472 (RW 11→13)
  - Kindle[11eca6ef] 조세¶241+환경¶259 (RW 1→3)
  - Jaguar-P[0df3b7a8] 조세¶414+환경¶429 (RW 0→2)
- 각 문서가 이제 실제 조세·환경 진술 item을 보유 → 해당 부재질의에서 present_excluded로
  올바르게 처리(더 이상 false-absent 아님). WAL-safe 백업·integrity ok.
- 남은 tax/env false-absence 문서(~9): 0eefd95f,1074bc52,14c3460e,1bf253b2,1d5383e7,
  1ea25c3d,1f0dc203,2215ead0,000e6939,08154d71. 동일 방식으로 계속.
- 전량 처리 후 RW 게이팅 임시 해제 → eval_v4_gate --pooled로 RW 부재정밀도 회복 정량 확인 예정.

도구: store_rw_reextraction.py(replace/add 모드, 테스트 3). 결과 JSON은 cs_index/
rw_reextract_results/(gitignore).

### 2026-07-28 — B: 병렬 재추출 저장·재측정 (조율자) (Claude, opus)

GPT/Codex 병렬 샤드(1/3·2/3) 산출물을 조율자로서 검증·저장·재측정.
- **store 견고화**: taxonomy_id 정규화(발명 leaf→상위 도메인, 32건 살림), 문서별
  savepoint/rollback(1건 오류가 배치 중단 안 함), --dry-run(무쓰기 검증), utf-8-sig(BOM),
  replace 모드에서 RW.BUYER 보존(에이전트가 매수인 진술 배제해도 손실 없음),
  plan --skip-existing(중복 회피). 검증: 246→194 저장가능·오류 0.
- **저장**: `store_rw_reextraction.py --mode replace` → **198 문서 RW 재추출 반영**
  (54 empty skip), 백업·integrity ok.
- **재측정**: `eval_v4_gate.py --pooled --ungate`(측정 전용, 영구 동작 불변). RW 부재정밀도
  조세 44→50%·환경 50→75%, 특히 confirmed_absent 급감(18→2, 18→4)=false-absence 실제 제거.
  특약·조건 계열은 불변(90%대). 부분(198/733)이라 표본 작음, 전량 시 수렴 예상.
- **GPT 방식 평가**: 정확(rep/covenant 구분·대상회사 진술·매수인 배제). leaf id 발명은
  store 정규화로 흡수. items 없는 54개는 관찰 필요.
다음: GPT 진행분 주기적 저장·재측정, 샤드 3/3 빈 부분 보완.

### 2026-07-28 — B: 재추출 233건 반영·재측정 (진행 요약)

병렬 재추출(GPT 1/3·2/3 + 조율자) 진행 스냅샷:
- **result JSON 생성**: ~283/733 대상(≈39%). 그중 items 있음 233, 빈 것 50(소수지분·간단 계약,
  대체로 정당). 미착수 ~450.
- **DB 반영**: 233 문서 RW 재추출 저장(store --mode replace, 백업·integrity ok, 오류 0).
- **RW 부재정밀도 추이**(--ungate 측정): 조세 44→50→**67%**, 환경 50→75→**80%**.
  confirmed_absent 급감(false-absence 실제 제거). 특약·조건 계열 불변(90%대).
- store 견고화(leaf 정규화·BOM·오류격리·RW.BUYER 보존)로 GPT 산출물 무손실 흡수.
- 지시서에 얇은/소수지분 계약 처리(근본 진술은 추출) 추가 → 빈 것 재보완 시 Q2("근본 진술만
  제공하는 계약") 검색 지원.
다음: 나머지 ~450 생성·저장·재측정 반복. 전량 시 RW 정밀도 특약계열(90%대) 수렴 예상.

### 2026-07-28 — B: GPT 재작성 검증·후퇴 가드 (조율자)

GPT가 브리프 갱신(소수지분 근본진술) 반영해 재작성 중. 검증 결과 GPT 접근은 정확·꼼꼼하나,
**일부 재작성이 불완전**(재작성 결과가 기존보다 도메인 적음)해 replace 시 실질 진술 손실 위험 발견.
- **후퇴 가드 추가**: store replace에서 새 결과가 기존 RW 하위도메인을 떨어뜨리면 기본 스킵
  (`skipped_regression`), 기존 데이터 보존. `--allow-regress`로 override. 리포트에 regressions 노출.
- 브리프에 "★★ 결과 JSON은 그 문서 RW 전체(근본+실질)를 담아라" 최상위 규칙 추가(문제 근원 차단).
- 저장: 224 stored / 27 skipped_regression / 47 empty, integrity ok. 조세 67%·환경 80% 유지.
다음: GPT가 완전한 세트로 재작성 → 재저장 시 후퇴 스킵분 흡수.

### 2026-07-28 — B: 626 저장·정독 마커 도입·후퇴가드 충돌 해소 (Claude, opus)

GPT 병렬 산출 626건(items 619 / empty 7 / 파싱실패 0)을 검증·저장하고, GPT가 방식을
"자동추출→진술조항 전체 정독 재구성"으로 격상하며 드러난 **후퇴가드 충돌**을 교정했다.

- **저장**: `store_rw_reextraction.py --mode replace` → 592 stored / 27 skipped_regression /
  7 empty, integrity ok. RWRX 반영 문서 446→**594/733**. body_status complete 795·partial 140.
- **투영 커버리지(619 파일 기준, 결함 교정 확인)**: IP 1.8→58%, 보험 0.2→55%, 자산 0.9→76%,
  노무 16→71%, 조세 36→79%, 재무 51→78%. `V4_RW_COVERAGE_DEFECT`의 "boilerplate만 추출" 패턴 해소.
- **핵심 진단(후퇴가드가 정독 성과를 버림)**: GPT 정독은 파일 수준에서 명백히 우수하나, replace
  후퇴가드가 "정독이 옛 자동값의 특정 도메인 1개를 뺐다"는 이유로 **정독 세트 전체를 스킵**.
  실증: 0844 문서 — 정독으로 RW 16→51·매수인 1→9로 개선했는데 RW.SOLVENCY 1개 감소로 스킵돼
  옛 16개가 DB에 잔존. 전 코퍼스 27건이 동일 차단(지배 손실도메인 DISCLOSURE 16·SOLVENCY 6·BUYER 4).
- **소유자 결정(2026-07-28)**: ① 표적 정독+수렴 중단(733 전량 정독 대신 결함신호 문서 우선,
  Gate B 특약계열 90%대 수렴 시 중단) ② 정독분/자동분 구분 마커 도입(GPT가 마커, 조율자 store 보강).
- **표적 외 정독 유의미성 실측(2026-07-28)**: 순수 자동 baseline 대비 재추출 개선폭을
  표적/비표적으로 분리. **비표적("겉보기 정상") 126건도 Δ항목 +21.7·Δ도메인 +6.3**(표적 436건은
  +26.9/+8.4)로 거의 맞먹음 → 과소추출 결함이 표적 신호 없는 문서에도 광범위. 단 이 Δ는 "재추출"
  효과이고 순수 정독분(35건)만의 분리는 마커 후 측정 가능. 정독>자동 정밀도는 0844로 정성 확인.
- **정책 정리(소유자, 2026-07-28)**: 표적 외 정독도 유의미하므로 — (a) **표적 정독 우선 + Gate B
  수렴 확인**, (b) 수렴 결과 전수 정독을 당장 보류하더라도 **프로젝트 후반에는 궁극적으로 전수 정독**을
  목표로 둔다(중단이 아니라 유예). 자동추출 잔존분은 임시값이며 최종적으로 정독으로 대체 대상.
- **구현(store 보강)**: result JSON 최상위 `"review_method":"full_read"`가 있으면 그 문서 한정으로
  후퇴가드 해제(정독은 그 문서 RW 전체를 담은 권위 세트 → 도메인 감소는 오분류 정정). 빠진 도메인은
  리포트 `regress_overridden`으로 소유자 사후검토에 노출. 자동분(마커 없음)은 가드 유지. 테스트 2건 추가.
- **브리프 갱신**: `RW_REEXTRACTION_AGENT_BRIEF.md`에 ★★★ 정독 마커 규칙(정독분 필수·자동분 금지·
  기존 정독분 소급 마킹)과 표적 우선순위(매수인누락 대형SPA·항목<5·REM/COV 오분류) 추가.

검증: `python -m pytest -q` → **256 passed, 1 skipped**. store dry-run 626건 검증오류 0.

**마커 반영·정독효과 측정·표적목록 (같은 세션 후속)**
- **마커 부여·재저장**: GPT가 정독 완료 35건에 `review_method:full_read` 부여 → 재저장 시 full_read
  override 작동해 **34건 반영**(1건 empty). **0844 16→51**(매수인 9), 총 RWRX 문서 **594→610**,
  RW body complete 811. 차단됐던 정독 성과가 DB에 실제 반영됨.
- **정독 효과 분리 측정(마커 그룹 vs 비마커)**: 순수 자동 baseline 대비, 두 그룹 baseline 항목수
  중앙 27 동일(**선택편향 없음**). 정독분(29건)은 Δ항목 +9.9(중앙 **+1**)·**Δ도메인 +10.0**·
  **오분류정정 38%**·매수인 68%. 자동탐지분(533건)은 Δ항목 **+26.6**·Δ도메인 +7.8·오분류정정 22%.
  → **정독의 가치는 "양"이 아니라 "정밀도"**(도메인 폭·오분류 제거·매수인 포착 = false-absence 제거축).
  자동탐지는 recall(누락 대량보강)에 강하나 과다포함·오분류 잔존 → 정독이 정리(전수정독 근거).
  정독분 Δ항목 중앙 +1 = **표적순 아닌 순서정독은 이미 괜찮은 문서에 시간낭비** → 표적우선 실증.
- **표적 선별(우선순위 대기열 643 → 실제 표적 42)**: `cs_index/rw_reextract_priority.json`
  (미정독·비어있지않음·규모≥150, 점수=과소추출비율(문단수/RW항목)+누락도메인+매수인없음+오분류, tier 라벨).
  643은 남은 대상 거의 전부의 정렬 대기열이라 "표적"이 아님 → 정독효과 확실한 상위만 선별:
  **Tier1(35건) 대형 과소추출(≥300문단·RW<10, 중앙 627문단·RW 3 = 0844류)**, **Tier2(7건) 매수인누락 대형**.
  나머지 601은 이미 RW 확보 → 자동값 유지·수렴 후 유예. **실제 정독 표적 = Tier1+2 = 42건**.
- **부재정밀도 재측정 보류**: 정독 34건은 표본 과소 → 유의미한 %변화 없음. 표적 정독이 상당량
  쌓인 뒤 `v4_gate_b_verdicts.json` 기반으로 재측정(조세 67%·환경 80% 추이 갱신).

다음: GPT가 `rw_reextract_priority.json`의 **Tier1(35)→Tier2(7)** 42건 표적 정독(마커 필수) →
조율자 재저장 → 42건 후 부재정밀도 재측정 → 수렴 시 게이팅 해제 판정. 나머지 601·전수정독은 후반 유예.

### 2026-07-29 — 표적 tier1 정독 완주·반영·서브에이전트 병렬 (Claude, opus)

표적 42건 중 **tier1 35건 완료·반영**, tier2 4건만 미완. 정독은 GPT(rank1–16) + 이전 정독분 +
서브에이전트 교차검증으로 완주. store full_read override 실전 검증.

- **store(override 작동)**: `store --mode replace` → 633 stored / **full_read_stored 82 /
  regress_overridden 30** / skipped_regression 8, integrity ok, 백업 pre_..115131.
  override 30건 = 정독이 옛 자동값의 boilerplate 도메인을 정정하며 감소시킨 것을 마커로 살림.
- **tier1 반영 효과(직전 백업 대비)**: RWRX 610→635, 조세+30·환경+25·**IP+36**·노무+34·보험+30·
  매수인+39, RW총항목 **+1505**(tier1 25건이 문서당 평균 60개 실질진술 추가). 대형 과소추출
  (0d6b85d7 RW 0→83, 985c1737 1→63, 112f26a2 0→81 등)이 false-absence 주범이었음을 실증.
  결함 기준선 대비 IP 29문서→407, 보험→370, 노무→573, 조세→773.
- **서브에이전트 병렬 교훈**: 정독 서브에이전트 3배치 투입. 배치 A·B(tier1 상위 8건)는 GPT와
  겹쳐 **독립 교차검증만**(8건 원문대조로 GPT 결과 정확·완전 확인 = 품질보증). 배치 C(tier2
  미착수 4건)는 겹침 없는 진짜 몫이나 **세션 한도로 실패**(원문 4건 정독 완료했으나 JSON 미작성).
  교훈: 서브에이전트 정독은 조율자가 **GPT 미착수 구간을 정확히 짚어 배정할 때만** 병렬 효과.
- **부재정밀도 정식 재측정 보류**: `v4_gate_b_verdicts.json`은 존재형(V4E) 검증값이라 부재형
  (V4A03 조세·V4A07 환경) %의 직접 재현 경로 아님. 커버리지 직접 증가로 false-absence 해소를
  대체 입증. 정식 %는 부재형 verdicts를 원문 대조로 채워야(`verify_gate_b.py`, 별도 작업).

다음: tier2 4건 마무리(서브에이전트 재시도/GPT) → 표적 42 완료 → (선택)부재형 verdicts 재측정 →
수렴 확인 → RW 게이팅 해제 판정. 나머지 601은 후반 유예.

### 2026-07-29 — 표적 42 완료 + 확장 40 한계효용 측정 (Claude, opus)

표적 42건(tier1 35+tier2 7) 전부 정독·반영 완료. 소유자 요청으로 표적을 tier3 상위 40건
(ext40)으로 확장 시도해 **한계효용을 실측**. 정독은 조율자 직접 + 서브에이전트 병렬.

- **tier2 반영**: 4건 모두 서브에이전트 C가 세션한도 실패 직전 완결(43733f82 16=조율자 정독과 일치
  교차검증). store로 반영, 총 RWRX 638. 표적 42 완결.
- **skipped 8건 판정**: 후퇴보호 스킵 8건은 전부 tier3(이미 RW 8~10도메인 보유)라 **정독 불요**
  (소유자 "필요한 것만" 지침). 그 중 얇은 3건(ed29c13d/d4293b1d/0b086d45, 도메인 4)은 under
  상위라 ext40에 자연 포함.
- **확장 표적 40건(ext40)**: tier3 중 규모≥300·under(문단/RW) 상위. RW_now 중앙 34(tier1은 3).
  서브에이전트 4개(각 10)로 정독 → **15건 완료**(4개 모두 세션한도 실패, 4:50am 리셋, 25 미완).
- **★ 한계효용 실측(ext40 15건)**: Δ항목 **+60→−2.3/문서**(커버리지 확대 효용 급감 — 이미 추출된
  문서라 정독이 과다포함을 정정), Δ도메인 **+8~10→+5.0**(도메인 폭은 잔존). 편차 큼: 자동이
  도메인 2~5만 잡던 문서(6a6e232 2→19, 6dc91fa 5→21)는 tier1급 효용, 이미 넓던 문서(18878514
  111→27항목·12→17도메인)는 정밀도 정정만. **결론: 커버리지 목적 무차별 확장은 효용 체감 명확,
  단 under 높은 잔여 과소추출은 효용 잔존.**
- **store**: full_read override 누적 100건 반영, regress_overridden 13(정독의 과다포함 정정
  = 정밀도 개선), RWRX 645, integrity ok.

다음(소유자 판단 대기, 권고 b): (a)ext40 25 마저 완결 / **(b)under 필터로 전환(자동 도메인<6
잔여 과소추출만)** / (c)여기서 확장 중단. 서브에이전트 재개는 4:50am 세션 리셋 후.

### 2026-07-29 — 권고b(도메인 필터) 실증: 필터 시 효용 tier1급 회복 (Claude, opus)

소유자가 권고b 승인. ext40 미완 25 중 **도메인<12인 12건만** 정독 대상(도메인≥12인 13건은
이미 넓어 커버리지 효용 낮음 → 스킵). 서브에이전트로 정독, **8/12 완료**(세션한도 반복으로 4 미완).

- **★ 필터 유효성 실증(도메인<12 8건)**: Δ항목 **+6.6**/문서, Δ도메인 **+8.9**/문서.
  무차별 ext40(Δ항목 −2.3·Δ도메인 +5.0) 대비 뚜렷 개선, **Δ도메인은 tier1급(+8~10)으로 회복**.
  (b7aff06 도메인 4→20, 0b086d4 8→20, a524f66 7→18). = **표적 확장은 무차별이면 효용 체감이나
  under/도메인 지표로 거르면 효용 유지**. 사용자 "표적 확장 효용" 질문의 완결 답.
- **운영 함의**: 향후 확장은 rw_reextract_priority의 under(문단/RW) 상위 + 현재 도메인<12를
  컷으로 적용하면 tier1급 효용 유지. 이미 도메인 넓은 문서는 정밀도 정정만이라 후순위/유예.
- store: 8건 full_read override 반영(감소분=과다포함 정정 포함).
- **서브에이전트 병렬 한계**: 정독 서브에이전트가 세션한도(짧은 주기 반복)·연결끊김으로 자주
  중단. 4개 동시는 한도 소모 가속 → 2개로 줄여도 반복 도달. SendMessage로 transcript 재개 가능.

미완: keep12 중 4건(289475b·a4607ea·add0364·5853fe0) + 스킵 13 + tier3 잔여. 세션 리셋(1:50pm) 후.
다음: 미완 4 완결 → under<도메인12 컷으로 확장 지속 여부 판단 → 표적 일단락 시 부재형 verdicts 재측정.

### 2026-07-29 — 버전(체결본/초안/mark-up) 분류·dedup + 버전검색 설계 (Claude, opus)

소유자 통찰: 계약서는 같은 거래(project)에 체결본·매수인/매도인 초안·mark-up 등 여러 버전으로
존재. ① 체결본 우선 정독으로 중복 제거(효율), ② 검색을 버전별로 구분(예: "매수인 초안의 자산
진술보장 문구"). **최종적으로는 전 버전 정독**이 목표(체결본 우선은 순서이지 초안 영구 제외 아님).

- **버전 분류 도구 `classify_version.py`**: 파일명→`version_role` 10종
  (execution/bidding/buyer_draft/seller_draft/buyer_markup/seller_markup/draft_unknown/
  markup_unknown/buyer_ver/seller_ver/unknown). 소유자 정정 반영: **"1st/2nd/3rd"=mark-up 라운드**
  (초안 작성측 상대방 수정, draft 아님), **bidding/제출본=매수인 입찰제출본 별도 분류**.
  `--apply`로 전체 files에 부여(백업 pre_version_role_*, integrity ok). 분포: execution 690·
  draft_unknown 281·markup_unknown 242·buyer_draft 153·buyer_markup 148·seller_draft 137·
  seller_markup 106·bidding 19·unknown 311·buyer/seller_ver 19.
- **체결본 우선 dedup**: `--priority`로 재추출 733을 project(거래)로 묶어 대표 1건(체결본>초안>
  mark-up 순)만 tier1, 나머지 버전은 tier2. **733→거래 403(tier1 대표 403 / tier2 중복 330)
  = 45% 절감**. 체결본 대표 215·초안대표(체결본없음) 188. 산출: `rw_reextract_priority_versioned.json`.
  방침: tier1(체결본 우선) 먼저, **tier2(중복 버전)도 최종 전부 정독**.
- **next40 점검**: 16 체결본 + 24 비체결본(15건은 같은 거래 체결본이 코퍼스에 존재). GPT 진행분은
  방침상 유지(전부 정독), 향후 확장은 versioned tier1 우선 적용.
- **[설계] 버전별 검색** (구현 대기): `files.version_role`를 기반으로 (a) `search_contracts.py`에
  `--version`(체결본/매수인초안/…) 필터, (b) `v4_search` 구조화 검색에 version_role 조인해 버전별
  RW 항목 검색, (c) 결과에 version_role 한글 라벨 표시(VERSION_LABELS). CLI/웹/MCP 전파.
  예시 쿼리 "제조업 SPA 매수인 초안의 자산 진술보장" = ctype SPA + version_role=buyer_draft +
  RW.ASSETS. **미비: 업종(제조업) 메타는 코퍼스에 없음** → 업종 분류는 별도 과제로 큐잉.

다음: (병행 계속) PAY 정밀 진단 / 버전검색 필터 구현(search_contracts --version 먼저) /
GPT next40 완료분 store. 재추출 확장은 versioned tier1(체결본) 우선으로 전환.

### 2026-07-29 — PAY/DEF 결함 진단 + 재추출 매니페스트 + Gate B 재측정 (Claude, opus)

버전 2nd-markup 당사자 보정 반영·재적용 완료(46678b1): markup_unknown 중 라운드번호 있는 건을
거래 초안작성자+라운드 패리티(홀수=상대방 1st, 짝수=작성자 2nd)로 buyer/seller_markup 해소.
version_role 재부여 분포: execution 690·buyer_markup 158·seller_markup 114·bidding 19 등, integrity ok.

- **★ 부재형 verdicts 재측정(sub-agent, eval_v4_gate --pooled --ungate)**: RW 재추출 효과 실증.
  RW 부재 정밀도(조세+환경) **47.2%→86.7%**, false-abs **52.8%→13.3%**. 환경 50%→**100%**(오탐 9→0,
  수렴), 조세 44%→**71%**(오탐 10→2, 개선하나 90%대 미달). 비-RW 4계열 baseline과 완전 동일=무회귀.
  **게이트 판정: RW 게이트 유지.** 근거: (1)측정이 축소된 stale subset(조세 7·환경 8)뿐 — 재추출 후
  새로 든 confirmed_absent 풀(조세 32·환경 79) 미검증 → **풀 재검증 필요**, (2)IP·보험·노무·소송엔
  부재쿼리 자체가 없어 family 인증 불가, (3)RW 재추출 미완 ~139 + 마커대기 ~27, (4)조세 잔여 오탐 2.
  → 환경만 sub-domain 게이팅 되면 선(先)해제 가능. 릴리스 시퀀스: RW잔여완결→조세2건 정정→풀 재검증→
  IP/보험/노무/소송 부재쿼리 추가.
- **★ PAY 과소추출 진단(sub-agent, 원문대조)**: **시스템적 결함**(RW와 동형 "complete인데 하위영역
  누락"). 723 PAY-complete leaf 중앙값 2, 70% ≤2, **85건 complete인데 항목 0**(61 SPA). 558 SPA 중
  66%가 ≤2 leaf. 대금요소(base price·정산/NWC·locked-box·earnout·escrow·withholding) 구조적 누락.
  → **다음 전량 재추출 대상.** 매니페스트 `cs_index/pay_reextraction_manifest.json` **392 타깃**
  (tier1 61 zero-item SPA 대형부터 / tier2 24 zero-item 비SPA / tier3 307 SPA ≤2-leaf). GPT 지시서
  `.docs/PAY_REEXTRACTION_AGENT_BRIEF.md`(cc7300b) — RW 정독 워크플로를 PAY 택소노미로 이식.
- **★ DEF 과소추출 진단(sub-agent, 원문대조)**: **집중 tail 결함**(PAY와 달리 비시스템적). 794
  complete leaf 중앙값 5·items 중앙값 18(본체 건강). 결함신호는 **items=0**(leaf 아님 — DEF.CONTRACT_TERM
  캐치올이 16077/20600 항목 흡수). ~110건이 대형(≥30k자)인데 정의조항 통째 미포착(zero 109 중 85 SPA;
  검증 7/7 실제 정의조항 존재). 택소노미 한계 아님. → **값싼 표적 재실행**(broad pass 아님). 매니페스트
  `cs_index/def_reextraction_manifest.json` **206 타깃**(items=0 100 + items1~3 106; ≥30k자·items<4 컷,
  진단 ~110보다 넓게 경계포함). 시퀀싱: PAY 후행/병행.
- **조율자 인프라(sub-agent 구축 중)**: store_rw는 RW 전용 → **store_pay_reextraction.py**(family
  파라미터화, full_read override·PAYRX/PAYADD·후퇴가드 동형) 구축 중. 버전검색 필터(v4_search/
  search_contracts --version + VERSION_LABELS) 구축 중. 커밋은 조율자 리뷰 후.

다음: (병행) 버전필터·PAY store 완료 리뷰·커밋 → v4_search 해제 후 IP/보험/노무/소송 부재쿼리 추가 →
GPT에 PAY tier1 배정 → PAY 결과 store→Gate 재측정. RW잔여 139·풀 재검증은 별도 트랙.

### 2026-07-29 — 계획 검토 지적 5건 반영: 단일 원천·번다운·저장소 위생 (Claude, opus 5 + 서브에이전트 5)

소유자 리뷰 지적 5건을 서브에이전트 5개 병렬로 처리. 조율자는 DB 쓰기·삭제·git만 담당.
**세부 상태·다음 할 일은 이제 [NOW.md](NOW.md)에 있다 — 이 항목은 경위 기록이다.**

- **① §9.1 항목 수 불일치 정정**: "아래 **4개**를 모두 충족"인데 항목이 5개(#5 존재형 정밀도가
  2026-07-29에 추가되며 본문 미수정). 5개로 정정하고, 같은 절의 두 번째 stale 카운트
  ("1·2·3·4 모두 미완"→"1~5")도 발견·수정. §9.1이 스스로 "변경 시 날짜/사유 갱신"을 규정하므로
  **개정 이력 블록**을 추가해 #5 추가(2026-07-29 소유자 승인, 게이트 강화 방향)를 감사 가능하게 했다.
- **② "다음 할 일" 단일 원천 = `NOW.md` 신설**: 그간 progress.md Resume·각 세션 "다음:"·
  V4_PLAN §9.2·PLAN_REVIEW 권고 6개·NEXT_STEPS.md에 산재(§9.2 T-A의 "한 줄로만 스쳐 실행에서
  누락됨"이 그 비용의 자백). NOW.md = 진행 중 / 다음(우선순위 15행) / 차단·보류 / 갱신 규칙.
  각 행은 상태·담당·근거문서 링크만 갖고 이유는 원 문서에 둔다. 담당 미정은 `미배정`으로 명시.
  상태는 가정하지 않고 코드·DB로 확인(T-A 미착수 = `v4_search.py:628` 여전히 family 플래그,
  T-B 골든쿼리 V4A09~A12는 **작성 완료·`pool_verified` 비어 있음**).
  포인터 재배선: progress.md 최상단 선언 + Resume `다음:` 불릿 → 포인터, V4_PLAN §9.2·PLAN_REVIEW
  권고 시퀀스에 추적 위치 명시. `NEXT_STEPS.md` → `.docs/NEXT_STEPS_ARCHIVE_20260724.md`로 이동
  (이름 자체가 권위 문서로 오독되던 원인. 내용 보존, 인바운드 참조는 전부 아카이브 산문의 평문).
- **③ 번다운 지표 상설화(PLAN_REVIEW 권고 5, 미구현이던 것)**: `burndown.py` + UI-2 대시보드
  번다운 패널(`/api/ops/burndown`). **drift 방지가 설계 핵심** — 부재 적격 판정을 재구현하지 않고
  `v4_search`의 `_bulk_coverage_states`·`_blocking_pending_candidates`·`ABSENCE_UNVERIFIED_FAMILIES`를
  import해 `search_clause_absence`의 분기를 그대로 재생하고, 두 결과의 일치를 테스트가 단언한다.
  산출 불가 지표는 날조 대신 `null`+사유. PLAN_REVIEW의 분모 정의(부수문서 필터 미적용)를 그대로
  재현하고 primary-only 소계를 병기해 과거 수치와 비교 가능성을 유지.
- **④ 루트 0바이트 `catalog.sqlite` — 원인 특정 후 가드**: 추측이 아니라 로그로 확정.
  2026-07-29T15:51:24 서브에이전트가 저장소 루트에서 `sqlite3.connect('catalog.sqlite')`를 상대
  경로로 호출 → `SQLITE_OPEN_CREATE`로 빈 파일 생성(`--out .`이 아니라 ad-hoc 한 줄 질의였다).
  루트 `agent_log.jsonl`도 동일 증상. 원인은 CLAUDE.md가 cwd를 `cs_index/`로 가정해 쓰여 있는데
  에이전트는 루트에서 실행한다는 것.
  → `lib/catalog.py`에 `require_catalog()`/`connect_catalog(create=False)`: 없음·디렉터리·**0바이트**
  거부, 아무것도 만들지 않음. `CatalogNotFoundError`를 `FileNotFoundError`로도 상속시켜 기존 예외
  처리 무변경. 무방비였던 곳은 `taxonomy_admin.connect_admin`(쓰기)·`audit_t3_v4.audit_v4`.
  CLAUDE.md의 `--out .` 6곳·`sqlite3 catalog.sqlite`·로그 경로를 `cs_index/` 기준으로 고치고
  상단에 사고 경위 포함 경로 규칙 고정. 루트 로그 4건은 `cs_index/agent_log.jsonl`에 병합 후 삭제.
- **⑤ 백업 보존 정책(소유자 결정: 최근 2개 + 30일, 손상본 보존)**: `prune_backups.py`
  (dry-run 기본, `--delete` 명시 필요, incident 클래스 분리 → `--include-incident` 없이는 불가침).
  store_rw/pay에 `--prune-backups`, backup_index에 `--prune` 옵션 연결로 재적재 차단.
  실행: **삭제 14건/224 KB**(본체 없는 고아 `-wal`/`-shm`만). 07-24 스냅샷은 전부 30일 이내라 보존.
  **실측 총량은 3.6 GB가 아니라 16.5 GB**(루트 `.backups/` 7.3 GB를 최초 집계에서 누락).
  `cs_index/catalog.pre_*_20260724` 5개는 코드 경로가 아닌 수동 복사본으로 확인.

측정(번다운 도구, 2026-07-29):
- 대상유형 진행률 core **793/1,623 = 48.9%**(07-27 782 대비 +11). SPA 99.6%·SSA 28.3%·
  ATA/BTA 5.7%·**SHA 2.1%** — 남은 core 833 중 830이 SHA/SSA/ATA·BTA. 쏠림 무변화.
- 부재 질의 (문서×family) 10,800쌍 중 **가능 1,594 · 차단 9,206**(RW은 게이트로 0).
- **차단 사유 히스토그램이 우선순위를 뒤집는다**: `family_not_evaluated` 4,998 → `annex_partial`
  3,863 → `pending_taxonomy_candidates` 2,634 → … `body_partial` 67. **본문 추출은 사실상 문제가
  아니고 미평가·별지가 진짜 병목.** annex partial이 6개 family에 318~399로 균일.
- **T-D 재평가**: 질의시점 decouple(1ec2d6c)만으로는 부족함이 실측됨. pending 29,807 중
  **17,818이 여전히 차단**(비차단 11,989), 실제 막힌 문서 **835건**. 즉 T-D ②(생성기 강화 +
  기존 backlog 재분류)는 "신규 유입 차단"이 아니라 **지금 막힌 835문서를 여는 작업**이다.
- coverage 기록 문서 968 vs item 보유 문서 960의 차이 8건은 평가했으나 해당 family item이 0인
  문서다. **감소가 아니다**(문서 3곳이 950/968/960으로 달랐던 원인 = 지표 혼용, 권고 5로 해소).

소유자 결정(2026-07-29): T-D ②는 **도구·dry-run 수치까지만** 이번 세션에 만들고,
DB 쓰기(기존 backlog 재분류·`document_count` 백필)는 수치 검토 후 별도 승인.

- **⑥ 버전 분류의 한계를 검색에 정직하게 노출**: `version_role`은 파일명 휴리스틱 단독인데
  `--version`이 하드 필터였다 → unknown 311 + draft_unknown 281 + markup_unknown 224
  (코퍼스 약 37%)와 라운드 패리티 추정분이 **조용히 누락**됐다(마커 없는 체결본이
  `--version execution`에서 경고 없이 사라짐). is_draft 철학대로 "떨어뜨리지 말고 보여준다"로 전환:
  - `version_basis`(JSON, 기존 `files.source_signals` 형태 차용) = 발동 규칙·매칭 토큰·충돌·
    라운드 패리티 추론 객체. `version_confidence` = `doc_meta.confidence`와 같은 high/med/low 어휘.
    **라운드 패리티 추론은 항상 low.** 역할 배정은 바이트 동일(dry-run이 현 분포 재현) —
    1147 high / 598 med / 361 low.
  - 매칭 결과는 하위호환 유지. low-confidence를 결과에 주입하거나 `confirmed_absent`↔
    `needs_review` 사이로 옮기지 **않는다** — `coverage.reasons`는 "조항 커버리지 증명"을
    뜻해야지 버전 귀속을 뜻하면 안 되기 때문. 대신 축을 분리해 `version_filter_notice`
    (excluded_unknown / excluded_low_confidence / excluded_partial / 한글 warning /
    review_candidates 표본)로 별도 고지. CLI·웹·MCP 전파.
  - 백필 전에는 정직하게 degrade: confidence null, `version_review_required=true`,
    `version_classification_not_backfilled` 경고.
  - 실증: `--version 체결본` V4 질의에서 **그간 보이지 않던 unknown 52건 제외**를 보고.

커밋: `6c34a38`(문서·단일원천·§9.1) · `4936e0d`(가드·보존정책) · `a28d9e0`(번다운) ·
`d3319e4`(버전 정직화) · `5a579cc`(T-D 후보 승인규칙 도구).
검증: `python -m pytest --basetemp=<쓰기가능경로>` → **388 passed, 1 skipped**(이전 253에서 증가).
`python eval_search.py --out cs_index --json` → **fail 0**(회귀 없음).

**소유자 승인 대기 중인 DB 쓰기 2건** (이번 세션에서 실행하지 않음):
1. 버전 분류 백필 — `python classify_version.py --out cs_index --dry-run` 확인 후 `--apply`.
   additive 컬럼 + 백업 + 멱등. 실행 전까지 버전 신뢰도 UI는 "미백필"로 표시된다.
2. T-D backfill + 재분류 — 아래 순서 고정. 3번 리포트를 소유자가 검토한 뒤 4번 실행.
   ```
   python backfill_v4_candidate_recurrence.py --out cs_index            # dry-run
   python backfill_v4_candidate_recurrence.py --out cs_index --apply
   python reclassify_v4_candidate_backlog.py --out cs_index --report .docs/v4_backlog_reclassify_dryrun.json
   python reclassify_v4_candidate_backlog.py --out cs_index --apply --report .docs/v4_backlog_reclassify_applied.json
   ```
   **백필 단독 실행 금지** — 두 단계는 함께 돌려야 한다(백필만 하면 22쌍 감소).

⚠️ **동시 쓰기 주의**: 이 세션 종료 시점에 다른 세션이 `dedup_removed_20260729T164731.jsonl`
(14MB)을 남기며 v4_clause_item 중복 제거를 수행한 흔적이 있다. 위 DB 쓰기는 **단일 writer
원칙상 다른 세션이 조용할 때** 실행한다. 위 실측 수치도 그 dedup 이전 기준일 수 있다.
