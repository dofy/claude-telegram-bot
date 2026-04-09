"""Admin Web UI plugin — NiceGUI-based config management panel."""

import html as html_mod
import logging
import time
import threading
from collections import defaultdict

from nicegui import ui, app as nicegui_app
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from telegram.ext import Application

from ..base import Plugin
from ...config import cfg

_BOOT_TIME = time.time()

log = logging.getLogger("claude_bot.plugins.admin_api")

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


# ── Shared UI helpers (used by core panels and plugin panels) ─────────────────

def section_header(icon: str, title: str):
    with ui.row().classes("w-full items-center mb-2"):
        ui.icon(icon, color="red", size="20px")
        ui.label(title).classes("text-base font-semibold")


def code_block(text: str, lang: str = ""):
    """Render a copyable code block with syntax highlighting."""
    escaped = html_mod.escape(text)
    lang_cls = f"language-{lang}" if lang else ""
    with ui.card().classes("w-full p-0 overflow-hidden").props("flat bordered"):
        with ui.row().classes("w-full items-start"):
            ui.html(
                f"<pre style='margin:0;overflow-x:auto;flex:1;min-width:0'>"
                f"<code class='hljs {lang_cls}' style='font-size:11px;"
                f"line-height:1.5;white-space:pre;padding:12px;display:block'>"
                f"{escaped}</code></pre>"
            ).classes("flex-grow min-w-0")

            def _copy(t=text):
                ui.run_javascript(
                    f"navigator.clipboard.writeText({t!r})"
                )
                ui.notify("Copied", type="positive", position="bottom", timeout=1000)

            ui.button(icon="content_copy", on_click=_copy).props(
                "flat dense round size=sm color=grey"
            ).classes("mt-1 mr-1").tooltip("Copy all")


def stat_card(label: str, value: str, icon: str, color: str = "zinc"):
    with ui.card().classes(
        f"p-3 bg-{color}-900/30 border border-{color}-700/30"
    ).props("flat").style("min-width:0"):
        with ui.row().classes("items-center gap-1 mb-1"):
            ui.icon(icon, size="16px").classes(f"text-{color}-400")
            ui.label(label).classes("text-xs text-gray-400 truncate")
        ui.label(value).classes("text-lg font-bold")


def mask_value(v: str) -> str:
    n = len(v)
    if n > 10:
        return v[:4] + "*" * (n - 8) + v[-4:]
    if n > 4:
        return v[:2] + "*" * (n - 2)
    return "****"


def boot_time() -> float:
    return _BOOT_TIME


# ── NiceGUI theme helper ─────────────────────────────────────────────────────

def _apply_theme():
    ui.dark_mode(True)
    ui.colors(primary="#dc2626")
    ui.add_head_html(
        '<link rel="stylesheet" href='
        '"https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11/build/styles/github-dark.min.css">'
        '<script src='
        '"https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11/build/highlight.min.js"></script>'
        '<script>'
        'window._hljs_apply = () => {'
        '  if(!window.hljs) return;'
        '  document.querySelectorAll("pre code.hljs").forEach(el => el.removeAttribute("data-highlighted"));'
        '  hljs.highlightAll();'
        '};'
        'document.addEventListener("DOMContentLoaded", () => {'
        '  const run = () => { if(window.hljs) window._hljs_apply(); else setTimeout(run, 100); };'
        '  run();'
        '});'
        '</script>'
        '<style>'
        'body{overflow-x:hidden}'
        '.q-tab-panels,.q-tab-panel,.q-card{max-width:100%!important;overflow-x:hidden}'
        '.q-tab-panel>*{max-width:100%}'
        '@media(max-width:640px){'
        '  .q-card{padding:8px!important}'
        '  .q-tab-panel{padding:8px 4px!important}'
        '}'
        '</style>'
    )


# ── Login page ────────────────────────────────────────────────────────────────

@ui.page("/login", title="Claude Bot Admin")
def login_page() -> RedirectResponse | None:
    _apply_theme()

    if not cfg.admin_token or nicegui_app.storage.user.get("authenticated"):
        nicegui_app.storage.user["authenticated"] = True
        return RedirectResponse("/")

    with ui.card().classes("absolute-center p-8").style("width:min(90vw,384px)"):
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

@ui.page("/", title="Claude Bot Admin")
def admin_page(request: Request) -> RedirectResponse | None:
    if not _is_authenticated():
        return RedirectResponse("/login")

    _apply_theme()

    from .panels import CORE_TAB_DEFS_BEFORE, CORE_TAB_DEFS_AFTER, CORE_TAB_BUILDERS
    from .. import get_loaded

    tab_defs = list(CORE_TAB_DEFS_BEFORE)
    tab_builders = dict(CORE_TAB_BUILDERS)

    for pname, p in get_loaded().items():
        if pname == "admin_api" or not p.is_enabled():
            continue
        for slug, label, icon, builder in p.get_admin_tabs():
            tab_defs.append((slug, label, icon))
            tab_builders[slug] = builder

    tab_defs.extend(CORE_TAB_DEFS_AFTER)

    active_tab = request.query_params.get("tab", "dashboard")
    if active_tab not in tab_builders:
        active_tab = "dashboard"

    with ui.header().classes(
        "items-center bg-[#18181b] border-b border-zinc-800 px-4"
    ):
        ui.icon("smart_toy", color="red", size="24px")
        ui.label("Claude Bot").classes("text-sm font-bold ml-1")
        ui.space()

        def logout():
            nicegui_app.storage.user["authenticated"] = False
            ui.navigate.to("/login")

        ui.button(icon="logout", on_click=logout).props(
            "flat round color=grey"
        ).tooltip("Logout")

    with ui.column().classes("w-full mx-auto px-2 sm:px-4 pt-2").style(
        "max-width: min(100vw, 960px)"
    ):
        with ui.row().classes("w-full justify-center gap-0 flex-nowrap"):
            tab_btns: dict[str, ui.button] = {}
            for slug, label, icon in tab_defs:
                is_active = slug == active_tab

                def _make_click(s=slug):
                    def on_click():
                        for k, b in tab_btns.items():
                            b.props(
                                "flat color=red" if k == s else "flat color=grey"
                            )
                        panels.value = s
                        ui.run_javascript(
                            f"history.replaceState(null, '', '/?tab={s}');"
                            "setTimeout(() => window._hljs_apply && window._hljs_apply(), 50);"
                        )
                    return on_click

                btn = ui.button(
                    icon=icon, on_click=_make_click()
                ).props(
                    f"flat color={'red' if is_active else 'grey'}"
                ).classes("px-2 min-w-0").tooltip(label)
                tab_btns[slug] = btn

        ui.separator().classes("mt-0 mb-2")

        with ui.tab_panels(value=active_tab).classes("w-full overflow-hidden") as panels:
            for slug, _, _ in tab_defs:
                with ui.tab_panel(slug):
                    tab_builders[slug]()


# ── Plugin class ──────────────────────────────────────────────────────────────

class AdminApiPlugin(Plugin):
    name = "admin_api"
    display_name = "Admin Panel"
    description = "Web-based admin panel for bot configuration and monitoring"

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
            title="Claude Bot Admin",
            favicon="🤖",
            reload=False,
            show=False,
            storage_secret=cfg.admin_token or "claude-bot-fallback-secret",
        )


plugin = AdminApiPlugin()
