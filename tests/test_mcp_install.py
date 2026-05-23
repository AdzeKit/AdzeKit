"""Tests for `adzekit mcp install/status/uninstall` (multi-server)."""

from __future__ import annotations

import json

import pytest

from adzekit.modules.mcp_install import (
    SERVERS,
    get_server,
    install_mcp,
    status_mcp,
    uninstall_mcp,
)


# --- install ---------------------------------------------------------------


def test_install_shed_only_creates_settings(workspace, tmp_path):
    """Without --only and without Gmail/Calendar adapters installed, only the
    shed entry is registered (the other two are skipped, not failed)."""
    settings_path = tmp_path / "settings.json"
    result = install_mcp(workspace, claude_settings_path=settings_path)
    assert any(r["name"] == "adzekit-shed" for r in result["installed"])
    skipped_names = {r["name"] for r in result["skipped"]}
    assert "adzekit-gmail" in skipped_names
    assert "adzekit-calendar" in skipped_names
    # settings.json was written.
    data = json.loads(settings_path.read_text())
    assert "adzekit-shed" in data["mcpServers"]
    assert "adzekit-gmail" not in data["mcpServers"]


def test_install_with_gmail_adapter_ready(workspace, tmp_path):
    """When the Gmail adapter cache exists, the Gmail MCP entry is registered."""
    cache_dir = workspace.drafts_dir / ".adapters"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "gmail-labels.json").write_text("{}")

    settings_path = tmp_path / "settings.json"
    result = install_mcp(workspace, claude_settings_path=settings_path)

    installed_names = {r["name"] for r in result["installed"]}
    assert "adzekit-shed" in installed_names
    assert "adzekit-gmail" in installed_names
    skipped_names = {r["name"] for r in result["skipped"]}
    assert "adzekit-calendar" in skipped_names


def test_install_all_available_when_adapters_installed(workspace, tmp_path):
    cache_dir = workspace.drafts_dir / ".adapters"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "gmail-labels.json").write_text("{}")
    (cache_dir / "calendar-list.json").write_text("{}")

    settings_path = tmp_path / "settings.json"
    result = install_mcp(workspace, claude_settings_path=settings_path)
    assert len(result["installed"]) == 3
    assert result["skipped"] == []


def test_install_only_shed(workspace, tmp_path):
    """--only shed installs just shed, even if other adapters are ready."""
    cache_dir = workspace.drafts_dir / ".adapters"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "gmail-labels.json").write_text("{}")
    settings_path = tmp_path / "settings.json"
    result = install_mcp(
        workspace, claude_settings_path=settings_path, only=["shed"],
    )
    installed_names = {r["name"] for r in result["installed"]}
    assert installed_names == {"adzekit-shed"}
    data = json.loads(settings_path.read_text())
    assert "adzekit-gmail" not in data["mcpServers"]


def test_install_only_unknown_name_raises(workspace, tmp_path):
    settings_path = tmp_path / "settings.json"
    with pytest.raises(RuntimeError, match="unknown MCP server"):
        install_mcp(
            workspace, claude_settings_path=settings_path, only=["garbage"],
        )


def test_install_preserves_other_mcp_servers(workspace, tmp_path):
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
    assert "adzekit-shed" in data["mcpServers"]
    assert data["otherKey"] == "preserved"


def test_install_refuses_on_malformed_settings(workspace, tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("not json {{{", encoding="utf-8")
    with pytest.raises(RuntimeError, match="not valid JSON"):
        install_mcp(workspace, claude_settings_path=settings_path)


# --- uninstall -------------------------------------------------------------


def test_uninstall_removes_all_adzekit_entries(workspace, tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({
        "mcpServers": {
            "slack": {"command": "slack-mcp"},
            "adzekit-shed": {"command": "adzekit-mcp-shed"},
            "adzekit-gmail": {"command": "adzekit-mcp-gmail"},
        },
    }), encoding="utf-8")
    result = uninstall_mcp(claude_settings_path=settings_path)
    assert set(result["removed"]) == {"adzekit-shed", "adzekit-gmail"}
    data = json.loads(settings_path.read_text())
    assert "adzekit-shed" not in data["mcpServers"]
    assert "slack" in data["mcpServers"]


def test_uninstall_only_one_server(workspace, tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({
        "mcpServers": {
            "adzekit-shed": {"command": "x"},
            "adzekit-gmail": {"command": "y"},
        },
    }), encoding="utf-8")
    result = uninstall_mcp(claude_settings_path=settings_path, only=["gmail"])
    assert result["removed"] == ["adzekit-gmail"]
    data = json.loads(settings_path.read_text())
    assert "adzekit-shed" in data["mcpServers"]


def test_uninstall_when_entries_not_present(workspace, tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
    result = uninstall_mcp(claude_settings_path=settings_path)
    assert result["removed"] == []


def test_uninstall_removes_empty_mcp_servers_key(workspace, tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({
        "mcpServers": {"adzekit-shed": {"command": "x"}},
        "other": "stays",
    }), encoding="utf-8")
    uninstall_mcp(claude_settings_path=settings_path)
    data = json.loads(settings_path.read_text())
    assert "mcpServers" not in data
    assert data["other"] == "stays"


# --- status ----------------------------------------------------------------


def test_status_reports_all_three_servers(workspace, tmp_path):
    settings_path = tmp_path / "settings.json"
    result = status_mcp(workspace, claude_settings_path=settings_path)
    names = {row["name"] for row in result["servers"]}
    assert names == {"shed", "gmail", "calendar"}
    # None registered yet.
    assert all(row["registered"] is False for row in result["servers"])


def test_status_after_install(workspace, tmp_path):
    settings_path = tmp_path / "settings.json"
    install_mcp(workspace, claude_settings_path=settings_path)
    result = status_mcp(workspace, claude_settings_path=settings_path)
    shed_row = next(r for r in result["servers"] if r["name"] == "shed")
    assert shed_row["registered"] is True
    assert shed_row["adapter_ready"] is True
    assert shed_row["shed_matches"] is True


def test_status_reports_adapter_not_ready(workspace, tmp_path):
    """Gmail/Calendar show adapter_ready=False until their adapter is installed."""
    settings_path = tmp_path / "settings.json"
    result = status_mcp(workspace, claude_settings_path=settings_path)
    gmail_row = next(r for r in result["servers"] if r["name"] == "gmail")
    cal_row = next(r for r in result["servers"] if r["name"] == "calendar")
    assert gmail_row["adapter_ready"] is False
    assert cal_row["adapter_ready"] is False
    # Shed has no cache file requirement.
    shed_row = next(r for r in result["servers"] if r["name"] == "shed")
    assert shed_row["adapter_ready"] is True


# --- get_server ------------------------------------------------------------


def test_get_server_by_short_name():
    srv = get_server("shed")
    assert srv.name == "adzekit-shed"


def test_get_server_by_full_name():
    srv = get_server("adzekit-gmail")
    assert srv.binary == "adzekit-mcp-gmail"


def test_get_server_unknown_raises():
    with pytest.raises(ValueError, match="unknown MCP server"):
        get_server("not-real")


def test_servers_inventory():
    """Three canonical servers ship today."""
    names = {srv.name for srv in SERVERS}
    assert names == {"adzekit-shed", "adzekit-gmail", "adzekit-calendar"}
