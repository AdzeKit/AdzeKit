"""Daily notes: ``daily/YYYY-MM-DD.md`` with Intention, Log, and Reflection."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from adzekit.workspace import Workspace, write_atomic

LOOKBACK_DAYS = 14

_OPEN_TASK = re.compile(r"^- \[ \] (.+)$")
_DONE_TASK = re.compile(r"^- \[[xX]\] (.+)$")


def section(lines: list[str], name: str) -> tuple[int, int] | None:
    """Return ``(heading_index, end_index)`` for ``## name``, or ``None``."""
    target = f"## {name}".lower()
    start = next((i for i, line in enumerate(lines) if line.strip().lower() == target), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return start, end


def intentions(text: str) -> tuple[list[str], list[str]]:
    """Return ``(open, done)`` task text from the Intention section."""
    lines = text.splitlines()
    bounds = section(lines, "Intention")
    if not bounds:
        return [], []
    body = lines[bounds[0] + 1 : bounds[1]]
    open_ = [m[1] for line in body if (m := _OPEN_TASK.match(line))]
    done = [m[1] for line in body if (m := _DONE_TASK.match(line))]
    return open_, done


def previous_note(ws: Workspace, day: date) -> Path | None:
    for back in range(1, LOOKBACK_DAYS + 1):
        path = ws.daily_path(day - timedelta(days=back))
        if path.is_file():
            return path
    return None


@dataclass
class Today:
    path: Path
    created: bool
    carried: list[str] = field(default_factory=list)
    left_behind: list[str] = field(default_factory=list)


def today(ws: Workspace, day: date) -> Today:
    """Create the day's note if missing, carrying forward unfinished intentions."""
    path = ws.daily_path(day)
    if path.is_file():
        return Today(path, created=False)

    unfinished: list[str] = []
    prev = previous_note(ws, day)
    if prev:
        unfinished = list(dict.fromkeys(intentions(prev.read_text(encoding="utf-8"))[0]))
    cap = ws.setting("max_daily_tasks")
    carried, left_behind = unfinished[:cap], unfinished[cap:]

    tasks = "".join(f"- [ ] {task}\n" for task in carried)
    text = f"# {day.isoformat()} {day:%A}\n\n## Intention\n{tasks}\n## Log\n\n## Reflection\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return Today(path, created=True, carried=carried, left_behind=left_behind)


def log(ws: Workspace, entry: str, day: date) -> Path:
    """Append ``- entry`` to the end of today's Log section."""
    path = today(ws, day).path
    lines = path.read_text(encoding="utf-8").splitlines()
    bounds = section(lines, "Log")
    if bounds is None:
        lines += ["", "## Log", f"- {entry}"]
    else:
        insert = bounds[1]
        while insert > bounds[0] + 1 and not lines[insert - 1].strip():
            insert -= 1
        lines.insert(insert, f"- {entry}")
        if insert + 1 < len(lines) and lines[insert + 1].startswith("## "):
            lines.insert(insert + 1, "")
    write_atomic(path, "\n".join(lines) + "\n")
    return path
