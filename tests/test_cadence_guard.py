"""Tests for the Phase 4 cadence layer's deep-work guard."""

from __future__ import annotations

from datetime import datetime, time

from adzekit.modules.automate import (
    SCHEDULES,
    in_deep_work_window,
    parse_deep_work_window,
)


def _write_soul(workspace, body: str) -> None:
    soul = workspace.knowledge_dir / "soul.md"
    soul.write_text(body, encoding="utf-8")


# --- parse_deep_work_window -------------------------------------------------


def test_parse_simple_range():
    assert parse_deep_work_window("09:00-11:00 America/Edmonton") == (
        time(9, 0),
        time(11, 0),
    )


def test_parse_with_emdash():
    assert parse_deep_work_window("09:00—11:30") == (time(9, 0), time(11, 30))


def test_parse_single_digit_hour():
    assert parse_deep_work_window("9:00-11:00") == (time(9, 0), time(11, 0))


def test_parse_empty_returns_none():
    assert parse_deep_work_window("") is None


def test_parse_malformed_returns_none():
    assert parse_deep_work_window("morning, sometimes") is None


def test_parse_multi_line_uses_first_match():
    text = "Nope, just text\n14:00-16:00 alternate\n"
    assert parse_deep_work_window(text) == (time(14, 0), time(16, 0))


# --- in_deep_work_window ----------------------------------------------------


def test_guard_inside_window(workspace):
    _write_soul(workspace, "# Soul\n\n## Deep work hours\n09:00-11:00 America/Edmonton\n")
    now = datetime(2026, 5, 22, 9, 30)  # naive local
    assert in_deep_work_window(now=now, settings=workspace) is True


def test_guard_outside_window(workspace):
    _write_soul(workspace, "# Soul\n\n## Deep work hours\n09:00-11:00\n")
    now = datetime(2026, 5, 22, 12, 0)
    assert in_deep_work_window(now=now, settings=workspace) is False


def test_guard_at_start_is_inside(workspace):
    _write_soul(workspace, "# Soul\n\n## Deep work hours\n09:00-11:00\n")
    now = datetime(2026, 5, 22, 9, 0)
    assert in_deep_work_window(now=now, settings=workspace) is True


def test_guard_at_end_is_outside(workspace):
    """The window is half-open: end time is exclusive."""
    _write_soul(workspace, "# Soul\n\n## Deep work hours\n09:00-11:00\n")
    now = datetime(2026, 5, 22, 11, 0)
    assert in_deep_work_window(now=now, settings=workspace) is False


def test_guard_no_soul_returns_false(workspace):
    """Missing soul.md fails open — no silence by accident."""
    now = datetime(2026, 5, 22, 9, 30)
    assert in_deep_work_window(now=now, settings=workspace) is False


def test_guard_soul_without_section_returns_false(workspace):
    _write_soul(workspace, "# Soul\n\n## Voice\n- Direct.\n")
    now = datetime(2026, 5, 22, 9, 30)
    assert in_deep_work_window(now=now, settings=workspace) is False


def test_guard_crosses_midnight(workspace):
    _write_soul(workspace, "# Soul\n\n## Deep work hours\n22:00-02:00\n")
    assert in_deep_work_window(
        now=datetime(2026, 5, 22, 23, 30), settings=workspace
    ) is True
    assert in_deep_work_window(
        now=datetime(2026, 5, 22, 1, 0), settings=workspace
    ) is True
    assert in_deep_work_window(
        now=datetime(2026, 5, 22, 12, 0), settings=workspace
    ) is False


# --- SCHEDULES dict sanity --------------------------------------------------


def test_schedules_contain_core_rituals():
    assert "daily-start" in SCHEDULES
    assert "daily-close" in SCHEDULES
    assert "weekly-review" in SCHEDULES
    assert "drafts-gc" in SCHEDULES


def test_weekly_review_runs_on_friday():
    assert SCHEDULES["weekly-review"]["weekdays"] == [5]


def test_drafts_gc_supports_multi_word_command():
    """`drafts gc` is two words; install() must tolerate it."""
    cmd = SCHEDULES["drafts-gc"]["command"]
    assert cmd == "drafts gc" or cmd == ["drafts", "gc"]
