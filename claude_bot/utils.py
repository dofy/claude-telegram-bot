"""Shared utilities used by core modules and plugins."""

from telegram import Update
from telegram.ext import ContextTypes

from .acl import is_owner

_REJECT = "🙀 (｀Д´) nope nope nope!!"


def owner_only(func):
    """Decorator: reject non-owner callers."""
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.effective_chat:
            return
        if not is_owner(update.effective_chat.id):
            await update.message.reply_text(_REJECT)
            return
        return await func(update, ctx)
    return wrapper
