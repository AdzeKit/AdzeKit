"""Git sync: the one channel between laptops, phones, and cloud agents.

Two guarantees:

* The repository is never left mid-rebase. If git can't finish, the rebase is
  aborted and your work stays committed locally.
* Nobody's text is discarded. Record folders merge by union (see the generated
  ``.gitattributes``), so two devices appending to the same note keep both
  lines. Anything git still can't merge is reported, not guessed.
"""

from __future__ import annotations

import socket
import subprocess
from datetime import datetime
from pathlib import Path

from adzekit.shed import Workspace, WorkspaceError


def _git(ws: Workspace, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(ws.root), *args], capture_output=True, text=True)


def _in_progress(ws: Workspace) -> str | None:
    git_dir = Path(_git(ws, "rev-parse", "--absolute-git-dir").stdout.strip())
    if (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists():
        return "rebase"
    if (git_dir / "MERGE_HEAD").exists():
        return "merge"
    return None


def _first_line(result: subprocess.CompletedProcess[str]) -> str:
    text = (result.stderr or result.stdout).strip()
    return text.splitlines()[0] if text else f"exit {result.returncode}"


def sync(ws: Workspace, message: str | None = None) -> list[str]:
    """Commit local changes, rebase onto the remote, push. Returns what happened."""
    if _git(ws, "rev-parse", "--is-inside-work-tree").returncode != 0:
        raise WorkspaceError(f"{ws.root} is not a git repository. Run `adzekit init {ws.root}`.")
    if op := _in_progress(ws):
        raise WorkspaceError(f"A git {op} is already in progress in {ws.root}. "
                             f"Finish it or run `git {op} --abort`, then sync again.")

    steps = []
    _git(ws, "add", "-A")
    if _git(ws, "diff", "--cached", "--quiet").returncode != 0:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        commit = _git(ws, "commit", "-q", "-m", message or f"sync: {socket.gethostname()} {stamp}")
        if commit.returncode != 0:
            raise WorkspaceError(f"git commit failed: {_first_line(commit)}")
        steps.append("committed local changes")

    # Only `origin` is ever pushed to, so parking a remote under another name is
    # a reliable way to keep a shed local.
    if "origin" not in _git(ws, "remote").stdout.split():
        return steps + ["no origin remote; kept local"]
    remote = "origin"
    branch = _git(ws, "branch", "--show-current").stdout.strip()
    if not branch:
        raise WorkspaceError("HEAD is detached; check out a branch before syncing.")

    for attempt in range(2):
        fetch = _git(ws, "fetch", "-q", remote)
        if fetch.returncode != 0:
            raise WorkspaceError(f"Couldn't reach {remote}: {_first_line(fetch)}. "
                                 "Your changes are committed locally; sync again later.")
        upstream = f"refs/remotes/{remote}/{branch}"
        if _git(ws, "rev-parse", "--verify", "-q", upstream).returncode == 0:
            rebase = _git(ws, "rebase", "--autostash", f"{remote}/{branch}")
            if rebase.returncode != 0:
                conflicted = _git(ws, "diff", "--name-only", "--diff-filter=U").stdout.split()
                _git(ws, "rebase", "--abort")
                listing = "\n".join(f"  - {name}" for name in conflicted) or "  (see git status)"
                raise WorkspaceError(
                    "Couldn't combine your changes with the remote automatically. Nothing was "
                    f"lost: your work is committed locally. Files involved:\n{listing}\n"
                    f"Merge them by hand (`git pull --rebase {remote} {branch}`), then sync again."
                )
            if "pulled" not in steps:
                steps.append("pulled")
        push = _git(ws, "push", "-q", "-u", remote, branch)
        if push.returncode == 0:
            return steps + ["pushed"]
        if attempt == 0 and ("rejected" in push.stderr or "fetch first" in push.stderr):
            continue  # someone pushed between our fetch and push; go around once more
        raise WorkspaceError(f"git push failed: {_first_line(push)}")
    raise WorkspaceError("The remote kept moving; sync again in a moment.")
