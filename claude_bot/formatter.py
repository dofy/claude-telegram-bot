"""Markdown → Telegram HTML converter."""

import re


def _html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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
            rows = [
                r
                for r in rows
                if not all(re.match(r"^[\-:]+$", c) for c in r if c)
            ]
            if rows:
                rows = [[_html_escape(c) for c in r] for r in rows]
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
                result.append("<pre>" + _html_escape(code).rstrip("\n") + "</pre>")
        else:
            subs = re.split(r"(`[^`\n]+`)", part)
            processed: list[str] = []
            for j, sub in enumerate(subs):
                if j % 2 == 1:
                    processed.append("<code>" + _html_escape(sub[1:-1]) + "</code>")
                else:
                    s = _html_escape(sub)
                    s = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", s)
                    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
                    s = re.sub(r"__(.+?)__", r"<u>\1</u>", s)
                    s = re.sub(r"\*([^\*\n]+)\*", r"<i>\1</i>", s)
                    s = re.sub(r"(?<![_\w])_([^_\n]+)_(?![_\w])", r"<i>\1</i>", s)
                    s = re.sub(r"~~(.+?)~~", r"<s>\1</s>", s)
                    s = re.sub(
                        r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s
                    )
                    s = re.sub(
                        r"^#{1,6} +(.+)$", r"<b>\1</b>", s, flags=re.MULTILINE
                    )
                    processed.append(s)
            result.append("".join(processed))
    return "".join(result)
