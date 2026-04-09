"""Admin UI panel for thinking messages."""

from nicegui import ui

from ...config import cfg


def build_thinking_panel():
    msgs: list[dict] = [dict(m) for m in cfg.thinking_messages]
    container = ui.column().classes("w-full gap-2")

    def _persist():
        cfg.set_value(["thinking_messages"], msgs)

    def _count_text():
        enabled = sum(1 for m in msgs if m.get("enabled", True))
        return f"{enabled}/{len(msgs)} enabled"

    def render():
        container.clear()
        with container:
            with ui.row().classes("w-full items-center mb-1"):
                ui.icon("chat", color="red", size="20px")
                ui.label("Thinking Messages").classes("text-base font-semibold")
                ui.space()
                ui.label(_count_text()).classes("text-xs text-gray-500")

            ui.label(
                "Bot randomly picks one enabled message while processing."
            ).classes("text-xs text-gray-500 mb-1")

            with ui.row().classes("gap-1 mb-1"):
                def enable_all():
                    for m in msgs:
                        m["enabled"] = True
                    _persist()
                    render()
                    ui.notify("All enabled", type="positive")

                def disable_all():
                    for m in msgs:
                        m["enabled"] = False
                    _persist()
                    render()
                    ui.notify("All disabled", type="info")

                ui.button("Enable All", icon="check_circle",
                          on_click=enable_all).props("flat dense size=sm")
                ui.button("Disable All", icon="unpublished",
                          on_click=disable_all).props("flat dense size=sm")

            for idx, msg in enumerate(msgs):

                def _make_row(i: int, m: dict):
                    enabled = m.get("enabled", True)
                    card_cls = "w-full p-1 px-2" if enabled else "w-full p-1 px-2 opacity-50"
                    with ui.card().classes(card_cls).props("flat bordered"):
                        with ui.row().classes(
                            "w-full items-center gap-1 flex-nowrap"
                        ):
                            ui.label(f"#{i + 1}").classes(
                                "text-xs text-gray-600 shrink-0"
                            ).style("width:20px")

                            def on_toggle(e, index=i):
                                msgs[index]["enabled"] = e.value
                                _persist()
                                render()

                            ui.switch(value=enabled, on_change=on_toggle).props(
                                "dense color=red"
                            ).classes("shrink-0")

                            inp = ui.input(value=m["text"]).classes(
                                "flex-grow min-w-0"
                            ).props("dense borderless")

                            def do_save(input_el=inp, index=i):
                                v = input_el.value.strip()
                                if not v:
                                    ui.notify("Empty — use delete instead",
                                              type="warning")
                                    return
                                msgs[index]["text"] = v
                                _persist()
                                ui.notify("Saved", type="positive")

                            def do_delete(index=i):
                                msgs.pop(index)
                                _persist()
                                render()
                                ui.notify("Deleted", type="info")

                            ui.button(icon="save", on_click=do_save).props(
                                "flat dense round size=xs color=primary"
                            ).classes("shrink-0")
                            ui.button(icon="close", on_click=do_delete).props(
                                "flat dense round size=xs color=negative"
                            ).classes("shrink-0")

                _make_row(idx, msg)

            with ui.card().classes("w-full p-1 px-2").props("flat bordered"):
                with ui.row().classes("w-full items-center gap-1 flex-nowrap"):
                    ui.icon("add", color="grey", size="18px").classes("shrink-0")
                    new_input = ui.input(
                        placeholder="Add new message..."
                    ).classes("flex-grow min-w-0").props("dense borderless")

                    def do_add():
                        v = new_input.value.strip()
                        if not v:
                            ui.notify("Enter a message first", type="warning")
                            return
                        msgs.append({"text": v, "enabled": True})
                        _persist()
                        render()
                        ui.notify("Added", type="positive")

                    ui.button(icon="add_circle", on_click=do_add).props(
                        "flat dense round size=xs color=primary"
                    ).classes("shrink-0")

    render()
