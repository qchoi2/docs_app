# CODING_AGENT_RULES — GPT-5.5 / Claude Code / Codex 코딩 원칙
_2026-07-08 · Andrej Karpathy식 LLM 코딩 원칙을 이 프로젝트에 맞게 구체화한 지침._

## 1. Think before coding

코드를 쓰기 전에 먼저 짧게 적는다.

```text
- 이번 Step의 목표
- 수정할 파일
- 수정하지 않을 파일
- 적용할 스키마/CLI 계약
- 실행할 테스트
```

모호한 부분을 크게 해석해서 임의 구현하지 않는다. `IMPLEMENTATION_BRIEF.md`와 `CODING_SEQUENCE.md`가 우선한다.

## 2. Simplicity first

- MVP 밖 기능을 넣지 않는다.
- 벡터DB, 웹 UI, OCR, 파일 감시, API 실호출은 지정 단계 전까지 금지한다.
- 작고 검증 가능한 함수로 나눈다.
- 설정값은 YAML 또는 CLI로 두고 코드에 하드코딩하지 않는다.

## 3. Surgical changes

- 요청받은 Step에 필요한 파일만 수정한다.
- unrelated refactor 금지.
- DDL, CLI 옵션, JSON 스키마를 임의 변경하지 않는다.
- 변경이 필요하면 코드에 반영하지 말고 `NOTES_FOR_OWNER.md`에 제안한다.

## 4. Verify every step

각 Step 후 다음 중 하나 이상을 실행한다.

```text
pytest
python -m py_compile ...
스모크 명령 1개
```

실패하면 다음을 기록한다.

```text
- 실패 명령
- 에러 요약
- 원인
- 수정 내용
- 재실행 결과
```

## 5. No hidden magic

- 조용한 실패 금지.
- 실패 파일은 `status`와 `error_reason`으로 드러낸다.
- fallback을 쓰면 report에 표시한다.
- 검색 확장, dedup 대표 선정, draft 제외 등 결과에 영향을 주는 판단은 `why` 또는 `score_breakdown`에 표시한다.

## 6. Determinism

- 같은 입력이면 같은 결과가 나와야 한다.
- `--sample`은 `--sample-seed`로 재현 가능해야 한다.
- 정렬 tie-breaker를 명시한다.
- 현재 시각은 로그/리포트 timestamp에만 사용한다.

## 7. User data safety

- 원본 계약서 파일은 읽기 전용으로 취급한다.
- `cs_index/`는 PC 로컬 디스크에 둔다.
- 색인 중 원본을 이동/수정/삭제하지 않는다.
- API 실호출은 사용자가 명시적으로 허용하기 전까지 금지한다.
- Haiku/Sonnet/Opus 런타임 API 경로(G1.5/A9/A10/G2)는 사용자의 ANTHROPIC_API_KEY와 api_budget.yaml 상한이 모두 있을 때만 동작한다.
- Codex 사용을 위해 OpenAI API key를 입력받거나 저장하지 않는다. Codex는 ChatGPT 구독계정 로그인 기반 도구로만 다룬다.

## 8. UI coding rules

UI 단계에서는 다음을 지킨다.

- `getdesign.md`를 먼저 확인한다.
- `DESIGN_AUDIT.md`를 작성한다.
- 검색 결과 카드에는 근거와 ¶번호를 숨기지 않는다.
- AI 답변은 검색 결과 확인 이후의 보조 기능으로 둔다.
- 검색 히스토리, 저장된 검색, 비교 목록은 사용자의 리서치 흐름을 보존하기 위한 기능으로 구현한다.
- Agent Setup Wizard는 상태 진단과 절차 안내만 제공한다. 계정 비밀번호, OAuth/세션 토큰, 로그인 코드를 수집·저장하지 않는다.
- API key 입력이 필요한 기능은 별도 Runtime API Settings에서만 다룬다. Runtime API Settings에는 `ANTHROPIC_API_KEY` 입력창을 만들고, 저장 후 키 전문은 마스킹한다. Codex용 OpenAI API key 입력란은 만들지 않는다.
- 초기 UI에서는 설치 명령 자동 실행을 만들지 말고, 복사 가능한 명령어와 다시 검사 버튼을 우선 구현한다.
- 고급 필터의 ctype/lang 목록을 UI 코드에 하드코딩하지 말고 catalog facets에서 동적으로 불러온다.
- 첫 실행 원본 폴더 설정은 브라우저 폴더 피커가 아니라 경로 텍스트 입력 + 백엔드 검증 API로 구현한다.
- 검색창 Enter 처리에는 한글 IME composition(`isComposing`, `keyCode==229`) 방어를 넣는다.
- CSV 다운로드는 한국어 Windows Excel 호환을 위해 `utf-8-sig`로 만든다.
- 매칭어 하이라이트가 원문 표면형에서 실패하면 하이라이트 없이 정상 표시한다.
- 검색 상태(query/filters/expand_mode)는 URL query parameter로 복원 가능하게 한다.
- search warnings와 AI disabled 사유를 사용자에게 숨기지 않는다.
- 진행률·검색 완료는 aria-live로 알리고, split view 키보드 포커스 이동 규칙을 둔다.

## 9. Git commit discipline

각 Step은 테스트 또는 스모크 테스트가 통과한 상태에서 하나의 git commit으로 닫는다.

```text
- Step 시작 전: git status로 작업트리 상태를 확인한다.
- Step 진행 중: 해당 Step 범위 밖 파일은 수정하지 않는다.
- Step 완료 후: pytest 또는 지정 스모크 테스트를 실행한다.
- 테스트 통과 후: git add/commit을 수행한다.
- commit message 형식: step-N: <short description>
- UI 단계 commit message 형식: ui-N: <short description>
```

금지사항:

```text
- 테스트 실패 상태에서 commit 금지
- 여러 Step을 하나의 commit에 섞기 금지
- unrelated refactor를 commit에 포함 금지
- 생성물/캐시/원본 계약서 파일을 실수로 commit 금지
```

테스트가 실패했지만 중간 상태를 보존해야 할 때에는 commit하지 말고, 실패 명령과 원인을 보고한 뒤 사용자 지시를 기다린다.

## 10. 최종 보고 형식

```text
1. 이번 Step 목표
2. 수정한 파일
3. 실행한 테스트
4. 결과
5. 생성한 git commit 또는 commit하지 않은 이유
6. 남은 제한사항
7. 다음 Step 제안
```
