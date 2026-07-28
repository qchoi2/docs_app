# RW 재추출 — 병렬 작업 에이전트 지시서 (2026-07-28)

_다른 코딩 에이전트(GPT/Codex 등)에게 이 파일을 그대로 주면 자기완결적으로 작업할 수 있다.
프로젝트 루트: `docs_app/`. 배경: `.docs/V4_RW_COVERAGE_DEFECT_20260727.md`,
`.docs/V4_GATE_B_SYNTHESIS_20260728.md`._

## 목표
V4 진술보장(RW) 추출이 실질 진술(IP·노무·환경·보험·조세 등)을 대량 누락해 "없는 계약 찾기"가
오답을 낸다. 배정된 계약서들의 **진술 조항 전체(매도인·대상회사 + 매수인)를 읽어 누락된 RW
진술을 원자 항목으로 추출**해 `result JSON`으로 저장한다.

## ★★ 가장 중요한 규칙: 결과 JSON은 그 문서의 RW **전체**를 담아라
조율자 store는 문서 단위로 RW를 **통째로 교체(replace)**한다(해결후보 item만 보존).
따라서 문서마다 그 문서의 진술 조항 **전체를 재정독**해, result JSON의 `items`에 **그 문서의
모든 RW 진술을 빠짐없이** 담아라. **매도인·대상회사 진술뿐 아니라 매수인 진술도 포함**한다:
- **근본적 진술**: RW.AUTHORITY(조직·권한·자격·집행가능성·위반없음·동의불요), RW.CAPITALIZATION
  (주식 소유·부담없음), RW.LITIGATION(소송 부존재) 등 — 소수지분·간이 계약이라도 있으면 반드시 포함.
- **실질 진술**: RW.TAX·RW.ENVIRONMENT·RW.LABOR·RW.IP·RW.FINANCIAL·RW.COMPLIANCE·RW.PERMITS·
  RW.CONTRACTS·RW.REAL_ESTATE·RW.ASSETS·RW.INSURANCE 등 원문에 있는 것 전부.
- **매수인 진술**: 매수인이 하는 진술(권한·자금조달/충분한 자금·no-reliance·독자조사·비상장 등)은
  **RW.BUYER**로 담아라. 이제 매수인 진술도 검색 대상이므로 **배제하지 말고 포함**한다.

**manifest의 `missing_subdomains`는 "과소추출됐던 힌트"일 뿐, 그것만 담으라는 뜻이 아니다.** 원문에
있는 근본+실질 진술을 **모두** 담아야 한다. 일부만(예: 실질만, 또는 근본만) 담으면:
- 근본 진술이 빠지면 → 그 문서는 근본 진술이 영영 안 들어가 "근본 진술만 제공하는 계약" 검색이 안 됨.
- 기존보다 도메인이 줄면 → 조율자 store가 **후퇴로 판정해 저장을 스킵**한다(네 작업이 버려짐).

이미 완전하게 든 문서를 다시 만들 필요는 없지만, **처리하는 문서는 항상 완전한 세트**로 내라.

## ★ 절대 규칙 (병렬 안전)
1. **catalog.sqlite(운영 DB)에 절대 쓰지 마라.** DB는 단일 writer 원칙이다. 너는 **result
   JSON 파일만** 쓴다. DB 반영(store)은 조율자 한 명이 중앙에서 순차 실행한다.
2. **유료 API 자동 호출 금지.** 구독형 에이전트로 파일을 읽고 판단해 작성한다.
3. 배정된 file_key 범위만 처리한다(다른 샤드 파일을 건드리지 마라).
4. 원문을 읽고 판단하라. 키워드만으로 단정하지 말 것(진술 vs 확약 구분은 아래 참조).

## 절차
1. **배정 샤드 받기** (조율자가 k/N 지정):
   `python plan_rw_reextraction.py --out cs_index --shard k/N --manifest cs_index/rw_manifest_k.json`
   → 배정 문서 목록. 각 항목에 `file_key`, `ctype`, `missing_subdomains`.
2. **문서 원문 읽기**: `cs_index/txt/<file_key>.txt` (문단마다 `[¶N]\t본문`). 진술 조항
   (통상 "제N조 진술 및 보장" / "ARTICLE III–IV Representations and Warranties")을 찾는다.
3. **추출 기준**: `.docs/extract_prompt_v4_rw_addendum.md`를 따른다. 핵심:
   - RW 하위영역 체크리스트(조세·노무·IP·환경·소송·준법·인허가·중요계약·부동산·자산·보험·
     개인정보·특수관계자 등)를 **하나씩 확인**해, 있으면 항목으로 추출.
   - **진술(rep) vs 확약(covenant) 구분**: "경업금지 조항을 포함한 계약"을 열거하는 문장은
     RW.CONTRACTS 진술이지 COV 확약이 아니다. (COV/CP/PAY/REM은 이 작업 범위 밖 — RW만.)
4. **result JSON 작성**: `cs_index/rw_reextract_results/<file_key>.json` (아래 스키마).
   원문의 실제 조항으로 `verbatim`과 `loc_start`(¶번호)를 채운다.
5. 다 끝내면 조율자에게 알린다. **store는 실행하지 마라.**

## result JSON 스키마
```json
{
  "file_key": "<key>",
  "reason": "RW 하위영역 재추출",
  "items": [
    {
      "taxonomy_id": "RW.TAX",          // 반드시 실제 RW 노드. 미상이면 도메인노드(RW.TAX 등)
      "proposition": "대상회사는 모든 세무신고·납부의무를 이행하였다.",  // 원자적 명제(한 문장)
      "verbatim": "<원문 그대로 발췌>",
      "loc_start": 99,                   // ¶번호(정수). 여러 문단이면 loc_end도
      "loc_end": 99,
      "statement_polarity": "affirmative", // affirmative|negative|none_exist|not_applicable
      "subject_role": "대상회사",         // 선택
      "parent_clause_ref": "제6조",       // 선택
      "confidence": "high"               // low|med|high
    }
  ]
}
```
- **얇은/소수지분 계약 처리 (중요)**: 소수지분 매각·간단 계약은 매도인이 **근본적 진술만**
  제공한다(조직·권한·자격, 대상주식 소유·부담 없음, 위반 없음, 소송 부존재). 이런 경우에도
  **그 근본적 진술을 반드시 item으로 추출하라**(RW.AUTHORITY / RW.CAPITALIZATION /
  RW.LITIGATION 등). 조세·환경·노무 같은 회사 진술이 아예 없으면 그 영역은 생략(진짜 부재).
  → 결과가 완전히 빈 `items: []`가 되는 경우는 **매도인이 실질적으로 아무 진술도 안 할 때뿐**이며,
  그때는 `"reason"`에 사유를 남겨라(예: `"소수지분 매각: 근본적 진술만 존재 — 회사 진술 없음"` /
  `"진술보장 조항 없음"`). 근본적 진술이 있는데 빈 결과를 내지 마라.
- **taxonomy_id**: 확실한 leaf를 모르면 **도메인 노드**를 써라(아래). 존재하지 않는 leaf를
  지어내지 마라(조율자 store가 미상 leaf를 상위 도메인으로 자동 정규화하지만, 애초에 도메인 노드를
  쓰는 게 깔끔하다). 유효 도메인 노드:
  `RW.TAX RW.LABOR RW.IP RW.ENVIRONMENT RW.LITIGATION RW.COMPLIANCE RW.PERMITS RW.CONTRACTS
  RW.REAL_ESTATE RW.ASSETS RW.INSURANCE RW.PRIVACY RW.FINANCIAL RW.CAPITALIZATION RW.AUTHORITY
  RW.RELATED_PARTY RW.BENEFITS RW.CUSTOMERS_SUPPLIERS RW.PRODUCTS RW.ABSENCE_OF_CHANGES` (전부 실재).
- **매수인 진술은 RW.BUYER**로 **반드시 포함**하라(자금조달·no-reliance·독자조사·권한 등).
  조항이 아예 없는 하위영역은 항목을 만들지 마라(생략 = 진짜 부재).

## 조율자(중앙, 1명)가 하는 일 — 병렬 아님
- 모든 에이전트의 result JSON이 `cs_index/rw_reextract_results/`에 모이면:
  `python store_rw_reextraction.py --mode replace`  (WAL-safe 백업 후 문서단위 저장; 순차 1회)
  - 부분적으로 몇 개 도메인만 추가하는 경우 `--mode add`, 조항 전문을 다시 뽑은 경우 `--mode replace`.
- 저장 후 `python eval_v4_gate.py --pooled`로 회귀, 필요시 `python audit_rw_coverage.py`.
- git commit은 조율자가 한다(에이전트끼리 같은 파일 동시 커밋 금지).

## 충돌 방지 요약
- 에이전트: **result JSON만 쓰기**, 서로 다른 file_key라 파일 충돌 없음.
- DB 쓰기·git commit·store 실행: **조율자 1명이 직렬**로.
