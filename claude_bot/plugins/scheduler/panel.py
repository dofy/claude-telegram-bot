"""Admin UI panel for scheduled tasks."""

from nicegui import ui

from . import sched
from ..theme import (
    ICON_MUTED, SWITCH, BTN_PRIMARY, BTN_FLAT_DANGER, BTN_DANGER,
    TASK_TYPE_COLORS, TASK_MODE_COLORS,
)

_TYPE_ICONS = {"once": "⏱", "interval": "🔄", "daily": "📅"}
_MODE_ICONS = {"remind": "💬", "ask": "🤖"}


def build_tasks_panel():
    container = ui.column().classes("w-full gap-4")

    def render():
        container.clear()
        tasks = sched.list_all()
        with container:
            with ui.row().classes("w-full items-center mb-1"):
                ui.icon("schedule", color=ICON_MUTED, size="20px")
                ui.label("Scheduled Tasks").classes("text-base font-semibold")
                ui.space()
                active = sum(1 for t in tasks if t.get("enabled", True))
                ui.label(f"{active}/{len(tasks)} active").classes(
                    "text-xs text-gray-500"
                )

            if not tasks:
                with ui.column().classes("w-full items-center py-8 gap-2"):
                    ui.icon("event_busy", size="40px").classes("text-gray-600")
                    ui.label("No scheduled tasks").classes("text-sm text-gray-500")
                    ui.label("Use /remind in Telegram to create tasks.").classes(
                        "text-xs text-gray-600"
                    )
            else:
                for task in tasks:
                    _render_task_row(task, render)

            done = sum(
                1 for t in tasks
                if t["type"] == "once" and not t.get("enabled", True)
            )
            if done:
                def do_clean():
                    removed = sched.cleanup_done()
                    ui.notify(f"Removed {removed} completed task(s)", type="info")
                    render()

                ui.button(
                    f"Clean up {done} completed",
                    icon="delete_sweep",
                    on_click=do_clean,
                ).props("flat size=sm color=grey")

    render()


def _render_task_row(task: dict, render_fn):
    enabled = task.get("enabled", True)
    tid = task["id"]
    ttype = task["type"]
    mode = task.get("mode", "remind")
    mode_icon = _MODE_ICONS.get(mode, "💬")
    mode_color = TASK_MODE_COLORS.get(mode, "grey")

    card_cls = "w-full p-3" if enabled else "w-full p-3 opacity-50"
    with ui.card().classes(card_cls).props("flat bordered") as card:
        # view row
        view_row = ui.column().classes("w-full gap-1")
        with view_row:
            with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                ui.badge(
                    f"{_TYPE_ICONS.get(ttype, '?')} {ttype}",
                    color=TASK_TYPE_COLORS.get(ttype, "grey"),
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
                    SWITCH
                ).classes("shrink-0")

                def show_edit(vr=view_row, c=card):
                    vr.set_visibility(False)
                    edit_form.set_visibility(True)

                ui.button(icon="edit", on_click=show_edit).props(
                    f"flat dense round size=sm {BTN_PRIMARY}"
                ).classes("shrink-0")

                def confirm_delete(task_id=tid, msg=task["message"]):
                    with ui.dialog() as dlg, ui.card().classes("p-4").style("min-width:280px"):
                        ui.label("Delete Task?").classes("text-sm font-semibold")
                        ui.label(msg[:80] + ("…" if len(msg) > 80 else "")).classes(
                            "text-xs text-gray-400 break-all"
                        )
                        with ui.row().classes("w-full justify-end gap-2 mt-3"):
                            ui.button("Cancel", on_click=dlg.close).props("flat size=sm")

                            def do_delete(task_id=task_id):
                                sched.remove(task_id)
                                dlg.close()
                                ui.notify("Deleted", type="info")
                                render_fn()

                            ui.button("Delete", icon="delete", on_click=do_delete).props(
                                f"{BTN_DANGER} size=sm"
                            )
                    dlg.open()

                ui.button(icon="delete", on_click=confirm_delete).props(
                    BTN_FLAT_DANGER
                ).classes("shrink-0")

            ui.label(task["message"]).classes("text-sm w-full break-all")

        # edit form (hidden by default)
        _SCHED_HINTS = {
            "once": ("Duration", "e.g. 5m, 1h30m"),
            "interval": ("Interval", "e.g. 30m, 2h"),
            "daily": ("Time", "HH:MM e.g. 09:00"),
        }

        edit_form = ui.column().classes("w-full gap-3")
        edit_form.set_visibility(False)
        with edit_form:
            ui.label(f"Edit Task #{tid}").classes("text-sm font-semibold")

            msg_input = ui.input(
                label="Message / Prompt",
                value=task["message"],
            ).classes("w-full")

            with ui.row().classes("w-full gap-2 flex-wrap items-end"):
                type_sel = ui.select(
                    label="Type",
                    options={
                        "once": "⏱ Once",
                        "interval": "🔄 Interval",
                        "daily": "📅 Daily",
                    },
                    value=ttype,
                ).classes("w-36")

                mode_sel = ui.select(
                    label="Mode",
                    options={"remind": "💬 Remind", "ask": "🤖 Ask Claude"},
                    value=mode,
                ).classes("w-36")

                if ttype == "interval":
                    from . import fmt_duration
                    init_sched_val = fmt_duration(task.get("interval", 0))
                elif ttype == "daily":
                    init_sched_val = task.get("time", "")
                else:
                    init_sched_val = task.get("schedule_str", "")

                hint_label, hint_ph = _SCHED_HINTS[ttype]
                sched_input = ui.input(
                    label=hint_label,
                    placeholder=hint_ph,
                    value=init_sched_val,
                ).classes("w-40")

                def _on_type_change(e):
                    lbl, ph = _SCHED_HINTS.get(e.value, ("Schedule", ""))
                    sched_input.label = lbl
                    sched_input.placeholder = ph
                    sched_input.value = ""

                type_sel.on_value_change(_on_type_change)

            with ui.row().classes("gap-2"):
                def do_save(task_id=tid, orig_type=ttype, orig_sched=init_sched_val):
                    new_msg = msg_input.value.strip()
                    new_mode = mode_sel.value
                    new_type = type_sel.value
                    new_sched = sched_input.value.strip() if sched_input.value else None

                    if not new_msg:
                        ui.notify("Message cannot be empty", type="warning")
                        return

                    type_changed = new_type != orig_type
                    sched_changed = new_sched != orig_sched

                    if type_changed and not new_sched:
                        ui.notify("Schedule is required when changing type", type="warning")
                        return

                    ok = sched.update(
                        task_id,
                        message=new_msg,
                        mode=new_mode,
                        task_type=new_type if type_changed else None,
                        schedule=new_sched if (type_changed or sched_changed) else None,
                    )
                    if ok:
                        ui.notify("Task updated", type="positive")
                        render_fn()
                    else:
                        ui.notify("Invalid schedule format", type="negative")

                ui.button("Save", icon="save", on_click=do_save).props(
                    f"{BTN_PRIMARY} size=sm"
                )

                def do_cancel():
                    edit_form.set_visibility(False)
                    view_row.set_visibility(True)

                ui.button("Cancel", icon="close", on_click=do_cancel).props(
                    "flat size=sm"
                )
