"""Tests for `adzekit mcp install/status/uninstall`."""

from __future__ import annotations

import json

import pytest

from adzekit.modules.mcp_install import (
    MCP_SERVER_NAME,
    install_mcp,
    status_mcp,
    uninstall_mcp,
)


def test_install_creates_settings_file_if_absent(workspace, tmp_path):
    settings_path = tmp_path / "settings.json"
    result = install_mcp(workspace, claude_settings_path=settings_path)
    assert result["installed"] is True
    assert settings_path.exists()
    data = json.loads(settings_path.read_text())
    assert MCP_SERVER_NAME in data["mcpServers"]
    assert data["mcpServers"][MCP_SERVER_NAME]["command"] == "adzekit-mcp-shed"
    assert data["mcpServers"][MCP_SERVER_NAME]["env"]["ADZEKIT_SHED"] == str(workspace.shed)


def test_install_preserves_other_mcp_servers(workspace, tmp_path):
    """The user's existing MCP servers must survive the install."""
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({
        "mcpServers": {
            "slack": {"command": "slack-mcp"},
            "jira": {"command": "jira-mcp"},
        },
        "otherKey": "preserved",
    }), encoding="utf-8")

    install_mcp(workspace, claude_settings_path=settings_path)
    data = json.loads(settings_path.read_text())
    assert "slack" in data["mcpServers"]
    assert "jira" in data["mcpServers"]
    assert MCP_SERVER_NAME in data["mcpServers"]
    assert data["otherKey"] == "preserved"


def test_install_refuses_on_malformed_settings(workspace, tmp_path):
    """A corrupt settings.json shouldn't be silently overwritten."""
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("not json {{{", encoding="utf-8")
    with pytest.raises(RuntimeError, match="not valid JSON"):
        install_mcp(workspace, claude_settings_path=settings_path)


def test_uninstall_removes_entry_preserving_others(workspace, tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({
        "mcpServers": {
            "slack": {"command": "slack-mcp"},
            MCP_SERVER_NAME: {"command": "adzekit-mcp-shed"},
        },
    }), encoding="utf-8")
    result = uninstall_mcp(claude_settings_path=settings_path)
    assert result["removed"] is True
    data = json.loads(settings_path.read_text())
    assert MCP_SERVER_NAME not in data["mcpServers"]
    assert "slack" in data["mcpServers"]


def test_uninstall_when_entry_not_present(workspace, tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
    result = uninstall_mcp(claude_settings_path=settings_path)
    assert result["removed"] is False


def test_uninstall_removes_empty_mcp_servers_key(workspace, tmp_path):
    """When the Shed entry was the only one, the empty `mcpServers` dict is removed."""
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({
        "mcpServers": {MCP_SERVER_NAME: {"command": "x"}},
        "other": "stays",
    }), encoding="utf-8")
    uninstall_mcp(claude_settings_path=settings_path)
    data = json.loads(settings_path.read_text())
    assert "mcpServers" not in data
    assert data["other"] == "stays"


def test_status_reports_uninstalled_state(workspace, tmp_path):
    settings_path = tmp_path / "settings.json"
    result = status_mcp(workspace, claude_settings_path=settings_path)
    assert result["entry_present"] is False
    assert result["settings_parseable"] is True


def test_status_after_install(workspace, tmp_path):
    settings_path = tmp_path / "settings.json"
    install_mcp(workspace, claude_settings_path=settings_path)
    result = status_mcp(workspace, claude_settings_path=settings_path)
    assert result["entry_present"] is True
    assert result["entry_command"] == "adzekit-mcp-shed"
    assert result["configured_shed"] == str(workspace.shed)
    assert result["shed_matches"] is True


def test_status_detects_shed_mismatch(workspace, tmp_path):
    """If the user moved their shed since install, status reports the drift."""
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({
        "mcpServers": {
            MCP_SERVER_NAME: {
                "command": "adzekit-mcp-shed",
                "env": {"ADZEKIT_SHED": "/old/path"},
            },
        },
    }), encoding="utf-8")
    result = status_mcp(workspace, claude_settings_path=settings_path)
    assert result["entry_present"] is True
    assert result["configured_shed"] == "/old/path"
    assert result["shed_matches"] is False
