"""Group chat message handler."""

import logging

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from ..acl import is_allowed_group
from .message import _handle_message

log = logging.getLogger("claude_bot.handlers.group")

_bot_username: str = ""


async def group_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not is_allowed_group(chat_id):
        return

    global _bot_username
    text = (update.message.text or "").strip()

    if not _bot_username:
        _bot_username = (await ctx.bot.get_me()).username
    mentioned = f"@{_bot_username}" in text
    starts_with_ask = text.startswith("/ask")

    if not mentioned and not starts_with_ask:
        return

    text = text.replace(f"@{_bot_username}", "").strip()
    if text.startswith("/ask"):
        text = text[4:].strip()

    if not text:
        return

    log.info("[%d] group message: %s", chat_id, text[:80])
    await _handle_message(chat_id, text, update, ctx)


def register(app: Application) -> None:
    app.add_handler(
        MessageHandler(filters.TEXT & filters.ChatType.GROUPS, group_handler)
    )
