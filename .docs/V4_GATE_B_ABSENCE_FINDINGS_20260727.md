# Gate B 결과 — 부재형(flagship) 전수 검증 (2026-07-27, Claude)

독립 pooled Gate B(`data/golden_queries_v4_independent.seed.yaml`)의 **부재형 8개 질의**를
전수 사람검증(원문 대조)했다. 검증 방식: 각 질의의 V4 `confirmed_absent` 문서를 원문에서
해당 조항 위치까지 열어, V4의 "없음" 판정이 맞는지(correct) / 실제로는 있는지(incorrect,
V4 오판) / 판단 불가(unknown)로 판정. 검증값은 `data/v4_gate_b_verdicts.json`.
`eval_v4_gate.py --pooled`가 동일 수치를 재현한다.

## 결과: V4 부재정밀도 = **130/171 = 76%** (오판 41건)

| 질의 | 주제 | family | V4 부재정밀도 | 오판 |
|---|---|---|---|---|
| V4A03 | 조세 진술 | **RW(진술)** | **44%** | 10/18 |
| V4A07 | 환경 진술 | **RW(진술)** | **50%** | 9/18 |
| V4A02 | 손해배상 상한 | REM | 67% | 7/21 |
| V4A01 | 경업금지 확약 | COV(특약) | 77% | 5/22 |
| V4A05 | 가격조정 | CP/PAY | 80% | 5/25 |
| V4A06 | no-shop | COV(특약) | 91% | 2/22 |
| V4A04 | 제3자 동의 선행조건 | CP(조건) | 92% | 2/24 |
| V4A08 | sandbagging | REM | 95% | 1/21 |

## 핵심 발견: **부재 정확도가 family에 따라 이봉분포(bimodal)**

- **RW 진술보장 family에서 체계적 과소추출**: 조세(44%)·환경(50%)처럼 거의 모든 M&A 계약에
  존재하는 진술 섹션("Section 4.14 Tax Matters", "대상회사는 환경 법령을 준수한다" 등)을
  V4가 **절반가량 놓친다.** 즉 V4가 "이 진술 없음"이라 해도 실제로는 있는 경우가 많다.
- **특약·선행조건 family는 신뢰 가능**: 경업금지·no-shop·제3자동의·가격조정·sandbagging은
  77~95%로 대체로 정확하다. 이들은 계약마다 존재 여부가 실제로 갈리고, V4가 그 유무를 잘 잡는다.
- 오판의 성격: 전부 **false absence**(있는 걸 없다고 함). 이는 §부재판정에서 가장 위험한 오류
  — 사용자가 "이 조항 없는 계약"을 찾을 때 잘못된 문서를 정답으로 준다.

## 의미와 권고

1. **부재 질의를 family 무차별로 신뢰하면 안 된다.** 특히 **RW 진술 계열(조세·환경, 그리고
   같은 성격의 노무·지재·소송 등 다른 RW.* 진술)** 의 `confirmed_absent`는 현재 신뢰도가 낮다.
   → 이들 family는 coverage가 실제로 `complete`가 아닌데 complete로 표시되고 있을 가능성이 크다
   (앞선 `.docs/PLAN_REVIEW_20260727.md`의 coverage/후보 결함 진단과 일치).
2. **단기 조치**: RW 진술 family의 `confirmed_absent`를 UI/응답에서 `needs_review`로 강등하거나
   경고를 붙인다. 특약/조건 family는 상대적으로 신뢰.
3. **근본 조치**: V4 추출/coverage가 왜 "Section 4.14 Tax Matters" 같은 명백한 진술 섹션을
   놓치는지 조사한다(추출 입력 범위? 진술 섹션 파싱 누락? coverage complete 오표기?). 이것이
   전량 확장보다 우선한다 — 지금 확장하면 같은 결함이 전 코퍼스로 복제된다.

## 남은 Gate B
- 존재형(V4E01~08)·비교형(V4C01~06)은 미완. 존재형은 현재 text-confirmed auto verdict만 반영돼
  있어 V4 vs legacy 상대재현율 비교는 아직 확정 아님.
- 도구: `python verify_gate_b.py cards --review-only`, `... ingest`, `python eval_v4_gate.py --pooled`.
