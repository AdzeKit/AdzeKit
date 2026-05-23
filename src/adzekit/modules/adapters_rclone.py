"""Rclone adapter: cloud sync for the workbench.

AdzeKit core has rclone code wired into `Settings` (sync_workbench,
push_workbench, sync_stock, sync_drafts). This adapter module is the
adapter-shaped surface over that existing code — same install / status /
uninstall verbs as the other adapters.

Responsibilities:
- install: configure the rclone remote in the shed's `.adzekit` marker
- uninstall: clear the remote (does not delete cloud content)
- status: report current rclone remote, last sync attempt, and whether
  the rclone binary is on PATH
- sync: invoke the existing push/pull flows

The actual sync mechanics (rclone subprocess calls, error handling, the
remote/path conventions) stay in src/adzekit/config.py — this adapter
delegates rather than duplicates. Why: rclone configuration is settings,
not runtime, and Settings is the source of truth for the shed.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from adzekit.config import (
    BACKBONE_VERSION,
    MARKER_FILE,
    Settings,
    get_settings,
)


def _read_marker(settings: Settings) -> dict[str, str]:
    """Read the .adzekit marker file as a key=value dict."""
    path = settings.marker_path
    if not path.exists():
        return {}
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, val = line.partition("=")
        if _:
            data[key.strip()] = val.strip()
    return data


def _write_marker(settings: Settings, fields: dict[str, str]) -> None:
    """Overwrite the .adzekit marker preserving the canonical layout."""
    lines = [
        f"backbone_version = {fields.get('backbone_version', BACKBONE_VERSION)}",
        f"max_active_projects = {fields.get('max_active_projects', '3')}",
        f"max_daily_tasks = {fields.get('max_daily_tasks', '5')}",
        f"loop_sla_hours = {fields.get('loop_sla_hours', '24')}",
        f"stale_loop_days = {fields.get('stale_loop_days', '7')}",
        f"stale_draft_days = {fields.get('stale_draft_days', '7')}",
        f"rclone_remote = {fields.get('rclone_remote', '')}",
    ]
    settings.marker_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def install_rclone(
    settings: Settings | None = None,
    *,
    remote: str | None = None,
    folder: str = "adzekit",
) -> dict[str, Any]:
    """Configure the rclone remote in the shed's .adzekit marker.

    Args:
        remote: rclone remote name (e.g. "gdrive"). Composed with `folder`
            to form the final path (e.g. "gdrive:adzekit"). If a full path
            (containing `:`) is passed it is used verbatim.
        folder: subfolder on the remote; ignored when `remote` already
            contains a colon.

    Does NOT push anything — that's a separate `adzekit sync push` call.
    Use status to confirm; sync to actually transfer.
    """
    settings = settings or get_settings()
    if not remote:
        raise ValueError("install_rclone requires a remote (e.g. 'gdrive')")
    remote_path = remote if ":" in remote else f"{remote}:{folder}"

    fields = _read_marker(settings)
    fields["rclone_remote"] = remote_path
    _write_marker(settings, fields)

    return {
        "adapter": "rclone",
        "remote_path": remote_path,
        "rclone_on_path": shutil.which("rclone") is not None,
    }


def uninstall_rclone(settings: Settings | None = None) -> dict[str, Any]:
    """Clear the rclone remote configuration. Cloud content is untouched."""
    settings = settings or get_settings()
    fields = _read_marker(settings)
    prior = fields.get("rclone_remote", "")
    fields["rclone_remote"] = ""
    _write_marker(settings, fields)
    return {
        "adapter": "rclone",
        "removed_remote": prior,
    }


def status_rclone(settings: Settings | None = None) -> dict[str, Any]:
    """Report rclone adapter status."""
    settings = settings or get_settings()
    return {
        "adapter": "rclone",
        "remote_path": settings.rclone_remote or "",
        "configured": bool(settings.rclone_remote),
        "rclone_on_path": shutil.which("rclone") is not None,
        "stock_remote": settings.rclone_stock_remote if settings.has_rclone_remote else "",
        "drafts_remote": settings.rclone_drafts_remote if settings.has_rclone_remote else "",
    }


def sync_rclone(
    settings: Settings | None = None,
    *,
    direction: str = "pull",
) -> dict[str, Any]:
    """Pull or push the workbench (stock/ + drafts/) via rclone.

    direction: 'pull' | 'push' | 'both'.
    """
    settings = settings or get_settings()
    if not settings.has_rclone_remote:
        return {"adapter": "rclone", "synced": False, "reason": "no_remote_configured"}
    if not shutil.which("rclone"):
        return {"adapter": "rclone", "synced": False, "reason": "rclone_not_on_path"}

    result: dict[str, Any] = {"adapter": "rclone", "synced": True, "direction": direction}
    if direction in ("pull", "both"):
        settings.sync_workbench()
        result["pulled"] = True
    if direction in ("push", "both"):
        settings.push_workbench()
        result["pushed"] = True
    return result
