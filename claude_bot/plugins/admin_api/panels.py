"""Core admin panel tab builders — owned by admin_api plugin."""

import os
import platform
import shutil
import sys
import time
from pathlib import Path

from nicegui import ui

from ...config import BASE_DIR, cfg
from ..theme import (
    STAT_UPTIME, STAT_MESSAGES, STAT_CLAUDE, STAT_AVG, STAT_SESSIONS,
    BADGE_CORE, SWITCH, BTN_PRIMARY, BTN_FLAT_PRIMARY, INPUT_PROPS,
)
from . import section_header, code_block, stat_card, mask_value, boot_time

# ── .env helpers ──────────────────────────────────────────────────────────────

_ENV_KEYS = ["BOT_TOKEN", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL"]
_MASK_KEYS = {"BOT_TOKEN", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"}
_ENV_PATH = BASE_DIR / ".env"
_SECRET_LABELS = {
    "BOT_TOKEN": "Bot Token",
    "ANTHROPIC_API_KEY": "Anthropic API Key",
    "ANTHROPIC_AUTH_TOKEN": "Anthropic Auth Token",
    "ANTHROPIC_BASE_URL": "Anthropic Base URL",
}


def _read_env() -> dict[str, str]:
    result: dict[str, str] = {}
    if not _ENV_PATH.exists():
        return result
    for line in _ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            k = k.strip()
            if k in _ENV_KEYS:
                result[k] = v.strip()
    return result


def _write_env(updates: dict[str, str]) -> None:
    existing_lines: list[str] = []
    written_keys: set[str] = set()
    if _ENV_PATH.exists():
        for line in _ENV_PATH.read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k = stripped.split("=", 1)[0].strip()
                if k in updates:
                    existing_lines.append(f"{k}={updates[k]}")
                    written_keys.add(k)
                    continue
            existing_lines.append(line)
    for k, v in updates.items():
        if k in _ENV_KEYS and k not in written_keys:
            existing_lines.append(f"{k}={v}")
    _ENV_PATH.write_text("\n".join(existing_lines) + "\n")


# ── Tab definitions ───────────────────────────────────────────────────────────

CORE_TAB_DEFS_BEFORE: list[tuple[str, str, str]] = [
    ("dashboard", "Dashboard", "dashboard"),
    ("secrets", "Secrets", "key"),
    ("acl", "ACL", "shield"),
    ("claude", "Claude", "memory"),
    ("plugins", "Plugins", "extension"),
]

CORE_TAB_DEFS_AFTER: list[tuple[str, str, str]] = [
    ("logs", "Logs", "terminal"),
    ("help", "Help", "help_outline"),
]

CORE_TAB_BUILDERS: dict[str, callable] = {}


def _register(slug: str):
    def decorator(fn):
        CORE_TAB_BUILDERS[slug] = fn
        return fn
    return decorator


# ── Dashboard ─────────────────────────────────────────────────────────────────

def _fmt_uptime(seconds: float) -> str:
    d, rem = divmod(int(seconds), 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    parts.append(f"{m}m")
    return " ".join(parts)


@_register("dashboard")
def _build_dashboard_panel():
    from ...app import __version__
    from ... import session

    section_header("dashboard", "Dashboard")

    uptime = time.time() - boot_time()

    try:
        from ..stats import stats
        s = stats.summary()
    except Exception:
        s = {
            "today_messages": 0, "today_calls": 0, "today_avg_time": 0.0,
            "today_total_time": 0.0, "total_messages": 0, "total_claude_calls": 0,
        }

    active_sessions = session.list_active()

    with ui.element("div").classes("w-full").style(
        "display:grid; grid-template-columns:repeat(auto-fit,minmax(100px,1fr)); gap:8px"
    ):
        stat_card("Uptime", _fmt_uptime(uptime), "schedule", STAT_UPTIME)
        stat_card("Messages", str(s["today_messages"]), "chat_bubble", STAT_MESSAGES)
        stat_card("Claude", str(s["today_calls"]), "psychology", STAT_CLAUDE)
        stat_card(
            "Avg",
            f"{s['today_avg_time']:.1f}s" if s["today_calls"] else "—",
            "speed", STAT_AVG,
        )
        stat_card("Sessions", str(len(active_sessions)), "group", STAT_SESSIONS)

    # ── Runtime info ──────────────────────────────────────────────────────
    with ui.card().classes("w-full mt-4").props("flat bordered"):
        ui.label("Runtime").classes("text-sm font-semibold mb-3")

        admin_cfg = cfg.plugins_config.get("admin_api", {})
        port = admin_cfg.get("port", 8080)

        rows = [
            ("Version", __version__),
            ("Python", platform.python_version()),
            ("OS", f"{platform.system()} {platform.release()}"),
            ("Owner", str(cfg.owner_chat_id)),
            ("Groups", str(len(cfg.allowed_group_ids))),
            ("Session TTL", f"{cfg.session_ttl_hours}h"),
            ("Max Retries", str(cfg.claude_max_retries)),
            ("Log Level", cfg.log_level),
            ("Admin Port", str(port)),
        ]
        with ui.element("div").classes("w-full").style(
            "display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:2px 16px"
        ):
            for label, val in rows:
                with ui.row().classes("items-center min-w-0"):
                    ui.label(label).classes("w-20 text-xs text-gray-400 shrink-0")
                    ui.label(val).classes("text-xs font-mono truncate min-w-0")

    # ── All-time stats ────────────────────────────────────────────────────
    with ui.card().classes("w-full mt-4").props("flat bordered"):
        ui.label("All-Time Statistics").classes("text-sm font-semibold mb-3")
        with ui.row().classes("gap-6 flex-wrap"):
            for label, val in [
                ("Total Messages", str(s["total_messages"])),
                ("Total Claude Calls", str(s["total_claude_calls"])),
                ("Today Time", f"{s['today_total_time']:.0f}s"),
            ]:
                with ui.column().classes("items-center"):
                    ui.label(val).classes("text-xl font-bold")
                    ui.label(label).classes("text-xs text-gray-400")

    # ── Active sessions table ─────────────────────────────────────────────
    if active_sessions:
        with ui.card().classes("w-full mt-4 overflow-hidden").props("flat bordered"):
            ui.label("Active Sessions").classes("text-sm font-semibold mb-3")
            columns = [
                {"name": "chat_id", "label": "Chat ID", "field": "chat_id", "align": "left"},
                {"name": "session_id", "label": "Session", "field": "session_id", "align": "left"},
                {"name": "idle_min", "label": "Idle", "field": "idle_min", "align": "right"},
            ]
            rows = [
                {**s, "idle_min": f"{s['idle_min']}min"}
                for s in active_sessions
            ]
            ui.table(columns=columns, rows=rows).classes("w-full").props(
                "flat dense bordered"
            )


# ── Secrets ───────────────────────────────────────────────────────────────────

@_register("secrets")
def _build_secrets_panel():
    container = ui.column().classes("w-full gap-4")

    def show_view():
        container.clear()
        raw = _read_env()
        with container:
            section_header("key", "Secrets (.env)")
            ui.label(
                "Stored in .env file. Changing BOT_TOKEN requires a bot restart."
            ).classes("text-xs text-gray-500 -mt-2")

            with ui.card().classes("w-full overflow-hidden"):
                for key in _ENV_KEYS:
                    val = raw.get(key, "")
                    with ui.column().classes("w-full py-2 px-2 gap-1"):
                        ui.label(_SECRET_LABELS.get(key, key)).classes(
                            "text-sm text-gray-400"
                        )
                        if not val:
                            ui.label("(not set)").classes(
                                "text-sm text-gray-600 italic"
                            )
                        elif key in _MASK_KEYS:
                            with ui.row().classes("items-center gap-2"):
                                masked = mask_value(val)
                                lbl = ui.label(masked).classes(
                                    "font-mono text-sm truncate"
                                ).style("max-width:calc(100vw - 120px)")

                                def _make_toggle(label_el, real, msk):
                                    state = {"revealed": False}

                                    def toggle():
                                        state["revealed"] = not state["revealed"]
                                        label_el.text = real if state["revealed"] else msk

                                    return toggle

                                ui.button(
                                    icon="visibility",
                                    on_click=_make_toggle(lbl, val, masked),
                                ).props("flat dense round size=sm")
                        else:
                            ui.label(val).classes(
                                "font-mono text-sm break-all"
                            )

            ui.button("Edit", icon="edit", on_click=show_edit).props(
                f"outline {BTN_PRIMARY}"
            )

    def show_edit():
        container.clear()
        with container:
            section_header("edit", "Edit Secrets")
            ui.label(
                "Enter new values. Leave blank to keep current value."
            ).classes("text-xs text-gray-500 -mt-2")

            inputs: dict[str, ui.input] = {}
            with ui.card().classes("w-full"):
                for key in _ENV_KEYS:
                    pw = key in _MASK_KEYS
                    inputs[key] = ui.input(
                        label=_SECRET_LABELS.get(key, key),
                        placeholder=f"Enter new {_SECRET_LABELS.get(key, key)}",
                        password=pw,
                        password_toggle_button=pw,
                    ).props(INPUT_PROPS).classes("w-full")

            with ui.row().classes("gap-2"):

                def save():
                    updates = {}
                    for k, inp in inputs.items():
                        v = inp.value.strip()
                        if v:
                            updates[k] = v
                    if not updates:
                        ui.notify("Nothing to save", type="warning")
                        return
                    current = _read_env()
                    current.update(updates)
                    _write_env(current)
                    os.environ.update(updates)
                    hint = (
                        " — restart bot for new token"
                        if "BOT_TOKEN" in updates
                        else ""
                    )
                    ui.notify(f"Secrets saved{hint}", type="positive")
                    show_view()

                ui.button("Save", icon="save", on_click=save).props(BTN_PRIMARY)
                ui.button("Cancel", icon="close", on_click=show_view).props("flat")

    show_view()


# ── ACL ───────────────────────────────────────────────────────────────────────

@_register("acl")
def _build_acl_panel():
    section_header("shield", "Access Control")

    owner_input = ui.number(
        label="Owner Chat ID",
        value=cfg.owner_chat_id or None,
    ).props(INPUT_PROPS).classes("w-full")

    groups_area = ui.textarea(
        label="Allowed Group IDs (one per line)",
        value="\n".join(str(g) for g in sorted(cfg.allowed_group_ids)),
    ).props(INPUT_PROPS).classes("w-full")

    def save():
        try:
            owner = int(owner_input.value) if owner_input.value else 0
            groups = [
                int(g.strip())
                for g in groups_area.value.split("\n")
                if g.strip()
            ]
            cfg.set_value(["acl", "owner_chat_id"], owner)
            cfg.set_value(["acl", "allowed_group_ids"], groups)
            ui.notify("Access control saved", type="positive")
        except ValueError:
            ui.notify("Invalid ID format", type="negative")

    ui.button("Save", icon="save", on_click=save).props(BTN_PRIMARY)


# ── Claude Settings ───────────────────────────────────────────────────────────

@_register("claude")
def _build_claude_panel():
    section_header("memory", "Claude Settings")

    skip_perm = ui.switch(
        "dangerously_skip_permissions",
        value=cfg.claude_skip_permissions,
    )

    with ui.row().classes("gap-4 flex-wrap"):
        max_retries = ui.number(
            label="Max Retries",
            value=cfg.claude_max_retries,
            min=0,
            max=5,
        ).props(INPUT_PROPS).classes("w-40")

        session_ttl = ui.number(
            label="Session TTL (hours)",
            value=cfg.session_ttl_hours,
            min=1,
        ).props(INPUT_PROPS).classes("w-40")

    def save():
        cfg.set_value(
            ["claude", "dangerously_skip_permissions"], skip_perm.value
        )
        cfg.set_value(["claude", "max_retries"], int(max_retries.value))
        cfg.set_value(["claude", "session_ttl_hours"], int(session_ttl.value))
        ui.notify("Claude settings saved", type="positive")

    ui.button("Save", icon="save", on_click=save).props(BTN_PRIMARY)


# ── Plugins ───────────────────────────────────────────────────────────────────

@_register("plugins")
def _build_plugins_panel():
    section_header("extension", "Plugins")
    from .. import get_loaded

    _PROTECTED = {"admin_api"}
    container = ui.column().classes("w-full gap-2")

    def render():
        container.clear()
        all_plugins = get_loaded()
        with container:
            ui.label(
                "Toggle plugins on/off. Changes take effect immediately — no restart needed."
            ).classes("text-xs text-gray-500 mb-1")

            for name in sorted(all_plugins):
                p = all_plugins[name]
                enabled = p.is_enabled()
                protected = name in _PROTECTED
                label = p.display_name or name
                desc = p.description or ""

                with ui.card().classes(
                    "w-full p-2" if enabled else "w-full p-2 opacity-50"
                ).props("flat bordered"):
                    with ui.row().classes("w-full items-center gap-2"):

                        with ui.column().classes("flex-grow gap-0 min-w-0"):
                            ui.label(label).classes("font-medium text-sm")
                            if desc:
                                ui.label(desc).classes(
                                    "text-xs text-gray-500 truncate"
                                )

                        if protected:
                            ui.badge("core", color=BADGE_CORE).classes("text-xs shrink-0")
                        else:
                            def _make_toggle(pname=name):
                                def on_change(e):
                                    cfg.set_value(
                                        ["plugins", pname, "enabled"], e.value
                                    )
                                    ui.run_javascript("setTimeout(() => window.location.assign('/?tab=plugins'), 300)")
                                return on_change

                            ui.switch(
                                value=enabled, on_change=_make_toggle()
                            ).props(SWITCH).classes("shrink-0")

    render()


# ── Logs ──────────────────────────────────────────────────────────────────────

@_register("logs")
def _build_logs_panel():
    section_header("terminal", "Logs")

    with ui.expansion("Log Settings", icon="tune").classes(
        "w-full"
    ).props("dense header-class='text-sm font-semibold'"):
        with ui.column().classes("w-full gap-3 pt-2"):
            log_dir = ui.input(
                label="Directory", value=cfg.log_dir
            ).props(INPUT_PROPS).classes("w-full")

            with ui.row().classes("gap-3 flex-wrap"):
                rotation = ui.select(
                    label="Rotation",
                    options=["daily", "weekly"],
                    value=cfg.log_rotation,
                ).props(INPUT_PROPS).classes("w-36")

                keep_days = ui.number(
                    label="Keep Days", value=cfg.log_keep_days
                ).props(INPUT_PROPS).classes("w-36")

                level = ui.select(
                    label="Level",
                    options=["DEBUG", "INFO", "WARNING", "ERROR"],
                    value=cfg.log_level,
                ).props(INPUT_PROPS).classes("w-36")

            ui.label("Changes require a bot restart.").classes(
                "text-xs text-gray-500"
            )

            def save_settings():
                cfg.set_value(["log", "dir"], log_dir.value)
                cfg.set_value(["log", "rotation"], rotation.value)
                cfg.set_value(["log", "keep_days"], int(keep_days.value))
                cfg.set_value(["log", "level"], level.value)
                ui.notify(
                    "Log settings saved — restart to apply", type="positive"
                )

            ui.button("Save", icon="save", on_click=save_settings).props(
                f"{BTN_PRIMARY} size=sm"
            )

    ui.separator().classes("my-2")

    log_path = Path(cfg.log_dir)
    if not log_path.is_absolute():
        log_path = BASE_DIR / log_path

    log_files: list[str] = []
    if log_path.exists():
        log_files = sorted(
            [f.name for f in log_path.iterdir() if f.is_file() and f.suffix == ".log"],
            reverse=True,
        )
        dated = sorted(
            [f.name for f in log_path.iterdir()
             if f.is_file() and f.suffix != ".log" and f.name.startswith("bot.log.")],
            reverse=True,
        )
        log_files.extend(dated)

    if not log_files:
        log_files = ["bot.log"]

    with ui.row().classes("w-full items-center gap-3 flex-wrap"):
        file_select = ui.select(
            label="Log File",
            options=log_files,
            value=log_files[0] if log_files else "bot.log",
        ).props(INPUT_PROPS).classes("w-48 min-w-0")

        lines_select = ui.select(
            label="Lines",
            options=[100, 200, 300, 500, 1000],
            value=300,
        ).props(INPUT_PROPS).classes("w-28")

        auto_scroll = ui.switch("Auto scroll", value=True).props(SWITCH)

    log_view = ui.log(max_lines=1000).classes("w-full").style("height:min(500px,60vh)")

    def refresh():
        fname = file_select.value
        max_lines = int(lines_select.value)
        fpath = log_path / fname
        log_view.clear()
        if fpath.exists():
            lines = fpath.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
            for line in lines[-max_lines:]:
                log_view.push(line)
        else:
            log_view.push(f"File not found: {fpath}")

    with ui.row().classes("gap-2 mt-1"):
        ui.button("Refresh", icon="refresh", on_click=refresh).props(
            f"{BTN_FLAT_PRIMARY} size=sm"
        )

        def clear_view():
            log_view.clear()

        ui.button("Clear", icon="clear_all", on_click=clear_view).props(
            "flat color=grey size=sm"
        )

    refresh()


# ── Help ──────────────────────────────────────────────────────────────────────

@_register("help")
def _build_help_panel():
    from ...app import __version__

    section_header("help_outline", "Help & Quick Reference")

    uv_path = shutil.which("uv") or "/opt/homebrew/bin/uv"
    python_ver = platform.python_version()
    os_info = f"{platform.system()} {platform.release()}"

    admin_cfg = cfg.plugins_config.get("admin_api", {})
    admin_port = admin_cfg.get("port", 8080)
    admin_enabled = admin_cfg.get("enabled", True)

    with ui.card().classes("w-full").props("flat bordered"):
        ui.label("Runtime Environment").classes("text-sm font-semibold mb-2")
        rows = [
            ("Version", __version__),
            ("Python", f"{python_ver} ({sys.executable})"),
            ("uv", uv_path),
            ("OS", os_info),
            ("Base Dir", str(BASE_DIR)),
            ("Admin Panel", f"http://127.0.0.1:{admin_port}" if admin_enabled else "disabled"),
            ("Admin Auth", cfg.admin_token or "(disabled)"),
        ]
        for label, val in rows:
            with ui.row().classes("w-full items-start py-1 px-2 min-w-0"):
                ui.label(label).classes("w-20 text-xs text-gray-400 shrink-0")
                ui.label(val).classes("text-xs font-mono break-all min-w-0")

    ui.label("Manual Start (Bot + Admin Panel)").classes(
        "text-sm font-semibold mt-6 mb-2"
    )
    code_block(f"cd {BASE_DIR}\n{uv_path} run bot.py", lang="bash")

    label_name = "xyz.phpz.claude-telegram-bot"
    home = Path.home()
    plist_path = home / "Library" / "LaunchAgents" / f"{label_name}.plist"

    ui.label("Daemon Management (launchd)").classes(
        "text-sm font-semibold mt-6 mb-2"
    )

    cmds = [
        ("Start", f"launchctl start {label_name}"),
        ("Stop", f"launchctl stop {label_name}"),
        ("Restart", f"launchctl stop {label_name} && sleep 2 && launchctl start {label_name}"),
        ("Load (enable)", f"launchctl load {plist_path}"),
        ("Unload (disable)", f"launchctl unload {plist_path}"),
        ("Check status", f"launchctl list | grep {label_name}"),
    ]
    for title, cmd in cmds:
        with ui.row().classes(
            "w-full items-center gap-2 mb-1 flex-nowrap min-w-0"
        ):
            ui.label(title).classes("w-20 text-xs text-gray-400 shrink-0")
            ui.label(cmd).classes(
                "text-xs font-mono bg-gray-100 text-gray-800 px-2 py-1.5 rounded "
                "min-w-0 border border-gray-200"
            ).style("flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap")

            def _copy(text=cmd):
                ui.run_javascript(
                    f"navigator.clipboard.writeText({text!r})"
                )
                ui.notify("Copied", type="positive", position="bottom", timeout=1000)

            ui.button(icon="content_copy", on_click=_copy).props(
                "flat dense round size=xs"
            ).classes("shrink-0").tooltip("Copy")

    ui.label("BotFather Command List").classes(
        "text-sm font-semibold mt-6 mb-1"
    )
    ui.label(
        "Copy and send to @BotFather → /setcommands"
    ).classes("text-xs text-gray-500 mb-2")

    _CORE_CMDS = [
        ("start", "Show welcome & command list"),
        ("help", "Same as /start"),
        ("status", "Check bot status"),
        ("sysinfo", "Show system info"),
        ("reset", "Clear conversation session"),
        ("stop", "Shut down the bot"),
    ]
    from .. import get_loaded
    plugin_cmds: list[tuple[str, str]] = []
    for pname, p in get_loaded().items():
        if p.is_enabled():
            plugin_cmds.extend(p.get_commands())

    all_cmds = _CORE_CMDS + plugin_cmds
    code_block("\n".join(f"{cmd} - {desc}" for cmd, desc in all_cmds))

    ui.label("Current plist File").classes("text-sm font-semibold mt-6 mb-1")
    ui.label(str(plist_path)).classes("text-xs text-gray-500 mb-2 font-mono break-all")

    if plist_path.exists():
        plist_content = plist_path.read_text(encoding="utf-8", errors="replace")
        code_block(plist_content, lang="xml")
    else:
        ui.label("No plist found at this path.").classes(
            "text-xs text-gray-500 italic"
        )
        ui.label("Install with:").classes("text-xs text-gray-400 mt-1")
        example = BASE_DIR / f"{label_name}.plist.example"
        code_block(
            f"cp {example} {plist_path}\n"
            f"# Edit paths in the plist, then:\n"
            f"launchctl load {plist_path}",
            lang="bash",
        )
