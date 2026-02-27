"""Tests for the AdzeKit CLI."""

from datetime import date

from adzekit.cli import main


def test_init_creates_shed(tmp_path):
    target = tmp_path / "shed"
    main(["init", str(target)])

    assert (target / "inbox.md").exists()
    assert (target / "loops" / "open.md").exists()
    assert (target / "loops" / "closed").is_dir()
    assert (target / "daily").is_dir()
    assert (target / "projects").is_dir()
    assert (target / "projects" / "backlog").is_dir()
    assert (target / "projects" / "archive").is_dir()
    assert (target / "knowledge").is_dir()
    assert (target / "reviews").is_dir()
    assert (target / "drafts").is_dir()

    assert "Inbox" in (target / "inbox.md").read_text()
    assert "Open Loops" in (target / "loops" / "open.md").read_text()


def test_init_idempotent(tmp_path):
    target = tmp_path / "shed"
    main(["init", str(target)])

    (target / "inbox.md").write_text("# My custom inbox\n")
    main(["init", str(target)])
    assert "My custom inbox" in (target / "inbox.md").read_text()


def test_today_creates_daily_note(tmp_path):
    target = tmp_path / "shed"
    main(["init", str(target)])
    main(["--shed", str(target), "today"])

    today = date.today().isoformat()
    daily_path = target / "daily" / f"{today}.md"
    assert daily_path.exists()
    assert "Morning: Intention" in daily_path.read_text()


def test_add_loop(tmp_path):
    target = tmp_path / "shed"
    main(["init", str(target)])
    main([
        "--shed", str(target),
        "add-loop", "Send update to Alice",
        "--size", "XS",
        "--due", "2026-02-20",
    ])

    content = (target / "loops" / "open.md").read_text()
    assert "Send update to Alice" in content
    assert "(XS)" in content
    assert "(2026-02-20)" in content
    assert f"[{date.today().isoformat()}]" in content


def test_review_creates_weekly_review(tmp_path, capsys):
    target = tmp_path / "shed"
    main(["init", str(target)])
    main(["--shed", str(target), "review"])

    output = capsys.readouterr().out.strip()
    review_path = target / "reviews" / output.split("/")[-1]
    assert review_path.exists()

    content = review_path.read_text()
    assert "Review" in content
    assert "Open Loops" in content
    assert "Reflection" in content


def test_review_with_date(tmp_path, capsys):
    target = tmp_path / "shed"
    main(["init", str(target)])
    main(["--shed", str(target), "review", "--date", "2026-01-06"])

    output = capsys.readouterr().out.strip()
    assert "2026-W02" in output

    review_path = target / "reviews" / "2026-W02.md"
    assert review_path.exists()
    content = review_path.read_text()
    assert "Week 02" in content
    assert "(2026-01-06)" in content


def test_status(tmp_path, capsys):
    target = tmp_path / "shed"
    main(["init", str(target)])
    main(["--shed", str(target), "status"])

    output = capsys.readouterr().out
    assert "Active projects:" in output
    assert "Open loops:" in output


def test_setup_sync_no_rclone(tmp_path, monkeypatch, capsys):
    """setup-sync should fail gracefully if rclone is not on PATH."""
    import pytest

    target = tmp_path / "shed"
    main(["init", str(target)])

    # Hide rclone from PATH
    monkeypatch.setenv("PATH", "")
    with pytest.raises(SystemExit):
        main(["--shed", str(target), "setup-sync"])

    output = capsys.readouterr().out
    assert "rclone is not installed" in output


def test_setup_sync_writes_config(tmp_path, monkeypatch, capsys):
    """setup-sync should write rclone_remote to .adzekit."""
    target = tmp_path / "shed"
    main(["init", str(target)])

    # Create a fake rclone that lists 'gdrive' as a remote
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_rclone = fake_bin / "rclone"
    fake_rclone.write_text("#!/bin/sh\necho 'gdrive:'\n", encoding="utf-8")
    fake_rclone.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin))

    main(["--shed", str(target), "setup-sync", "--remote", "gdrive", "--folder", "mykit"])

    config = target / ".adzekit"
    assert config.exists()
    content = config.read_text()
    assert "rclone_remote = gdrive:mykit" in content
