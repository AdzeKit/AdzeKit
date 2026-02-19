"""Tests for workspace initialization and scaffolding."""

from datetime import date

from adzekit.workspace import create_daily_note, create_project, init_workspace


def test_init_workspace_creates_directories(workspace):
    init_workspace(workspace)
    assert workspace.loops_dir.exists()
    assert workspace.loops_closed_dir.exists()
    assert workspace.active_dir.exists()
    assert workspace.backlog_dir.exists()
    assert workspace.archive_dir.exists()
    assert workspace.daily_dir.exists()
    assert workspace.knowledge_dir.exists()
    assert workspace.reviews_dir.exists()
    assert workspace.stock_dir.exists()


def test_init_workspace_seeds_files(workspace):
    init_workspace(workspace)
    assert workspace.inbox_path.exists()
    assert workspace.loops_open.exists()
    assert "Inbox" in workspace.inbox_path.read_text()


def test_create_daily_note(workspace):
    today = date.today()
    path = create_daily_note(today, workspace)
    assert path.exists()
    content = path.read_text()
    assert "Morning: Intention" in content
    assert "Evening: Reflection" in content
    assert today.isoformat() in content

    # Creating again should not overwrite
    path.write_text("custom content")
    path2 = create_daily_note(today, workspace)
    assert path2.read_text() == "custom content"


def test_create_daily_note_has_no_frontmatter(workspace):
    today = date.today()
    path = create_daily_note(today, workspace)
    content = path.read_text()
    assert not content.startswith("---")
    assert content.startswith("# ")
    assert today.isoformat() in content


def test_create_project(workspace):
    path = create_project(
        slug="test-proj",
        title="Test Project",
        backlog=True,
        settings=workspace,
    )
    assert path.exists()
    assert path.suffix == ".md"
    content = path.read_text()
    assert "Test Project" in content
    assert "## Context" in content
    assert "## Log" in content
    assert "## Notes" in content

    # Creating again should not overwrite
    path.write_text("custom content")
    path2 = create_project(slug="test-proj", backlog=True, settings=workspace)
    assert path2.read_text() == "custom content"


def test_create_project_active(workspace):
    path = create_project(
        slug="active-proj",
        backlog=False,
        settings=workspace,
    )
    assert "active" in str(path)
    assert path.parent == workspace.active_dir
    assert path.name == "active-proj.md"


def test_init_workspace_gitignores_stock(workspace):
    init_workspace(workspace)
    gitignore = workspace.workspace / ".gitignore"
    assert gitignore.exists()
    assert "stock/" in gitignore.read_text()


def test_rclone_remote_defaults_empty():
    from adzekit.config import Settings

    s = Settings()
    assert s.has_rclone_remote is False
    assert s.rclone_remote == ""


def test_sync_stock_raises_without_remote(workspace):
    import pytest

    with pytest.raises(ValueError, match="rclone_remote is not configured"):
        workspace.sync_stock()


def test_push_stock_raises_without_remote(workspace):
    import pytest

    with pytest.raises(ValueError, match="rclone_remote is not configured"):
        workspace.push_stock()