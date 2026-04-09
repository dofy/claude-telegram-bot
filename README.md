# Claude Telegram Bot

[中文文档](README_CN.md)

A Telegram bot that forwards messages to [Claude Code](https://claude.ai/code) and sends back the response. Supports multi-turn conversations, media handling, group chats, plugin system, and a web admin panel.

## Features

- **Multi-turn conversations** — sessions persist per chat (in `/tmp`, cleared on reboot)
- **Typing indicator** — shows "typing…" while Claude is thinking
- **Image / file receiving** — photos and documents are downloaded and passed to Claude
- **File auto-sending** — if Claude's response references a local file path, the bot sends it
- **Group support** — responds in group chats when mentioned (`@botname`) or via `/ask`
- **Markdown → HTML** — converts Claude's Markdown output to Telegram-compatible HTML
- **Plugin system** — extend or disable features via config
- **Admin web panel** — NiceGUI-based UI with token auth and rate limiting
- **Auto-retry** — Claude CLI failures retry with exponential backoff
- **Session TTL** — conversations auto-expire after configurable idle time
- **Inbox cleanup** — downloaded media files auto-deleted after configurable age
- **Log rotation** — daily/weekly log files with configurable retention

## Prerequisites

- Python 3.14+ / [uv](https://docs.astral.sh/uv/)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- Claude Code CLI installed (`claude` in PATH)
- An Anthropic API key (or OpenRouter key)

## Installation

```bash
git clone https://github.com/dofy/claude-telegram-bot.git
cd claude-telegram-bot
uv sync
```

## Configuration

The bot uses two config layers:

| File          | Purpose                                                   |
| ------------- | --------------------------------------------------------- |
| `.env`        | Secrets only (bot token, API keys)                        |
| `config.json` | Dynamic config (ACL, thinking messages, plugins, logging) |

```bash
cp .env.example .env
cp config.json.example config.json
# Edit .env with your BOT_TOKEN and API credentials
# Edit config.json to set your owner_chat_id
```

### `.env` variables

| Variable               | Required | Description                               |
| ---------------------- | -------- | ----------------------------------------- |
| `BOT_TOKEN`            | Yes      | Telegram bot token                        |
| `ANTHROPIC_API_KEY`    | \*       | Direct Anthropic access                   |
| `ANTHROPIC_AUTH_TOKEN` | \*       | OpenRouter / proxy token                  |
| `ANTHROPIC_BASE_URL`   | No       | Custom API endpoint                       |
| `ADMIN_TOKEN`          | No       | Admin panel login token (empty = no auth) |

\* One of `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` is required.

### `config.json` structure

| Section             | Key fields                                                         |
| ------------------- | ------------------------------------------------------------------ |
| `acl`               | `owner_chat_id`, `allowed_group_ids`                               |
| `log`               | `dir`, `rotation` (daily/weekly), `keep_days`, `level`             |
| `thinking_messages` | Array of `{text, enabled}` objects, individually toggleable        |
| `plugins`           | Plugin enable/disable and per-plugin config                        |
| `claude`            | `dangerously_skip_permissions`, `max_retries`, `session_ttl_hours` |
| `inbox`             | `max_age_hours` (auto-delete downloaded media, default 72)         |

> You can also manage config via the **Admin Web Panel** (default `http://127.0.0.1:8080`, port configurable in `plugins.admin_api.port`).

## Running

### Direct

```bash
uv run bot.py
```

### With launchd (macOS auto-start)

```bash
cp xyz.phpz.claude-telegram-bot.plist.example ~/Library/LaunchAgents/xyz.phpz.claude-telegram-bot.plist
# Edit the plist and update paths
launchctl load ~/Library/LaunchAgents/xyz.phpz.claude-telegram-bot.plist
```

To stop (fully unload, prevents KeepAlive auto-restart):

```bash
launchctl unload ~/Library/LaunchAgents/xyz.phpz.claude-telegram-bot.plist
```

> **Note:** `launchctl stop` only kills the process — KeepAlive will immediately restart it. Use `unload` to truly stop, `load` to start again.

## Project Structure

```
├── bot.py                  # Entry point (3 lines)
├── config.json             # Dynamic config (gitignored)
├── .env                    # Secrets (gitignored)
├── claude_bot/
│   ├── app.py              # Application assembly
│   ├── config.py           # Config loading / saving
│   ├── log.py              # Logging with file rotation
│   ├── claude.py           # Claude CLI invocation
│   ├── session.py          # Conversation session mgmt
│   ├── formatter.py        # Markdown → HTML
│   ├── sender.py           # Message chunking & sending
│   ├── acl.py              # Access control
│   ├── cleanup.py          # Inbox media cleanup
│   ├── handlers/
│   │   ├── commands.py     # /start, /status, /reset...
│   │   ├── message.py      # Private text + media
│   │   └── group.py        # Group chat
│   └── plugins/
│       ├── base.py         # Plugin base class
│       └── admin_api.py    # Built-in admin web panel
```

## Plugin System

Plugins live in `claude_bot/plugins/`. Each plugin is a Python module exposing a `plugin` instance:

```python
from claude_bot.plugins.base import Plugin
from telegram.ext import Application

class MyPlugin(Plugin):
    name = "my_plugin"
    description = "Does something cool"

    def register(self, app: Application, config: dict) -> None:
        # Register handlers, start background tasks, etc.
        pass

plugin = MyPlugin()
```

Enable/disable in `config.json`:

```json
{
  "plugins": {
    "my_plugin": { "enabled": true }
  }
}
```

## Commands Reference

| Command       | Description                           |
| ------------- | ------------------------------------- |
| `/start`      | Show welcome message                  |
| `/help`       | Same as /start                        |
| `/status`     | Check bot is alive (hostname + time)  |
| `/sysinfo`    | Show Claude version, Node, macOS info |
| `/reset`      | Clear current conversation session    |
| `/stop`       | Shut down the bot process             |
| `/ask <text>` | (Groups) Ask Claude a question        |

## Group Setup

1. Add the bot to a group.
2. Get the group's chat ID (e.g. via [@getidsbot](https://t.me/getidsbot)).
3. Add the group ID to `config.json` → `acl.allowed_group_ids`.
4. In the group, either:
   - Mention the bot: `@yourbotname do something`
   - Use `/ask do something`
