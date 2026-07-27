# T3 v3 정밀 보강 파일럿

## 목표

현재 v2의 조항 존재·위치 초벌 데이터를 당사자·대금·정규화 수치·유형별 조항까지
검색 가능한 정밀 메타데이터로 보강한다. v3 파일럿은 기존 v2 코퍼스를 덮어쓰지 않는다.

## 구현된 안전장치

- v2와 v3 입출력 폴더 분리
- v3 유형별 필수 조항 누락 거부
- present 조항의 문단 위치·요약·원문·신뢰도 강제
- 당사자·대금·정의의 `evaluated` 상태 강제
- 정규화 수치 타입 및 위치 범위 검증
- 결과 저장 전 자동 근거 감사
- v2 문서를 구조화 조건의 부재로 오판하지 않고 미평가로 분리
- DB 저장은 기존 `enrich_contracts.py` 단일 경로만 사용

## 파일럿 현황

- 표본: 60건
- 유형: 14개
- 언어: 국문 39, 영문 18, 국영문 3
- Draft 상태: Draft 18, 비Draft 21, 미상 21
- 기존 신뢰도: low 47, med 9, high 4
- 입력 생성: 완료
- v3 결과 생성: **60/60 완료**
- 자동 감사: **pass 42, review 18, error 0, pending 0** (`review`는 초안·공란에 따른 신뢰도 표시)
- 사람 검수: **60/60 승인 완료** (2026-07-16)
- DB 저장: **v3 60건 완료**
- V4-0 게이트: **통과**

생성물은 `cs_index` 아래에 있으며 Git에는 포함하지 않는다.

- `t3_v3_pilot_manifest.json`
- `t3_v3_pilot_review.md`
- `enrich_inputs_v3/<file_key>.json`
- `t3_v3_audit_report.json`
- `t3_v3_human_approval_60.json`
- `t3_v3_v4_0_gate.md`
- `enrich_progress_v3.json`

## 실행 순서

```powershell
# 1. 표본과 입력 생성(완료)
python plan_t3_v3_pilot.py --out cs_index --limit 60 --write-inputs

# 2. AI 클라이언트가 입력을 읽고 같은 file_key로 결과 작성
# 입력: cs_index/enrich_inputs_v3
# 결과: cs_index/enrich_results_v3
# 지침: .docs/extract_prompt_v3.md

# 3. DB 저장 전 자동 감사
python audit_t3_v3.py --manifest cs_index/t3_v3_pilot_manifest.json

# 4. 사람 승인 파일이 manifest 전체를 포괄할 때만 정확한 60건 저장(완료)
python store_t3_v3_manifest.py --out cs_index --manifest cs_index/t3_v3_pilot_manifest.json `
  --approval cs_index/t3_v3_human_approval_60.json `
  --input-dir cs_index/enrich_inputs_v3 --result-dir cs_index/enrich_results_v3
```

## 구조화 검색 계약

CLI·웹 API·MCP는 다음 v3 조건을 공유한다.

- 당사자명·역할
- 지급 방식과 거래대금 범위
- 손해배상 상한 비율 범위
- 존속기간 범위
- 준거법
- 법원·중재기관

v3 값이 없는 문서는 결과에서 조용히 제외하지 않고 `needs_review`의 미평가 건수로 알린다.

## 승인 기준

1. 필수 태그가 계약 유형별로 빠짐없이 평가됨
2. present 조항 위치와 verbatim이 실제 본문과 일치
3. 정규화 수치가 verbatim과 모순되지 않음
4. low 전수 및 med 유형별 표본 검수 완료
5. 오류 패턴을 프롬프트에 반영한 뒤 표본 재검증
6. 승인 전 전량 v3 재추출 금지

## 다음 단계

파일럿 60건의 사람 승인이 끝나면 v4 세부 조항 원자 항목 계층으로 진행한다.
계획은 `.docs/V4_PLAN.md`를 따른다(v3 승인이 V4-0 게이트).

## 사람 확인이 필요한 결정

- 표본 결과의 법률적 의미가 원문과 일치하는지 최종 승인
- 오류 패턴을 반영한 프롬프트 변경 승인
- 파일럿 통과 후 1,999건 전량 재추출 승인
- 골든 질의의 실제 정답 file_key 확정
