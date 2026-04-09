"""Plugin discovery and lifecycle management.

Design: ALL discovered plugins are always registered at startup.
Enable/disable is a runtime flag — checked by guard() on command handlers
and is_enabled() in business logic.  No restart needed to toggle plugins.
"""

import importlib
import logging
import pkgutil
from pathlib import Path

from telegram.ext import Application

from .base import Plugin
from ..config import cfg

log = logging.getLogger("claude_bot.plugins")

_plugins: dict[str, Plugin] = {}


def discover() -> dict[str, Plugin]:
    """Scan the plugins directory for Plugin subclasses."""
    plugins_dir = Path(__file__).parent
    found: dict[str, Plugin] = {}
    for info in pkgutil.iter_modules([str(plugins_dir)]):
        if info.name.startswith("_") or info.name == "base":
            continue
        try:
            mod = importlib.import_module(f".{info.name}", __package__)
            if hasattr(mod, "plugin") and isinstance(mod.plugin, Plugin):
                found[mod.plugin.name] = mod.plugin
        except Exception as e:
            log.warning("Failed to load plugin module %s: %s", info.name, e)
    return found


def load_all(app: Application) -> None:
    """Discover and register ALL plugins. Enable/disable is runtime-only."""
    global _plugins
    _plugins = discover()
    plugins_cfg = cfg.plugins_config

    for name, plugin in _plugins.items():
        pcfg = plugins_cfg.get(name, {})
        enabled = pcfg.get("enabled", True)
        try:
            plugin.register(app, pcfg)
            log.info("Plugin registered: %s (enabled=%s)", name, enabled)
        except Exception as e:
            log.error("Plugin %s failed to register: %s", name, e)

    for name, plugin in _plugins.items():
        try:
            plugin.on_app_ready(app)
        except Exception as e:
            log.error("Plugin %s on_app_ready failed: %s", name, e)


def get_loaded() -> dict[str, Plugin]:
    """Return all registered plugins (enabled or not)."""
    return _plugins.copy()
