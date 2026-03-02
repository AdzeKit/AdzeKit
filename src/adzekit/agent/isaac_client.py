"""Agent client — runs prompts through Isaac, Claude Code, or local orchestrator.

Backend resolution (first wins):
  1. ``backend`` argument passed directly
  2. ``ADZEKIT_AGENT_BACKEND`` env var
  3. ``agent_backend`` key in shed's .adzekit config
  4. Default: ``isaac``

Backends:
  ``isaac``  — dbexec repo run isaac --print (Databricks Isaac, recommended)
  ``claude`` — claude --print (vanilla Claude Code CLI)
  ``local``  — direct Anthropic API via adzekit.agent.orchestrator (no MCP)
"""

import asyncio
import json
import os
import shutil
from pathlib import Path

CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"
MCP_SERVER_NAMES = ("adzekit-backbone", "adzekit-gmail")

# Common install locations that may not be in the web server's restricted PATH
_EXTRA_SEARCH_DIRS = [
    Path.home() / ".local" / "bin",
    Path("/usr/local/bin"),
    Path("/opt/homebrew/bin"),
    Path("/opt/homebrew/sbin"),
]


class AgentNotAvailableError(RuntimeError):
    pass


def _find_binary(name: str) -> str | None:
    """Find a binary via PATH, then known install directories."""
    found = shutil.which(name)
    if found:
        return found
    for d in _EXTRA_SEARCH_DIRS:
        candidate = d / name
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _clean_env() -> dict:
    """Return env without CLAUDECODE so nested sessions are allowed."""
    return {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}


# --- availability checks ---------------------------------------------------


def check_isaac() -> dict:
    path = _find_binary("dbexec")
    return {"available": path is not None, "path": path, "command": "dbexec repo run isaac"}


def check_claude() -> dict:
    path = _find_binary("claude")
    return {"available": path is not None, "path": path}


def check_mcp_servers() -> dict:
    if not CLAUDE_SETTINGS.exists():
        return {
            name: {"configured": False, "error": f"{CLAUDE_SETTINGS} not found"}
            for name in MCP_SERVER_NAMES
        }
    try:
        mcp_servers = json.loads(CLAUDE_SETTINGS.read_text(encoding="utf-8")).get("mcpServers", {})
    except Exception as exc:
        return {name: {"configured": False, "error": str(exc)} for name in MCP_SERVER_NAMES}

    result = {}
    for name in MCP_SERVER_NAMES:
        if name not in mcp_servers:
            result[name] = {"configured": False}
            continue
        cmd = mcp_servers[name].get("command", "")
        result[name] = {
            "configured": True,
            "command": cmd,
            "command_available": _find_binary(cmd) is not None if cmd else False,
        }
    return result


# --- runners ----------------------------------------------------------------


async def run_isaac(prompt: str, timeout: int = 120) -> str:
    """Run a prompt through Isaac (dbexec repo run isaac --print)."""
    dbexec = _find_binary("dbexec")
    if not dbexec:
        raise AgentNotAvailableError("dbexec not found — Isaac unavailable")

    proc = await asyncio.create_subprocess_exec(
        dbexec, "repo", "run", "isaac", "--print", prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_clean_env(),
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"Isaac timed out after {timeout}s")

    if proc.returncode != 0:
        raise RuntimeError(
            f"Isaac exited {proc.returncode}: {stderr.decode(errors='replace').strip()}"
        )
    return stdout.decode(errors="replace").strip()


async def run_claude(prompt: str, timeout: int = 120) -> str:
    """Run a prompt through Claude Code CLI (--print)."""
    claude = _find_binary("claude")
    if not claude:
        raise AgentNotAvailableError("claude not found — Claude Code unavailable")

    proc = await asyncio.create_subprocess_exec(
        claude, "--print", prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_clean_env(),
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"Claude timed out after {timeout}s")

    if proc.returncode != 0:
        raise RuntimeError(
            f"Claude exited {proc.returncode}: {stderr.decode(errors='replace').strip()}"
        )
    return stdout.decode(errors="replace").strip()


async def run_agent(prompt: str, backend: str = "isaac", timeout: int = 120) -> tuple[str, str]:
    """Run a prompt with the chosen backend.

    Returns:
        (response_text, backend_used)
    """
    if backend == "isaac":
        return await run_isaac(prompt, timeout=timeout), "isaac"
    if backend == "claude":
        return await run_claude(prompt, timeout=timeout), "claude"
    raise AgentNotAvailableError(f"Unknown CLI backend: {backend!r} — use 'isaac' or 'claude'")
