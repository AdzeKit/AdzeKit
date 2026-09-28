"""Git sync: the bridge between laptop, phone, and every agent.

Commit whatever changed, rebase onto the remote, push. Phones join the same
repository through any git-capable Markdown app.
"""

from __future__ import annotations

import socket
import subprocess
from datetime import datetime

from adzekit.workspace import Workspace, WorkspaceError


def _git(ws: Workspace, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(ws.root), *args], capture_output=True, text=True, check=False
    )


def _ok(result: subprocess.CompletedProcess[str], action: str) -> str:
    if result.returncode != 0:
        raise WorkspaceError(f"git {action} failed:\n{(result.stderr or result.stdout).strip()}")
    return result.stdout.strip()


def sync(ws: Workspace, message: str | None = None) -> list[str]:
    """Commit local changes, pull with rebase, and push. Returns a step log."""
    if _git(ws, "rev-parse", "--is-inside-work-tree").returncode != 0:
        raise WorkspaceError(f"{ws.root} is not a git repository. Run `git init` there first.")

    steps = []
    _ok(_git(ws, "add", "-A"), "add")
    if _git(ws, "diff", "--cached", "--quiet").returncode != 0:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        _ok(_git(ws, "commit", "-m", message or f"sync: {socket.gethostname()} {stamp}"), "commit")
        steps.append("committed local changes")
    else:
        steps.append("nothing to commit")

    if not _git(ws, "remote").stdout.strip():
        steps.append("no remote configured; skipped pull/push")
        return steps
    _ok(_git(ws, "pull", "--rebase", "--autostash"), "pull")
    steps.append("pulled")
    _ok(_git(ws, "push"), "push")
    steps.append("pushed")
    return steps
