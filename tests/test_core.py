"""Tests for the transport-neutral public API."""

import json

import pytest

from adzekit import Workspace


def test_workspace_uses_explicit_root(workspace):
    api = Workspace(workspace.shed)
    assert api.root == workspace.shed.resolve()
    assert api.snapshot()["version"] == 1


def test_snapshot_is_json_safe(workspace):
    workspace.loops_active.write_text(
        "# Active Loops\n\n- [ ] (S) [2026-05-22] Send estimate\n",
        encoding="utf-8",
    )
    payload = Workspace(workspace.shed).snapshot()
    assert json.loads(json.dumps(payload))["loops"][0]["title"] == "Send estimate"


def test_propose_only_writes_to_drafts(workspace):
    api = Workspace(workspace.shed)
    result = api.propose(workflow="review", markdown="# Proposal\n", summary="Review me")
    assert result["path"].startswith("drafts/")
    assert (workspace.shed / result["path"]).is_file()
    assert not list(workspace.knowledge_dir.iterdir())


def test_knowledge_rejects_path_traversal(workspace):
    api = Workspace(workspace.shed)
    with pytest.raises(ValueError, match="single filename stem"):
        api.knowledge("../.adzekit")


def test_initialize_creates_workspace(tmp_path):
    api = Workspace.initialize(tmp_path / "portable")
    assert api.settings.is_initialized
    assert api.snapshot()["workspace"] == str((tmp_path / "portable").resolve())
    assert api.snapshot()["projects"] == []
    assert api.snapshot()["today"] is None
    assert list(api.settings.knowledge_dir.iterdir()) == []
    assert list(api.settings.reviews_dir.iterdir()) == []


def test_workspace_environment_alias(tmp_path, monkeypatch):
    from adzekit.config import get_settings

    root = tmp_path / "from-env"
    Workspace.initialize(root)
    monkeypatch.delenv("ADZEKIT_SHED", raising=False)
    monkeypatch.setenv("ADZEKIT_WORKSPACE", str(root))
    assert get_settings().workspace == root
