<div align="center">

# tunaPi

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/github/actions/workflow/status/hang-in/tunaPi/release.yml?label=tests)](https://github.com/hang-in/tunaPi/actions)
[![GitHub release](https://img.shields.io/github/v/release/hang-in/tunaPi?include_prereleases)](https://github.com/hang-in/tunaPi/releases)

A bridge that lets you run AI coding tools from your chat app

[한국어](../readme.md) | [**English**](#english) | [日本語](README_JP.md)

<!-- TODO: add demo GIF -->

</div>

---

## English

### Background

Forked from [takopi](https://github.com/banteg/takopi) to use it with Mattermost and Slack instead of Telegram. Features accumulated from there.

### How it works

```
chat message → tunaPi → runs AI on your machine → sends result back to chat
```

What it looks like in chat:

```
you:     fix the login bug

tunaPi:  working · claude/opus4.6 · 0s · step 1
         ↳ Reading src/auth/login.py...

tunaPi:  working · claude/opus4.6 · 12s · step 4
         ↳ Writing fix...

tunaPi:  ✓ done · 23s · 3 files changed
         Fixed token expiry handling in login.py.
```

### When is this useful?

- You want to trigger AI work from chat without switching to a terminal
- You want separate projects in separate chat rooms
- You want to control your work machine from your phone
- You want multiple AIs to debate a topic

### Features

- **Multi-agent roundtable** — `!rt "topic"` runs Claude, Gemini, and Codex in turn
- **Per-channel project and engine mapping** — each channel can use a different project and AI
- **Live progress display** — `working · claude/opus4.6 · 12s · step 4` in chat
- **Session resumption** — context is preserved between conversations
- **Model-level selection** — `!model claude claude-opus-4-6` sets the exact model, not just the engine

### Test status

- Tests: 1,023
- Coverage: 79%

### Works with

Mattermost · Slack · Telegram

### Runs these AI tools

Claude Code · Codex · Gemini CLI · OpenCode · Pi

### Install

```sh
uv tool install -U tunapi
```

From source:

```sh
git clone https://github.com/hang-in/tunaPi.git
cd tunaPi
uv tool install -e .
```

### Requirements

- Python 3.12+
- `uv`
- at least one of: `claude` / `codex` / `gemini` / `opencode` / `pi`

### Setup

`~/.tunapi/tunapi.toml`

```toml
transport = "slack"          # or mattermost, telegram
default_engine = "claude"

[transports.slack]
bot_token = "xoxb-..."
app_token = "xapp-..."
channel_id = "C0123456789"
```

```toml
# Mattermost
transport = "mattermost"
default_engine = "claude"

[transports.mattermost]
url = "https://mm.example.com"
token = "YOUR_TOKEN"
channel_id = "YOUR_CHANNEL_ID"
```

```toml
# Telegram
transport = "telegram"
default_engine = "claude"

[transports.telegram]
bot_token = "YOUR_BOT_TOKEN"
chat_id = 123456789
```

### Run

```sh
tunapi
```

Check your setup:

```sh
tunapi doctor
```

### Commands

| What you want | Example |
|---|---|
| ask for work | `fix this bug` |
| switch engine | `!model codex` |
| set model | `!model claude claude-opus-4-6` |
| list available models | `!models` |
| bind a project | `!project set my-project` |
| multi-agent roundtable | `!rt "architecture review" --rounds 2` |
| start fresh | `!new` |
| cancel a run | `!cancel` or 🛑 reaction |
| check status | `!status` |
| see all commands | `!help` |

### Note

- Image files can be transferred, but image content is not analyzed.
- Full docs: [docs/index.md](index.md)

### Credit

[takopi](https://github.com/banteg/takopi) — this project started as a fork.

### License

MIT — [LICENSE](../LICENSE)
