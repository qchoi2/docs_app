# FRONTEND_HARDENING_APPLIED_20260709

첨부 문서의 실제 1행 제목을 기준으로 파일명/내용 불일치를 복원한 뒤, 다음 프론트엔드 개선사항을 반영했다.

## 반영 항목

1. 고급 필터 ctype/lang 옵션을 catalog facets 기반 동적 생성으로 변경
2. 원본 계약서 폴더 선택을 경로 입력 + 백엔드 검증 API 방식으로 변경
3. 한글 IME composition Enter 방어
4. CSV 다운로드 utf-8-sig(BOM) 명시
5. 매칭어 하이라이트 normalize/표면형 불일치 폴백 규칙 추가
6. job 진행률 폴링 방식 확정
7. short_term_fallback 등 warnings UI 배지 추가
8. AI disabled reason 원인별 표시 추가
9. 비교 목록 ui_state.sqlite 영속 저장 추가
10. 검색 상태 URL query parameter 복원 추가
11. STACK_DECISION.md 산출물 추가
12. 접근성 보강(aria-live, split view 포커스, 검색창 단축키 충돌 방지)

## 주요 수정 파일

- UI_PRODUCT_SPEC.md
- UI_REVIEW_PC.md
- UI_ROADMAP.md
- IMPLEMENTATION_BRIEF.md
- CODING_SEQUENCE.md
- CODING_AGENT_RULES.md
- BACKEND_REVIEW_PC.md
- DESIGN_INTEGRATION.md
- docs_progress_v2.md
- CHANGELOG_20260708.md
- MANIFEST.txt
