<div align="center">

# tunapi

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/github/actions/workflow/status/hang-in/tunapi/release.yml?label=tests)](https://github.com/hang-in/tunapi/actions)
[![GitHub release](https://img.shields.io/github/v/release/hang-in/tunapi?include_prereleases)](https://github.com/hang-in/tunapi/releases)

コーディングエージェントCLI用 Mattermost・Telegramブリッジ

[한국어](../readme.md) | [English](README_EN.md) | [**日本語**](#日本語)

</div>

---

## 日本語

**Claude Code**、**Codex**、**Gemini CLI** などのコーディングエージェントを、MattermostチャンネルやTelegramチャットから実行できます。

[takopi](https://github.com/banteg/takopi)からフォーク。現在のフォークはMattermostに重点を置いていますが、upstreamのTelegramトランスポートも完全に保持されています。

### 主な機能

- **2つのトランスポート** — Mattermost（WebSocket、Bearer認証）+ Telegram（ロングポーリング、インラインキーボード）
- **マルチエンジン** — Claude、Codex、Gemini、OpenCode、Pi。チャンネルごとに異なるエンジンをマッピング
- **リアルタイム進捗表示** — ツール呼び出し、ファイル変更、経過時間をストリーミング
- **セッション再開** — resumeトークンで会話コンテキストを維持（`session_mode = "chat"`）
- **プロジェクト & ワークツリー** — チャンネルをリポジトリにバインド、ブランチ別git worktree
- **キャンセル** — Mattermost: 🛑リアクション / Telegram: インラインボタン
- **ファイル転送** — 添付ファイルの自動認識、エージェント作業ディレクトリに保存
- **音声文字起こし** — 音声メッセージをテキストに変換してエージェントに転送
- **トリガーモード** — @メンション検出によるボット呼び出し（グループチャンネルで便利）
- **チャット設定** — チャンネルごとのエンジン/トリガーモード保存（`/model`、`/trigger`）
- **スラッシュコマンド** — `/help`、`/model`、`/trigger`、`/status`、`/cancel`、`/file`、`/new`
- **プラグインシステム** — Python entry pointでエンジン、トランスポート、コマンドを追加

> **注意:** エージェントは画像を分析できません。画像ファイルは転送されますが、内容の分析はサポートされていません。

### 必要要件

- [uv](https://docs.astral.sh/uv/)（`curl -LsSf https://astral.sh/uv/install.sh | sh`）
- Python 3.14+（`uv python install 3.14`）
- エージェントCLIが最低1つPATHに必要: `claude`、`codex`、`gemini`、`opencode`、`pi`

### インストール

```sh
uv tool install -U tunapi
```

ソースから:

```sh
git clone https://github.com/hang-in/tunapi.git
cd tunapi
uv tool install -e .
```

### セットアップ

#### 1. トランスポートを選択

`~/.tunapi/tunapi.toml`:

```toml
transport = "mattermost"   # または "telegram"
```

#### 2a. Mattermost

**System Console** → **Integrations** → **Bot Accounts** → **Add Bot Account** でボットを作成し、**Access Token** をコピーします。

```toml
transport = "mattermost"
default_engine = "claude"

[transports.mattermost]
url = "https://mm.example.com"
token = "ボットアクセストークン"
channel_id = "デフォルトチャンネルID"
show_resume_line = false
session_mode = "chat"
```

`.env`ファイルでトークン管理:

```sh
MATTERMOST_TOKEN=ボットアクセストークン
```

#### 2b. Telegram

[@BotFather](https://t.me/BotFather)でボットを作成し、トークンをコピーします。

```toml
transport = "telegram"
default_engine = "claude"

[transports.telegram]
bot_token = "123456:ABC-DEF..."
chat_id = 123456789
```

Telegram専用機能: トピック、フォワード結合、メディアグループ

両方のトランスポート共通機能: 音声文字起こし、ファイル転送、トリガーモード（@メンション検出）、スラッシュコマンド、チャット設定の保存

#### 3. チャンネルごとのエンジンマッピング（オプション）

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

### 使い方

```sh
tunapi                                    # フォアグラウンド
nohup tunapi > /tmp/tunapi.log 2>&1 &    # バックグラウンド
tunapi --debug                            # デバッグモード
```

| アクション | 方法 |
|-----------|------|
| エンジン選択 | `/claude`、`/codex`、`/gemini` プレフィックス |
| プロジェクト登録 | `tunapi init my-project` |
| プロジェクト指定 | `/my-project バグを直して` |
| ワークツリー使用 | `/my-project @feat/branch 作業して` |
| 新しいセッション | `/new` |
| 実行キャンセル | 🛑リアクション（Mattermost）/ Cancelボタン（Telegram） |
| 設定確認 | `tunapi config list` |

### 対応エンジン

| エンジン | CLI | ステータス |
|---------|-----|-----------|
| Claude Code | `claude` | 内蔵 |
| Codex | `codex` | 内蔵 |
| Gemini CLI | `gemini` | 内蔵 |
| OpenCode | `opencode` | 内蔵 |
| Pi | `pi` | 内蔵 |

### トランスポート機能比較

| 機能 | Mattermost | Telegram |
|------|------------|----------|
| セッション再開 | ✅ | ✅ |
| リアルタイム進捗 | ✅ | ✅ |
| キャンセル | 🛑リアクション | インラインボタン |
| チャンネル別エンジン | ✅ | ✅ |
| Config ホットリロード | ✅ | ✅ |
| ファイル転送 | ✅ | ✅ |
| 音声文字起こし | ✅ | ✅ |
| トリガーモード（@メンション） | ✅ | ✅ |
| スラッシュコマンド | ✅ | ✅ |
| チャット設定保存 | ✅ | ✅ |
| トピック / フォーラム | — | ✅ |
| フォワード結合 | — | ✅ |
| メディアグループ | — | ✅ |

### プラグイン

entry-pointプラグインでエンジン、トランスポート、コマンドを追加できます。

[`docs/how-to/write-a-plugin.md`](how-to/write-a-plugin.md) / [`docs/reference/plugin-api.md`](reference/plugin-api.md)

### 開発

```sh
uv sync --dev
just check                              # format + lint + typecheck + tests
uv run pytest --no-cov -k "test_name"   # 単体テスト
```

### ライセンス

MIT — [LICENSE](../LICENSE)
