"""Tests for the insight extractors and orchestration."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from adzekit.modules.insights import (
    CarryForward,
    EnergySummary,
    InsightData,
    TagFrequency,
    Velocity,
    _classify_projects,
    _normalize_task,
    calendar_month_window,
    compute_window,
    extract_carry_forwards,
    extract_energy,
    extract_insights,
    extract_reflections,
    extract_tags,
    extract_velocity,
    iso_week_window,
    period_label,
    quarter_window,
    render_insight_markdown,
    run_insight,
)


# --- Window helpers --------------------------------------------------------


def test_iso_week_window_basic():
    # 2026-05-22 is Friday; ISO week starts Mon May 18.
    start, end = iso_week_window(date(2026, 5, 22))
    assert start == date(2026, 5, 18)
    assert end == date(2026, 5, 24)


def test_iso_week_window_on_monday():
    start, end = iso_week_window(date(2026, 5, 18))
    assert start == date(2026, 5, 18)
    assert end == date(2026, 5, 24)


def test_calendar_month_window():
    start, end = calendar_month_window(date(2026, 5, 22))
    assert start == date(2026, 5, 1)
    assert end == date(2026, 5, 31)


def test_calendar_month_window_december():
    start, end = calendar_month_window(date(2026, 12, 15))
    assert start == date(2026, 12, 1)
    assert end == date(2026, 12, 31)


def test_quarter_window_q2():
    start, end = quarter_window(date(2026, 5, 22))  # Q2: Apr-Jun
    assert start == date(2026, 4, 1)
    assert end == date(2026, 6, 30)


def test_quarter_window_q4():
    start, end = quarter_window(date(2026, 11, 10))  # Q4: Oct-Dec
    assert start == date(2026, 10, 1)
    assert end == date(2026, 12, 31)


def test_compute_window_unknown_raises():
    with pytest.raises(ValueError, match="unknown period"):
        compute_window("yearly", date(2026, 5, 22))


def test_period_label():
    d = date(2026, 5, 22)
    assert period_label("weekly", d) == "2026-W21"
    assert period_label("monthly", d) == "2026-05"
    assert period_label("quarterly", d) == "2026-Q2"


# --- Loop velocity ---------------------------------------------------------


def _write_open_loops(workspace, content: str) -> None:
    workspace.loops_active.write_text(content, encoding="utf-8")


def _write_closed_loops(workspace, content: str) -> None:
    (workspace.loops_dir / "archive.md").write_text(content, encoding="utf-8")


def test_velocity_empty_shed(workspace):
    v = extract_velocity(workspace, date(2026, 5, 18), date(2026, 5, 24), [])
    assert v.opened == 0
    assert v.closed == 0
    assert v.closure_rate_pct == 0.0
    assert v.oldest_open_loop_title is None
    assert v.projects_moved == 0
    assert v.projects_stalled == 0


def test_velocity_counts_open_in_window(workspace):
    _write_open_loops(workspace,
        "# Open\n\n"
        "- [ ] (S) [2026-05-19] In-window loop\n"
        "- [ ] (M) [2026-05-10] Pre-window loop\n",
    )
    v = extract_velocity(
        workspace, date(2026, 5, 18), date(2026, 5, 24), [],
        today=date(2026, 5, 25),
    )
    assert v.opened == 1
    # Oldest open loop is the pre-window one.
    assert v.oldest_open_loop_title == "Pre-window loop"
    assert v.oldest_open_loop_age_days == 15


def test_velocity_counts_closed_in_window(workspace):
    _write_open_loops(workspace,
        "# Open\n\n- [ ] (S) [2026-05-10] Still open\n",
    )
    _write_closed_loops(workspace,
        "# Closed\n\n"
        "- [x] (S) [2026-05-20] Closed in window\n"
        "- [x] (M) [2026-04-15] Closed before window\n",
    )
    v = extract_velocity(
        workspace, date(2026, 5, 18), date(2026, 5, 24), [],
        today=date(2026, 5, 25),
    )
    assert v.opened == 0
    assert v.closed == 1


def test_velocity_closure_rate(workspace):
    _write_open_loops(workspace,
        "# Open\n\n"
        "- [ ] (S) [2026-05-19] A\n"
        "- [ ] (S) [2026-05-19] B\n",
    )
    _write_closed_loops(workspace,
        "# Closed\n\n"
        "- [x] (S) [2026-05-20] X\n"
        "- [x] (S) [2026-05-21] Y\n"
        "- [x] (S) [2026-05-22] Z\n",
    )
    v = extract_velocity(
        workspace, date(2026, 5, 18), date(2026, 5, 24), [],
        today=date(2026, 5, 25),
    )
    assert v.opened == 2
    assert v.closed == 3
    assert v.closure_rate_pct == 150.0


def test_velocity_supports_closed_md_filename(workspace):
    """Workspace convention uses closed.md instead of archive.md."""
    (workspace.loops_dir / "closed.md").write_text(
        "# Closed\n\n- [x] (S) [2026-05-20] Workspace-style closure\n",
        encoding="utf-8",
    )
    v = extract_velocity(
        workspace, date(2026, 5, 18), date(2026, 5, 24), [],
        today=date(2026, 5, 25),
    )
    assert v.closed == 1


# --- Project classification ------------------------------------------------


def test_classify_projects_no_projects(workspace):
    moved, stalled = _classify_projects([], [])
    assert moved == 0
    assert stalled == 0


def test_classify_projects_moved_when_mentioned(workspace):
    """Project is 'moved' when its slug appears in any daily note in window."""
    from adzekit.models import Project, ProjectState
    from datetime import date

    proj = Project(slug="acme-poc", state=ProjectState.ACTIVE, title="Acme POC")
    from adzekit.parser import parse_daily_note
    note = parse_daily_note(
        "# 2026-05-22\n\n## Log\n- 09:00 worked on acme-poc\n",
        date(2026, 5, 22),
    )
    moved, stalled = _classify_projects([proj], [(date(2026, 5, 22), note)])
    assert moved == 1
    assert stalled == 0


def test_classify_projects_stalled_when_silent(workspace):
    from adzekit.models import Project, ProjectState
    from adzekit.parser import parse_daily_note

    proj = Project(slug="ghost-project", state=ProjectState.ACTIVE, title="Ghost")
    note = parse_daily_note(
        "# 2026-05-22\n\n## Log\n- 09:00 unrelated work\n",
        date(2026, 5, 22),
    )
    moved, stalled = _classify_projects([proj], [(date(2026, 5, 22), note)])
    assert moved == 0
    assert stalled == 1


# --- Carry-forward patterns -----------------------------------------------


def _make_daily_note(d: date, tasks: list[str], extra_body: str = ""):
    from adzekit.parser import parse_daily_note
    task_lines = "\n".join(f"- [ ] {t}" for t in tasks)
    text = (
        f"# {d.isoformat()}\n\n"
        "## Intention\n"
        f"{task_lines}\n\n"
        "## Log\n\n"
        "## Reflection\n"
        f"{extra_body}\n"
    )
    return parse_daily_note(text, d)


def test_carry_forwards_finds_consecutive_run():
    base = date(2026, 5, 18)
    notes = [
        (base, _make_daily_note(base, ["Send POC summary", "Other"])),
        (base + timedelta(days=1), _make_daily_note(base + timedelta(days=1),
            ["Send POC summary", "Different"])),
        (base + timedelta(days=2), _make_daily_note(base + timedelta(days=2),
            ["Send POC summary", "Yet another"])),
    ]
    cfs = extract_carry_forwards(notes)
    titles = {cf.task_text for cf in cfs}
    assert "send poc summary" in titles
    poc = next(cf for cf in cfs if cf.task_text == "send poc summary")
    assert poc.consecutive_days == 3


def test_carry_forwards_excludes_non_consecutive():
    """A task that appears Mon and Wed (but not Tue) shouldn't count as carry."""
    base = date(2026, 5, 18)
    notes = [
        (base, _make_daily_note(base, ["Sporadic"])),
        (base + timedelta(days=1), _make_daily_note(base + timedelta(days=1), ["Other"])),
        (base + timedelta(days=2), _make_daily_note(base + timedelta(days=2), ["Sporadic"])),
    ]
    cfs = extract_carry_forwards(notes)
    titles = {cf.task_text for cf in cfs}
    assert "sporadic" not in titles


def test_carry_forwards_min_threshold():
    """Default min_consecutive=2; a task in only one day doesn't count."""
    base = date(2026, 5, 18)
    notes = [
        (base, _make_daily_note(base, ["Single mention"])),
    ]
    cfs = extract_carry_forwards(notes)
    assert cfs == []


def test_normalize_task_collapses_whitespace():
    assert _normalize_task("  send    POC  ") == "send poc"


# --- Energy ---------------------------------------------------------------


def test_energy_no_samples_returns_zero():
    from adzekit.parser import parse_daily_note
    note = parse_daily_note(
        "# 2026-05-22\n\n## Intention\n- [ ] x\n", date(2026, 5, 22),
    )
    summary = extract_energy([(date(2026, 5, 22), note)])
    assert summary.samples == 0
    assert summary.avg == 0.0
    assert summary.lowest_day is None


def test_energy_extracts_end_blockquote():
    from adzekit.parser import parse_daily_note
    note_a = parse_daily_note(
        "# 2026-05-22\n\n## Intention\n- [ ] x\n\n> End: Energy 4/5. tomorrow.\n",
        date(2026, 5, 22),
    )
    note_b = parse_daily_note(
        "# 2026-05-23\n\n## Intention\n- [ ] x\n\n> End: Energy 2/5. drained.\n",
        date(2026, 5, 23),
    )
    summary = extract_energy([
        (date(2026, 5, 22), note_a),
        (date(2026, 5, 23), note_b),
    ])
    assert summary.samples == 2
    assert summary.avg == 3.0
    assert summary.lowest_day == date(2026, 5, 23)
    assert summary.lowest_value == 2


# --- Tags -----------------------------------------------------------------


def test_extract_tags_frequency():
    from adzekit.parser import parse_daily_note
    note_a = parse_daily_note(
        "# 2026-05-22\n\n#aer-compliance #vector-search\n#aer-compliance\n",
        date(2026, 5, 22),
    )
    note_b = parse_daily_note(
        "# 2026-05-23\n\n#aer-compliance\n#deep-work\n",
        date(2026, 5, 23),
    )
    tags = extract_tags([
        (date(2026, 5, 22), note_a),
        (date(2026, 5, 23), note_b),
    ])
    by_name = {t.tag: t.count for t in tags}
    assert by_name["aer-compliance"] == 3
    assert by_name["vector-search"] == 1
    assert by_name["deep-work"] == 1


def test_extract_tags_top_n_caps_results():
    from adzekit.parser import parse_daily_note
    note = parse_daily_note(
        "# x\n\n#a #b #c #d #e #f #g #h #i #j #k #l\n",
        date(2026, 5, 22),
    )
    tags = extract_tags([(date(2026, 5, 22), note)], top_n=3)
    assert len(tags) == 3


# --- Reflections ----------------------------------------------------------


def test_extract_reflections_pulls_finished_blocked_tomorrow():
    from adzekit.parser import parse_daily_note
    note = parse_daily_note(
        "# 2026-05-22\n\n"
        "## Reflection\n"
        "- **Finished:** ARC summary\n"
        "- **Blocked:** waiting on MLflow\n"
        "- **Tomorrow:** ship Acme summary\n",
        date(2026, 5, 22),
    )
    refls = extract_reflections([(date(2026, 5, 22), note)])
    assert len(refls) == 1
    d, bits = refls[0]
    assert d == date(2026, 5, 22)
    assert "ARC summary" in bits
    assert "waiting on MLflow" in bits
    assert "ship Acme summary" in bits


# --- extract_insights end-to-end ------------------------------------------


def _populate_synthetic_shed(workspace) -> date:
    """7-day synthetic shed with mixed signals. Returns Friday of the week."""
    base = date(2026, 5, 18)  # Monday
    # Open loops: one in-window, one ancient.
    workspace.loops_active.write_text(
        "# Open\n\n"
        "- [ ] (S) [2026-05-19] Send POC summary (2026-05-25)\n"
        "- [ ] (M) [2026-04-20] Ancient debt loop\n",
        encoding="utf-8",
    )
    # Closed loops: 2 in-window closures.
    (workspace.loops_dir / "archive.md").write_text(
        "# Closed\n\n"
        "- [x] (S) [2026-05-20] Reply to acme\n"
        "- [x] (S) [2026-05-22] Ship deck\n",
        encoding="utf-8",
    )
    # Daily notes Mon-Wed with "Send POC summary" carried; energy varies.
    for i, energy in enumerate([4, 3, 2]):
        d = base + timedelta(days=i)
        (workspace.daily_dir / f"{d.isoformat()}.md").write_text(
            f"# {d.isoformat()}\n\n"
            "## Triage\n\n"
            "## Intention\n"
            "- [ ] Send POC summary\n"
            f"- [ ] Day-{i} unique task\n\n"
            "## Log\n"
            "- 09:00 #deep-work block\n"
            "- 10:30 acme follow-up\n\n"
            "## Reflection\n"
            f"- **Finished:** something for day {i}\n"
            "- **Blocked:** morning email overwhelm\n\n"
            f"> End: Energy {energy}/5. okay day.\n",
            encoding="utf-8",
        )
    return base + timedelta(days=4)  # Friday


def test_extract_insights_end_to_end(workspace):
    target = _populate_synthetic_shed(workspace)
    data = extract_insights(workspace, period="weekly", target=target)
    assert data.period == "weekly"
    assert data.window_start == date(2026, 5, 18)
    assert data.window_end == date(2026, 5, 24)
    # Velocity:
    assert data.velocity.opened == 1  # the in-window open loop
    assert data.velocity.closed == 2
    assert data.velocity.closure_rate_pct == 200.0
    # Oldest open loop is the ancient one.
    assert data.velocity.oldest_open_loop_title == "Ancient debt loop"
    # Carry-forward:
    cf_texts = {cf.task_text for cf in data.carry_forwards}
    assert "send poc summary" in cf_texts
    # Energy:
    assert data.energy.samples == 3
    assert data.energy.avg == 3.0
    # Tag:
    by_tag = {t.tag: t.count for t in data.tags}
    assert by_tag.get("deep-work") == 3
    # Reflections present.
    assert len(data.reflections) == 3


def test_render_insight_markdown_includes_all_sections(workspace):
    target = _populate_synthetic_shed(workspace)
    data = extract_insights(workspace, period="weekly", target=target)
    body = render_insight_markdown(data)
    assert "# Weekly Insight — 2026-W21" in body
    assert "## Velocity" in body
    assert "Opened: 1 loops" in body
    assert "Closed: 2 loops" in body
    assert "## Carry-forward patterns" in body
    assert "send poc summary" in body
    assert "## Energy" in body
    assert "## Top tags" in body
    assert "## Reflections (per day)" in body
    # The skill-polish placeholder is present and labeled.
    assert "## Themes & suggested experiments" in body


def test_run_insight_writes_draft_to_insights_subdir(workspace):
    target = _populate_synthetic_shed(workspace)
    data, path = run_insight(period="weekly", settings=workspace, target=target)
    assert path is not None
    assert path.parent == workspace.drafts_dir / "insights"
    # The draft body has provenance + the rendered markdown.
    body = path.read_text(encoding="utf-8")
    assert body.startswith("<!-- adzekit-draft")
    assert "skill: insight-weekly" in body
    assert "# Weekly Insight — 2026-W21" in body


def test_run_insight_surfaces_in_inbox(workspace):
    from adzekit.modules.drafts import parse_inbox
    target = _populate_synthetic_shed(workspace)
    run_insight(period="weekly", settings=workspace, target=target)
    entries = parse_inbox(workspace)
    assert len(entries) == 1
    assert entries[0].skill == "insight-weekly"
    # INBOX path points at the insights subdir, not the drafts root.
    assert entries[0].path.startswith("drafts/insights/")


def test_run_insight_reproducible_body(workspace):
    """Same shed + same target date = same body hash."""
    from adzekit.preprocessor import read_draft_frontmatter

    target = _populate_synthetic_shed(workspace)
    _, path_a = run_insight(period="weekly", settings=workspace, target=target)
    hash_a = read_draft_frontmatter(path_a)["hash"]

    # Wipe drafts and rerun.
    import shutil
    if (workspace.drafts_dir / "INBOX.d").exists():
        shutil.rmtree(workspace.drafts_dir / "INBOX.d")
    if (workspace.drafts_dir / "insights").exists():
        shutil.rmtree(workspace.drafts_dir / "insights")

    _, path_b = run_insight(period="weekly", settings=workspace, target=target)
    hash_b = read_draft_frontmatter(path_b)["hash"]
    assert hash_a == hash_b
