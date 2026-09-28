"""Weekly review: gather the week's evidence into ``reviews/YYYY-Www.md``.

The scaffold is mechanical. The review itself is the person deciding, for each
stale loop and quiet project, whether to act, schedule, or drop it.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

from adzekit import daily, loops, projects
from adzekit.workspace import Workspace

_ARCHIVE_HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2})\s*$")


def week_of(day: date) -> tuple[str, date, date]:
    year, week, _ = day.isocalendar()
    monday = day - timedelta(days=day.weekday())
    return f"{year}-W{week:02d}", monday, monday + timedelta(days=6)


def _closed_loops(ws: Workspace, start: date, end: date) -> list[str]:
    if not ws.loops_archive.is_file():
        return []
    closed, in_week = [], False
    for line in ws.loops_archive.read_text(encoding="utf-8").splitlines():
        heading = _ARCHIVE_HEADING.match(line)
        if heading:
            in_week = start <= date.fromisoformat(heading[1]) <= end
        elif in_week and (loop := loops.parse(line)):
            closed.append(loop[0].title)
    return closed


def _bullets(items: list[str], empty: str) -> str:
    return "\n".join(f"- {item}" for item in items) if items else f"- _{empty}_"


def build(ws: Workspace, day: date) -> str:
    label, start, end = week_of(day)

    done: list[str] = []
    for offset in range(7):
        path = ws.daily_path(start + timedelta(days=offset))
        if path.is_file():
            done += daily.intentions(path.read_text(encoding="utf-8"))[1]

    stale_days = ws.setting("stale_loop_days")
    stale_loops = [
        f"[ ] {loop.title} — open {loop.age(day)}d → act / schedule / drop"
        for loop in loops.open_loops(ws)
        if (loop.age(day) or 0) > stale_days or loop.overdue(day)
    ]

    quiet_days = ws.setting("stale_project_days")
    quiet = [
        f"[ ] {p.slug} — last dated {p.last_touched or 'never'} → continue / backlog / archive"
        for p in projects.load(ws, "active", day)
        if p.last_touched is None or (day - p.last_touched).days > quiet_days
    ]

    return (
        f"# Review {label} ({start:%b %d} – {end:%b %d})\n\n"
        f"## Done\n{_bullets(list(dict.fromkeys(done)), 'no completed intentions recorded')}\n\n"
        f"## Loops closed\n{_bullets(_closed_loops(ws, start, end), 'none swept this week')}\n\n"
        f"## Decide: loops open more than {stale_days} days\n"
        f"{_bullets(stale_loops, 'nothing stale')}\n\n"
        f"## Decide: projects quiet more than {quiet_days} days\n"
        f"{_bullets(quiet, 'every active project moved')}\n\n"
        "## Next week\n- [ ] \n\n"
        "## Reflection\n"
    )


def write(ws: Workspace, day: date) -> tuple[Path, bool]:
    """Write the scaffold unless this week's review already exists."""
    label, _, _ = week_of(day)
    path = ws.reviews_dir / f"{label}.md"
    if path.is_file():
        return path, False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build(ws, day), encoding="utf-8")
    return path, True
