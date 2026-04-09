"""Application assembly and entry point."""

import logging

from telegram.ext import Application, ContextTypes

from .config import cfg, BASE_DIR
from .log import setup_logging
from .cleanup import cleanup_inbox
from . import plugins
from .handlers import commands, message, group

__version__ = "0.3.0"


async def _periodic_cleanup(_ctx: ContextTypes.DEFAULT_TYPE) -> None:
    cleanup_inbox()


def _banner(log: logging.Logger) -> None:
    admin_cfg = cfg.plugins_config.get("admin_api", {})
    admin_enabled = admin_cfg.get("enabled", True)
    admin_port = admin_cfg.get("port", 8080)

    lines = [
        "",
        "╔══════════════════════════════════════════╗",
        "║        Claude Telegram Bot v{}        ║".format(__version__),
        "╚══════════════════════════════════════════╝",
        "",
        "  Configuration",
        "  ├─ Owner Chat ID :  {}".format(cfg.owner_chat_id or "(not set)"),
        "  ├─ Allowed Groups:  {}".format(
            ", ".join(str(g) for g in cfg.allowed_group_ids) or "(none)"
        ),
        "  ├─ Session TTL   :  {}h".format(cfg.session_ttl_hours),
        "  ├─ Max Retries   :  {}".format(cfg.claude_max_retries),
        "  └─ Inbox Cleanup :  {}h".format(cfg.inbox_max_age_hours),
        "",
        "  Services",
        "  ├─ Telegram Bot  :  polling",
        "  ├─ Admin Panel   :  {}".format(
            "http://127.0.0.1:{}".format(admin_port) if admin_enabled else "disabled"
        ),
        "  └─ Auth          :  {}".format(
            "token required" if cfg.admin_token else "open (no ADMIN_TOKEN)"
        ),
        "",
        "  Paths",
        "  ├─ Base Dir      :  {}".format(BASE_DIR),
        "  ├─ Config        :  {}".format(cfg._path),
        "  └─ Logs          :  {}".format(cfg.log_dir),
        "",
    ]
    for line in lines:
        log.info(line)


def create_app() -> Application:
    app = Application.builder().token(cfg.bot_token).build()
    commands.register(app)
    message.register(app)
    group.register(app)
    plugins.load_all(app)

    cleanup_inbox()
    app.job_queue.run_repeating(_periodic_cleanup, interval=3600, first=3600)

    return app


def run() -> None:
    log = setup_logging()

    if not cfg._path.exists():
        cfg.save()
        log.info("Created default config.json")

    _banner(log)

    app = create_app()
    log.info("Bot is now running. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)
