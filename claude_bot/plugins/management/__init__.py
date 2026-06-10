"""Management plugin — owner-only admin commands via Telegram."""

import logging
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from ..base import Plugin
from ...config import BASE_DIR, cfg
from ...claude import FALLBACK_MODELS, fetch_models
from ... import session
from ...utils import owner_only

log = logging.getLogger("claude_bot.plugins.management")


@owner_only
async def cmd_reload(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    cfg.load()
    await update.message.reply_text("✅ Config reloaded!")


@owner_only
async def cmd_sessions(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    active = session.list_active()
    if not active:
        await update.message.reply_text("📭 No active sessions")
        return
    lines = [f"📋 <b>Active Sessions</b> ({len(active)})\n"]
    for s in active:
        lines.append(
            f"• <code>{s['chat_id']}</code>  "
            f"idle {s['idle_min']}min  "
            f"<code>{s['session_id']}</code>"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


@owner_only
async def cmd_logs(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    args = (update.message.text or "").split()
    n = 20
    if len(args) > 1:
        try:
            n = min(int(args[1]), 50)
        except ValueError:
            pass

    log_path = Path(cfg.log_dir)
    if not log_path.is_absolute():
        log_path = BASE_DIR / log_path
    log_file = log_path / "bot.log"

    if not log_file.exists():
        await update.message.reply_text("📭 No log file found")
        return

    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    tail = lines[-n:]
    text = "\n".join(tail)
    if len(text) > 4000:
        text = text[-4000:]
    await update.message.reply_text(f"<pre>{text}</pre>", parse_mode="HTML")


@owner_only
async def cmd_config(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    admin_cfg = cfg.plugins_config.get("admin_api", {})
    port = admin_cfg.get("port", 8080)
    prompt = cfg.get_system_prompt(update.effective_chat.id)  # type: ignore[union-attr]
    await update.message.reply_text(
        f"⚙️ <b>Config Summary</b>\n\n"
        f"Owner: <code>{cfg.owner_chat_id}</code>\n"
        f"Groups: {len(cfg.allowed_group_ids)}\n"
        f"Session TTL: {cfg.session_ttl_hours}h\n"
        f"Max retries: {cfg.claude_max_retries}\n"
        f"Inbox cleanup: {cfg.inbox_max_age_hours}h\n"
        f"Log level: {cfg.log_level}\n"
        f"Admin port: {port}\n"
        f"System prompt: {prompt[:60] + '…' if len(prompt) > 60 else prompt or '(none)'}",
        parse_mode="HTML",
    )


@owner_only
async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    admin_cfg = cfg.plugins_config.get("admin_api", {})
    port = admin_cfg.get("port", 8080)
    token = cfg.admin_token
    lines = [f"🌐 <b>Admin Panel</b>\n", f"URL: http://127.0.0.1:{port}"]
    if token:
        lines.append(f"Token: <code>{token}</code>")
    else:
        lines.append("Auth: disabled")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


@owner_only
async def cmd_prompt(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message and update.effective_chat
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()
    arg = text[len("/prompt"):].strip() if text.startswith("/prompt") else ""

    if not arg:
        current = cfg.get_system_prompt(chat_id)
        if current:
            await update.message.reply_text(
                f"📝 <b>Current System Prompt</b>\n\n{current}\n\n"
                f"Use <code>/prompt clear</code> to remove.",
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text(
                "📝 No system prompt set.\n"
                "Use <code>/prompt &lt;text&gt;</code> to set one.",
                parse_mode="HTML",
            )
        return

    if arg.lower() == "clear":
        cfg.set_system_prompt(chat_id, "")
        await update.message.reply_text("✅ System prompt cleared!")
        return

    cfg.set_system_prompt(chat_id, arg)
    await update.message.reply_text(f"✅ System prompt set:\n\n{arg}")


@owner_only
async def cmd_model(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current model or present a selection keyboard."""
    assert update.message and update.effective_chat
    chat_id = update.effective_chat.id

    models, _ = fetch_models()
    # Always include current model even if not in the fetched list.
    current = cfg.get_chat_model(chat_id)
    if current not in models:
        models = [current] + models

    buttons = []
    for m in models:
        label = f"✓ {m}" if m == current else m
        buttons.append([InlineKeyboardButton(label, callback_data=f"model:{chat_id}:{m}")])
    buttons.append([InlineKeyboardButton("↩ Reset to global default", callback_data=f"model:{chat_id}:__reset__")])

    await update.message.reply_text(
        f"🤖 <b>Model</b>\nCurrent: <code>{current}</code>\n\nPick a model for this chat:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def _model_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard button presses for /model."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    parts = query.data.split(":", 2)
    if len(parts) != 3 or parts[0] != "model":
        return

    target_chat_id = int(parts[1])
    chosen = parts[2]

    if chosen == "__reset__":
        cfg.set_chat_model(target_chat_id, "")
        label = f"global default ({cfg.claude_model})"
    else:
        cfg.set_chat_model(target_chat_id, chosen)
        label = chosen

    await query.edit_message_text(f"✅ Model set to <code>{label}</code>", parse_mode="HTML")


# ── Plugin class ──────────────────────────────────────────────────────────────

class ManagementPlugin(Plugin):
    name = "management"
    display_name = "Management Commands"
    description = "Owner-only Telegram commands: /reload, /sessions, /logs, /config, /admin, /prompt"

    def register(self, app: Application, config: dict) -> None:
        for cmd, fn in {
            "reload": cmd_reload,
            "sessions": cmd_sessions,
            "logs": cmd_logs,
            "config": cmd_config,
            "admin": cmd_admin,
            "prompt": cmd_prompt,
            "model": cmd_model,
        }.items():
            app.add_handler(self.command(cmd, fn))
        # CallbackQueryHandler for model selection buttons (not a command).
        app.add_handler(CallbackQueryHandler(_model_callback, pattern=r"^model:"))

    def get_commands(self) -> list[tuple[str, str]]:
        return [
            ("reload", "Reload config"),
            ("sessions", "Active sessions"),
            ("logs", "Recent log lines"),
            ("config", "Config summary"),
            ("admin", "Admin panel link"),
            ("prompt", "Set/view system prompt"),
            ("model", "Set model for this chat"),
        ]


plugin = ManagementPlugin()
