# NOTES_FOR_OWNER — 적용한 기본값·이탈사항·제안

_Brief §0.2/§9에 따라, 코드에 임의 반영하지 않은 개선 아이디어와 적용한 기본값을 기록한다._

## 적용한 기본값·의도적 이탈

- **무결과 검색의 exit code는 0** — Brief §2.6은 1이지만 Step 6 진행 중 소유자
  지시로 0으로 확정 (progress.md 참조).
- **`--dry-run`도 리포트 파일은 기록** — DB/txt 캐시는 변경하지 않는다.
  테스트(`test_dry_run_writes_report_without_db_or_txt_cache`)로 고정된 동작.
- **읽기 불가 파일(권한 오류 등)의 file_key** — 바이트를 읽을 수 없어
  sha256(파일 바이트)가 불가하므로 경로 기반 의사 키를 사용한다. 권한이
  복구되어 다시 색인되면 정상 바이트 해시 키로 새로 등록된다.
- **`--sample`은 단순 무작위** — Brief의 "가능하면 층화(stratified)"는
  미적용. 파일럿 결과 유형 쏠림이 보이면 층화 샘플링 추가를 권장.
- **empty/error/unsupported 문서는 dup_group에 참여하지 않음** — 빈 추출
  텍스트끼리 같은 content_hash를 공유해 무관한 스캔 PDF들이 하나의 중복
  그룹으로 묶이는 오탐이 실제 파일럿에서 발생해 수정함 (2026-07-10).
- **meta_filter_match** — 메타 필터(type/lang)를 지정하지 않은 검색에서는
  true 대신 null (해당 없음).
- **스니펫 길이** — 매치 문단 중심 총 240자 (Brief §9).
- **lib/termdict.py 별도 모듈은 만들지 않음** — term_dict 로드/확장 로직은
  search_contracts.py에 포함되어 있고 eval/inspect가 이를 import한다.

## 미구현 위험 (Brief §4 지적 항목)

- **파일 단위 추출 타임아웃 없음** — 손상 PDF에서 pdfminer가 무한 대기하면
  배치 전체가 멈출 수 있다. Windows에는 SIGALRM이 없어 파일 단위
  subprocess 또는 watchdog 스레드가 필요하다. 전체 코퍼스 색인 중 특정
  파일에서 멈추면 해당 파일을 제외 후 재실행하고 이 항목의 구현을 지시할 것.
- **Windows 260자 경로(`\\?\`) 미처리** — 깊은 한글 폴더 경로에서 MAX_PATH
  초과 시 파일 열기가 실패할 수 있다 (permission_denied가 아닌
  unknown_error로 기록됨). 파일럿 리포트에서 해당 오류가 보이면 구현 필요.

## 남은 계획 항목 (미착수, 순서상 다음)

- **Phase 1B**: `lib/budget.py`, `answer_quick.py` — 검색 품질 확인 후 (Step 11*).
- `plan_extract.py` — Phase 2 추출 후보 추천 (Step 12*).
- 웹 UI 전 단계 (UI-0 ~ UI-4).

  (*CODING_SEQUENCE.md 기준 번호)

## 제안

- **golden_queries.yaml에 선택 필드 `kw:` 추가** — eval_search.py는 문항에
  `kw: [키워드...]`가 있으면 키워드 검색까지 실행해 recall을 실질적으로
  채점한다 (코드 이미 지원, 데이터는 소유자 관할이라 미수정). expected_files를
  채울 때 함께 채우면 T4 필요성 판정 근거가 좋아진다.
- **성능 실측 기록** — 전체 코퍼스 색인 시 소요시간·peak memory·디스크
  사용량을 report에 남기는 자동화는 미구현. 파일럿에서는 수동 기록 권장.

## 소유자 지시로 변경된 항목 (2026-07-10)

- **data/term_dict.yaml v2.2** — 파일럿에서 확인된 미수록 변이(배상상한:
  손해배상 상한 계열, 해제: 계약해제 계열)를 소유자 지시로 병합.
  효과 실측: "손해배상 상한" 1→92건, "계약해제" 9→264건.
- **CLAUDE.md / AGENTS.md 수정** — Brief §7은 CLAUDE.md 수정을 금지했으나,
  소유자가 "term_dict 확장을 적극 제안하라"고 지시하여 제안 섹션을 추가함.
  직접 병합은 여전히 금지(사람 승인 필수), 유료 API 호출 금지 유지.
- **term_dict_tools.py 신설** — --validate(형식/중복 검사),
  --suggest(query_log 기반 pending_terms.yaml 생성), --zero-hits(0히트 변이 점검).
  term_dict.yaml 헤더의 유지보수 파이프라인(제안→사람 승인→병합→eval 회귀 확인)을 구현.

## Web Backend Step 1 결정사항 (2026-07-10)

- **스택: 표준 라이브러리 WSGI(wsgiref)** — Phase 1 의존성 화이트리스트를 유지하기 위해
  FastAPI/Pydantic을 도입하지 않고 stdlib로 구현. 요청 검증은 수동(BACKEND_REVIEW_PC §2.8의
  "argparse 검증으로 충분" 원칙의 연장). UI 단계에서 동시성·스키마 요구가 커지면
  FastAPI 전환을 검토하되, 엔드포인트 계약은 그대로 유지 가능.
- `GET /api/catalog/facets`를 `GET /api/search/facets`의 별칭으로 함께 제공
  (BACKEND_REVIEW_PC §2.8 문서 경로와 소유자 지시 경로 모두 수용).
- `POST /api/search`의 offset은 내부적으로 offset+limit 검색 후 슬라이스 —
  파일럿 규모에서 충분하며, 전체 코퍼스에서 성능 문제가 보이면 커서 방식으로 전환.
- 검색 API도 CLI와 동일하게 query_log.jsonl에 기록됨 (읽기 전용 DB 연결과 별개의 로그 append).
- 미구현(후속 단계): job queue, Runtime API Settings, Agent Setup Wizard, AI 답변,
  관리자 인증(§2.2 — 현재는 read-only 엔드포인트만이라 유예, 쓰기 기능 추가 전 필수).

