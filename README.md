# Claude Telegram Bot

A Telegram bot that forwards messages to [Claude Code](https://claude.ai/code) and sends back the response. Supports multi-turn conversations, media handling, group chats, and more.

## Features

- **Multi-turn conversations** — sessions persist per chat (in `/tmp`, cleared on reboot)
- **Typing indicator** — shows "typing…" while Claude is thinking
- **Image / file receiving** — photos and documents are downloaded to `inbox/` and passed to Claude as attachment paths
- **File auto-sending** — if Claude's response references a local file path, the bot sends it automatically
- **Group support** — responds in group chats when mentioned (`@botname`) or via `/ask`
- **Markdown → HTML** — converts Claude's Markdown output to Telegram-compatible HTML
- **Long message chunking** — splits responses at paragraph boundaries to stay within Telegram's 4096-char limit

## Prerequisites

- Python 3.11+
- `pip` / `pyenv`
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- Claude Code CLI installed (`claude` in PATH)
- An Anthropic API key (or OpenRouter key)

## Installation

```bash
cd ~/.claude/telegram-bot
pip install -r requirements.txt
```

## Configuration

```bash
cp .env.example .env
# Edit .env and fill in your BOT_TOKEN, ALLOWED_CHAT_ID, ANTHROPIC_API_KEY
```

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | Yes | Telegram bot token |
| `ALLOWED_CHAT_ID` | Yes | Your personal Telegram chat ID |
| `ALLOWED_GROUP_IDS` | No | Comma-separated group IDs |
| `ANTHROPIC_API_KEY` | Yes | API key |
| `ANTHROPIC_BASE_URL` | No | Custom endpoint (e.g. OpenRouter) |
| `CONTEXT_LENGTH` | No | Conversation rounds to keep (default: 3) |

To find your chat ID, message [@userinfobot](https://t.me/userinfobot).

## Running

### Direct

```bash
python3 bot.py
```

### With launchd (macOS auto-start)

```bash
cp com.seven.claude-telegram-bot.plist.example ~/Library/LaunchAgents/com.seven.claude-telegram-bot.plist
# Edit the plist and update the paths to match your username
launchctl load ~/Library/LaunchAgents/com.seven.claude-telegram-bot.plist
```

Logs go to `/tmp/claude-telegram-bot.log` and `/tmp/claude-telegram-bot.err`.

To stop:

```bash
launchctl unload ~/Library/LaunchAgents/com.seven.claude-telegram-bot.plist
```

## Group Setup

1. Add the bot to a group.
2. Get the group's chat ID (e.g. via [@getidsbot](https://t.me/getidsbot)).
3. Add the group ID to `ALLOWED_GROUP_IDS` in `.env`.
4. In the group, either:
   - Mention the bot: `@yourbotname do something`
   - Use `/ask do something`

## Commands Reference

| Command | Description |
|---------|-------------|
| `/start` | Show welcome message |
| `/help` | Same as /start |
| `/status` | Check bot is alive (hostname + time) |
| `/sysinfo` | Show Claude version, Node, macOS info |
| `/reset` | Clear current conversation session |
| `/stop` | Shut down the bot process |
| `/ask <text>` | (Groups) Ask Claude a question |
