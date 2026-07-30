# Taxonomy 확장 권고 (2026-07-31, full_read 근거) — 소유자 결정 대기

_근거: 조율자 소유 Sonnet-5 정독(T-C SHA 파일럿 98b037 + CP/COV/REM 측정 SPA 정독들).
배경: [[spa-shaped-taxonomy-sha-mismatch]], [NOW.md](../NOW.md) 문서-클래스 구분._

## 문제
현재 taxonomy 6-family(RW·CP·PAY·REM·COV·DEF)는 **매매/인수계약 해부구조**다. 정독으로
**어느 노드에도 담기지 않는 실재 조항 도메인**이 반복 확인됐다. 이 노드들이 없으면 그 조항들은
부모/오노드에 low-confidence로 임시배치되거나(캐치올 재발) 아예 누락된다.

## 권고 신설 도메인 (근거 문서와 함께)

| 우선 | 신설 | 성격 | 근거 |
|---|---|---|---|
| **1** | **`SEC` (담보·보증) 신규 최상위 family** — 질권·저당·양도담보·보증의 설정/유지/실행/해지/우선순위 | 교차적(투자·담보부 매매 공통) | SHA 98b037: §14.2 신용보강 + 주식질권설정계약 3건이 **문서의 ~40%**인데 커버리지 0. SPA 59e6ec·00c09f: 질권설정 확약이 `COV.FURTHER_ASSURANCES`에 뭉개짐 |
| **2** | **SHA 경제적권리 도메인** (`COV.SHA.ECONOMICS.*` 또는 신규): 청산우선권·상환권(RCPS)·전환조건·옵션 워터폴/가격·배당우선 | SHA·투자 클래스 | SHA 98b037 §14.5(상환·청산우선 포기) — 담을 노드 없어 `COV.SHA` 부모 low-conf |
| **3** | **재무유지약정 노드** `COV.FINANCIAL_MAINTENANCE`: 레버리지·재무비율 유지 | 투자·차입 딜 | SHA 98b037 §14.3(Net Debt/EBITDA≤9x) → 임시 `COV.RESTRICTED_ACTIONS` |
| 4 | **`COV.IP_TRANSFER`**(지재권 이전 확약) · **`COV.CORPORATE_ACTION`**(주총·EGM 소집 확약) | 인수 클래스 | SPA 59e6ec: 둘 다 `COV.FURTHER_ASSURANCES`에 medium-conf로 뭉개짐 |
| 5 | **일반조항(boilerplate) 귀속**: 통지방식·counterparts·완전합의 등 | 전 클래스 | 여러 문서에서 노드 없어 REM/COV로 강제 or skip. REM의 일반조항 가지(GOVERNING_LAW·ENTIRE_AGREEMENT·SEVERABILITY 존재)에 `REM.NOTICE_MECHANICS`·`REM.COUNTERPARTS` 추가 권고 |

## 비-권고 (오해 방지)
- **CP.RESIGNATION·CP.DELIVERABLE는 이미 존재** — 문제는 노드 부재가 아니라 자동추출이
  "확약 조항(제6조)" 표제만 보고 COV로 오분류하는 **추출 결함**이다(CP↔COV 오분류). taxonomy가
  아니라 재추출로 해결.
- **QUORUM 등 SHA governance 죽은노드**는 노드는 있으나 그 조항이 해당 문서에 실제로 없거나
  자동추출이 generic stub으로 붕괴시킨 것 — 노드 신설 불필요, 재추출/정독 대상(센서스 v2 참조).

## 처리 원칙
1. **taxonomy 변경은 소유자 게이트**(dict_version·taxonomy_version 상승, 병합 전후 eval 회귀 확인).
2. **신설 전에는 SHA·투자 클래스 full_read를 store하지 마라** — 노드 없이 저장하면 오배치가 굳는다
   (SHA 파일럿 98b037은 이 원칙대로 **store 보류**, 정답지 진단용으로만 사용).
3. 신설 후: 영향 문서를 재추출/재정독해 항목이 올바른 노드에 착지하게 한다.
4. `SEC` family 신설 시 **부재 게이트·doc-class 맵·search family 필터**에 파급됨 — 함께 반영.

## 열린 질문 (소유자 판단)
- 경제적권리를 `COV.SHA.ECONOMICS`(SHA 하위)로 둘지, 클래스 독립 도메인으로 승격할지.
- `SEC`를 최상위 family로 둘지, 각 계약의 확약/조건 하위로 분산할지 — 정독상 **독립 family가
  타당**(질권설정계약이 별도 문서로도 존재하고, 딜 그룹핑에서 부속문서 role로 쓰임).
