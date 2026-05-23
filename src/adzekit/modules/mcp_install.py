"""`adzekit mcp install/status/uninstall` — wire AdzeKit's MCP servers
into Claude Code's settings.

Three MCP servers ship with AdzeKit:
  - shed:     the canonical shed access tool (always available)
  - gmail:    Gmail capabilities (available iff the Gmail adapter is
              installed — i.e., the label cache exists)
  - calendar: Calendar capabilities (available iff the Calendar adapter
              is installed)

`adzekit mcp install` writes entries for every available server. `--only`
lets the user be surgical: `adzekit mcp install --only shed`.

Single-responsibility split (per the refactor):
  - adapter install (e.g. `adzekit adapter install gmail`)  → preflight + cache
  - mcp install                                              → register MCP servers
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from adzekit.config import Settings, get_settings

CLAUDE_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"


@dataclass(frozen=True)
class McpServer:
    name: str  # the key under `mcpServers` in settings.json
    binary: str  # the console-script binary

    @property
    def cache_relpath(self) -> str | None:
        """Adapter cache file (relative to drafts/) whose existence signals
        the server is ready to install. None means 'always available'.
        """
        if self.name == "adzekit-shed":
            return None
        if self.name == "adzekit-gmail":
            return ".adapters/gmail-labels.json"
        if self.name == "adzekit-calendar":
            return ".adapters/calendar-list.json"
        return None


SERVERS: tuple[McpServer, ...] = (
    McpServer("adzekit-shed", "adzekit-mcp-shed"),
    McpServer("adzekit-gmail", "adzekit-mcp-gmail"),
    McpServer("adzekit-calendar", "adzekit-mcp-calendar"),
)


# Backwards-compat aliases (kept so existing tests don't break in this commit).
MCP_SERVER_NAME = SERVERS[0].name
MCP_SERVER_BIN = SERVERS[0].binary


def get_server(name: str) -> McpServer:
    """Lookup a server by its short name ('shed', 'gmail', 'calendar') or
    by its full `mcpServers` key ('adzekit-shed', etc.)."""
    canonical = name if name.startswith("adzekit-") else f"adzekit-{name}"
    for srv in SERVERS:
        if srv.name == canonical:
            return srv
    raise ValueError(
        f"unknown MCP server {name!r}; valid: "
        + ", ".join(srv.name.removeprefix("adzekit-") for srv in SERVERS)
    )


def _is_server_available(srv: McpServer, settings: Settings) -> bool:
    """Return True iff the prerequisites for this server are in place."""
    if srv.cache_relpath is None:
        return True
    return (settings.drafts_dir / srv.cache_relpath).exists()


# --- settings.json I/O ------------------------------------------------------


def _load_settings_json(path: Path = CLAUDE_SETTINGS_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"__parse_error__": True}


def _write_settings_json(data: dict[str, Any], path: Path = CLAUDE_SETTINGS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".settings.", suffix=".tmp", dir=str(path.parent),
    )
    try:
        os.write(fd, (json.dumps(data, indent=2) + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    Path(tmp_name).replace(path)


# --- install/status/uninstall ----------------------------------------------


def install_mcp(
    settings: Settings | None = None,
    *,
    claude_settings_path: Path = CLAUDE_SETTINGS_PATH,
    only: list[str] | None = None,
) -> dict[str, Any]:
    """Register the available MCP servers into ~/.claude/settings.json.

    `only` is an optional list of short names (e.g. ["shed", "gmail"]) to
    restrict the install. Without `only`, every available server is
    registered.
    """
    settings = settings or get_settings()
    data = _load_settings_json(claude_settings_path)
    if data.get("__parse_error__"):
        raise RuntimeError(
            f"{claude_settings_path} exists but is not valid JSON. "
            "Fix it manually before installing the MCP servers."
        )

    if only:
        try:
            wanted = [get_server(n) for n in only]
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc
    else:
        wanted = list(SERVERS)

    mcp_servers = data.setdefault("mcpServers", {})
    installed: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []

    for srv in wanted:
        if not _is_server_available(srv, settings):
            skipped.append({
                "name": srv.name,
                "reason": (
                    f"adapter not installed; run "
                    f"`adzekit adapter install {srv.name.removeprefix('adzekit-')}` first"
                ),
            })
            continue
        mcp_servers[srv.name] = {
            "command": srv.binary,
            "env": {"ADZEKIT_SHED": str(settings.shed)},
        }
        installed.append({
            "name": srv.name,
            "command": srv.binary,
            "binary_on_path": shutil.which(srv.binary) is not None,
        })

    if installed:
        _write_settings_json(data, claude_settings_path)

    return {
        "installed": installed,
        "skipped": skipped,
        "settings_path": str(claude_settings_path),
        "shed": str(settings.shed),
    }


def uninstall_mcp(
    *,
    claude_settings_path: Path = CLAUDE_SETTINGS_PATH,
    only: list[str] | None = None,
) -> dict[str, Any]:
    """Remove AdzeKit MCP entries; preserve any others the user installed.

    Without `only`, removes all three. With `only=['shed']`, removes just shed.
    """
    data = _load_settings_json(claude_settings_path)
    if data.get("__parse_error__"):
        raise RuntimeError(
            f"{claude_settings_path} is not valid JSON. Fix manually."
        )

    if only:
        try:
            wanted = [get_server(n) for n in only]
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc
    else:
        wanted = list(SERVERS)

    mcp_servers = data.get("mcpServers", {})
    removed: list[str] = []
    for srv in wanted:
        if mcp_servers.pop(srv.name, None) is not None:
            removed.append(srv.name)

    if removed:
        # Trim empty `mcpServers` so settings.json stays tidy.
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
    """Per-server status: registered? binary on PATH? adapter ready?"""
    settings = settings or get_settings()
    data = _load_settings_json(claude_settings_path)
    parse_error = bool(data.get("__parse_error__"))
    mcp_servers = data.get("mcpServers", {}) if not parse_error else {}

    rows: list[dict[str, Any]] = []
    for srv in SERVERS:
        entry = mcp_servers.get(srv.name)
        binary_path = shutil.which(srv.binary)
        configured_shed = (entry or {}).get("env", {}).get("ADZEKIT_SHED")
        rows.append({
            "name": srv.name.removeprefix("adzekit-"),
            "registered": entry is not None,
            "binary_on_path": binary_path is not None,
            "adapter_ready": _is_server_available(srv, settings),
            "configured_shed": configured_shed,
            "shed_matches": (
                configured_shed == str(settings.shed)
                if configured_shed else False
            ),
        })

    return {
        "settings_path": str(claude_settings_path),
        "settings_parseable": not parse_error,
        "current_shed": str(settings.shed),
        "servers": rows,
    }
