"""Tests for shed initialization and scaffolding."""

from datetime import date

from adzekit.workspace import create_daily_note, create_project, init_shed


def test_init_shed_creates_directories(workspace):
    init_shed(workspace)
    assert workspace.loops_dir.exists()
    assert workspace.loops_closed_dir.exists()
    assert workspace.active_dir.exists()
    assert workspace.backlog_dir.exists()
    assert workspace.archive_dir.exists()
    assert workspace.daily_dir.exists()
    assert workspace.knowledge_dir.exists()
    assert workspace.reviews_dir.exists()
    assert workspace.stock_dir.exists()
    assert workspace.drafts_dir.exists()


def test_init_shed_seeds_files(workspace):
    init_shed(workspace)
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


def test_init_shed_gitignores_stock_and_drafts(workspace):
    init_shed(workspace)
    gitignore = workspace.shed / ".gitignore"
    assert gitignore.exists()
    content = gitignore.read_text()
    assert "stock/" in content
    assert "drafts/" in content


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


def test_sync_drafts_raises_without_remote(workspace):
    import pytest

    with pytest.raises(ValueError, match="rclone_remote is not configured"):
        workspace.sync_drafts()


def test_push_drafts_raises_without_remote(workspace):
    import pytest

    with pytest.raises(ValueError, match="rclone_remote is not configured"):
        workspace.push_drafts()


def test_rclone_derived_paths():
    from adzekit.config import Settings

    s = Settings(rclone_remote="gdrive:adzekit")
    assert s.rclone_stock_remote == "gdrive:adzekit/stock"
    assert s.rclone_drafts_remote == "gdrive:adzekit/drafts"


def test_rclone_derived_paths_trailing_slash():
    from adzekit.config import Settings

    s = Settings(rclone_remote="gdrive:adzekit/")
    assert s.rclone_stock_remote == "gdrive:adzekit/stock"
    assert s.rclone_drafts_remote == "gdrive:adzekit/drafts"


# --- .adzekit marker tests ---


def test_init_shed_writes_marker(workspace):
    init_shed(workspace)
    assert workspace.marker_path.exists()
    content = workspace.marker_path.read_text()
    assert "backbone_version = 1" in content


def test_is_initialized(workspace):
    assert workspace.is_initialized is True


def test_not_initialized(tmp_path):
    from adzekit.config import Settings

    s = Settings(shed=tmp_path)
    assert s.is_initialized is False


def test_require_initialized_raises(tmp_path):
    import pytest

    from adzekit.config import Settings, ShedNotInitializedError

    s = Settings(shed=tmp_path)
    with pytest.raises(ShedNotInitializedError, match="not an AdzeKit shed"):
        s.require_initialized()


def test_backbone_version(workspace):
    from adzekit.config import BACKBONE_VERSION

    assert workspace.shed_backbone_version == BACKBONE_VERSION


def test_cli_refuses_uninitialized_shed(tmp_path):
    """CLI commands (except init) should fail if the shed is not initialized."""
    import pytest

    from adzekit.cli import main

    with pytest.raises(SystemExit):
        main(["--shed", str(tmp_path), "today"])


def test_cli_init_works_on_fresh_dir(tmp_path):
    """init should succeed even when .adzekit doesn't exist yet."""
    from adzekit.cli import main
    from adzekit.config import Settings

    target = tmp_path / "new-shed"
    main(["init", str(target)])

    s = Settings(shed=target)
    assert s.is_initialized
    assert s.shed_backbone_version == 1


def test_settings_loads_config_from_adzekit(tmp_path, monkeypatch):
    """Settings should pick up rclone_remote from the .adzekit config."""
    from adzekit.config import Settings

    shed = tmp_path / "shed"
    shed.mkdir()
    (shed / ".adzekit").write_text(
        "backbone_version = 1\n"
        "rclone_remote = gdrive:mykit\n"
    )

    monkeypatch.delenv("ADZEKIT_RCLONE_REMOTE", raising=False)

    s = Settings(shed=shed)
    assert s.rclone_remote == "gdrive:mykit"


def test_settings_env_var_overrides_adzekit_config(tmp_path, monkeypatch):
    """A real env var should win over the .adzekit config file."""
    from adzekit.config import Settings

    shed = tmp_path / "shed"
    shed.mkdir()
    (shed / ".adzekit").write_text(
        "backbone_version = 1\n"
        "rclone_remote = gdrive:from-config\n"
    )

    monkeypatch.setenv("ADZEKIT_RCLONE_REMOTE", "s3:from-env")

    s = Settings(shed=shed)
    assert s.rclone_remote == "s3:from-env"


# --- .adzekit config fields ---


def test_marker_has_config_defaults(tmp_path):
    """init should write all config keys with defaults."""
    from adzekit.config import Settings

    s = Settings(shed=tmp_path)
    s.write_marker()
    content = s.marker_path.read_text()
    assert "max_active_projects = 3" in content
    assert "max_daily_tasks = 5" in content
    assert "loop_sla_hours = 24" in content
    assert "stale_loop_days = 7" in content


def test_config_reads_custom_values(tmp_path):
    """Settings should read custom limits from .adzekit."""
    from adzekit.config import Settings

    shed = tmp_path / "shed"
    shed.mkdir()
    (shed / ".adzekit").write_text(
        "backbone_version = 1\n"
        "max_active_projects = 5\n"
        "max_daily_tasks = 10\n"
        "loop_sla_hours = 48\n"
        "stale_loop_days = 14\n"
    )

    s = Settings(shed=shed)
    assert s.max_active_projects == 5
    assert s.max_daily_tasks == 10
    assert s.loop_sla_hours == 48
    assert s.stale_loop_days == 14


def test_config_defaults_when_missing(tmp_path):
    """If .adzekit has no custom keys, defaults should apply."""
    from adzekit.config import Settings

    shed = tmp_path / "shed"
    shed.mkdir()
    (shed / ".adzekit").write_text("backbone_version = 1\n")

    s = Settings(shed=shed)
    assert s.max_active_projects == 3
    assert s.max_daily_tasks == 5
    assert s.loop_sla_hours == 24
    assert s.stale_loop_days == 7


def test_write_marker_preserves_custom_values(tmp_path):
    """Re-running write_marker should preserve existing custom values."""
    from adzekit.config import Settings

    shed = tmp_path / "shed"
    shed.mkdir()
    (shed / ".adzekit").write_text(
        "backbone_version = 1\n"
        "max_active_projects = 7\n"
        "max_daily_tasks = 12\n"
        "loop_sla_hours = 36\n"
        "stale_loop_days = 3\n"
    )

    s = Settings(shed=shed)
    s.write_marker()

    content = s.marker_path.read_text()
    assert "max_active_projects = 7" in content
    assert "max_daily_tasks = 12" in content
    assert "loop_sla_hours = 36" in content
    assert "stale_loop_days = 3" in content


def test_active_dir_is_projects_root(workspace):
    """Active projects should live at projects/ root, not projects/active/."""
    assert workspace.active_dir == workspace.projects_dir
