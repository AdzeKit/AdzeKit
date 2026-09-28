from datetime import date

import pytest

from adzekit import Workspace, WorkspaceError, daily, loops, projects, review
from adzekit.cli import main

MON = date(2026, 9, 28)


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("ADZEKIT_WORKSPACE", raising=False)
    monkeypatch.delenv("ADZEKIT_SHED", raising=False)
    workspace, _ = Workspace.init(tmp_path / "ws")
    return workspace


# --- workspace -----------------------------------------------------------


def test_init_creates_contract_and_is_idempotent(ws):
    for name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md", ".gitignore", "loops/active.md",
                 "skills/daily-start.md", "projects/backlog"):
        assert (ws.root / name).exists(), name
    assert "@AGENTS.md" in (ws.root / "CLAUDE.md").read_text()
    (ws.root / "AGENTS.md").write_text("mine")
    _, created = Workspace.init(ws.root)
    assert created == []
    assert (ws.root / "AGENTS.md").read_text() == "mine"


def test_init_records_global_config(ws, tmp_path):
    config = tmp_path / "home" / ".config" / "adzekit" / "config"
    assert config.read_text().strip() == f"workspace = {ws.root}"


def test_find_order(ws, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert Workspace.find().root == ws.root  # global config
    monkeypatch.chdir(ws.root / "daily")
    assert Workspace.find().root == ws.root  # enclosing folder
    monkeypatch.setenv("ADZEKIT_SHED", str(tmp_path / "missing"))
    with pytest.raises(WorkspaceError, match="no .adzekit"):
        Workspace.find()


def test_settings_read_marker_with_defaults(ws):
    ws.marker.write_text("max_active_projects = 10\nmax_daily_tasks = oops\n")
    assert ws.setting("max_active_projects") == 10
    assert ws.setting("max_daily_tasks") == 5
    assert ws.setting("stale_loop_days") == 7


# --- loops ---------------------------------------------------------------


def test_parse_real_world_line():
    text = (
        "# Active Loops\n\n"
        "- [ ] (S) [2026-09-08] **Unblock #pcc login** — IT on it (2026-09-12)\n"
        "  - [ ] nested notes are not loops\n"
        "- [x] [2026-13-40] bad date still parses\n"
        "free text is ignored\n"
    )
    first, second = loops.parse(text)
    assert first.size == "S" and first.opened == date(2026, 9, 8)
    assert first.title == "**Unblock #pcc login** — IT on it"
    assert first.due == date(2026, 9, 12) and first.overdue(MON)
    assert second.done and second.opened is None


def test_add_close_sweep_preserves_other_lines(ws):
    ws.loops_file.write_text("# Active Loops\n\nNotes stay put.\n\n- [ ] [2026-09-01] Old one\n")
    loops.add(ws, "Send estimate to Ana", today=MON, size="m", due=date(2026, 10, 1))
    text = ws.loops_file.read_text()
    assert "- [ ] (M) [2026-09-28] Send estimate to Ana (2026-10-01)" in text
    assert text.index("Old one") < text.index("Send estimate")

    assert loops.close(ws, "estimate").title == "Send estimate to Ana"
    assert loops.sweep(ws, today=MON) == [
        "- [x] (M) [2026-09-28] Send estimate to Ana (2026-10-01)"
    ]
    assert "Notes stay put." in ws.loops_file.read_text()
    assert [lp.title for lp in loops.open_loops(ws)] == ["Old one"]

    loops.close(ws, "1")
    loops.sweep(ws, today=MON)
    archive = ws.loops_archive.read_text()
    assert archive.count("## 2026-09-28") == 1
    assert "Old one" in archive and "Send estimate" in archive


def test_close_rejects_ambiguous_and_missing(ws):
    loops.add(ws, "Call Ana", today=MON)
    loops.add(ws, "Email Ana", today=MON)
    with pytest.raises(WorkspaceError, match="2 loops match"):
        loops.close(ws, "ana")
    with pytest.raises(WorkspaceError, match="No open loop #9"):
        loops.close(ws, "9")


# --- daily ---------------------------------------------------------------


def test_today_carries_unfinished_up_to_cap(ws):
    ws.marker.write_text("max_daily_tasks = 2\n")
    ws.daily_path(date(2026, 9, 25)).write_text(
        "# 2026-09-25 Friday\n\n## Intention\n- [x] Done\n- [ ] A\n- [ ] B\n- [ ] C\n\n## Log\n"
    )
    result = daily.today(ws, MON)
    assert result.created and result.carried == ["A", "B"] and result.left_behind == ["C"]
    assert daily.intentions(result.path.read_text()) == (["A", "B"], [])
    assert not daily.today(ws, MON).created


def test_log_appends_inside_section(ws):
    daily.log(ws, "first", MON)
    daily.log(ws, "second", MON)
    lines = ws.daily_path(MON).read_text().splitlines()
    log = lines.index("## Log")
    assert lines[log + 1 : log + 4] == ["- first", "- second", ""]
    assert lines[log + 4] == "## Reflection"


# --- projects ------------------------------------------------------------


def test_project_cap_and_moves(ws):
    ws.marker.write_text("max_active_projects = 1\n")
    projects.new(ws, "acme-poc", today=MON)
    with pytest.raises(WorkspaceError, match="1/1 active"):
        projects.new(ws, "globex", today=MON)
    projects.new(ws, "globex", today=MON, state="backlog")
    with pytest.raises(WorkspaceError, match="already exists"):
        projects.new(ws, "globex", today=MON)
    projects.move(ws, "acme-poc", "archive")
    projects.move(ws, "globex", "active")
    [active] = projects.load(ws, "active", MON)
    assert active.slug == "globex" and active.title == "Globex"
    assert active.last_touched == MON


def test_last_touched_ignores_future_dates():
    text = "- 2026-09-17: done\n- 2026-10-30: planned workshop\n"
    assert projects.last_touched(text, MON) == date(2026, 9, 17)


# --- review --------------------------------------------------------------


def test_review_collects_week(ws):
    ws.marker.write_text("stale_loop_days = 3\n")
    ws.daily_path(date(2026, 9, 29)).write_text("## Intention\n- [x] Shipped demo\n- [ ] Not yet\n")
    loops.add(ws, "Old promise", today=date(2026, 9, 1))
    loops.add(ws, "Fresh promise", today=MON)
    loops.add(ws, "Finished thing", today=MON)
    loops.close(ws, "Finished")
    loops.sweep(ws, today=date(2026, 9, 30))
    projects.new(ws, "quiet", today=date(2026, 8, 1))

    text = review.build(ws, date(2026, 10, 1))
    assert text.startswith("# Review 2026-W40 (Sep 28 – Oct 04)")
    assert "- Shipped demo" in text and "Not yet" not in text
    assert "- Finished thing" in text
    assert "Old promise — open 30d" in text and "Fresh promise" not in text
    assert "quiet — last dated 2026-08-01" in text

    path, created = review.write(ws, date(2026, 10, 1))
    assert created and not review.write(ws, date(2026, 10, 1))[1]
    assert path.name == "2026-W40.md"


# --- cli -----------------------------------------------------------------


def test_cli_round_trip(ws, capsys):
    base = ["-w", str(ws.root)]
    assert main(base + ["loop", "add", "Reply", "to", "Ana", "--due", "2020-01-01"]) == 0
    assert main(base + ["log", "Met", "Ana"]) == 0
    assert main(base + ["status"]) == 0
    out = capsys.readouterr().out
    assert "1 open, 1 overdue" in out and "overdue: Reply to Ana" in out
    assert main(base + ["loop", "close", "nothing"]) == 1
    assert "No open loop matches" in capsys.readouterr().err
