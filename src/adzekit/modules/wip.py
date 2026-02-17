"""M2: WIP Gatekeeper.

Design doc Principle 1: Cap Work-in-Progress. Maximum 3 active projects.
Maximum 5 daily focus tasks. No exceptions -- only trade-offs.

The gatekeeper runs a 4-question filter before any new project enters
active status:
  1. Does this displace something more important?
  2. Can this realistically ship in 2 weeks?
  3. Who is this for, and do they actually need it now?
  4. What happens if I just don't do this?

The LLM can draft answers; the human decides.
"""

import shutil
from pathlib import Path

from adzekit.config import MAX_ACTIVE_PROJECTS, MAX_DAILY_TASKS, Settings, get_settings
from adzekit.models import ProjectState
from adzekit.preprocessor import load_daily_note, load_projects

WIP_QUESTIONS = [
    "Does this displace something more important?",
    "Can this realistically ship in 2 weeks?",
    "Who is this for, and do they actually need it now?",
    "What happens if I just don't do this?",
]


def count_active_projects(settings: Settings | None = None) -> int:
    """Return the number of currently active projects."""
    settings = settings or get_settings()
    projects = load_projects(ProjectState.ACTIVE, settings)
    return len(projects)


def count_daily_tasks(settings: Settings | None = None) -> int:
    """Return the number of intention items in today's daily note."""
    settings = settings or get_settings()
    daily = load_daily_note(settings=settings)
    if daily is None:
        return 0
    return len(daily.intentions)


def can_activate(settings: Settings | None = None) -> tuple[bool, str]:
    """Check whether a new project can enter active status.

    Returns (allowed, reason).
    """
    settings = settings or get_settings()
    n = count_active_projects(settings)
    if n >= MAX_ACTIVE_PROJECTS:
        return False, (
            f"WIP limit reached: {n}/{MAX_ACTIVE_PROJECTS} active projects. "
            "Archive or complete a project before activating a new one."
        )
    return True, f"WIP OK: {n}/{MAX_ACTIVE_PROJECTS} active slots used."


def activate_project(project_slug: str, settings: Settings | None = None) -> Path:
    """Move a project from backlog/ to active/.

    Raises ValueError if the WIP limit would be exceeded.
    Returns the new project directory path.
    """
    settings = settings or get_settings()
    allowed, reason = can_activate(settings)
    if not allowed:
        raise ValueError(reason)

    src = settings.backlog_dir / project_slug
    if not src.exists():
        raise FileNotFoundError(f"Project '{project_slug}' not found in backlog/.")
    dst = settings.active_dir / project_slug
    shutil.move(str(src), str(dst))
    return dst


def archive_project(project_slug: str, settings: Settings | None = None) -> Path:
    """Move a project from active/ to archive/.

    Returns the new project directory path.
    """
    settings = settings or get_settings()
    src = settings.active_dir / project_slug
    if not src.exists():
        raise FileNotFoundError(f"Project '{project_slug}' not found in active/.")
    dst = settings.archive_dir / project_slug
    shutil.move(str(src), str(dst))
    return dst


def wip_status(settings: Settings | None = None) -> dict:
    """Return a summary of current WIP state."""
    settings = settings or get_settings()
    active = count_active_projects(settings)
    daily = count_daily_tasks(settings)
    return {
        "active_projects": active,
        "max_active_projects": MAX_ACTIVE_PROJECTS,
        "projects_available": MAX_ACTIVE_PROJECTS - active,
        "daily_tasks": daily,
        "max_daily_tasks": MAX_DAILY_TASKS,
        "daily_available": MAX_DAILY_TASKS - daily,
    }
