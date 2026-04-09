import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from .config import BASE_DIR, cfg

_ROTATION_MAP = {"daily": "midnight", "weekly": "W0"}


def setup_logging() -> logging.Logger:
    log_dir = Path(cfg.log_dir)
    if not log_dir.is_absolute():
        log_dir = BASE_DIR / log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    when = _ROTATION_MAP.get(cfg.log_rotation, "midnight")
    file_handler = TimedRotatingFileHandler(
        log_dir / "bot.log",
        when=when,
        backupCount=cfg.log_keep_days,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.suffix = "%Y-%m-%d"

    root = logging.getLogger("claude_bot")
    root.setLevel(getattr(logging, cfg.log_level.upper(), logging.INFO))
    root.addHandler(console)
    root.addHandler(file_handler)

    return root
