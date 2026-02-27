"""Loop lifecycle: capture, track, close.

Principle 2: Close Every Loop. Every commitment gets a response
within 24 hours. A loop stays open until explicitly closed with evidence.

Loop lifecycle:
  1. Capture: added to open.md
  2. Track: system surfaces approaching deadlines
  3. Close: human sends the thing; loop moves to closed/YYYY-WW.md
"""

from datetime import date, timedelta

from adzekit.config import Settings, get_settings
from adzekit.models import Loop
from adzekit.parser import format_loop, format_loops, parse_loops


def get_open_loops(settings: Settings | None = None) -> list[Loop]:
    """Read all loops from open.md."""
    settings = settings or get_settings()
    text = settings.loops_open.read_text(encoding="utf-8")
    return parse_loops(text)


def add_loop(loop: Loop, settings: Settings | None = None) -> None:
    """Append a new loop to open.md."""
    settings = settings or get_settings()
    current = settings.loops_open.read_text(encoding="utf-8")
    current += "\n" + format_loop(loop)
    settings.loops_open.write_text(current, encoding="utf-8")


def close_loop(title: str, settings: Settings | None = None) -> bool:
    """Move a loop from open.md to the current week's closed file.

    Returns True if the loop was found and closed.
    """
    settings = settings or get_settings()
    loops = get_open_loops(settings)
    to_close = None
    remaining = []

    for loop in loops:
        if loop.title == title and to_close is None:
            to_close = loop
            to_close.status = "Closed"
        else:
            remaining.append(loop)

    if to_close is None:
        return False

    # Rewrite open.md without the closed loop
    settings.loops_open.write_text(
        "# Open Loops\n\n" + format_loops(remaining),
        encoding="utf-8",
    )

    # Append to closed/YYYY-WW.md
    today = date.today()
    week_num = today.isocalendar()[1]
    closed_file = settings.loops_closed_dir / f"{today.year}-W{week_num:02d}.md"
    if closed_file.exists():
        existing = closed_file.read_text(encoding="utf-8")
    else:
        existing = f"# Closed Loops -- {today.year} Week {week_num}\n\n"
    existing += format_loop(to_close)
    closed_file.write_text(existing, encoding="utf-8")

    return True


def sweep_closed(settings: Settings | None = None) -> list[Loop]:
    """Move all [x] loops from open.md to closed.md.

    Returns the list of loops that were swept.
    """
    settings = settings or get_settings()
    loops = get_open_loops(settings)
    still_open = []
    swept = []

    today = date.today()
    for loop in loops:
        if loop.status.lower() == "closed":
            loop.date = today  # stamp the closed date
            swept.append(loop)
        else:
            still_open.append(loop)

    if not swept:
        return []

    # Rewrite open.md with only open loops
    open_content = "# Open Loops\n\n" + format_loops(still_open) + "\n"
    settings.loops_open.write_text(open_content, encoding="utf-8")

    # Append swept loops to closed.md
    closed_path = settings.loops_dir / "closed.md"
    if closed_path.exists():
        existing = closed_path.read_text(encoding="utf-8").rstrip()
    else:
        existing = "# Closed Loops"
    existing += "\n" + format_loops(swept) + "\n"
    closed_path.write_text(existing, encoding="utf-8")

    return swept


def get_overdue_loops(settings: Settings | None = None) -> list[Loop]:
    """Return loops that are past their due date."""
    settings = settings or get_settings()
    today = date.today()
    return [l for l in get_open_loops(settings) if l.due and l.due < today]


def get_approaching_sla(settings: Settings | None = None) -> list[Loop]:
    """Return loops nearing the 24-hour SLA window."""
    settings = settings or get_settings()
    cutoff = date.today() - timedelta(hours=settings.loop_sla_hours)
    return [
        l for l in get_open_loops(settings)
        if l.date <= cutoff and l.status.lower() != "closed"
    ]


def loop_stats(settings: Settings | None = None) -> dict:
    """Summary statistics for loops."""
    settings = settings or get_settings()
    open_loops = get_open_loops(settings)
    overdue = get_overdue_loops(settings)
    approaching = get_approaching_sla(settings)
    return {
        "open": len(open_loops),
        "overdue": len(overdue),
        "approaching_sla": len(approaching),
    }
