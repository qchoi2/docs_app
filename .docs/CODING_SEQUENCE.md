# CODING_SEQUENCE — GPT-5.5/Claude Code 단계별 구현 명령
_2026-07-08 · IMPLEMENTATION_BRIEF.md를 단일 기준으로 삼고, 이 문서는 구현 순서를 강제하는 실행 지침이다._

## 원칙
- `CODING_AGENT_RULES.md`를 모든 Step의 상위 코딩 행동 원칙으로 적용한다.
- 전체를 한 번에 구현하지 않는다. 색인 → 검색 → 운영도구 → 평가 → API 보조 순서로 나눈다.
- 각 Step 종료 시 반드시 `pytest` 또는 해당 스모크 테스트를 실행하고, 실행 예시 1개를 남긴다.
- 각 Step 완료 후 테스트가 통과하면 즉시 git commit을 만든다. commit message는 `step-N: <short description>` 또는 `ui-N: <short description>` 형식을 사용한다.
- 테스트 실패 상태에서는 commit하지 않는다. 여러 Step을 하나의 commit에 섞지 않는다.
- DDL·CLI·JSON 스키마는 `IMPLEMENTATION_BRIEF.md`를 따른다. 충돌 시 Brief가 우선한다.
- 유료 API는 호출하지 않는다. Phase 1B는 mock으로만 테스트한다.
- 개선 아이디어는 코드에 임의 반영하지 말고 `NOTES_FOR_OWNER.md`에 남긴다.

## 모든 Step의 공통 진행 루프

각 Step은 아래 순서로 진행한다.

```text
1. git status로 시작 상태 확인
2. 이번 Step의 목표, 수정할 파일, 실행할 테스트를 먼저 적기
3. 해당 Step 범위만 구현
4. py_compile / pytest / 스모크 테스트 실행
5. 실패 시 수정 후 재실행, 그래도 실패하면 commit하지 않고 보고
6. 통과 시 git add로 관련 파일만 stage
7. git diff --cached로 불필요한 변경이 없는지 확인
8. git commit -m "step-N: <short description>"
9. 보고서에 commit hash 또는 commit하지 않은 이유 포함
```

UI 단계는 `ui-N: <short description>` 형식으로 commit한다.


## Step 1 — 저장소 골격 만들기
코딩 모델에게 줄 명령:

```text
IMPLEMENTATION_BRIEF.md와 CODING_SEQUENCE.md를 읽고, 저장소 골격만 만들어라.
requirements.txt, lib/ 패키지, data/ 파일 배치, tests/ 디렉토리, README.md 초안을 만든다.
CLAUDE_v2.md는 저장소 루트의 CLAUDE.md로 복사한다. 아직 핵심 로직은 구현하지 마라.
```

완료 기준:
- `python -m py_compile` 대상 파일이 있으면 통과
- `requirements.txt`에 허용 의존성만 있음
- `data/`에 yaml 파일들이 배치됨

## Step 2 — normalize.py
명령:

```text
lib/normalize.py를 구현하고 단위 테스트를 작성하라.
NFC, 전각→반각, 하이픈/따옴표 표준화, 소프트하이픈/제로폭 제거, 공백 정규화를 검증한다.
색인과 검색이 반드시 같은 normalize()를 import하도록 설계하라.
```

완료 기준:
- `pytest tests/test_normalize.py` 통과
- 한글/영문/전각/하이픈 샘플 테스트 포함

## Step 3 — catalog.py와 DDL
명령:

```text
lib/catalog.py를 구현하라.
IMPLEMENTATION_BRIEF.md §2.4 DDL을 그대로 생성하고, SQLite FTS5 trigram 가용성 점검을 구현하라.
trigram 미지원 시 명확한 오류와 pysqlite3-binary 안내를 출력하고 중단하라.
```

완료 기준:
- 임시 DB 생성 테스트 통과
- `files`, `fts`, `doc_meta`, `clause_index` 테이블 존재 확인

## Step 4 — index_contracts.py 1차
명령:

```text
index_contracts.py의 기본 색인을 구현하라.
파일 스캔, file_key/content_hash, docx/pdf 텍스트 추출, ¶ txt 캐시, files/fts 기록까지 구현한다.
DOCX는 문서 등장 순서대로 문단과 표를 처리하고, 각주·머리글·바닥글은 best-effort로 처리한다.
```

완료 기준:
- 합성 docx fixture 3~4개와 텍스트 pdf 1개 색인 성공
- txt 캐시에 `[¶N]\t` 형식이 유지됨
- FTS para와 txt ¶번호가 일치

## Step 5 — index_contracts.py 2차: 증분·파일럿·리포트
명령:

```text
index_contracts.py에 증분 갱신, --full, --include-misc, --batch-label, --file-list, --sample, --sample-seed, --dry-run을 구현하라.
report_YYYYMMDD.md에는 Brief §2.5의 9개 섹션을 모두 출력하라.
--file-list와 --sample이 동시에 주어지면 오류 처리하라.
```

완료 기준:
- 같은 root/out에서 파일 추가 시 신규만 처리
- 이동/삭제(missing)/복원/내용변경 테스트 통과
- `--file-list` 파일럿 후 전체 증분 확장 테스트 통과
- `--sample N --sample-seed`가 결정적 결과를 냄

## Step 6 — search_contracts.py
명령:

```text
search_contracts.py를 구현하라.
FTS5 trigram 검색, term_dict 확장, --expand strict|normal|broad, --no-expand, RRF, dedup 대표 선택, --show-duplicates, --exclude-drafts, JSON 출력, query_log.jsonl 기록을 구현한다.
```

완료 기준:
- `--kw` 반복은 AND로 동작
- 정확질의 랭크가 확장질의보다 우선됨
- JSON에 `why`, `score_breakdown`, `snippet_paras` 포함
- 검색 결과 없음은 exit code 1, 오류는 2

## Step 7 — stats_contracts.py
명령:

```text
stats_contracts.py를 구현하라.
--by ctype, --by ctype,lang, --status, --errors, --batches, --dedup 옵션을 지원한다.
```

완료 기준:
- status=ok 기준 집계와 전체 status 집계가 구분됨
- `--dedup` 시 dup_group 대표 기준으로 집계됨

## Step 8 — 운영 디버깅 도구
명령:

```text
inspect_file.py와 open_text.py를 구현하라.
inspect_file.py는 파일 1건의 분류, 중복, 실패사유, batch_label, source_signals, doc_meta stale 여부를 출력한다.
open_text.py는 --para와 --search 두 모드를 지원하고, 원문 전체 출력 대신 주변 문단만 보여준다.
```

완료 기준:
- 실제 file_key 기준 조회 가능
- `--show-dup-group` 출력 가능
- `open_text.py --search TERM --context C` 동작

## Step 9 — eval_search.py
명령:

```text
eval_search.py를 구현하라.
golden_queries.yaml의 T1/T2 문항만 실행하고, expected_filter/expected_files/expected_count를 부분채점 방식으로 처리한다.
eval_history.jsonl에 결과를 추가 기록한다.
```

완료 기준:
- 실코퍼스가 없어도 fixture 기준 부분채점으로 완주
- count 성격 문항은 stats_contracts.py 또는 검색 결과를 사용

## Step 10 — README.md 완성
명령:

```text
README.md를 완성하라.
설치, 최초 파일럿 색인, --file-list 파일럿, --sample 파일럿, 검색 예시, 결과 해석, 전체 코퍼스 확장, 평가, manual_overrides.yaml, 백업/복구, 오류 FAQ를 포함한다.
```

완료 기준:
- 사용자가 파일럿 subset → 전체 확장까지 따라 할 수 있음
- cs_index를 PC 로컬 디스크에 두라는 경고 포함
- SQLite WAL 백업 주의 포함

## Step 11 — Phase 1B: budget.py와 answer_quick.py
명령:

```text
검색 품질 확인 후 Phase 1B를 구현하라.
lib/budget.py는 api_budget.yaml을 읽고 예산 상한, 캐시, ledger를 처리한다.
answer_quick.py는 search_contracts.py --json 상위 후보만 사용해 짧은 답변을 생성한다.
실 API 호출 테스트는 금지하고 mock으로만 검증한다. 최종 답변 로그는 agent_log.jsonl에 남긴다.
```

완료 기준:
- per_call/per_run null이면 API 실행 거부
- 상한 초과 시 호출 차단
- cache hit 시 무호출
- `api_ledger.jsonl`과 `agent_log.jsonl` 기록

## Step 12 — plan_extract.py
명령:

```text
plan_extract.py를 구현하라.
Phase 2 추출 후보를 SPA/SHA/SSA, final/signed, dedup 대표, query_log 빈도 기준으로 추천한다.
API 호출이나 doc_meta 기록은 하지 않는다.
```

완료 기준:
- 추천 목록과 추천 사유 출력
- limit 옵션 동작



## UI-0 — 디자인 인수(getdesign.md)
명령:

```text
CLI 검색 MVP가 안정화된 뒤 UI 구현을 시작하라.
먼저 getdesign.md를 읽고 DESIGN_INTEGRATION.md 절차에 따라 DESIGN_AUDIT.md를 작성하라.
아직 UI 코드는 만들지 말고, 사용할 디자인 자산과 부족한 항목만 정리하라.
```

완료 기준:
- DESIGN_AUDIT.md 작성
- 사용 가능한 색상/폰트/간격/컴포넌트 목록 정리
- UI_PRODUCT_SPEC.md와의 충돌 또는 부족한 항목 기록

## UI-1 — 읽기 전용 검색 UI
명령:

```text
UI_PRODUCT_SPEC.md의 UI MVP 범위만 구현하라.
검색창, 고급 필터, 필터 칩, 코퍼스 상태 배너, 결과 카드, 문단 주변 보기, 중복본 보기, 최근 검색, Markdown/CSV 내보내기를 구현한다.
검색 결과 카드에는 why, matched_terms, score_breakdown, ¶번호, draft 여부, 중복 수를 표시하라.
```

완료 기준:
- 검색 상태가 URL 또는 UI state로 복원 가능
- 최근 검색이 UI에 표시되고 다시 실행 가능
- 파일럿 코퍼스 배너가 항상 표시됨
- 결과 카드에서 문단 주변 보기로 이동 가능

## UI-2 — 운영 UI
명령:

```text
색인 상태 대시보드와 실패 파일 목록을 구현하라.
saved searches, result feedback, manual_overrides 후보 export를 구현한다.
```

완료 기준:
- status/error/batch 통계 표시
- 실패 파일별 error_reason과 권장 조치 표시
- 저장된 검색을 생성/실행/삭제 가능
- 결과 피드백이 result_feedback에 기록됨

## UI-3 — 리서치 UI
명령:

```text
비교 목록, 북마크/메모, 리서치 세션을 구현하라.
선택한 문단을 Markdown/CSV로 내보낼 수 있게 하라.
```

완료 기준:
- 검색 결과를 비교 목록에 추가/삭제 가능
- session_items에 선택 문단이 저장됨
- user_marks에 즐겨찾기/메모가 저장됨

## UI-4 — AI 보조 UI
명령:

```text
선택한 결과만 근거로 AI 요약/비교표를 생성하는 화면을 구현하라.
file_key와 ¶번호를 반드시 인용하고, 파일럿 코퍼스인 경우 주의 문구를 답변 상단에 표시하라.
```

완료 기준:
- 검색 결과에 없는 일반론 생성 금지
- API 예산 상태 표시
- agent_log.jsonl 기록
- 사용자가 선택하지 않은 문서를 근거로 쓰지 않음

## 최종 보고 형식
마지막 보고는 아래 형식으로 한다.

```text
1. 구현한 파일 목록
2. 실행한 테스트와 결과
3. 생성한 git commit 목록(hash + message)
4. Brief §6 DoD 체크리스트
5. 적용한 기본값
6. 남은 제한사항/질문
7. 파일럿 실행 권장 명령
```
