from abc import ABC, abstractmethod

from telegram.ext import Application


class Plugin(ABC):
    """Base class for bot plugins.

    Each plugin module should expose a module-level `plugin` instance.
    """

    name: str = ""
    description: str = ""

    @abstractmethod
    def register(self, app: Application, config: dict) -> None:
        """Called when the plugin is loaded. Register handlers here."""

    def unregister(self, app: Application) -> None:
        """Called when the plugin is unloaded. Override for cleanup."""
