<div align="center">

# tunapi

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/github/actions/workflow/status/hang-in/tunapi/release.yml?label=tests)](https://github.com/hang-in/tunapi/actions)
[![GitHub release](https://img.shields.io/github/v/release/hang-in/tunapi?include_prereleases)](https://github.com/hang-in/tunapi/releases)

Mattermost and Telegram bridge for coding agent CLIs

[한국어](../readme.md) | [**English**](#english) | [日本語](README_JA.md)

</div>

---

## English

Run **Claude Code**, **Codex**, **Gemini CLI**, and other coding agents from any Mattermost channel or Telegram chat.

Forked from [takopi](https://github.com/banteg/takopi). The current fork focuses on Mattermost, while the Telegram transport from upstream is fully retained.

### Features

- **Two transports** — Mattermost (WebSocket, Bearer auth) + Telegram (long-polling, inline keyboard)
- **Multi-engine** — Claude, Codex, Gemini, OpenCode, Pi. Map each channel/chat to a different engine
- **Live progress** — stream tool calls, file changes, and elapsed time as the agent works
- **Session resume** — conversations persist across messages via resume tokens (`session_mode = "chat"`)
- **Projects & worktrees** — bind channels to repos; mention a branch to run in a dedicated git worktree
- **Cancel** — Mattermost: 🛑 reaction / Telegram: inline keyboard button
- **Plugin system** — add engines, transports, or commands via Python entry points

### Requirements

- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Python 3.14+ (`uv python install 3.14`)
- At least one agent CLI on PATH: `claude`, `codex`, `gemini`, `opencode`, or `pi`

### Install

```sh
uv tool install -U tunapi
```

From source:

```sh
git clone https://github.com/hang-in/tunapi.git
cd tunapi
uv tool install -e .
```

### Setup

#### 1. Choose a transport

`~/.tunapi/tunapi.toml`:

```toml
transport = "mattermost"   # or "telegram"
```

#### 2a. Mattermost

Create a bot in **System Console** → **Integrations** → **Bot Accounts** → **Add Bot Account**, then copy the **Access Token**.

```toml
transport = "mattermost"
default_engine = "claude"

[transports.mattermost]
url = "https://mm.example.com"
token = "your-bot-access-token"
channel_id = "default-channel-id"
show_resume_line = false
session_mode = "chat"
```

Or use a `.env` file:

```sh
MATTERMOST_TOKEN=your-bot-access-token
```

#### 2b. Telegram

Create a bot via [@BotFather](https://t.me/BotFather) and copy the token.

```toml
transport = "telegram"
default_engine = "claude"

[transports.telegram]
bot_token = "123456:ABC-DEF..."
chat_id = 123456789
```

Telegram-only features: topics, voice notes, file transfer, forward coalescing, media groups, trigger mode, command menu, and persistent chat preferences.

#### 3. Map channels to engines (optional)

```toml
[projects.backend]
path = "/home/user/projects/backend"
default_engine = "claude"
chat_id = "claude-channel-id"

[projects.infra]
path = "/home/user/projects/infra"
default_engine = "codex"
chat_id = "codex-channel-id"

[projects.research]
path = "/home/user/projects/research"
default_engine = "gemini"
chat_id = "gemini-channel-id"
```

### Usage

```sh
tunapi                                    # foreground
nohup tunapi > /tmp/tunapi.log 2>&1 &    # background
tunapi --debug                            # debug mode
```

| Action | How |
|--------|-----|
| Pick an engine | `/claude`, `/codex`, `/gemini` prefix |
| Register a project | `tunapi init my-project` |
| Target a project | `/my-project fix the bug` |
| Use a worktree | `/my-project @feat/branch do something` |
| Start a new session | `/new` |
| Cancel a running task | 🛑 reaction (Mattermost) or Cancel button (Telegram) |
| View config | `tunapi config list` |

### Supported Engines

| Engine | CLI | Status |
|--------|-----|--------|
| Claude Code | `claude` | Built-in |
| Codex | `codex` | Built-in |
| Gemini CLI | `gemini` | Built-in |
| OpenCode | `opencode` | Built-in |
| Pi | `pi` | Built-in |

### Transport Feature Matrix

| Feature | Mattermost | Telegram |
|---------|------------|----------|
| Session resume | ✅ | ✅ |
| Live progress | ✅ | ✅ |
| Cancel | 🛑 reaction | Inline button |
| Channel-per-engine | ✅ | ✅ |
| Config hot reload | ✅ | ✅ |
| Topics / forums | — | ✅ |
| Voice transcription | — | ✅ |
| File transfer | — | ✅ |
| Forward coalescing | — | ✅ |
| Media groups | — | ✅ |
| Trigger mode | — | ✅ |
| Command menu | — | ✅ |
| Chat preferences | — | ✅ |

### Plugins

Add engines, transports, or commands via entry-point plugins.

[`docs/how-to/write-a-plugin.md`](how-to/write-a-plugin.md) / [`docs/reference/plugin-api.md`](reference/plugin-api.md)

### Development

```sh
uv sync --dev
just check                              # format + lint + typecheck + tests
uv run pytest --no-cov -k "test_name"   # single test
```

### License

MIT — [LICENSE](../LICENSE)
