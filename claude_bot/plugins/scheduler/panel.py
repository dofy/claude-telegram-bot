"""Admin UI panel for scheduled tasks."""

from nicegui import ui

from ...config import cfg
from . import sched, parse_duration, fmt_duration, parse_time_str


_TYPE_ICONS = {"once": "⏱", "interval": "🔄", "daily": "📅"}
_TYPE_COLORS = {"once": "grey", "interval": "blue", "daily": "purple"}
_MODE_BADGES = {"remind": ("💬", "grey"), "ask": ("🤖", "red")}


def build_tasks_panel():
    container = ui.column().classes("w-full gap-4")

    def render():
        container.clear()
        tasks = sched.list_all()
        with container:
            with ui.row().classes("w-full items-center mb-1"):
                ui.icon("schedule", color="red", size="20px")
                ui.label("Scheduled Tasks").classes("text-base font-semibold")
                ui.space()
                active = sum(1 for t in tasks if t.get("enabled", True))
                ui.label(f"{active}/{len(tasks)} active").classes(
                    "text-xs text-gray-500"
                )

            if not tasks:
                ui.label("No tasks yet. Add one below.").classes(
                    "text-sm text-gray-500 italic"
                )
            else:
                for task in tasks:
                    _render_task_row(task, render)

            ui.separator().classes("my-2")

            # ── Add task form ─────────────────────────────────────────────
            ui.label("Add Task").classes("text-sm font-semibold")
            with ui.card().classes("w-full p-4").props("flat bordered"):
                with ui.row().classes("w-full gap-2 flex-wrap items-end"):
                    type_sel = ui.select(
                        label="Type",
                        options=["once", "interval", "daily"],
                        value="once",
                    ).classes("w-28")

                    mode_sel = ui.select(
                        label="Mode",
                        options={"remind": "💬 Remind", "ask": "🤖 Ask Claude"},
                        value="remind",
                    ).classes("w-36")

                    schedule_in = ui.input(
                        label="Schedule",
                        placeholder="5m / 1h / 09:00",
                    ).classes("w-32")

                    chat_in = ui.number(
                        label="Chat ID",
                        value=cfg.owner_chat_id or None,
                    ).classes("w-32")

                msg_in = ui.input(
                    label="Message / Prompt",
                    placeholder="Reminder text or Claude prompt...",
                ).classes("w-full")

                def do_add():
                    t = type_sel.value
                    md = mode_sel.value
                    s = (schedule_in.value or "").strip()
                    m = (msg_in.value or "").strip()
                    cid = int(chat_in.value) if chat_in.value else 0

                    if not s or not m or not cid:
                        ui.notify("Fill all fields", type="warning")
                        return

                    if t == "once":
                        dur = parse_duration(s)
                        if dur is None:
                            ui.notify("Invalid duration (e.g. 5m, 1h30m)", type="negative")
                            return
                        sched.add_once(cid, m, dur, md)
                    elif t == "interval":
                        dur = parse_duration(s)
                        if dur is None:
                            ui.notify("Invalid interval (e.g. 30m, 2h)", type="negative")
                            return
                        sched.add_interval(cid, m, dur, md)
                    elif t == "daily":
                        ts = parse_time_str(s)
                        if ts is None:
                            ui.notify("Invalid time (e.g. 09:00)", type="negative")
                            return
                        sched.add_daily(cid, m, ts, md)

                    ui.notify("Task added", type="positive")
                    render()

                ui.button("Add", icon="add", on_click=do_add).props(
                    "color=primary size=sm"
                )

            # ── Cleanup button ────────────────────────────────────────────
            done = sum(1 for t in tasks if t["type"] == "once" and not t.get("enabled", True))
            if done:
                def do_clean():
                    removed = sched.cleanup_done()
                    ui.notify(f"Removed {removed} completed task(s)", type="info")
                    render()

                ui.button(
                    f"Clean up {done} completed", icon="delete_sweep", on_click=do_clean,
                ).props("flat size=sm color=grey")

    render()


def _render_task_row(task: dict, render_fn):
    enabled = task.get("enabled", True)
    tid = task["id"]
    ttype = task["type"]
    card_cls = "w-full p-3" if enabled else "w-full p-3 opacity-50"

    mode = task.get("mode", "remind")
    mode_icon, mode_color = _MODE_BADGES.get(mode, ("💬", "grey"))

    with ui.card().classes(card_cls).props("flat bordered"):
        with ui.row().classes("w-full items-center gap-2 flex-wrap"):
            ui.badge(
                f"{_TYPE_ICONS.get(ttype, '?')} {ttype}",
                color=_TYPE_COLORS.get(ttype, "grey"),
            ).classes("text-xs")

            ui.badge(
                f"{mode_icon} {mode}",
                color=mode_color,
            ).classes("text-xs")

            ui.label(task.get("schedule_str", "")).classes(
                "text-xs font-mono text-gray-400"
            )

            ui.label(f"#{tid}").classes("text-xs text-gray-600")

            ui.space()

            def on_toggle(e, task_id=tid):
                sched.toggle(task_id, e.value)
                render_fn()

            ui.switch(value=enabled, on_change=on_toggle).props(
                "dense color=red"
            ).classes("shrink-0")

            def do_delete(task_id=tid):
                sched.remove(task_id)
                ui.notify("Deleted", type="info")
                render_fn()

            ui.button(icon="delete", on_click=do_delete).props(
                "flat dense round size=sm color=negative"
            ).classes("shrink-0")

        ui.label(task["message"]).classes(
            "text-sm w-full truncate"
        )
