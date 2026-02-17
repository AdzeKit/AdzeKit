"""Tests for the AdzeKit CLI."""

from datetime import date

from adzekit.cli import main


def test_init_creates_vault(tmp_path):
    target = tmp_path / "vault"
    main(["init", str(target)])

    assert (target / "inbox.md").exists()
    assert (target / "loops" / "open.md").exists()
    assert (target / "loops" / "closed").is_dir()
    assert (target / "daily").is_dir()
    assert (target / "projects" / "active").is_dir()
    assert (target / "projects" / "backlog").is_dir()
    assert (target / "projects" / "archive").is_dir()
    assert (target / "knowledge").is_dir()
    assert (target / "reviews").is_dir()

    assert "Inbox" in (target / "inbox.md").read_text()
    assert "Open Loops" in (target / "loops" / "open.md").read_text()


def test_init_idempotent(tmp_path):
    target = tmp_path / "vault"
    main(["init", str(target)])

    (target / "inbox.md").write_text("# My custom inbox\n")
    main(["init", str(target)])
    assert "My custom inbox" in (target / "inbox.md").read_text()


def test_today_creates_daily_note(tmp_path):
    target = tmp_path / "vault"
    main(["init", str(target)])
    main(["--vault", str(target), "today"])

    today = date.today().isoformat()
    daily_path = target / "daily" / f"{today}.md"
    assert daily_path.exists()
    assert "Morning: Intention" in daily_path.read_text()


def test_add_loop(tmp_path):
    target = tmp_path / "vault"
    main(["init", str(target)])
    main([
        "--vault", str(target),
        "add-loop", "Send update to Alice",
        "--who", "Alice",
        "--what", "Weekly status on API project",
        "--due", "2026-02-20",
    ])

    content = (target / "loops" / "open.md").read_text()
    assert "Send update to Alice" in content
    assert "Alice" in content
    assert "2026-02-20" in content


def test_status(tmp_path, capsys):
    target = tmp_path / "vault"
    main(["init", str(target)])
    main(["--vault", str(target), "status"])

    output = capsys.readouterr().out
    assert "Active projects:" in output
    assert "Open loops:" in output
