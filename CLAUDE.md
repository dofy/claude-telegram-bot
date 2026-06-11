# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run the bot
uv run bot.py

# Reload config without restart (via Telegram)
/reload   # send this as the owner in Telegram

# launchd (macOS)
launchctl load ~/Library/LaunchAgents/xyz.phpz.claude-telegram-bot.plist
launchctl unload ~/Library/LaunchAgents/xyz.phpz.claude-telegram-bot.plist
# Note: use unload/load, not stop/start — KeepAlive will restart a stopped process
```

No test suite is configured; there is no lint step in pyproject.toml.

## Architecture

### Request flow

`bot.py` → `app.run()` → `create_app()` in `app.py`

Handler registration order in `create_app()` is significant:
1. `commands.register(app)` — slash commands
2. `plugins.load_all(app)` — plugin handlers
3. `message.register(app)` — private text/media (catch-all)
4. `group.register(app)` — group mentions and `/ask`

Inbound messages hit `handlers/message.py` or `handlers/group.py`, which call `_handle_message()`. That function uses `invoke_stream()` to spawn the `claude` CLI subprocess with `--output-format stream-json` and streams tokens into a live-edited Telegram message. When the stream ends, the placeholder is deleted and the full reply is sent via `send_reply()` (handles chunking and file detection). For contexts where streaming isn't suitable (inline queries), `invoke()` is still available as a non-streaming alternative. Both share `_build_cmd()` for CLI assembly. Markdown → HTML conversion is done by `formatter.py`.

### Config layers

Two-layer config — merged at startup, deeper wins:
- `_DEFAULTS` dict in `config.py` — baseline values
- `config.json` — user overrides (deep-merged on top)
- `.env` — secrets only (`BOT_TOKEN`, `ANTHROPIC_*`, `ADMIN_TOKEN`)

`cfg` is a module-level singleton (`config.py`). Call `cfg.load()` to hot-reload; `/reload` command triggers this.

Key config sections:
- `claude.model` — global default model
- `claude.inline_model` — model used for inline queries (default `claude-haiku-4-5`, fast to stay within Telegram's 10 s timeout)
- `chat_models` — per-chat model overrides set via `/model` command, keyed by `chat_id` string
- `system_prompts` — per-chat system prompts, same structure

`cfg.get_chat_model(chat_id)` returns the per-chat override or falls back to `claude.model`. Use `cfg.set_chat_model()` / `cfg.set_system_prompt()` to persist per-chat settings.

### Plugin system

All plugins are always registered at startup. Enable/disable is a **runtime toggle** — no restart needed.

`Plugin.register()` must use `self.command(...)` (returns `GuardedCommandHandler`) instead of raw `CommandHandler`. `GuardedCommandHandler.check_update()` returns `None` when `is_enabled()` is false, letting the update fall through to the message handler (which routes it to Claude instead of the plugin command).

To add a plugin:
1. Create a package in `claude_bot/plugins/my_plugin/`
2. Subclass `Plugin` from `claude_bot.plugins.base`
3. Expose a module-level `plugin = MyPlugin()` instance
4. `plugins/__init__.py` auto-discovers and loads all `plugin` instances

Plugins that add admin UI implement `get_admin_tabs()` returning `[(slug, label, icon, builder_fn)]`. The builder function receives a NiceGUI container.

The `inline` plugin uses `InlineQueryHandler` (not `GuardedCommandHandler`) so it must check `plugin.is_enabled()` manually inside the handler.

### Session persistence

Sessions are stored in `/tmp/claude-bot-session-{chat_id}` (cleared on reboot) by `session.py`. The Claude CLI `--resume <session_id>` flag continues a conversation. Session IDs come from the `"result"` type line in the stream-json output.

Inline queries use an ephemeral `chat_id` of `-(user_id)` so they never collide with real DM sessions.

### UI theming

All NiceGUI admin panel colors live in `claude_bot/plugins/theme.py`. Edit that single file to restyle the entire admin panel.
