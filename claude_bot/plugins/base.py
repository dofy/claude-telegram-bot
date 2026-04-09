from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

from telegram.ext import Application, CommandHandler


class GuardedCommandHandler(CommandHandler):
    """CommandHandler that only matches when its owning plugin is enabled.

    When the plugin is disabled, check_update() returns None (no match),
    so the update falls through to subsequent handlers (e.g. the message
    handler that routes to Claude).
    """

    def __init__(self, command, callback, plugin: Plugin, **kwargs):
        super().__init__(command, callback, **kwargs)
        self._plugin = plugin

    def check_update(self, update):
        if not self._plugin.is_enabled():
            return None
        return super().check_update(update)


class Plugin(ABC):
    """Base class for bot plugins.

    Each plugin module/package should expose a module-level `plugin` instance.
    """

    name: str = ""
    display_name: str = ""
    description: str = ""

    @abstractmethod
    def register(self, app: Application, config: dict) -> None:
        """Called when the plugin is loaded. Register handlers here."""

    def on_app_ready(self, app: Application) -> None:
        """Called after all plugins are loaded and job_queue is available."""

    def unregister(self, app: Application) -> None:
        """Called when the plugin is unloaded. Override for cleanup."""

    def is_enabled(self) -> bool:
        from ..config import cfg
        return cfg.plugins_config.get(self.name, {}).get("enabled", True)

    def command(self, cmd: str, callback, **kwargs) -> GuardedCommandHandler:
        """Create a CommandHandler guarded by this plugin's enabled state."""
        return GuardedCommandHandler(cmd, callback, self, **kwargs)

    def get_admin_tabs(self) -> list[tuple[str, str, str, Callable]]:
        """Return admin UI tabs: [(slug, label, icon, builder_fn), ...]"""
        return []

    def get_commands(self) -> list[tuple[str, str]]:
        """Return bot commands for BotFather: [(command, description), ...]"""
        return []
