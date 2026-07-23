# V4 세부 조항 원자 항목 추출 지침

버전: `v4-prompt-8` / taxonomy version: 입력값 사용

## 목적

v3에서 위치가 확정된 `진술보장(RW)`·`선행조건(CP)`·`확약(COV)`·
`정의(DEF)`·`대금/지급(PAY)`·`위반/구제(REM)`을 검색 가능한
원자 명제로 분해한다. v3를 대체하거나 현재 계약에 없는 내용을 추측하지 않는다.

## 출력 최상위 형식

```json
{
  "file_key": "...",
  "meta_schema_version": 4,
  "taxonomy_version": 1,
  "extractor_version": "ai-file-harness-1",
  "prompt_version": "v4-prompt-8",
  "items": [],
  "coverage": {
    "RW": {"body_status": "complete|partial|not_evaluated|unreadable", "annex_status": "complete|partial|not_evaluated|unreadable|no_annex", "reason": null},
    "CP": {"body_status": "complete|partial|not_evaluated|unreadable", "annex_status": "complete|partial|not_evaluated|unreadable|no_annex", "reason": null},
    "COV": {"body_status": "complete|partial|not_evaluated|unreadable", "annex_status": "complete|partial|not_evaluated|unreadable|no_annex", "reason": null},
    "DEF": {"body_status": "complete|partial|not_evaluated|unreadable", "annex_status": "complete|partial|not_evaluated|unreadable|no_annex", "reason": null},
    "PAY": {"body_status": "complete|partial|not_evaluated|unreadable", "annex_status": "complete|partial|not_evaluated|unreadable|no_annex", "reason": null},
    "REM": {"body_status": "complete|partial|not_evaluated|unreadable", "annex_status": "complete|partial|not_evaluated|unreadable|no_annex", "reason": null}
  },
  "source_coverage": [
    {"family": "RW", "source_id": "...", "source_kind": "body|schedule|disclosure_schedule|annex|exhibit", "source_name": "...", "source_ref": "...", "storage_file_key": null, "status": "complete|partial|not_evaluated|unreadable|missing", "reason": null}
  ],
  "taxonomy_candidates": []
}
```

## item 형식

각 item에는 다음을 모두 넣는다.

- `item_ref`: 결과 파일 안에서 유일한 안정적 참조(예: `RW-001`, `PAY-003`)
- `family`: `RW|CP|COV|DEF|PAY|REM`
- `taxonomy_id`: 제공된 활성 taxonomy의 가장 가까운 기존 노드. 새 topic을 임의 ID로 만들지 않는다.
- `proposition`: 한 문장에 한 가지 의미만 담은 원자적 한국어 명제
- `statement_polarity`: `affirmative|negative|none_exist|not_applicable`
- `subject_role`, `counterparty_role`, `action`, `object_type`, `effective_time`: 해당 없거나 불명확하면 `null`
- `qualifier`: 중요성·인식·기간·예외·조건을 구조화한 객체
- `verbatim`: 조항 제목이 아니라 판단을 직접 뒷받침하는 운영문구
- `loc_start`, `loc_end`: verbatim이 실제 존재하는 문단 범위
- `normalized`: 원문 범위에 실제 적힌 수치만 구조화. 빈칸·대괄호 협상값은 확정 수치로 만들지 않는다.
- `confidence`: `low|med|high`
- `review_status`: low 또는 새 분류 후보가 연관되면 `needs_review`, 그 밖에는 `pending`
- `source_kind`, `source_id`, `source_name`, `source_ref`, `parent_clause_ref`: 본문/별지 출처와 본문-별지 연결. 본문 item은 `source_kind=body`, 별지 item은 입력 `source_inventory`의 `source_id`를 그대로 사용한다.
- `related_item_ref`: 같은 원문이 다른 family 기능도 갖는 경우 상대 item의 `item_ref`.
  해당 없으면 `null`; 자기 자신이나 존재하지 않는 item을 참조하지 않는다.

## 핵심 판단 규칙

1. **평가 범위의 모든 하위 항·호를 끝까지 읽고 독립 명제를 전수 item화한다.** 조항 제목이나
   `RW.LABOR` 같은 상위 도메인 item 하나로 요약하고 끝내지 않는다. 예를 들어 하나의 노무
   조항에 법 위반 없음, 근로조건 준수, 장부 외 임금 없음, 미지급 보수 없음이 있으면 4개 이상의
   item으로 분리한다.
2. 한 문장이 여러 의미이면 여러 item으로 분리한다. 기업결합 승인 문구는 CP 승인취득과 COV 신고협력으로 각각 저장할 수 있다.
3. “미지급임금이 없다”는 RW 항목의 `statement_polarity=none_exist`이다. 해당 항목 부재가 아니다.
4. **같은 법적 명제는 표현·언어가 달라도 동일 taxonomy_id를 사용한다.** 예: 노무 관련 법령
   위반이 없다는 문구는 표현 변이에 관계없이 `RW.LABOR.NO_VIOLATION`. 차이는 alias,
   object, qualifier에 저장한다.
   입력의 `taxonomy_catalog`에서 정의·포함/제외 기준·alias를 먼저 확인하고 가장 구체적인
   기존 노드를 사용한다. 하위 노드가 있는데 상위 domain만 사용하는 것은 금지한다.
5. 기존 taxonomy의 포함기준으로 설명되지 않는 독립적인 검색·비교 개념일 때만 candidate를
   만든다. 단순 동의어는 candidate가 아니라 alias 제안이다.
6. 어떤 세부 항목이 없다고 단정하지 않는다. 부재는 저장된 item이 아니라 `coverage`가 body complete이고 annex complete/no_annex인 경우에만 검색 시 계산한다.
7. 본문에서 Schedule·Disclosure Schedule·별지·부속서·첨부를 참조하면 `source_coverage`에
   전부 열거하고 제공된 자료를 모두 읽는다. 별지의 진술·보장, 예외·공개사항도 item으로 만들고
   `parent_clause_ref`로 본문 item과 연결한다.
8. 참조자료가 입력에 없거나 판독 불가하면 해당 source를 `missing|not_evaluated|unreadable`로
   기록하고 aggregate `annex_status=complete`를 사용하지 않는다. 이 상태는 V4 완료가 아니다.
9. 별도 계약의 금액·권리, 비구속 제안, 공란 당사자·대금은 현재 계약의 확정 item으로 승격하지 않는다.
10. candidate에는 `proposed_ko`, `proposed_en`, `family`, `recommended_parent_id`, `distinction_reason`, `loc_start`, `loc_end`, `verbatim`, `nearest_taxonomy_id`를 넣는다.
11. 문서 전체를 무차별 입력하지 않는다. 입력에 제공된 해당 family의 전체 하위 항·호와
    `source_inventory`의 관련 참조자료를 모두 평가한다.
12. **정의(DEF)**는 용어 하나를 하나의 item으로 만들되, 포함요소·제외요소·재포함,
    지정인, 회계원칙, 산식과 threshold가 독립적으로 검색될 필요가 있으면 하위 item으로
    분리한다. 동일한 단어라도 계약별 정의문과 원문 좌표를 보존한다.
13. **대금(PAY)**은 지급 단계별로 payer/payee, 금액·비율, 통화, 시점, 조건,
    지급수단, 환율, 원천징수와 상계를 구조화한다. completion accounts와 locked-box,
    계약금·중도금·잔금, escrow, earn-out, rollover, seller note를 서로 합치지 않는다.
14. **구제(REM)**는 indemnity trigger, cap, basket, de minimis, survival,
    특별배상, 청구절차, 손해범위 제외, 보험·조세혜택 차감, sandbagging, fraud carve-out,
    특정이행, 위약벌과 해제수수료를 각각 원자화한다.
15. 하나의 문구가 여러 기능을 가지면 각 family에 item을 만들고 `related_item_ref`로
    연결한다. 예: payoff(PAY/COV/CP), 계약금(PAY/REM), Fraud(DEF/REM),
    R&W 보험(COV/REM). 단순 중복 item은 만들지 않는다.
16. **SHA 권리**는 `ROFR|ROFO|TAG_ALONG|DRAG_ALONG|PUT_OPTION|CALL_OPTION`을
    서로 합치지 않는다. 각 운영조항에서 권리자, 상대방, 대상주식, 발동조건,
    가격·동일조건, 통지내용, 행사기간, 종결협력, 비용·진술보장 부담을 독립
    명제로 분리한다. `Encumbrance` 정의 안에 이름만 열거된 권리는 COV 운영
    item으로 만들지 않고 해당 정의 item의 포함요소로만 저장한다.
17. **SHA 지배구조**는 이사 지명·선임권, reserved matters, 정보·검사권,
    배당정책, lock-up, 창업자 재직·전념을 각각 가장 구체적인 leaf로 분류한다.
    `COV.GOVERNANCE` 또는 `COV.SHA.EXIT` 하나로 뭉치지 않는다.
18. **자산양수도 범위**는 양수대상자산, 제외자산, 승계채무, 제외채무를 각각
    DEF item으로 만들고, 열거된 자산·채무 종류와 종결 전후 발생시점을 원자화한다.
    실제 이전·인수·면책 의무가 같은 문구에 있으면 COV/PAY/REM 기능을 별도 item으로
    만들고 연결한다.
19. **materiality scrape**는 CP의 bring-down 중요성 기준과 혼동하지 않는다.
    손해배상 조항에서 위반 존재 판단용 scrape와 손해액 산정용 scrape가 모두 있으면
    각각 별도 item 또는 명시적인 `qualifier.scope`로 저장한다.
20. **청구통지**는 통지기한, 필수내용, 송달대상, 지연통지의 권리상실 여부와
    실제 손해 범위 효과를 분리한다. 단순 제3자청구 절차와 청구권 존속기한도
    동일 item으로 합치지 않는다.
21. 배상금에 부과되는 조세·원천징수의 gross-up은 `REM.TAX_GROSS_UP`,
    매매대금 지급단계의 원천징수는 `PAY.WITHHOLDING`으로 구분한다.
    임직원 보상에 관한 280G tax gross-up 진술은 PAY/REM이 아니라 해당 RW
    복리후생 문맥으로 분류한다.
22. 동일한 MAC 표현이라도 기준일 이후 중요 변경의 부재에 관한 진술은
    `RW.ABSENCE_OF_CHANGES`, 종결조건은 `CP.NO_MAC`, MAE 용어의 carve-out
    정의는 `DEF.MAE`로 각각 분리한다.
23. **RW의 상위 도메인으로 요약하지 않는다.** 입력 taxonomy에 하위 leaf가 있으면
    반드시 가장 구체적인 leaf를 사용한다. 특히 다음 명제는 서로 분리한다.
    - 권한: 설립·존속 / 행위능력 / 내부승인 / 구속력 / 무충돌 / 동의 불요
    - 자본구조: 수권·발행주식 / 소유권 / 완전납입 / 잠재주식 / 우선권 /
      주식 제한부담 / 자회사
    - 재무: 회계기준 / 적정표시 / 회계정책 일관성 / 장부 / 내부통제 /
      미공개채무 / 매출채권 / 지급능력
    - 자산: 소유권 / 충분성 / 상태 / 제한부담 / 재고
    - 중요계약: 목록 / 유효성 / 위반 / 해지통지 / 거래에 따른 불이익
    - 소송: 계류 / 제기 우려 / 명령·판결 / 정부조사
    - 조세: 신고 / 납부 / 원천징수 / 조사 / 분쟁 / 조세담보권 /
      기간연장 / 조세배분계약 / 타 관할 / 이전가격
    - 지식재산: 소유권 / 유효성 / 충분성 / 제3자 권리 비침해 /
      제3자의 침해 / 라이선스 / 임직원 권리양도 / 오픈소스 / 영업비밀
    - 환경: 법규준수 / 인허가 / 오염 / 유해물질 / 청구·조사 / 정화의무
    - 보험: 유효성 / 보험료 / 해지통지 / 보험청구 / 보장 적정성
    - 인허가: 필수 인허가 / 유효성 / 조건준수 / 취소·정지 우려
24. 하나의 문장이 여러 RW leaf를 동시에 뒷받침하면 leaf별 item을 만들되,
    같은 verbatim을 사용할 수 있다. 반대로 제목·목차·정의에 이름만 나온 경우에는
    사실 진술 item을 만들지 않는다.
25. **basket 구조**는 기준액 초과분만 배상하는 공제형
    `REM.BASKET.DEDUCTIBLE`과, 기준액을 넘으면 최초 손해부터 전액 배상하는 소급형
    `REM.BASKET.TIPPING`을 구분한다. 단순 threshold만 확인되면 임의 추정하지 않는다.
26. **SHA 운영규칙**에서 의결권 위임, 정족수, 의장 결정권, 등록청구권은 각각
    `COV.SHA.VOTING_PROXY|QUORUM|CASTING_VOTE|REGISTRATION_RIGHTS`로 분리한다.
    정의 또는 제한부담 열거에 이름만 나온 경우에는 운영 item으로 만들지 않는다.
27. **가격·정의 세분화**에서 주식대가, 마일스톤 지급, 언아웃 지급보증,
    정산금 지급기한을 각각 PAY leaf로 분리한다. 회계원칙·데이터룸·공개목록,
    종결 순차입금·목표운전자본은 각각 가장 구체적인 DEF leaf를 사용한다.
28. **구제재원과 손해유형**에서 징벌적 손해 배제, 취소·해제권 포기,
    에스크로 한정구제, 청구대표자, 배상재원 청구순서를 서로 합치지 않는다.
    `REM.CONSEQUENTIAL|EXCLUSIVE_REMEDY|DIRECT_CLAIMS|INDEMNITY` 상위노드 대신
    해당 하위 leaf를 사용한다.

## Taxonomy v8 추가 원자화 규칙

29. **IT 진술보장**은 시스템 충분성과 재해복구·업무연속성을 구분한다.
    사업 운영에 충분하다는 명제는 `RW.IT.SYSTEMS_SUFFICIENCY`, 백업·복구계획과
    장애 시 연속성은 `RW.IT.DISASTER_RECOVERY`로 분리한다.
30. **RWI 확약**은 보험 가입·증권 교부, 보험의 유효한 유지, 보험자의 매도인에
    대한 구상·대위권 제한을 각각 `COV.RWI.PROCUREMENT|MAINTENANCE|
    SUBROGATION_WAIVER`로 분리한다.
31. **제3자청구 절차**는 방어 주도권, 합의·화해 동의, 문서·증언 등 방어 협조를
    `REM.THIRD_PARTY_CLAIMS.DEFENSE_CONTROL|SETTLEMENT_CONSENT|COOPERATION`으로
    각각 기록한다. 같은 문단에 있어도 독립 item으로 만든다.
32. **손해배상 trigger**는 진술보장 위반, 확약 위반, 조세채무, 제외채무를
    `REM.INDEMNITY.RW_BREACH|COVENANT_BREACH|TAX|EXCLUDED_LIABILITIES`로
    구분한다. 하나의 면책문장에 여러 trigger가 열거되면 각 trigger를 item으로 만든다.
33. **손해유형 배제**는 일실이익, 가치감소, valuation multiple 기준 손해를
    `REM.CONSEQUENTIAL.LOST_PROFITS|DIMINUTION_IN_VALUE|MULTIPLE_BASED`로
    나눈다. 단순 `consequential damages` 상위노드로 합치지 않는다.
34. **구제수단 예외**는 배타적 구제의 사기 예외와 특정이행·가처분 예외를
    `REM.EXCLUSIVE_REMEDY.FRAUD_CARVEOUT|SPECIFIC_PERFORMANCE_CARVEOUT`으로
    별도 기록한다.
35. **대금구조**에서 holdback, earn-out 이의절차, escrow 해제·분배는
    `PAY.HOLDBACK|PAY.EARNOUT.DISPUTE|PAY.ESCROW.RELEASE`로 분리한다.

## 금지

- 원문에 없는 수치·주체·시점 보충
- 조항 제목만 verbatim으로 사용
- 상위 도메인 하나로 여러 독립 명제를 뭉쳐 저장
- 본문이 참조한 별지·Disclosure Schedule을 누락한 채 complete 처리
- 기존 taxonomy와 같은 의미를 새 taxonomy 후보로 중복 생성
- 미평가를 부재로 저장
- 새 taxonomy_id를 결과에 직접 생성
- 유료 API 자동 호출
