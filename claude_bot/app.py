"""Application assembly and entry point."""

import logging

from telegram.ext import Application, ContextTypes

from .config import cfg
from .log import setup_logging
from .cleanup import cleanup_inbox
from . import plugins
from .handlers import commands, message, group


async def _periodic_cleanup(_ctx: ContextTypes.DEFAULT_TYPE) -> None:
    cleanup_inbox()


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
    log.info("Claude Bot starting...")
    log.info("Owner=%d  Groups=%s", cfg.owner_chat_id, cfg.allowed_group_ids)

    if not cfg._path.exists():
        cfg.save()
        log.info("Created default config.json")

    app = create_app()
    app.run_polling(drop_pending_updates=True)
