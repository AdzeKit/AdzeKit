import subprocess
from datetime import date

import pytest

from adzekit import Workspace, WorkspaceError, __version__, records
from adzekit.cli import main
from adzekit.shed import init
from adzekit.sync import sync

MON = date(2026, 9, 28)


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True,
                          check=True).stdout


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("ADZEKIT_WORKSPACE", raising=False)
    for key in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{key}_NAME", "t")
        monkeypatch.setenv(f"GIT_{key}_EMAIL", "t@t")
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def ws(tmp_path):
    return init(tmp_path / "shed")[0]


# --- init ----------------------------------------------------------------


def test_init_generates_contract_and_is_idempotent(ws):
    agents = (ws.root / "AGENTS.md").read_text()
    assert f"adzekit:begin v{__version__}" in agents and "## About me" in agents
    assert "at most 5" in agents and "at most 3" in agents  # rendered from settings
    assert "@AGENTS.md" in (ws.root / "CLAUDE.md").read_text()
    assert (ws.root / "skills/daily-start.md").is_file()
    assert (ws.root / ".git").is_dir()
    assert init(ws.root)[1] == []


def test_init_refreshes_only_the_managed_block(ws):
    agents = ws.root / "AGENTS.md"
    agents.write_text(agents.read_text().replace("<!-- Who you are", "I build agents.\n<!--"))
    (ws.root / ".adzekit").write_text("max_active_projects = 10\n")
    assert "AGENTS.md" in init(ws.root)[1]
    text = agents.read_text()
    assert "at most 10" in text and "I build agents." in text
    assert text.count("adzekit:begin") == 1


def test_init_respects_existing_files(tmp_path):
    root = tmp_path / "old"
    root.mkdir()
    (root / "CLAUDE.md").write_text("@AGENTS.md\n\nMy Claude notes.\n")
    (root / ".gitignore").write_text("*\n!*/\n!*.md\n")
    (root / "skills").mkdir()
    (root / "skills/daily-start.md").write_text("mine")
    init(root)
    assert (root / "CLAUDE.md").read_text() == "@AGENTS.md\n\nMy Claude notes.\n"
    assert (root / "skills/daily-start.md").read_text() == "mine"
    ignore = (root / ".gitignore").read_text()
    assert ignore.startswith("*\n") and ignore.index("!.adzekit") > ignore.index("*")
    # settings and merge rules must travel, even under an ignore-everything rule
    git(root, "add", "-A")
    tracked = git(root, "ls-files").split()
    assert ".adzekit" in tracked and ".gitattributes" in tracked


def test_records_merge_by_union(ws):
    for path in ("daily/2026-09-28.md", "loops/active.md", "projects/archive/x.md"):
        assert git(ws.root, "check-attr", "merge", path).strip().endswith("union"), path
    assert git(ws.root, "check-attr", "merge", "AGENTS.md").strip().endswith("unspecified")


def test_find_order(ws, tmp_path, monkeypatch):
    assert Workspace.find().root == ws.root  # global config written by init
    monkeypatch.chdir(ws.root / "skills")
    assert Workspace.find().root == ws.root  # enclosing folder
    monkeypatch.setenv("ADZEKIT_WORKSPACE", str(tmp_path / "missing"))
    with pytest.raises(WorkspaceError, match="no .adzekit"):
        Workspace.find()


# --- records -------------------------------------------------------------


def test_parse_real_world_loop_line():
    text = ("# Active Loops\n\n"
            "- [ ] (S) [2026-09-08] **Unblock #acme login** — IT on it (2026-09-12)\n"
            "  - [ ] nested notes are not loops\n"
            "- [x] [2026-13-40] bad date still parses\n")
    first, second = records.parse_loops(text)
    assert (first.size, first.opened, first.due) == ("S", date(2026, 9, 8), date(2026, 9, 12))
    assert first.title == "**Unblock #acme login** — IT on it" and first.overdue(MON)
    assert second.done and second.opened is None


def test_today_carries_forward_and_sweeps(ws):
    (ws.root / ".adzekit").write_text("max_daily_tasks = 2\n")
    ws.daily_path(date(2026, 9, 25)).parent.mkdir(exist_ok=True)
    ws.daily_path(date(2026, 9, 25)).write_text(
        "## Intention\n- [x] Done\n- [ ] A\n- [ ] B\n- [ ] C\n")
    (ws.root / "loops/active.md").write_text(
        "# Active Loops\n\nNotes stay.\n- [x] [2026-09-01] Sent it\n- [ ] [2026-09-02] Open\n")

    result = records.today(ws, MON)
    assert result.created and result.carried == ["A", "B"] and result.left_behind == ["C"]
    assert result.swept == ["- [x] [2026-09-01] Sent it"]
    assert records.intentions(result.path.read_text()) == (["A", "B"], [])
    assert (ws.root / "loops/active.md").read_text() == (
        "# Active Loops\n\nNotes stay.\n- [ ] [2026-09-02] Open\n")
    assert "## 2026-09-28\n- [x] [2026-09-01] Sent it" in (ws.root / "loops/archive.md").read_text()

    again = records.today(ws, MON)
    assert not again.created and again.swept == []


def test_today_archives_old_dailies(ws):
    (ws.root / ".adzekit").write_text("archive_daily_days = 30\n")
    (ws.root / "daily").mkdir(exist_ok=True)
    old = ws.daily_path(date(2026, 7, 1))       # 89 days before MON → archived
    boundary = ws.daily_path(date(2026, 8, 29))  # exactly 30 days before → kept
    old.write_text("# old\n")
    boundary.write_text("# boundary\n")

    result = records.today(ws, MON)
    assert result.archived == ["2026-07-01.md"]
    assert not old.exists()
    assert (ws.root / "daily/archive/2026-07-01.md").read_text() == "# old\n"
    assert boundary.exists()  # on the cutoff stays put
    assert result.path.exists()  # today's own note is never archived


def test_review_gathers_the_week(ws):
    (ws.root / ".adzekit").write_text("stale_loop_days = 3\n")
    (ws.root / "daily").mkdir(exist_ok=True)
    ws.daily_path(date(2026, 9, 29)).write_text("## Intention\n- [x] Shipped demo\n- [ ] Not yet\n")
    (ws.root / "loops/active.md").write_text(
        "- [ ] [2026-09-01] Old promise\n- [ ] [2026-09-28] Fresh\n- [x] [2026-09-28] Finished\n")
    records.sweep(ws, date(2026, 9, 30))
    (ws.root / "projects").mkdir()
    (ws.root / "projects/quiet.md").write_text("# Quiet\n\n## Log\n- 2026-08-01: Created.\n")

    text = records.build_review(ws, date(2026, 10, 1))
    assert text.startswith("# Review 2026-W40 (Sep 28 – Oct 04)")
    assert "- Shipped demo" in text and "Not yet" not in text and "- Finished" in text
    assert "Old promise — open 30d" in text and "Fresh" not in text
    assert "quiet — last dated 2026-08-01" in text
    path, created = records.write_review(ws, date(2026, 10, 1))
    assert created and path.name == "2026-W40.md"
    assert not records.write_review(ws, date(2026, 10, 1))[1]


def test_last_touched_ignores_future_dates(ws):
    (ws.root / "projects").mkdir()
    note = "# Acme\n- 2026-09-17: done\n- 2026-10-30: workshop\n"
    (ws.root / "projects/acme.md").write_text(note)
    [project] = records.active_projects(ws, MON)
    assert project.title == "Acme" and project.last_touched == date(2026, 9, 17)


# --- sync ----------------------------------------------------------------


@pytest.fixture
def two_devices(tmp_path, ws):
    """A laptop shed pushed to a bare remote, and a phone that joined it."""
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    git(ws.root, "remote", "add", "origin", str(remote))
    (ws.root / "daily").mkdir(exist_ok=True)
    ws.daily_path(MON).write_text("# Mon\n\n## Log\n- seed\n\n## Reflection\n")
    assert sync(ws) == ["committed local changes", "pushed"]
    phone, _ = init(tmp_path / "phone", remote=str(remote))
    return ws, phone


def test_join_existing_shed_by_clone(two_devices):
    laptop, phone = two_devices
    assert phone.daily_path(MON).read_text() == laptop.daily_path(MON).read_text()
    assert init(phone.root)[1] == []  # nothing to regenerate on the second device


def test_concurrent_appends_keep_both_lines(two_devices):
    laptop, phone = two_devices
    for device, line in ((phone, "- phone note"), (laptop, "- laptop note")):
        path = device.daily_path(MON)
        path.write_text(path.read_text().replace("- seed\n", f"- seed\n{line}\n"))
    sync(phone)
    assert sync(laptop) == ["committed local changes", "pulled", "pushed"]
    log = laptop.daily_path(MON).read_text()
    assert "- phone note" in log and "- laptop note" in log and "<<<<" not in log
    sync(phone)
    assert phone.daily_path(MON).read_text() == log


def test_unmergeable_change_aborts_cleanly(two_devices):
    laptop, phone = two_devices
    for device, text in ((phone, "phone rules"), (laptop, "laptop rules")):
        skill = device.root / "skills/capture.md"
        skill.write_text(skill.read_text().replace("# Capture", f"# Capture ({text})"))
    sync(phone)
    with pytest.raises(WorkspaceError, match=r"Nothing was lost(.|\n)*skills/capture.md"):
        sync(laptop)
    assert not (laptop.root / ".git/rebase-merge").exists()
    assert "laptop rules" in (laptop.root / "skills/capture.md").read_text()
    assert git(laptop.root, "status", "--porcelain") == ""  # committed, not stranded


def test_sync_without_remote_commits_locally(ws):
    assert sync(ws) == ["committed local changes", "no origin remote; kept local"]
    assert sync(ws) == ["no origin remote; kept local"]


def test_sync_only_pushes_to_origin(ws, tmp_path):
    parked = tmp_path / "parked.git"
    git(tmp_path, "init", "-q", "--bare", str(parked))
    git(ws.root, "remote", "add", "personal-legacy", str(parked))
    assert sync(ws)[-1] == "no origin remote; kept local"
    assert git(parked, "rev-list", "--all") == ""  # nothing was pushed


def test_stock_symlink_is_never_committed(ws, tmp_path):
    drive = tmp_path / "drive"
    drive.mkdir()
    (ws.root / "stock").symlink_to(drive)
    sync(ws)
    assert "stock" not in git(ws.root, "ls-files").split()


def test_sync_refuses_a_stuck_repository(ws):
    sync(ws)
    (ws.root / ".git/rebase-merge").mkdir()
    with pytest.raises(WorkspaceError, match="rebase is already in progress"):
        sync(ws)


# --- cli -----------------------------------------------------------------


def test_cli_round_trip(ws, capsys):
    (ws.root / "loops/active.md").write_text("- [ ] [2020-01-01] Reply to Ana (2020-01-02)\n")
    assert main(["-w", str(ws.root), "today"]) == 0
    assert main(["-w", str(ws.root), "status"]) == 0
    out = capsys.readouterr().out
    assert "1 open, 1 overdue, 1 stale" in out and "overdue: Reply to Ana" in out
    assert main(["-w", str(ws.root / "nope"), "status"]) == 1


# --- several sheds ---------------------------------------------------------


def test_sheds_register_by_name_and_act_together(tmp_path, capsys):
    work, _ = init(tmp_path / "work-shed", name="work")
    life, _ = init(tmp_path / "life-shed", name="life")
    assert work.name == "work" and "name = work" in (work.root / ".adzekit").read_text()
    assert "the **life** shed" in (life.root / "AGENTS.md").read_text()
    assert Workspace.find("life").root == life.root  # -w accepts a name
    assert [ws.name for ws in Workspace.targets()] == ["work", "life"]

    assert main(["status"]) == 0  # outside any shed: every registered shed
    out = capsys.readouterr().out
    assert "== work" in out and "== life" in out


def test_inside_a_shed_only_that_shed_is_touched(tmp_path, monkeypatch):
    work, _ = init(tmp_path / "work", name="work")
    life, _ = init(tmp_path / "life", name="life")
    monkeypatch.chdir(work.root / "skills")
    assert [ws.name for ws in Workspace.targets()] == ["work"]
    assert main(["today"]) == 0
    assert (work.root / "daily").is_dir() and not (life.root / "daily").exists()


def test_register_replaces_legacy_entry_for_same_folder(tmp_path):
    root = tmp_path / "old-shed"
    config = tmp_path / "home/.config/adzekit/config"
    config.parent.mkdir(parents=True)
    config.write_text(f"shed = {root}\n")
    init(root, name="work")
    assert config.read_text() == f"work = {root.resolve()}\n"
    assert init(root)[1] == []  # the name travels in .adzekit; nothing to redo


def test_sync_keeps_going_when_one_shed_fails(tmp_path, capsys):
    good, _ = init(tmp_path / "good", name="good")
    bad, _ = init(tmp_path / "bad", name="bad")
    (bad.root / ".git/rebase-merge").mkdir(parents=True)
    assert main(["sync"]) == 1
    captured = capsys.readouterr()
    assert "rebase is already in progress" in captured.err
    assert "sync failed for: bad" in captured.err
    assert "committed local changes" in captured.out
    assert subprocess.run(["git", "-C", str(good.root), "status", "--porcelain"],
                          capture_output=True, text=True).stdout == ""


def test_shed_names_are_validated(tmp_path):
    with pytest.raises(WorkspaceError, match="lowercase"):
        init(tmp_path / "x", name="My Life")
