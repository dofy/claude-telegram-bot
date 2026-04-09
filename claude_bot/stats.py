"""Lightweight usage statistics with daily breakdown."""

import json
import time
from datetime import date
from pathlib import Path

from .config import BASE_DIR

_STATS_DIR = BASE_DIR / "logs"
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
        self._data["total_messages"] += 1
        self._today()["messages"] += 1
        self._save()

    def record_claude_call(self, elapsed: float):
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
