# Telegram Bot Python Rewrite — Design Spec

**Date**: 2026-04-08  
**Status**: Approved  

---

## Overview

Rewrite `~/.claude/telegram-bot/bot.sh` in Python using `python-telegram-bot==20.x`.  
Adds four new features: typing indicator, image/file receiving, file auto-sending, group support.  
Existing `.env`, `.offset`, launchd plist structure remain compatible.

---

## File Structure

```
~/.claude/telegram-bot/
├── bot.py                  # Main program (replaces bot.sh)
├── requirements.txt        # python-telegram-bot>=20.0
├── .env                    # Unchanged (BOT_TOKEN, ALLOWED_CHAT_ID, etc.)
├── .env.example            # Template for GitHub (no real tokens)
├── .offset                 # No longer used (PTB manages offset internally)
├── inbox/                  # Downloaded photos and files
├── com.seven.claude-telegram-bot.plist.example  # launchd template
├── README.md
├── .gitignore
└── docs/
    └── superpowers/specs/
        └── 2026-04-08-telegram-bot-python-rewrite-design.md
```

---

## Architecture

**Framework**: `python-telegram-bot` v20.x (async, PTB Application pattern)  
**Runtime**: Python 3.11 (existing pyenv)  
**Entry point**: `python3 bot.py`

### Handler Registration

```
Application
├── CommandHandler: /start, /help, /status, /sysinfo, /reset, /stop
├── MessageHandler(filters.PHOTO | filters.Document.ALL) → media_handler
├── MessageHandler(filters.TEXT & filters.ChatType.PRIVATE) → text_handler
└── MessageHandler(filters.TEXT & filters.ChatType.GROUPS) → group_handler
```

### Access Control

- Private chats: `chat_id == ALLOWED_CHAT_ID` (existing behavior)
- Groups: `chat_id` in `ALLOWED_GROUP_IDS` env var (comma-separated list)
- Unauthorized: reply with rejection message

---

## Feature Designs

### 1. Typing Indicator

Send once before invoking Claude:
```python
await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
```
Simple, no background loop. Disappears after 5s for long responses — acceptable.

### 2. Image / File Receiving

**Photos**: Download highest-resolution version to `inbox/<file_id>.jpg`  
**Documents**: Download to `inbox/<filename>`  
**Injection**: Prepend `[附件: /path/to/file]\n` to user message text before passing to Claude.  
**Inbox path**: `~/.claude/telegram-bot/inbox/` (created on first use)

### 3. File Auto-Sending

After Claude responds, scan reply text with regex for absolute paths:
```
/(?:/Users/[^\s]+|/tmp/[^\s]+|/var/folders/[^\s]+)/\S+
```
For each matched path that exists on disk:
- Image extensions (`.jpg`, `.png`, `.gif`, `.webp`): `send_photo()`
- All others: `send_document()`
- Remove the path from the reply text to avoid redundant display

### 4. Group Support

Trigger conditions (both required):
1. Group chat_id is in `ALLOWED_GROUP_IDS`
2. Message contains `@botname` mention OR starts with `/ask`

Strip the `/ask` prefix and `@botname` mention before passing to Claude.  
Silent ignore for all other group messages.

---

## Claude Invocation

Unchanged from `bot.sh`:
```bash
env -i HOME=... PATH=... ANTHROPIC_API_KEY=... ANTHROPIC_BASE_URL=... \
  claude --print "<message>" \
  --output-format stream-json --verbose \
  --dangerously-skip-permissions \
  [--resume <session_id>]
```

Session persistence: `/tmp/claude-bot-session-<chat_id>` (in-memory, cleared on restart)

### Markdown → HTML

Reuse existing inline Python `md_to_html()` logic, ported to a Python function in `bot.py`.  
Long messages chunked at 4000 chars on paragraph boundaries (existing behavior).

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | Yes | Telegram bot token |
| `ALLOWED_CHAT_ID` | Yes | Numeric ID for private chat allowlist |
| `ALLOWED_GROUP_IDS` | No | Comma-separated group IDs (e.g. `-1001234567,−1009876543`) |
| `ANTHROPIC_API_KEY` | Yes | API key |
| `ANTHROPIC_BASE_URL` | No | OpenRouter or custom endpoint |
| `CONTEXT_LENGTH` | No | Conversation rounds to keep (default: 3) |

---

## launchd Update

Change in `com.seven.claude-telegram-bot.plist`:
```xml
<!-- Before -->
<string>/bin/bash</string>
<string>/Users/seven/.claude/telegram-bot/bot.sh</string>

<!-- After -->
<string>/usr/bin/python3</string>
<string>/Users/seven/.claude/telegram-bot/bot.py</string>
```

Or use pyenv python path if needed.

---

## GitHub Publishing

**Repo**: `github.com/dofy/claude-telegram-bot` (public, create if not exists)  
**Clone**: `~/Works/github/claude-telegram-bot`

### .gitignore
```
.env
inbox/
.offset
*.pyc
__pycache__/
```

### README sections
1. Features
2. Prerequisites (Python 3.11+, pip)
3. Installation
4. Configuration (.env setup)
5. Running (direct + launchd)
6. Group setup
7. Commands reference

---

## Out of Scope

- Persistent session across restarts (sessions in `/tmp`, cleared on reboot)
- Multi-user private chat support
- Inline keyboard / callback buttons
- Scheduled messages
