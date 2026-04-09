"""Scheduler plugin — persistent scheduled tasks: reminders and Claude queries."""

import json
import logging
import re
import time
import uuid
from datetime import datetime, time as dt_time
from pathlib import Path

from telegram import Update
from telegram.ext import Application, ContextTypes

from ..base import Plugin
from ...config import BASE_DIR, cfg
from ...utils import owner_only

log = logging.getLogger("claude_bot.plugins.scheduler")

_TASKS_PATH = BASE_DIR / "data" / "tasks.json"
_TIME_RE = re.compile(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?")


# ── Time parsing utilities ────────────────────────────────────────────────────

def parse_duration(s: str) -> int | None:
    m = _TIME_RE.fullmatch(s.strip())
    if not m or not any(m.groups()):
        return None
    h, mi, sec = (int(g) if g else 0 for g in m.groups())
    total = h * 3600 + mi * 60 + sec
    return total if total > 0 else None


def fmt_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{m}m{s}s" if s else f"{m}m"
    h, rem = divmod(seconds, 3600)
    m = rem // 60
    return f"{h}h{m}m" if m else f"{h}h"


def parse_time_str(s: str) -> str | None:
    """Validate 'HH:MM' format, return normalized string or None."""
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", s.strip())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if 0 <= h <= 23 and 0 <= mi <= 59:
        return f"{h:02d}:{mi:02d}"
    return None


def _short_id() -> str:
    return uuid.uuid4().hex[:6]


# ── Scheduler core ────────────────────────────────────────────────────────────

class Scheduler:
    def __init__(self):
        self._tasks: list[dict] = []
        self._job_queue = None
        self._load()

    def _load(self):
        if _TASKS_PATH.exists():
            try:
                self._tasks = json.loads(_TASKS_PATH.read_text())
            except (json.JSONDecodeError, OSError):
                self._tasks = []

    def _save(self):
        try:
            _TASKS_PATH.parent.mkdir(parents=True, exist_ok=True)
            _TASKS_PATH.write_text(
                json.dumps(self._tasks, indent=2, ensure_ascii=False)
            )
        except OSError:
            pass

    def init_job_queue(self, job_queue, *, restore: bool = True) -> None:
        self._job_queue = job_queue
        if not restore:
            log.info("Scheduler: job_queue ready (task restore skipped — plugin disabled)")
            return
        now = time.time()
        restored = 0
        for task in self._tasks:
            if not task.get("enabled", True):
                continue
            t = task["type"]
            if t == "once":
                remaining = task.get("fire_at", 0) - now
                if remaining <= 0:
                    task["enabled"] = False
                    continue
                self._register_once(task, remaining)
            elif t == "interval":
                self._register_interval(task)
            elif t == "daily":
                self._register_daily(task)
            restored += 1
        self._save()
        log.info("Scheduler initialized: %d/%d tasks restored", restored, len(self._tasks))

    def _make_callback(self, task_id: str, chat_id: int, message: str,
                        is_once: bool, mode: str = "remind"):
        async def _cb(context):
            if mode == "ask":
                from ...claude import invoke
                from ...sender import send_reply
                from ..stats import stats as _stats
                _stats.record_message()
                reply_html, elapsed = await invoke(chat_id, message)
                _stats.record_claude_call(elapsed)
                await send_reply(context.bot, chat_id, reply_html)
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⏰ <b>Reminder</b>\n\n{message}",
                    parse_mode="HTML",
                )
            if is_once:
                for t in self._tasks:
                    if t["id"] == task_id:
                        t["enabled"] = False
                        break
                self._save()
        return _cb

    def _register_once(self, task: dict, when_seconds: float):
        if not self._job_queue:
            return
        mode = task.get("mode", "remind")
        cb = self._make_callback(task["id"], task["chat_id"], task["message"], True, mode)
        self._job_queue.run_once(
            cb, when=when_seconds, name=task["id"], chat_id=task["chat_id"],
        )

    def _register_interval(self, task: dict):
        if not self._job_queue:
            return
        mode = task.get("mode", "remind")
        cb = self._make_callback(task["id"], task["chat_id"], task["message"], False, mode)
        self._job_queue.run_repeating(
            cb, interval=task["interval"], name=task["id"], chat_id=task["chat_id"],
        )

    def _register_daily(self, task: dict):
        if not self._job_queue:
            return
        h, m = map(int, task["time"].split(":"))
        mode = task.get("mode", "remind")
        cb = self._make_callback(task["id"], task["chat_id"], task["message"], False, mode)
        self._job_queue.run_daily(
            cb, time=dt_time(hour=h, minute=m), name=task["id"], chat_id=task["chat_id"],
        )

    def _cancel_job(self, task_id: str):
        if not self._job_queue:
            return
        for job in self._job_queue.get_jobs_by_name(task_id):
            job.schedule_removal()

    # ── CRUD ──

    def add_once(self, chat_id: int, message: str, seconds: int,
                 mode: str = "remind") -> dict:
        task = {
            "id": _short_id(), "chat_id": chat_id, "message": message,
            "type": "once", "mode": mode, "fire_at": time.time() + seconds,
            "schedule_str": fmt_duration(seconds), "enabled": True,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._tasks.append(task)
        self._save()
        self._register_once(task, seconds)
        return task

    def add_interval(self, chat_id: int, message: str, seconds: int,
                     mode: str = "remind") -> dict:
        task = {
            "id": _short_id(), "chat_id": chat_id, "message": message,
            "type": "interval", "mode": mode, "interval": seconds,
            "schedule_str": f"every {fmt_duration(seconds)}", "enabled": True,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._tasks.append(task)
        self._save()
        self._register_interval(task)
        return task

    def add_daily(self, chat_id: int, message: str, time_str: str,
                  mode: str = "remind") -> dict:
        task = {
            "id": _short_id(), "chat_id": chat_id, "message": message,
            "type": "daily", "mode": mode, "time": time_str,
            "schedule_str": f"daily {time_str}", "enabled": True,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._tasks.append(task)
        self._save()
        self._register_daily(task)
        return task

    def remove(self, task_id: str) -> bool:
        self._cancel_job(task_id)
        before = len(self._tasks)
        self._tasks = [t for t in self._tasks if t["id"] != task_id]
        if len(self._tasks) < before:
            self._save()
            return True
        return False

    def update(self, task_id: str, *, message: str | None = None,
               mode: str | None = None, task_type: str | None = None,
               schedule: str | None = None) -> bool:
        """Update a task's fields and re-register its job."""
        for task in self._tasks:
            if task["id"] != task_id:
                continue
            if message is not None:
                task["message"] = message
            if mode is not None:
                task["mode"] = mode

            new_type = task_type if task_type else task["type"]
            if task_type and task_type != task["type"]:
                task["type"] = task_type
                # schedule is required when switching type
                if not schedule:
                    return False

            if schedule is not None:
                if new_type == "interval":
                    dur = parse_duration(schedule)
                    if dur is None:
                        return False
                    task["interval"] = dur
                    task["schedule_str"] = f"every {fmt_duration(dur)}"
                    task.pop("time", None)
                    task.pop("fire_at", None)
                elif new_type == "daily":
                    ts = parse_time_str(schedule)
                    if ts is None:
                        return False
                    task["time"] = ts
                    task["schedule_str"] = f"daily {ts}"
                    task.pop("interval", None)
                    task.pop("fire_at", None)
                elif new_type == "once":
                    dur = parse_duration(schedule)
                    if dur is None:
                        return False
                    task["fire_at"] = time.time() + dur
                    task["schedule_str"] = fmt_duration(dur)
                    task.pop("interval", None)
                    task.pop("time", None)

            self._cancel_job(task_id)
            if task.get("enabled", True):
                if new_type == "once":
                    remaining = task.get("fire_at", 0) - time.time()
                    if remaining > 0:
                        self._register_once(task, remaining)
                    else:
                        task["enabled"] = False
                elif new_type == "interval":
                    self._register_interval(task)
                elif new_type == "daily":
                    self._register_daily(task)
            self._save()
            return True
        return False

    def toggle(self, task_id: str, enabled: bool) -> bool:
        for task in self._tasks:
            if task["id"] != task_id:
                continue
            if task["enabled"] == enabled:
                return True
            task["enabled"] = enabled
            if enabled:
                if task["type"] == "once":
                    remaining = task.get("fire_at", 0) - time.time()
                    if remaining > 0:
                        self._register_once(task, remaining)
                    else:
                        task["enabled"] = False
                elif task["type"] == "interval":
                    self._register_interval(task)
                elif task["type"] == "daily":
                    self._register_daily(task)
            else:
                self._cancel_job(task_id)
            self._save()
            return True
        return False

    def list_all(self, chat_id: int | None = None) -> list[dict]:
        if chat_id is not None:
            return [t for t in self._tasks if t["chat_id"] == chat_id]
        return list(self._tasks)

    def cleanup_done(self) -> int:
        before = len(self._tasks)
        self._tasks = [
            t for t in self._tasks
            if not (t["type"] == "once" and not t.get("enabled", True))
        ]
        removed = before - len(self._tasks)
        if removed:
            self._save()
        return removed


sched = Scheduler()


# ── Telegram command handlers ─────────────────────────────────────────────────

_REMIND_USAGE = (
    "⏰ <b>Usage:</b>\n\n"
    "<b>Reminders</b> (send text only):\n"
    "<code>/remind 5m 喝水</code>\n"
    "<code>/remind every 1h 站起来活动</code>\n"
    "<code>/remind daily 09:00 早安</code>\n\n"
    "<b>Tasks</b> (ask Claude):\n"
    "<code>/remind 5m ask 今日天气</code>\n"
    "<code>/remind every 2h ask 随机推荐一首歌</code>\n"
    "<code>/remind daily 08:00 ask 今日新闻摘要</code>\n\n"
    "<b>Manage:</b>\n"
    "<code>/remind list</code> · <code>/remind del &lt;id&gt;</code> · "
    "<code>/remind clean</code>"
)


def _extract_mode(text: str) -> tuple[str, str]:
    if text.lower().startswith("ask "):
        return "ask", text[4:].strip()
    return "remind", text


@owner_only
async def cmd_remind(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message and update.effective_chat
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()
    parts = text.split()

    if len(parts) < 2:
        await update.message.reply_text(_REMIND_USAGE, parse_mode="HTML")
        return

    sub = parts[1].lower()

    if sub == "list":
        await _show_tasks(update, chat_id)
        return

    if sub == "del" and len(parts) >= 3:
        tid = parts[2]
        if sched.remove(tid):
            await update.message.reply_text(f"✅ Task <code>{tid}</code> deleted.", parse_mode="HTML")
        else:
            await update.message.reply_text(f"❌ Task <code>{tid}</code> not found.", parse_mode="HTML")
        return

    if sub == "clean":
        removed = sched.cleanup_done()
        await update.message.reply_text(f"🧹 Removed {removed} completed task(s).")
        return

    if sub == "every":
        if len(parts) < 4:
            await update.message.reply_text(_REMIND_USAGE, parse_mode="HTML")
            return
        dur = parse_duration(parts[2])
        if dur is None:
            await update.message.reply_text("❌ Invalid interval. Use: 30m, 1h, 2h30m")
            return
        rest = text.split(None, 3)[3]
        mode, msg = _extract_mode(rest)
        task = sched.add_interval(chat_id, msg, dur, mode)
        label = "🤖 Task" if mode == "ask" else "✅ Reminder"
        await update.message.reply_text(
            f"{label} <code>{task['id']}</code> — every {fmt_duration(dur)}",
            parse_mode="HTML",
        )
        return

    if sub == "daily":
        if len(parts) < 4:
            await update.message.reply_text(_REMIND_USAGE, parse_mode="HTML")
            return
        time_str = parse_time_str(parts[2])
        if time_str is None:
            await update.message.reply_text("❌ Invalid time. Use HH:MM like 09:00")
            return
        rest = text.split(None, 3)[3]
        mode, msg = _extract_mode(rest)
        task = sched.add_daily(chat_id, msg, time_str, mode)
        label = "🤖 Task" if mode == "ask" else "✅ Reminder"
        await update.message.reply_text(
            f"{label} <code>{task['id']}</code> — daily at {time_str}",
            parse_mode="HTML",
        )
        return

    # one-shot
    if len(parts) < 3:
        await update.message.reply_text(_REMIND_USAGE, parse_mode="HTML")
        return

    dur = parse_duration(parts[1])
    if dur is None:
        await update.message.reply_text("❌ Invalid time format. Use: 5m, 1h, 30s, 1h30m")
        return

    rest = text.split(None, 2)[2]
    mode, msg = _extract_mode(rest)
    task = sched.add_once(chat_id, msg, dur, mode)
    label = "🤖 Task" if mode == "ask" else "✅ Reminder"
    await update.message.reply_text(
        f"{label} <code>{task['id']}</code> — in {fmt_duration(dur)}",
        parse_mode="HTML",
    )


async def _show_tasks(update: Update, chat_id: int) -> None:
    assert update.message
    tasks = sched.list_all(chat_id)
    if not tasks:
        await update.message.reply_text("📭 No scheduled tasks.")
        return

    _TYPE_ICONS = {"once": "⏱", "interval": "🔄", "daily": "📅"}
    lines = [f"📋 <b>Scheduled Tasks</b> ({len(tasks)})\n"]
    for t in tasks:
        icon = _TYPE_ICONS.get(t["type"], "❓")
        status = "✅" if t.get("enabled", True) else "⬜"
        mode_tag = "🤖" if t.get("mode") == "ask" else "💬"
        lines.append(
            f"{status} {icon}{mode_tag} <code>{t['id']}</code>  "
            f"{t.get('schedule_str', t['type'])}  "
            f"{t['message'][:40]}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


@owner_only
async def cmd_tasks(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message and update.effective_chat
    await _show_tasks(update, update.effective_chat.id)


# ── Plugin class ──────────────────────────────────────────────────────────────

class SchedulerPlugin(Plugin):
    name = "scheduler"
    display_name = "Task Scheduler"
    description = "Persistent scheduled tasks, reminders, and timed Claude queries"

    def register(self, app: Application, config: dict) -> None:
        app.add_handler(self.command("remind", cmd_remind))
        app.add_handler(self.command("tasks", cmd_tasks))

    def on_app_ready(self, app: Application) -> None:
        if app.job_queue:
            sched.init_job_queue(app.job_queue, restore=self.is_enabled())

    def get_admin_tabs(self) -> list[tuple[str, str, str, callable]]:
        from .panel import build_tasks_panel
        return [("tasks", "Tasks", "schedule", build_tasks_panel)]

    def get_commands(self) -> list[tuple[str, str]]:
        return [
            ("remind", "Scheduled tasks & reminders"),
            ("tasks", "List all scheduled tasks"),
        ]


plugin = SchedulerPlugin()
