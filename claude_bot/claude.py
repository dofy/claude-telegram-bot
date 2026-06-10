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


# Curated fallback list used when the router can't be reached.
FALLBACK_MODELS = [
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-haiku-4-5",
]


def fetch_models(timeout: float = 5.0) -> tuple[list[str], str]:
    """Fetch Claude-family model ids from the router's /v1/models endpoint.

    Returns (model_ids, error). On success error is "". On failure the
    fallback list is returned alongside a short error message.
    """
    import json as _json
    import urllib.request

    base = os.environ.get("ANTHROPIC_BASE_URL", "").rstrip("/")
    if not base:
        return list(FALLBACK_MODELS), "ANTHROPIC_BASE_URL not set"

    url = f"{base}/v1/models"
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    req = urllib.request.Request(url)
    if key:
        req.add_header("x-api-key", key)
    req.add_header("anthropic-version", "2023-06-01")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = _json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        log.warning("fetch_models failed: %s", e)
        return list(FALLBACK_MODELS), str(e)

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return list(FALLBACK_MODELS), "unexpected response format"

    ids = [
        m["id"]
        for m in data
        if isinstance(m, dict) and isinstance(m.get("id"), str)
    ]
    claude_ids = sorted(
        i for i in ids
        if "claude" in i.lower() or "anthropic" in i.lower()
    )
    if not claude_ids:
        return list(FALLBACK_MODELS), "no Claude models found"
    return claude_ids, ""


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


def _build_cmd(chat_id: int, message: str, model: str, session_id: str | None) -> list[str]:
    """Assemble the claude CLI command list."""
    sys_prompt = cfg.get_system_prompt(chat_id)
    cmd = [
        get_bin(),
        "--print", message,
        "--output-format", "stream-json",
        "--verbose",
        "--model", model,
    ]
    if cfg.claude_skip_permissions:
        cmd.append("--dangerously-skip-permissions")
    if session_id:
        cmd += ["--resume", session_id]
    if sys_prompt:
        cmd += ["--append-system-prompt", sys_prompt]
    return cmd


async def invoke(chat_id: int, message: str, model: str | None = None) -> tuple[str, float]:
    """Call claude CLI and return (HTML-formatted reply, elapsed_seconds)."""
    import time as _time

    session_id = session.load(chat_id)
    env = cfg.claude_env()
    effective_model = model or cfg.get_chat_model(chat_id)
    cmd = _build_cmd(chat_id, message, effective_model, session_id)

    max_attempts = cfg.claude_max_retries + 1
    backoff = [1, 3, 5]
    last_error = ""
    t0 = _time.monotonic()

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
            elapsed = _time.monotonic() - t0
            return f"(ಥ﹏ಥ) failed to start claude: {e}", elapsed

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
        elapsed = _time.monotonic() - t0
        return md_to_html(raw_text), elapsed

    elapsed = _time.monotonic() - t0
    return f"(ಥ﹏ಥ) claude failed after {max_attempts} attempts: {last_error}", elapsed


async def invoke_stream(
    chat_id: int,
    message: str,
    model: str | None = None,
) -> "AsyncGenerator[str, None]":
    """Stream assistant text tokens as they arrive from claude CLI.

    Yields incremental plain-text chunks. The caller is responsible for
    formatting / sending. After the generator is exhausted, the session is
    saved via side-effect inside parse_output_stream().
    """
    import time as _time
    from typing import AsyncGenerator  # noqa: F401 — for the return-type hint

    session_id = session.load(chat_id)
    env = cfg.claude_env()
    effective_model = model or cfg.get_chat_model(chat_id)
    cmd = _build_cmd(chat_id, message, effective_model, session_id)

    log.info(
        "[%d] invoke_stream (resume=%s) len=%d",
        chat_id, session_id or "none", len(message),
    )

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        stdin=asyncio.subprocess.DEVNULL,
    )

    assert proc.stdout is not None
    accumulated = ""

    async for raw_line in proc.stdout:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue

        t = d.get("type", "")
        if t == "assistant":
            for block in d.get("message", {}).get("content", []):
                if block.get("type") == "text":
                    chunk = block.get("text", "")
                    if chunk:
                        accumulated += chunk
                        yield chunk
        elif t == "result":
            new_sid = d.get("session_id", "")
            if new_sid:
                session.save(chat_id, new_sid)

    await proc.wait()
    log.info("[%d] invoke_stream done exit=%d", chat_id, proc.returncode)
