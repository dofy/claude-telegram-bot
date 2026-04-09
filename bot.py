#!/usr/bin/env python3
# Claude Code Telegram Bot (Python rewrite)
# Requires: python-telegram-bot>=20.0, python-dotenv

import asyncio
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction as ChatActionEnum
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent.resolve()

# Load .env (fallback to legacy Documents path used by old bot.sh)
_env_paths = [
    SCRIPT_DIR / ".env",
    Path.home() / "Documents/config/claude/telegram-bot/.env",
]
for _p in _env_paths:
    if _p.exists():
        load_dotenv(_p)
        log.info("Loaded .env from %s", _p)
        break

BOT_TOKEN = os.environ["BOT_TOKEN"]
ALLOWED_CHAT_ID = int(os.environ["ALLOWED_CHAT_ID"])
ALLOWED_GROUP_IDS: set[int] = set()
for _gid in os.environ.get("ALLOWED_GROUP_IDS", "").split(","):
    _gid = _gid.strip()
    if _gid:
        ALLOWED_GROUP_IDS.add(int(_gid))

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "")
CONTEXT_LENGTH = int(os.environ.get("CONTEXT_LENGTH", "3"))

INBOX_DIR = SCRIPT_DIR / "inbox"

# ── Claude binary discovery ───────────────────────────────────────────────────

def _find_claude() -> str:
    which = subprocess.run(["which", "claude"], capture_output=True, text=True)
    if which.returncode == 0:
        return which.stdout.strip()
    candidates = [
        "/opt/homebrew/bin/claude",
        str(Path.home() / ".local/bin/claude"),
    ]
    # nvm shims
    nvm_base = Path.home() / ".nvm/versions/node"
    if nvm_base.exists():
        for node_dir in nvm_base.iterdir():
            p = node_dir / "bin/claude"
            if p.is_file() and os.access(p, os.X_OK):
                candidates.append(str(p))
    for c in candidates:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    raise RuntimeError("Cannot find claude executable")


CLAUDE_BIN = _find_claude()
log.info("Using claude: %s", CLAUDE_BIN)

# ── Session store (in-memory, per chat_id) ────────────────────────────────────

_sessions: dict[int, str] = {}  # chat_id -> session_id

SESSION_FILE_TEMPLATE = "/tmp/claude-bot-session-{}"

def _load_session(chat_id: int) -> str | None:
    # Check in-memory first, then on-disk (compat with old bot.sh)
    if chat_id in _sessions:
        return _sessions[chat_id]
    p = Path(SESSION_FILE_TEMPLATE.format(chat_id))
    if p.exists():
        sid = p.read_text().strip()
        if sid:
            _sessions[chat_id] = sid
            return sid
    return None


def _save_session(chat_id: int, session_id: str) -> None:
    _sessions[chat_id] = session_id
    try:
        Path(SESSION_FILE_TEMPLATE.format(chat_id)).write_text(session_id)
    except OSError:
        pass


def _clear_session(chat_id: int) -> None:
    _sessions.pop(chat_id, None)
    p = Path(SESSION_FILE_TEMPLATE.format(chat_id))
    p.unlink(missing_ok=True)

# ── Markdown → HTML ───────────────────────────────────────────────────────────

def _table_to_pre(text: str) -> str:
    lines = text.split("\n")
    result: list[str] = []
    i = 0
    while i < len(lines):
        if (
            i + 1 < len(lines)
            and "|" in lines[i]
            and re.match(r"^[\s|:\-]+$", lines[i + 1])
        ):
            table_lines: list[str] = []
            while i < len(lines) and "|" in lines[i]:
                table_lines.append(lines[i])
                i += 1
            rows = [
                [c.strip() for c in tl.strip().strip("|").split("|")]
                for tl in table_lines
            ]
            rows = [r for r in rows if not all(re.match(r"^[\-:]+$", c) for c in r if c)]
            if rows:
                def esc(s: str) -> str:
                    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                rows = [[esc(c) for c in r] for r in rows]
                col_w = [
                    max((len(r[c]) if c < len(r) else 0) for r in rows)
                    for c in range(max(len(r) for r in rows))
                ]
                formatted: list[str] = []
                for ri, row in enumerate(rows):
                    cells = [
                        row[c].ljust(col_w[c]) if c < len(row) else " " * col_w[c]
                        for c in range(len(col_w))
                    ]
                    formatted.append("  ".join(cells))
                    if ri == 0:
                        formatted.append("  ".join("\u2500" * w for w in col_w))
                result.append("<pre>" + "\n".join(formatted) + "</pre>")
        else:
            result.append(lines[i])
            i += 1
    return "\n".join(result)


def md_to_html(text: str) -> str:
    text = _table_to_pre(text)
    parts = re.split(r"(```(?:[^\n]*)?\n[\s\S]*?```|<pre>[\s\S]*?</pre>)", text)
    result: list[str] = []
    for idx, part in enumerate(parts):
        if idx % 2 == 1:
            if part.startswith("<pre>"):
                result.append(part)
            else:
                m = re.match(r"```[^\n]*\n([\s\S]*?)```", part)
                code = m.group(1) if m else part
                code = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                result.append("<pre>" + code.rstrip("\n") + "</pre>")
        else:
            subs = re.split(r"(`[^`\n]+`)", part)
            processed: list[str] = []
            for j, sub in enumerate(subs):
                if j % 2 == 1:
                    code = sub[1:-1].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    processed.append("<code>" + code + "</code>")
                else:
                    s = sub.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    s = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", s)
                    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
                    s = re.sub(r"__(.+?)__", r"<u>\1</u>", s)
                    s = re.sub(r"\*([^\*\n]+)\*", r"<i>\1</i>", s)
                    s = re.sub(r"(?<![_\w])_([^_\n]+)_(?![_\w])", r"<i>\1</i>", s)
                    s = re.sub(r"~~(.+?)~~", r"<s>\1</s>", s)
                    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
                    s = re.sub(r"^#{1,6} +(.+)$", r"<b>\1</b>", s, flags=re.MULTILINE)
                    processed.append(s)
            result.append("".join(processed))
    return "".join(result)

# ── Message chunking ──────────────────────────────────────────────────────────

def _chunk_text(text: str, max_len: int = 4000) -> list[str]:
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

# ── File auto-sending ─────────────────────────────────────────────────────────

_PATH_RE = re.compile(
    r"(?:/Users/[^\s]+|/tmp/[^\s]+|/var/folders/[^\s]+)/\S+"
)
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


async def _send_files_in_text(bot, chat_id: int, text: str) -> str:
    """Detect file paths in text, send them, return cleaned text."""
    paths = _PATH_RE.findall(text)
    for raw_path in paths:
        # Strip trailing punctuation that might be part of sentence
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
                    await bot.send_document(chat_id=chat_id, document=fh, filename=p.name)
        except Exception as e:
            log.warning("Failed to send file %s: %s", path_str, e)
        # Remove path from text
        text = text.replace(raw_path, "").replace(path_str, "")
    return text.strip()

# ── Claude invocation ─────────────────────────────────────────────────────────

def _parse_claude_output(output: str) -> tuple[str, str]:
    """Parse stream-json output. Returns (reply_text, session_id)."""
    import json

    text_parts: list[str] = []
    session_id = ""
    is_error = False
    error_msg = ""

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            t = d.get("type", "")
            if t == "result":
                session_id = d.get("session_id", "") or session_id
                if d.get("is_error"):
                    is_error = True
                    errors = d.get("errors") or []
                    error_msg = (
                        errors[0] if errors else d.get("result") or "未知错误"
                    )
                else:
                    session_id = d.get("session_id", "")
                    r = d.get("result", "")
                    if r:
                        text_parts = [r]
            elif t == "assistant":
                msg = d.get("message", {})
                for block in msg.get("content", []):
                    if block.get("type") == "text":
                        txt = block.get("text", "")
                        if txt:
                            text_parts.append(txt)
        except Exception:
            pass

    if is_error:
        return f"(ಥ﹏ಥ) owie something broke: {error_msg}", ""  # don't persist error session
    if text_parts:
        return "\n\n".join(text_parts), session_id
    return "(・ω・)? brain empty... no thoughts", session_id


async def invoke_claude(chat_id: int, message: str) -> str:
    """Call claude CLI, return HTML-formatted reply."""
    session_id = _load_session(chat_id)

    env = {
        "HOME": os.environ["HOME"],
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
        "ANTHROPIC_BASE_URL": ANTHROPIC_BASE_URL,
        "CLAUDE_BIN": CLAUDE_BIN,
    }

    cmd = [
        CLAUDE_BIN,
        "--print", message,
        "--output-format", "stream-json",
        "--verbose",
        "--dangerously-skip-permissions",
    ]
    if session_id:
        cmd += ["--resume", session_id]

    log.info("[%d] Invoking claude (resume=%s) len=%d", chat_id, session_id or "none", len(message))

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={k: v for k, v in env.items() if v},
            stdin=asyncio.subprocess.DEVNULL,
        )
        stdout, stderr = await proc.communicate()
    except Exception as e:
        log.error("Claude invocation failed: %s", e)
        return f"(ಥ﹏ಥ) failed to start claude: {e}"

    output = stdout.decode("utf-8", errors="replace")
    log.info("[%d] exit=%d stdout=%d bytes stderr=%d bytes",
             chat_id, proc.returncode, len(output), len(stderr))
    if stderr:
        log.debug("[%d] stderr: %s", chat_id, stderr.decode("utf-8", errors="replace")[:300])

    raw_text, new_session_id = _parse_claude_output(output)
    if new_session_id:
        _save_session(chat_id, new_session_id)

    return md_to_html(raw_text)

# ── Send helpers ──────────────────────────────────────────────────────────────

async def send_reply(bot, chat_id: int, html: str) -> None:
    """Send (possibly chunked) HTML reply, with plain-text fallback."""
    # First scan for file paths and send them
    html = await _send_files_in_text(bot, chat_id, html)

    if not html:
        html = "(・_・;) uhh... nothing came out??"

    chunks = _chunk_text(html)
    for chunk in chunks:
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

# ── Access control ────────────────────────────────────────────────────────────

def _is_allowed_private(chat_id: int) -> bool:
    return chat_id == ALLOWED_CHAT_ID


def _is_allowed_group(chat_id: int) -> bool:
    return chat_id in ALLOWED_GROUP_IDS

# ── Command handlers ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not _is_allowed_private(chat_id):
        await update.message.reply_text("🙀 (｀Д´) nope nope nope!!")
        return
    await update.message.reply_text(
        "ฅ^•ﻌ•^ฅ nyaa~ hewo!!\n\n"
        "just throw tasks at me, i gotchu (๑•̀ㅂ•́)و✧\n"
        "• /reset — poof! fresh start ✧\n"
        "• /status — check if im alive lol\n"
        "• /sysinfo — system info\n"
        "• /stop — zzz time for kitty"
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, ctx)


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    import datetime
    chat_id = update.effective_chat.id
    if not _is_allowed_private(chat_id) and not _is_allowed_group(chat_id):
        await update.message.reply_text("🙀 (｀Д´) nope nope nope!!")
        return
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    import socket
    hostname = socket.gethostname()
    await update.message.reply_text(
        f"ᕙ(`▿´)ᕗ pawsitively operational!!\n"
        f"🖥 host: {hostname}\n"
        f"🕐 time: {now}"
    )


async def cmd_sysinfo(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    import datetime
    chat_id = update.effective_chat.id
    if not _is_allowed_private(chat_id):
        await update.message.reply_text("🙀 (｀Д´) nope nope nope!!")
        return

    def _run(cmd: list[str]) -> str:
        try:
            return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip().splitlines()[0]
        except Exception:
            return "unknown"

    claude_ver = _run([CLAUDE_BIN, "--version"])
    node_ver = _run(["node", "--version"])
    os_ver = _run(["sw_vers", "-productVersion"])
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await update.message.reply_text(
        f"🖥 <b>System Info</b>\n\n"
        f"🤖 Claude: {claude_ver}\n"
        f"📦 Node: {node_ver}\n"
        f"🍎 macOS: {os_ver}\n"
        f"📂 工作目录: {Path.home()}\n"
        f"⏱ 时间: {now}",
        parse_mode="HTML",
    )


async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not _is_allowed_private(chat_id):
        await update.message.reply_text("🙀 (｀Д´) nope nope nope!!")
        return
    _clear_session(chat_id)
    await update.message.reply_text("✧ _(´ཀ`」 ∠)_ poof!! who r u again lol")


async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not _is_allowed_private(chat_id):
        await update.message.reply_text("🙀 (｀Д´) nope nope nope!!")
        return
    await update.message.reply_text("💤 (=`ω´=) zzZZZzz... bai bai~")
    os._exit(0)

# ── Message handlers ──────────────────────────────────────────────────────────

_THINKING_MSGS = [
    "⏳ ꉂ ೭(˵¯̴͒ꇴ¯̴͒˵)౨ thinking noises...",
    "⚡ •̀.̫•́✧ ooh ooh on it!!",
    "🔥 (`∀´)Ψ lemme cook~",
    "🐾 ฅ(^ω^ฅ) purring intensifies...",
    "💭 ( •̀ᴗ•́ )و brb big brain time!!",
    "🌀 (°ロ°) !!! processing at max floof power",
    "✨ (ﾉ◕ヮ◕)ﾉ*:･ﾟ✧ manifesting ur answer rn",
    "🎲 ₍ᐢ•ﻌ•ᐢ₎ rolling the dice of intelligence...",
    "🍜 (づ｡◕‿‿◕｡)づ stirring the brain soup~",
    "🔮 (　˘ω˘ ) peering into the void for u",
    "🚀 ε=ε=ε=┌(;￣▽￣)┘ zooming thru knowledge base!!",
    "💡 (¬‿¬ ) ohhhh i have a GALAXY brain idea",
    "🐱 ฅ•ω•ฅ nyaa~ crunching the numbers",
    "🎯 (⌐■_■) target acquired. computing...",
    "🌊 〰️(oᴗo〰️) riding the wave of computation~",
]


async def _handle_message(chat_id: int, text: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    import random
    thinking = random.choice(_THINKING_MSGS)
    await update.message.reply_text(thinking)
    # Typing indicator
    await ctx.bot.send_chat_action(chat_id=chat_id, action=ChatActionEnum.TYPING)
    reply_html = await invoke_claude(chat_id, text)
    await send_reply(ctx.bot, chat_id, reply_html)


async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle private chat text messages."""
    chat_id = update.effective_chat.id
    if not _is_allowed_private(chat_id):
        await update.message.reply_text("🙀 (｀Д´) nope nope nope!!")
        return
    text = (update.message.text or "").strip()
    if not text:
        return
    log.info("[%d] text: %s", chat_id, text[:80])
    await _handle_message(chat_id, text, update, ctx)


async def media_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming photos and documents."""
    chat_id = update.effective_chat.id
    if not _is_allowed_private(chat_id) and not _is_allowed_group(chat_id):
        await update.message.reply_text("🙀 (｀Д´) nope nope nope!!")
        return

    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    caption = (update.message.caption or "").strip()
    file_refs: list[str] = []

    if update.message.photo:
        # Highest resolution = last element
        photo = update.message.photo[-1]
        tg_file = await ctx.bot.get_file(photo.file_id)
        dest = INBOX_DIR / f"{photo.file_id}.jpg"
        await tg_file.download_to_drive(dest)
        file_refs.append(f"[附件: {dest}]")
        log.info("[%d] photo -> %s", chat_id, dest)

    elif update.message.document:
        doc = update.message.document
        tg_file = await ctx.bot.get_file(doc.file_id)
        dest = INBOX_DIR / (doc.file_name or f"{doc.file_id}.bin")
        await tg_file.download_to_drive(dest)
        file_refs.append(f"[附件: {dest}]")
        log.info("[%d] document -> %s", chat_id, dest)

    if not file_refs:
        return

    prefix = "\n".join(file_refs)
    full_text = f"{prefix}\n{caption}" if caption else prefix
    await _handle_message(chat_id, full_text, update, ctx)


async def group_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle group chat text messages."""
    chat_id = update.effective_chat.id
    if not _is_allowed_group(chat_id):
        return  # Silent ignore for unauthorized groups

    message = update.message
    text = (message.text or "").strip()

    # Determine bot username for mention detection
    bot_username = (await ctx.bot.get_me()).username
    mentioned = f"@{bot_username}" in text
    starts_with_ask = text.startswith("/ask")

    if not mentioned and not starts_with_ask:
        return  # Silent ignore

    # Strip trigger prefix
    text = text.replace(f"@{bot_username}", "").strip()
    if text.startswith("/ask"):
        text = text[4:].strip()

    if not text:
        return

    log.info("[%d] group message: %s", chat_id, text[:80])
    await _handle_message(chat_id, text, update, ctx)

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("Claude Bot 启动 (python-telegram-bot 20.x)")
    log.info("ALLOWED_CHAT_ID=%d  ALLOWED_GROUP_IDS=%s", ALLOWED_CHAT_ID, ALLOWED_GROUP_IDS)

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("sysinfo", cmd_sysinfo))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("stop", cmd_stop))

    # Media (photos + documents)
    app.add_handler(
        MessageHandler(filters.PHOTO | filters.Document.ALL, media_handler)
    )

    # Private text
    app.add_handler(
        MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, text_handler)
    )

    # Group text
    app.add_handler(
        MessageHandler(filters.TEXT & filters.ChatType.GROUPS, group_handler)
    )

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
