"""Tests for the WIP gatekeeper.

Design doc Principle 1: Cap Work-in-Progress. Max 3 active projects.
"""

import pytest

from adzekit.modules.wip import (
    activate_project,
    archive_project,
    can_activate,
    count_active_projects,
    wip_status,
)
from adzekit.workspace import create_project


def test_empty_workspace_allows_activation(workspace):
    allowed, reason = can_activate(workspace)
    assert allowed
    assert "0/3" in reason


def test_wip_limit_enforced(workspace):
    # Create 3 active projects
    for i in range(3):
        create_project(f"proj-{i}", backlog=False, settings=workspace)
    assert count_active_projects(workspace) == 3

    allowed, reason = can_activate(workspace)
    assert not allowed
    assert "WIP limit" in reason


def test_activate_from_backlog(workspace):
    create_project("new-proj", backlog=True, settings=workspace)
    assert count_active_projects(workspace) == 0

    activate_project("new-proj", workspace)
    assert count_active_projects(workspace) == 1
    assert (workspace.active_dir / "new-proj" / "README.md").exists()


def test_activate_respects_limit(workspace):
    for i in range(3):
        create_project(f"active-{i}", backlog=False, settings=workspace)
    create_project("waiting", backlog=True, settings=workspace)

    with pytest.raises(ValueError, match="WIP limit"):
        activate_project("waiting", workspace)


def test_archive_project(workspace):
    create_project("done", backlog=False, settings=workspace)
    assert count_active_projects(workspace) == 1

    archive_project("done", workspace)
    assert count_active_projects(workspace) == 0
    assert (workspace.archive_dir / "done" / "README.md").exists()


def test_wip_status_summary(workspace):
    create_project("p1", backlog=False, settings=workspace)
    status = wip_status(workspace)
    assert status["active_projects"] == 1
    assert status["max_active_projects"] == 3
    assert status["projects_available"] == 2
