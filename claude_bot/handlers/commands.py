"""Bot command handlers."""

import datetime
import logging
import os
import re
import socket
import subprocess
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from ..acl import is_allowed_group, is_owner
from ..claude import get_bin
from ..config import BASE_DIR, cfg
from .. import session
from ..stats import stats

log = logging.getLogger("claude_bot.handlers.commands")

_REJECT = "🙀 (｀Д´) nope nope nope!!"


def _owner_only(func):
    """Decorator: reject non-owner callers."""
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.effective_chat:
            return
        if not is_owner(update.effective_chat.id):
            await update.message.reply_text(_REJECT)
            return
        return await func(update, ctx)
    return wrapper


# ── Basic commands ────────────────────────────────────────────────────────────

@_owner_only
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    await update.message.reply_text(
        "ฅ^•ﻌ•^ฅ nyaa~ hewo!!\n\n"
        "just throw tasks at me, i gotchu (๑•̀ㅂ•́)و✧\n\n"
        "<b>Chat</b>\n"
        "• /reset — poof! fresh start ✧\n"
        "• /prompt — set/view system prompt\n\n"
        "<b>Info</b>\n"
        "• /status — check if im alive lol\n"
        "• /sysinfo — system info\n"
        "• /usage — usage statistics\n"
        "• /sessions — active sessions\n\n"
        "<b>Admin</b>\n"
        "• /config — config summary\n"
        "• /admin — admin panel link\n"
        "• /reload — reload config\n"
        "• /logs — recent log lines\n"
        "• /remind — set a reminder\n"
        "• /stop — zzz time for kitty",
        parse_mode="HTML",
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, ctx)


@_owner_only
async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hostname = socket.gethostname()
    await update.message.reply_text(
        f"ᕙ(`▿´)ᕗ pawsitively operational!!\n"
        f"🖥 host: {hostname}\n"
        f"🕐 time: {now}"
    )


@_owner_only
async def cmd_sysinfo(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message

    def _run(cmd: list[str]) -> str:
        try:
            return subprocess.check_output(
                cmd, text=True, stderr=subprocess.DEVNULL
            ).strip().splitlines()[0]
        except Exception:
            return "unknown"

    claude_ver = _run([get_bin(), "--version"])
    node_ver = _run(["node", "--version"])
    os_ver = _run(["sw_vers", "-productVersion"])
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await update.message.reply_text(
        f"🖥 <b>System Info</b>\n\n"
        f"🤖 Claude: {claude_ver}\n"
        f"📦 Node: {node_ver}\n"
        f"🍎 macOS: {os_ver}\n"
        f"📂 工作目录: {Path.home()}\n"
        f"⌛️ 时间: {now}",
        parse_mode="HTML",
    )


@_owner_only
async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    session.clear(update.effective_chat.id)  # type: ignore[union-attr]
    await update.message.reply_text("✧ _(´ཀ`」 ∠)_ poof!! who r u again lol")


@_owner_only
async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    await update.message.reply_text("💤 (=`ω´=) zzZZZzz... bai bai~")
    os._exit(0)


# ── Admin management commands ────────────────────────────────────────────────

@_owner_only
async def cmd_reload(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    cfg.load()
    await update.message.reply_text("✅ Config reloaded!")


@_owner_only
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


@_owner_only
async def cmd_usage(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    s = stats.summary()
    await update.message.reply_text(
        f"📊 <b>Usage Statistics</b>\n\n"
        f"<b>Today</b>\n"
        f"  Messages: {s['today_messages']}\n"
        f"  Claude calls: {s['today_calls']}\n"
        f"  Avg response: {s['today_avg_time']:.1f}s\n"
        f"  Total time: {s['today_total_time']:.0f}s\n\n"
        f"<b>All Time</b>\n"
        f"  Messages: {s['total_messages']}\n"
        f"  Claude calls: {s['total_claude_calls']}",
        parse_mode="HTML",
    )


@_owner_only
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


@_owner_only
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


@_owner_only
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


# ── System prompt ─────────────────────────────────────────────────────────────

@_owner_only
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
    await update.message.reply_text(
        f"✅ System prompt set:\n\n{arg}",
    )


# ── Reminder ──────────────────────────────────────────────────────────────────

_TIME_RE = re.compile(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?")


def _parse_duration(s: str) -> int | None:
    """Parse a duration string like '5m', '1h30m', '90s' into seconds."""
    m = _TIME_RE.fullmatch(s.strip())
    if not m or not any(m.groups()):
        return None
    h, mi, sec = (int(g) if g else 0 for g in m.groups())
    total = h * 3600 + mi * 60 + sec
    return total if total > 0 else None


def _fmt_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{m}m{s}s" if s else f"{m}m"
    h, rem = divmod(seconds, 3600)
    m = rem // 60
    return f"{h}h{m}m" if m else f"{h}h"


@_owner_only
async def cmd_remind(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message and update.effective_chat
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()
    parts = text.split(None, 2)

    if len(parts) < 3:
        await update.message.reply_text(
            "⏰ <b>Usage:</b> <code>/remind &lt;time&gt; &lt;message&gt;</code>\n\n"
            "Examples:\n"
            "  <code>/remind 5m 喝水</code>\n"
            "  <code>/remind 1h30m 开会</code>\n"
            "  <code>/remind 30s 检查</code>",
            parse_mode="HTML",
        )
        return

    duration = _parse_duration(parts[1])
    if duration is None:
        await update.message.reply_text(
            "❌ Invalid time format. Use like: 5m, 1h, 30s, 1h30m"
        )
        return

    reminder_text = parts[2]

    async def _fire(context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⏰ <b>Reminder!</b>\n\n{reminder_text}",
            parse_mode="HTML",
        )

    if not ctx.job_queue:
        await update.message.reply_text("❌ Job queue not available")
        return

    ctx.job_queue.run_once(_fire, when=duration, chat_id=chat_id)
    await update.message.reply_text(
        f"✅ Reminder set! I'll ping you in {_fmt_duration(duration)}."
    )


# ── Registration ──────────────────────────────────────────────────────────────

def register(app: Application) -> None:
    commands = {
        "start": cmd_start,
        "help": cmd_help,
        "status": cmd_status,
        "sysinfo": cmd_sysinfo,
        "reset": cmd_reset,
        "stop": cmd_stop,
        "reload": cmd_reload,
        "sessions": cmd_sessions,
        "usage": cmd_usage,
        "logs": cmd_logs,
        "config": cmd_config,
        "admin": cmd_admin,
        "prompt": cmd_prompt,
        "remind": cmd_remind,
    }
    for name, handler in commands.items():
        app.add_handler(CommandHandler(name, handler))
