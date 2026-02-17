"""Configuration for AdzeKit.

Reads settings from environment variables, a .env file, or explicit
constructor arguments. The workspace path defaults to ~/adzekit/.

If git_repo is set, the workspace is backed by a git repository.
The sync_workspace() method clones or pulls to keep the local copy
up to date, and commit_workspace() stages, commits, and pushes changes.
"""

import subprocess
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

MAX_ACTIVE_PROJECTS = 3
MAX_DAILY_TASKS = 5
LOOP_SLA_HOURS = 24
STALE_LOOP_DAYS = 7


class Settings(BaseSettings):
    """AdzeKit application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ADZEKIT_",
        extra="ignore",
        populate_by_name=True,
    )

    workspace: Path = Field(
        default=Path.home() / "adzekit",
        description="Root directory of the AdzeKit workspace.",
    )

    git_repo: str = Field(
        default="",
        description="Git remote URL for the vault repo.",
    )
    git_branch: str = Field(
        default="main",
        description="Branch to use when syncing with the git remote.",
    )

    # --- Derived workspace paths (v1 backbone) ---

    @property
    def loops_dir(self) -> Path:
        return self.workspace / "loops"

    @property
    def loops_open(self) -> Path:
        return self.loops_dir / "open.md"

    @property
    def loops_closed_dir(self) -> Path:
        return self.loops_dir / "closed"

    @property
    def projects_dir(self) -> Path:
        return self.workspace / "projects"

    @property
    def active_dir(self) -> Path:
        return self.projects_dir / "active"

    @property
    def backlog_dir(self) -> Path:
        return self.projects_dir / "backlog"

    @property
    def archive_dir(self) -> Path:
        return self.projects_dir / "archive"

    @property
    def daily_dir(self) -> Path:
        return self.workspace / "daily"

    @property
    def knowledge_dir(self) -> Path:
        return self.workspace / "knowledge"

    @property
    def reviews_dir(self) -> Path:
        return self.workspace / "reviews"

    @property
    def inbox_path(self) -> Path:
        return self.workspace / "inbox.md"

    @property
    def is_git_backed(self) -> bool:
        return bool(self.git_repo)

    def ensure_workspace(self) -> None:
        """Create the full workspace directory tree."""
        for d in [
            self.loops_dir,
            self.loops_closed_dir,
            self.active_dir,
            self.backlog_dir,
            self.archive_dir,
            self.daily_dir,
            self.knowledge_dir,
            self.reviews_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

        for f in [self.loops_open, self.inbox_path]:
            if not f.exists():
                f.write_text("", encoding="utf-8")

    # --- Git operations ---

    def _run_git(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=cwd or self.workspace,
            capture_output=True,
            text=True,
            check=True,
        )

    def sync_workspace(self) -> None:
        """Clone or pull the vault repo."""
        if not self.is_git_backed:
            raise ValueError("git_repo is not configured. Set ADZEKIT_GIT_REPO.")

        ws = self.workspace
        if ws.exists() and (ws / ".git").is_dir():
            self._run_git("fetch", "origin", self.git_branch)
            self._run_git("merge", "--ff-only", f"origin/{self.git_branch}")
        else:
            ws.mkdir(parents=True, exist_ok=True)
            self._run_git(
                "clone", "--branch", self.git_branch, self.git_repo, str(ws),
                cwd=ws.parent,
            )

    def commit_workspace(self, message: str = "adzekit: sync") -> bool:
        """Stage, commit, and push. Returns True if a commit was made."""
        if not self.is_git_backed:
            raise ValueError("git_repo is not configured. Set ADZEKIT_GIT_REPO.")

        self._run_git("add", "-A")

        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=self.workspace,
            capture_output=True,
        )
        if result.returncode == 0:
            return False

        self._run_git("commit", "-m", message)
        self._run_git("push", "origin", self.git_branch)
        return True

    def workspace_git_status(self) -> str:
        if not self.is_git_backed:
            return ""
        if not (self.workspace / ".git").is_dir():
            return ""
        result = self._run_git("status", "--short")
        return result.stdout


def get_settings() -> Settings:
    return Settings()
