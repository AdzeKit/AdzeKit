"""Tests for hard WIP/SLA enforcement and Pillar B mechanics."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from adzekit.modules import wip
from adzekit.modules.bench import stale_bench_items
from adzekit.modules.daily import (
    _apply_triage_decisions,
    daily_close,
    daily_start,
    parse_triage_decisions,
)
from adzekit.workspace import create_project


def _seed_active_projects(settings, n: int) -> None:
    for i in range(n):
        create_project(f"proj-{i}", title=f"Project {i}", backlog=False, settings=settings)


class TestWIPGate:
    def test_can_activate_under_cap(self, workspace):
        allowed, _ = wip.can_activate(workspace)
        assert allowed

    def test_can_activate_at_cap(self, workspace):
        _seed_active_projects(workspace, workspace.max_active_projects)
        allowed, reason = wip.can_activate(workspace)
        assert not allowed
        assert "WIP limit reached" in reason

    def test_demote_project_moves_to_backlog(self, workspace):
        create_project("alpha", title="Alpha", backlog=False, settings=workspace)
        path = wip.demote_project("alpha", settings=workspace)
        assert path == workspace.backlog_dir / "alpha.md"
        assert not (workspace.active_dir / "alpha.md").exists()

    def test_demote_missing_raises(self, workspace):
        with pytest.raises(FileNotFoundError):
            wip.demote_project("ghost", settings=workspace)

    def test_activate_at_cap_raises(self, workspace):
        _seed_active_projects(workspace, workspace.max_active_projects)
        create_project("waiting", title="Waiting", backlog=True, settings=workspace)
        with pytest.raises(ValueError, match="WIP limit reached"):
            wip.activate_project("waiting", settings=workspace)


class TestStaleProjects:
    def test_no_stale_when_fresh(self, workspace):
        create_project("fresh", title="Fresh", backlog=False, settings=workspace)
        result = wip.stale_active_projects(workspace, days=7)
        # Fresh files have inactive=0; with threshold 7, none should appear.
        assert result == []

    def test_detects_old_mtime(self, workspace):
        create_project("ancient", title="Ancient", backlog=False, settings=workspace)
        path = workspace.active_dir / "ancient.md"
        # Backdate the mtime to 30 days ago.
        old = (date.today() - timedelta(days=30))
        import os
        import time
        epoch = time.mktime(old.timetuple())
        os.utime(path, (epoch, epoch))

        result = wip.stale_active_projects(workspace, days=7)
        assert len(result) == 1
        proj, days = result[0]
        assert proj.slug == "ancient"
        assert days >= 25  # rounding tolerance


class TestStaleBenchItems:
    def test_finds_old_items(self, workspace):
        old = (date.today() - timedelta(days=14)).isoformat()
        recent = (date.today() - timedelta(days=2)).isoformat()
        workspace.bench_path.write_text(
            "# Bench\n\n## Pending\n\n"
            f"- [ ] [{old}] Old triage thing (foo.md)\n"
            f"- [ ] [{recent}] Recent triage thing (bar.md)\n"
        )
        result = stale_bench_items(workspace, days=7)
        assert len(result) == 1
        assert result[0]["text"] == "Old triage thing"
        assert result[0]["days"] >= 14


class TestTriagePanel:
    def test_no_triage_when_clean(self, workspace):
        path, summary = daily_start(settings=workspace)
        content = path.read_text()
        assert "## Triage" not in content
        assert summary["triage_count"] == 0

    def test_triage_block_with_overdue_loop(self, workspace):
        d = (date.today() - timedelta(days=20)).isoformat()
        due = (date.today() - timedelta(days=10)).isoformat()
        workspace.loops_active.write_text(
            f"# Active Loops\n\n- [ ] (S) [{d}] Stale promise ({due})\n"
        )
        path, summary = daily_start(settings=workspace)
        content = path.read_text()
        assert "## Triage" in content
        assert "OVERDUE" in content
        assert "Stale promise" in content
        assert summary["triage_count"] == 1


class TestParseTriageDecisions:
    def test_unresolved_when_unchecked(self):
        text = "## Triage (must resolve before daily-close)\n" \
               "- [ ] OVERDUE 12d: Manulife KARL → kill / defer / promote\n"
        decisions = parse_triage_decisions(text)
        assert len(decisions) == 1
        assert decisions[0]["resolved"] is False

    def test_unresolved_when_checked_but_placeholder(self):
        text = "## Triage\n- [x] OVERDUE 12d: Manulife KARL → kill / defer / promote\n"
        decisions = parse_triage_decisions(text)
        assert decisions[0]["resolved"] is False

    def test_resolved_when_decided(self):
        text = "## Triage\n- [x] OVERDUE 12d: Manulife KARL → kill\n"
        decisions = parse_triage_decisions(text)
        assert decisions[0]["resolved"] is True
        assert decisions[0]["decision"] == "kill"

    def test_handles_stale_kind(self):
        text = "## Triage\n- [x] STALE 22d: aer-compliance → kill\n"
        decisions = parse_triage_decisions(text)
        assert decisions[0]["resolved"] is True
        assert decisions[0]["kind"] == "STALE"

    def test_stops_at_next_section(self):
        text = (
            "## Triage\n- [ ] OVERDUE 1d: a → kill / defer / promote\n"
            "## Morning: Intention\n- [ ] something else\n"
        )
        decisions = parse_triage_decisions(text)
        assert len(decisions) == 1


class TestDailyCloseEnforcement:
    def _seed_note(self, workspace, content: str) -> None:
        today = date.today().isoformat()
        path = workspace.daily_dir / f"{today}.md"
        path.write_text(content, encoding="utf-8")

    def test_blocks_on_unresolved_triage(self, workspace):
        self._seed_note(workspace,
            "# day\n\n"
            "## Triage (must resolve before daily-close)\n"
            "- [ ] OVERDUE 5d: thing → kill / defer / promote\n\n"
            "## Morning: Intention\n- [ ] do stuff\n\n"
            "## Log\n\n## Evening: Reflection\n- **Finished:**\n"
        )
        ok, summary = daily_close(settings=workspace)
        assert ok is False
        assert summary["triage_blocked"] is True
        assert summary["unresolved_count"] == 1

    def test_succeeds_with_resolved_triage(self, workspace):
        # Seed an active loop so the "kill" decision can match
        d = (date.today() - timedelta(days=20)).isoformat()
        due = (date.today() - timedelta(days=10)).isoformat()
        workspace.loops_active.write_text(
            f"# Active Loops\n\n- [ ] (S) [{d}] Stale promise ({due})\n"
        )
        self._seed_note(workspace,
            "# day\n\n"
            "## Triage (must resolve before daily-close)\n"
            "- [x] OVERDUE 10d: Stale promise → kill\n\n"
            "## Morning: Intention\n- [ ] do stuff\n\n"
            "## Log\n\n## Evening: Reflection\n- **Finished:**\n"
        )
        ok, summary = daily_close(settings=workspace)
        assert ok is True
        assert summary["triage_resolved"] == 1
        # The kill should have closed the loop and swept it.
        active = workspace.loops_active.read_text()
        assert "Stale promise" not in active or "[x]" in active


class TestApplyTriageDecisions:
    def test_kill_overdue_marks_loop_closed(self, workspace):
        d = (date.today() - timedelta(days=10)).isoformat()
        due = (date.today() - timedelta(days=3)).isoformat()
        workspace.loops_active.write_text(
            f"# Active Loops\n\n- [ ] (XS) [{d}] Forgotten thing ({due})\n"
        )
        decisions = [{
            "resolved": True, "kind": "OVERDUE", "days": 3,
            "subject": "Forgotten thing", "decision": "kill",
        }]
        counts = _apply_triage_decisions(decisions, workspace)
        assert counts["killed"] == 1
        text = workspace.loops_active.read_text()
        assert "[x]" in text

    def test_kill_stale_archives_project(self, workspace):
        create_project("doomed", title="Doomed", backlog=False, settings=workspace)
        decisions = [{
            "resolved": True, "kind": "STALE", "days": 30,
            "subject": "doomed", "decision": "kill",
        }]
        counts = _apply_triage_decisions(decisions, workspace)
        assert counts["killed"] == 1
        assert not (workspace.active_dir / "doomed.md").exists()
        assert (workspace.archive_dir / "doomed.md").exists()
