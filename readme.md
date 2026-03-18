<div align="center">

# tunapi

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/github/actions/workflow/status/hang-in/tunapi/release.yml?label=tests)](https://github.com/hang-in/tunapi/actions)
[![GitHub release](https://img.shields.io/github/v/release/hang-in/tunapi?include_prereleases)](https://github.com/hang-in/tunapi/releases)

Mattermost and Telegram bridge for coding agent CLIs

[**한국어**](#한국어) | [**English**](docs/README_EN.md) | [**日本語**](docs/README_JA.md)

</div>

---

## 한국어

**Claude Code**, **Codex**, **Gemini CLI** 등 코딩 에이전트를 Mattermost 채널이나 Telegram 채팅에서 실행하세요.

[takopi](https://github.com/banteg/takopi)에서 포크. 현재 포크의 초점은 Mattermost이며, upstream의 Telegram transport도 그대로 유지됩니다.

### 주요 기능

- **두 가지 트랜스포트** — Mattermost (WebSocket, Bearer 인증) + Telegram (long-polling, 인라인 키보드)
- **멀티 엔진** — Claude, Codex, Gemini, OpenCode, Pi. 채널별로 다른 엔진 매핑
- **실시간 진행 표시** — 도구 호출, 파일 변경, 경과 시간을 스트리밍
- **세션 이어가기** — resume 토큰으로 대화 컨텍스트 유지 (`session_mode = "chat"`)
- **프로젝트 & 워크트리** — 채널을 레포에 바인딩, 브랜치별 git worktree
- **취소** — Mattermost: 🛑 반응 / Telegram: 인라인 버튼
- **파일 전송** — 첨부 파일 자동 인식, 에이전트 작업 디렉토리에 저장
- **음성 전사** — 음성 메시지를 텍스트로 변환하여 에이전트에 전달
- **트리거 모드** — @멘션 감지로 봇 호출 (그룹 채널에서 유용)
- **채팅 설정** — 채널별 엔진/트리거 모드 저장 (`/model`, `/trigger`)
- **슬래시 커맨드** — `/help`, `/model`, `/trigger`, `/status`, `/cancel`, `/file`, `/new`
- **플러그인** — 엔진, 트랜스포트, 커맨드를 Python entry point로 추가

> **참고:** 에이전트는 이미지를 분석할 수 없습니다. 이미지 파일은 전달되지만 내용 분석은 지원되지 않습니다.

### 요구사항

- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Python 3.14+ (`uv python install 3.14`)
- 에이전트 CLI 최소 1개: `claude`, `codex`, `gemini`, `opencode`, `pi`

### 설치

```sh
uv tool install -U tunapi
```

소스에서 설치:

```sh
git clone https://github.com/hang-in/tunapi.git
cd tunapi
uv tool install -e .
```

### 설정

#### 1. 트랜스포트 선택

`~/.tunapi/tunapi.toml`:

```toml
transport = "mattermost"   # 또는 "telegram"
```

#### 2a. Mattermost

**System Console** → **Integrations** → **Bot Accounts** → **Add Bot Account**에서 봇을 만들고 Access Token을 복사하세요.

```toml
transport = "mattermost"
default_engine = "claude"

[transports.mattermost]
url = "https://mm.example.com"
token = "봇-액세스-토큰"
channel_id = "기본-채널-id"
show_resume_line = false
session_mode = "chat"
```

`.env`로 토큰 관리:

```sh
MATTERMOST_TOKEN=봇-액세스-토큰
```

#### 2b. Telegram

[@BotFather](https://t.me/BotFather)에서 봇을 만들고 토큰을 복사하세요.

```toml
transport = "telegram"
default_engine = "claude"

[transports.telegram]
bot_token = "123456:ABC-DEF..."
chat_id = 123456789
```

Telegram 전용 기능: 토픽, 포워드 합치기, 미디어 그룹

양쪽 트랜스포트 공통 기능: 음성 전사, 파일 전송, 트리거 모드 (@멘션 감지), 슬래시 커맨드, 채팅 설정 저장

#### 3. 채널별 엔진 매핑 (선택)

```toml
[projects.backend]
path = "/home/user/projects/backend"
default_engine = "claude"
chat_id = "claude-채널-id"

[projects.infra]
path = "/home/user/projects/infra"
default_engine = "codex"
chat_id = "codex-채널-id"

[projects.research]
path = "/home/user/projects/research"
default_engine = "gemini"
chat_id = "gemini-채널-id"
```

### 사용법

```sh
tunapi                                    # 포그라운드 실행
nohup tunapi > /tmp/tunapi.log 2>&1 &    # 백그라운드 실행
tunapi --debug                            # 디버그 모드
```

| 동작 | 방법 |
|------|------|
| 엔진 선택 | `/claude`, `/codex`, `/gemini` 접두사 |
| 프로젝트 등록 | `tunapi init my-project` |
| 프로젝트 지정 | `/my-project 버그 고쳐줘` |
| 워크트리 사용 | `/my-project @feat/branch 작업해줘` |
| 새 세션 시작 | `/new` |
| 실행 취소 | 🛑 반응 (Mattermost) / Cancel 버튼 (Telegram) |
| 설정 확인 | `tunapi config list` |

### 지원 엔진

| 엔진 | CLI | 상태 |
|------|-----|------|
| Claude Code | `claude` | 내장 |
| Codex | `codex` | 내장 |
| Gemini CLI | `gemini` | 내장 |
| OpenCode | `opencode` | 내장 |
| Pi | `pi` | 내장 |

### 트랜스포트 기능 비교

| 기능 | Mattermost | Telegram |
|------|------------|----------|
| 세션 이어가기 | ✅ | ✅ |
| 실시간 진행 표시 | ✅ | ✅ |
| 취소 | 🛑 반응 | 인라인 버튼 |
| 채널별 엔진 | ✅ | ✅ |
| Config 핫 리로드 | ✅ | ✅ |
| 파일 전송 | ✅ | ✅ |
| 음성 전사 | ✅ | ✅ |
| 트리거 모드 (@멘션) | ✅ | ✅ |
| 슬래시 커맨드 | ✅ | ✅ |
| 채팅 설정 저장 | ✅ | ✅ |
| 토픽 / 포럼 | — | ✅ |
| 포워드 합치기 | — | ✅ |
| 미디어 그룹 | — | ✅ |

### 플러그인

엔진, 트랜스포트, 커맨드를 entry-point 플러그인으로 추가할 수 있습니다.

[`docs/how-to/write-a-plugin.md`](docs/how-to/write-a-plugin.md) / [`docs/reference/plugin-api.md`](docs/reference/plugin-api.md)

### 개발

```sh
uv sync --dev
just check                              # format + lint + typecheck + tests
uv run pytest --no-cov -k "test_name"   # 단일 테스트
```

### 라이선스

MIT — [LICENSE](LICENSE)
