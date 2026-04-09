"""Session management with TTL expiration."""

import time
from pathlib import Path

_sessions: dict[int, str] = {}
_last_active: dict[int, float] = {}
_SESSION_DIR = Path("/tmp")


def _ttl_seconds() -> float:
    from .config import cfg
    return cfg.session_ttl_hours * 3600


def _path_for(chat_id: int) -> Path:
    return _SESSION_DIR / f"claude-bot-session-{chat_id}"


def load(chat_id: int) -> str | None:
    ttl = _ttl_seconds()
    now = time.time()

    if chat_id in _sessions:
        if ttl and now - _last_active.get(chat_id, 0) > ttl:
            clear(chat_id)
            return None
        _last_active[chat_id] = now
        return _sessions[chat_id]

    p = _path_for(chat_id)
    if p.exists():
        if ttl and now - p.stat().st_mtime > ttl:
            clear(chat_id)
            return None
        sid = p.read_text().strip()
        if sid:
            _sessions[chat_id] = sid
            _last_active[chat_id] = now
            return sid
    return None


def save(chat_id: int, session_id: str) -> None:
    _sessions[chat_id] = session_id
    _last_active[chat_id] = time.time()
    try:
        _path_for(chat_id).write_text(session_id)
    except OSError:
        pass


def clear(chat_id: int) -> None:
    _sessions.pop(chat_id, None)
    _last_active.pop(chat_id, None)
    _path_for(chat_id).unlink(missing_ok=True)


def list_active() -> list[dict]:
    """Return info about all known sessions."""
    now = time.time()
    ttl = _ttl_seconds()
    result = []
    for cid, sid in list(_sessions.items()):
        last = _last_active.get(cid, 0)
        if ttl and now - last > ttl:
            continue
        idle_min = int((now - last) / 60) if last else 0
        result.append({
            "chat_id": cid,
            "session_id": sid[:12] + "…",
            "idle_min": idle_min,
        })
    return result
