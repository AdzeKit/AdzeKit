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

# Triage line: `- [ ] OVERDUE 23d: Manulife KARL POC ticket → kill / defer / promote`
# After resolution: `- [x] OVERDUE 23d: Manulife KARL POC ticket → kill`
_TRIAGE_LINE_RE = re.compile(
    r"^-\s+\[([ xX])\]\s+"
    r"(OVERDUE|STALE|STALE BENCH)\s+(\d+)d:\s+"
    r"(.+?)\s+→\s+(.+)$"
)


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


def _build_triage_section(
    overdue_loops: list[Loop],
    settings: Settings,
    target_date: date,
) -> tuple[str, int]:
    """Build the ## Triage block for items needing kill/defer/promote decisions.

    Returns (section_text, item_count). Empty string when nothing is due.
    """
    from adzekit.modules.bench import stale_bench_items
    from adzekit.modules.wip import stale_active_projects

    lines: list[str] = []

    for loop in overdue_loops:
        days = (target_date - loop.due).days if loop.due else 0
        lines.append(f"- [ ] OVERDUE {days}d: {loop.title} → kill / defer / promote")

    try:
        for proj, days in stale_active_projects(settings):
            lines.append(f"- [ ] STALE {days}d: {proj.slug} → kill / defer / commit")
    except Exception:
        pass

    try:
        for item in stale_bench_items(settings):
            lines.append(f"- [ ] STALE BENCH {item['days']}d: {item['text']} → keep / drop")
    except Exception:
        pass

    if not lines:
        return "", 0

    body = "\n".join(lines)
    section = (
        "## Triage (must resolve before daily-close)\n"
        f"{body}\n\n"
    )
    return section, len(lines)


def _build_graph_context_blurbs(task_lines: list[str], settings: Settings) -> dict[str, str]:
    """For each task line, return a 'task_text -> "> Context: ..."' blurb if the
    task references a project slug that exists in the graph. Silent on failure."""
    try:
        from adzekit.modules.graph import get_context, load_graph
    except Exception:
        return {}

    graph = load_graph(settings)
    if graph is None:
        return {}

    blurbs: dict[str, str] = {}
    for line in task_lines:
        m = _TASK_RE.match(line.strip())
        if not m:
            continue
        text = m.group(2).lower()
        # Match the longest entity name that appears in the task line.
        best: str | None = None
        for name in graph.entities:
            if name in text and (best is None or len(name) > len(best)):
                best = name
        if best is None:
            continue
        ctx = get_context(best, graph, depth=1)
        # Pull just the "Connected:" line if present — keep it tight.
        connected = next(
            (ln for ln in ctx.splitlines() if ln.startswith("Connected:")),
            None,
        )
        if connected:
            short = connected.replace("Connected: ", "")
            blurbs[line] = f"  > Context [{best}]: {short[:120]}"
    return blurbs


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

    # Build optional ## Triage section (overdue loops + stale projects + stale bench)
    triage_section, triage_count = _build_triage_section(overdue, settings, target_date)

    # Annotate task lines with graph context where available.
    blurbs = _build_graph_context_blurbs(task_lines, settings)
    annotated_tasks: list[str] = []
    for line in task_lines:
        annotated_tasks.append(line)
        if line in blurbs:
            annotated_tasks.append(blurbs[line])

    # Format the note in existing section format
    intention_block = "\n".join(annotated_tasks) if annotated_tasks else "- [ ] Top priority:"
    content = f"""# {iso} {weekday}

{triage_section}## Morning: Intention
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
        "triage_count": triage_count,
        "graph_blurbs": len(blurbs),
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


def parse_triage_decisions(text: str) -> list[dict]:
    """Extract triage decisions from a daily note's ## Triage section.

    Each result is {"resolved": bool, "kind": "OVERDUE"|"STALE"|"STALE BENCH",
    "days": int, "subject": str, "decision": str}. Decisions are extracted
    from text after the arrow (everything past the literal "→").
    A line is considered resolved iff it's checked AND the decision is one of
    the canonical verbs (kill/defer/promote/commit/keep/drop, optionally with
    a date).
    """
    in_triage = False
    decisions: list[dict] = []

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("## triage"):
            in_triage = True
            continue
        if in_triage and stripped.startswith("## "):
            break
        if not in_triage:
            continue

        m = _TRIAGE_LINE_RE.match(stripped)
        if not m:
            continue
        checked = m.group(1).lower() == "x"
        kind = m.group(2)
        days = int(m.group(3))
        subject = m.group(4).strip()
        decision_raw = m.group(5).strip().lower()

        # A "raw" placeholder still containing the menu text (e.g. "kill / defer / promote")
        # is unresolved.
        is_placeholder = "/" in decision_raw and "kill" in decision_raw and "defer" in decision_raw
        verb = decision_raw.split()[0] if decision_raw else ""
        canonical = verb in {"kill", "defer", "promote", "commit", "keep", "drop"}
        resolved = checked and canonical and not is_placeholder

        decisions.append({
            "resolved": resolved,
            "checked": checked,
            "kind": kind,
            "days": days,
            "subject": subject,
            "decision": decision_raw,
        })
    return decisions


def _apply_triage_decisions(
    decisions: list[dict],
    settings: Settings,
) -> dict:
    """Apply resolved triage decisions to the backbone.

    - kill (OVERDUE) → set the matching loop's status to Closed; the caller's
      sweep_closed() then moves it from active.md to archive.md
    - kill (STALE)   → archive_project (active → archive)
    - defer / promote / commit / keep / drop → noted; no structural change
    """
    from adzekit.modules.loops import get_active_loops
    from adzekit.modules.wip import archive_project
    from adzekit.parser import format_loops

    counts = {"killed": 0, "deferred": 0, "promoted": 0, "kept": 0}

    for d in decisions:
        if not d["resolved"]:
            continue
        verb = d["decision"].split()[0]
        kind = d["kind"]
        subject = d["subject"]

        if verb == "kill" and kind == "OVERDUE":
            try:
                loops = get_active_loops(settings)
                hit = False
                for loop in loops:
                    if (not hit
                        and subject.lower() in loop.title.lower()
                        and loop.status.lower() != "closed"):
                        loop.status = "Closed"
                        hit = True
                if hit:
                    new_content = "# Active Loops\n\n" + format_loops(loops) + "\n"
                    _atomic_write(settings.loops_active, new_content)
                    counts["killed"] += 1
            except Exception:
                pass

        elif verb == "kill" and kind == "STALE":
            try:
                archive_project(subject, settings)
                counts["killed"] += 1
            except FileNotFoundError:
                pass

        elif verb == "defer":
            counts["deferred"] += 1

        elif verb in {"promote", "commit", "keep"}:
            counts["promoted"] += 1

        elif verb == "drop":
            counts["kept"] += 1

    return counts


def daily_close(
    target_date: date | None = None,
    settings: Settings | None = None,
) -> tuple[bool, dict]:
    """Append the > End: line to today's note, sweep closed loops, and push.

    Hard-blocks if the daily note has unresolved ## Triage items. The user
    must check each triage line and write a canonical decision (kill / defer /
    promote / commit / keep / drop) before the day can close.

    Also pushes the workbench (stock + drafts) to rclone if configured,
    refreshes Cursor tag autocomplete snippets, and rebuilds the graph.

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

    # Hard block: unresolved triage decisions.
    triage = parse_triage_decisions(text)
    unresolved = [d for d in triage if not d["resolved"]]
    if unresolved:
        return False, {
            "triage_blocked": True,
            "unresolved_count": len(unresolved),
            "unresolved": [
                f"{d['kind']} {d['days']}d: {d['subject']}" for d in unresolved
            ],
            "date": iso,
        }

    triage_counts = _apply_triage_decisions(triage, settings)

    done, open_count, log_entries = _count_items(text)

    loops = get_active_loops(settings)
    open_tasks = _extract_open_task_descriptions(text)
    tomorrow = _build_tomorrow_suggestion(loops, target_date, open_tasks)

    triage_summary = ""
    if triage:
        bits = [f"{v} {k}" for k, v in triage_counts.items() if v]
        if bits:
            triage_summary = f" Triage: {', '.join(bits)}."

    end_line = (
        f"\n> End: Energy /5. "
        f"{done} done, {open_count} open."
        f"{triage_summary} "
        f"Tomorrow: {tomorrow}.\n"
    )
    _atomic_write(path, text.rstrip() + "\n" + end_line)

    swept = sweep_closed(settings)

    # Rebuild the graph after the day's edits land
    try:
        from adzekit.modules.graph import build_graph, save_graph
        save_graph(build_graph(settings), settings)
    except Exception:
        pass

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
        "triage_resolved": len(triage),
        "triage_counts": triage_counts,
        "synced": synced,
        "tags_refreshed": tags_refreshed,
    }
    return True, summary
