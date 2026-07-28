# Progress

> 상세 초기 이력(Phase 0~3, 2026-07-09~07-16)은 [.docs/PROGRESS_ARCHIVE.md](.docs/PROGRESS_ARCHIVE.md)로 이동했다.
> 이 파일은 **현재 상태 요약 + V4 원자 항목 계층 이력**을 유지한다.

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

**진행 중 / 다음 단계**
- **V4-6 확장 배치 계속**: 기존 600건 재처리와 증권계약 포함 300건 적재 완료.
  다음 순서는 남은 SSA→ATA/BTA→SHA이며, 이후 미처리 증권계약을 포함해 계속 확장한다.
  pending taxonomy 후보와 partial source는 부재 판정에서 제외하고 `needs_review`로 보존.
- **taxonomy 후보 검수**: 31,083개 후보의 반복 문구 군집화를 완료하고 신규 leaf
  5개를 승격했으며, 고신뢰 후보 1,245건을 1,272개 원자 item으로 병합했다.
  남은 29,807건은 다음 family별 tranche에서 계속 검수한다.
- **Gate B 정식화**: 현재 recall 평가는 승인 item 기반 회귀이므로 독립 사람검수 골드 필요.
- **T4 (벡터 하이브리드)**: 미착수. V4-5 게이트 통과·coverage 안정 후 시작(Phase 4).

**테스트**: `python -m pytest` → **238 passed, 1 skipped**.
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
