# DESIGN_AUDIT — getdesign.md 디자인 자산 감사 (UI-0)

_2026-07-10 · DESIGN_INTEGRATION.md §4 양식 기준. UI 코드는 아직 작성하지 않음._

## 확인한 디자인 소스

- getdesign.md 경로: 저장소 루트 `getdesign.md` (version: alpha, "Vercel Analysis" — Geist 시스템)
- 참조 파일: **없음** — getdesign.md 단일 문서로 완결. YAML frontmatter에 토큰
  (colors/typography/rounded/spacing/components) + 본문 설명. 별도 CSS/컴포넌트 코드/
  스크린샷/Figma 참조 없음.
- **데이터 결함 1건**: `typography.label-sm.fontWeight` 줄에 무관한 텍스트 혼입
  ("500 burada komikledin mi ...") → 엄격한 YAML 파서가 실패할 수 있음.
  감사 판단: 값은 `500`으로 간주. 소유자가 getdesign.md 원본 정리 권장.

## 사용 가능한 토큰

- **색상**: ink 사다리(#171717 ink → #4d4d4d body → #8f8f8f mute → #a1a1a1 faint),
  표면(#fafafa canvas / #ffffff elevated / #f2f2f2 soft), 경계 #ebebeb hairline,
  링크 #0070f3(+deep/soft), error #ee0000(+deep), warning #f5a623(+soft/deep),
  장식용 gradient 3종(develop/preview/ship). 성공 상태는 link 블루가 겸함.
- **폰트**: Geist Sans(대체: Inter) / Geist Mono(대체: JetBrains Mono).
  11개 타입 토큰 (display-xl 48/600/-2.4px ~ body-sm 12/400, mono-eyebrow, code).
  웨이트는 600(헤딩)/500(버튼·라벨)/400(본문)만 사용.
- **간격**: 4px 기본 단위, xxs 4 ~ section 128 (10단계).
- **radius/shadow**: 6px(기능 chrome) / 12~16px(카드) / pill 100px(마케팅 CTA) /
  full. 그림자 3단계(Flat: hairline만 / Whisper: 1px 미세 / Floating: 저알파 레이어).

## 사용 가능한 컴포넌트

- 버튼: button-primary(-sm), button-secondary, button-ghost-sm, button-category-pill,
  button-icon-circular — 앱 chrome은 6px 사각(button-*-sm) 계열 사용
- 입력창: text-input (elevated + hairline + 6px)
- 카드: feature-card(12px), feature-card-elevated, pricing-card(16px)
- 테이블: **없음** (hairline + body-md로 직접 구성)
- 배지: **없음** (button-category-pill 축소형 + warning-soft/link-soft 배경으로 파생)
- 사이드바: **없음** (nav-bar/footer 패턴의 hairline 구분 원칙으로 파생)
- 기타 제공: nav-bar, nav-link, code-block, logo-strip, hero-band, cta-band, footer

## UI_PRODUCT_SPEC 적용 계획

- **검색 화면**: 상태 배너=logo-strip 변형(파일럿 경고 시 warning-soft 배경),
  검색창=text-input 확대(body-lg), 검색 버튼=button-primary-sm(앱 컨텍스트이므로
  pill 아닌 6px 사각), 필터 칩=category-pill 축소형+삭제 x, 고급 필터=feature-card 패널
- **결과 카드**: feature-card + heading-md 파일명 + mono-eyebrow로 file_key 표기,
  "왜 검색됐나"=body-md 리스트, 매칭 문단=code-block(¶ 좌표는 Geist Mono),
  배지(정확/동의어/넓은 확장/Draft/중복 대표본)=파생 배지 — broad는 warning 계열 필수
- **문단 뷰어**: code-block 기반 split view 우측 패널, ¶번호 mono, 현재 문단 link-soft 하이라이트
- **히스토리 사이드바**: hairline 좌측 구분 + nav-link 목록 (MVP는 최근 검색만)
- **대시보드**: pricing-card 그리드에 status 집계, error_reason 테이블은 hairline 행 구분

## 충돌/부족한 부분

1. **한글 타이포그래피**: Geist는 한글 글리프 미지원 → 폰트 스택에 한글 폴백 필수
   (`Geist, Pretendard, "Malgun Gothic", Inter, sans-serif`). display 급의 음수
   letter-spacing(-2.4px)은 한글에 부적합 → **한글 헤딩은 tracking 0~-0.5px로 완화**
   (getdesign 원칙의 의도적 지역화 예외로 기록).
2. **마케팅 지향 요소 미사용**: hero mesh gradient, cta-band, logo-strip(고객 로고),
   pricing-card 원용도, pill CTA는 검색앱과 무관 → 사용하지 않음. DESIGN_INTEGRATION §5
   "결과 신뢰 > 시각적 polish" 원칙과 일치.
3. **미정의 상태**: hover/focus/disabled 상태 미문서화("No hover states are documented")
   → focus는 link 블루 2px outline, hover는 hairline→mute 경계 강화로 최소 정의 예정.
4. **데이터 UI 컴포넌트 부재**: 테이블/배지/셀렉트/체크박스/토글/모달/토스트/페이지네이션
   미제공 → 위 파생 규칙으로 구성하고 새 디자인 체계(Tailwind 등)는 도입하지 않음.
5. **다크모드 없음**: 토큰이 라이트 단일 → MVP는 라이트 전용.
6. label-sm fontWeight 줄의 혼입 텍스트(위 데이터 결함) — 소유자 정리 필요.
