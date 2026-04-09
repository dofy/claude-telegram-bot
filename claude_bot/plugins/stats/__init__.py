"""Stats plugin — lightweight usage statistics with daily breakdown."""

import json
import logging
from datetime import date
from pathlib import Path

from telegram import Update
from telegram.ext import Application, ContextTypes

from ..base import Plugin
from ...config import BASE_DIR
from ...utils import owner_only

log = logging.getLogger("claude_bot.plugins.stats")

_STATS_DIR = BASE_DIR / "data"
_STATS_PATH = _STATS_DIR / "stats.json"


class Stats:
    def __init__(self):
        self._data: dict = {
            "total_messages": 0,
            "total_claude_calls": 0,
            "daily": {},
        }
        self._load()

    def _load(self):
        if _STATS_PATH.exists():
            try:
                self._data = json.loads(_STATS_PATH.read_text())
            except (json.JSONDecodeError, OSError):
                pass

    def _save(self):
        try:
            _STATS_DIR.mkdir(parents=True, exist_ok=True)
            _STATS_PATH.write_text(json.dumps(self._data, indent=2))
        except OSError:
            pass

    def _today(self) -> dict:
        key = date.today().isoformat()
        return self._data["daily"].setdefault(
            key, {"messages": 0, "claude_calls": 0, "total_time": 0.0}
        )

    def record_message(self):
        if not plugin.is_enabled():
            return
        self._data["total_messages"] += 1
        self._today()["messages"] += 1
        self._save()

    def record_claude_call(self, elapsed: float):
        if not plugin.is_enabled():
            return
        self._data["total_claude_calls"] += 1
        day = self._today()
        day["claude_calls"] += 1
        day["total_time"] += elapsed
        self._save()

    def summary(self) -> dict:
        day = self._today()
        calls = day.get("claude_calls", 0)
        total_time = day.get("total_time", 0.0)
        return {
            "total_messages": self._data.get("total_messages", 0),
            "total_claude_calls": self._data.get("total_claude_calls", 0),
            "today_messages": day.get("messages", 0),
            "today_calls": calls,
            "today_avg_time": total_time / calls if calls else 0.0,
            "today_total_time": total_time,
        }


stats = Stats()


# ── Telegram command ──────────────────────────────────────────────────────────

@owner_only
async def cmd_usage(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    s = stats.summary()
    await update.message.reply_text(
        f"📊 <b>Usage Statistics</b>\n\n"
        f"<b>Today</b>\n"
        f"  Messages: {s['today_messages']}\n"
        f"  Claude calls: {s['today_calls']}\n"
        f"  Avg response: {s['today_avg_time']:.1f}s\n"
        f"  Total time: {s['today_total_time']:.0f}s\n\n"
        f"<b>All Time</b>\n"
        f"  Messages: {s['total_messages']}\n"
        f"  Claude calls: {s['total_claude_calls']}",
        parse_mode="HTML",
    )


# ── Plugin class ──────────────────────────────────────────────────────────────

class StatsPlugin(Plugin):
    name = "stats"
    display_name = "Usage Statistics"
    description = "Track message counts, Claude call stats, and response times"

    def register(self, app: Application, config: dict) -> None:
        app.add_handler(self.command("usage", cmd_usage))

    def get_commands(self) -> list[tuple[str, str]]:
        return [("usage", "Usage statistics")]


plugin = StatsPlugin()
