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
