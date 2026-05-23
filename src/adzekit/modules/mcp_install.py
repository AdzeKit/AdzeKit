"""`adzekit mcp install/status/uninstall` — wire the Shed MCP into Claude Code.

The Shed MCP server is launched via the `adzekit-mcp-shed` console script
(registered in pyproject.toml). To make Claude Code start it on demand, an
entry must be written into `~/.claude/settings.json` under `mcpServers`:

    {
      "mcpServers": {
        "adzekit-shed": {
          "command": "adzekit-mcp-shed",
          "env": {"ADZEKIT_SHED": "/path/to/shed"}
        }
      }
    }

This module:
  - preserves any other MCP servers the user has configured (we never blow
    away their settings.json)
  - writes atomically (tempfile + rename)
  - reports clean status (does the entry exist? does the binary resolve on
    PATH?)
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from adzekit.config import Settings, get_settings

CLAUDE_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
MCP_SERVER_NAME = "adzekit-shed"
MCP_SERVER_BIN = "adzekit-mcp-shed"


def _load_settings_json(path: Path = CLAUDE_SETTINGS_PATH) -> dict[str, Any]:
    """Read ~/.claude/settings.json. Returns an empty dict if missing or
    invalid (we don't want to silently overwrite a corrupt file, but the
    caller can decide what to do — install will refuse, status will report)."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"__parse_error__": True}


def _write_settings_json(data: dict[str, Any], path: Path = CLAUDE_SETTINGS_PATH) -> None:
    """Atomically rewrite ~/.claude/settings.json with `data`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".settings.", suffix=".tmp", dir=str(path.parent),
    )
    try:
        os.write(fd, (json.dumps(data, indent=2) + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    Path(tmp_name).replace(path)


def install_mcp(
    settings: Settings | None = None,
    *,
    claude_settings_path: Path = CLAUDE_SETTINGS_PATH,
) -> dict[str, Any]:
    """Wire the adzekit-shed MCP server into Claude Code's settings.

    Preserves any other configured mcpServers. Embeds the shed path as an
    env var so the server doesn't need to discover the shed from cwd.
    """
    settings = settings or get_settings()
    data = _load_settings_json(claude_settings_path)
    if data.get("__parse_error__"):
        raise RuntimeError(
            f"{claude_settings_path} exists but is not valid JSON. "
            "Fix it manually before installing the MCP."
        )

    mcp_servers = data.setdefault("mcpServers", {})
    mcp_servers[MCP_SERVER_NAME] = {
        "command": MCP_SERVER_BIN,
        "env": {"ADZEKIT_SHED": str(settings.shed)},
    }
    _write_settings_json(data, claude_settings_path)

    return {
        "installed": True,
        "settings_path": str(claude_settings_path),
        "server_name": MCP_SERVER_NAME,
        "command": MCP_SERVER_BIN,
        "shed": str(settings.shed),
        "binary_on_path": shutil.which(MCP_SERVER_BIN) is not None,
    }


def uninstall_mcp(
    *,
    claude_settings_path: Path = CLAUDE_SETTINGS_PATH,
) -> dict[str, Any]:
    """Remove the adzekit-shed MCP entry, preserving others."""
    data = _load_settings_json(claude_settings_path)
    if data.get("__parse_error__"):
        raise RuntimeError(
            f"{claude_settings_path} is not valid JSON. Fix manually."
        )
    mcp_servers = data.get("mcpServers", {})
    removed = mcp_servers.pop(MCP_SERVER_NAME, None) is not None
    if removed:
        # Don't leave a stale empty `mcpServers` key if it was the only one.
        if not mcp_servers:
            data.pop("mcpServers", None)
        _write_settings_json(data, claude_settings_path)
    return {
        "removed": removed,
        "settings_path": str(claude_settings_path),
    }


def status_mcp(
    settings: Settings | None = None,
    *,
    claude_settings_path: Path = CLAUDE_SETTINGS_PATH,
) -> dict[str, Any]:
    """Report installed state of the Shed MCP server."""
    settings = settings or get_settings()
    data = _load_settings_json(claude_settings_path)
    parse_error = bool(data.get("__parse_error__"))
    mcp_servers = data.get("mcpServers", {}) if not parse_error else {}
    entry = mcp_servers.get(MCP_SERVER_NAME)
    binary_path = shutil.which(MCP_SERVER_BIN)
    configured_shed = (entry or {}).get("env", {}).get("ADZEKIT_SHED")

    return {
        "settings_path": str(claude_settings_path),
        "settings_parseable": not parse_error,
        "entry_present": entry is not None,
        "entry_command": (entry or {}).get("command"),
        "configured_shed": configured_shed,
        "current_shed": str(settings.shed),
        "shed_matches": configured_shed == str(settings.shed) if configured_shed else False,
        "binary_on_path": binary_path is not None,
        "binary_path": binary_path,
    }
