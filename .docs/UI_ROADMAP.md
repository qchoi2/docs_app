# UI_ROADMAP — 웹 UI 단계별 구현 순서
_2026-07-08 · CLI 검색 MVP 이후 UI를 붙일 때의 단계별 로드맵._

## UI-0 — 디자인 인수

목표: getdesign.md 기반 디자인 자산 확인.

산출물:

```text
- DESIGN_AUDIT.md
- STACK_DECISION.md
- UI 구현에 사용할 색상/폰트/간격/컴포넌트 목록
```

`STACK_DECISION.md`에는 서버 렌더링+경량 JS(htmx/vanilla)와 SPA(React+Vite 등)를 비교하고, 개인 Windows PC 로컬 단일 사용자 앱이라는 배포 조건에서 어떤 스택을 선택했는지 명시한다. getdesign.md 자산이 컴포넌트 코드인지, 토큰/스크린샷인지에 따라 판단하되 코딩 에이전트가 임의로 무거운 SPA를 선택하지 못하게 한다.

명령 예:

```text
getdesign.md를 읽고 DESIGN_INTEGRATION.md 절차에 따라 DESIGN_AUDIT.md를 작성하라.
아직 UI 코드는 만들지 말고, 사용 가능한 디자인 자산과 부족한 항목만 정리하라.
```


## UI-0.2 — PC 로컬 첫 실행 온보딩

목표: 사용자가 원본 폴더, 인덱스 저장 위치, 최초 색인, 선택 기능 설정을 한 번에 이해하게 한다.

필수 기능:

```text
- 원본 계약서 루트 경로 텍스트 입력 + 백엔드 검증(`POST /api/settings/root-path/validate`)
- 인덱스/캐시/로그 저장 위치 표시
- 최초 색인 시작
- API key/예산은 선택 설정으로 안내
- Claude Code/Codex는 개발·배치 보조용임을 표시
```

금지:

```text
- 첫 실행에서 API key 입력을 필수로 만들기
- 원본 폴더를 수정하는 것처럼 보이는 문구
- NAS/서버 배포를 기본 경로로 안내
```

## UI-0.3 — 작업 진행률/상태 UX

목표: 색인·재색인·AI 답변 생성 같은 장시간 작업을 안전하게 표시한다.

필수 기능:

```text
- job 상태: idle/running/failed/completed
- 진행률과 현재 파일
- MVP 갱신 방식: `GET /api/jobs/{id}` 1~2초 폴링
- 취소/실패 파일만 재시도
- raw traceback 대신 표준 오류 메시지
- 진행률/완료/실패 알림은 aria-live에 반영
```

## UI-1 — 읽기 전용 검색 UI

목표: CLI 검색 기능을 웹에서 사용할 수 있게 한다.

필수 기능:

```text
- 자연어 검색창
- catalog facets 기반 고급 필터(ctype/lang 하드코딩 금지)
- 필터 칩
- URL query parameter로 query/filters/expand_mode 복원
- 한글 IME composition 중 Enter 검색 방지
- 코퍼스 상태 배너
- 결과 카드
- 문단 주변 보기
- 중복본 보기
- 최근 검색
- Markdown/CSV 내보내기(CSV는 utf-8-sig)
- search warnings 배지(`short_term_fallback`, `unsearchable_docs` 등)
- 매칭어 하이라이트 실패 시 원문 표시 폴백
```

금지:

```text
- AI 요약 자동 생성
- 원본 파일 수정
- 색인 자동 실행
```

## UI-2 — 운영 UI

목표: 파일럿/전체 운영 상태를 사용자가 이해하고 보정할 수 있게 한다.

필수 기능:

```text
- 색인 상태 대시보드
- 실패 파일 목록
- batch별 통계
- saved searches
- result feedback
- manual_overrides 후보 export
```

## UI-3 — 리서치 UI

목표: 검색 결과를 실무 리서치 자료로 모으고 재사용하게 한다.

필수 기능:

```text
- ui_state.sqlite에 영속 저장되는 기본 비교 목록
- 북마크/메모
- 리서치 세션
- 선택 문단 Markdown/CSV export
```

## UI-4 — AI 보조

목표: 선택한 검색 결과만 근거로 짧은 요약/비교표를 생성한다.

필수 기능:

```text
- 선택 결과 기반 요약
- 선택 문단 비교표
- file_key/¶번호 인용
- API 예산 표시
- agent_log 기록
```

금지:

```text
- 검색 결과에 없는 일반론 생성
- 파일럿 결과를 전체 경향처럼 표현
- 근거 없는 조항 비교
```

## 구현 우선순위

1. UI-0
2. UI-0.2
3. UI-0.3
4. UI-1
5. UI-2
6. UI-3
7. UI-4

CLI 검색 품질이 안정되기 전에는 UI-4로 가지 않는다.


## 2026-07-09 UI Hardening 반영사항

```text
- 필터 옵션은 catalog DISTINCT ctype/lang/batch에서 동적으로 생성한다.
- 브라우저 폴더 피커 절대경로 취득에 의존하지 않고, 경로 입력 + 백엔드 검증을 사용한다.
- 검색창은 한글 IME composition Enter를 무시한다.
- CSV export는 utf-8-sig로 생성한다.
- normalize() 기준 검색과 원문 표면형 하이라이트 불일치 시 하이라이트 없이 표시한다.
- job 진행률은 MVP에서 폴링으로 구현하고 SSE/WebSocket은 v2로 미룬다.
- warnings는 결과 요약줄 배지로 표시한다.
- AI disabled 상태는 원인별 문구와 설정 링크를 제공한다.
- 비교 목록은 MVP에서도 새로고침에 보존한다.
- 검색 상태는 URL에 반영한다.
- UI-0 산출물에 STACK_DECISION.md를 포함한다.
- 접근성: aria-live, split view 포커스 이동, 검색창 포커스 중 j/k 비활성화.
```
