"""Locate, create, and configure an AdzeKit workspace.

A workspace is a folder of Markdown with a ``.adzekit`` settings file at its
root. Nothing else is required; every folder below is a convention.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from importlib import resources
from pathlib import Path

MARKER = ".adzekit"

DEFAULTS = {
    "max_active_projects": 3,
    "max_daily_tasks": 5,
    "stale_loop_days": 7,
    "stale_project_days": 14,
}

FOLDERS = (
    "daily",
    "loops",
    "projects",
    "projects/backlog",
    "projects/archive",
    "knowledge",
    "reviews",
    "skills",
)

# Files copied from templates/ on init. Existing files are never overwritten.
TEMPLATE_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    ".gitignore",
    "skills/daily-start.md",
    "skills/daily-close.md",
    "skills/weekly-review.md",
    "skills/capture.md",
)


class WorkspaceError(Exception):
    """Raised when a workspace cannot be found or used."""


def global_config_path() -> Path:
    return Path.home() / ".config" / "adzekit" / "config"


def read_kv(path: Path) -> dict[str, str]:
    """Parse a ``key = value`` file, ignoring blanks and ``#`` comments."""
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def write_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


@dataclass(frozen=True)
class Workspace:
    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root).expanduser().resolve())

    # --- discovery -------------------------------------------------------

    @classmethod
    def find(cls, explicit: str | Path | None = None) -> "Workspace":
        """Resolve the workspace: flag, env, enclosing folder, then global config."""
        candidate = explicit or os.environ.get("ADZEKIT_WORKSPACE") or os.environ.get(
            "ADZEKIT_SHED"
        )
        if not candidate:
            here = Path.cwd().resolve()
            for folder in (here, *here.parents):
                if (folder / MARKER).is_file():
                    candidate = folder
                    break
        if not candidate:
            config = read_kv(global_config_path())
            candidate = config.get("workspace") or config.get("shed")
        if not candidate:
            raise WorkspaceError(
                "No workspace found. Run `adzekit init PATH`, pass --workspace, "
                "or set ADZEKIT_WORKSPACE."
            )
        ws = cls(Path(candidate))
        if not ws.marker.is_file():
            raise WorkspaceError(f"{ws.root} has no {MARKER} file. Run `adzekit init {ws.root}`.")
        return ws

    @classmethod
    def init(cls, root: str | Path) -> tuple["Workspace", list[str]]:
        """Create folders and starter files. Safe to re-run; never overwrites."""
        ws = cls(Path(root))
        created: list[str] = []
        ws.root.mkdir(parents=True, exist_ok=True)
        for folder in FOLDERS:
            path = ws.root / folder
            if not path.exists():
                path.mkdir(parents=True)
                created.append(folder + "/")

        starters = {
            MARKER: "# AdzeKit settings\n"
            + "".join(f"{k} = {v}\n" for k, v in DEFAULTS.items()),
            "loops/active.md": "# Active Loops\n",
            "loops/archive.md": "# Archived Loops\n",
        }
        templates = resources.files("adzekit") / "templates"
        for name in TEMPLATE_FILES:
            source = "gitignore" if name == ".gitignore" else name
            starters[name] = (templates / source).read_text(encoding="utf-8")

        for name, text in starters.items():
            path = ws.root / name
            if not path.exists():
                path.write_text(text, encoding="utf-8")
                created.append(name)

        config = global_config_path()
        if not config.exists():
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(f"workspace = {ws.root}\n", encoding="utf-8")
            created.append(str(config))
        return ws, created

    # --- settings --------------------------------------------------------

    @property
    def marker(self) -> Path:
        return self.root / MARKER

    def setting(self, key: str) -> int:
        raw = read_kv(self.marker).get(key)
        try:
            return int(raw) if raw is not None else DEFAULTS[key]
        except ValueError:
            return DEFAULTS[key]

    # --- paths -----------------------------------------------------------

    @property
    def daily_dir(self) -> Path:
        return self.root / "daily"

    def daily_path(self, day: date) -> Path:
        return self.daily_dir / f"{day.isoformat()}.md"

    @property
    def loops_file(self) -> Path:
        return self.root / "loops" / "active.md"

    @property
    def loops_archive(self) -> Path:
        return self.root / "loops" / "archive.md"

    @property
    def projects_dir(self) -> Path:
        return self.root / "projects"

    @property
    def reviews_dir(self) -> Path:
        return self.root / "reviews"
