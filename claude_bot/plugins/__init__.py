"""Plugin discovery and lifecycle management."""

import importlib
import logging
import pkgutil
from pathlib import Path

from telegram.ext import Application

from .base import Plugin
from ..config import cfg

log = logging.getLogger("claude_bot.plugins")

_loaded: dict[str, Plugin] = {}


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
    """Discover and register all enabled plugins."""
    plugins_cfg = cfg.plugins_config
    for name, plugin in discover().items():
        pcfg = plugins_cfg.get(name, {})
        if not pcfg.get("enabled", True):
            log.info("Plugin %s is disabled, skipping", name)
            continue
        try:
            plugin.register(app, pcfg)
            _loaded[name] = plugin
            log.info("Plugin loaded: %s", name)
        except Exception as e:
            log.error("Plugin %s failed to register: %s", name, e)


def get_loaded() -> dict[str, Plugin]:
    return _loaded.copy()
