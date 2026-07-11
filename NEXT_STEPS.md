# NEXT_STEPS — 앞으로 소유자가 할 일 (단계별 안내)

_작성: 2026-07-11. 기준 문서: `docs_progress_v2.md`(티어 사다리), `IMPLEMENTATION_BRIEF.md`,
`NOTES_FOR_OWNER.md`, `PILOT_REPORT_20260710.md`._

## 지금까지 온 지점

검색 티어 사다리는 T1~T4로 설계돼 있고, 지금은 **T1·T2까지 완성 + 271건 로컬 파일럿 검증**
상태입니다. T2+/T3/T4는 원래 지시서가 "인터페이스 자리만 비워두라"고 한 대로 아직 미구현입니다.

| 티어 | 내용 | 현재 |
|---|---|---|
| T1 | 메타 필터(유형·언어) | ✅ 완성 |
| T2 | FTS5 전문검색 + 용어사전 확장 | ✅ 완성 (파일럿 검증) |
| T2+ | Haiku 즉답(`answer_quick.py`) | ❌ 미착수 |
| T3 | 조항 태그 검색(`doc_meta`) + `read_contract.py` | ❌ 스키마만 존재 |
| T4 | 벡터 하이브리드 + 재순위 | ❌ 미착수 |

아래 순서대로 진행하면 됩니다. **0단계는 소유자가 PC에서 직접** 하고, 1단계 이후는 코딩
작업(Claude Code 또는 Codex)에 맡겨도 됩니다.

> **개발 우선 진행을 택한 경우:** 0단계(전체 색인)를 기다리지 않고 T3 코드부터 만들려면
> **[부록 A](#부록-a--코드-개발-우선-진행-codex-작업자-기준)** 를 보세요. 파일럿 인덱스(271건) 위에서
> 1~2단계 코드를 완성·검증한 뒤, 그다음에 0단계(전체 색인)를 돌리고 추출 배치를 완주하는
> 순서입니다. **비싼 추출 배치의 "완주"만 전체 색인 뒤로 미루고, 코드·프롬프트·검증은 지금 다
> 해둡니다.**

---

## 0단계 (지금 바로 · 소유자 작업) — 전체 코퍼스 색인하고 품질 재측정

T3에 시간을 쓰기 전에, 검색이 **실제 규모(~2,245건)에서도 잘 되는지**부터 확인합니다.
이게 다음 단계 착수의 게이트입니다.

1. 프로젝트 폴더로 이동:
   ```
   cd C:\Users\qchoi\Desktop\cowork\docs_app
   ```
2. 전체 원본 폴더를 색인 (경로는 실제 위치로 바꾸세요):
   ```
   python index_contracts.py --root D:\Contracts --out cs_index --full --batch-label full_001
   ```
   - 2,245건은 수 시간 걸릴 수 있고, 중간에 멈춰도 다시 같은 명령을 실행하면 이어서 처리됩니다(증분).
   - 끝나면 `cs_index\report_YYYYMMDD.md`가 생성됩니다. 이 리포트를 꼭 확인하세요.
3. 리포트에서 볼 것:
   - `status=empty`(스캔 PDF, 본문 검색 불가) 건수 — 답변 시 "검색 불가 n건" 고지 대상.
   - `error` 목록 — 아래 "알려진 위험"에 해당하면 그 파일만 빼고 재실행.
   - 유형·언어 분포가 상식과 맞는지 (파일럿에서 언어 오분류가 있었으니 특히 확인).
4. 골든셋으로 검색 품질 측정:
   ```
   python eval_search.py --out cs_index --tiers T1,T2
   ```
   - Q01~Q21 계열이 통과해야 T1/T2가 스케일에서도 OK라는 뜻입니다.
   - 결과는 `eval_history.jsonl`에 누적돼 이후 회귀 비교 기준이 됩니다.
5. 웹 UI로 눈으로도 확인 (선택):
   ```
   run_webapp.bat
   ```
   브라우저에서 실제 질의를 몇 개 던져보고 결과가 납득되는지 봅니다.

**알려진 위험 2가지** (전체 규모에서 처음 터질 수 있음, `NOTES_FOR_OWNER.md` §미구현 위험):
- 손상 PDF에서 추출이 멈추면 배치 전체가 정지할 수 있음 → 그 파일을 빼고 재실행 후,
  "파일 단위 추출 타임아웃" 구현을 지시하세요.
- 아주 깊은 한글 폴더 경로(260자 초과)에서 파일 열기 실패가 `unknown_error`로 찍힐 수 있음
  → 리포트에 보이면 "Windows 긴 경로(`\\?\`) 처리" 구현을 지시하세요.

**여력이 되면 같이:** `data/golden_queries.yaml`의 각 문항에 정답 파일(`expected_files`)과
`kw:` 키워드를 채워두면, 이후 recall 채점과 T4 필요성 판정 근거가 크게 좋아집니다(코드는
이미 지원, 데이터는 소유자 관할).

**0단계 통과 기준:** 전체 색인 완료 + eval 통과 + 웹에서 실제 질의 결과가 납득됨.
여기까지 되면 1단계로.

---

## 1단계 (1순위 추천 · 무료 · 효과 최대) — T3 착수: `enrich_contracts.py`

정확도를 가장 크게 올리는 핵심 투자입니다. 계약서를 1건씩 읽혀 **조항 존재맵·위치·요약**을
`doc_meta` 테이블에 저장하면, "earn-out 있는 SPA의 손해배상 상한 비교" 같은 질의가 본문
정독 대신 `WHERE has_earnout=1` + 조항맵 열람으로 환원됩니다. 정독량이 격감합니다.

코딩 작업(Claude Code)에 다음을 지시하세요:

1. **먼저 샘플 10건으로 추출 프롬프트 검수** (품질 루프). `extract_prompt_v1.md`의 스키마로
   SPA 10건을 추출해보고 결과 JSON을 사람이 확인 → 프롬프트 수정 → 재추출. 여기서 품질을
   잡고 나서 전량 배치로 갑니다.
2. `enrich_contracts.py` 구현 요건:
   - 문서 단위 커밋 = **재개형 배치**(중단돼도 다음 실행이 이어감), `enrich_progress.json` 유지.
   - **우선순위 큐**: SPA → SHA → SSA → MOU → ATA/BTA → JVA → CB/BW/EB → 주식교환 →
     분할합병 → 기타. (`--priority` 기본값 내장, 덮어쓰기 가능)
   - **dup 대표 1건만 추출** — 규모를 실질적으로 줄이는 첫 수단.
   - 이미 추출된 건 skip(증분), `meta_schema_version`으로 재추출 대상 식별.
   - 유료 API 없이 Claude Code 세션 한도 안에서 수일 분할 배치.
3. 배치를 돌려 `doc_meta`를 채웁니다. Claude Code 한도에 걸리면 우아하게 멈추고 재개.

**주의:** 이 단계는 개발 중 유료 API를 쓰지 않습니다(Claude Code 세션으로 추출).

---

## 2단계 — T3 활성화: `read_contract.py` + `[T3]` 기능 켜기

`doc_meta`가 채워지면 실제 검색 경로에 연결합니다. 코딩 작업에 지시:

1. `read_contract.py --file-key K --section 손해배상` — `clause_map`의 위치정보를 좌표로 쓰는
   **조항 단위 부분읽기**. 원문 전체 cat 금지의 구조적 대안.
2. `search_contracts.py`에 예약돼 있던 `--clause 태그 [--present/--absent]` 활성화.
3. `CLAUDE.md`에 `[T3]`로 표시된 로직 켜기 — 특히 **부재 증명**: `present=false`(평가 후 부재)와
   조항맵에서 생략된 "미평가"를 절대 혼동하지 않도록.
4. 골든셋 재측정으로 **T3 베이스라인** 확정:
   ```
   python eval_search.py --out cs_index --tiers T1,T2,T3
   ```
   이 수치가 4단계(T4) 절제실험의 비교 기준이 됩니다.

---

## 3단계 (선택 · 소품) — T2+: `answer_quick.py` + `lib/budget.py`

작고 저렴한 편의 기능이라 검색 품질 사인오프 후 아무 때나 끼워넣을 수 있습니다. 폰/원격에서
Claude Code 세션 열 것도 없이 CLI 즉답이 필요할 때 유용합니다.

- 상위 후보(기본 10건) 스니펫만 Haiku에 넘겨 2~3문장 즉답 + file_key 인용.
- 가드레일: 입력 상한 20k 토큰, **호출 전 예상 비용 출력**, 회당 $0.20 초과 시 실행 거부.
  실측 회당 1~3¢.
- 인프라는 이미 있음 — API 키 저장(설정 화면 `/settings`, DPAPI 암호화), `data/api_budget.yaml`
  예산. 붙이기만 하면 됩니다.
- 이때 처음으로 **소유자의 `ANTHROPIC_API_KEY`가 필요**합니다. 설정 화면에서 등록.

> 급하면 이 단계를 1~2단계보다 먼저 빼서 진행할 수도 있습니다. 다만 T2+는 검색 결과의
> 질 자체를 올리지는 못합니다(요약 편의일 뿐). 그래서 기본 추천은 T3 먼저입니다.

---

## 4단계 (마지막 · 확정됐지만 후순위) — T4: 벡터 하이브리드 + 재순위

T3 베이스라인이 나온 뒤에만 착수합니다. `embed_contracts.py` / `hybrid_search.py`로 임베딩 +
재순위를 붙이되, **각 구성요소(벡터, 리랭커)를 골든셋 절제실험(ablation)으로 기여도를 측정해
개별 채택/폐기**합니다. "구현하되 맹신하지 않는다"는 원칙 — 측정으로 도움이 확인된 것만 남깁니다.

---

## 병행 가능한 독립 트랙 — 웹 UI

검색 티어 작업과 분리돼 언제든 병행 가능하지만, **검색 품질 확정(0~2단계)보다는 후순위** 추천:
- UI-2 운영 대시보드(색인 상태·실패 파일·batch 통계·saved searches·피드백·보정 후보 export)
- UI-3 나머지(비교 목록·북마크·리서치 세션·선택 문단 export)
- UI-4 AI 답변 화면 (T2+/T4 답변 경로가 준비된 후)

---

## 한눈에 보는 순서

```
0. 전체 색인 + eval 재측정 (소유자, 지금)      ← 게이트
      ↓ 통과하면
1. enrich_contracts.py = doc_meta 채우기 (T3, 무료·최대 효과)  ← 1순위
      ↓
2. read_contract.py + [T3] 기능 켜기 → T3 베이스라인 측정
      ↓
3. answer_quick.py 즉답 (T2+, 선택·소품, API 키 필요)  ← 언제든 끼워넣기 가능
      ↓
4. 벡터 하이브리드 (T4, 절제실험으로 채택 판정)  ← 마지막
─────
(병행) 웹 UI: UI-2 → UI-3 → UI-4   ← 후순위
```

**당장 할 일 = 0단계.** `python index_contracts.py --root <원본폴더> --out cs_index --full`
부터 실행하세요.

---

# 부록 A — 코드 개발 우선 진행 (Codex 작업자 기준)

0단계(전체 색인)를 기다리지 않고, **지금 있는 파일럿 인덱스(`cs_index`, 271건) 위에서**
T3 코드를 거의 다 만들고 검증하는 방법입니다. 작업자는 Codex로 상정합니다.

## 작업자·모델에 관한 사실 (먼저 알아둘 것)

- **색인(`index_contracts.py`)은 AI를 쓰지 않습니다.** 텍스트 추출 + 규칙 분류뿐인 결정적
  처리라, 색인을 Codex로 돌리든 Claude Code로 돌리든 결과가 동일합니다. "색인 AI 선택"이라는
  대상 자체가 없습니다.
- **`enrich_contracts.py`(T3 추출)는 AI를 씁니다.** 단, 유료 API를 호출하는 구조가 아니라,
  스크립트는 재개형 배치 **하네스**이고 실제 추출 추론은 그걸 구동하는 코딩 에이전트 세션
  (Claude Code 또는 Codex, 둘 다 구독 로그인·API 키 불필요)이 수행합니다. 따라서 **Codex로
  진행 가능**합니다. "Claude Code가 한다"는 건 문서상 기본 상정일 뿐 코드 하드코딩이 아닙니다.
- **전제 조건:** `enrich_contracts.py`를 처음부터 **worker-agnostic**(특정 API를 하드코딩하지
  않음)으로 만들어야 Codex가 구동할 수 있습니다. 아래 A-1 프롬프트에 이 요건을 넣어 둡니다.
- **UI 선택 기능은 없습니다.** 웹앱의 Agent Setup Wizard는 미구현(out of scope)이고, 구현돼도
  설치·로그인 상태 표시일 뿐 enrich를 라우팅하지 않습니다. 작업자 선택은 **어떤 도구를 여느냐**로.
- **모델별 추출 품질 차이:** 추출 프롬프트(`extract_prompt_v1.md`)는 Claude 기준으로 설계됐습니다.
  Codex(GPT)로 추출한다면 A-2의 샘플 10건 검수를 특히 꼼꼼히 하세요.

## 진행 순서 (파일럿 위에서, 한 번에 한 단계)

1. **A-1** `enrich_contracts.py` 하네스 구현
2. **A-2** 샘플 10건 추출 품질 루프 (프롬프트 검수 게이트)
3. **A-3** `read_contract.py` 조항 단위 부분읽기
4. **A-4** `search_contracts.py`에 `[T3]` 검색 기능 활성화
5. **A-5** T3 골든 문항 + `eval_search.py --tiers T1,T2,T3` 연결
6. → 여기까지 파일럿에서 통과하면 **0단계(전체 색인)** 실행 후 전량 추출 배치 완주

## Codex에 붙여 쓸 프롬프트

각 프롬프트는 한 번에 하나만 맡기세요. 모든 프롬프트에 공통으로 적용되는 규칙이라
매번 첫 줄에 두는 것을 권장합니다:

> **공통 규칙:** 저장소의 `IMPLEMENTATION_BRIEF.md`, `CODING_SEQUENCE.md`,
> `CODING_AGENT_RULES.md`, `docs_progress_v2.md`, `CLAUDE.md`를 기준 문서로 따른다.
> Python 3.9 호환 문법만 사용(match 등 금지). 의존성 화이트리스트(python-docx,
> pdfminer.six, PyYAML, 표준 라이브러리) 밖의 패키지를 추가하지 마라. 결정적(deterministic)
> 동작 — 같은 입력이면 같은 출력. 개발 중 유료 API를 호출하지 마라. 요청한 것만 구현하고,
> 인접 코드를 임의로 리팩터링하지 마라. 완료 기준은 결정적 테스트 통과다.

### A-1 · enrich_contracts.py 하네스

```
enrich_contracts.py를 구현해줘. 이건 T3 보강(enrichment) 배치의 "하네스"다.
목적: cs_index 카탈로그에 색인된 계약서를 1건씩 처리해 구조화 메타를 doc_meta 테이블에 저장한다.

핵심 설계 (반드시 지킬 것):
- worker-agnostic: 특정 AI API(anthropic/openai)를 호출하거나 하드코딩하지 마라.
  실제 조항 추출 추론은 이 스크립트를 구동하는 코딩 에이전트 세션이 수행한다.
  스크립트는 (a) 다음 처리 대상 선정, (b) txt 캐시 읽어 에이전트에 제시할 입력 구성,
  (c) 에이전트가 만든 JSON을 검증해 doc_meta에 기록, (d) 진행률/재개 관리만 담당한다.
  에이전트-스크립트 인터페이스(입력 JSON을 어디서 읽고 결과 JSON을 어디에 쓰는지)를
  파일 기반으로 명확히 정의하고 README에 적어라.
- 재개형 배치: 문서 단위 커밋. 중단돼도 다음 실행이 이어간다. enrich_progress.json 유지.
- 증분: 이미 추출된 file_key는 skip. meta_schema_version 컬럼으로 재추출 대상 식별.
- 우선순위 큐: SPA → SHA → SSA → MOU → ATA/BTA → JVA → CB/BW/EB → 주식교환 →
  분할합병 → 기타. --priority로 덮어쓰기 가능, 기본값 내장.
- dup 대표 1건만 추출 (dup_group 대표만 대상).
- status='ok' 문서만 대상. missing/empty/error 제외.

doc_meta 스키마는 docs_progress_v2.md 계층 1.5 초안과 extract_prompt_v1.md를 따른다
(file_key, meta_schema_version, extracted_at, parties_json, deal_type_detail,
consideration_json, clause_map_json[조항 존재+위치 문단범위+3줄요약], special_notes,
definitions_json, confidence). clause_map의 위치정보는 read_contract.py의 좌표가 된다.

CLI: --out cs_index [--priority ...] [--file-key K] [--limit N] [--dry-run].
테스트: 재개(중단 후 이어감), 증분 skip, 우선순위 정렬, dup 대표만 처리, 스키마 검증 실패
처리 — 결정적 테스트로 작성. 대상은 로컬 파일럿 cs_index.
개발 중 실제 AI 호출 없이 mock 추출 결과로 테스트해라.
```

### A-2 · 샘플 10건 품질 루프 (게이트)

```
파일럿 cs_index에서 SPA 10건을 골라 enrich_contracts.py 인터페이스로 조항 추출을 실제로
수행해줘(네 세션에서 계약서를 읽고 extract_prompt_v1.md 스키마대로 JSON을 만든다).
각 건의 clause_map(진술보장/선행조건/확약/손해배상[상한·존속기간]/해제/경업금지/earn-out/
MAC/분쟁해결)이 실제 원문과 맞는지, 위치 문단범위가 정확한지, confidence가 타당한지
표로 정리해줘. 틀린 항목과 프롬프트 개선안을 제시하되, extract_prompt_v1.md나 term_dict.yaml을
임의 수정하지 말고 제안만 해라(사람 승인 후 반영).
```

### A-3 · read_contract.py

```
read_contract.py를 구현해줘. doc_meta.clause_map_json의 위치정보(문단 범위)를 좌표로 써서
조항 단위 부분읽기를 한다. CLI: --out cs_index --file-key K --section 손해배상 [--context N].
해당 조항의 문단 범위만 txt 캐시에서 읽어 출력한다. 원문 파일 전체를 읽지 마라.
section 이름은 term_dict.yaml canonical 태그로 정규화해 매칭한다. doc_meta에 해당 태그가
없으면 "미평가"로 명확히 표기하고, 있지만 present=false면 "평가 후 부재"로 구분해 표기한다.
doc_meta의 txt_hash가 현재 content_hash와 다르면(원문 갱신됨) "재추출 전"임을 표시한다.
테스트: 조항 범위 정확 출력, 미평가/부재 구분, stale 표기 — 결정적 테스트. 대상 파일럿 cs_index.
```

### A-4 · search_contracts.py [T3] 활성화

```
search_contracts.py에 예약돼 있던 [T3] 기능을 활성화해줘.
- --clause 태그 [--present | --absent]: doc_meta.clause_map_json을 SQL 질의해 해당 조항이
  present=true/false인 문서로 후보를 좁힌다. clause_map에서 그 태그가 생략된 문서는 "미평가"로
  분류하고 present=false(평가 후 부재)와 절대 혼동하지 마라. --absent는 present=false만
  반환하고, 미평가·confidence=low는 "확인 필요"로 분리 표기한다.
- 기존 T1/T2 경로(메타 필터, FTS5, 용어사전 확장, RRF 랭킹, dedup)는 건드리지 마라.
- --json 출력에 clause 근거(어떤 조항이 present인지, 위치, confidence)를 포함한다.
테스트: --clause present/absent 필터, 미평가 vs 부재 구분, T1/T2 회귀 없음 — 결정적 테스트.
대상 파일럿 cs_index(A-1으로 doc_meta가 채워진 상태).
```

### A-5 · T3 골든 문항 + eval 연결

```
eval_search.py가 --tiers에 T3를 포함해 실행되도록 확장해줘. data/golden_queries.yaml에
T3 문항(조항 존재/부재, 수치 조건 예: 손해배상 상한 조건)을 추가하는 자리와 채점 로직을
연결한다. golden_queries.yaml 데이터 자체는 사람이 채우므로, 코드는 T3 문항이 있으면
--clause 경로로 채점하고 없으면 건너뛰게만 해라(데이터를 임의 생성하지 마라).
python eval_search.py --out cs_index --tiers T1,T2,T3 가 오류 없이 돌고 문항별 pass/fail을
출력하며 eval_history.jsonl에 누적되게 한다. 테스트: T3 문항 채점, T3 문항 부재 시 skip,
회귀 로깅 — 결정적 테스트.
```

## 파일럿 완료 후 (0단계로 전환)

A-1~A-5가 파일럿에서 전부 통과하면, 본문 0단계로 가서 전체 코퍼스를 색인(Codex 터미널에서
`python index_contracts.py --root <원본폴더> --out cs_index --full` 실행)하고 eval를 재측정한
뒤, 검증된 전체 카탈로그 위에서 `enrich_contracts.py` 추출 배치를 우선순위 큐대로 완주합니다.
이때 Claude Code 또는 Codex 세션 한도에 걸리면 재개형 배치라 다시 실행해 이어가면 됩니다.
