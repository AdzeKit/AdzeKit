"""Tests for the loop system.

Principle 2: Close Every Loop. Tests cover the full lifecycle:
capture, track, close.
"""

from datetime import date, timedelta

from adzekit.models import Loop
from adzekit.modules.loops import (
    add_loop,
    close_loop,
    get_open_loops,
    get_overdue_loops,
    loop_stats,
)


def _make_loop(title="Test loop", who="Alice", days_ago=0, due_in=3):
    return Loop(
        date=date.today() - timedelta(days=days_ago),
        title=title,
        who=who,
        what="Test commitment",
        due=date.today() + timedelta(days=due_in),
        status="Open",
    )


def test_add_and_read_loop(workspace):
    loop = _make_loop()
    add_loop(loop, workspace)
    loops = get_open_loops(workspace)
    assert len(loops) == 1
    assert loops[0].title == "Test loop"
    assert loops[0].who == "Alice"


def test_close_loop(workspace):
    add_loop(_make_loop(title="Close me"), workspace)
    add_loop(_make_loop(title="Keep me"), workspace)
    assert len(get_open_loops(workspace)) == 2

    result = close_loop("Close me", workspace)
    assert result is True

    remaining = get_open_loops(workspace)
    assert len(remaining) == 1
    assert remaining[0].title == "Keep me"

    # Verify it ended up in closed/
    closed_files = list(workspace.loops_closed_dir.glob("*.md"))
    assert len(closed_files) == 1


def test_close_nonexistent_loop(workspace):
    result = close_loop("Does not exist", workspace)
    assert result is False


def test_overdue_loops(workspace):
    # Due yesterday
    overdue = _make_loop(title="Late", due_in=-1)
    add_loop(overdue, workspace)
    # Due tomorrow
    ok = _make_loop(title="On time", due_in=1)
    add_loop(ok, workspace)

    result = get_overdue_loops(workspace)
    assert len(result) == 1
    assert result[0].title == "Late"


def test_loop_stats(workspace):
    add_loop(_make_loop(title="A"), workspace)
    add_loop(_make_loop(title="B"), workspace)
    stats = loop_stats(workspace)
    assert stats["open"] == 2
    assert "waiting" not in stats
