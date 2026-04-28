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

from pathlib import Path

from adzekit.config import Settings, get_settings
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
    cap = settings.max_active_projects
    if n >= cap:
        return False, (
            f"WIP limit reached: {n}/{cap} active projects. "
            "Archive or complete a project before activating a new one."
        )
    return True, f"WIP OK: {n}/{cap} active slots used."


def activate_project(project_slug: str, settings: Settings | None = None) -> Path:
    """Move a project from backlog/ to active/.

    Raises ValueError if the WIP limit would be exceeded.
    Returns the new project file path.
    """
    settings = settings or get_settings()
    allowed, reason = can_activate(settings)
    if not allowed:
        raise ValueError(reason)

    src = settings.backlog_dir / f"{project_slug}.md"
    if not src.exists():
        raise FileNotFoundError(f"Project '{project_slug}' not found in backlog/.")
    dst = settings.active_dir / f"{project_slug}.md"
    src.rename(dst)
    return dst


def archive_project(project_slug: str, settings: Settings | None = None) -> Path:
    """Move a project from active/ to archive/.

    Returns the new project file path.
    """
    settings = settings or get_settings()
    src = settings.active_dir / f"{project_slug}.md"
    if not src.exists():
        raise FileNotFoundError(f"Project '{project_slug}' not found in active/.")
    dst = settings.archive_dir / f"{project_slug}.md"
    src.rename(dst)
    return dst


def demote_project(project_slug: str, settings: Settings | None = None) -> Path:
    """Move a project from active/ back to backlog/.

    Returns the new project file path.
    """
    settings = settings or get_settings()
    src = settings.active_dir / f"{project_slug}.md"
    if not src.exists():
        raise FileNotFoundError(f"Project '{project_slug}' not found in active/.")
    settings.backlog_dir.mkdir(parents=True, exist_ok=True)
    dst = settings.backlog_dir / f"{project_slug}.md"
    src.rename(dst)
    return dst


def stale_active_projects(
    settings: Settings | None = None,
    days: int | None = None,
) -> list[tuple]:
    """Return active projects whose markdown file hasn't been modified in N days.

    Uses git history (via git_age) when available, falling back to the file's
    mtime. Returns a list of (Project, days_inactive) tuples, oldest first.
    """
    from datetime import date as _date

    from adzekit.modules.git_age import file_age
    from adzekit.preprocessor import load_projects

    settings = settings or get_settings()
    threshold = days if days is not None else settings.stale_loop_days

    today = _date.today()
    results: list[tuple] = []

    for proj in load_projects(ProjectState.ACTIVE, settings):
        path = settings.active_dir / f"{proj.slug}.md"
        age = file_age(path, settings)
        # Prefer git-modified date; fall back to filesystem mtime.
        if age.modified is not None:
            inactive = (today - age.modified).days
        else:
            try:
                from datetime import datetime
                mtime = datetime.fromtimestamp(path.stat().st_mtime).date()
                inactive = (today - mtime).days
            except OSError:
                continue

        if inactive >= threshold:
            results.append((proj, inactive))

    results.sort(key=lambda x: -x[1])
    return results


def wip_status(settings: Settings | None = None) -> dict:
    """Return a summary of current WIP state."""
    settings = settings or get_settings()
    active = count_active_projects(settings)
    daily = count_daily_tasks(settings)
    max_proj = settings.max_active_projects
    max_tasks = settings.max_daily_tasks
    return {
        "active_projects": active,
        "max_active_projects": max_proj,
        "projects_available": max_proj - active,
        "daily_tasks": daily,
        "max_daily_tasks": max_tasks,
        "daily_available": max_tasks - daily,
    }
