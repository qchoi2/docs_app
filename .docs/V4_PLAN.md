# V4_PLAN — M&A 계약 세부 원자 항목 계층
_2026-07-16 작성. progress.md "V4 다음 단계" 초안을 검토·확장해 확정한 계획.
전제: T3 v3 파일럿(`.docs/T3_V3_PILOT.md`)의 사람 승인 완료. v3 승인 전에는 V4에 착수하지 않는다._

> 진행 상태(2026-07-24): **V4-0 통과, V4-1R2 구현, V4-2 대표 10건
> 승인·적재 및 V4-3 60건 파일럿 완료.**
> `.docs/V4_SCOPE_REVIEW_20_20260723.md`와
> `.docs/V4_SCOPE_REVIEW_100_20260723.md`의 한국·미국형 표본 결과에 따라 family를
> `RW|CP|COV|DEF|PAY|REM`으로 확장했다. 기존 additive DB migration,
> `source_kind/source_ref`, 자료별 `v4_source_coverage`, taxonomy catalog 포함 입력,
> 별지 인벤토리, 원자 단위·별지 completeness 감사, 검증 통과분 전용 저장 경로를 구현했다.
> taxonomy는 398노드·1,561 aliases, version 12이다. 국문 SPA
> `[0ba3a1b8246c5dd5]`는 본문·별지·공개목록의 131개 item을 승인·적재했다.
> 기존 대표 표본의 나머지 9건은 529개 사전분류 item과 450개 후보를 문맥 재검수해
> 861개 원자 item으로 확정했다. 별지·Schedule·Exhibit 64개 고유 source를 추적했고,
> 제공된 63개는 검수 완료, 코퍼스에 없는 Seller Disclosure Schedule 1개는
> `missing`으로 보존했다. 최종 감사 9/9 pass 후 운영 DB에 적재했다.
> V4-3에서는 기존 대표 10건과 층화 선정한 추가 50건을 합쳐 60건 코호트를
> 구성했다. 추가 50건에서 확정 item 2,500개를 추출하고 사전 후보 1,583개 중
> 1,393개를 해소했다. 반복 명제 10개 노드(구조 부모 포함)를 v12에 반영했고,
> 잔여 후보 190개는 확정 item과 분리해 운영 후보 큐에 저장했다. 감사 결과는
> pass 17, review 33, pending/error 0, 구조 issue 0이다.
> V4-4 UI-5도 구현했다. `/taxonomy`에서 190개 후보를 179개 문구 묶음으로
> 보고 기존 노드 귀속·신규 leaf 승격·기각을 일괄 처리할 수 있다. 모든 변경은
> 단일 SQLite 트랜잭션과 `v4_taxonomy_action_log`에 기록된다.

## 0. 목적과 판단 근거

v4는 v3를 대체하지 않는다. v3의 조항 존재·위치 위에 진술보장·선행조건·확약·정의·
대금지급·위반구제의
**세부 의미를 검색 가능한 원자 항목**으로 저장하는 계층을 추가한다.

MCP + AI 클라이언트가 있는데도 v4가 필요한 이유는 질의 유형에 따라 다르다.

| 질의 유형 | MCP 에이전트(v3 정독)로 가능? | v4 필요성 |
|---|---|---|
| 존재형 탐색("불법파견 진술보장 있는 SPA") | 가능하나 매번 다수 정독 → 느리고 키워드 누락 잔존 | recall·속도 개선 |
| **부재형**("미지급임금 진술보장이 없는 계약") | 불가 — 전수 정독 없이는 부재 판정 불가 | **필수** (coverage) |
| 횡단 비교·집계("채택률", "10건 비교표") | 질의당 비용이 문서 수에 비례 | **필수** |

따라서 v4의 최우선 산출물은 (1) 원자 항목 + (2) 평가 커버리지이며,
탐색형 질의의 누락 감소는 아래 §4 하이브리드 검색이 함께 담당한다.

## 1. 설계 원칙

1. **원자 항목**: 조항 유형(family) + 분야(domain) + 세부주제(topic) + 행위/쟁점 +
   대상 + 시점 + 주체 + 원자적 명제를 분리 저장한다. 긴 복합 태그를 만들지 않는다.
2. **부재 vs 부정형 구분**: "미지급임금이 없음"은 해당 진술보장이 **존재**하는 것이다
   (`statement_polarity=none_exist`). 세부 항목의 부재로 저장하지 않는다.
3. **통제 taxonomy + alias**: 표현 변이는 신규 분류가 아니라 alias. 대상만 다르면
   object 필드, 조건·예외 차이면 qualifier 필드로 저장한다.
4. **후보 → 승인 거버넌스**: 신규 표현은 즉시 정식 태그가 되지 않는다. 승격은
   **웹 UI 버튼으로만** 수행한다(§5). 소유자가 이후 코드·yaml을 직접 수정하지 않아도
   taxonomy가 성장할 수 있어야 한다.
5. **분류를 단일 실패점으로 만들지 않는다**: 항목 텍스트도 FTS에 넣어, 분류 오류가
   "검색 불가"가 아니라 "텍스트로는 검색됨"으로 강등되게 한다(§4).
6. **유료 API 자동 호출 금지 유지**: 추출은 AI 클라이언트가 파일 하네스로 수행하고,
   서버(스크립트)는 검증·저장만 담당한다.
7. **세부 명제 전수 원자화**: 평가 범위에 포함된 진술보장·선행조건·확약은 제목이나 상위
   도메인에서 멈추지 않는다. 예를 들어 노무 진술은 `위반사항 없음`, `근로조건 준수`,
   `규정 외 임금 없음`, `미지급 보수 없음`처럼 독립적으로 참·거짓을 판단하거나 비교할 수 있는
   최소 명제까지 분리한다. 하나라도 상위 `RW.LABOR` item 하나로 뭉치면 해당 family의
   `body_status=complete`를 허용하지 않는다.
8. **본문 참조자료 전수 추적**: 본문이 Schedule·Disclosure Schedule·별지·부속서·첨부를
   참조하면 참조 목록을 먼저 만들고, 코퍼스에서 존재하는 각 참조자료의 내용을 모두 평가한다.
   누락·별도파일·판독불가 상태를 참조자료별로 기록하며, 본문만 읽고 완료 처리하지 않는다.
9. **동일 의미는 동일 taxonomy**: 문구·언어·주체 표현이 달라도 법적 명제가 같으면 기존
   taxonomy_id와 alias에 매핑한다. 기존 노드로 표현할 수 없는 독립적인 검색 개념일 때만 신규
   후보를 만들고, 승인 후 정식 노드로 승격·기존 item을 재분류한다.
10. **한국·미국형 거래구조 병렬 지원**: 계약금·중도금·잔금·위약벌·임직원 승계와
    Estimated/Final Purchase Price·NWC/debt/cash adjustment·escrow/holdback·
    disclosure schedules·efforts standard를 동일한 원자 모델에서 검색할 수 있게 한다.
11. **다중 기능 문구 중복 색인**: 계약금 몰취처럼 지급구조와 위반구제 기능을 동시에
    가지는 문구는 `PAY`와 `REM` item으로 각각 저장하고 `related_item_ref`로 연결한다.

## 2. 데이터 모델

기존 `doc_meta`(v2/v3)는 불변. 다음 테이블을 `catalog.sqlite`에 추가한다.

- **`v4_taxonomy_node`** — 통제 분류체계. `taxonomy_id`(예: `RW.LABOR.WAGE.UNPAID`),
  `parent_id`, `family(RW|CP|COV|DEF|PAY|REM)`, `canonical_ko/en`, 정의, 포함·제외 기준, `depth`,
  `status(active|deprecated)`, `taxonomy_version`, `origin(seed|promoted)`.
  **DB 테이블이 단일 원천이다.** yaml은 내보내기 산출물일 뿐이며 손편집 대상이 아니다.
- **`v4_taxonomy_alias`** — 노드별 표현 변이(미지급임금/체불임금/미불임금 등).
- **`v4_clause_item`** — 문서별 원자 항목. `family`은
  `RW|CP|COV|DEF|PAY|REM`. `file_key`, `family`, `taxonomy_id`,
  결과 내 고유 `item_ref`와 복수 기능 연결용 `related_item_ref`,
  `proposition`(원자적 명제), `statement_polarity`, `subject_role`, `counterparty_role`,
  `action`, `object_type`, `effective_time`, `qualifier_json`(조건·예외·중요성·인식 제한),
  `verbatim`, `loc_start/loc_end`, 정규화 값, `confidence`, `txt_hash`,
  `taxonomy_version`, `extractor_version`, `prompt_version`, `review_status`.
  한 문장이 복수 의미를 가지면 복수 항목으로 저장한다(예: 기업결합 문구 →
  확약/신고서 제출 + 선행조건/승인 취득).
  본문과 별지의 관계를 확인할 수 있도록 `source_kind(body|schedule|disclosure_schedule|annex|exhibit)`,
  `source_name`, `source_ref`, `parent_clause_ref`도 저장한다. 별지가 본문 진술의 예외·한정이면
  별도 item으로 저장하되 관련 본문 item과 연결한다. 복수 기능 문구는
  `related_item_ref`로 다른 family의 대응 item과 연결한다.
  DEF item은 `defined_term`, 포함·제외 요소·정량 threshold를 qualifier에 저장한다.
  PAY item은 지급단계·payer/payee·금액/비율·통화·시점·조건을 저장한다.
  REM item은 구제유형·trigger·beneficiary·금액산식·배타성·survival을 저장한다.
- **`v4_item_fts`** — `proposition` + `verbatim`의 FTS5 인덱스(§4의 2번째 경로).
- **`v4_document_coverage`** — family별 평가 상태. **본문과 별지를 분리**한다:
  `family`, `body_status(complete|partial|not_evaluated|unreadable)`,
  `annex_status(complete|partial|not_evaluated|unreadable|no_annex)`, 사유, 평가 버전.
  한국 M&A 계약은 진술보장 세부를 별지(공개목록)에 두는 경우가 많고 코퍼스에
  스캔 PDF(empty) 48건이 있으므로, 본문만 평가 완료인 문서에서 부재를 단정하면 틀린다.
- **`v4_source_coverage`** — 문서가 참조하는 자료별 평가 인벤토리. `file_key`, `family`,
  `source_kind`, `source_name`, `source_ref`, `storage_file_key`(별도 파일이면),
  `status(complete|partial|not_evaluated|unreadable|missing)`, `reason`, `txt_hash`를 저장한다.
  `v4_document_coverage.annex_status`는 이 자료별 행을 집계한 값이며, 참조자료 하나라도
  `complete`가 아니면 aggregate `annex_status=complete`를 금지한다.
- **`v4_taxonomy_candidate`** — 신규 분류 후보 큐. 제안 이름, 추천 상위 노드,
  기존 분류와 다른 이유, 원문 근거(file_key·¶·verbatim), 발견 문서 수(자동 갱신),
  가장 가까운 기존 노드, `status(pending|approved|merged|rejected)`, 처리 이력.

### 부재 판정 규칙 (답변 원칙 4·5의 확장)

"X 항목이 없는 계약"은 다음을 **모두** 만족할 때만 부재로 판정한다.

1. 해당 family의 `body_status=complete`
2. `annex_status`가 `complete` 또는 `no_annex` — 아니면 "별지 미평가"로 분리 고지
3. 해당 taxonomy_id(하위 노드 포함)의 item이 없음

응답에는 항상 "별지 미평가/판독불가 n건 제외"를 포함한다.

## 3. taxonomy 초기 구성과 term_dict 통합

- 기존 2단계(family/domain) seed는 상위 골격으로 유지한다. 도메인 목록은 progress.md 초안의
  대분류(당사자·자본구조·재무·자산·노무·조세·환경·지재·개인정보·보험·부패방지 등 /
  CP: 승인·정부신고·정부승인·제3자동의·종결서류·계약상태 등 / COV: 사업유지·행위제한·
  신고승인·인사·비밀유지·경업금지 등)를 사용한다.
- **3단계 이하 topic은 대표 계약서에서 실제 확인된 원자 명제를 기준으로 만든다.** V4-2를
  시작하기 전에 대표 문서의 반복 항목을 seed/승인 노드로 확정한다. 예:
  `RW.LABOR.NO_VIOLATION`, `RW.LABOR.WORKING_CONDITIONS`,
  `RW.LABOR.NO_OFF_BOOK_WAGES`, `RW.LABOR.UNPAID_COMPENSATION`.
  표현만 다른 문구는 새 노드를 만들지 않고 alias로 병합한다. 기존 노드와 다른 독립 명제는
  후보 큐에 넣고, §5의 승인 절차 후 정식 taxonomy로 추가한다. 깊이 확장의 근거는 원문 근거,
  반복 발견 문서 수, `query_log.jsonl`·`agent_log.jsonl`의 실제 질의 분포를 함께 사용한다.
- 추가 100건에서는 복리후생·연금, 근로자 분류, 사이버보안, 제재·수출통제,
  고객·공급업체, D&O tail, TSA, R&W 보험, payoff·담보해제, locked-box,
  rollover, seller note, sandbagging, 손해범위 제외, 보험·조세혜택 차감,
  이중배상 금지를 확인해 taxonomy version 3 seed로 보강했다. 문구 검출 건수와
  file_key 근거는 `.docs/V4_SCOPE_REVIEW_100_20260723.md`에 기록한다.
- 기존 120건과 겹치지 않는 추가 200건에서는 매출채권·재고·지급능력·개인정보
  법규준수, 장부보존·특권·보증해제·종결후협조, SHA의 tag/drag·ROFR/ROFO·
  put/call·reserved matters·이사지명·정보권·배당·lock-up·창업자 전념,
  기업결합·주주승인·FIRPTA·good standing, 자산양수도의 양수/제외자산과
  승계/제외채무, materiality scrape·연대/개별책임·구상·기본진술 별도 cap·
  청구통지기한·배상금 tax gross-up을 확인해 taxonomy version 4 seed로
  보강했다. SHA 권리가 `Encumbrance` 정의에 이름만 열거된 경우에는 운영
  COV item으로 오분류하지 않는 규칙도 추가했다. 근거는
  `.docs/V4_SCOPE_REVIEW_200_20260723.md`와
  `.docs/V4_SCOPE_GAPS_200_20260723.md`에 기록한다.
- **분류 결정 순서**: (1) 정규화된 명제와 기존 노드의 포함·제외 기준 비교 →
  (2) 동일 의미면 기존 node 사용 및 표현을 alias로 축적 → (3) 대상·조건 차이는 object/qualifier로
  저장 → (4) 독립적으로 검색·비교할 새 법적 명제일 때만 candidate 생성. 후보 승인 후 해당
  parent에 임시 매핑된 item을 새 node로 재분류해야 배치가 완료된다.
- **term_dict.yaml과의 이원화 금지**: term_dict의 "진술보장 하위" 항목(인사노무진술 등)은
  대응하는 v4 domain 노드에 1:1 매핑하거나 alias로 흡수한다. `term_dict_tools.py --validate`에
  매핑 검증을 추가해, 매핑 없는 하위 주제 항목이 있으면 경고한다. 검색 시 canonical
  정규화(CLAUDE.md 워크플로우 0단계)는 v4 taxonomy_id까지 해석되어야 한다.

## 4. 하이브리드 검색 — 누락 방지의 핵심

세부 질의는 세 경로의 **합집합**으로 검색하고, 결과에 매칭 경로를 표시한다.

1. **구조화 경로**: `v4_clause_item`의 taxonomy_id(하위 노드 포함)·polarity·시점·주체 필터
2. **항목 텍스트 경로**: `v4_item_fts`에서 proposition/verbatim FTS — 분류가 틀렸거나
   아직 후보 상태인 항목도 여기서 잡힌다
3. **문단 FTS 폴백**: 기존 T2 경로 — v4 미평가 문서를 위한 안전망. 결과는
   `needs_review`(미평가)로 분리해 구조화 결과와 혼동하지 않는다

이 합집합 구조 덕분에 taxonomy 오분류는 recall 손실이 아니라 순위 하락으로 강등된다.

## 5. taxonomy 거버넌스 UI — 버튼만으로 운영 (필수 요건)

**소유자가 이후 개발을 이어가지 않아도 운영 가능해야 한다.** 승격·병합·반려에
코드 수정, yaml 편집, SQL 실행이 일절 필요 없어야 한다. `/taxonomy` 관리 화면(UI-5,
`UI_ROADMAP.md` 참조)을 웹앱에 추가한다.

화면 구성:

- **후보 목록 탭**: `v4_taxonomy_candidate` pending 목록. 각 후보에 제안 이름, 추천 상위
  노드, 원문 근거(verbatim + file_key/¶ 링크 → 기존 문단 보기 재사용), 발견 문서 수,
  가장 가까운 기존 노드와의 비교를 표시. 행마다 세 버튼:
  - **[정식 분류로 승격]** — 상위 노드 선택(추천값 기본) 후 확정. 새 node 생성,
    `taxonomy_version` 자동 +1, 해당 후보로 잡혀 있던 item들의 taxonomy_id 자동 재지정.
  - **[기존 분류의 alias로 병합]** — 대상 노드 선택. alias 추가 + item 재지정.
  - **[반려]** — 사유 선택(표현 차이/무의미/오추출). 동일 표현 재제안 시 이력 표시.
- **분류체계 탭**: 트리 보기, 노드별 item 수·문서 수, deprecated 처리 버튼(삭제 금지 —
  기존 item 보존), yaml 내보내기 버튼(백업·리뷰용).
- **영향 미리보기**: 승격/병합 확정 전에 영향받는 item 수·문서 수를 표시한다.
- **자동 회귀 확인**: 승격/병합 후 골든 질의 eval을 백그라운드 job으로 실행하는
  [회귀 확인 실행] 버튼(기존 job queue 재사용). 결과 악화 시 배너로 경고.

API(웹앱 표준 오류 코드·127.0.0.1 규칙 준수):
`GET /api/v4/taxonomy`, `GET /api/v4/taxonomy/candidates`,
`POST /api/v4/taxonomy/candidates/{id}/approve|merge|reject`,
`POST /api/v4/taxonomy/export`. 쓰기는 기존 단일 job queue 경로를 따른다.

선택 확장: term_dict `pending_terms.yaml` 후보도 같은 화면의 별도 탭에서 승인 처리
(현재 소유자 수동 병합 흐름의 UI화). v4와 독립적으로 구현 가능하며 우선순위는 낮다.

## 6. 적용 범위 — 유형별 계층 적용

전 코퍼스 × 전 세부주제 균일 적용은 하지 않는다.

- **v4 전 항목 추출 대상**: **SPA, SSA, ATA/BTA, SHA, CB 인수계약,
  CB 매수계약, BW 인수계약, W 매수계약, EB 인수계약** 및 해당 유형 신규 문서.
  SHA는 진술보장·확약 구조가 SPA와 다르지만(주주간 의무·
  지배구조 확약 중심) 실무 검색 수요가 크므로 전 항목 대상에 포함한다.
  SHA 특유 확약(동의사항 이행, 이사지명 협조, 자금조달 의무 등)은 COV 도메인
  seed에 반영한다.
- CB·BW·W·EB 유형은 발행·인수 또는 매수 구조, 사채·워런트 조건, 전환·행사,
  조기상환, 기한이익상실, 담보, 발행회사 확약과 진술보장을 PAY·COV·DEF·RW·REM
  원자 명제로 모두 추출한다. `CBSA`, `BWSA`, `EBSA`, `NPA`,
  `Warrant Purchase Agreement/WPA` 표현도 각 유형의 식별 신호로 사용한다.
  폴더 기준 유형은 런타임 canonical 값
  `CB인수|CB매수|BW인수|W매수|EB인수`로 정규화한다.
- **나머지 유형**(MOU, JVA, 분할합병, 주식교환, 기타): v3 유지.
  agent_log에서 세부 질의 수요가 확인되면 유형 단위로 추가 편입한다.
- 처리 순서: SPA → CB인수 → CB매수 → BW인수 → W매수 → EB인수 → SSA →
  ATA/BTA → SHA (dup 대표만, 기존 원칙 유지). 증권계약 유형이 뒤로 밀리지 않도록
  각 증권계약 유형의 미처리분을 우선 포함한 뒤 기존 M&A 유형 확장을 계속한다.

## 7. 추출 파이프라인 — 검증된 파일 하네스 재사용

새 MCP 추출 도구(get_next_v4_task 등)는 만들지 않는다. v2·v3에서 검증된
`enrich_contracts.py` 파일 하네스 패턴을 확장한다.

1. `plan_v4_batch.py`(또는 enrich_contracts 옵션)가 본문에서 Schedule·Disclosure Schedule·
   별지·부속서·첨부 참조를 먼저 탐지해 `source_inventory`를 만든다. 같은 파일 뒤쪽 또는
   별도 파일에 있는 자료를 `storage_file_key`와 연결한다. 참조자료의 존재 여부와 판독 가능성도
   입력에 포함한다.
2. `cs_index/enrich_inputs_v4/`에는 v3의 family 위치 좌표로 **해당 조항의 전체 하위 항·호 +
   source_inventory의 관련 참조자료 전체**를 넣는다. 조항이 길면 항·호 단위 chunk로 분할하되
   순서와 parent reference를 보존한다. 문서 전체를 무차별 입력하지 않는다.
3. AI 클라이언트가 `.docs/extract_prompt_v4.md` 기준으로
   `cs_index/enrich_results_v4/<file_key>.json` 작성. **결정적 로컬(키워드) 추출로
   대체하지 않는다** — v2 전량 초벌의 한계(표현 변이 누락)가 v4를 하는 이유다.
4. **원자성·완전성 감사**: `audit_t3_v4.py`는 taxonomy_id, verbatim, ¶ 위치, polarity뿐 아니라
   (a) 본문에서 열거된 하위 항·호 대비 item 누락, (b) 복수 독립 명제의 단일 item 뭉침,
   (c) source_inventory 대비 별지 미평가, (d) 기존 taxonomy와 의미가 같은 신규 후보의 중복
   생성을 검사한다.
5. 후보가 있으면 사람/UI가 기존 노드 alias 병합 또는 신규 노드 승격을 처리하고 item을
   재분류한다. 미처리 후보가 남은 문서는 V4 완료로 계산하지 않는다.
6. `enrich_contracts.py --meta-schema-version 4`가 위 검증과 후보 정리를 통과한 결과만 저장한다.
   재개형·증분으로 수행한다.
7. **드리프트 보정**: 확정 항목 20건을 보정 세트로 두고, 프롬프트/extractor 버전이
   바뀔 때마다 재추출해 일치율을 기록한다. 항목별 `extractor_version`·`prompt_version`
   저장으로 어느 배치 산출물인지 항상 추적 가능하게 한다.

## 8. 검색 인터페이스

- **CLI**: `search_contracts.py --item RW.LABOR.WAGE.UNPAID [--polarity none_exist]
  [--time 종결일] [--subject 대상회사]` + `--item-absent`(§2 부재 판정 규칙 적용).
- **웹**: 검색 화면에 v4 필터(family/domain/topic 셀렉트 — taxonomy 테이블에서 동적
  생성, 하드코딩 금지), 결과 카드에 매칭 경로(구조화/항목텍스트/문단FTS) 배지와
  coverage 상태 표시.
- **MCP**: 질의 쪽 2개만 추가 — `search_clause_items`, `compare_clause_items`
  (문서별 세부 항목 비교표, 각 셀에 verbatim·¶). 기존 7개 도구 계약은 불변.
- 모든 인터페이스에서 v4 미평가 문서는 부재로 오판하지 않고 `needs_review`로 분리한다
  (v3 구조화 조건과 동일한 규칙).

## 9. 평가 — 이중 게이트

**게이트 A(자체 품질)**: 전 present 항목에 verbatim·¶ 위치 존재, taxonomy 외 ID 저장
불가(스키마 강제), 원문-명제 의미 일치율 95%+(검수 표본), **열거된 하위 항·호의 원자 명제
누락 0건**, **참조된 별지·Disclosure Schedule의 미추적 0건**, 동일 의미의 taxonomy 중복 0건,
신규 후보·low confidence 전수 검토, 잘못된 부재 판정 0건, 기존 T1~T3 eval 회귀 없음.

**게이트 B(비교 게이트 — 전량 확장의 조건)**: 세부 골든 질의 30~50개
(부재형·비교형 포함, `golden_queries.yaml`에 T4 섹션으로 추가)를 두 방식으로 실행:

- (a) v3 + MCP 에이전트 정독 (현행 베이스라인)
- (b) v4 하이브리드 검색

recall, 정독 문서 수, 소요 시간을 비교한다. **(b)가 recall에서 유의미하게 우위가
아니면 전량 확장을 중단**하고, 부재 판정·비교 기능만 v4로 유지하는 축소판으로
전환한다. 이 결과가 "MCP만으로 충분한가"에 대한 데이터 근거다.

### 9.1 RW 부재 게이트 해제 체크리스트 (고정 — 2026-07-29)

_배경: RW `confirmed_absent`가 하위영역 과소추출로 대부분 false여서 `v4_search.ABSENCE_UNVERIFIED_FAMILIES={"RW"}`로 needs_review 강등 중. 해제 조건이 검증할 때마다 하나씩 늘어나 게이트가 무기한 밀리는 것을 막기 위해, 아래를 **고정 체크리스트**로 못박는다. 항목 추가·임계치 변경은 §11 소유자 재승인 없이는 금지하고, 변경 시 이 날짜/사유를 갱신한다._

**소유자 승인(2026-07-29): 해제 임계치 = 정밀도 90%로 확정.** 이 체크리스트와 90% 기준은 고정이며, 이후 게이트는 이 기준으로만 판정한다(임의 조건 추가·임계치 변경은 소유자 재승인 없이 금지).

RW를 family 단위로 해제(confirmed_absent 허용)하려면 **아래 4개를 모두** 충족:
1. **재추출 완결**: RW 잔여 ~139건 + full_read 마커 소급 대기 ~27항목 store 완료(RWRX 반영).
2. **풀 재검증(축소 표본 아닌 현재 전량)**: 재추출 후의 `confirmed_absent` 풀 전량을 소유자 라벨링으로 검증 — 조세(현재 32)·환경(79) 및 신설 IP·보험·노무·소송 풀. **정밀도 ≥90%**(특약계열 수준)에서 해제.
3. **하위영역별 통과 또는 명시적 제외**: 부재쿼리가 있는 각 RW 하위영역이 정밀도 ≥90%를 달성하거나, 미달 하위영역은 confirmed_absent에서 제외(needs_review 유지)하도록 sub-domain 게이팅이 구현·적용됨(§9.2 T-A).
4. **잔여 오탐 정정**: 재측정에서 남은 개별 false-absence(예: 2026-07-29 기준 조세 잔여 2건) 정독 정정 완료.
5. **존재형·비교형 정밀도 ≥90%**(소유자 승인 2026-07-29, §9.3): 부재형과 동급으로 family별(RW·COV·PAY) 사람 원문대조 표본에서 존재 판정(진술을 확약으로 오인 등 오분류·과다분절 없음) 정밀도 ≥90%. "부재는 정확한데 존재는 얼마나 틀렸는지 모르는" 채 해제 방지. rep→covenant류 오분류 수정의 실효 재측정 포함.

**측정 시 주의(방법 고정)**: 정밀도는 **재추출 후 현재 confirmed_absent 풀**에서 산정한다. 고쳐져 풀을 빠져나간 문서만 남은 stale subset(2026-07-29 재측정의 조세 7·환경 8)으로 90%대를 주장하지 않는다.

**현재 상태(2026-07-29)**: 조세 44%→71%(오탐 10→2), 환경 50%→100%(오탐 9→0, 단 검증 8건). 1·2·3·4 모두 미완 → **게이트 유지**.

### 9.2 게이트 해제 병행 트랙 (재추출과 독립 — 지금 진행 가능)

"RW 완벽 후 PAY, PAY 후 DEF"의 단일 순차 사고에서, 재추출 진척과 무관하게 지금 당길 수 있는 것을 병행 트랙으로 분리한다(같은 작업량으로 해제 시점을 앞당김).

- **T-A 환경 선(先)해제**: 환경은 이미 100% 수렴 → family 전체를 기다리지 말고 **sub-domain 단위 게이팅**을 구현(`ABSENCE_UNVERIFIED_FAMILIES` family 플래그를 하위영역 예외 목록으로 확장)하고, 환경 풀(79) 재검증만 통과하면 **환경만 confirmed_absent 허용**. 비용 대비 빠른 승리. **다음 액션 리스트에 명시**(그간 progress.md에 한 줄로만 스쳐 실행에서 누락됨).
- **T-B 부재쿼리 신규 작성(IP·보험·노무·소송)**: 골든 쿼리 **작성은 추출 완료와 무관** — 지금 작성해두면 해당 하위영역 재추출이 끝나는 즉시 검증 착수 가능. 단 **작성≠측정**: 작성 직후 정밀도는 과소추출로 낮으며 **이를 해제 신호로 읽지 않는다**(재추출 반영 후에만 유효).
- **T-C 비-SPA 유형 검증(V4-6 진입 게이트)**: 진단·재추출 표본이 SPA에 편중(PAY 매니페스트 tier1 61·tier3 307 전부 SPA, 비-SPA는 tier2 24뿐). SHA·CB류는 2026-07-27 기준 커버리지 ~1.9%로 사실상 미검증. **V4-6 전량 확장 재개 전에** 비-SPA 각 유형 소표본(각 5~10건)에서 (a) 동일 결함 패턴 존재 여부, (b) SPA용 수정 방식의 적용 가능성을 진단하는 단계를 **필수 게이트로 삽입**. "SPA만 검증하고 확장 시작"을 방지.
- **T-D taxonomy 후보 backlog 결정(별도 축) — 소유자 결정 완료(2026-07-29)**: `v4_taxonomy_candidate` pending **29,807**(approved 31·merged 1,540·rejected 16). 이 backlog가 "complete인데 후보 미처리"로 다수 문서(2026-07-27 기준 약 43%)의 부재 질의를 막는다 — 재추출 깊이 문제와 **별개 축**. **소유자 결정(권장안 채택)**:
  1. **부재 판정을 미처리 후보에 의존시키지 않는다(decouple).** 문서의 부재 적격성은 §2 coverage + 구조화 item 존재로만 판정하고, **문서-특정 1회성 DEF 후보**(단일 문서에서만 나온 정의어, DEF.CONTRACT_TERM 캐치올 성격)는 미처리 상태라도 그 문서를 coverage=partial로 잡아 부재 질의를 끄지 않는다.
  2. **후보 생성기를 조인다.** 문서-특정 정의어가 각기 전역 taxonomy 후보를 생성하지 않도록(캐치올 DEF.CONTRACT_TERM로 흡수) 생성 기준을 강화 → 신규 backlog 유입 차단.
  구현은 추적 과제(별도)로 두되, **이 결정으로 부재 커버리지 언블록 경로가 확정**됨. 실행 순서: PAY tier1 확대·DEF 표적 재실행과 병행 가능.

### 9.3 과대추출(존재형 정밀도) 검증 축 — 미확립 공백 (2026-07-29, Fable 검토)

_지금까지 검증은 거의 전부 recall/부재 축(부재정밀도 47→87%)이고, **존재형(과대추출) 축은 사실상 미검증**이다. 유일한 표본이 2026-07-28 E03(경업금지) 14건인데 그중 **7/14=50%가 rep→covenant 오분류**였다. 과소추출 방지장치(정독·후퇴가드·audit_t3_v4)는 모두 비대칭이라 과다분절·오분류·중복태깅을 못 잡는다. **정독은 이 실패유형을 직접 못 고친다** — 오분류는 "안 읽어서"가 아니라 "읽고 인접분류(진술 vs 확약) 판단을 틀려서"이고, §1 설계원칙 7(세부 명제 전수 원자화)은 오히려 더 잘게·더 많이 쪼개라는 압력을 준다._

**확인된 결함(수정 효과 재측정 필요)**:
- COV.NON_COMPETE **31%가 rep→covenant 오분류** — "재추출 프롬프트로 시정 예정"으로만 기록, 고쳤는지 재측정 없음.
- E03 존재 표본 14건 중 50% 오분류 — 확대 검증 없음.
- taxonomy 후보 과다생성(29,807·이름 13,199종) = "굳이 새 분류 불필요한 걸 과다 생성"하는 동계열 위험(§9.2 T-D에서 별도 처리).

**대칭 방지장치(추가 조치)**:
1. **감사기 과다분절/중복 탐지**: `audit_t3_v4.py`는 현재 verbatim 실재(날조)·항호 누락만 본다. **한 문단·겹치는 loc 범위에서 item이 비정상적으로 많이(예 ≥5) 나오면** 플래그해 사람이 보게 하는 대칭 체크 추가.
2. **후퇴가드 대칭화**: 현재 store 가드는 "도메인 감소 차단"(과소추출 방지)뿐. **이전 대비 item 수 N배↑ 급증 시 store 전 표본확인 신호**(full_read가 문서당 +21.7·16→51 급증을 이미 아는 만큼 급증 자체를 신호로). 하드 블록이 아닌 WARN/표본요구로 시작.
3. **경계 자기설명 필드 강제**: REP vs COV 등 인접분류 item에 "왜 확약이고 진술이 아닌가"를 짧게 적게 하고(qualifier_json 확장), 비거나 상투적이면 감사기가 review 강등. 판단 근거 언어화로 얼버무린 분류 감소. **도입 시점(소유자 결정 2026-07-29): 현재 진행 중인 RW 20건·PAY tier1 정독 배치 종료 후** 브리프에 반영(진행 중 작업 방해·부분 재작업 방지).
4. **존재형 검증을 부재형 동급으로**: family별(RW·COV·PAY) 최소표본을 정해 사람이 원문대조하는 절차를 부재형과 동급 강도로. E03 단일 표본 탈피.
5. **COV.NON_COMPETE 오분류 수정 재측정**: rep→covenant 시정이 실제 효과 있었는지 원문대조 재측정.

**§9.1 반영 — 소유자 승인 완료(2026-07-29)**: RW 해제 조건에 "**존재형·비교형 정밀도 ≥90%**(family별 표본, 사람 검증)"를 **블로킹 조건으로 추가**(§9.1 #5). 게이트가 더 엄격해지는 방향.

## 10. 구현 단계

| 단계 | 내용 | 게이트 |
|---|---|---|
| V4-0 | **v3 파일럿 완료**: 60건 결과 생성·감사·사람 승인 (T3_V3_PILOT.md) | v3 승인 없이는 진행 금지 |
| V4-1R | 기존 스키마 보강: `source_kind/source_ref`, `v4_source_coverage`, 원자성·참조자료 감사, 세부 topic taxonomy/alias 규칙 | 본문·별지 연결 및 중복분류 테스트 |
| V4-1R2 | 누적 120건 범위검토를 반영해 `DEF|PAY|REM` 런타임 family, 6-family coverage, `related_item_ref`, taxonomy v3 및 입력 범위를 구현 | 6-family 스키마·입력·감사 테스트 |
| V4-2 | 대표 **국문 SPA 1건을 먼저 재추출**해 모든 RW 하위 항목과 참조 별지를 전수 원자화 → 소유자 검수 후 나머지 9건 진행 | 하위 명제 누락 0, 참조자료 미추적 0, taxonomy 중복 0 |
| V4-3 | **완료**: 60건 파일럿, 확정 2,500 item, 후보 190개(7.1%), taxonomy v12 | 구조 issue 0, 후보 큐 운영 적재 |
| V4-4 | **완료**: UI-5 후보 묶음·기존 귀속·신규 승격·기각·action log | 서비스·웹 통합 테스트로 버튼 처리 경로 확인 |
| V4-5 | **완료**: CLI·웹·MCP 원자 taxonomy 검색, 안전한 부재 판정·비교 + 36개 예비 골든 질의 Gate B | 구조화 recall 1.000, legacy 0.3748, 전체 회귀 205 passed |
| V4-6 | 통과 시 SPA→CB인수→CB매수→BW인수→W매수→EB인수→SSA→ATA/BTA→SHA 배치 확장, agent_log 기반 깊이·유형 증분 조정 | **비-SPA 소표본 결함/수정 검증(§9.2 T-C) 통과 필수** + 유형별 eval 회귀 확인 |

UI-5는 V4-4에 두되, V4-3 후보가 쌓이기 시작하면 곧바로 필요해지므로 V4-3와 병행
개발을 허용한다. **V4-6 전량 확장 시작 전에 UI-5가 반드시 완성되어 있어야 한다**
(확장 중 후보가 대량 발생하며, 이때부터 소유자는 버튼으로만 운영한다).

## 10.1 T4 인계 조건과 임베딩 단위

V4와 검색 티어 T4는 별도 체계다. V4는 검색할 구조화 데이터를 만들고,
T4는 그 데이터를 의미 유사도로 찾는 검색 경로다. T4 본 구현은 최소한
V4-5의 게이트 B가 끝나고 taxonomy·coverage·검색 인터페이스가 안정된 뒤 시작한다.
V4-6 전량 처리가 진행 중이어도 아래 조건을 만족한 승인 범위로 소표본 T4 A/B는 가능하지만,
미승인·partial 결과를 완전한 V4 데이터처럼 임베딩해서는 안 된다.

T4 입력 우선순위:

1. `review_status=approved`인 V4 원자 항목
2. V4가 partial/not_evaluated인 범위의 T3 clause_map 조항 청크
3. V4/T3가 커버하지 않는 문단 슬라이딩 윈도우

각 벡터 레코드는 `unit_kind`, file_key, item_ref 또는 canonical tag, taxonomy_id,
원문 ¶범위, txt_hash, taxonomy/extractor/prompt/embedding model version을 보존한다.
V4 item이 수정·재승인되거나 taxonomy가 재지정되면 해당 item 벡터만 stale 처리해
증분 재생성한다. 문서와 질문 벡터는 동일 임베딩 모델·revision·전처리를 사용한다.

T4는 V4의 부재 판정 규칙을 대체하지 않는다. 벡터 미검출은 부재의 근거가 될 수 없고,
부재 질의는 계속 §2 coverage 조건과 구조화 item 존재 여부로만 판정한다.

상세 런타임·성능·ablation 계약은 `docs_progress_v2.md`의 T4 계층을 따른다.

## 11. 사람 확인이 필요한 결정

- v3 파일럿 60건 승인 (V4-0)
- V4-2 대표 10건의 원자 항목 검수, V4-3 후보 큐 1차 일괄 처리
- 게이트 B 결과에 따른 전량 확장 / 축소판 전환 결정
- **RW 부재 게이트 해제 임계치 — 결정됨(2026-07-29): 90% 확정**(§9.1). **존재형·비교형 정밀도 ≥90%를 블로킹 조건으로 추가 승인**(§9.1 #5, §9.3). 이후 항목 추가·임계치 변경 시에만 재승인 필요
- **경계 자기설명 필드 도입 시점 — 결정됨(2026-07-29): 현재 RW20·PAY tier1 배치 종료 후**(§9.3-3)
- **taxonomy 후보 backlog(29,807 pending) 처리 방침 — 결정됨(2026-07-29, §9.2 T-D)**: (1) 부재 판정을 미처리 문서-특정 후보에서 decouple, (2) 후보 생성기 강화. 구현은 추적 과제
- **비-SPA 유형(SHA·CB류 등) V4-6 확장 진입 승인** — 소표본 결함/수정 유효성 검증 결과 기반(§9.2 T-C)
- 이후 taxonomy 승격·병합은 전부 UI-5 버튼 — 별도 개발 지시 불필요
