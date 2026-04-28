"""Mechanical daily-start and daily-close.

Pure Python implementations of the morning and evening rituals.
No LLM required -- these handle the deterministic parts:
  - daily-start: carry yesterday's context into today's note
  - daily-close: append reflection line, sweep closed loops
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

from adzekit.config import Settings, get_settings
from adzekit.models import DailyNote, Loop, Task
from adzekit.modules.loops import get_active_loops, sweep_closed
from adzekit.parser import parse_daily_note

_TASK_RE = re.compile(r"^-\s+\[([ xX])\]\s+(.+)$")


def _atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically via temp file + rename."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.rename(path)


def _find_previous_note(
    target_date: date,
    settings: Settings,
    lookback: int = 3,
) -> DailyNote | None:
    """Load the most recent daily note before target_date.

    Walks back up to ``lookback`` days to handle weekends and gaps.
    """
    for i in range(1, lookback + 1):
        prev_date = target_date - timedelta(days=i)
        path = settings.daily_dir / f"{prev_date.isoformat()}.md"
        if path.exists():
            text = path.read_text(encoding="utf-8")
            return parse_daily_note(text, prev_date)
    return None


def _filter_overdue(loops: list[Loop], target_date: date) -> list[Loop]:
    """Loops with due date before target_date."""
    return [
        loop for loop in loops
        if loop.due and loop.due < target_date and loop.status.lower() != "closed"
    ]


def _filter_due_today(loops: list[Loop], target_date: date) -> list[Loop]:
    """Loops with due date equal to target_date."""
    return [
        loop for loop in loops
        if loop.due and loop.due == target_date and loop.status.lower() != "closed"
    ]


def _filter_due_tomorrow(loops: list[Loop], target_date: date) -> list[Loop]:
    """Loops with due date equal to target_date + 1."""
    tomorrow = target_date + timedelta(days=1)
    return [
        loop for loop in loops
        if loop.due and loop.due == tomorrow and loop.status.lower() != "closed"
    ]


def _loop_to_task_line(loop: Loop, annotation: str = "") -> str:
    """Format a loop as a task line for the daily note."""
    parts = ["- [ ]"]
    if loop.size:
        parts.append(f"({loop.size})")
    parts.append(loop.title)
    if annotation:
        parts.append(f" <- {annotation}")
    return " ".join(parts)


def _build_task_list(
    overdue: list[Loop],
    due_today: list[Loop],
    tomorrow_items: list[str],
    carried: list[Task],
    max_tasks: int = 5,
) -> list[str]:
    """Build a ranked, de-duplicated task list capped at max_tasks.

    Priority: overdue > due-today > tomorrow items > carried intentions.
    """
    lines: list[str] = []
    seen_titles: set[str] = set()

    for loop in overdue:
        if len(lines) >= max_tasks:
            break
        if loop.title.lower() not in seen_titles:
            lines.append(_loop_to_task_line(loop, "OVERDUE"))
            seen_titles.add(loop.title.lower())

    for loop in due_today:
        if len(lines) >= max_tasks:
            break
        if loop.title.lower() not in seen_titles:
            lines.append(_loop_to_task_line(loop, "due today"))
            seen_titles.add(loop.title.lower())

    for item in tomorrow_items:
        if len(lines) >= max_tasks:
            break
        if item.lower() not in seen_titles:
            lines.append(f"- [ ] {item}")
            seen_titles.add(item.lower())

    for task in carried:
        if len(lines) >= max_tasks:
            break
        if task.description.lower() not in seen_titles:
            lines.append(f"- [ ] {task.description}")
            seen_titles.add(task.description.lower())

    return lines


# ---------------------------------------------------------------------------
# daily-start
# ---------------------------------------------------------------------------


def _try_sync_pull(settings: Settings) -> bool:
    """Pull workbench from rclone remote if configured. Returns True on success."""
    if not settings.has_rclone_remote:
        return False
    try:
        settings.sync_workbench()
        return True
    except Exception:
        return False


def _try_sync_push(settings: Settings) -> bool:
    """Push workbench to rclone remote if configured. Returns True on success."""
    if not settings.has_rclone_remote:
        return False
    try:
        settings.push_workbench()
        return True
    except Exception:
        return False


def _refresh_tag_snippets(settings: Settings) -> bool:
    """Regenerate Cursor autocomplete snippets. Returns True on success."""
    try:
        from adzekit.modules.tags import generate_cursor_snippets
        generate_cursor_snippets(settings)
        return True
    except Exception:
        return False


def daily_start(
    target_date: date | None = None,
    settings: Settings | None = None,
) -> tuple[Path | None, dict]:
    """Create today's daily note from yesterday's context and active loops.

    Also pulls the workbench (stock + drafts) from rclone if configured,
    and refreshes Cursor tag autocomplete snippets.

    Returns (path_or_None, summary_dict).
    If the note already exists, returns (None, {"already_exists": True, ...}).
    """
    settings = settings or get_settings()
    target_date = target_date or date.today()
    weekday = target_date.strftime("%A")
    iso = target_date.isoformat()
    path = settings.daily_dir / f"{iso}.md"

    # Sync before building the note so carried context is up to date
    synced = _try_sync_pull(settings)
    tags_refreshed = _refresh_tag_snippets(settings)

    if path.exists():
        return None, {
            "already_exists": True,
            "date": iso,
            "synced": synced,
            "tags_refreshed": tags_refreshed,
        }

    # Load previous note
    prev = _find_previous_note(target_date, settings)
    carried = [t for t in prev.intentions if not t.done] if prev else []
    tomorrow_items = prev.tomorrow if prev else []

    # Load loops
    loops = get_active_loops(settings)
    overdue = _filter_overdue(loops, target_date)
    due_today = _filter_due_today(loops, target_date)

    # Build task list
    task_lines = _build_task_list(
        overdue, due_today, tomorrow_items, carried,
    )

    # Format the note in existing section format
    intention_block = "\n".join(task_lines) if task_lines else "- [ ] Top priority:"
    content = f"""# {iso} {weekday}

## Morning: Intention
{intention_block}

## Log

## Evening: Reflection
- **Finished:**
- **Blocked:**
- **Tomorrow:**
"""
    _atomic_write(path, content)

    summary = {
        "date": iso,
        "weekday": weekday,
        "proposed_tasks": len(task_lines),
        "overdue_count": len(overdue),
        "due_today_count": len(due_today),
        "carried_count": len(carried),
        "tomorrow_count": len(tomorrow_items),
        "active_loops_total": len(loops),
        "synced": synced,
        "tags_refreshed": tags_refreshed,
    }
    return path, summary


# ---------------------------------------------------------------------------
# daily-close
# ---------------------------------------------------------------------------


def _count_items(text: str) -> tuple[int, int, int]:
    """Count (done, open, log_entries) in a daily note's raw text."""
    done = 0
    open_count = 0
    log_entries = 0
    in_log = False

    for line in text.splitlines():
        stripped = line.strip()

        if stripped.lower() == "## log":
            in_log = True
            continue
        if stripped.startswith("## "):
            in_log = False

        m = _TASK_RE.match(stripped)
        if m:
            if m.group(1).lower() == "x":
                done += 1
            else:
                open_count += 1
        elif in_log and stripped.startswith("- "):
            log_entries += 1

    return done, open_count, log_entries


def _build_tomorrow_suggestion(
    loops: list[Loop],
    target_date: date,
    open_tasks: list[str],
) -> str:
    """Build a short tomorrow suggestion string."""
    suggestions: list[str] = []

    due_tomorrow = _filter_due_tomorrow(loops, target_date)
    if due_tomorrow:
        suggestions.append(due_tomorrow[0].title)

    overdue = _filter_overdue(loops, target_date)
    if overdue and (not suggestions or overdue[0].title != suggestions[0]):
        suggestions.append(overdue[0].title)

    if not suggestions and open_tasks:
        suggestions.append(open_tasks[0])

    return ", ".join(suggestions[:2]) if suggestions else "review loops"


def _extract_open_task_descriptions(text: str) -> list[str]:
    """Pull descriptions of unchecked tasks from the note."""
    results: list[str] = []
    for line in text.splitlines():
        m = _TASK_RE.match(line.strip())
        if m and m.group(1) == " ":
            results.append(m.group(2))
    return results


def daily_close(
    target_date: date | None = None,
    settings: Settings | None = None,
) -> tuple[bool, dict]:
    """Append the > End: line to today's note, sweep closed loops, and push.

    Also pushes the workbench (stock + drafts) to rclone if configured,
    and refreshes Cursor tag autocomplete snippets.

    Returns (success, summary_dict).
    """
    settings = settings or get_settings()
    target_date = target_date or date.today()
    iso = target_date.isoformat()
    path = settings.daily_dir / f"{iso}.md"

    if not path.exists():
        return False, {"no_note": True, "date": iso}

    text = path.read_text(encoding="utf-8")

    if "> End:" in text:
        return False, {"already_closed": True, "date": iso}

    done, open_count, log_entries = _count_items(text)

    loops = get_active_loops(settings)
    open_tasks = _extract_open_task_descriptions(text)
    tomorrow = _build_tomorrow_suggestion(loops, target_date, open_tasks)

    end_line = (
        f"\n> End: Energy /5. "
        f"{done} done, {open_count} open. "
        f"Tomorrow: {tomorrow}.\n"
    )
    _atomic_write(path, text.rstrip() + "\n" + end_line)

    swept = sweep_closed(settings)

    # Push workbench and refresh tags after closing
    synced = _try_sync_push(settings)
    tags_refreshed = _refresh_tag_snippets(settings)

    summary = {
        "date": iso,
        "done_count": done,
        "open_count": open_count,
        "log_count": log_entries,
        "tomorrow_suggestion": tomorrow,
        "swept_count": len(swept),
        "synced": synced,
        "tags_refreshed": tags_refreshed,
    }
    return True, summary
