"""Append a session line to today's daily-note `> Sessions:` footer.

The footer convention from backbone-spec/schema.md:

    > Sessions:
    > - claude-code:abc12345 08:14-08:42 /telegram
    > - claude-code:def67890 11:02-11:05 /capture

Each agent invocation that touches the shed appends one line. New entries
go at the END of the footer (chronological), so the footer reads top-to-
bottom in the order things happened.

If today's daily note doesn't exist yet (the user hasn't run /daily-start),
the appender silently no-ops — there's no place to put the line. The
gateway logs the skip but doesn't fail the user-facing exchange.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path


_FOOTER_HEADING = "> Sessions:"


def format_session_line(
    *,
    runtime: str,
    session_id: str,
    start: datetime,
    end: datetime,
    command: str,
    draft_rel: Path | None = None,
) -> str:
    """Build the one-line entry. session_id is truncated to first 8 chars."""
    short_id = session_id[:8] if session_id else "?"
    start_str = start.strftime("%H:%M")
    end_str = end.strftime("%H:%M")
    line = f"> - {runtime}:{short_id} {start_str}-{end_str} {command}"
    if draft_rel is not None:
        line += f" -> {draft_rel}"
    return line


def append_session_line(
    shed: Path,
    line: str,
    *,
    target_date: date | None = None,
) -> bool:
    """Append `line` to today's daily-note Sessions footer.

    Returns True if the line was appended, False if today's note doesn't
    exist (silent no-op so the gateway doesn't crash on a first-message-
    of-the-day scenario before daily-start runs).
    """
    target_date = target_date or date.today()
    daily_path = shed / "daily" / f"{target_date.isoformat()}.md"
    if not daily_path.exists():
        return False

    text = daily_path.read_text(encoding="utf-8")
    new_text = _insert_session_line(text, line)
    daily_path.write_text(new_text, encoding="utf-8")
    return True


def _insert_session_line(text: str, line: str) -> str:
    """Insert `line` at the end of the existing Sessions footer, or create
    a new footer block at end-of-file if none exists.

    Lives as a pure function so it's trivially unit-testable.
    """
    if _FOOTER_HEADING not in text:
        # No footer yet — append one.
        body = text.rstrip("\n")
        return f"{body}\n\n{_FOOTER_HEADING}\n{line}\n"

    # Footer exists. Find the end of the contiguous `> - ` lines that follow
    # the heading and insert there. The "end" is the first line that doesn't
    # start with `> `.
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    inserted = False
    i = 0
    while i < len(lines):
        cur = lines[i]
        out.append(cur)
        if not inserted and cur.rstrip() == _FOOTER_HEADING:
            # Walk forward over the existing block (lines starting with `> `).
            j = i + 1
            while j < len(lines) and lines[j].startswith(">"):
                out.append(lines[j])
                j += 1
            # Inject our new line just before the first non-`> ` line (or EOF).
            new_line = line if line.endswith("\n") else line + "\n"
            out.append(new_line)
            inserted = True
            i = j
            continue
        i += 1

    if not inserted:
        # Shouldn't happen given the early `in` check, but be defensive.
        return text.rstrip("\n") + f"\n\n{_FOOTER_HEADING}\n{line}\n"

    return "".join(out)


# Backward-compat regex used by tests/scripts that want to detect the block.
SESSION_LINE_RE = re.compile(
    r"^>\s+-\s+(?P<runtime>\S+):(?P<sid>\S+)\s+"
    r"(?P<start>\d{2}:\d{2})-(?P<end>\d{2}:\d{2})\s+"
    r"(?P<command>\S+)"
    r"(?:\s+->\s+(?P<draft>\S+))?\s*$"
)
