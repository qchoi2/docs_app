# T-C 비-SPA 파일럿 — 정독 지시서 (2026-07-31)

_**실행 주체(2026-07-31 정책)**: 정독은 **Sonnet 5 서브에이전트**가 수행한다(조율자 Opus가 표본 배정·store·게이트·측정).
유료 API 미사용 — 구독형 에이전트의 직접 정독. 외부 GPT/Codex 샤드에 위임하지 않는다.
프로젝트 루트: `docs_app/`. 배경: [V4_PLAN §9.2 T-C](V4_PLAN.md), [NOW.md](../NOW.md) 추출 로드맵 Phase 0-②,
결함 뿌리: [RW_REEXTRACT_NEXT40](RW_REEXTRACT_NEXT40_20260730.md)(범위 미경계 = 자동추출 결함의 단일 뿌리)._

> **★ SHA는 특수 취급 — "도메인 적합성 평가"다.** 현재 taxonomy 6-family(RW·CP·PAY·REM·COV·DEF)는 **매매/인수계약
> 해부구조**이고 SHA 내용은 전부 `COV.SHA.*` 하위로 욱여넣어져 있다. SHA엔 CP(선행조건)·PAY(대금)·REM(손해배상)이
> SPA와 같은 의미로 거의 없다. 그러니 SHA를 정독할 때는 **"이 조항이 COV.SHA의 어느 노드에 담기는가, 안 담기면
> 어떤 도메인이 없어서인가"를 `defect_notes`에 taxonomy 권고로 남겨라** — 결함률이 아니라 **구조 적합성**이 SHA의 산출물이다.
> (예: "청산우선권/상환권/전환조건은 담을 노드가 없음 — SHA 경제적권리 도메인 부재", "이사회 운영이 COV(확약) 하위로만
> 존재해 '거버넌스 계약' 검색이 안 됨"). 매매/인수(ATA/BTA·CB인수 등)는 기존 6-family로 정독하되 안 맞는 지점을 같은 방식으로 기록.

## 목표 (셋 다)
지금까지 V4 추출은 SPA에 99.6% 집중돼 있고 비-SPA 유형은 색인이 사실상 없다(SHA 2.1%·ATA/BTA 5.7%·SSA 28.3%).
확장을 재개하기 전에, **비-SPA 유형 소표본을 처음부터 끝까지 정독**해 세 가지를 얻는다:
1. **유형 결함 스멜테스트** — SPA에서 학습한 결함(아래 체크리스트)이 이 유형들에도 같은 모양으로
   나타나는지, 아니면 유형 특유의 새 결함이 있는지. **완전한 결함 "프로파일"이 목표가 아니라
   스멜테스트다** — 소표본이므로 "있다/없다/다른 결함"의 방향만 잡으면 된다.
2. **유형별 절대-recall 정답지 부산물** — 정독으로 그 문서의 조항을 원자 항목으로 담으면, 그 자체가
   해당 유형의 정답지가 된다. 현재 정답지의 89%가 SPA라 "모든 유형에서 잘 되는가"를 잴 수단이 없다 —
   이 부산물이 그 공백을 메운다.
3. **V4-6 게이트 요건** — 비-SPA 소표본 통과는 전량 확장 재개의 필수 진입 게이트다.

## 표본
`cs_index/tc_pilot_manifest.json`에 배정 표본이 있다(SHA 8·SSA 5·ATA/BTA 5·CB인수 5 = 23건, 유형×언어×크기 분산).
각 문서에 `structure_preview`(조항 골격 미리보기)와 `existing_v4_items`(현재 저장된 item 수)가 붙어 있다.
**SHA 8건은 전부 existing_items=0** — 순수 greenfield 정독이다.

## ★★ 전(全) 계열 full_read — 그 문서의 모든 조항계열을 담아라
RW 재추출과 달리 이건 **유형 프로파일**이므로 RW만이 아니라 그 문서에 있는 **모든 계열**을 담는다:
RW(진술보장)·COV(확약)·REM(구제·손배·해제)·CP(선행조건)·PAY(대금)·DEF(정의). 문서를 처음부터 끝까지
읽고, 각 조항을 원자 명제로 추출해 result JSON의 `items`에 **빠짐없이** 넣어라.
조율자 store는 문서 단위로 **통째로 교체(replace)** 하므로, 처리하는 문서는 항상 **완전한 세트**로 낸다.

### SHA 특유 주의 — governance 조항을 절대 빠뜨리지 마라
센서스 v2에서 다음 SHA governance 노드가 **코퍼스 전체에서 item 0(dead node)** 로 확인됐다.
SHA를 정독할 때 이 조항들이 원문에 있으면 반드시 담아라(canonical 노드):
- `COV.SHA.QUORUM`(정족수) · `COV.SHA.DEADLOCK`(교착상태·분쟁해결) · `COV.SHA.VOTING_PROXY`(의결권 위임·공동행사) ·
  `COV.SHA.DIVIDEND_POLICY`(배당정책) · `COV.SHA.BUSINESS_PLAN_BUDGET`(사업계획·예산 승인) ·
  `COV.SHA.ANTI_DILUTION`(희석방지) · `COV.SHA.AFFILIATE_TRANSFER`(계열사 허용양도) · `COV.SHA.FOUNDER_COMMITMENT`(창업자 전념).
- 이미 있는 노드: `COV.SHA.TAG_ALONG`·`DRAG_ALONG`·`ROFR`·`RESERVED_MATTERS`·`BOARD`(있으면 담되 위 dead node를 우선 확인).
- **예약사항(reserved matters)/이사회 사전동의 목록**은 항목별로 분해하지 말고 그 조항 하나를
  `COV.SHA.RESERVED_MATTERS`로 담되, 그 안의 배당정책·사업계획 항목은 별도 명제로도 남겨라(중복 허용).

## ★★★ 정독 마커: `"review_method": "full_read"` (필수, 최상위)
store에는 후퇴 가드가 있어 새 결과가 기존 DB의 계열을 하나라도 떨어뜨리면 저장을 스킵한다(옛 자동추출 보존).
**정독 결과는 그 문서 전체를 담은 권위 있는 세트**이므로, 최상위에 `"review_method": "full_read"`를 넣어야
store가 그 문서 한정으로 가드를 해제하고 정독 세트를 그대로 저장한다. 빠진 계열은 리포트
`regress_overridden`에 남아 소유자가 사후 검토한다. **정독분에만 넣고, 부분·자동분에는 넣지 마라.**

## ★ 스멜테스트 산출: `defect_notes` (최상위, 이번 파일럿의 1차 산출물)
각 문서를 정독하며 관찰한 결함을 최상위 `defect_notes` 배열에 문서당 몇 줄로 남겨라. 아래 SPA-학습 결함이
**이 유형에도 나타나는지** 명시하고, 유형 특유의 새 결함도 적어라:
- **범위 미경계** — 진술/조항의 범위를 경계하지 못해 (a) 별지 편입형 과소추출, (b) 범위 밖 문장을
  긁어와 false-present. (SPA의 단일 뿌리 결함. 비-SPA에도 나타나는가?)
- **무내용 템플릿 proposition** — proposition이 목차 표제·빈 템플릿("Section 5.6 Solvency 13" 같은)인데 item으로 저장.
- **과대추출** — 한 조항을 과분할하거나 목차(TOC) 줄을 item으로 만듦.
- **오분류** — REM/COV 어투가 RW로, 또는 계열 간 혼동(특히 SHA governance ↔ 일반 COV).
- **유형 특유 결함** — 위 목록에 없는, 이 유형에서 처음 보는 결함(예: SHA의 정관 편입 구조, SSA의 자산목록 별지).

예: `"defect_notes": ["범위경계 결함 재현: §4 진술이 별지 4.2를 편입하나 별지 미추출", "TOC 21줄이 별도 문단으로 잡힘 — 과대추출 위험", "SHA governance(정족수·교착)는 정관 제3장에 있고 계약 본문엔 참조만 — 편입 경계 주의"]`

## ★ 절대 규칙 (병렬 안전)
1. **`catalog.sqlite`(운영 DB)에 절대 쓰지 마라.** 단일 writer 원칙 — 너는 **result JSON 파일만** 쓴다.
   DB 반영(store)은 조율자 한 명이 중앙에서 순차 실행한다.
2. **유료 API 자동 호출 금지.** 구독형 에이전트로 파일을 읽고 판단해 작성한다.
3. 배정된 file_key 범위만 처리한다(다른 샤드 파일을 건드리지 마라).
4. **원문을 읽고 판단하라. 키워드만으로 단정하지 말 것** — "키워드 검출 ≠ 존재"(정의·목차·별지표제에
   조항어휘가 박혀 있어도 그 조항이 아니다). 진술(RW) vs 확약(COV) vs 구제(REM)는 주어·어투로 구분.

## 절차
1. 배정 file_key의 원문 txt 캐시를 처음부터 끝까지 정독한다(`open_text.py --file-key K` 또는 txt 직접).
2. 각 조항을 원자 명제로 추출해 아래 스키마의 `items`에 담는다(그 문서 **전 계열 완전 세트**).
3. 최상위에 `review_method: full_read`, `defect_notes`를 채운다.
4. `cs_index/tc_results/<file_key 앞16자>.json`으로 저장한다(디렉터리 없으면 생성). **DB는 건드리지 않는다.**
5. 배정분을 마치면 조율자에게 알린다 — 조율자가 store + Gate 재측정 + 유형별 정답지 편입을 수행한다.

## 출력 스키마 (result JSON)
```json
{
  "file_key": "<배정 file_key>",
  "review_method": "full_read",
  "meta_schema_version": "v4",
  "taxonomy_version": <현재 버전>,
  "defect_notes": ["<문서당 몇 줄>"],
  "items": [
    {
      "item_ref": "RW-0001",              // 계열 접두어-일련번호
      "family": "RW",                     // RW|COV|REM|CP|PAY|DEF
      "taxonomy_id": "RW.TAX.GENERAL",    // term_dict/taxonomy canonical 노드
      "proposition": "<한 문장 명제 — 목차·빈 템플릿 금지>",
      "statement_polarity": "affirmative|negative",
      "subject_role": "seller|purchaser|buyer|company|shareholder|null",
      "counterparty_role": null,
      "action": null, "object_type": null, "effective_time": null,
      "source_kind": "body|schedule|annex", "source_id": null,
      "source_name": "계약서 본문", "source_ref": "¶<문단>",
      "parent_clause_ref": null, "related_item_ref": null,
      "qualifier": {}, "verbatim": "<원문 그대로 짧게>",
      "loc_start": <문단번호>, "loc_end": <문단번호>,
      "normalized": {}, "confidence": "high|medium|low",
      "review_status": "approved"
    }
  ]
}
```
`loc_start`/`loc_end`는 txt 캐시의 `[¶n]` 문단번호다(정답지 좌표로 쓰이므로 정확히). `verbatim`은 원문
그대로(수치·조항 내용 보존), `proposition`은 그 조항의 규범적 요지 한 문장.
