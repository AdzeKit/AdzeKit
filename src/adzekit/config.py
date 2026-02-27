"""Configuration for AdzeKit.

Reads settings from environment variables, the ``.adzekit`` config file
in the shed directory, or explicit constructor arguments.
The shed path defaults to ~/adzekit/.

Settings resolution order:
  1. Explicit keyword arguments (e.g. ``Settings(shed=...)``)
  2. Environment variables (``ADZEKIT_SHED``, ``ADZEKIT_RCLONE_REMOTE``, etc.)
  3. ``.adzekit`` config file inside the shed directory
  4. Field defaults

If git_repo is set, the shed is backed by a git repository.
The sync_shed() method clones or pulls to keep the local copy
up to date, and commit_shed() stages, commits, and pushes changes.
"""

import os
import shutil
import subprocess
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKBONE_VERSION = 1
MARKER_FILE = ".adzekit"

# Defaults -- overridden per-shed via the .adzekit config file.
DEFAULT_MAX_ACTIVE_PROJECTS = 3
DEFAULT_MAX_DAILY_TASKS = 5
DEFAULT_LOOP_SLA_HOURS = 24
DEFAULT_STALE_LOOP_DAYS = 7


def _parse_kv_file(path: Path) -> dict[str, str]:
    """Parse a simple ``key = value`` file into a dict."""
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, val = line.partition("=")
        if sep:
            data[key.strip()] = val.strip()
    return data


class ShedNotInitializedError(RuntimeError):
    """Raised when operating on a directory that hasn't been initialized."""

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(
            f"{path} is not an AdzeKit shed.\n"
            f"\n"
            f"  To create a new shed here:\n"
            f"    adzekit init {path}\n"
            f"\n"
            f"  To point at an existing shed:\n"
            f"    adzekit --shed /path/to/shed <command>\n"
            f"    export ADZEKIT_SHED=/path/to/shed"
        )


class Settings(BaseSettings):
    """AdzeKit application settings."""

    model_config = SettingsConfigDict(
        env_prefix="ADZEKIT_",
        extra="ignore",
        populate_by_name=True,
    )

    shed: Path = Field(
        default=Path.home() / "adzekit",
        description="Root directory of the AdzeKit shed.",
    )

    git_repo: str = Field(
        default="",
        description="Git remote URL for the shed repo.",
    )
    git_branch: str = Field(
        default="main",
        description="Branch to use when syncing with the git remote.",
    )

    rclone_remote: str = Field(
        default="",
        description=(
            "rclone remote base path, e.g. 'gdrive:adzekit'. "
            "stock/ and drafts/ are synced as subdirectories under this path."
        ),
    )

    @model_validator(mode="after")
    def _load_shed_config(self) -> "Settings":
        """Load connection settings from the shed's .adzekit config file.

        Environment variables take precedence. For fields still at their
        default and not set via an env var, values from .adzekit are used.
        """
        marker = self.shed / MARKER_FILE
        if not marker.is_file():
            return self

        config = _parse_kv_file(marker)

        # Map .adzekit keys to Settings field names and their env var names.
        field_map = {
            "rclone_remote": "ADZEKIT_RCLONE_REMOTE",
            "git_repo": "ADZEKIT_GIT_REPO",
            "git_branch": "ADZEKIT_GIT_BRANCH",
        }
        for field_name, env_key in field_map.items():
            if env_key in os.environ:
                continue
            val = config.get(field_name)
            if val and getattr(self, field_name) == type(self).model_fields[field_name].default:
                object.__setattr__(self, field_name, val)

        return self

    # --- Derived shed paths (v1 backbone) ---

    @property
    def loops_dir(self) -> Path:
        return self.shed / "loops"

    @property
    def loops_open(self) -> Path:
        return self.loops_dir / "open.md"

    @property
    def loops_closed_dir(self) -> Path:
        return self.loops_dir / "closed"

    @property
    def projects_dir(self) -> Path:
        return self.shed / "projects"

    @property
    def active_dir(self) -> Path:
        return self.projects_dir

    @property
    def backlog_dir(self) -> Path:
        return self.projects_dir / "backlog"

    @property
    def archive_dir(self) -> Path:
        return self.projects_dir / "archive"

    @property
    def daily_dir(self) -> Path:
        return self.shed / "daily"

    @property
    def knowledge_dir(self) -> Path:
        return self.shed / "knowledge"

    @property
    def reviews_dir(self) -> Path:
        return self.shed / "reviews"

    @property
    def inbox_path(self) -> Path:
        return self.shed / "inbox.md"

    @property
    def stock_dir(self) -> Path:
        return self.shed / "stock"

    @property
    def drafts_dir(self) -> Path:
        return self.shed / "drafts"

    @property
    def marker_path(self) -> Path:
        return self.shed / MARKER_FILE

    @property
    def is_initialized(self) -> bool:
        """True if this shed has a .adzekit marker file."""
        return self.marker_path.exists()

    def _read_marker(self) -> dict[str, str]:
        """Parse the .adzekit config file into a key-value dict."""
        return _parse_kv_file(self.marker_path)

    @property
    def shed_backbone_version(self) -> int | None:
        """Read the backbone version from the .adzekit marker, or None."""
        raw = self._read_marker().get("backbone_version")
        if raw is None:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    @property
    def max_active_projects(self) -> int:
        raw = self._read_marker().get("max_active_projects")
        return int(raw) if raw else DEFAULT_MAX_ACTIVE_PROJECTS

    @property
    def max_daily_tasks(self) -> int:
        raw = self._read_marker().get("max_daily_tasks")
        return int(raw) if raw else DEFAULT_MAX_DAILY_TASKS

    @property
    def loop_sla_hours(self) -> int:
        raw = self._read_marker().get("loop_sla_hours")
        return int(raw) if raw else DEFAULT_LOOP_SLA_HOURS

    @property
    def stale_loop_days(self) -> int:
        raw = self._read_marker().get("stale_loop_days")
        return int(raw) if raw else DEFAULT_STALE_LOOP_DAYS

    def require_initialized(self) -> None:
        """Raise ShedNotInitializedError if this shed has no .adzekit marker."""
        if not self.is_initialized:
            raise ShedNotInitializedError(self.shed)

    def write_marker(self) -> None:
        """Write the .adzekit config file.

        Preserves any existing user-configured values and fills in
        defaults for keys that don't exist yet.
        """
        self.shed.mkdir(parents=True, exist_ok=True)
        existing = self._read_marker()

        lines = [
            f"backbone_version = {BACKBONE_VERSION}",
            f"max_active_projects = {existing.get('max_active_projects', DEFAULT_MAX_ACTIVE_PROJECTS)}",
            f"max_daily_tasks = {existing.get('max_daily_tasks', DEFAULT_MAX_DAILY_TASKS)}",
            f"loop_sla_hours = {existing.get('loop_sla_hours', DEFAULT_LOOP_SLA_HOURS)}",
            f"stale_loop_days = {existing.get('stale_loop_days', DEFAULT_STALE_LOOP_DAYS)}",
        ]

        # Connection settings -- only written when they have a value.
        rclone = existing.get("rclone_remote", "") or self.rclone_remote
        git = existing.get("git_repo", "") or self.git_repo
        git_br = existing.get("git_branch", "") or self.git_branch

        if rclone:
            lines.append(f"rclone_remote = {rclone}")
        if git:
            lines.append(f"git_repo = {git}")
            lines.append(f"git_branch = {git_br}")

        self.marker_path.write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8",
        )

    def set_config(self, key: str, value: str) -> None:
        """Set a single key in the .adzekit config file."""
        existing = self._read_marker()
        existing[key] = value
        lines = [f"{k} = {v}" for k, v in existing.items()]
        self.marker_path.write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8",
        )

    @property
    def has_rclone_remote(self) -> bool:
        return bool(self.rclone_remote)

    @property
    def rclone_stock_remote(self) -> str:
        """Remote path for stock/, e.g. 'gdrive:adzekit/stock'."""
        return f"{self.rclone_remote.rstrip('/')}/stock"

    @property
    def rclone_drafts_remote(self) -> str:
        """Remote path for drafts/, e.g. 'gdrive:adzekit/drafts'."""
        return f"{self.rclone_remote.rstrip('/')}/drafts"

    @property
    def is_git_backed(self) -> bool:
        return bool(self.git_repo)

    def ensure_shed(self) -> None:
        """Create the full shed directory tree."""
        for d in [
            self.loops_dir,
            self.loops_closed_dir,
            self.projects_dir,
            self.backlog_dir,
            self.archive_dir,
            self.daily_dir,
            self.knowledge_dir,
            self.reviews_dir,
            self.stock_dir,
            self.drafts_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

        for f in [self.loops_open, self.inbox_path]:
            if not f.exists():
                f.write_text("", encoding="utf-8")

        # Keep stock/ and drafts/ out of git
        gitignore = self.shed / ".gitignore"
        ignore_entries = ["stock/", "drafts/"]
        if gitignore.exists():
            content = gitignore.read_text(encoding="utf-8")
            for entry in ignore_entries:
                if entry not in content:
                    content = content.rstrip() + f"\n{entry}\n"
            gitignore.write_text(content, encoding="utf-8")
        else:
            gitignore.write_text("\n".join(ignore_entries) + "\n", encoding="utf-8")

    # --- Git operations ---

    def _run_git(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=cwd or self.shed,
            capture_output=True,
            text=True,
            check=True,
        )

    def sync_shed(self) -> None:
        """Clone or pull the shed repo."""
        if not self.is_git_backed:
            raise ValueError("git_repo is not configured. Set ADZEKIT_GIT_REPO.")

        root = self.shed
        if root.exists() and (root / ".git").is_dir():
            self._run_git("fetch", "origin", self.git_branch)
            self._run_git("merge", "--ff-only", f"origin/{self.git_branch}")
        else:
            root.mkdir(parents=True, exist_ok=True)
            self._run_git(
                "clone", "--branch", self.git_branch, self.git_repo, str(root),
                cwd=root.parent,
            )

    def commit_shed(self, message: str = "adzekit: sync") -> bool:
        """Stage, commit, and push. Returns True if a commit was made."""
        if not self.is_git_backed:
            raise ValueError("git_repo is not configured. Set ADZEKIT_GIT_REPO.")

        self._run_git("add", "-A")

        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=self.shed,
            capture_output=True,
        )
        if result.returncode == 0:
            return False

        self._run_git("commit", "-m", message)
        self._run_git("push", "origin", self.git_branch)
        return True

    def shed_git_status(self) -> str:
        if not self.is_git_backed:
            return ""
        if not (self.shed / ".git").is_dir():
            return ""
        result = self._run_git("status", "--short")
        return result.stdout

    # --- rclone operations (workbench: stock/ + drafts/) ---

    def _check_rclone(self) -> None:
        """Raise if rclone is not installed."""
        if shutil.which("rclone") is None:
            raise RuntimeError(
                "rclone is not installed. Install with: brew install rclone"
            )

    def _require_rclone_remote(self) -> None:
        if not self.has_rclone_remote:
            raise ValueError(
                "rclone_remote is not configured. "
                "Run 'adzekit setup-sync' or set ADZEKIT_RCLONE_REMOTE."
            )

    def _rclone_pull(self, remote: str, local: Path) -> None:
        """Pull from remote to local, tolerating a missing remote dir."""
        local.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["rclone", "sync", remote, str(local), "--create-empty-src-dirs"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # rclone exits 3 for "directory not found" -- normal on first use
            if "directory not found" in (result.stderr or ""):
                return
            raise subprocess.CalledProcessError(
                result.returncode,
                result.args,
                output=result.stdout,
                stderr=result.stderr,
            )

    def _rclone_push(self, local: Path, remote: str) -> None:
        """Push from local to remote (creates remote dir automatically)."""
        local.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["rclone", "sync", str(local), remote, "--create-empty-src-dirs"],
            check=True,
        )

    def sync_stock(self) -> None:
        """Pull stock/ from the rclone remote."""
        self._require_rclone_remote()
        self._check_rclone()
        self._rclone_pull(self.rclone_stock_remote, self.stock_dir)

    def push_stock(self) -> None:
        """Push local stock/ to the rclone remote."""
        self._require_rclone_remote()
        self._check_rclone()
        self._rclone_push(self.stock_dir, self.rclone_stock_remote)

    def sync_drafts(self) -> None:
        """Pull drafts/ from the rclone remote."""
        self._require_rclone_remote()
        self._check_rclone()
        self._rclone_pull(self.rclone_drafts_remote, self.drafts_dir)

    def push_drafts(self) -> None:
        """Push local drafts/ to the rclone remote."""
        self._require_rclone_remote()
        self._check_rclone()
        self._rclone_push(self.drafts_dir, self.rclone_drafts_remote)

    def sync_workbench(self) -> None:
        """Pull both stock/ and drafts/ from the rclone remote."""
        self.sync_stock()
        self.sync_drafts()

    def push_workbench(self) -> None:
        """Push both stock/ and drafts/ to the rclone remote."""
        self.push_stock()
        self.push_drafts()


def get_settings() -> Settings:
    return Settings()
