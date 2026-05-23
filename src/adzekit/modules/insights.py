"""Insight extractors: deterministic synthesis of accumulated shed data.

`adzekit insight --period weekly|monthly|quarterly` runs this module's
extractors against the shed, then writes a structured draft to
`drafts/insights/insight-<period>-<id>-{host}.md` via
`write_draft_with_frontmatter`. The draft surfaces in INBOX.

What gets extracted (deterministic, no LLM in core):

  velocity        — loops opened/closed in the window; closure rate;
                    oldest open loop; projects moved vs stalled
  carry_forwards  — intentions repeated across consecutive daily notes
  energy          — averages + lowest day from `> End: Energy N/5` lines
  tags            — #tag frequency across the window's daily notes
  reflections     — raw `## Reflection` bodies (passed to the LLM layer)

The skill markdown (`src/adzekit/skills/insight.md`) describes what the
LLM layer should add on top: themes from reflections, suggested
experiments, narrative connections.

All extractors are pure functions of (loops list, daily-notes list, projects
list, window). Tests populate a synthetic shed and assert outputs match.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from adzekit.config import Settings, get_settings
from adzekit.models import DailyNote, Loop, Project


# --- Window helpers --------------------------------------------------------


def iso_week_window(target: date) -> tuple[date, date]:
    """Monday..Sunday of the ISO week containing `target`."""
    monday = target - timedelta(days=target.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def calendar_month_window(target: date) -> tuple[date, date]:
    """First..last day of the calendar month containing `target`."""
    start = target.replace(day=1)
    if start.month == 12:
        end = date(start.year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(start.year, start.month + 1, 1) - timedelta(days=1)
    return start, end


def quarter_window(target: date) -> tuple[date, date]:
    """First..last day of the calendar quarter containing `target`."""
    start_month = ((target.month - 1) // 3) * 3 + 1
    start = date(target.year, start_month, 1)
    end_month = start_month + 2
    if end_month == 12:
        end = date(target.year, 12, 31)
    else:
        end = date(target.year, end_month + 1, 1) - timedelta(days=1)
    return start, end


def compute_window(period: str, target: date) -> tuple[date, date]:
    if period == "weekly":
        return iso_week_window(target)
    if period == "monthly":
        return calendar_month_window(target)
    if period == "quarterly":
        return quarter_window(target)
    raise ValueError(
        f"unknown period: {period!r}; valid: weekly, monthly, quarterly"
    )


def period_label(period: str, target: date) -> str:
    """Short human label for the period header."""
    if period == "weekly":
        iso_year, iso_week, _ = target.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    if period == "monthly":
        return target.strftime("%Y-%m")
    if period == "quarterly":
        q = (target.month - 1) // 3 + 1
        return f"{target.year}-Q{q}"
    return f"{target.isoformat()}"


# --- Dataclasses -----------------------------------------------------------


@dataclass
class Velocity:
    opened: int
    closed: int
    closure_rate_pct: float
    oldest_open_loop_title: str | None
    oldest_open_loop_age_days: int | None
    projects_moved: int
    projects_stalled: int


@dataclass
class CarryForward:
    task_text: str
    consecutive_days: int
    first_seen: date


@dataclass
class EnergySummary:
    samples: int
    avg: float
    lowest_day: date | None
    lowest_value: int | None


@dataclass
class TagFrequency:
    tag: str
    count: int


@dataclass
class InsightData:
    period: str
    target_date: date
    window_start: date
    window_end: date
    velocity: Velocity
    carry_forwards: list[CarryForward]
    energy: EnergySummary
    tags: list[TagFrequency]
    reflections: list[tuple[date, list[str]]] = field(default_factory=list)


# --- Loop file loaders -----------------------------------------------------


def _load_loops_from(path: Path) -> list[Loop]:
    """Parse loops from a file if it exists; else empty list."""
    from adzekit.parser import parse_loops
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []
    return parse_loops(text)


def _find_closed_loops_file(settings: Settings) -> Path | None:
    """Return whichever closed-loops file the workspace has, if any.

    Supports both naming conventions:
      - loops/archive.md (canonical spec)
      - loops/closed.md (workspace convention)
    """
    candidates = [
        settings.loops_dir / "archive.md",
        settings.loops_dir / "closed.md",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _find_open_loops_file(settings: Settings) -> Path | None:
    """Return whichever open-loops file the workspace has, if any."""
    candidates = [
        settings.loops_dir / "active.md",
        settings.loops_dir / "open.md",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


# --- Velocity --------------------------------------------------------------


def extract_velocity(
    settings: Settings,
    window_start: date,
    window_end: date,
    daily_notes: list[tuple[date, DailyNote]],
    today: date | None = None,
) -> Velocity:
    today = today or date.today()
    open_loops_path = _find_open_loops_file(settings)
    closed_loops_path = _find_closed_loops_file(settings)

    open_loops = _load_loops_from(open_loops_path) if open_loops_path else []
    closed_loops = _load_loops_from(closed_loops_path) if closed_loops_path else []

    opened = sum(
        1 for loop in open_loops
        if loop.date and window_start <= loop.date <= window_end
    )
    closed = sum(
        1 for loop in closed_loops
        if loop.date and window_start <= loop.date <= window_end
    )
    closure_rate_pct = (closed / opened * 100.0) if opened else 0.0

    # Oldest currently-open loop (regardless of window — we surface it as a
    # nag, not a window statistic).
    open_loops_dated = [loop for loop in open_loops if loop.date]
    if open_loops_dated:
        oldest = min(open_loops_dated, key=lambda loop: loop.date)
        oldest_title = oldest.title
        oldest_age_days = (today - oldest.date).days
    else:
        oldest_title = None
        oldest_age_days = None

    # Project activity: project is "moved" if its slug appears in any daily
    # note in the window; else stalled.
    from adzekit.preprocessor import load_projects
    from adzekit.models import ProjectState
    active_projects: list[Project] = load_projects(
        state=ProjectState.ACTIVE, settings=settings,
    )
    moved, stalled = _classify_projects(active_projects, daily_notes)

    return Velocity(
        opened=opened,
        closed=closed,
        closure_rate_pct=closure_rate_pct,
        oldest_open_loop_title=oldest_title,
        oldest_open_loop_age_days=oldest_age_days,
        projects_moved=moved,
        projects_stalled=stalled,
    )


def _classify_projects(
    projects: list[Project],
    daily_notes: list[tuple[date, DailyNote]],
) -> tuple[int, int]:
    """A project is 'moved' iff its slug appears in any daily note body
    within the window. Otherwise it's 'stalled'."""
    moved_count = 0
    for proj in projects:
        slug = proj.slug.lower()
        moved = any(
            slug in note.raw_content.lower()
            for _, note in daily_notes
        )
        if moved:
            moved_count += 1
    return moved_count, len(projects) - moved_count


# --- Carry-forward patterns ------------------------------------------------


def extract_carry_forwards(
    daily_notes: list[tuple[date, DailyNote]],
    *,
    min_consecutive: int = 2,
) -> list[CarryForward]:
    """Detect intentions that appear in N consecutive daily notes.

    Sorts daily_notes by date, walks adjacent pairs, and tracks runs of the
    same (normalized) task text. Returns the longest run per task in the
    window, filtered by `min_consecutive`.
    """
    sorted_notes = sorted(daily_notes, key=lambda pair: pair[0])
    # Map (normalized_text) -> (first_seen_date, current_run_length, max_run)
    runs: dict[str, dict] = {}
    prev_tasks: set[str] = set()
    prev_date: date | None = None

    for d, note in sorted_notes:
        current_tasks = {
            _normalize_task(t.description) for t in note.intentions
            if not t.done
        }
        for task in current_tasks:
            if task in prev_tasks and prev_date and (d - prev_date).days == 1:
                # Continuing a run.
                state = runs.get(task)
                if state is None:
                    state = {"first_seen": d - timedelta(days=1), "current": 2, "max": 2}
                    runs[task] = state
                else:
                    state["current"] += 1
                    state["max"] = max(state["max"], state["current"])
            else:
                # Starting (or restarting) a run.
                state = runs.get(task)
                if state is None:
                    runs[task] = {"first_seen": d, "current": 1, "max": 1}
                else:
                    # If we had a streak that broke and is restarting:
                    state["current"] = 1
                    # Don't reset max — it tracks the longest historical run.
        prev_tasks = current_tasks
        prev_date = d

    return [
        CarryForward(
            task_text=task,
            consecutive_days=state["max"],
            first_seen=state["first_seen"],
        )
        for task, state in runs.items()
        if state["max"] >= min_consecutive
    ]


def _normalize_task(text: str) -> str:
    """Lowercase + strip surrounding whitespace + collapse internal spaces."""
    return re.sub(r"\s+", " ", text.strip().lower())


# --- Energy ----------------------------------------------------------------


_ENERGY_RE = re.compile(r"Energy\s+(\d)\s*/\s*5", re.IGNORECASE)


def extract_energy(daily_notes: list[tuple[date, DailyNote]]) -> EnergySummary:
    """Parse Energy N/5 from `> End:` blockquote lines in each daily note."""
    samples: list[tuple[date, int]] = []
    for d, note in daily_notes:
        m = _ENERGY_RE.search(note.raw_content)
        if m:
            try:
                v = int(m.group(1))
                samples.append((d, v))
            except ValueError:
                continue
    if not samples:
        return EnergySummary(
            samples=0, avg=0.0, lowest_day=None, lowest_value=None,
        )
    values = [v for _, v in samples]
    lowest_day, lowest_value = min(samples, key=lambda pair: pair[1])
    return EnergySummary(
        samples=len(samples),
        avg=sum(values) / len(values),
        lowest_day=lowest_day,
        lowest_value=lowest_value,
    )


# --- Tags ------------------------------------------------------------------


_TAG_RE = re.compile(r"(?<![A-Za-z0-9_])#([a-z0-9][a-z0-9-]*)\b")


def extract_tags(
    daily_notes: list[tuple[date, DailyNote]],
    *,
    top_n: int = 10,
) -> list[TagFrequency]:
    """Top-N #tag frequency across all daily-note bodies in the window."""
    counter: Counter[str] = Counter()
    for _, note in daily_notes:
        counter.update(_TAG_RE.findall(note.raw_content.lower()))
    return [
        TagFrequency(tag=t, count=c) for t, c in counter.most_common(top_n)
    ]


# --- Reflections (raw, for the LLM layer) ----------------------------------


def extract_reflections(
    daily_notes: list[tuple[date, DailyNote]],
) -> list[tuple[date, list[str]]]:
    """Per-day collection of free-form reflection text.

    For each daily note, returns the human-written content under
    `## Reflection`: the Finished/Blocked/Tomorrow bullet bodies. The LLM
    layer reads these to surface themes the deterministic extractors miss.
    """
    out: list[tuple[date, list[str]]] = []
    for d, note in daily_notes:
        bits: list[str] = []
        bits.extend(note.finished)
        bits.extend(note.blocked)
        bits.extend(note.tomorrow)
        out.append((d, bits))
    return out


# --- Orchestration ---------------------------------------------------------


def extract_insights(
    settings: Settings | None = None,
    *,
    period: str = "weekly",
    target: date | None = None,
) -> InsightData:
    """End-to-end: compute the window, load data, run all extractors."""
    from adzekit.preprocessor import load_daily_note

    settings = settings or get_settings()
    target = target or date.today()
    window_start, window_end = compute_window(period, target)

    # Load every daily note in the window.
    daily_notes: list[tuple[date, DailyNote]] = []
    d = window_start
    while d <= window_end:
        note = load_daily_note(target_date=d, settings=settings)
        if note is not None:
            daily_notes.append((d, note))
        d += timedelta(days=1)

    velocity = extract_velocity(
        settings, window_start, window_end, daily_notes, today=target,
    )
    carry_forwards = extract_carry_forwards(daily_notes)
    energy = extract_energy(daily_notes)
    tags = extract_tags(daily_notes)
    reflections = extract_reflections(daily_notes)

    return InsightData(
        period=period,
        target_date=target,
        window_start=window_start,
        window_end=window_end,
        velocity=velocity,
        carry_forwards=carry_forwards,
        energy=energy,
        tags=tags,
        reflections=reflections,
    )


# --- Rendering -------------------------------------------------------------


def render_insight_markdown(data: InsightData) -> str:
    """Render the InsightData into a draft markdown body."""
    lines: list[str] = []
    title_period = data.period.capitalize()
    label = period_label(data.period, data.target_date)
    lines.append(f"# {title_period} Insight — {label}")
    lines.append("")
    lines.append(
        f"_Window: {data.window_start.isoformat()} → {data.window_end.isoformat()}_"
    )
    lines.append("")

    # Velocity
    lines.append("## Velocity")
    v = data.velocity
    lines.append(f"- Opened: {v.opened} loops")
    lines.append(f"- Closed: {v.closed} loops")
    if v.opened > 0 or v.closed > 0:
        lines.append(f"- Closure rate: {v.closure_rate_pct:.0f}%")
    if v.oldest_open_loop_title:
        lines.append(
            f"- Oldest open loop: \"{v.oldest_open_loop_title}\" "
            f"({v.oldest_open_loop_age_days} days old)"
        )
    lines.append(f"- Projects: {v.projects_moved} moved, {v.projects_stalled} stalled")
    lines.append("")

    # Carry-forward
    lines.append("## Carry-forward patterns")
    if data.carry_forwards:
        # Sort by longest streak first.
        sorted_cfs = sorted(
            data.carry_forwards,
            key=lambda c: -c.consecutive_days,
        )
        for cf in sorted_cfs:
            lines.append(
                f"- \"{cf.task_text}\" carried {cf.consecutive_days} consecutive days "
                f"(first seen {cf.first_seen.isoformat()})"
            )
    else:
        lines.append("- (no intentions carried multiple days)")
    lines.append("")

    # Energy
    lines.append("## Energy")
    e = data.energy
    if e.samples > 0:
        lines.append(f"- Samples: {e.samples}; avg {e.avg:.1f}/5")
        if e.lowest_day and e.lowest_value is not None:
            lines.append(
                f"- Lowest: {e.lowest_day.strftime('%A %Y-%m-%d')} ({e.lowest_value}/5)"
            )
    else:
        lines.append("- (no `> End: Energy N/5` lines logged in this window)")
    lines.append("")

    # Tags
    lines.append("## Top tags")
    if data.tags:
        for tag in data.tags:
            lines.append(f"- #{tag.tag}: {tag.count}")
    else:
        lines.append("- (no tags found)")
    lines.append("")

    # Reflections — raw, for the LLM layer
    lines.append("## Reflections (per day)")
    if any(bits for _, bits in data.reflections):
        for d, bits in data.reflections:
            if not bits:
                continue
            lines.append(f"### {d.strftime('%A %Y-%m-%d')}")
            for bit in bits:
                lines.append(f"- {bit}")
            lines.append("")
    else:
        lines.append("- (no reflections in this window)")
    lines.append("")

    # Footer placeholder for the LLM layer
    lines.append("## Themes & suggested experiments")
    lines.append(
        "_The `/insight` skill (Claude Code adapter) reads the data above "
        "and adds synthesis here: themes that repeat across reflections, "
        "experiments worth running next period, connections the deterministic "
        "extractors don't see._"
    )
    lines.append("")

    return "\n".join(lines)


# --- CLI entry point -------------------------------------------------------


def run_insight(
    period: str = "weekly",
    *,
    settings: Settings | None = None,
    target: date | None = None,
    write: bool = True,
) -> tuple[InsightData, Path | None]:
    """Compute the insight, render markdown, optionally write a draft.

    Returns (InsightData, draft_path). When write=False, the draft is not
    written and draft_path is None — useful for testing the renderer in
    isolation.
    """
    from adzekit.preprocessor import write_draft_with_frontmatter

    settings = settings or get_settings()
    data = extract_insights(settings, period=period, target=target)
    body = render_insight_markdown(data)
    if not write:
        return data, None

    summary = f"{period} {period_label(period, data.target_date)}"
    path = write_draft_with_frontmatter(
        f"insight-{period}",
        body=body,
        settings=settings,
        summary=summary,
        trigger="cli",
    )
    # Route the draft into drafts/insights/ to keep them grouped.
    insights_dir = settings.drafts_dir / "insights"
    insights_dir.mkdir(parents=True, exist_ok=True)
    target_path = insights_dir / path.name
    target_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    path.unlink()
    _retarget_inbox_line(settings, path.name, target_path)
    return data, target_path


def _retarget_inbox_line(
    settings: Settings,
    filename: str,
    new_path: Path,
) -> None:
    """Rewrite the INBOX sidecar so it points at the relocated draft."""
    old_marker = f"`drafts/{filename}`"
    try:
        rel = str(new_path.resolve().relative_to(settings.shed.resolve()))
    except ValueError:
        rel = str(new_path)
    new_marker = f"`{rel}`"
    sidecar = settings.drafts_dir / "INBOX.d" / f"{Path(filename).stem}.entry"
    if sidecar.exists():
        text = sidecar.read_text(encoding="utf-8")
        sidecar.write_text(text.replace(old_marker, new_marker), encoding="utf-8")
        from adzekit.preprocessor import _regenerate_inbox_view
        _regenerate_inbox_view(settings)
        return
    inbox = settings.drafts_dir / "INBOX.md"
    if inbox.exists():
        text = inbox.read_text(encoding="utf-8")
        inbox.write_text(text.replace(old_marker, new_marker), encoding="utf-8")
