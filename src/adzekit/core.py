"""Small, transport-neutral API for an AdzeKit workspace.

The CLI, MCP server, web handlers, and agent adapters should be thin wrappers
around this module.  Values returned here contain only JSON-safe primitives so
callers do not need to understand AdzeKit's parser models.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from adzekit.config import Settings
from adzekit.models import ProjectState


class Workspace:
    """An explicit handle to one AdzeKit workspace.

    No global config or environment variables are consulted.  This makes the
    object safe to construct per request in web applications and per tool call
    in agent runtimes.
    """

    def __init__(self, root: str | Path, *, require_initialized: bool = True) -> None:
        self.root = Path(root).expanduser().resolve()
        self.settings = Settings(shed=self.root)
        if require_initialized:
            self.settings.require_initialized()

    @classmethod
    def initialize(cls, root: str | Path) -> "Workspace":
        """Create a workspace and return an explicit handle to it."""
        from adzekit.workspace import init_shed

        instance = cls(root, require_initialized=False)
        init_shed(instance.settings)
        return instance

    def loops(self) -> list[dict[str, Any]]:
        """Return open commitments as JSON-safe records."""
        from adzekit.preprocessor import load_active_loops

        return [
            {
                "title": loop.title,
                "size": loop.size or "",
                "date": loop.date.isoformat() if loop.date else None,
                "due": loop.due.isoformat() if loop.due else None,
                "status": loop.status,
                "who": loop.who,
                "next_action": loop.next_action,
                "project": loop.project,
            }
            for loop in load_active_loops(self.settings)
        ]

    def projects(self, state: str = "active") -> list[dict[str, Any]]:
        """Return projects in one lifecycle state."""
        from adzekit.preprocessor import load_projects

        try:
            project_state = ProjectState(state)
        except ValueError as exc:
            raise ValueError("state must be active, backlog, or archive") from exc
        return [
            {
                "slug": project.slug,
                "title": project.title,
                "state": project.state.value,
                "progress": project.progress,
            }
            for project in load_projects(state=project_state, settings=self.settings)
        ]

    def today(self, target_date: date | None = None) -> dict[str, Any] | None:
        """Return a daily note without creating it, or ``None`` when absent."""
        from adzekit.preprocessor import load_daily_note

        target_date = target_date or date.today()
        note = load_daily_note(target_date=target_date, settings=self.settings)
        if note is None:
            return None
        return {"date": note.date.isoformat(), "markdown": note.raw_content}

    def knowledge(self, slug: str) -> dict[str, str] | None:
        """Return one knowledge note. Slugs cannot escape ``knowledge/``."""
        if not slug or Path(slug).name != slug or slug in {".", ".."}:
            raise ValueError("slug must be a single filename stem")
        path = self.settings.knowledge_dir / f"{slug}.md"
        if not path.is_file():
            return None
        return {"slug": slug, "markdown": path.read_text(encoding="utf-8")}

    def inbox(self) -> list[dict[str, Any]]:
        """Return pending agent proposals."""
        from adzekit.modules.drafts import parse_inbox

        return [
            {
                "index": entry.index,
                "date": entry.date,
                "time": entry.time,
                "skill": entry.skill,
                "summary": entry.summary,
                "path": entry.path,
            }
            for entry in parse_inbox(self.settings)
        ]

    def propose(
        self,
        *,
        workflow: str,
        markdown: str,
        summary: str = "",
        confidence: float | None = None,
        source: str = "api",
    ) -> dict[str, Any]:
        """Create a reviewable proposal; never write to human-owned files."""
        from adzekit.preprocessor import write_draft_with_frontmatter

        path = write_draft_with_frontmatter(
            workflow,
            markdown,
            settings=self.settings,
            summary=summary,
            confidence=confidence,
            trigger=source,
        )
        relative = path.resolve().relative_to(self.settings.drafts_dir.resolve())
        return {
            "path": (Path("drafts") / relative).as_posix(),
            "workflow": workflow,
            "summary": summary,
        }

    def snapshot(self) -> dict[str, Any]:
        """Return the small, common read model used by UIs and agents."""
        return {
            "version": 1,
            "workspace": str(self.root),
            "today": self.today(),
            "loops": self.loops(),
            "projects": self.projects(),
            "inbox": self.inbox(),
        }
