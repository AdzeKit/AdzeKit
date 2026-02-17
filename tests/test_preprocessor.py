"""Tests for the loaders."""

from adzekit.models import ProjectState
from adzekit.preprocessor import load_open_loops, load_projects
from adzekit.workspace import create_project


def test_load_open_loops_empty(workspace):
    assert load_open_loops(workspace) == []


def test_load_projects_by_state(workspace):
    create_project("active-1", backlog=False, settings=workspace)
    create_project("backlog-1", backlog=True, settings=workspace)
    active = load_projects(ProjectState.ACTIVE, workspace)
    backlog = load_projects(ProjectState.BACKLOG, workspace)
    assert len(active) == 1
    assert len(backlog) == 1
    assert active[0].slug == "active-1"
