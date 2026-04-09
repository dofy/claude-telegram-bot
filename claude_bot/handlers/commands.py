"""Core bot command handlers."""

import datetime
import logging
import os
import socket
import subprocess
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from ..claude import get_bin
from ..config import BASE_DIR
from .. import session
from ..utils import owner_only

log = logging.getLogger("claude_bot.handlers.commands")


@owner_only
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    from .. import plugins

    lines = [
        "ฅ^•ﻌ•^ฅ nyaa~ hewo!!\n",
        "just throw tasks at me, i gotchu (๑•̀ㅂ•́)و✧\n",
        "<b>Core</b>",
        "• /reset — poof! fresh start ✧",
        "• /status — check if im alive lol",
        "• /sysinfo — system info",
        "• /stop — zzz time for kitty",
    ]

    plugin_cmds = []
    for pname, p in plugins.get_loaded().items():
        if p.is_enabled():
            plugin_cmds.extend(p.get_commands())
    if plugin_cmds:
        lines.append("\n<b>Plugins</b>")
        for cmd, desc in plugin_cmds:
            lines.append(f"• /{cmd} — {desc}")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, ctx)


@owner_only
async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hostname = socket.gethostname()
    await update.message.reply_text(
        f"ᕙ(`▿´)ᕗ pawsitively operational!!\n"
        f"🖥 host: {hostname}\n"
        f"🕐 time: {now}"
    )


@owner_only
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


@owner_only
async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    session.clear(update.effective_chat.id)  # type: ignore[union-attr]
    await update.message.reply_text("✧ _(´ཀ`」 ∠)_ poof!! who r u again lol")


@owner_only
async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    await update.message.reply_text("💤 (=`ω´=) zzZZZzz... bai bai~")
    os._exit(0)


def register(app: Application) -> None:
    commands = {
        "start": cmd_start,
        "help": cmd_help,
        "status": cmd_status,
        "sysinfo": cmd_sysinfo,
        "reset": cmd_reset,
        "stop": cmd_stop,
    }
    for name, handler in commands.items():
        app.add_handler(CommandHandler(name, handler))
