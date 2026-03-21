<div align="center">

# tunaPi

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/github/actions/workflow/status/hang-in/tunaPi/release.yml?label=tests)](https://github.com/hang-in/tunaPi/actions)
[![GitHub release](https://img.shields.io/github/v/release/hang-in/tunaPi?include_prereleases)](https://github.com/hang-in/tunaPi/releases)

チャットアプリから AI コーディングツールを動かすブリッジ

[한국어](../readme.md) | [English](README_EN.md) | [**日本語**](#日本語)

<!-- TODO: デモ GIF を追加 -->

</div>

---

## 日本語

### 背景

[takopi](https://github.com/banteg/takopi) を Telegram の代わりに Mattermost/Slack で使いたくてフォークしました。使っているうちに機能が増えました。

### どう動くのか

```
チャットのメッセージ → tunaPi → 自分の PC で AI を実行 → 結果をチャットに返す
```

チャット画面での実際の見た目:

```
自分:    ログインのバグを直して

tunaPi:  working · claude/opus4.6 · 0s · step 1
         ↳ Reading src/auth/login.py...

tunaPi:  working · claude/opus4.6 · 12s · step 4
         ↳ Writing fix...

tunaPi:  ✓ done · 23s · 3 files changed
         login.py のトークン期限切れ処理を修正しました。
```

### こんなときに便利です

- ターミナルを開かずチャットから AI に作業を頼みたいとき
- プロジェクトごとにチャットルームを分けて管理したいとき
- スマートフォンから作業 PC を操作したいとき
- 複数の AI に同じテーマで議論させたいとき

### 主な機能

- **マルチエージェント討論** — `!rt "テーマ"` で Claude・Gemini・Codex が順番に意見を出す
- **チャンネルごとのプロジェクト/エンジン割り当て** — チャンネルごとに異なるプロジェクトと AI を使用可能
- **リアルタイム進捗表示** — `working · claude/opus4.6 · 12s · step 4` 形式でチャットに表示
- **セッション再開** — 会話を中断しても後からコンテキストを引き継いで再開
- **モデル単位の指定** — `!model claude claude-opus-4-6` でエンジンだけでなくモデルも指定可能

### テスト状況

- テスト数: 1,023
- カバレッジ: 79%

### 対応チャット

Mattermost · Slack · Telegram

### 動かせる AI ツール

Claude Code · Codex · Gemini CLI · OpenCode · Pi

### インストール

```sh
uv tool install -U tunapi
```

ソースから:

```sh
git clone https://github.com/hang-in/tunaPi.git
cd tunaPi
uv tool install -e .
```

### 必要なもの

- Python 3.12+
- `uv`
- `claude` / `codex` / `gemini` / `opencode` / `pi` のどれか 1 つ以上

### 設定

`~/.tunapi/tunapi.toml`

```toml
transport = "slack"          # mattermost, telegram も可
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

### 起動

```sh
tunapi
```

設定確認:

```sh
tunapi doctor
```

### よく使うコマンド

| やりたいこと | 例 |
|---|---|
| AI に作業を頼む | `このバグを直して` |
| AI エンジンを切り替える | `!model codex` |
| モデルを指定する | `!model claude claude-opus-4-6` |
| 使えるモデルを確認 | `!models` |
| プロジェクトを紐づける | `!project set my-project` |
| マルチエージェント討論 | `!rt "アーキテクチャ検討" --rounds 2` |
| 新しい会話を始める | `!new` |
| 実行を止める | `!cancel` または 🛑 リアクション |
| 現在の状態を確認 | `!status` |
| 全コマンドを見る | `!help` |

### 注意

- 画像ファイルは送れますが、画像の中身は解析しません。
- 詳しい使い方: [docs/index.md](index.md)

### クレジット

[takopi](https://github.com/banteg/takopi) — このプロジェクトのフォーク元です。

### ライセンス

MIT — [LICENSE](../LICENSE)
