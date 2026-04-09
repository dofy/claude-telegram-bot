"""Private chat message handlers: text + media."""

import logging
import random

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from ..acl import is_allowed_group, is_owner
from ..claude import invoke
from ..config import BASE_DIR, cfg
from ..sender import send_reply

log = logging.getLogger("claude_bot.handlers.message")

INBOX_DIR = BASE_DIR / "inbox"

_REJECT = "🙀 (｀Д´) nope nope nope!!"


async def _handle_message(
    chat_id: int, text: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE
) -> None:
    msgs = cfg.active_thinking_messages
    if msgs and update.message:
        await update.message.reply_text(random.choice(msgs))
    await ctx.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    reply_html = await invoke(chat_id, text)
    await send_reply(ctx.bot, chat_id, reply_html)


async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    chat_id = update.effective_chat.id
    if not is_owner(chat_id):
        await update.message.reply_text(_REJECT)
        return
    text = (update.message.text or "").strip()
    if not text:
        return
    log.info("[%d] text: %s", chat_id, text[:80])
    await _handle_message(chat_id, text, update, ctx)


async def media_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    chat_id = update.effective_chat.id
    if not is_owner(chat_id) and not is_allowed_group(chat_id):
        await update.message.reply_text(_REJECT)
        return

    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    caption = (update.message.caption or "").strip()
    file_refs: list[str] = []

    if update.message.photo:
        photo = update.message.photo[-1]
        tg_file = await ctx.bot.get_file(photo.file_id)
        dest = INBOX_DIR / f"{photo.file_id}.jpg"
        await tg_file.download_to_drive(dest)
        file_refs.append(f"[附件: {dest}]")
        log.info("[%d] photo -> %s", chat_id, dest)
    elif update.message.document:
        doc = update.message.document
        tg_file = await ctx.bot.get_file(doc.file_id)
        dest = INBOX_DIR / (doc.file_name or f"{doc.file_id}.bin")
        await tg_file.download_to_drive(dest)
        file_refs.append(f"[附件: {dest}]")
        log.info("[%d] document -> %s", chat_id, dest)

    if not file_refs:
        return

    prefix = "\n".join(file_refs)
    full_text = f"{prefix}\n{caption}" if caption else prefix
    await _handle_message(chat_id, full_text, update, ctx)


def register(app: Application) -> None:
    app.add_handler(
        MessageHandler(filters.PHOTO | filters.Document.ALL, media_handler)
    )
    app.add_handler(
        MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, text_handler)
    )
