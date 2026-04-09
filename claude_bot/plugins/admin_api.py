"""Admin Web UI plugin — NiceGUI-based config management panel."""

import logging
import os
import time
import threading
from collections import defaultdict
from pathlib import Path

from nicegui import ui, app as nicegui_app
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from telegram.ext import Application

from .base import Plugin
from ..config import BASE_DIR, cfg

log = logging.getLogger("claude_bot.plugins.admin_api")

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


def _mask(v: str) -> str:
    n = len(v)
    if n > 10:
        return v[:4] + "*" * (n - 8) + v[-4:]
    if n > 4:
        return v[:2] + "*" * (n - 2)
    return "****"


# ── Rate limiter middleware ───────────────────────────────────────────────────

_rate_hits: dict[str, list[float]] = defaultdict(list)
_RATE_MAX = 60
_RATE_WINDOW = 60.0


@nicegui_app.middleware("http")
async def _rate_limit(request: Request, call_next):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    hits = _rate_hits[ip]
    _rate_hits[ip] = [t for t in hits if now - t < _RATE_WINDOW]
    if len(_rate_hits[ip]) >= _RATE_MAX:
        return JSONResponse({"error": "rate limited"}, status_code=429)
    _rate_hits[ip].append(now)
    return await call_next(request)


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _is_authenticated() -> bool:
    if not cfg.admin_token:
        return True
    return bool(nicegui_app.storage.user.get("authenticated"))


# ── NiceGUI theme helper ─────────────────────────────────────────────────────

def _apply_theme():
    ui.dark_mode(True)
    ui.colors(primary="#dc2626")


# ── Login page ────────────────────────────────────────────────────────────────

@ui.page("/login")
def login_page() -> RedirectResponse | None:
    _apply_theme()

    if not cfg.admin_token or nicegui_app.storage.user.get("authenticated"):
        nicegui_app.storage.user["authenticated"] = True
        return RedirectResponse("/")

    with ui.card().classes("absolute-center w-96 p-8"):
        with ui.row().classes("items-center gap-3 mb-6"):
            ui.icon("smart_toy", size="32px").classes("text-red-600")
            ui.label("Claude Bot Admin").classes("text-xl font-bold")

        token_input = ui.input(
            "Admin Token",
            password=True,
            password_toggle_button=True,
        ).classes("w-full")

        def do_login():
            if token_input.value == cfg.admin_token:
                nicegui_app.storage.user["authenticated"] = True
                ui.navigate.to("/")
            else:
                ui.notify("Invalid token", type="negative")

        token_input.on("keydown.enter", do_login)
        ui.button("Login", on_click=do_login, icon="login").classes("w-full mt-4")
    return None


# ── Admin page ────────────────────────────────────────────────────────────────

@ui.page("/")
def admin_page() -> RedirectResponse | None:
    if not _is_authenticated():
        return RedirectResponse("/login")

    _apply_theme()

    with ui.header().classes("items-center bg-[#18181b] border-b border-zinc-800"):
        ui.icon("smart_toy", color="red", size="28px")
        ui.label("Claude Bot").classes("text-lg font-bold")
        ui.label("Admin").classes("text-red-500 text-sm ml-1")
        ui.space()

        def logout():
            nicegui_app.storage.user["authenticated"] = False
            ui.navigate.to("/login")

        ui.button(icon="logout", on_click=logout).props("flat round color=grey").tooltip("Logout")

    with ui.column().classes("w-full max-w-5xl mx-auto p-6"):
        with ui.tabs().classes("w-full") as tabs:
            secrets_tab = ui.tab("Secrets", icon="key")
            acl_tab = ui.tab("ACL", icon="shield")
            thinking_tab = ui.tab("Thinking", icon="chat")
            claude_tab = ui.tab("Claude", icon="memory")
            log_tab = ui.tab("Log", icon="tune")
            plugins_tab = ui.tab("Plugins", icon="extension")
            logs_tab = ui.tab("Logs", icon="terminal")

        with ui.tab_panels(tabs, value=secrets_tab).classes("w-full"):
            with ui.tab_panel(secrets_tab):
                _build_secrets_panel()
            with ui.tab_panel(acl_tab):
                _build_acl_panel()
            with ui.tab_panel(thinking_tab):
                _build_thinking_panel()
            with ui.tab_panel(claude_tab):
                _build_claude_panel()
            with ui.tab_panel(log_tab):
                _build_log_panel()
            with ui.tab_panel(plugins_tab):
                _build_plugins_panel()
            with ui.tab_panel(logs_tab):
                _build_logs_panel()


# ── Panel builders ────────────────────────────────────────────────────────────

def _section_header(icon: str, title: str):
    with ui.row().classes("w-full items-center mb-4"):
        ui.icon(icon, color="red", size="24px")
        ui.label(title).classes("text-lg font-semibold")


def _build_secrets_panel():
    container = ui.column().classes("w-full gap-4")

    def show_view():
        container.clear()
        raw = _read_env()
        with container:
            _section_header("key", "Secrets (.env)")
            ui.label(
                "Stored in .env file. Changing BOT_TOKEN requires a bot restart."
            ).classes("text-xs text-gray-500 -mt-2")

            with ui.card().classes("w-full"):
                for key in _ENV_KEYS:
                    val = raw.get(key, "")
                    with ui.row().classes("w-full items-center py-2 px-2"):
                        ui.label(_SECRET_LABELS.get(key, key)).classes(
                            "w-52 text-sm text-gray-400"
                        )
                        if not val:
                            ui.label("(not set)").classes(
                                "text-sm text-gray-600 italic flex-grow"
                            )
                        elif key in _MASK_KEYS:
                            masked = _mask(val)
                            lbl = ui.label(masked).classes(
                                "font-mono text-sm flex-grow"
                            )

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
                            ui.label(val).classes("font-mono text-sm flex-grow")

            ui.button("Edit", icon="edit", on_click=show_edit).props(
                "outline color=primary"
            )

    def show_edit():
        container.clear()
        with container:
            _section_header("edit", "Edit Secrets")
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
                    ).classes("w-full")

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

                ui.button("Save", icon="save", on_click=save).props("color=primary")
                ui.button("Cancel", icon="close", on_click=show_view).props("flat")

    show_view()


def _build_acl_panel():
    _section_header("shield", "Access Control")

    owner_input = ui.number(
        label="Owner Chat ID",
        value=cfg.owner_chat_id or None,
    ).classes("w-full")

    groups_area = ui.textarea(
        label="Allowed Group IDs (one per line)",
        value="\n".join(str(g) for g in sorted(cfg.allowed_group_ids)),
    ).classes("w-full")

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

    ui.button("Save", icon="save", on_click=save).props("color=primary")


def _build_thinking_panel():
    _section_header("chat", "Thinking Messages")
    ui.label("One per line. Bot picks randomly while processing.").classes(
        "text-xs text-gray-500 -mt-2"
    )

    area = ui.textarea(
        value="\n".join(cfg.thinking_messages),
    ).classes("w-full").props("rows=16")

    def save():
        msgs = [m for m in area.value.split("\n") if m.strip()]
        cfg.set_value(["thinking_messages"], msgs)
        ui.notify("Thinking messages saved", type="positive")

    ui.button("Save", icon="save", on_click=save).props("color=primary")


def _build_claude_panel():
    _section_header("memory", "Claude Settings")

    skip_perm = ui.switch(
        "dangerously_skip_permissions",
        value=cfg.claude_skip_permissions,
    )

    with ui.row().classes("gap-4"):
        max_retries = ui.number(
            label="Max Retries",
            value=cfg.claude_max_retries,
            min=0,
            max=5,
        ).classes("w-48")

        session_ttl = ui.number(
            label="Session TTL (hours)",
            value=cfg.session_ttl_hours,
            min=1,
        ).classes("w-48")

    def save():
        cfg.set_value(
            ["claude", "dangerously_skip_permissions"], skip_perm.value
        )
        cfg.set_value(["claude", "max_retries"], int(max_retries.value))
        cfg.set_value(["claude", "session_ttl_hours"], int(session_ttl.value))
        ui.notify("Claude settings saved", type="positive")

    ui.button("Save", icon="save", on_click=save).props("color=primary")


def _build_log_panel():
    _section_header("tune", "Log Settings")

    log_dir = ui.input(label="Directory", value=cfg.log_dir).classes("w-full")

    with ui.row().classes("gap-4"):
        rotation = ui.select(
            label="Rotation",
            options=["daily", "weekly"],
            value=cfg.log_rotation,
        ).classes("w-48")

        keep_days = ui.number(
            label="Keep Days", value=cfg.log_keep_days
        ).classes("w-48")

        level = ui.select(
            label="Level",
            options=["DEBUG", "INFO", "WARNING", "ERROR"],
            value=cfg.log_level,
        ).classes("w-48")

    ui.label("Changes require a bot restart.").classes(
        "text-xs text-gray-500"
    )

    def save():
        cfg.set_value(["log", "dir"], log_dir.value)
        cfg.set_value(["log", "rotation"], rotation.value)
        cfg.set_value(["log", "keep_days"], int(keep_days.value))
        cfg.set_value(["log", "level"], level.value)
        ui.notify("Log settings saved — restart to apply", type="positive")

    ui.button("Save", icon="save", on_click=save).props("color=primary")


def _build_plugins_panel():
    _section_header("extension", "Plugins")
    from . import get_loaded

    loaded = get_loaded()
    with ui.card().classes("w-full"):
        for name, pcfg in cfg.plugins_config.items():
            is_loaded = name in loaded
            with ui.row().classes("w-full items-center py-2 px-2"):
                ui.icon(
                    "circle",
                    color="green" if is_loaded else "grey",
                    size="12px",
                )
                ui.label(name).classes("font-medium text-sm flex-grow")
                color = "green" if pcfg.get("enabled", True) else "grey"
                text = "enabled" if pcfg.get("enabled", True) else "disabled"
                ui.badge(text, color=color).classes("text-xs")


def _build_logs_panel():
    _section_header("terminal", "Live Logs")
    log_view = ui.log(max_lines=500).classes("w-full h-[600px]")

    def refresh():
        log_path = Path(cfg.log_dir)
        if not log_path.is_absolute():
            log_path = BASE_DIR / log_path
        log_file = log_path / "bot.log"
        if log_file.exists():
            lines = log_file.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
            log_view.clear()
            for line in lines[-300:]:
                log_view.push(line)

    ui.button("Refresh", icon="refresh", on_click=refresh).props(
        "flat color=primary"
    )
    refresh()


# ── Plugin class ──────────────────────────────────────────────────────────────


class AdminApiPlugin(Plugin):
    name = "admin_api"
    description = "Web admin panel for bot configuration"

    def register(self, app: Application, config: dict) -> None:
        port = config.get("port", 8080)
        thread = threading.Thread(
            target=self._run, args=(port,), daemon=True
        )
        thread.start()
        log.info("Admin API listening on http://127.0.0.1:%d", port)

    def _run(self, port: int) -> None:
        ui.run(
            port=port,
            host="127.0.0.1",
            reload=False,
            show=False,
            storage_secret=cfg.admin_token or "claude-bot-fallback-secret",
        )


plugin = AdminApiPlugin()
