"""Weekly review: cull the shed and generate a pulse summary draft.

`adzekit weekly-review` runs on the Friday cadence. It:
  1. Updates bench.md from drafts/ and archives daily notes older than N days
  2. Writes a pulse summary to `reviews/YYYY-WNN-pulse.md` with pre-populated
     bullets harvested from the week's daily notes, loops, and projects
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from adzekit.config import Settings, get_settings
from adzekit.models import DailyNote, Loop
from adzekit.modules.bench import cull
from adzekit.modules.daily import DAILY_ARCHIVE_DAYS, archive_old_dailies
from adzekit.modules.daily import _filter_overdue  # noqa: PLC2701 — shared ritual logic
from adzekit.modules.insights import (
    extract_carry_forwards,
    iso_week_window,
    period_label,
)
from adzekit.modules.loops import get_active_loops
from adzekit.modules.wip import stale_active_projects
from adzekit.preprocessor import load_daily_note

_TASK_PREFIX_RE = re.compile(r"^\([A-Za-z]+\)\s+")


@dataclass
class PulseData:
    week_label: str
    week_ending: date
    window_start: date
    window_end: date
    proud: list[str]
    focus: list[str]
    blockers: list[str]


def _clean_task(text: str) -> str:
    text = _TASK_PREFIX_RE.sub("", text.strip())
    return re.sub(r"\s+", " ", text)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _dedupe(items: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = _normalize(item)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def _load_weekly_daily_notes(
    settings: Settings,
    window_start: date,
    window_end: date,
) -> list[tuple[date, DailyNote]]:
    notes: list[tuple[date, DailyNote]] = []
    d = window_start
    while d <= window_end:
        note = load_daily_note(target_date=d, settings=settings)
        if note is not None:
            notes.append((d, note))
        d += timedelta(days=1)
    return notes


def _loops_due_soon(
    loops: list[Loop],
    *,
    after: date,
    within_days: int = 7,
) -> list[Loop]:
    end = after + timedelta(days=within_days)
    due_soon: list[Loop] = []
    for loop in loops:
        if loop.due is None:
            continue
        if after < loop.due <= end:
            due_soon.append(loop)
    due_soon.sort(key=lambda loop: loop.due or after)
    return due_soon


def extract_pulse(
    settings: Settings | None = None,
    *,
    target: date | None = None,
) -> PulseData:
    """Harvest pulse bullets from the ISO week containing `target`."""
    settings = settings or get_settings()
    target = target or date.today()
    window_start, window_end = iso_week_window(target)
    daily_notes = _load_weekly_daily_notes(settings, window_start, window_end)

    proud_candidates: list[str] = []
    for _, note in daily_notes:
        for task in note.intentions:
            if task.done:
                proud_candidates.append(_clean_task(task.description))
        for entry in note.finished:
            proud_candidates.append(entry.strip())

    proud = _dedupe(proud_candidates, 3)
    if not proud:
        proud = ["_(Add 1–3 wins from this week.)_"]

    active_loops = get_active_loops(settings)
    overdue = _filter_overdue(active_loops, target)
    due_soon = _loops_due_soon(active_loops, after=target)
    carry_forwards = sorted(
        extract_carry_forwards(daily_notes),
        key=lambda cf: -cf.consecutive_days,
    )

    focus_candidates: list[str] = []
    for loop in overdue:
        focus_candidates.append(f"Overdue: {loop.title}")
    for loop in due_soon:
        focus_candidates.append(f"Due {loop.due}: {loop.title}")
    for cf in carry_forwards:
        focus_candidates.append(
            f"Carried {cf.consecutive_days}d: {cf.task_text}"
        )
    if daily_notes:
        _, latest = daily_notes[-1]
        for task in latest.intentions:
            if not task.done:
                focus_candidates.append(_clean_task(task.description))
        focus_candidates.extend(latest.tomorrow)

    focus = _dedupe(focus_candidates, 3)
    if not focus:
        focus = ["_(Add 1–3 priorities for next week.)_"]

    blocker_candidates: list[str] = []
    for _, note in daily_notes:
        blocker_candidates.extend(note.blocked)
    for loop in overdue:
        blocker_candidates.append(f"Overdue loop ({loop.title})")
    for proj, days in stale_active_projects(settings):
        blocker_candidates.append(f"Stale project: {proj.slug} ({days}d)")

    blockers = _dedupe(blocker_candidates, 3)

    return PulseData(
        week_label=period_label("weekly", target),
        week_ending=window_end,
        window_start=window_start,
        window_end=window_end,
        proud=proud,
        focus=focus,
        blockers=blockers,
    )


def render_pulse_markdown(data: PulseData, *, generated: date | None = None) -> str:
    """Render the pulse check-in format."""
    generated = generated or date.today()
    lines = [
        f"# Pulse — {data.week_label} (week ending {data.week_ending.isoformat()})",
        "",
        f"_Generated {generated.isoformat()}. Edit bullets before sharing._",
        f"_Window: {data.window_start.isoformat()} → {data.window_end.isoformat()}_",
        "",
        "## What did you get done this week that you're proud of?",
        "",
    ]
    lines.extend(f"- {item}" for item in data.proud)
    lines.extend([
        "",
        "## What's your top focus for next week?",
        "",
    ])
    lines.extend(f"- {item}" for item in data.focus)
    lines.extend([
        "",
        "## Any blockers or challenges you're facing?",
        "",
    ])
    if data.blockers:
        lines.extend(f"- {item}" for item in data.blockers)
    else:
        lines.append("_Nothing flagged from shed data — add items or delete this section._")
    lines.append("")
    return "\n".join(lines)


def run_weekly_review(
    settings: Settings | None = None,
    *,
    target: date | None = None,
    archive_days: int | None = None,
) -> dict:
    """Cull the shed, archive old dailies, and write the pulse summary."""
    settings = settings or get_settings()
    target = target or date.today()
    days = archive_days if archive_days is not None else DAILY_ARCHIVE_DAYS

    bench_added, bench_cleared = cull(settings)
    archived = archive_old_dailies(settings, days=days)
    pulse = extract_pulse(settings, target=target)

    year, week_num, _ = target.isocalendar()
    review_id = f"{year}-W{week_num:02d}"
    pulse_path = settings.reviews_dir / f"{review_id}-pulse.md"
    pulse_path.parent.mkdir(parents=True, exist_ok=True)
    pulse_path.write_text(render_pulse_markdown(pulse), encoding="utf-8")

    return {
        "week_label": pulse.week_label,
        "pulse_path": pulse_path,
        "bench_added": bench_added,
        "bench_cleared": bench_cleared,
        "archived_dailies": archived,
        "window_start": pulse.window_start.isoformat(),
        "window_end": pulse.window_end.isoformat(),
    }
