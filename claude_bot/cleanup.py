"""Periodic cleanup of inbox media files."""

import logging
import time
from pathlib import Path

from .config import BASE_DIR, cfg

log = logging.getLogger("claude_bot.cleanup")

INBOX_DIR = BASE_DIR / "inbox"


def cleanup_inbox() -> int:
    """Delete files older than configured max_age_hours. Returns count."""
    max_age = cfg.inbox_max_age_hours * 3600
    if not INBOX_DIR.exists():
        return 0
    now = time.time()
    deleted = 0
    for f in INBOX_DIR.iterdir():
        if f.is_file() and now - f.stat().st_mtime > max_age:
            try:
                f.unlink()
                deleted += 1
            except OSError:
                pass
    if deleted:
        log.info("Cleaned up %d old inbox file(s)", deleted)
    return deleted
