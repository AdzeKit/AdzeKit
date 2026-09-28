"""Projects: one Markdown file each. The folder is the state.

    projects/*.md           active (capped by max_active_projects)
    projects/backlog/*.md   parked
    projects/archive/*.md   done or dropped
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from adzekit.workspace import Workspace, WorkspaceError

STATES = ("active", "backlog", "archive")

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_ISO_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


@dataclass
class Project:
    slug: str
    title: str
    state: str
    path: Path
    last_touched: date | None


def folder(ws: Workspace, state: str) -> Path:
    if state not in STATES:
        raise WorkspaceError(f"State must be one of: {', '.join(STATES)}.")
    return ws.projects_dir if state == "active" else ws.projects_dir / state


def last_touched(text: str, today: date) -> date | None:
    """Latest date written in the file that is not in the future."""
    seen = []
    for raw in _ISO_DATE.findall(text):
        try:
            seen.append(date.fromisoformat(raw))
        except ValueError:
            continue
    past = [d for d in seen if d <= today]
    return max(past) if past else None


def load(ws: Workspace, state: str, today: date) -> list[Project]:
    projects = []
    for path in sorted(folder(ws, state).glob("*.md")):
        text = path.read_text(encoding="utf-8")
        first = text.splitlines()[0] if text else ""
        title = first[2:].strip() if first.startswith("# ") else path.stem
        projects.append(Project(path.stem, title, state, path, last_touched(text, today)))
    return projects


def locate(ws: Workspace, slug: str) -> tuple[str, Path]:
    for state in STATES:
        path = folder(ws, state) / f"{slug}.md"
        if path.is_file():
            return state, path
    raise WorkspaceError(f"No project named {slug!r}.")


def _check_capacity(ws: Workspace, force: bool) -> None:
    cap = ws.setting("max_active_projects")
    active = sorted(p.stem for p in ws.projects_dir.glob("*.md"))
    if len(active) >= cap and not force:
        raise WorkspaceError(
            f"{len(active)}/{cap} active projects. Move one to backlog or archive first "
            f"(or pass --force):\n" + "\n".join(f"  - {s}" for s in active)
        )


def new(ws: Workspace, slug: str, *, today: date, title: str = "", state: str = "active",
        force: bool = False) -> Path:
    if not _SLUG.match(slug):
        raise WorkspaceError("Project slugs are lowercase letters, digits, and hyphens.")
    try:
        locate(ws, slug)
    except WorkspaceError:
        pass
    else:
        raise WorkspaceError(f"Project {slug!r} already exists.")
    if state == "active":
        _check_capacity(ws, force)
    path = folder(ws, state) / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    heading = title or slug.replace("-", " ").title()
    path.write_text(
        f"# {heading}\n\n## Context\n\n## Log\n- {today.isoformat()}: Created.\n",
        encoding="utf-8",
    )
    return path


def move(ws: Workspace, slug: str, state: str, *, force: bool = False) -> Path:
    current, path = locate(ws, slug)
    if current == state:
        return path
    if state == "active":
        _check_capacity(ws, force)
    target = folder(ws, state) / path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    path.rename(target)
    return target
