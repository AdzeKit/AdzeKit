"""Loop lifecycle: capture, track, close.

Principle 2: Close Every Loop. Every commitment gets a response
within 24 hours. A loop stays open until explicitly closed with evidence.

Loop lifecycle:
  1. Capture: added to active.md
  2. Track: system surfaces approaching deadlines
  3. Close: human sends the thing; loop moves to archive.md

Loops mirror the project lifecycle: active / backlog / archive.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from adzekit.config import Settings, get_settings
from adzekit.models import Loop
from adzekit.parser import format_loop, format_loops, parse_loops


def _atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically via temp file + rename."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.rename(path)


def _loops_match(a: Loop, b: Loop) -> bool:
    """Match loops by title + creation date (not title alone)."""
    return a.title == b.title and a.date == b.date


def get_active_loops(settings: Settings | None = None) -> list[Loop]:
    """Read all loops from active.md."""
    settings = settings or get_settings()
    text = settings.loops_active.read_text(encoding="utf-8")
    return parse_loops(text)


def get_backlog_loops(settings: Settings | None = None) -> list[Loop]:
    """Read all loops from backlog.md."""
    settings = settings or get_settings()
    if not settings.loops_backlog.exists():
        return []
    text = settings.loops_backlog.read_text(encoding="utf-8")
    return parse_loops(text)


def _is_duplicate(loop: Loop, existing: list[Loop]) -> bool:
    """Check if a loop with the same title and date already exists."""
    return any(_loops_match(loop, e) for e in existing)


def add_loop(loop: Loop, settings: Settings | None = None) -> bool:
    """Append a new loop to active.md.

    Returns False if a duplicate (same title + date) already exists.
    """
    settings = settings or get_settings()
    current_text = settings.loops_active.read_text(encoding="utf-8")
    existing = parse_loops(current_text)
    if _is_duplicate(loop, existing):
        return False
    current_text += "\n" + format_loop(loop)
    _atomic_write(settings.loops_active, current_text)
    return True


def add_backlog_loop(loop: Loop, settings: Settings | None = None) -> bool:
    """Append a new loop to backlog.md.

    Returns False if a duplicate (same title + date) already exists.
    """
    settings = settings or get_settings()
    path = settings.loops_backlog
    if not path.exists():
        path.write_text("# Backlog Loops\n", encoding="utf-8")
    current_text = path.read_text(encoding="utf-8")
    existing = parse_loops(current_text)
    if _is_duplicate(loop, existing):
        return False
    current_text += "\n" + format_loop(loop)
    _atomic_write(path, current_text)
    return True


def close_loop(
    title: str,
    settings: Settings | None = None,
    *,
    loop_date: date | None = None,
) -> bool:
    """Move a loop from active.md to the current week's archive file.

    Matches by title + date when loop_date is provided, title-only otherwise.
    Returns True if the loop was found and closed.
    """
    settings = settings or get_settings()
    loops = get_active_loops(settings)
    to_close = None
    remaining = []

    for loop in loops:
        matched = loop.title == title and to_close is None
        if matched and loop_date is not None:
            matched = loop.date == loop_date
        if matched and to_close is None:
            to_close = loop
            to_close.status = "Closed"
        else:
            remaining.append(loop)

    if to_close is None:
        return False

    _atomic_write(
        settings.loops_active,
        "# Active Loops\n\n" + format_loops(remaining),
    )

    today = date.today()
    week_num = today.isocalendar()[1]
    archive_file = settings.loops_archive_dir / f"{today.year}-W{week_num:02d}.md"
    if archive_file.exists():
        existing = archive_file.read_text(encoding="utf-8")
    else:
        existing = f"# Archived Loops -- {today.year} Week {week_num}\n\n"
    existing += format_loop(to_close)
    _atomic_write(archive_file, existing)

    return True


def sweep_closed(settings: Settings | None = None) -> list[Loop]:
    """Move all [x] loops from active.md to archive.md.

    Uses atomic writes to prevent data loss if interrupted.
    Returns the list of loops that were swept.
    """
    settings = settings or get_settings()
    loops = get_active_loops(settings)
    still_active = []
    swept = []

    today = date.today()
    for loop in loops:
        if loop.status.lower() == "closed":
            loop.date = today
            swept.append(loop)
        else:
            still_active.append(loop)

    if not swept:
        return []

    active_content = "# Active Loops\n\n" + format_loops(still_active) + "\n"
    archive_path = settings.loops_dir / "archive.md"

    if archive_path.exists():
        archive_existing = archive_path.read_text(encoding="utf-8").rstrip()
    else:
        archive_existing = "# Archived Loops"
    archive_content = archive_existing + "\n" + format_loops(swept) + "\n"

    _atomic_write(settings.loops_active, active_content)
    _atomic_write(archive_path, archive_content)

    return swept


def get_overdue_loops(settings: Settings | None = None) -> list[Loop]:
    """Return active loops that are past their due date."""
    settings = settings or get_settings()
    today = date.today()
    return [l for l in get_active_loops(settings) if l.due and l.due < today]


def get_approaching_sla(settings: Settings | None = None) -> list[Loop]:
    """Return active loops nearing the 24-hour SLA window."""
    settings = settings or get_settings()
    cutoff = date.today() - timedelta(hours=settings.loop_sla_hours)
    return [
        l for l in get_active_loops(settings)
        if l.date <= cutoff and l.status.lower() != "closed"
    ]


def loop_stats(settings: Settings | None = None) -> dict:
    """Summary statistics for loops."""
    settings = settings or get_settings()
    active = get_active_loops(settings)
    backlog = get_backlog_loops(settings)
    overdue = get_overdue_loops(settings)
    approaching = get_approaching_sla(settings)
    return {
        "active": len(active),
        "backlog": len(backlog),
        "overdue": len(overdue),
        "approaching_sla": len(approaching),
    }
