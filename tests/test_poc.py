"""Tests for POC design document generation."""

import pytest

from adzekit.modules.poc import generate_poc
from adzekit.workspace import create_project


def test_generate_poc_requires_project(workspace):
    """Raise FileNotFoundError when no project file exists for the slug."""
    with pytest.raises(FileNotFoundError, match="No project file found"):
        generate_poc("nonexistent-slug", workspace)


def test_generate_poc_from_project(workspace):
    """Generate a POC template that pulls from an existing project."""
    create_project(
        slug="test-proj",
        title="Test Project",
        backlog=False,
        settings=workspace,
    )
    proj = workspace.active_dir / "test-proj.md"
    proj.write_text(
        """# Test Project #consulting

## Context
Build a data pipeline for real-time analytics.

## Log
- [ ] Set up Spark cluster
- [ ] Define schema
- 2026-02-19: Kickoff meeting with stakeholders

## Notes
Some scratch notes here.
""",
        encoding="utf-8",
    )

    path = generate_poc("test-proj", workspace)
    assert path.exists()
    content = path.read_text()

    assert "# [POC] Test Project" in content
    assert "Build a data pipeline for real-time analytics" in content
    assert "Set up Spark cluster" in content
    assert "Define schema" in content
    assert "{{" not in content


def test_generate_poc_creates_stock_dir(workspace):
    """Stock subdirectory is created if it doesn't exist."""
    create_project("brand-new", title="Brand New", backlog=False, settings=workspace)
    path = generate_poc("brand-new", workspace)
    assert (workspace.stock_dir / "brand-new").is_dir()
    assert path.exists()


def test_generate_poc_has_all_sections(workspace):
    """Verify the template has all major sections."""
    create_project("full-check", title="Full Check", backlog=False, settings=workspace)
    path = generate_poc("full-check", workspace)
    content = path.read_text()

    expected_sections = [
        "## TL;DR",
        "## Goals & Non-Goals",
        "## Problem",
        "### Why Now",
        "## Solution Overview",
        "### Component Map",
        "## Requirements",
        "## Prerequisites",
        "## Implementation Plan",
        "### Milestones",
        "### Tasks",
        "## Results",
    ]
    for section in expected_sections:
        assert section in content, f"Missing section: {section}"


def test_generate_poc_finds_project_in_backlog(workspace):
    """Project lookup works across backlog/."""
    create_project(
        slug="backlog-proj",
        title="Backlog Project",
        backlog=True,
        settings=workspace,
    )
    path = generate_poc("backlog-proj", workspace)
    content = path.read_text()
    assert "# [POC] Backlog Project" in content


def test_generate_poc_finds_project_in_root_projects_dir(workspace):
    """Project lookup works when file is directly in projects/."""
    proj = workspace.projects_dir / "root-proj.md"
    proj.write_text("# Root Project\n\n## Context\nDirect placement.\n", encoding="utf-8")

    path = generate_poc("root-proj", workspace)
    content = path.read_text()
    assert "# [POC] Root Project" in content
    assert "Direct placement." in content
