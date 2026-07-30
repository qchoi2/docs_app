# extract_prompt_v4 — 하위영역 present/absent 공통 부록 (2026-07-29)

_근거: 환경(RW.ENVIRONMENT) 사건 — coverage가 blanket `complete`로 찍혔지만 하위영역은
미추출이라, "환경 진술 없는 계약" 부재판정이 대량 오답이 됐다(30건 진짜 누락 확인). 정독조차
2/9에서 놓쳤다. 원인은 읽기 실패가 아니라 **"이 하위영역을 확인했는가?"를 강제하는 장치의 부재**다.
이 부록은 그 강제 장치를 전 family(RW·PAY·DEF·COV·CP·REM)로 일반화하고, 저장 시 자동 검증에 연결한다._

## 규칙 1 — 하위영역은 present/absent를 **명시**한다 (침묵 금지)

한 family를 재추출할 때, 그 family의 taxonomy 하위영역(2단계 노드, 예: `RW.LABOR`, `PAY.EARNOUT`)을
**하나씩** 확인하고 각각 **둘 중 하나**를 반드시 한다:

1. 해당 진술/조항이 **있으면** → 원자 명제를 `<FAMILY>.<DOMAIN>.*` taxonomy_id로 item 추출
   (verbatim + ¶좌표). 여러 명제면 여러 item으로 분리.
2. **없으면** → 그 하위영역을 `present=false`로 명시(확인한 조항 범위를 근거로). **그냥 생략하지 않는다.**

**어느 쪽도 하지 않은 하위영역이 하나라도 있으면 `body_status=complete`를 주지 마라(→ `partial`).**
침묵한 하위영역은 "미평가"이지 "부재"가 아니다 — 부재판정을 오염시킨다.

family별 하위영역 목록은 taxonomy가 정본이다:

```
sqlite3 cs_index/catalog.sqlite \
  "SELECT taxonomy_id, canonical_ko, canonical_en FROM v4_taxonomy_node
   WHERE family='RW' AND depth<=2 ORDER BY taxonomy_id"
```

(RW의 서술형 체크리스트는 [extract_prompt_v4_rw_addendum.md](extract_prompt_v4_rw_addendum.md) 참조.
굵은 누락 상습영역: RW.LABOR·IP·ENVIRONMENT·REAL_ESTATE·INSURANCE·PRIVACY.)

## 규칙 2 — 저장이 자동 검증한다 (absence recall-net)

`store_rw_reextraction.py` / `store_pay_reextraction.py`는 각 문서 저장 직후
`lib/absence_net.doc_absence_suspects`를 돌린다. **문서 본문이 어떤 하위영역 어휘를 분명히 언급하는데
그 하위영역 item이 0개면** 그 문서를 `absence_suspects`로 리포트한다 (환경 누락과 같은 병리).

- 어휘는 `data/term_dict.yaml`(+`v4_term_mapping.yaml`) 동의어 + taxonomy 노드명 + `TERM_SUPPLEMENTS`에서
  자동 도출한다. 손으로 유지하지 않는다.
- 이 검증은 **비파괴·비차단**(advisory)이다 — 저장을 막지 않고 플래그만 남긴다.
- 운영자는 실행 리포트의 `absence_suspect_count > 0`을 **`complete` 수용 전 재확인 신호**로 다룬다:
  진짜 누락이면 그 하위영역을 add로 보충, 오탐(정의문·복합문 등)이면 확인 후 넘어간다.

→ 결론: 추출자는 규칙 1로 침묵 누락을 **선제 차단**하고, 저장 검증이 규칙 1의 빈틈을 **사후 포착**한다.
정독을 반복하는 게 아니라, 정독(깊이) + 자동 그물(넓이)로 상호보완한다.

## 표준 감사 (전 하위영역 일괄)

```
# 전 family 스윕 — 하위영역별 suspect(언급O·item X) 건수 랭킹 (읽기 전용, API 0)
python subdomain_absence_pool.py --all

# 한 하위영역 상세 (문서목록 + 근거 스니펫)
python subdomain_absence_pool.py --subdomain RW.LABOR
```

`vocab_too_broad=true`로 표시된 하위영역은 어휘가 너무 일반적이라(단일 흔한 단어) 판별력이 없다는 뜻 →
그 하위영역은 `TERM_SUPPLEMENTS`에 정제 어휘를 보강한 뒤 재감사한다(term_dict 직접 수정 금지, 소유자 승인 병합).
