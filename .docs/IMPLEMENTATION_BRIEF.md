# IMPLEMENTATION_BRIEF — M&A 계약서 검색 프로그램 구현 지시서 v1
_2026-07-08 · 이 문서는 코딩을 수행할 AI(또는 사람)를 위한 단일 기준 문서다.
기획·아키텍처 논의는 끝났다. 이 문서와 동봉 파일들이 정한 것을 바꾸지 말고
구현하라. 문서 간 충돌 시 우선순위: 본 문서 > docs_progress_v2.md > 나머지._

---

## 0. 너(코딩 모델)의 역할과 작업 규칙

1. **범위: Phase 0~1만 구현한다** (아래 §5). T3/T4는 인터페이스 자리만
   비워두고 구현하지 마라. 요청받지 않은 기능을 추가하지 마라.
2. **스키마·CLI 계약·파일 포맷은 본 문서가 확정한 그대로.** 개선 아이디어가
   있으면 코드로 반영하지 말고 `NOTES_FOR_OWNER.md`에 제안으로 적어라.
3. **모호하면 §9의 기본값을 적용하고, 적용한 기본값을 최종 보고에 명시하라.**
   §9에 없는 모호함만 사용자에게 질문하라.
4. **개발 중 유료 API를 호출하지 마라.** answer_quick.py는 작성하되,
   테스트는 mock으로. 실호출은 사용자가 한다.
5. **term_dict.yaml, type_rules.yaml, golden_queries.yaml은 런타임 로드
   데이터다.** 내용을 코드에 하드코딩하지 마라 (사용자가 코드 수정 없이
   갱신하는 것이 설계 요건).
6. 모든 스크립트는 **결정적(deterministic)**이어야 한다 — 같은 입력이면
   같은 catalog, 같은 ¶번호, 같은 검색 순위.
7. 완료 기준은 §6. "동작하는 것 같음"이 아니라 테스트와 eval 통과다.

## 1. 프로젝트 한 줄 요약과 파일 매니페스트

개인 NAS의 M&A 계약서 샘플 **2,245개(855MB, .docx 위주+일부 .pdf)**를
색인해 자연어로 검색·질의하는 로컬 시스템. 답변은 주로 구독제 Claude
Code(무료)가 수행하고, API는 폴백·판정용으로만 엄격한 예산 하에 사용.

| 동봉 파일 | 역할 | 코더가 할 일 |
|---|---|---|
| `docs_progress_v2.md` | 전체 설계·로드맵·가드레일 | 배경 이해 (§2 티어, §API 공통 가드레일 필독) |
| `type_rules.yaml` | 폴더/파일명 → ctype·lang·버전 규칙 | index_contracts.py가 로드 |
| `term_dict.yaml` | 통제 어휘 88항목 (동의어 확장) | search_contracts.py가 로드 |
| `golden_queries.yaml` | 평가 기준 33문항 | eval_search.py가 로드 |
| `CLAUDE_v2.md` | Claude Code 에이전트 지침 | 저장소에 CLAUDE.md로 배치만 (수정 금지) |
| `extract_prompt_v1.md` | Phase 2 추출 스키마 | Phase 1에서는 **¶마커·clause_index DDL 근거로만 참조** |
| `api_budget.yaml` | API 예산 설정 (사용자 입력란 포함) | data/에 그대로 배치, budget.py가 로드 |
| `manual_overrides.yaml` | 자동분류 보정 템플릿 | data/에 배치, index_contracts.py가 로드 |
| `PILOT_ROLLOUT.md` | 소규모 파일셋→전체 확장 운용 절차 | README에 요약하고 상세 절차를 유지 |
| `CODING_SEQUENCE.md` | 코딩 모델에게 단계별로 시킬 구현 명령 | 작업 순서를 이 문서에 맞춰 진행 |
| `CODING_AGENT_RULES.md` | GPT-5.5/Claude Code 코딩 원칙 | 코딩 작업 전 항상 적용 |
| `UI_PRODUCT_SPEC.md` | 웹 UI 제품/화면 스펙 | UI 단계에서 기준 문서로 사용 |
| `DESIGN_INTEGRATION.md` | getdesign.md 디자인 자산 활용 절차 | UI 구현 전 DESIGN_AUDIT.md 작성 |
| `UI_ROADMAP.md` | UI-0~UI-4 구현 순서 | CLI MVP 이후 UI 확장 순서 |

## 2. 확정 기술 결정 (변경 금지)

- **언어/버전**: Python, **3.9 호환** 하한 (Synology NAS 기본 파이썬 고려).
  3.10+ 전용 문법(match 등) 금지.
- **의존성 화이트리스트**: `python-docx`, `pdfminer.six`, `PyYAML`,
  표준 라이브러리. `answer_quick.py`만 `anthropic` 추가. 그 외 금지
  (pandas·chroma 등 불필요). requirements.txt 작성.
- **저장 위치**: 모든 산출물은 단일 색인 디렉토리 `cs_index/` 하위.
  코드는 색인 디렉토리와 분리.
- **저장소 레이아웃**:
```
contract-search/
  index_contracts.py   search_contracts.py   stats_contracts.py   eval_search.py
  inspect_file.py      open_text.py        plan_extract.py     answer_quick.py
  lib/  normalize.py  catalog.py  termdict.py  budget.py  extract.py
  data/ term_dict.yaml  type_rules.yaml  golden_queries.yaml  api_budget.yaml
  data/manual_overrides.yaml
  CLAUDE.md   tests/   requirements.txt   README.md   PILOT_ROLLOUT.md
```
- **실행 환경 확정 (소유자 답변, 2026-07-08)**: **스크립트는 PC에서 실행**
  (RAM 16GB). 계약서 원본은 NAS를 네트워크 마운트로 **읽기만** 하고,
  `cs_index/`(sqlite·txt 캐시)는 반드시 **PC 로컬 디스크**에 둔다
  (sqlite를 네트워크 파일시스템에 두지 않는다 — README에 경고 명시).
  venv 사용 안내 포함. 3.9 하한은 유지하되 PC이므로 최신 파이썬 권장.

### 2.1 식별자 3종 (혼동 금지 — 가장 중요한 규약)
- `file_key` = sha256(**파일 바이트**)의 상위 16 hex. 불변 기본키.
  파일명 변경·이동에도 유지되므로 증분/rename 처리의 축.
- `content_hash` = sha256(**정규화된 추출 텍스트**, ¶마커 제외)의 상위
  16 hex. **중복 판정 전용** (서식만 다른 동일 계약을 잡음).
- `dup_group` = 같은 content_hash 그룹 중 **사전순 최소 file_key**.
  단독 문서는 자기 자신.

### 2.2 정규화 사양 — `lib/normalize.py` (색인·검색이 반드시 공유)
단일 함수 `normalize(text) -> str`:
1. 유니코드 **NFC** 정규화
2. 전각 영숫자·기호 → 반각
3. 하이픈류(‐-–—) → `-`, 따옴표류 → `'"` 표준화
4. `earn out|earn-out|earnout` → `earnout` 류의 하이픈+공백 접합은
   하지 **않는다** (trigram이 흡수). 단 소프트하이픈(U+00AD)·제로폭
   문자는 제거
5. 연속 공백·탭 → 단일 공백, 줄 양끝 trim
색인 텍스트와 FTS 질의어 **양쪽에 동일 함수 적용** — 이것이 이 모듈의
존재 이유다.

### 2.3 txt 캐시 포맷 (¶마커)
- 경로: `cs_index/txt/<file_key>.txt`, UTF-8
- 형식: 문단당 1행, `[¶N]\t` 접두 (N은 1부터 순차). 빈 문단은 건너뛰되
  번호는 건너뛴 문단에 부여하지 않는다(연속 번호).
- **docx**: 본문 요소를 **문서 등장 순서대로** 순회해야 한다
  (python-docx의 `document.paragraphs` + `document.tables` 분리 접근 금지
  — `document.element.body` 순회로 문단·표를 원래 순서로).
  표는 행 단위 1문단, 셀은 ` | ` 로 연결. **머리글/바닥글·각주는 best-effort**로 본문 뒤에
  `[¶N]\t[각주] ...` 또는 `[¶N]\t[머리글] ...` 형태로 부록화한다.
  추출 라이브러리 한계로 각주·머리글·바닥글을 안정적으로 읽지 못하는 경우 전체 색인을 실패시키지 말고
  report에 `footnote_extract_skipped` 또는 `header_footer_extract_skipped` 경고를 남긴다. MVP의 필수 범위는 본문 문단과 표다.
- **pdf**: pdfminer.six 텍스트 추출, 빈 줄 기준 문단 분리. 텍스트가 전무/
  공백뿐이면 status=`empty`.
- ¶번호는 결정적: 같은 파일이면 항상 같은 번호 (Phase 2의 위치좌표 기반).

### 2.4 catalog.sqlite DDL (확정)
```sql
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS files (
  file_key    TEXT PRIMARY KEY,
  path        TEXT NOT NULL,
  folder      TEXT, filename TEXT,
  ctype       TEXT NOT NULL DEFAULT '미분류',
  lang        TEXT NOT NULL DEFAULT '미상',
  ext         TEXT, size INTEGER, mtime REAL,
  txt_path    TEXT, char_count INTEGER,
  status      TEXT NOT NULL CHECK(status IN
              ('ok','empty','error','unsupported','excluded','missing')),
  error_reason TEXT,             -- §2.4.1의 enum 값
  source_signals TEXT,           -- 파일명/폴더명 기반 추정 단서 JSON
  batch_label TEXT,              -- pilot_001, full_001 등 색인 실행 배치 식별자
  content_hash TEXT, dup_group TEXT,
  is_draft    INTEGER,           -- 1/0/NULL(판별불가)
  version_hint TEXT,
  indexed_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_meta ON files(ctype, lang, status);
CREATE INDEX IF NOT EXISTS idx_dup  ON files(dup_group);
-- FTS: 문단 단위 1행 (matched_terms의 ¶ 좌표와 스니펫 품질의 근거)
CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(
  content, file_key UNINDEXED, para INTEGER UNINDEXED,
  tokenize='trigram'
);
-- Phase 2 예약 (지금은 생성만, 기록 안 함)
CREATE TABLE IF NOT EXISTS doc_meta (
  file_key TEXT PRIMARY KEY REFERENCES files(file_key),
  meta_schema_version INTEGER, txt_hash TEXT,   -- 추출 당시 content_hash
  extracted_at TEXT, json TEXT, confidence TEXT
);
CREATE TABLE IF NOT EXISTS clause_index (
  file_key TEXT, tag TEXT, present INTEGER,
  loc_start INTEGER, loc_end INTEGER,
  PRIMARY KEY (file_key, tag)
);
```
- **trigram 가용성 점검 필수**: 시작 시 `sqlite3.sqlite_version` 확인,
  trigram 미지원(<3.34)이면 명확한 오류 메시지 + `pysqlite3-binary`
  설치 안내를 출력하고 중단 (조용한 폴백 금지).
- doc_meta.txt_hash: Phase 2에서 추출 시점의 content_hash를 기록 —
  재추출 없이 원문이 갱신되면 위치좌표가 무효임을 탐지하는 장치.
  Phase 1에서는 스키마만.


### 2.4.1 error_reason 확정 enum
`error_reason`은 집계 가능해야 하므로 아래 값만 사용한다. 상세 예외 메시지는 report에 별도 부록으로 남겨도 되지만 DB 값은 임의 문자열로 확장하지 않는다.

| 값 | 사용 조건 |
|---|---|
| `encrypted_pdf` | 암호 PDF라 본문 추출 불가 |
| `pdf_text_empty` | PDF 추출은 성공했으나 공백/빈 텍스트 |
| `pdf_extract_failed` | PDF 파서 오류 등으로 추출 실패 |
| `docx_extract_failed` | DOCX 추출 실패 |
| `corrupt_docx` | 손상된 DOCX |
| `permission_denied` | 파일 읽기 권한 없음 |
| `unsupported_ext` | 지원하지 않는 확장자 |
| `decode_error` | 텍스트 디코딩 오류 |
| `empty_text` | 비PDF 파일에서 추출 결과가 빈 텍스트 |
| `footnote_extract_skipped` | 본문/표는 추출했으나 각주 추출은 생략됨(경고성) |
| `header_footer_extract_skipped` | 본문/표는 추출했으나 머리글/바닥글 추출은 생략됨(경고성) |
| `unknown_error` | 위 분류로 포착되지 않는 예외 |

status와의 매핑 기본값: `unsupported_ext`는 status=`unsupported`, `pdf_text_empty`·`empty_text`는 status=`empty`, 나머지 치명 오류는 status=`error`. `footnote_extract_skipped`·`header_footer_extract_skipped`는 본문 추출이 성공했으면 status=`ok`를 유지하고 report 경고로만 집계할 수 있다.

### 2.5 index_contracts.py CLI 계약
```
python3 index_contracts.py --root PATH --out ./cs_index
  [--include-misc]      # type_rules의 exclude_by_default 폴더 포함
  [--full]              # 증분 무시 전량 재색인
  [--batch-label LABEL] # pilot_001, full_001 등 실행 배치 표시
  [--file-list FILE]    # root 기준 상대경로 목록만 색인(파일럿 권장)
  [--sample N] [--sample-seed SEED] # root에서 재현 가능한 파일럿 샘플 자동 선정
  [--dry-run]           # 변경 예정 리포트만 출력, DB/캐시 미변경
```
- 증분 기준: (path, size, mtime) 동일 → skip. 다르면 재해시.
- **파일럿→전체 확장 운용 지원**: 성능 테스트용 일부 계약서만 먼저 색인할 수 있다.
  같은 `cs_index`를 유지하려면 파일럿과 전체 확장 모두 **동일 `--root` 기준 상대 경로**를 유지해야 한다.
  가장 권장되는 방식은 `--file-list pilot_files.txt`로 root 기준 상대경로 목록을 지정하는 것이다.
  `--sample N --sample-seed SEED`는 파일럿 후보를 자동 선정한다. 샘플링은 결정적이어야 하며,
  가능하면 폴더/확장자/파일명 type hint가 한쪽으로 쏠리지 않게 층화(stratified)한다.
  `--file-list`와 `--sample`이 동시에 주어지면 오류로 종료한다.
  별도 임시 폴더에 복사해 파일럿을 수행한 경우, 전체 색인은 새 `cs_index`를 만들거나 파일럿 캐시를 버리고 `--full`로 재색인하라.
  `--batch-label`은 pilot/full 실행분을 리포트와 files.batch_label에 남기는 용도다.
- **변경분 처리 규칙 (증분 갱신 런북 §D의 구현)**:
  - 이동: file_key 동일·path 다름 → path만 갱신 (리포트 "이동").
  - 삭제: 스캔에서 사라진 path의 레코드 → status='missing' (레코드·
    txt 캐시·doc_meta 보존, 검색에서 제외). 같은 file_key가 재등장하면
    status 원복 (리포트 "복원").
  - 내용변경: 같은 path에서 새 바이트 해시 → **새 file_key로 신규 등록**,
    같은 path의 옛 레코드는 status='missing' 처리 (리포트 "내용변경",
    old_key→new_key 표기).
  - 검색 계층은 status='missing'을 항상 제외한다.
- zip: 열지 않음. status와 무관하게 "제외 목록" 리포트에만 기록.
- 미지원 확장자(.doc, .hwp 등): status=`unsupported`.
- 심볼릭 링크는 따라가지 않는다 (루프 방지).
- 종료 시 리포트(stdout + `cs_index/report_YYYYMMDD.md`):
  **① 이번 실행 변경분** (신규/내용변경/이동/삭제(missing)/복원 건수와
  목록 — 증분 실행의 첫 화면) / ② 유형×언어 분포표 / ③ 미분류 폴더 목록 /
  ④ status별 건수 / ⑤ **dup_group 크기≥2 목록** (이번에 새로 생긴 중복은
  별도 표시) / ⑥ 미지원 확장자·zip 제외 목록 /
  ⑦ 실패 원인별 집계(error_reason) / ⑧ batch_label별 건수 /
  ⑨ [Phase 2 대비] **stale doc_meta 건수** — doc_meta.txt_hash가 현재
  content_hash와 다른 문서 (Phase 1에서는 doc_meta가 비어 있어 0건).

### 2.6 search_contracts.py CLI·JSON 계약
```
python3 search_contracts.py --out ./cs_index
  [--type T] [--lang L] [--kw K ...]      # --kw 반복 = AND
  [--limit N] [--context N] [--json]
  [--expand strict|normal|broad] [--no-expand]
  [--exclude-drafts] [--exclude-draft] [--show-duplicates]
```
- 기본 동작: dedup ON(그룹 대표만+개수 표시), 드래프트 포함하되 표시,
  term_dict 동의어 확장 ON. 확장 강도 기본값은 `--expand normal`이다.
  `--expand strict`는 canonical 및 강한 변이만, `normal`은 일반 변이까지,
  `broad`는 오탐 가능성이 있는 넓은 관련어까지 사용한다. `--no-expand`는 확장을 끈다.
  `avoid_expanding_to`에 기재된 용어는 어떤 강도에서도 자동 확장하지 않는다.
  `--exclude-drafts`가 표준 옵션이며, `--exclude-draft`는 하위호환 alias로만 허용한다.
  `--show-duplicates`는 같은 dup_group의 중복본까지 펼쳐 보여준다.
- **정확일치 우선 랭킹**: 원질의 FTS 결과와 확장질의 FTS 결과를 파일
  단위 RRF(k=60)로 융합하되 원질의 랭크에 가중 2.0.
- `--json` 출력 (이 스키마 고정 — CLAUDE.md와 G1.5가 파싱):
```json
{"query": {"type":null,"lang":null,"kw":["..."],"expanded":{"원어":["변이",...]}},
 "total": 0,
 "results": [{"file_key":"","path":"","ctype":"","lang":"",
   "is_draft":null,"version_hint":null,"dup_group":"","dup_count":1,
   "dup_representative_reason":"final version preferred",
   "matched_terms":[{"term":"","canonical":"","para":0}],
   "score_breakdown":{"exact_rank":null,"expanded_rank":null,"meta_filter_match":true},
   "why":["원질의 직접 매칭","SPA 유형 필터 일치"],
   "snippet":"[¶42] ...",
   "snippet_paras":[42]}],
 "warnings": ["unsearchable_docs:12"]}
```
- warnings에는 조건에 걸리는 status=empty/error 건수를 반드시 포함.
- 모든 `search_contracts.py` 실행은 `cs_index/query_log.jsonl`에 ts, query, filters, expand_mode, result_count, warnings를 1행 기록한다. Claude Code/answer_quick.py가 최종 답변 후 남기는 로그는 `agent_log.jsonl`로 분리한다.
- 종료코드: 0=결과 있음, 1=결과 없음(정상), 2=오류.

### 2.7 answer_quick.py (G1.5)
- 파이프라인: search --json 상위 후보(기본 10) → 스니펫+메타만 프롬프트
  구성 → Haiku 1회 호출 → 2~3문장 답 + file_key 인용 출력.
- `lib/budget.py` 경유 필수: `data/api_budget.yaml` 로드 (**동봉 파일
  그대로 사용** — 사용자 입력란 2개: per_call/per_run 상한. 값이 null이면
  모든 API 도구는 실행 거부 + 입력 안내), 호출 전 토큰 추산·견적 출력,
  상한 검사, `cs_index/api_ledger.jsonl` 기록(추적용), (프롬프트+입력)
  sha256 캐시(`cs_index/api_cache/`) — 캐시 적중 시 무호출.
  모델 문자열·단가·용도별 입력 토큰 상한도 api_budget.yaml에서 로드.
- 재시도 최대 2회(지수 백오프), 그 후 실패 보고. 자동 재실행 루프 금지.
- 모델 문자열·단가는 코드에 상수로 박지 말고 api_budget.yaml에서 로드
  (단가 변동 대응).

### 2.8 stats_contracts.py
집계 질의는 검색 목록과 분리해 별도 도구로 구현한다.

```
python3 stats_contracts.py --out ./cs_index --by ctype [--dedup]
python3 stats_contracts.py --out ./cs_index --by ctype,lang [--dedup]
python3 stats_contracts.py --out ./cs_index --status
python3 stats_contracts.py --out ./cs_index --errors
python3 stats_contracts.py --out ./cs_index --batches
```

- 기본적으로 status=`ok`인 문서를 대상으로 집계한다. `--status`·`--errors`는 전체 status를 보여준다.
- `--dedup`이 켜지면 dup_group 대표 기준으로 센다.
- golden query 중 expected_count 성격의 문항은 가능하면 이 도구를 사용한다.

### 2.9 eval_search.py
- golden_queries.yaml 로드 → tier가 T1/T2인 문항만 실행 (Phase 1 기준).
- expected_filter 기반 precision, expected_files 있으면 recall,
  expected_count 문항은 `stats_contracts.py` 또는 검색 결과 개수로 채점. 문항별 pass/fail + 요약표 출력,
  `cs_index/eval_history.jsonl`에 추가 기록 (회귀 추적).
- expected_files가 빈 문항은 "부분채점(필터만)"으로 표시.

### 2.10 inspect_file.py / open_text.py / plan_extract.py
- `inspect_file.py --out ./cs_index --file-key K [--show-dup-group]`: 파일 1건의
  path, ctype/lang, status/error_reason, source_signals, batch_label, content_hash,
  dup_group, char_count, matched term_dict entries, doc_meta stale 여부를 출력한다.
- `open_text.py --out ./cs_index --file-key K --para N --context C`: txt 캐시에서
  해당 ¶ 주변만 출력한다. 원문 전체 cat을 대체하는 안전한 부분 열람 도구다.
- `open_text.py --out ./cs_index --file-key K --search TERM --context C`: ¶번호를 모를 때 txt 캐시에서 TERM 주변 문단을 찾아 출력한다.
- `plan_extract.py --out ./cs_index --limit N`: Phase 2 전용 계획 도구. SPA/SHA/SSA,
  final/signed, dedup 대표, 파일럿에서 자주 검색된 유형 순으로 추출 후보를 추천한다.
  Phase 1에서는 API를 호출하지 않고 추천 목록만 만든다.

## 3. 불변식 (위반 = 버그)
1. 색인과 검색은 같은 normalize()를 쓴다.
2. file_key는 파일 바이트 해시, content_hash는 텍스트 해시 — 뒤섞지 않는다.
3. ¶번호는 결정적이고, FTS의 para와 txt 캐시의 [¶N]이 항상 일치한다.
4. 유료 API 호출은 반드시 lib/budget.py를 통과한다 (직접 SDK 호출 금지).
5. 어떤 코드 경로도 사용자 승인 없이 예산 상한을 넘지 못한다.
6. dedup 기본 ON — "10개 보여줘"에 같은 계약이 두 번 나오면 안 된다.
7. 데이터 파일(term_dict 등) 내용은 하드코딩하지 않는다.
8. 파일럿 subset에서 전체 코퍼스로 확장할 때 기존 파일의 상대 경로를 임의로 바꾸지 않는다.
9. 검색 결과에는 가능한 한 why/score_breakdown을 포함해 결과 선정 이유를 설명한다.

## 4. 알려진 함정 (구현 시 반드시 처리)
- **NFD 파일명**: macOS 유래 파일은 파일명이 NFD일 수 있음 — 경로 비교·
  폴더 패턴 매칭 전에 파일명도 NFC 정규화.
- **docx 본문 순서**: §2.3 참고. paragraphs/tables 분리 접근은 표 위치를
  잃는 흔한 버그.
- **암호 걸린 docx/pdf, 손상 파일**: 예외 잡아 status=error + 사유 기록,
  배치는 계속.
- **거대 단일 문서**(수백 페이지): char_count 상한 없이 처리하되 메모리
  스트리밍 유의. txt 캐시가 수 MB여도 정상.
- **type_rules 매칭**: 대소문자 무시 "포함" 검사, 목록 순서 = 우선순위.
  폴더 전체 경로가 아니라 **경로의 각 폴더명 세그먼트**에 대해 검사.
- **국문/영문 혼합 비율 폴백**: lang 미매치 시 한글 문자 비율로 추정
  (>30% 국문, <5% 영문, 사이는 국영문 후보 → 리포트에 표시).
- **WAL 파일**: cs_index를 통째로 복사·백업할 때 -wal/-shm 포함 안내
  (README).
- **인코딩**: 모든 파일 IO는 encoding='utf-8' 명시.



### 2.8 UI 확장용 SQLite 테이블(Phase UI에서 구현)

Phase 1A CLI MVP에서는 필수 구현 대상이 아니다. 다만 웹 UI로 확장할 때는 아래 테이블을 같은 `catalog.sqlite` 또는 별도 `ui_state.sqlite`에 둔다. 개인용 로컬 앱이므로 우선 `catalog.sqlite`에 두어도 된다.

```sql
CREATE TABLE IF NOT EXISTS search_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  query TEXT NOT NULL,
  filters_json TEXT,
  expand_mode TEXT,
  corpus_scope TEXT,
  result_count INTEGER,
  top_file_keys_json TEXT,
  duration_ms INTEGER,
  user_note TEXT
);

CREATE TABLE IF NOT EXISTS saved_searches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  query TEXT NOT NULL,
  filters_json TEXT,
  expand_mode TEXT,
  created_at TEXT NOT NULL,
  last_run_at TEXT
);

CREATE TABLE IF NOT EXISTS research_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS session_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL,
  file_key TEXT NOT NULL,
  para INTEGER,
  note TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_marks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_key TEXT NOT NULL,
  para INTEGER,
  mark_type TEXT NOT NULL,
  note TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS result_feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  search_history_id INTEGER,
  file_key TEXT,
  para INTEGER,
  feedback TEXT NOT NULL,
  note TEXT,
  created_at TEXT NOT NULL
);
```

역할 구분:

- `query_log.jsonl`: CLI/운영 로그. 자동 분석용.
- `agent_log.jsonl`: AI 답변 생성 로그.
- `search_history`: 사용자가 UI에서 다시 여는 최근 검색.
- `saved_searches`: 사용자가 이름 붙여 저장한 검색.
- `research_sessions`: 하나의 리서치 업무 단위.
- `user_marks`, `result_feedback`: 북마크, 메모, 검색 품질 피드백.

## 5. 구현 범위와 추천 구현 순서 (Phase 0~1)
한 번에 전체를 구현하지 말고 아래 순서대로 모듈을 나누어 진행한다. 각 단계가 끝나면 테스트와 실행 예시 1개를 남긴 뒤 다음 단계로 넘어간다. 더 자세한 코딩 명령은 `CODING_SEQUENCE.md`를 따른다.

### Phase 1A — 검색 MVP 필수
1. 저장소 골격, `requirements.txt`, `data/` 파일 배치, `CLAUDE.md` 복사
2. `lib/normalize.py` + 단위 테스트
3. `lib/catalog.py` 기본 DDL·trigram 점검·DB 유틸
4. `index_contracts.py` 1차: 파일 스캔, file_key/content_hash, txt 캐시, docx/pdf 추출, DDL 기록
5. `index_contracts.py` 2차: 증분 규칙, `--file-list`, `--sample/--sample-seed`, `--batch-label`, `--dry-run`, report 9개 섹션
6. `search_contracts.py`: FTS trigram, term_dict 확장, `--expand strict|normal|broad`, RRF, dedup, JSON 스키마, `query_log.jsonl`
7. `stats_contracts.py`: ctype/lang/status/error/batch 집계
8. `inspect_file.py`, `open_text.py`: 디버깅·부분 열람 도구
9. `eval_search.py`: T1/T2 golden query 실행, 부분채점, `eval_history.jsonl`
10. README.md: 설치, 파일럿 색인, 검색, 전체 확장, 평가, 수동보정, 백업/복구, 오류 FAQ
11. `data/manual_overrides.yaml` 로드 및 예시 유지
12. NOTES_FOR_OWNER.md: 적용한 기본값 목록, 제안 사항

### Phase 1B — API 보조(검색 품질 확인 후)
13. `lib/budget.py` + mock 테스트
14. `answer_quick.py`: search --json 상위 후보 기반 2~3문장 답변, API cache/ledger, `agent_log.jsonl`
15. `plan_extract.py`: Phase 2 추출 우선순위 목록만 생성(API 호출·doc_meta 기록 금지)



### Phase UI — CLI MVP 이후 웹 UI 확장

Phase UI는 Phase 1A 검색 MVP가 안정화된 뒤 시작한다. `UI_PRODUCT_SPEC.md`, `DESIGN_INTEGRATION.md`, `UI_ROADMAP.md`를 기준으로 진행한다.

1. **UI-0 디자인 인수**: `getdesign.md`를 읽고 `DESIGN_AUDIT.md` 작성. 디자인 자산이 없으면 기능 우선 MVP로 진행.
2. **UI-1 읽기 전용 검색 UI**: 검색창, 고급 필터, 필터 칩, 결과 카드, 문단 주변 보기, 중복본 보기, 최근 검색, Markdown/CSV 내보내기.
3. **UI-2 운영 UI**: 색인 상태 대시보드, 실패 파일 목록, saved searches, result feedback, manual_overrides 후보 export.
4. **UI-3 리서치 UI**: 비교 목록, 북마크/메모, 리서치 세션.
5. **UI-4 AI 보조**: 선택 결과 기반 요약/비교표, API 예산 표시, file_key/¶번호 인용.

UI 금지 원칙:

- 검색 결과 확인 전 AI 답변을 기본 화면으로 만들지 않는다.
- 파일럿 코퍼스 결과를 전체 경향처럼 표현하지 않는다.
- `getdesign.md` 확인 없이 임의 디자인 시스템을 만들지 않는다.
- 검색 히스토리를 `query_log.jsonl`만으로 대체하지 않는다. 사용자가 보는 최근 검색/저장된 검색은 별도 UI 상태로 관리한다.

참고: `update_contracts.py`(색인→추출→임베딩→eval 체인 오케스트레이터)는
**Phase 2 산출물**이다 — 지금은 만들지 마라. 단, 위의 변경분 처리 규칙과
델타 리포트는 Phase 1의 index_contracts.py에 반드시 포함한다 (증분 갱신
런북의 토대).

## 6. 완료 정의 (Definition of Done)
- [ ] pytest 전부 통과 (fixtures 기반, 네트워크 무요구)
- [ ] 합성 fixtures 색인 → 골든 문항 형식의 스모크 질의 통과
- [ ] eval_search.py가 golden_queries.yaml(T1/T2 문항)을 오류 없이 실행
      (실코퍼스 없는 상태에서는 부분채점 모드로 완주하면 됨)
- [ ] index 리포트에 §2.5의 9개 섹션이 모두 출력
- [ ] budget mock 테스트: 상한 초과 시 호출 차단·캐시 적중 시 무호출 검증
- [ ] Python 3.9에서 문법 오류 없음 (`python3.9 -m py_compile` 또는 CI 대체)
- [ ] `--file-list` 파일럿 색인 후 같은 root/out에 전체 또는 추가 파일을 증분 색인하는 테스트 통과
- [ ] `--sample N --sample-seed`가 결정적 샘플을 만들고 `--file-list`와 동시 사용 시 오류 처리
- [ ] 검색 결과 JSON에 why/score_breakdown/snippet_paras가 포함됨
- [ ] inspect_file.py/open_text.py가 실제 file_key 기준으로 동작
- [ ] stats_contracts.py가 ctype/lang/status/error/batch 집계를 출력
- [ ] UI 단계 착수 시 getdesign.md 확인 후 DESIGN_AUDIT.md 작성
- [ ] UI 단계에서 최근 검색, 저장된 검색, 결과 피드백, 비교 목록의 상태 저장 설계가 반영됨
- [ ] 성능 기준 기록: 파일럿 문서 수, 색인 소요시간, 검색 소요시간, peak memory를 README 또는 report에 남김

## 7. 하지 말 것
- T3/T4 구현(임베딩, 벡터DB, reranker, doc_meta 기록) — 스키마 예약까지만
- 웹 UI, 데몬화, 파일 감시
- term_dict/type_rules 내용 "개선" — 데이터는 소유자 관할
- 실 API 호출, 외부 네트워크 의존 테스트
- CLAUDE.md 수정

## 8. 소유자 제공값 (확정 답변 반영, 2026-07-08)
| 항목 | 확정 내용 |
|---|---|
| 실행 환경 | **PC** (RAM 16GB). NAS는 원본 읽기 전용, cs_index는 PC 로컬 |
| Claude Code 플랜 | Pro — 전량 추출은 1~2주 분할 전제 (Phase 2 참고사항) |
| 추출 우선순위 | SPA → SHA → SSA → MOU → ATA/BTA → JVA·공동투자 → CB·BW·EB → 주식교환 → 분할합병·분할계획서 → 기타 (enrich의 --priority 기본값) |
| api_budget 수치 | **동봉 api_budget.yaml의 입력란을 사용자가 채움** — null이면 API 도구 실행 거부 |
| 99_ 잡폴더 | 기본 제외, `--include-misc`로 포함 (type_rules 플래그) |
| OCR | 색인 리포트의 empty 건수 확인 후 소유자가 결정 — Phase 1 범위 아님 |
| 계약서 루트 경로 | README에 플레이스홀더 |
| 파일럿 운용 | 먼저 일부 계약서 subset으로 성능·품질 확인 후 동일 루트에 나머지 파일 추가. 별도 복사 폴더를 썼다면 전체 색인은 새 cs_index 권장 |

## 9. 모호할 때의 기본값
- 스니펫 길이: 매치 문단 앞뒤 합 240자
- --limit 기본 20, --context 기본 1문단, --expand 기본 normal
- report 파일명 충돌 시 -2, -3 접미
- 로그는 stdout, --quiet 옵션 제공
- dedup 대표 선택: non-draft → final/signed/clean → 짧은 경로 → 읽기 쉬운 filename → file_key 사전순
- 성능 목표(초기 가이드): 파일럿 100~300건 색인 5분 이내, 검색 3초 이내, peak memory 1GB 이하. 전체 코퍼스 기준은 실측 후 조정
- 기타 사소한 결정: 관례적 선택 후 NOTES_FOR_OWNER.md에 기록

---

## 10. 킥오프 프롬프트 (아래를 코딩 모델에게 그대로 붙여넣기)

```
너는 이 저장소의 구현 담당이다. 첨부한 IMPLEMENTATION_BRIEF.md가 단일 기준 문서다.
시작 전에 IMPLEMENTATION_BRIEF.md 전체, CODING_SEQUENCE.md 전체,
docs_progress_v2.md의 "§2 티어", "§API 공통 가드레일" 절을 읽어라.

작업: Brief §5 및 CODING_SEQUENCE.md의 순서대로 Phase 0~1을 구현하라.
- Brief가 확정한 DDL·CLI 계약·JSON 스키마·파일 포맷을 변경하지 마라.
- 범위 밖(T3/T4, UI) 구현 금지. 개선 제안은 NOTES_FOR_OWNER.md에.
- 모호하면 Brief §9 기본값 적용 후 기록하라. §9에 없는 모호함만 질문하라.
- 유료 API는 절대 호출하지 마라. Phase 1B의 answer_quick.py는 mock으로 테스트한다.
- 한 번에 전부 만들지 말고 CODING_SEQUENCE.md의 단계별 명령 순서대로 진행한다.
- 각 단계 완료 시 테스트 명령과 실행 예시 1개를 보여라.
- 완료 기준은 Brief §6 전 항목이다. 마지막에 §6 체크리스트를 채워 보고하고,
  적용한 기본값과 남은 질문을 정리하라.

먼저: Step 1(저장소 골격, requirements.txt, data/ 배치, CLAUDE.md 복사)과
Step 2(lib/normalize.py + 테스트)만 구현하라. 이후 사용자가 계속 지시하면 다음 단계로 진행한다.
```
