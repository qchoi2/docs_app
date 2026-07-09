# AGENT_SETUP_AND_MODEL_OPTIONS — Claude Code / Codex 준비 절차와 선택 기준
_2026-07-09 · 최초 실행 환경에서 코딩 에이전트가 아직 설치·로그인되지 않은 경우를 위한 운영 지침._

## 1. 적용 원칙

이 패키지는 기본적으로 **Claude Code 구독제**를 대량 작업자/코딩 에이전트로 상정한다. 다만 사용자가 **Codex 구독요금제**를 사용할 수 있는 경우에는 동일한 구현 패키지를 Codex에도 선택적으로 맡길 수 있다.

- **Claude Code 우선**: 장시간 배치, 대량 파일 처리, 계약서 구조화 추출, 반복 리팩터링.
- **Codex 선택 활용**: VS Code 내 코드 수정, 테스트 실패 원인 파악, 작은 단위의 패치, Claude Code 한도 도달 시 대체 작업자.
- **GPT-5.5 검토 역할**: 구현 전후 설계 검토, 단계 쪼개기, 결과물 리뷰, 오류 메시지 해석.
- **API 실호출 금지(개발 단계)**: Phase 1 구현·테스트 중에는 유료 API를 실호출하지 않는다. `answer_quick.py`는 mock으로만 검증한다.
- **역할 분리**: Claude Code/Codex는 개발·배치 작업자이고, `answer_quick.py`(G1.5 Haiku), A9/A10, G2는 웹앱/CLI 런타임에서 Anthropic API를 직접 호출하는 별도 기능이다.
- **Codex API key 금지**: Codex는 ChatGPT 구독계정 로그인 기반으로만 사용하고 OpenAI API key를 요구·저장하지 않는다.
- **Claude 런타임 API key 필요**: Haiku/Sonnet/Opus API 경로를 실제로 쓰려면 사용자가 `ANTHROPIC_API_KEY`를 제공해야 한다. 단, 이는 Agent Setup Wizard가 아니라 별도 **Runtime API Settings** 또는 PC 로컬 secret 저장소에서 처리한다. `.env`는 개발자용 백업 경로로만 둔다.

## 2. 최초에 Claude Code가 설치되어 있지 않은 경우

README 작성 시 아래 절차를 그대로 포함한다.

### 2.1 사전 확인

```bash
claude --version
```

- `claude` 명령이 없으면 Claude Code CLI를 설치한다.
- Windows에서는 PowerShell/CMD/WSL 중 실제로 사용할 셸을 먼저 정한다.
- 회사/개인 PC의 보안정책상 설치 스크립트 실행이 제한되면 관리자 권한, 보안 예외 또는 대체 설치 방식을 선택한다.

### 2.2 설치

macOS/Linux/WSL:

```bash
curl -fsSL https://claude.ai/install.sh | bash
claude --version
```

Windows PowerShell:

```powershell
irm https://claude.ai/install.ps1 | iex
claude --version
```

Windows CMD:

```cmd
curl -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd && del install.cmd
claude --version
```

설치 후 새 터미널을 열어 `claude --version`이 동작하는지 확인한다. PATH 문제로 인식되지 않으면 설치 안내에 따라 PATH를 갱신하거나 새 터미널을 연다.

### 2.3 로그인

```bash
claude
```

최초 실행 시 로그인 프롬프트가 뜨면 브라우저에서 구독 계정으로 인증한다. 실행 중 계정을 바꾸거나 다시 인증해야 하면 Claude Code 세션 안에서 `/login`을 입력한다. 로그인 후 아래 명령으로 프로젝트 루트에서 실행 가능 여부를 확인한다.

```bash
cd contract-search
claude
```

프로젝트 루트에는 `CLAUDE.md`가 있어야 하며, 이는 패키지의 `CLAUDE_v2.md`를 복사한 파일이다.

## 3. Claude Code 로그인 또는 실행이 안 될 때

아래 순서로만 점검하고, 해결 전에는 구현을 진행하지 않는다.

1. **명령 인식 문제**: `claude --version`이 실패하면 설치/PATH 문제다. 재설치 또는 PATH 확인.
2. **브라우저 로그인 문제**: `claude` 최초 실행 또는 `/login`이 멈추면 기본 브라우저, 회사 보안 프록시, VPN, 팝업 차단을 확인.
3. **권한 문제**: 프로젝트 폴더에 쓰기 권한이 없으면 저장소를 사용자 홈 또는 작업 가능한 경로로 옮긴다.
4. **구독/한도 문제**: 로그인은 되었지만 사용이 막히면 구독 상태 또는 사용한도 도달 여부를 확인한다.
5. **샌드박스/파일시스템 문제**: 코드 수정이 반영되지 않거나 읽기 전용처럼 보이면, 해당 에이전트에서만 파일시스템 뷰가 꼬인 것일 수 있다. `git status`, 새 파일 생성/삭제, `cat` 결과를 비교하고, 이상하면 새 세션/새 터미널에서 재시작한다.

문제가 지속되면 README의 FAQ에 실제 오류 메시지를 붙여 기록하고, 작업은 Codex 또는 수동 터미널 방식으로 전환한다.

## 4. Codex 구독요금제 선택 활용

Codex를 사용할 수 있으면 아래와 같이 역할을 나눈다.

Codex는 ChatGPT 계정으로 로그인해 사용할 수 있다. VS Code 확장을 우선 사용하되, CLI가 필요하면 아래 중 하나를 사용한다.

macOS/Linux:

```bash
curl -fsSL https://chatgpt.com/codex/install.sh | sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://chatgpt.com/codex/install.ps1 | iex"
```

패키지 매니저가 편하면 `npm install -g @openai/codex` 또는 `brew install --cask codex`도 가능하다. 설치 후 `codex`를 실행하고 ChatGPT 계정으로 로그인한다.


| 상황 | 권장 작업자 | 이유 |
|---|---|---|
| Step 1~12의 작은 코드 구현 | Claude Code 또는 Codex | 둘 다 가능. 한 번에 한 Step만 맡긴다. |
| VS Code에서 파일 단위 수정 | Codex | IDE 컨텍스트와 diff 확인이 편함. |
| 대량 배치 추출·반복 실행 | Claude Code | 원 설계상 장시간 작업자. |
| Claude Code 한도 도달 | Codex | 다음 Step 또는 테스트 수정만 이어서 진행. |
| 설계/품질 리뷰 | GPT-5.5 | 구현자와 검토자를 분리. |

Codex를 쓰더라도 `IMPLEMENTATION_BRIEF.md`, `CODING_SEQUENCE.md`, `CODING_AGENT_RULES.md`를 동일하게 적용한다. Codex에게는 다음 첫 지시문을 사용한다.

```text
IMPLEMENTATION_BRIEF.md, CODING_SEQUENCE.md, CODING_AGENT_RULES.md를 먼저 읽어라.
현재 Step 하나만 구현하고, 범위를 넘는 개선은 NOTES_FOR_OWNER.md에 적어라.
유료 API 실호출은 금지한다. 테스트 통과 후 관련 파일만 git add/commit하라.
```

## 5. Claude Code와 Codex를 같이 쓸 때의 충돌 방지

- 동시에 같은 브랜치/같은 파일을 수정하지 않는다.
- 한 에이전트가 Step을 완료하고 commit한 뒤, 다른 에이전트는 `git pull` 또는 최신 commit 확인 후 시작한다.
- Step 단위 commit 규칙을 유지한다: `step-N: ...`, `ui-N: ...`.
- 테스트 실패 상태는 commit하지 않는다.
- 두 에이전트가 다른 판단을 하면 `IMPLEMENTATION_BRIEF.md`가 우선이고, 그다음 `docs_progress_v2.md`, 나머지 문서 순서로 판단한다.

## 6. README에 반드시 들어갈 문구

README의 설치 섹션에는 아래 내용을 포함한다.

```text
처음 실행하기 전에 Claude Code가 설치·로그인되어 있는지 확인한다.
설치되어 있지 않으면 운영체제에 맞는 Claude Code 공식 설치 명령을 실행한 뒤 `claude`를 실행해 브라우저 로그인을 완료한다.
Claude Code 사용이 불가하거나 한도에 도달한 경우, Codex 구독요금제를 선택적으로 사용해 동일한 Step 단위 구현을 진행할 수 있다.
단, 어느 에이전트를 쓰더라도 IMPLEMENTATION_BRIEF.md / CODING_SEQUENCE.md / CODING_AGENT_RULES.md를 먼저 읽고, 유료 API 실호출은 금지한다.
```

## 7. 웹앱 Agent Setup Wizard 반영 원칙

웹앱에는 **설치·로그인 대리 기능**이 아니라 **상태 진단 및 절차 안내 기능**을 넣는다. 목표는 사용자가 웹앱 안에서 현재 상태를 이해하고, 필요한 명령을 복사해 **Windows PowerShell 또는 VS Code 터미널**에서 직접 실행한 뒤, 웹앱에서 다시 검사할 수 있게 하는 것이다.

### 7.1 UI가 제공할 기능

```text
설정 > AI 코딩 에이전트

[상태 진단]
- Claude Code: 설치됨 / 미설치 / 로그인 필요 / 사용 가능 / 오류
- Codex CLI: 설치됨 / 미설치 / 로그인 필요 / 사용 가능 / 오류
- Node.js/npm: 설치됨 / 미설치 / 버전 불충분
- Git: 설치됨 / 미설치
- 프로젝트 폴더 쓰기 권한: 정상 / 오류
- 샌드박스 또는 파일시스템 상태: 정상 / 의심 / 오류

[권장 조치]
- 미설치 항목별 설치 명령 표시
- 로그인 필요 항목별 CLI 로그인 절차 표시
- 오류 메시지별 FAQ 연결
- 설치 후 [다시 검사] 버튼 제공

[작업자 선택]
- Claude Code 우선
- Codex 보조
- Claude 불가 시 Codex로 전환
- 둘 다 불가 시 수동 터미널/VS Code 절차 표시
```

### 7.2 UI가 직접 하지 않을 것

Agent Setup Wizard는 아래 정보를 직접 수집·저장·대리 입력하지 않는다.

```text
- Claude 계정 비밀번호
- ChatGPT 계정 비밀번호
- OAuth 토큰 / 세션 토큰
- OpenAI API key
- Codex 관련 API key
- 브라우저 로그인 코드 또는 임시 인증 코드
```

**중요한 경계:** Agent Setup Wizard는 Claude Code/Codex의 설치·로그인 상태만 다룬다. 반면 `answer_quick.py`(G1.5 Haiku), A9/A10, G2 같은 런타임 API 기능은 웹앱 백엔드가 Anthropic API를 직접 호출하는 구조이므로, 실제 사용 시 사용자의 `ANTHROPIC_API_KEY`가 필요하다. 이 키는 Agent Setup Wizard가 아니라 별도 **Runtime API Settings** 또는 서버 `.env`에서 받는다.

**Codex는 API key를 가져오지 않는 구조로 설계한다.** Codex 사용 경로는 ChatGPT 구독계정 기반의 VS Code 확장 또는 CLI 로그인 흐름을 전제로 하며, 웹앱은 OpenAI API key를 입력받는 화면을 만들지 않는다. OpenAI API 직접 호출은 본 프로젝트 범위가 아니다.

### 7.3 설치 명령 자동 실행에 대한 제한

웹앱에서 설치 버튼을 제공하더라도 기본값은 **명령어 복사 방식**으로 둔다. PC 백엔드에서 직접 설치 명령을 실행하는 기능은 선택 기능이며, 구현하더라도 아래 조건을 만족해야 한다.

```text
- 관리자 인증 필수
- 실행 가능한 명령 allowlist 고정
- 사용자가 실행 전 명령 전문을 확인
- dry-run 또는 진단 우선
- 실행 로그 저장
- 실패 시 원복/수동 조치 안내
- 임의 shell 입력 금지
```

초기 버전에서는 자동 설치 버튼을 만들지 말고, `copy command` + `다시 검사` UX를 구현한다.

### 7.4 진단 API 설계

웹앱 백엔드는 다음 정도의 읽기 전용 진단만 제공한다.

```text
GET /admin/agents/status

응답 예시:
{
  "claude": {"installed": true, "version": "...", "login_state": "unknown|ready|needs_login|error"},
  "codex": {"installed": false, "version": null, "login_state": "unknown|ready|needs_login|error"},
  "node": {"installed": true, "version": "..."},
  "npm": {"installed": true, "version": "..."},
  "git": {"installed": true, "version": "..."},
  "project_path": {"writable": true},
  "recommended_next_action": "codex_install_or_claude_login"
}
```

로그인 상태는 토큰을 읽어서 판단하지 않는다. 가능한 경우 `claude`/`codex`의 비파괴적 진단 명령 또는 간단 실행 결과만 보고, 확실하지 않으면 `unknown`으로 표시한다.

### 7.5 PC 로컬 진단 실행 원칙

Agent Setup Wizard의 백엔드 진단은 임의 shell 실행기가 아니다. Windows PC 로컬 환경에서 아래 allowlist 명령만 `shell=False`, timeout, 출력 길이 제한을 적용해 실행한다.

```text
claude --version
codex --version
node --version
npm --version
git --version
python --version
```

설치 명령 자동 실행, 사용자가 입력한 명령 실행, 환경변수 덤프, 토큰 파일 읽기는 MVP에서 금지한다.

## 8. Runtime API Settings — Haiku/Sonnet 직접 호출 경로

`docs_progress_v2.md`의 원래 구조상 Haiku는 단순한 코딩 에이전트가 아니라, 다음 기능에서 **백엔드가 직접 호출하는 Anthropic API 모델**이다.

```text
- G1.5 answer_quick.py: 검색 상위 후보 스니펫을 Haiku에 전달해 2~3문장 즉답
- A10 분류 폴백: 미분류 폴더/대표 파일을 Haiku로 판정
- A9 교차검증: Claude Code 추출 결과와 Sonnet API 결과 비교
- G2 답변: T4에서 Haiku/Sonnet/Opus 중 선택 호출
```

따라서 API 기능을 실제로 켜려면 사용자가 Anthropic API key를 제공해야 한다. MVP에서는 **관리자 전용 Runtime API Settings 화면에 `ANTHROPIC_API_KEY` 입력창을 만든다.** `.env` 직접 편집은 고급/수동 백업 경로로만 남긴다.

```text
1. 기본 경로: 관리자 전용 `설정 > API 예산 및 키` 화면에서 Anthropic API key 입력
2. 저장 후: PC 로컬 사용자 전용 secret 저장소에 저장하고, UI에는 마지막 4자리만 표시
3. 관리 기능: [저장] [연결 테스트] [삭제/교체] 제공
4. 금지: 프론트엔드 localStorage/sessionStorage 저장, 로그 출력, 응답 본문 노출
5. PC 로컬 저장 위치 권장: `%APPDATA%/contract-search/secrets.json` 또는 동등한 사용자 전용 secret 저장소
6. 수동 백업 경로: 개발자용 `.env`에 ANTHROPIC_API_KEY=... 직접 설정
```

운영 원칙:

```text
- API key 입력/저장은 Agent Setup Wizard와 분리하고, Runtime API Settings에 `ANTHROPIC_API_KEY` 입력창을 둔다.
- Codex를 위해 OpenAI API key를 받지 않는다.
- API key가 없으면 G1.5/A9/A10/G2 기능은 disabled 상태로 표시한다.
- api_budget.yaml의 per_call/per_run 상한이 null이면 API key가 있어도 호출하지 않는다.
- 모든 호출은 lib/budget.py를 통과하고 api_ledger.jsonl 및 api_cache를 사용한다.
- 개발·테스트 단계에서는 mock만 사용하고 실 API 호출은 사용자의 명시적 실행 때만 허용한다.
```
