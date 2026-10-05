"""Read the records, and do the few edits that must be exact.

People and agents edit records directly. The code here only parses them and
performs the mechanical passes: create today's note, carry forward, sweep
ticked loops, and gather the week for review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from adzekit.shed import (
    LOOPS_ARCHIVE,
    LOOPS_FILE,
    PROJECTS_DIR,
    REVIEWS_DIR,
    Workspace,
    write_atomic,
)

LOOKBACK_DAYS = 14

_LOOP = re.compile(
    r"^- \[(?P<mark>[ xX])\] "
    r"(?:\((?P<size>[A-Z]{1,2})\)\s+)?"
    r"(?:\[(?P<opened>\d{4}-\d{2}-\d{2})\]\s+)?"
    r"(?P<title>.+?)"
    r"(?:\s+\((?P<due>\d{4}-\d{2}-\d{2})\))?\s*$"
)
_OPEN_TASK = re.compile(r"^- \[ \] (.+)$")
_DONE_TASK = re.compile(r"^- \[[xX]\] (.+)$")
_ISO_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_ARCHIVE_HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2})\s*$")


def _date(text: str | None) -> date | None:
    try:
        return date.fromisoformat(text) if text else None
    except ValueError:
        return None


# --- loops ---------------------------------------------------------------


@dataclass
class Loop:
    line: int
    done: bool
    title: str
    size: str = ""
    opened: date | None = None
    due: date | None = None

    def age(self, today: date) -> int | None:
        return (today - self.opened).days if self.opened else None

    def overdue(self, today: date) -> bool:
        return bool(self.due and self.due < today and not self.done)


def parse_loops(text: str) -> list[Loop]:
    """Top-level checkbox lines only; every other line is free text."""
    loops = []
    for i, line in enumerate(text.splitlines()):
        if m := _LOOP.match(line):
            loops.append(Loop(i, m["mark"] != " ", m["title"], m["size"] or "",
                              _date(m["opened"]), _date(m["due"])))
    return loops


def open_loops(ws: Workspace) -> list[Loop]:
    path = ws.path(LOOPS_FILE)
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    return [loop for loop in parse_loops(text) if not loop.done]


def sweep(ws: Workspace, today: date) -> list[str]:
    """Move ticked loops to the archive under today's heading."""
    path = ws.path(LOOPS_FILE)
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    done = {loop.line for loop in parse_loops("\n".join(lines)) if loop.done}
    if not done:
        return []
    swept = [lines[i] for i in sorted(done)]
    write_atomic(path, "\n".join(line for i, line in enumerate(lines) if i not in done) + "\n")

    archive_path = ws.path(LOOPS_ARCHIVE)
    archive = (archive_path.read_text(encoding="utf-8").rstrip()
               if archive_path.is_file() else "# Archived Loops")
    heading = f"## {today.isoformat()}"
    last = next((ln for ln in reversed(archive.splitlines()) if ln.startswith("## ")), None)
    if last != heading:
        archive += f"\n\n{heading}"
    write_atomic(archive_path, archive + "\n" + "\n".join(swept) + "\n")
    return swept


# --- daily notes ---------------------------------------------------------


def section(lines: list[str], name: str) -> tuple[int, int] | None:
    """``(heading_index, end_index)`` of ``## name``, or ``None``."""
    target = f"## {name}".lower()
    start = next((i for i, ln in enumerate(lines) if ln.strip().lower() == target), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return start, end


def intentions(text: str) -> tuple[list[str], list[str]]:
    """``(open, done)`` task text from the Intention section."""
    lines = text.splitlines()
    bounds = section(lines, "Intention")
    body = lines[bounds[0] + 1 : bounds[1]] if bounds else []
    return ([m[1] for ln in body if (m := _OPEN_TASK.match(ln))],
            [m[1] for ln in body if (m := _DONE_TASK.match(ln))])


@dataclass
class Today:
    path: Path
    created: bool
    carried: list[str] = field(default_factory=list)
    left_behind: list[str] = field(default_factory=list)
    swept: list[str] = field(default_factory=list)


def today(ws: Workspace, day: date) -> Today:
    """The morning pass: ensure today's note exists, carry forward, sweep loops."""
    result = Today(ws.daily_path(day), created=False, swept=sweep(ws, day))
    if result.path.is_file():
        return result

    unfinished: list[str] = []
    for back in range(1, LOOKBACK_DAYS + 1):
        prev = ws.daily_path(day - timedelta(days=back))
        if prev.is_file():
            unfinished = list(dict.fromkeys(intentions(prev.read_text(encoding="utf-8"))[0]))
            break
    cap = ws.setting("max_daily_tasks")
    result.carried, result.left_behind = unfinished[:cap], unfinished[cap:]
    result.created = True

    tasks = "".join(f"- [ ] {task}\n" for task in result.carried)
    heading = f"# {day.isoformat()} {day:%A}"
    write_atomic(result.path, f"{heading}\n\n## Intention\n{tasks}\n## Log\n\n## Reflection\n")
    return result


# --- projects ------------------------------------------------------------


@dataclass
class Project:
    slug: str
    title: str
    last_touched: date | None


def active_projects(ws: Workspace, today: date) -> list[Project]:
    projects = []
    for path in sorted(ws.path(PROJECTS_DIR).glob("*.md")):
        text = path.read_text(encoding="utf-8")
        first = text.split("\n", 1)[0]
        dates = [d for raw in _ISO_DATE.findall(text) if (d := _date(raw)) and d <= today]
        title = first[2:].strip() if first.startswith("# ") else path.stem
        projects.append(Project(path.stem, title, max(dates) if dates else None))
    return projects


# --- health and review ---------------------------------------------------


@dataclass
class Health:
    loops: list[Loop]
    overdue: list[Loop]
    stale: list[Loop]
    projects: list[Project]
    quiet: list[Project]


def health(ws: Workspace, today: date) -> Health:
    loops = open_loops(ws)
    stale_days, quiet_days = ws.setting("stale_loop_days"), ws.setting("stale_project_days")
    projects = active_projects(ws, today)
    return Health(
        loops=loops,
        overdue=[lp for lp in loops if lp.overdue(today)],
        stale=[lp for lp in loops if (lp.age(today) or 0) > stale_days or lp.overdue(today)],
        projects=projects,
        quiet=[p for p in projects
               if not p.last_touched or (today - p.last_touched).days > quiet_days],
    )


def week_of(day: date) -> tuple[str, date, date]:
    year, week, _ = day.isocalendar()
    monday = day - timedelta(days=day.weekday())
    return f"{year}-W{week:02d}", monday, monday + timedelta(days=6)


def _bullets(items: list[str], empty: str) -> str:
    return "\n".join(f"- {item}" for item in items) if items else f"- _{empty}_"


def build_review(ws: Workspace, day: date) -> str:
    label, start, end = week_of(day)
    done: list[str] = []
    for offset in range(7):
        path = ws.daily_path(start + timedelta(days=offset))
        if path.is_file():
            done += intentions(path.read_text(encoding="utf-8"))[1]

    closed, in_week = [], False
    archive = ws.path(LOOPS_ARCHIVE)
    for line in (archive.read_text(encoding="utf-8").splitlines() if archive.is_file() else []):
        if heading := _ARCHIVE_HEADING.match(line):
            in_week = start <= date.fromisoformat(heading[1]) <= end
        elif in_week and (parsed := parse_loops(line)):
            closed.append(parsed[0].title)

    h = health(ws, day)
    stale = [f"[ ] {lp.title} — open {lp.age(day)}d → act / schedule / drop" for lp in h.stale]
    quiet = [f"[ ] {p.slug} — last dated {p.last_touched or 'never'} → continue / archive"
             for p in h.quiet]
    return (
        f"# Review {label} ({start:%b %d} – {end:%b %d})\n\n"
        f"## Done\n{_bullets(list(dict.fromkeys(done)), 'no completed intentions recorded')}\n\n"
        f"## Loops closed\n{_bullets(closed, 'none swept this week')}\n\n"
        f"## Decide: stale loops\n{_bullets(stale, 'nothing stale')}\n\n"
        f"## Decide: quiet projects\n{_bullets(quiet, 'every active project moved')}\n\n"
        "## Next week\n- [ ] \n\n## Reflection\n"
    )


def write_review(ws: Workspace, day: date) -> tuple[Path, bool]:
    path = ws.path(f"{REVIEWS_DIR}/{week_of(day)[0]}.md")
    if path.is_file():
        return path, False
    write_atomic(path, build_review(ws, day))
    return path, True
