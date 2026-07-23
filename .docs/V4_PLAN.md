# V4_PLAN — M&A 계약 세부 원자 항목 계층
_2026-07-16 작성. progress.md "V4 다음 단계" 초안을 검토·확장해 확정한 계획.
전제: T3 v3 파일럿(`.docs/T3_V3_PILOT.md`)의 사람 승인 완료. v3 승인 전에는 V4에 착수하지 않는다._

> 진행 상태(2026-07-23): **V4-0 통과, V4-1R2 구현, taxonomy v8 및
> V4-2 대표 1건 승인·적재 완료.**
> `.docs/V4_SCOPE_REVIEW_20_20260723.md`와
> `.docs/V4_SCOPE_REVIEW_100_20260723.md`의 한국·미국형 표본 결과에 따라 family를
> `RW|CP|COV|DEF|PAY|REM`으로 확장했다. 기존 additive DB migration,
> `source_kind/source_ref`, 자료별 `v4_source_coverage`, taxonomy catalog 포함 입력,
> 별지 인벤토리, 원자 단위·별지 completeness 감사, 검증 통과분 전용 저장 경로를 구현했다.
> taxonomy는 369노드·1,390 aliases, version 8이다. 국문 SPA
> `[0ba3a1b8246c5dd5]`는 본문·별지·공개목록의 131개 item을 승인·적재했다.
> 기존 대표 표본의 나머지 9건은 taxonomy v8 입력으로 재생성했고, 보수적 사전분류
> 528개 item과 451개 문맥·taxonomy 후보를 `needs_review/partial` 상태로 격리했다.
> 다음은 9건의 원문 문맥 검수, 별지 coverage 확정 및 감사 pass 처리다.

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

- **v4 전 항목 추출 대상**: **SPA, SSA, ATA/BTA, SHA** (v2 메타 기준 약 1,623건 +
  해당 유형 신규 문서). SHA는 진술보장·확약 구조가 SPA와 다르지만(주주간 의무·
  지배구조 확약 중심) 실무 검색 수요가 크므로 전 항목 대상에 포함한다.
  SHA 특유 확약(동의사항 이행, 이사지명 협조, 자금조달 의무 등)은 COV 도메인
  seed에 반영한다.
- **나머지 유형**(MOU, JVA, CB/BW/EB, 분할합병, 주식교환, 기타): v3 유지.
  agent_log에서 세부 질의 수요가 확인되면 유형 단위로 추가 편입한다.
- 처리 순서: SPA → SSA → SHA → ATA/BTA (dup 대표만, 기존 원칙 유지).

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

## 10. 구현 단계

| 단계 | 내용 | 게이트 |
|---|---|---|
| V4-0 | **v3 파일럿 완료**: 60건 결과 생성·감사·사람 승인 (T3_V3_PILOT.md) | v3 승인 없이는 진행 금지 |
| V4-1R | 기존 스키마 보강: `source_kind/source_ref`, `v4_source_coverage`, 원자성·참조자료 감사, 세부 topic taxonomy/alias 규칙 | 본문·별지 연결 및 중복분류 테스트 |
| V4-1R2 | 누적 120건 범위검토를 반영해 `DEF|PAY|REM` 런타임 family, 6-family coverage, `related_item_ref`, taxonomy v3 및 입력 범위를 구현 | 6-family 스키마·입력·감사 테스트 |
| V4-2 | 대표 **국문 SPA 1건을 먼저 재추출**해 모든 RW 하위 항목과 참조 별지를 전수 원자화 → 소유자 검수 후 나머지 9건 진행 | 하위 명제 누락 0, 참조자료 미추적 0, taxonomy 중복 0 |
| V4-3 | 60건 파일럿 → 후보 큐 축적, 신규 후보 발생률 관찰 | 발생률 안정화 |
| V4-4 | **UI-5 taxonomy 관리 화면**(§5) + 후보 일괄 처리 → taxonomy v1 확정 | 버튼만으로 승격 가능 확인 |
| V4-5 | CLI·웹·MCP 검색(§8) + 세부 골든 질의 작성 → **게이트 B 실행** | §9 |
| V4-6 | 통과 시 SPA→SSA→SHA→ATA/BTA 배치 확장, agent_log 기반 깊이·유형 증분 조정 | 유형별 eval 회귀 확인 |

UI-5는 V4-4에 두되, V4-3 후보가 쌓이기 시작하면 곧바로 필요해지므로 V4-3와 병행
개발을 허용한다. **V4-6 전량 확장 시작 전에 UI-5가 반드시 완성되어 있어야 한다**
(확장 중 후보가 대량 발생하며, 이때부터 소유자는 버튼으로만 운영한다).

## 11. 사람 확인이 필요한 결정

- v3 파일럿 60건 승인 (V4-0)
- V4-2 대표 10건의 원자 항목 검수, V4-3 후보 큐 1차 일괄 처리
- 게이트 B 결과에 따른 전량 확장 / 축소판 전환 결정
- 이후 taxonomy 승격·병합은 전부 UI-5 버튼 — 별도 개발 지시 불필요
