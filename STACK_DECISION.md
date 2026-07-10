# STACK_DECISION — 프론트엔드 스택 결정 (UI-0)

_2026-07-10 · DESIGN_INTEGRATION.md §7 판단 기준 적용._

## 후보

| 기준 | A. 서버 정적 서빙 + vanilla JS | B. htmx | C. SPA (React+Vite) |
|---|---|---|---|
| getdesign 자산 형태 적합성 | 토큰→CSS 변수 직결 | 동일 | 컴포넌트 코드 없음 — 이점 없음 |
| 결합 난이도 | webapp.py(stdlib WSGI)가 정적 파일 1개 서빙 | 동일+라이브러리 파일 | 별도 dev server/빌드 산출물 |
| Windows 로컬 설치·빌드 | 빌드 없음, Python만 | htmx.js 1파일 동봉 | Node.js+npm+빌드 필요 |
| 접근성(aria-live, IME 보호) | 직접 제어 용이 | 부분 자동화 | 라이브러리 의존 |
| 필요 상호작용 수준 | 검색/필터/카드/split view — fetch+DOM으로 충분 | 동일 | 과잉 |

## 선택

- **선택한 스택**: **A. 정적 단일 페이지(HTML+CSS+vanilla JS) + 기존 read-only JSON API**.
  webapp.py가 `static/` 아래 정적 파일을 서빙(UI-1에서 추가)하고, UI는 `/api/*`만 호출.
- **선택 이유**: getdesign.md가 토큰/설명 형태(특정 스택 코드 없음)이므로
  DESIGN_INTEGRATION §7의 기본 권장이 그대로 적용됨. 단일 사용자 로컬 앱에서
  빌드 체인 제거가 유지보수성의 최대 요소. UI MVP 요구(검색창·필터 칩·결과 카드·
  문단 주변 보기·URL 상태 복원·utf-8-sig 내보내기·IME 보호)는 전부 표준 브라우저
  API(fetch, history.pushState, isComposing)로 구현 가능.
- **getdesign.md 자산과의 호환성**: frontmatter 토큰을 `:root` CSS custom property로
  1:1 매핑(`--color-ink`, `--spacing-md`, `--rounded-sm` 등). 컴포넌트 명세는 CSS
  클래스(.feature-card, .button-ghost-sm...)로 전사. 한글 폴백 폰트 스택 적용
  (DESIGN_AUDIT 충돌 1).
- **빌드/배포 복잡도**: 없음. `python webapp.py --out ...` 하나로 API+UI 제공.
  npm/node/번들러/트랜스파일 불요. 오프라인 동작(외부 CDN 미사용).
- **개인 Windows PC 로컬 단일 사용자 앱 관점의 유지보수성**: 파일 3개 내외
  (index.html, app.css, app.js)를 소유자가 직접 읽고 고칠 수 있는 규모 유지.
  Python 의존성 화이트리스트도 그대로 유지됨.

## 명시적 배제

- **React+Vite 등 SPA**: Node 툴체인·빌드 산출물 관리가 단일 사용자 로컬 앱에 과잉.
  getdesign.md가 React 컴포넌트를 제공하지 않으므로 §7 기준상 선택 근거 없음.
  (UI v2에서 리서치 세션·비교 목록의 상태 관리가 크게 복잡해지면 재검토 — 그 경우
  이 문서를 갱신하고 사유를 기록한다.)
- **Tailwind/Bootstrap/기성 CSS 프레임워크**: 사용 가능한 디자인 토큰이 있으므로
  DESIGN_INTEGRATION §3 금지사항("새 디자인 체계 임의 도입 금지")에 해당.
- **htmx**: 외부 라이브러리 동봉이 필요하고, 현재 상호작용 수준에서는 vanilla 대비
  이득이 없음. 서버가 JSON API로 이미 확정되어(web-1) HTML 부분 응답 방식과도 결이 다름.
- **SSE/WebSocket**: BACKEND_REVIEW_PC 지침대로 v2로 유예, MVP는 폴링.
