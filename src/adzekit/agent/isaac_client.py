"""Agent client -- runs prompts through Isaac.

Isaac is the Databricks-internal AI agent runner (dbexec repo run isaac --print).
"""

import asyncio
import os
import shutil
from pathlib import Path

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


def check_isaac() -> dict:
    path = _find_binary("dbexec")
    return {"available": path is not None, "path": path}


async def run_agent(prompt: str, timeout: int = 120) -> tuple[str, str]:
    """Run a prompt through Isaac (dbexec repo run isaac --print).

    Returns:
        (response_text, "isaac")
    """
    dbexec = _find_binary("dbexec")
    if not dbexec:
        raise AgentNotAvailableError("dbexec not found -- Isaac unavailable")

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
    return stdout.decode(errors="replace").strip(), "isaac"
