"""Tests for git-backed workspace operations.

Uses a real local bare repo as the remote -- no mocks, no network.
"""

import subprocess

import pytest

from adzekit.config import Settings


def _git(cwd, *args):
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@pytest.fixture
def bare_repo(tmp_path):
    bare = tmp_path / "remote.git"
    bare.mkdir()
    _git(bare, "init", "--bare")

    src = tmp_path / "seed"
    src.mkdir()
    _git(src, "init", "-b", "main")
    _git(src, "config", "user.email", "test@test.com")
    _git(src, "config", "user.name", "Test")

    (src / "inbox.md").write_text("# Inbox\n", encoding="utf-8")
    (src / "loops").mkdir()
    (src / "loops" / "open.md").write_text("# Open Loops\n\n", encoding="utf-8")

    _git(src, "add", "-A")
    _git(src, "commit", "-m", "init")
    _git(src, "remote", "add", "origin", str(bare))
    _git(src, "push", "origin", "main")

    return bare


@pytest.fixture
def git_settings(tmp_path, bare_repo):
    ws = tmp_path / "workspace"
    return Settings(
        workspace=ws,
        git_repo=str(bare_repo),
        git_branch="main",
    )


def test_is_git_backed(git_settings):
    assert git_settings.is_git_backed is True


def test_not_git_backed():
    s = Settings()
    assert s.is_git_backed is False


def test_sync_clones_repo(git_settings):
    git_settings.sync_workspace()
    assert (git_settings.workspace / ".git").is_dir()
    assert (git_settings.workspace / "inbox.md").exists()
    assert (git_settings.workspace / "loops" / "open.md").exists()


def test_sync_pulls_existing(git_settings, bare_repo, tmp_path):
    git_settings.sync_workspace()
    assert "Inbox" in git_settings.inbox_path.read_text()

    other = tmp_path / "other"
    _git(tmp_path, "clone", "--branch", "main", str(bare_repo), str(other))
    _git(other, "config", "user.email", "test@test.com")
    _git(other, "config", "user.name", "Test")
    (other / "inbox.md").write_text("# Inbox\n\n- new item\n", encoding="utf-8")
    _git(other, "add", "-A")
    _git(other, "commit", "-m", "add item")
    _git(other, "push", "origin", "main")

    git_settings.sync_workspace()
    assert "new item" in git_settings.inbox_path.read_text()


def test_commit_workspace(git_settings):
    git_settings.sync_workspace()

    _git(git_settings.workspace, "config", "user.email", "test@test.com")
    _git(git_settings.workspace, "config", "user.name", "Test")

    assert git_settings.commit_workspace("nothing") is False

    (git_settings.workspace / "inbox.md").write_text(
        "# Inbox\n\n- [2026-02-16] test entry\n", encoding="utf-8"
    )
    assert git_settings.commit_workspace("add entry") is True

    verify = git_settings.workspace.parent / "verify"
    _git(
        git_settings.workspace.parent,
        "clone", "--branch", "main", str(git_settings.git_repo), str(verify),
    )
    assert "test entry" in (verify / "inbox.md").read_text()


def test_workspace_git_status(git_settings):
    git_settings.sync_workspace()
    assert git_settings.workspace_git_status() == ""

    (git_settings.workspace / "inbox.md").write_text("dirty", encoding="utf-8")
    status = git_settings.workspace_git_status()
    assert "inbox.md" in status


def test_sync_without_git_repo_raises():
    s = Settings()
    with pytest.raises(ValueError, match="git_repo is not configured"):
        s.sync_workspace()


def test_commit_without_git_repo_raises():
    s = Settings()
    with pytest.raises(ValueError, match="git_repo is not configured"):
        s.commit_workspace()
