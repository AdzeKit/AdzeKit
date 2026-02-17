"""Loaders for AdzeKit.

Thin wrappers that read backbone files and return typed objects.
"""

from datetime import date

from adzekit.config import Settings, get_settings
from adzekit.models import DailyNote, Loop, Project, ProjectState
from adzekit.parser import parse_daily_note, parse_loops, parse_project


def load_open_loops(settings: Settings | None = None) -> list[Loop]:
    """Load all loops from loops/open.md."""
    settings = settings or get_settings()
    if not settings.loops_open.exists():
        return []
    text = settings.loops_open.read_text(encoding="utf-8")
    if not text.strip():
        return []
    return parse_loops(text)


def load_projects(
    state: ProjectState | None = None,
    settings: Settings | None = None,
) -> list[Project]:
    """Load projects, optionally filtered by state."""
    settings = settings or get_settings()
    projects: list[Project] = []
    state_dirs = {
        ProjectState.ACTIVE: settings.active_dir,
        ProjectState.BACKLOG: settings.backlog_dir,
        ProjectState.ARCHIVE: settings.archive_dir,
    }

    targets = {state: state_dirs[state]} if state and state in state_dirs else state_dirs

    for proj_state, parent in targets.items():
        if not parent.exists():
            continue
        for f in sorted(parent.iterdir()):
            if f.is_file() and f.suffix == ".md":
                projects.append(parse_project(f, proj_state))

    return projects


def load_daily_note(
    target_date: date | None = None,
    settings: Settings | None = None,
) -> DailyNote | None:
    """Load a single daily note by date."""
    settings = settings or get_settings()
    target_date = target_date or date.today()
    path = settings.daily_dir / f"{target_date.isoformat()}.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    return parse_daily_note(text, target_date)
