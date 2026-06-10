"""Inline mode plugin — answer @botname queries in any chat."""

import asyncio
import logging
import time

from telegram import InlineQueryResultArticle, InputTextMessageContent, Update
from telegram.ext import Application, ContextTypes, InlineQueryHandler

from ..base import Plugin
from ...config import cfg
from ...claude import invoke
from ...formatter import md_to_html

log = logging.getLogger("claude_bot.plugins.inline")

# Telegram's hard deadline for answerInlineQuery is 10 s.
# We leave a 1-second margin for network overhead.
_INLINE_TIMEOUT = 9.0


class InlinePlugin(Plugin):
    name = "inline"
    display_name = "Inline Mode"
    description = "Answer @botname queries from any Telegram chat"

    def register(self, app: Application, config: dict) -> None:
        app.add_handler(InlineQueryHandler(inline_handler))

    def get_commands(self) -> list[tuple[str, str]]:
        return []


async def inline_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.inline_query
    if not query:
        return

    if not plugin.is_enabled():
        return

    text = (query.query or "").strip()
    if not text:
        # Show a hint when the user hasn't typed anything yet.
        await query.answer(
            results=[
                InlineQueryResultArticle(
                    id="hint",
                    title="Ask Claude anything…",
                    description="Type your question after @botname",
                    input_message_content=InputTextMessageContent("…"),
                )
            ],
            cache_time=0,
        )
        return

    # Use a dedicated fast/cheap model for inline to stay within the 10 s limit.
    model = cfg.inline_model
    # Inline queries have no persistent session — use a throw-away chat_id
    # derived from the Telegram user id so each user gets an isolated context.
    ephemeral_chat_id = -(query.from_user.id)  # negative to avoid real chat collisions

    log.info("[inline/%d] query: %s", query.from_user.id, text[:80])
    t0 = time.monotonic()

    try:
        html, elapsed = await asyncio.wait_for(
            invoke(ephemeral_chat_id, text, model=model),
            timeout=_INLINE_TIMEOUT,
        )
    except asyncio.TimeoutError:
        log.warning("[inline/%d] timed out after %.1fs", query.from_user.id, _INLINE_TIMEOUT)
        html = "⏳ Still thinking… try sending me a direct message for long queries."
        elapsed = _INLINE_TIMEOUT

    # Strip HTML tags for the description preview (plain text only).
    import re
    plain = re.sub(r"<[^>]+>", "", html).strip()
    preview = plain[:120] + ("…" if len(plain) > 120 else "")

    await query.answer(
        results=[
            InlineQueryResultArticle(
                id="reply",
                title=f"Claude ({model})",
                description=preview or "(empty response)",
                input_message_content=InputTextMessageContent(
                    html or "(・ω・)? nothing came out??",
                    parse_mode="HTML",
                ),
            )
        ],
        cache_time=0,  # Don't cache — each query is unique.
    )
    log.info("[inline/%d] answered in %.1fs", query.from_user.id, elapsed)


plugin = InlinePlugin()
