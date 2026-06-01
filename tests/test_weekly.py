"""Tests for weekly review and pulse summary generation."""

from __future__ import annotations

from datetime import date, timedelta

from adzekit.modules.weekly import extract_pulse, render_pulse_markdown, run_weekly_review


def _write_daily(workspace, d: date, body: str) -> None:
    path = workspace.daily_dir / f"{d.isoformat()}.md"
    path.write_text(body, encoding="utf-8")


def test_extract_pulse_harvests_completed_tasks_and_overdue_loops(workspace):
    target = date(2026, 5, 30)  # Friday
    monday = date(2026, 5, 26)
    _write_daily(
        workspace,
        monday,
        """# 2026-05-26 Monday

## Intention
- [x] Ship model landscape repo
- [ ] Southbow ML profiling

## Log
- Closed out Southbow baseline run

## Reflection
- **Blocked:** Waiting on customer data access
""",
    )
    due = (target - timedelta(days=2)).isoformat()
    workspace.loops_active.write_text(
        f"- [ ] (S) [{monday.isoformat()}] Reply to Scotiabank on governance doc ({due})\n",
        encoding="utf-8",
    )

    pulse = extract_pulse(workspace, target=target)

    assert any("Ship model landscape" in item for item in pulse.proud)
    assert any("Overdue" in item for item in pulse.focus)
    assert any("Blocked" in item or "customer data" in item for item in pulse.blockers)


def test_render_pulse_markdown_includes_sections(workspace):
    data = extract_pulse(workspace, target=date(2026, 5, 30))
    body = render_pulse_markdown(data, generated=date(2026, 5, 30))

    assert "## What did you get done this week that you're proud of?" in body
    assert "## What's your top focus for next week?" in body
    assert "## Any blockers or challenges you're facing?" in body


def test_run_weekly_review_writes_pulse_and_archives_old_dailies(workspace):
    target = date(2026, 6, 1)
    old = target - timedelta(days=20)
    recent = target - timedelta(days=5)
    (workspace.daily_dir / f"{old.isoformat()}.md").write_text("# Old\n")
    (workspace.daily_dir / f"{recent.isoformat()}.md").write_text("# Recent\n")
    _write_daily(
        workspace,
        target - timedelta(days=1),
        """# Recent day

## Intention
- [x] Finish weekly prep
""",
    )

    summary = run_weekly_review(workspace, target=target)

    pulse_path = workspace.reviews_dir / f"{target.isocalendar()[0]}-W{target.isocalendar()[1]:02d}-pulse.md"
    assert summary["pulse_path"] == pulse_path
    assert pulse_path.exists()
    assert not (workspace.daily_dir / f"{old.isoformat()}.md").exists()
    assert (workspace.daily_archive_dir / f"{old.isoformat()}.md").exists()
    assert (workspace.daily_dir / f"{recent.isoformat()}.md").exists()


def test_cli_weekly_review(tmp_path, capsys):
    from adzekit.cli import main

    target = tmp_path / "shed"
    main(["init", str(target)])
    main(["--shed", str(target), "weekly-review", "--date", "2026-06-01"])
    output = capsys.readouterr().out
    assert "Weekly Review" in output
    week_id = date(2026, 6, 1).isocalendar()
    pulse_name = f"{week_id[0]}-W{week_id[1]:02d}-pulse.md"
    assert (target / "reviews" / pulse_name).exists()
