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


def test_create_daily_note_has_universal_frontmatter(workspace):
    today = date.today()
    path = create_daily_note(today, workspace)
    content = path.read_text()
    assert content.startswith("---\n")
    assert f'id: "{today.isoformat()}"' in content
    assert f"created_at: {today.isoformat()}" in content
    assert f"updated_at: {today.isoformat()}" in content


def test_create_project(workspace):
    path = create_project(
        slug="test-proj",
        title="Test Project",
        backlog=True,
        settings=workspace,
    )
    assert path.exists()
    assert (path / "README.md").exists()
    assert (path / "tasks.md").exists()
    assert (path / "notes.md").exists()
    readme = (path / "README.md").read_text()
    assert "Test Project" in readme
    assert 'id: "test-proj"' in readme


def test_create_project_active(workspace):
    path = create_project(
        slug="active-proj",
        backlog=False,
        settings=workspace,
    )
    assert "active" in str(path)
    assert path.parent == workspace.active_dir
