"""Tests for daily-start and daily-close."""

from datetime import date, timedelta

from adzekit.cli import main
from adzekit.modules.daily import daily_close, daily_start


class TestDailyStart:
    def test_creates_note(self, workspace):
        path, summary = daily_start(settings=workspace)
        assert path is not None
        assert path.exists()
        assert not summary.get("already_exists")

    def test_stops_if_note_exists(self, workspace):
        today = date.today()
        note = workspace.daily_dir / f"{today.isoformat()}.md"
        note.write_text("# existing\n")

        path, summary = daily_start(settings=workspace)
        assert path is None
        assert summary["already_exists"] is True

    def test_carries_intentions_from_yesterday(self, workspace):
        yesterday = date.today() - timedelta(days=1)
        note = workspace.daily_dir / f"{yesterday.isoformat()}.md"
        note.write_text(
            f"# {yesterday.isoformat()} Test\n\n"
            "## Morning: Intention\n"
            "- [ ] Carry this forward\n"
            "- [x] Already done\n\n"
            "## Log\n\n"
            "## Evening: Reflection\n"
            "- **Finished:**\n"
            "- **Blocked:**\n"
            "- **Tomorrow:** Do next thing\n"
        )

        path, summary = daily_start(settings=workspace)
        content = path.read_text()
        assert "Carry this forward" in content
        assert "Already done" not in content
        assert summary["carried_count"] == 1
        assert summary["tomorrow_count"] == 1

    def test_includes_overdue_loops(self, workspace):
        yesterday = date.today() - timedelta(days=1)
        workspace.loops_active.write_text(
            "# Active Loops\n\n"
            f"- [ ] (S) [{(date.today() - timedelta(days=5)).isoformat()}] "
            f"Overdue task ({yesterday.isoformat()})\n"
        )

        path, summary = daily_start(settings=workspace)
        content = path.read_text()
        assert "Overdue task" in content
        assert "OVERDUE" in content
        assert summary["overdue_count"] >= 1

    def test_includes_due_today_loops(self, workspace):
        today = date.today()
        workspace.loops_active.write_text(
            "# Active Loops\n\n"
            f"- [ ] (M) [{today.isoformat()}] Due today task "
            f"({today.isoformat()})\n"
        )

        path, summary = daily_start(settings=workspace)
        content = path.read_text()
        assert "Due today task" in content
        assert "due today" in content

    def test_max_five_tasks(self, workspace):
        lines = ["# Active Loops\n"]
        for i in range(8):
            d = (date.today() - timedelta(days=10)).isoformat()
            due = (date.today() - timedelta(days=1)).isoformat()
            lines.append(f"- [ ] (XS) [{d}] Task {i} ({due})\n")
        workspace.loops_active.write_text("\n".join(lines))

        path, _ = daily_start(settings=workspace)
        content = path.read_text()
        # Count `- [ ]` only inside the Morning: Intention section. The new
        # Triage block can also contain unchecked items (one per overdue loop)
        # but the WIP cap of 5 applies only to the day's intentions.
        morning = content.split("## Morning: Intention", 1)[1].split("## Log", 1)[0]
        assert morning.count("- [ ]") <= 5

    def test_has_section_headers(self, workspace):
        path, _ = daily_start(settings=workspace)
        content = path.read_text()
        assert "## Morning: Intention" in content
        assert "## Log" in content
        assert "## Evening: Reflection" in content

    def test_lookback_across_gap(self, workspace):
        today = date.today()
        three_ago = today - timedelta(days=3)
        note = workspace.daily_dir / f"{three_ago.isoformat()}.md"
        note.write_text(
            f"# {three_ago.isoformat()} Test\n\n"
            "## Morning: Intention\n"
            "- [ ] Weekend carry\n\n"
            "## Log\n\n"
            "## Evening: Reflection\n"
            "- **Finished:**\n"
            "- **Blocked:**\n"
            "- **Tomorrow:**\n"
        )

        path, summary = daily_start(target_date=today, settings=workspace)
        content = path.read_text()
        assert "Weekend carry" in content

    def test_deduplicates_tasks(self, workspace):
        yesterday = date.today() - timedelta(days=1)
        workspace.daily_dir.mkdir(parents=True, exist_ok=True)
        note = workspace.daily_dir / f"{yesterday.isoformat()}.md"
        note.write_text(
            f"# {yesterday.isoformat()} Test\n\n"
            "## Morning: Intention\n"
            "- [ ] Same task name\n\n"
            "## Log\n\n"
            "## Evening: Reflection\n"
            "- **Tomorrow:** Same task name\n"
        )

        path, _ = daily_start(settings=workspace)
        content = path.read_text()
        assert content.count("Same task name") == 1

    def test_cli_daily_start(self, tmp_path, capsys):
        main(["init", str(tmp_path / "shed")])
        today = date.today()
        note = tmp_path / "shed" / "daily" / f"{today.isoformat()}.md"
        if note.exists():
            note.unlink()

        main(["--shed", str(tmp_path / "shed"), "daily-start"])
        output = capsys.readouterr().out
        assert "Daily Start" in output


class TestDailyClose:
    def test_appends_end_line(self, workspace):
        today = date.today()
        note = workspace.daily_dir / f"{today.isoformat()}.md"
        note.write_text(
            f"# {today.isoformat()} Test\n\n"
            "## Morning: Intention\n"
            "- [x] Done thing\n"
            "- [ ] Open thing\n\n"
            "## Log\n"
            "- 09:00 Did stuff\n\n"
            "## Evening: Reflection\n"
            "- **Finished:**\n"
            "- **Blocked:**\n"
            "- **Tomorrow:**\n"
        )

        success, summary = daily_close(settings=workspace)
        assert success is True
        content = note.read_text()
        assert "> End:" in content
        assert summary["done_count"] == 1
        assert summary["open_count"] == 1

    def test_stops_if_no_note(self, workspace):
        success, summary = daily_close(settings=workspace)
        assert success is False
        assert summary["no_note"] is True

    def test_stops_if_already_closed(self, workspace):
        today = date.today()
        note = workspace.daily_dir / f"{today.isoformat()}.md"
        note.write_text(
            f"# {today.isoformat()} Test\n\n"
            "> End: Energy 3/5. 1 done, 0 open. Tomorrow: rest.\n"
        )

        success, summary = daily_close(settings=workspace)
        assert success is False
        assert summary["already_closed"] is True

    def test_sweeps_closed_loops(self, workspace):
        today = date.today()
        note = workspace.daily_dir / f"{today.isoformat()}.md"
        note.write_text(
            f"# {today.isoformat()} Test\n\n## Log\n\n"
            "## Evening: Reflection\n"
        )
        workspace.loops_active.write_text(
            "# Active Loops\n\n"
            f"- [x] (S) [{today.isoformat()}] Closed loop\n"
            f"- [ ] (M) [{today.isoformat()}] Open loop\n"
        )

        success, summary = daily_close(settings=workspace)
        assert success is True
        assert summary["swept_count"] == 1
        active_content = workspace.loops_active.read_text()
        assert "Closed loop" not in active_content
        assert "Open loop" in active_content

    def test_tomorrow_suggestion_from_loops(self, workspace):
        today = date.today()
        tomorrow = today + timedelta(days=1)
        note = workspace.daily_dir / f"{today.isoformat()}.md"
        note.write_text(
            f"# {today.isoformat()} Test\n\n## Log\n\n"
            "## Evening: Reflection\n"
        )
        workspace.loops_active.write_text(
            "# Active Loops\n\n"
            f"- [ ] (S) [{today.isoformat()}] Tomorrow loop "
            f"({tomorrow.isoformat()})\n"
        )

        success, summary = daily_close(settings=workspace)
        assert success is True
        assert "Tomorrow loop" in summary["tomorrow_suggestion"]

    def test_energy_placeholder(self, workspace):
        today = date.today()
        note = workspace.daily_dir / f"{today.isoformat()}.md"
        note.write_text(f"# {today.isoformat()} Test\n\n## Log\n")

        daily_close(settings=workspace)
        content = note.read_text()
        assert "Energy /5" in content

    def test_cli_daily_close(self, tmp_path, capsys):
        main(["init", str(tmp_path / "shed")])
        main(["--shed", str(tmp_path / "shed"), "daily-close"])
        output = capsys.readouterr().out
        assert "Daily Close" in output or "already has" in output
