"""Claude CLI invocation and output parsing."""

import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path

from . import session
from .config import cfg
from .formatter import md_to_html

log = logging.getLogger("claude_bot.claude")

_claude_bin: str | None = None


def _find_claude() -> str:
    which = subprocess.run(["which", "claude"], capture_output=True, text=True)
    if which.returncode == 0:
        return which.stdout.strip()
    candidates = [
        "/opt/homebrew/bin/claude",
        str(Path.home() / ".local/bin/claude"),
    ]
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


def get_bin() -> str:
    global _claude_bin
    if _claude_bin is None:
        _claude_bin = _find_claude()
        log.info("Using claude: %s", _claude_bin)
    return _claude_bin


def parse_output(output: str) -> tuple[str, str]:
    """Parse stream-json output. Returns (reply_text, session_id)."""
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
        return f"(ಥ﹏ಥ) owie something broke: {error_msg}", ""
    if text_parts:
        return "\n\n".join(text_parts), session_id
    return "(・ω・)? brain empty... no thoughts", session_id


async def invoke(chat_id: int, message: str) -> str:
    """Call claude CLI and return HTML-formatted reply (with retry)."""
    session_id = session.load(chat_id)
    env = cfg.claude_env()

    cmd = [
        get_bin(),
        "--print", message,
        "--output-format", "stream-json",
        "--verbose",
    ]
    if cfg.claude_skip_permissions:
        cmd.append("--dangerously-skip-permissions")
    if session_id:
        cmd += ["--resume", session_id]

    max_attempts = cfg.claude_max_retries + 1
    backoff = [1, 3, 5]
    last_error = ""

    for attempt in range(max_attempts):
        log.info(
            "[%d] Invoking claude (resume=%s) len=%d attempt=%d/%d",
            chat_id, session_id or "none", len(message),
            attempt + 1, max_attempts,
        )
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                stdin=asyncio.subprocess.DEVNULL,
            )
            stdout, stderr = await proc.communicate()
        except Exception as e:
            last_error = str(e)
            log.error("Claude invocation failed: %s", e)
            if attempt < max_attempts - 1:
                delay = backoff[min(attempt, len(backoff) - 1)]
                log.info("[%d] Retrying in %ds...", chat_id, delay)
                await asyncio.sleep(delay)
                continue
            return f"(ಥ﹏ಥ) failed to start claude: {e}"

        output = stdout.decode("utf-8", errors="replace")
        log.info(
            "[%d] exit=%d stdout=%d bytes stderr=%d bytes",
            chat_id, proc.returncode, len(output), len(stderr),
        )
        if stderr:
            log.debug(
                "[%d] stderr: %s",
                chat_id, stderr.decode("utf-8", errors="replace")[:300],
            )

        if proc.returncode != 0 and attempt < max_attempts - 1:
            last_error = f"exit code {proc.returncode}"
            delay = backoff[min(attempt, len(backoff) - 1)]
            log.warning(
                "[%d] Non-zero exit (%d), retrying in %ds...",
                chat_id, proc.returncode, delay,
            )
            await asyncio.sleep(delay)
            continue

        raw_text, new_session_id = parse_output(output)
        if new_session_id:
            session.save(chat_id, new_session_id)
        return md_to_html(raw_text)

    return f"(ಥ﹏ಥ) claude failed after {max_attempts} attempts: {last_error}"
