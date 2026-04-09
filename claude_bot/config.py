import json
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent.resolve()

load_dotenv(BASE_DIR / ".env")

_DEFAULT_THINKING = [
    "⏳ ꉂ ೭(˵¯̴͒ꇴ¯̴͒˵)౨ thinking noises...",
    "⚡ •̀.̫•́✧ ooh ooh on it!!",
    "🔥 (`∀´)Ψ lemme cook~",
    "🐾 ฅ(^ω^ฅ) purring intensifies...",
    "💭 ( •̀ᴗ•́ )و brb big brain time!!",
    "🌀 (°ロ°) !!! processing at max floof power",
    "✨ (ﾉ◕ヮ◕)ﾉ*:･ﾟ✧ manifesting ur answer rn",
    "🎲 ₍ᐢ•ﻌ•ᐢ₎ rolling the dice of intelligence...",
    "🍜 (づ｡◕‿‿◕｡)づ stirring the brain soup~",
    "🔮 (　˘ω˘ ) peering into the void for u",
    "🚀 ε=ε=ε=┌(;￣▽￣)┘ zooming thru knowledge base!!",
    "💡 (¬‿¬ ) ohhhh i have a GALAXY brain idea",
    "🐱 ฅ•ω•ฅ nyaa~ crunching the numbers",
    "🎯 (⌐■_■) target acquired. computing...",
    "🌊 〰️(oᴗo〰️) riding the wave of computation~",
]

_DEFAULTS: dict = {
    "log": {
        "dir": "./logs",
        "rotation": "daily",
        "keep_days": 30,
        "level": "INFO",
    },
    "acl": {
        "owner_chat_id": 0,
        "allowed_group_ids": [],
    },
    "thinking_messages": _DEFAULT_THINKING,
    "plugins": {
        "admin_api": {"enabled": True, "port": 8080},
    },
    "claude": {
        "dangerously_skip_permissions": True,
        "max_retries": 2,
        "session_ttl_hours": 24,
    },
    "inbox": {
        "max_age_hours": 72,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning a new dict."""
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


class Config:
    def __init__(self, path: Path | None = None):
        self._path = path or (BASE_DIR / "config.json")
        self._data: dict = {}
        self.load()

    def load(self) -> None:
        file_data: dict = {}
        if self._path.exists():
            with open(self._path) as f:
                file_data = json.load(f)
        self._data = _deep_merge(_DEFAULTS, file_data)
        # Migrate from .env on first run
        if not self._data["acl"]["owner_chat_id"]:
            env_id = os.environ.get("ALLOWED_CHAT_ID", "")
            if env_id:
                self._data["acl"]["owner_chat_id"] = int(env_id)
        if not self._data["acl"]["allowed_group_ids"]:
            for gid in os.environ.get("ALLOWED_GROUP_IDS", "").split(","):
                gid = gid.strip()
                if gid:
                    self._data["acl"]["allowed_group_ids"].append(int(gid))

    def save(self) -> None:
        with open(self._path, "w") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
            f.write("\n")

    @property
    def data(self) -> dict:
        return self._data

    def get(self, *keys, default=None):
        d = self._data
        for k in keys:
            if isinstance(d, dict) and k in d:
                d = d[k]
            else:
                return default
        return d

    def set_value(self, keys: list[str], value) -> None:
        d = self._data
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value
        self.save()

    # ── Typed accessors ──

    @property
    def bot_token(self) -> str:
        return os.environ["BOT_TOKEN"]

    @property
    def owner_chat_id(self) -> int:
        return self.get("acl", "owner_chat_id", default=0)

    @property
    def allowed_group_ids(self) -> set[int]:
        return set(self.get("acl", "allowed_group_ids", default=[]))

    @property
    def thinking_messages(self) -> list[str]:
        return self.get("thinking_messages", default=[])

    @property
    def log_dir(self) -> str:
        return self.get("log", "dir", default="./logs")

    @property
    def log_rotation(self) -> str:
        return self.get("log", "rotation", default="daily")

    @property
    def log_keep_days(self) -> int:
        return self.get("log", "keep_days", default=30)

    @property
    def log_level(self) -> str:
        return self.get("log", "level", default="INFO")

    @property
    def admin_token(self) -> str:
        return os.environ.get("ADMIN_TOKEN", "")

    @property
    def claude_skip_permissions(self) -> bool:
        return self.get("claude", "dangerously_skip_permissions", default=True)

    @property
    def claude_max_retries(self) -> int:
        return self.get("claude", "max_retries", default=2)

    @property
    def session_ttl_hours(self) -> int:
        return self.get("claude", "session_ttl_hours", default=24)

    @property
    def inbox_max_age_hours(self) -> int:
        return self.get("inbox", "max_age_hours", default=72)

    @property
    def plugins_config(self) -> dict:
        return self.get("plugins", default={})

    def claude_env(self) -> dict[str, str]:
        """Build minimal env dict for Claude CLI subprocess."""
        env = {
            "HOME": os.environ["HOME"],
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        }
        for k, v in os.environ.items():
            if k.startswith("ANTHROPIC_") or k.startswith("OPENROUTER_"):
                env[k] = v
        return env


cfg = Config()
