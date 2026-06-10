"""Private chat message handlers: text + media."""

import logging
import time

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from ..acl import is_allowed_group, is_owner
from ..claude import invoke_stream
from ..config import BASE_DIR
from ..formatter import md_to_html
from ..sender import send_reply, send_files_in_text
from ..plugins.stats import stats
from ..plugins.thinking import get_random_message

log = logging.getLogger("claude_bot.handlers.message")

INBOX_DIR = BASE_DIR / "inbox"

_REJECT = "🙀 (｀Д´) nope nope nope!!"

# Minimum interval between Telegram edits to stay within rate limits (~1/s).
_EDIT_INTERVAL = 1.1
# Accumulate at least this many characters before pushing an edit.
_EDIT_MIN_CHARS = 40


def _fmt_elapsed(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(int(seconds), 60)
    return f"{m}m{s}s"


async def _handle_message(
    chat_id: int, text: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE,
    model: str | None = None,
) -> None:
    stats.record_message()

    thinking = get_random_message()
    placeholder = thinking or "✦"

    # Send placeholder message that we'll edit in-place as tokens arrive.
    if update.message:
        status_msg = await update.message.reply_text(placeholder)
    else:
        status_msg = await ctx.bot.send_message(chat_id=chat_id, text=placeholder)

    await ctx.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    accumulated = ""
    last_edit = 0.0
    t0 = time.monotonic()

    try:
        async for chunk in invoke_stream(chat_id, text, model=model):
            accumulated += chunk
            now = time.monotonic()
            # Throttle edits: only push when enough text has arrived and
            # enough time has passed since the last edit.
            if (
                len(accumulated) - len(placeholder) >= _EDIT_MIN_CHARS
                and now - last_edit >= _EDIT_INTERVAL
            ):
                preview = accumulated.replace("<", "&lt;").replace(">", "&gt;")
                try:
                    await status_msg.edit_text(preview + " ✦")
                    last_edit = now
                except Exception:
                    pass  # rate-limit or unchanged text — skip silently
    except Exception as e:
        log.error("[%d] invoke_stream error: %s", chat_id, e)
        accumulated = f"(ಥ﹏ಥ) stream error: {e}"

    elapsed = time.monotonic() - t0
    stats.record_claude_call(elapsed)

    if not accumulated:
        accumulated = "(・ω・)? brain empty... no thoughts"

    # Convert full accumulated text to HTML and send via send_reply
    # (handles chunking + file detection). Delete the placeholder first.
    try:
        await status_msg.delete()
    except Exception:
        pass

    html = md_to_html(accumulated)
    await send_reply(ctx.bot, chat_id, html)

    if update.message:
        await update.message.reply_text(f"⏱ {_fmt_elapsed(elapsed)}")


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
