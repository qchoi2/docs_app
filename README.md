# Contract Search — M&A 계약서 로컬 검색 CLI

M&A 계약서 샘플(.docx/.pdf)을 색인해 자연어 키워드로 검색하는 **Windows PC 로컬 실행** 도구입니다.
모든 산출물(catalog.sqlite, txt 캐시, 로그)은 `cs_index/` 한 곳에 생성됩니다.

> **중요:** `cs_index/`는 반드시 **PC 로컬 디스크**에 두세요. SQLite를 네트워크 드라이브(NAS 등)에
> 두면 손상될 수 있습니다. 계약서 원본은 로컬 폴더 또는 읽기 전용 네트워크 드라이브 모두 가능합니다.

## 1. 설치 (venv + requirements)

Python 3.10+ 권장 (3.9 문법 호환 유지). PowerShell에서:

```powershell
cd C:\path\to\contract-search
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

출력이 리다이렉트될 때 한글/특수문자 깨짐을 막으려면 환경 변수를 켜두는 것을 권장합니다:

```powershell
$env:PYTHONUTF8 = "1"
```

## 2. 파일럿 색인

전체 코퍼스(2,000여 건)를 한 번에 색인하기 전에, 일부만 먼저 색인해 품질과 성능을 확인합니다.

방법 A — 상대경로 목록 지정(권장):

```powershell
# pilot_files.txt: --root 기준 상대경로를 한 줄에 하나씩
python index_contracts.py --root C:\contracts --out C:\cs_index --file-list pilot_files.txt --batch-label pilot_001
```

방법 B — 결정적 무작위 샘플:

```powershell
python index_contracts.py --root C:\contracts --out C:\cs_index --sample 200 --sample-seed 42 --batch-label pilot_001
```

`--file-list`와 `--sample`은 동시에 쓸 수 없습니다. `--dry-run`을 붙이면 DB/캐시 변경 없이
변경 예정 리포트만 확인할 수 있습니다. 실행이 끝나면 `cs_index/report_YYYYMMDD.md`에서
status별 건수, 중복 그룹, 실패 원인(empty/error)을 확인하세요.

## 3. 전체 코퍼스 확장

파일럿과 **같은 `--root`, 같은 `--out`**을 유지하면 증분 색인으로 나머지만 처리됩니다:

```powershell
python index_contracts.py --root C:\contracts --out C:\cs_index --batch-label full_001
```

- 파일 이동/삭제/복원/내용변경은 자동 감지되어 리포트 §1에 표시됩니다.
- 파일럿을 별도 복사 폴더에서 했다면 전체 색인은 새 `cs_index`를 만들거나 `--full`로 재색인하세요.
- `--full`은 files/fts 색인만 재구축하며 query_log, eval_history 등 로그는 보존합니다.
- 전체 확장 직후에는 `eval_search.py`를 다시 실행해 검색 품질 회귀를 확인하세요.

## 4. 검색

```powershell
# 키워드 검색 (term_dict 동의어 확장 기본 ON, 중복 제거 기본 ON)
python search_contracts.py --out C:\cs_index --kw 손해배상 --limit 10 --json

# AND 검색 + 유형/언어 필터 + 드래프트 제외
python search_contracts.py --out C:\cs_index --type SPA --lang 국문 --kw earn-out --kw 손해배상 --exclude-drafts --json

# 확장 강도 조절: --expand strict|normal|broad, 확장 끄기: --no-expand
# 중복본 펼쳐 보기: --show-duplicates

# T3 clause_map 필터
python search_contracts.py --out C:\cs_index --clause 손해배상 --present --json
python search_contracts.py --out C:\cs_index --clause 경업금지 --absent --json

# 계약 버전 필터 (role key 또는 한글 라벨, 콤마로 다중)
python search_contracts.py --out C:\cs_index --kw 손해배상 --version 체결본 --json
python search_contracts.py --out C:\cs_index --kw 손해배상 --version "매수인 초안,매도인 초안" --json
```

### 4.1 `--version` 필터의 근거와 한계

`--version`은 `files.version_role`(체결본/매수인 초안/…)에 대한 필터이고, 이 라벨은
`classify_version.py`가 **파일명만 보고** 붙인 휴리스틱 결과입니다. 본문을 읽지 않으므로
파일명에 표식이 없는 체결본은 `unknown`으로 남고, `draft_unknown`·`markup_unknown`처럼
당사자나 단계가 비어 있는 라벨, `1st/2nd` 라운드 패리티로 **추론된** 당사자도 있습니다.
따라서 `--version`은 "그 버전의 전수"가 아닙니다.

- 각 분류는 근거 `files.version_basis`(JSON: 발화한 토큰·규칙·추론)와 신뢰도
  `files.version_confidence`(high/med/low)를 함께 저장합니다. 두 컬럼이 아직 비어 있는
  색인(백필 전)에서는 결과가 `version_confidence: null`로 나오고 전부 "확인 필요"로
  표시됩니다 — 확신처럼 읽지 마세요.
- `--version`을 쓴 응답에는 항상 `version_filter_notice`가 붙습니다:
  `excluded_unknown`(버전 미상), `excluded_partial`(당사자·단계 부분 미상),
  `excluded_low_confidence`(저신뢰), `excluded_unrated`(신뢰도 미기록),
  `matched_low_confidence`(결과에 포함됐지만 확인 필요), `review_candidates`(제외된
  문서 표본). `warnings`에도 같은 내용이 `version_filter_excluded_*` 토큰으로 들어갑니다.
- 결과 행에는 `version_label`, `version_confidence`, `version_basis`,
  `version_basis_summary`, `version_review_required`가 함께 실립니다.
- 라벨 백필/갱신(단일 writer가 실행):

```powershell
python classify_version.py --out C:\cs_index --dry-run   # 쓰기 없이 분포 확인
python classify_version.py --out C:\cs_index --apply     # 백업 후 role/basis/confidence 부여
```

JSON 결과의 `why`, `score_breakdown`, `snippet_paras`로 선정 이유와 ¶위치를 확인하고,
`--clause` 사용 시 `clause` 근거에서 present/absent, 문단 위치, confidence를 확인합니다.
특정 문단 주변은 `open_text.py`, 파일 상세는 `inspect_file.py`로 봅니다:

`--clause`는 `data/term_dict.yaml`의 canonical 태그와 동의어로 정규화합니다. 태그가
`clause_map_json`에 없으면 미평가로 `query.clause.needs_review`에 분리하고,
`present=false`와 혼동하지 않습니다. `--absent`는 `present=false`만 결과로 반환하며,
미평가 및 `confidence=low` 문서는 확인 필요로 분리합니다.

```powershell
python open_text.py --out C:\cs_index --file-key ab12cd34ef567890 --para 42 --context 3
python inspect_file.py --out C:\cs_index --file-key ab12cd34ef567890 --show-dup-group
```

집계는 `stats_contracts.py`를 사용합니다 (`--by ctype,lang`, `--status`, `--errors`, `--batches`, `--dedup`).

## 5. 평가 (golden queries)

```powershell
python eval_search.py --out C:\cs_index
python eval_search.py --out C:\cs_index --tiers T1,T2,T3
```

`data/golden_queries.yaml`의 문항을 실행해 문항별 pass/fail을 출력하고
`cs_index/eval_history.jsonl`에 기록합니다. expected_files가 없는 문항은 부분채점(필터만)입니다.
T3 문항은 `expected_filter.clause`가 있으면 `search_contracts.py --clause` 경로로 채점하고,
아직 사람이 채우지 않은 placeholder처럼 채점 가능한 clause 조건이 없으면 skipped로 기록합니다.

## 5.5 T3 enrich 하네스

`enrich_contracts.py`는 실제 AI API를 호출하지 않는 T3 보강 배치 하네스입니다. 역할은 다음 처리 대상 선정, txt 캐시를 읽은 입력 JSON 생성, 에이전트가 작성한 결과 JSON 검증, `doc_meta` 저장, 재개 상태 기록까지만입니다.

```powershell
python enrich_contracts.py --out C:\cs_index --limit 10
```

파일 기반 인터페이스:

- 입력: `C:\cs_index\enrich_inputs\<file_key>.json`
- 결과: `C:\cs_index\enrich_results\<file_key>.json`
- 진행률/재개: `C:\cs_index\enrich_progress.json`

작업 흐름:

1. 스크립트를 실행하면 `status='ok'`이고 dup 대표인 문서만 우선순위(SPA → SHA → SSA → MOU → ATA/BTA → JVA → CB/BW/EB → 주식교환 → 분할합병 → 기타)에 따라 입력 JSON으로 생성합니다.
2. 코딩 에이전트 세션이 입력 JSON의 문단을 읽고, 같은 `file_key` 이름으로 결과 JSON을 `enrich_results`에 작성합니다.
3. 스크립트를 다시 실행하면 결과 JSON을 검증해 `doc_meta`의 `parties_json`, `consideration_json`, `clause_map_json`, `definitions_json`, `confidence` 등에 저장합니다.
4. 이미 같은 `meta_schema_version`과 `txt_hash`로 저장된 문서는 skip합니다. 재추출이 필요하면 schema version을 올리는 방식으로 처리합니다.

결과 JSON 필수 키: `file_key`, `meta_schema_version`, `parties_json`, `deal_type_detail`, `consideration_json`, `clause_map_json`, `special_notes`, `definitions_json`, `confidence`. 현재 하네스 스키마는 `meta_schema_version=2`입니다. `clause_map_json`의 각 평가 조항은 `present`를 반드시 true/false로 담고, `loc_start`, `loc_end`, `summary`를 담아 이후 `read_contract.py`가 문단 좌표로 부분 정독할 수 있게 합니다. `손해배상`이 `present=true`이면 `cap_verbatim`, `basket_verbatim`, `de_minimis_verbatim`, `survival_verbatim`도 필수이며, 원문에서 확인하지 못한 값은 null 대신 `"not confirmed"`로 씁니다.

### 5.5.1 T3 v3 정밀 보강 파일럿

v3는 기존 v2를 덮어쓰지 않고 별도 폴더에서 당사자·대금·정규화 수치·유형별 조항을 검증합니다.

```powershell
# 유형·언어·Draft·기존 신뢰도를 섞은 60건 표본과 입력 생성
python plan_t3_v3_pilot.py --out C:\cs_index --limit 60 --write-inputs

# AI 클라이언트 결과를 DB 저장 전에 형식·위치·원문·수치 기준으로 감사
python audit_t3_v3.py --manifest C:\cs_index\t3_v3_pilot_manifest.json

# 사람 검수 승인 후에만 v3 결과 저장
python enrich_contracts.py --out C:\cs_index --meta-schema-version 3 --limit 60
```

- 입력: `C:\cs_index\enrich_inputs_v3\<file_key>.json`
- 결과: `C:\cs_index\enrich_results_v3\<file_key>.json`
- 추출 지침: `.docs/extract_prompt_v3.md`
- 파일럿 계획·승인 기준: `.docs/T3_V3_PILOT.md`

v3 구조화 검색은 CLI·웹 API·MCP에서 당사자명/역할, 지급 방식·대금 범위,
손해배상 상한 비율, 존속기간, 준거법, 법원·중재기관 조건을 지원합니다.
v3가 없는 기존 문서는 조건 불일치나 부재로 단정하지 않고 `needs_review`에 미평가로 분리합니다.

## 5.6 T3 조항 단위 부분 읽기

`read_contract.py`는 `doc_meta.clause_map_json`에 저장된 문단 범위를 좌표로 사용해 txt 캐시에서 해당 조항만 출력합니다.

```powershell
python read_contract.py --out cs_index --file-key c97356967ef00c57 --section 손해배상
python read_contract.py --out cs_index --file-key c97356967ef00c57 --section indemnity --context 1 --json
```

`--section`은 `data/term_dict.yaml`의 canonical 태그와 동의어로 정규화합니다. `doc_meta`에 해당 태그가 없으면 `미평가`, 태그는 있지만 `present=false`이면 `평가 후 부재`로 구분합니다. `doc_meta.txt_hash`가 현재 `files.content_hash`와 다르면 `재추출 전`을 표시합니다.

## 6. 자동 분류 수동 보정 (manual_overrides.yaml)

색인 리포트에서 잘못 분류된 문서를 발견하면 코드 수정 없이 `data/manual_overrides.yaml`로 보정합니다:

```yaml
paths:
  "**/SPA/**":
    ctype: SPA
files:
  "0123abcd4567ef89":
    ctype: SPA
    lang: 영문
    is_draft: false
    version_hint: final
```

적용 우선순위는 자동 추정 → path 패턴(glob) → file_key이며, file_key 보정이 최종 우선합니다.
보정 대상은 ctype/lang/is_draft/version_hint만이고 file_key/content_hash는 보정할 수 없습니다.
보정 후 해당 파일이 다시 색인될 때(또는 `--full` 실행 시) 반영됩니다.

## 6.5 검색어 사전(term_dict) 확장

`data/term_dict.yaml`은 질의 시점에 로드되므로 **수정 후 재색인 없이 즉시 반영**됩니다.
사용 중 검색이 빈약한 표현을 발견하면:

```powershell
# 1) 검색 로그에서 사전 미수록 검색어 후보 추출 → cs_index/pending_terms.yaml 생성
python term_dict_tools.py --suggest --out C:\cs_index

# 2) 후보 검토 후 승인분만 data/term_dict.yaml의 해당 항목 ko/en에 병합, dict_version 주석 올리기

# 3) 형식 검증 + 병합 전후 eval로 회귀 확인
python term_dict_tools.py --validate
python eval_search.py --out C:\cs_index

# (선택) 현재 코퍼스에서 한 번도 매치되지 않는 변이 점검 (오타/불필요 후보)
python term_dict_tools.py --zero-hits --out C:\cs_index
```

검색 에이전트(Claude Code)도 검색 중 미수록 표현을 발견하면 pending_terms.yaml에
후보를 제안하도록 지침되어 있습니다. 병합 결정은 항상 사람이 합니다.

## 7. 백업/복구

- 권장: `python backup_index.py --out C:\cs_index --dest D:\backup`
  SQLite 파일(catalog/ui_state/jobs)은 `Connection.backup()`으로 온라인 백업되어
  WAL 미체크포인트 내용 누락이 없습니다. txt 캐시와 jsonl 로그도 함께 복사됩니다.
- 수동으로 폴더를 복사하는 경우에는 `catalog.sqlite-wal`, `catalog.sqlite-shm`
  파일도 **반드시 함께** 복사하세요 (WAL 모드 사용 중).
- 안전한 시점: 색인 실행이 끝난 직후 (종료 시 wal_checkpoint 수행됨).
- `catalog.sqlite`와 `txt/`는 재색인으로 언제든 재생성 가능하지만,
  `query_log.jsonl`, `eval_history.jsonl` 등 로그는 재생성이 불가능하니 백업 대상입니다.
- 복구는 백업 폴더를 원래 위치에 되돌려 놓기만 하면 됩니다.

## 8. AI 코딩 에이전트 (개발 작업용)

### Claude Code 설치/로그인

```powershell
irm https://claude.ai/install.ps1 | iex
claude --version
```

설치 후 프로젝트 루트에서 `claude`를 실행하면 최초 1회 브라우저에서 구독 계정으로 로그인합니다.
세션 중 재인증이 필요하면 `/login`을 입력합니다. 상세 절차와 문제 해결은
`.docs/AGENT_SETUP_AND_MODEL_OPTIONS.md`를 참고하세요.

### Codex 선택 활용

Claude Code 사용량 한도에 도달했거나 작은 패치 작업에는 Codex CLI/VS Code 확장을
보조 작업자로 쓸 수 있습니다 (`npm install -g @openai/codex` 후 ChatGPT 계정 로그인).
**Codex는 ChatGPT 구독계정 로그인 기반으로만 사용하며, OpenAI API key를 입력받거나
저장하지 않습니다.**

### ANTHROPIC_API_KEY (런타임 AI 답변 경로)

`answer_quick.py` 등 Haiku API 호출 기능(Phase 1B, 미구현)은 Claude Code 로그인과 **별개**로
사용자 제공 `ANTHROPIC_API_KEY`와 `data/api_budget.yaml`의 per_call/per_run 상한이 모두
설정되어야 활성화됩니다. 키 입력은 추후 웹 UI의 **Runtime API Settings 화면**에서 받는 것이
표준 경로이며, `.env` 직접 설정은 고급/수동 백업 경로로만 사용합니다. 예산 상한이 null이면
API 도구는 실행을 거부합니다.

## 9. 오류 FAQ

| 증상 | 원인/조치 |
|---|---|
| `SQLite FTS5 trigram tokenizer is required` | SQLite < 3.34. Python 3.10+ 사용 또는 `pysqlite3-binary` 설치 |
| 리포트에 empty 문서 다수 | 스캔 PDF (본문 텍스트 없음). OCR은 Phase 1 범위 밖 — 건수 확인 후 소유자가 결정 |
| `pdf_extract_failed` / `corrupt_docx` | 손상/암호화 파일. 해당 파일만 실패하고 배치는 계속됨 |
| 파이프/리다이렉트 시 UnicodeEncodeError | `$env:PYTHONUTF8="1"` 설정 |
| 검색 결과가 기대보다 적음 | `--expand broad` 시도, 2글자 용어는 자동 LIKE 폴백(warnings 확인) |
| `term_dict_not_found` 경고 | `data/term_dict.yaml`을 찾지 못함 — 저장소 루트에서 실행 중인지 확인 |

## 10. 웹 API / 웹 UI

읽기 전용 검색 화면(UI-1)과 API 서버가 포함되어 있습니다. 추가 의존성 없이 실행됩니다:

```powershell
python webapp.py --out C:\cs_index          # 브라우저에서 http://127.0.0.1:8765 열기
```

검색 화면 기능: 검색창(쉼표로 AND 조건, 한글 IME 조합 중 Enter 보호), catalog 기반 동적
고급 필터와 필터 칩, 결과 카드(왜 검색됐나·score·¶위치·배지), warnings 배지, 문단 주변
보기, 중복본 보기, Markdown/CSV(utf-8-sig) 내보내기, URL로 검색 상태 복원, j/k 결과 이동,
최근 검색(클릭 시 검색 조건·URL 복원 — `cs_index/ui_state.sqlite`에 영속, 재색인·`--full`과 무관).

엔드포인트: `GET /api/health`, `GET /api/corpus/status`, `POST /api/search`(limit/offset),
`GET /api/files/{file_key}/context`, `GET /api/files/{file_key}/duplicates`,
`POST /api/export/markdown`, `POST /api/export/csv`(utf-8-sig), `GET /api/search/facets`.
기본 바인딩은 127.0.0.1이며 검색은 read-only connection, 파일 접근은 file_key 기준입니다.

웹 UI 화면(검색 화면, 색인 대시보드, Agent Setup Wizard, Runtime API Settings)과
job queue·AI 답변은 **후속 단계**입니다. `.docs/UI_ROADMAP.md` 순서(UI-0 ~ UI-4)로 진행합니다.

## 11. MCP 어댑터 (선택)

기존 웹앱과 함께 로컬 AI 클라이언트에서 계약 검색 도구를 사용할 수 있습니다. MCP는
별도 선택 설치이며, 설치하지 않아도 웹앱과 CLI는 그대로 동작합니다. Python 3.10 이상에서:

```powershell
python -m pip install -r requirements-mcp.txt
python mcp_server.py --out C:\cs_index --check
```

AI 클라이언트에는 로컬 stdio 서버로 다음 command/args를 등록합니다. 실제 Python 실행 파일과
프로젝트·색인 경로는 PC 환경에 맞게 절대경로로 바꾸세요.

```json
{
  "command": "C:\\path\\to\\.venv\\Scripts\\python.exe",
  "args": [
    "C:\\path\\to\\docs_app\\mcp_server.py",
    "--out",
    "C:\\cs_index"
  ]
}
```

제공 도구: 계약 검색, 조항 단위 부분 정독, 문단 주변 읽기, 파일 상태 점검, 중복·버전 확인,
코퍼스 상태와 필터 조회. 모두 읽기 전용이며 색인 시작·설정 변경·저장 검색 등 쓰기 작업은
기존 웹앱이 담당합니다. MCP 사용 시 최종 요약·비교 답변은 연결된 AI 클라이언트가 작성하므로
별도의 답변 API key가 필요하지 않습니다. 단, MCP 클라이언트의 구독 사용량·한도는 적용됩니다.
