"""Git-backed file age utility.

Uses git history to determine when files were created and last modified,
without requiring any embedded metadata or frontmatter.
"""

import subprocess
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from adzekit.config import Settings, get_settings


@dataclass
class FileAge:
    """Git-derived timestamps for a single file."""

    path: Path
    created: date | None = None
    modified: date | None = None

    @property
    def age_days(self) -> int | None:
        """Days since the file was created."""
        if self.created is None:
            return None
        return (date.today() - self.created).days

    @property
    def stale_days(self) -> int | None:
        """Days since the file was last modified."""
        if self.modified is None:
            return None
        return (date.today() - self.modified).days


def _git_date(args: list[str], cwd: Path) -> date | None:
    """Run a git log command and parse the ISO date from stdout."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        output = result.stdout.strip()
        if not output:
            return None
        return datetime.fromisoformat(output).date()
    except (subprocess.CalledProcessError, ValueError):
        return None


def file_age(path: Path, settings: Settings | None = None) -> FileAge:
    """Get git-derived creation and modification dates for a file."""
    settings = settings or get_settings()
    cwd = settings.workspace
    rel = path.relative_to(cwd) if path.is_absolute() else path

    created = _git_date(
        ["log", "--diff-filter=A", "--follow", "--format=%aI", "--", str(rel)],
        cwd=cwd,
    )
    modified = _git_date(
        ["log", "-1", "--format=%aI", "--", str(rel)],
        cwd=cwd,
    )
    return FileAge(path=path, created=created, modified=modified)


def project_ages(settings: Settings | None = None) -> list[FileAge]:
    """Get ages for all project files, sorted oldest-modified first."""
    settings = settings or get_settings()
    ages = []
    for d in [settings.projects_dir, settings.active_dir, settings.backlog_dir]:
        if not d.exists():
            continue
        for f in sorted(d.glob("*.md")):
            ages.append(file_age(f, settings))
    ages.sort(key=lambda a: a.stale_days or 0, reverse=True)
    return ages
