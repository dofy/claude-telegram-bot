"""Message sending: chunking, file detection, HTML fallback."""

import logging
import re
from pathlib import Path

log = logging.getLogger("claude_bot.sender")

_PATH_RE = re.compile(
    r"(?:/Users/[^\s]+|/tmp/[^\s]+|/var/folders/[^\s]+)/\S+"
)
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def chunk_text(text: str, max_len: int = 4000) -> list[str]:
    if len(text) <= max_len:
        return [text]
    segs = re.split(r"(\n\n+)", text)
    chunks: list[str] = []
    cur = ""
    for seg in segs:
        if len(cur) + len(seg) <= max_len:
            cur += seg
        else:
            if cur.strip():
                chunks.append(cur)
            seg = seg.lstrip("\n")
            while len(seg) > max_len:
                chunks.append(seg[:max_len])
                seg = seg[max_len:]
            cur = seg
    if cur.strip():
        chunks.append(cur)
    return chunks


async def send_files_in_text(bot, chat_id: int, text: str) -> str:
    """Detect file paths in text, send them, return cleaned text."""
    paths = _PATH_RE.findall(text)
    for raw_path in paths:
        path_str = raw_path.rstrip(".,;:!?)")
        p = Path(path_str)
        if not p.exists() or not p.is_file():
            continue
        try:
            ext = p.suffix.lower()
            with open(p, "rb") as fh:
                if ext in _IMAGE_EXTS:
                    await bot.send_photo(chat_id=chat_id, photo=fh)
                else:
                    await bot.send_document(
                        chat_id=chat_id, document=fh, filename=p.name
                    )
        except Exception as e:
            log.warning("Failed to send file %s: %s", path_str, e)
        text = text.replace(raw_path, "").replace(path_str, "")
    return text.strip()


async def send_reply(bot, chat_id: int, html: str) -> None:
    """Send (possibly chunked) HTML reply, with plain-text fallback."""
    html = await send_files_in_text(bot, chat_id, html)
    if not html:
        html = "(・_・;) uhh... nothing came out??"

    for chunk in chunk_text(html):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            await bot.send_message(chat_id=chat_id, text=chunk, parse_mode="HTML")
        except Exception as e:
            log.warning("HTML send failed (%s), falling back to plain text", e)
            plain = re.sub(r"<[^>]+>", "", chunk)
            try:
                await bot.send_message(chat_id=chat_id, text=plain)
            except Exception as e2:
                log.error("Plain text send also failed: %s", e2)
