"""Bot command handlers: /start, /help, /status, /sysinfo, /reset, /stop."""

import datetime
import logging
import os
import socket
import subprocess
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from ..acl import is_allowed_group, is_owner
from ..claude import get_bin
from .. import session

log = logging.getLogger("claude_bot.handlers.commands")

_REJECT = "🙀 (｀Д´) nope nope nope!!"


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    if not is_owner(update.effective_chat.id):
        await update.message.reply_text(_REJECT)
        return
    await update.message.reply_text(
        "ฅ^•ﻌ•^ฅ nyaa~ hewo!!\n\n"
        "just throw tasks at me, i gotchu (๑•̀ㅂ•́)و✧\n"
        "• /reset — poof! fresh start ✧\n"
        "• /status — check if im alive lol\n"
        "• /sysinfo — system info\n"
        "• /stop — zzz time for kitty"
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, ctx)


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    chat_id = update.effective_chat.id
    if not is_owner(chat_id) and not is_allowed_group(chat_id):
        await update.message.reply_text(_REJECT)
        return
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hostname = socket.gethostname()
    await update.message.reply_text(
        f"ᕙ(`▿´)ᕗ pawsitively operational!!\n"
        f"🖥 host: {hostname}\n"
        f"🕐 time: {now}"
    )


async def cmd_sysinfo(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    if not is_owner(update.effective_chat.id):
        await update.message.reply_text(_REJECT)
        return

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


async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    if not is_owner(update.effective_chat.id):
        await update.message.reply_text(_REJECT)
        return
    session.clear(update.effective_chat.id)
    await update.message.reply_text("✧ _(´ཀ`」 ∠)_ poof!! who r u again lol")


async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    if not is_owner(update.effective_chat.id):
        await update.message.reply_text(_REJECT)
        return
    await update.message.reply_text("💤 (=`ω´=) zzZZZzz... bai bai~")
    os._exit(0)


def register(app: Application) -> None:
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("sysinfo", cmd_sysinfo))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("stop", cmd_stop))
