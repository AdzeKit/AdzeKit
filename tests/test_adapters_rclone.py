"""Tests for the rclone adapter."""

from __future__ import annotations

import pytest

from adzekit.modules.adapters_rclone import (
    install_rclone,
    status_rclone,
    sync_rclone,
    uninstall_rclone,
)


def test_install_rclone_requires_remote(workspace):
    with pytest.raises(ValueError):
        install_rclone(workspace, remote=None)


def test_install_rclone_composes_remote_with_folder(workspace):
    result = install_rclone(workspace, remote="gdrive", folder="adzekit")
    assert result["remote_path"] == "gdrive:adzekit"
    # Marker file got rewritten with the remote path.
    marker = workspace.marker_path.read_text(encoding="utf-8")
    assert "rclone_remote = gdrive:adzekit" in marker


def test_install_rclone_full_path_passed_through(workspace):
    """If `remote` already contains `:`, it's used verbatim and folder is ignored."""
    result = install_rclone(
        workspace, remote="gdrive:custom/subfolder", folder="ignored",
    )
    assert result["remote_path"] == "gdrive:custom/subfolder"


def test_uninstall_rclone_clears_marker(workspace):
    install_rclone(workspace, remote="gdrive", folder="adzekit")
    result = uninstall_rclone(workspace)
    assert result["removed_remote"] == "gdrive:adzekit"
    marker = workspace.marker_path.read_text(encoding="utf-8")
    assert "rclone_remote = \n" in marker or "rclone_remote =\n" in marker


def test_status_rclone_unconfigured(workspace):
    result = status_rclone(workspace)
    assert result["configured"] is False
    assert result["remote_path"] == ""


def test_status_rclone_configured(workspace):
    install_rclone(workspace, remote="gdrive", folder="adzekit")
    # Re-resolve settings so the marker change is observed.
    from adzekit.config import Settings
    fresh = Settings(shed=workspace.shed)
    result = status_rclone(fresh)
    assert result["configured"] is True
    assert result["remote_path"] == "gdrive:adzekit"
    assert "gdrive:adzekit/stock" == result["stock_remote"]
    assert "gdrive:adzekit/drafts" == result["drafts_remote"]


def test_sync_rclone_no_remote_short_circuits(workspace):
    """Without a configured remote, sync returns synced=False without erroring."""
    result = sync_rclone(workspace, direction="both")
    assert result["synced"] is False
    assert result["reason"] == "no_remote_configured"


def test_sync_rclone_missing_binary_short_circuits(workspace, monkeypatch):
    install_rclone(workspace, remote="gdrive", folder="adzekit")
    from adzekit.config import Settings
    fresh = Settings(shed=workspace.shed)
    monkeypatch.setattr(
        "adzekit.modules.adapters_rclone.shutil.which",
        lambda _name: None,
    )
    result = sync_rclone(fresh, direction="both")
    assert result["synced"] is False
    assert result["reason"] == "rclone_not_on_path"
