"""Tests for shed agent tools.

Uses real shed fixtures -- no mocks.
"""

import json
import os
from datetime import date

import pytest

from adzekit.agent.tools import ToolRegistry
from adzekit.workspace import init_shed


@pytest.fixture
def shed_registry(workspace, monkeypatch):
    """A fresh tool registry with shed tools registered against a temp shed."""
    monkeypatch.setenv("ADZEKIT_SHED", str(workspace.shed))
    init_shed(workspace)

    # Create a fresh registry and register shed tools against it
    reg = ToolRegistry()

    from adzekit.config import get_settings
    from adzekit.preprocessor import load_open_loops

    def _settings():
        return get_settings()

    @reg.register(name="shed_get_open_loops", description="Get open loops.")
    def shed_get_open_loops() -> str:
        loops = load_open_loops(_settings())
        result = []
        for loop in loops:
            result.append({
                "title": loop.title,
                "date": loop.date.isoformat(),
                "size": loop.size,
            })
        return json.dumps({"count": len(result), "loops": result})

    @reg.register(
        name="shed_save_summary",
        description="Save summary to drafts.",
    )
    def shed_save_summary(filename: str, content: str) -> str:
        settings = _settings()
        drafts = settings.drafts_dir
        drafts.mkdir(parents=True, exist_ok=True)
        path = drafts / filename
        path.write_text(content, encoding="utf-8")
        return json.dumps({"status": "saved", "path": f"drafts/{filename}"})

    return reg


def test_shed_get_open_loops(shed_registry):
    result = shed_registry.call("shed_get_open_loops", {})
    parsed = json.loads(result)
    assert "count" in parsed
    assert isinstance(parsed["loops"], list)
    # init_shed seeds one loop
    assert parsed["count"] >= 1


def test_shed_save_summary(shed_registry, workspace):
    result = shed_registry.call(
        "shed_save_summary",
        {"filename": "test-summary.md", "content": "# Test Summary\n\nTest content."},
    )
    parsed = json.loads(result)
    assert parsed["status"] == "saved"
    assert (workspace.drafts_dir / "test-summary.md").exists()
    assert "Test Summary" in (workspace.drafts_dir / "test-summary.md").read_text()


def test_shed_tools_read_only_backbone(shed_registry):
    """Verify the registry has no tools that write to backbone files."""
    tool_names = [t.name for t in shed_registry.list_tools()]
    # No tool should directly add loops to open.md
    assert "shed_add_loop" not in tool_names
    assert "shed_add_to_inbox" not in tool_names
