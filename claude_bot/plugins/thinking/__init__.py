"""Thinking messages plugin — random status messages while Claude processes."""

import random

from telegram.ext import Application

from ..base import Plugin
from ...config import cfg


def get_random_message() -> str | None:
    """Return a random enabled thinking message, or None if plugin is disabled."""
    if not plugin.is_enabled():
        return None
    msgs = cfg.active_thinking_messages
    return random.choice(msgs) if msgs else None


class ThinkingPlugin(Plugin):
    name = "thinking"
    display_name = "Thinking Messages"
    description = "Show random status messages while Claude is processing"

    def register(self, app: Application, config: dict) -> None:
        pass

    def get_admin_tabs(self) -> list[tuple[str, str, str, callable]]:
        from .panel import build_thinking_panel
        return [("thinking", "Thinking", "chat", build_thinking_panel)]


plugin = ThinkingPlugin()
