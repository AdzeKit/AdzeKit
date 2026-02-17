"""Workspace initialization and management.

Creates the v1 directory tree, seeds template files, and validates workspace health.
"""

from datetime import date
from pathlib import Path

from adzekit.config import Settings, get_settings


def init_workspace(settings: Settings | None = None) -> Path:
    """Create or verify the AdzeKit workspace directory tree.

    Seeds example files for every backbone file type on first run.
    Returns the workspace root path.
    """
    settings = settings or get_settings()
    settings.ensure_workspace()
    today = date.today()
    iso = today.isoformat()

    # Seed inbox.md if empty
    if settings.inbox_path.stat().st_size == 0:
        settings.inbox_path.write_text(
            f"""---
id: inbox
created_at: {iso}
updated_at: {iso}
tags: []
---

# Inbox

Capture anything here. No structure needed.

- [{iso}] Example: remember to follow up with Alice about the API estimate
""",
            encoding="utf-8",
        )

    # Seed loops/open.md with an example loop if empty
    if settings.loops_open.stat().st_size == 0:
        settings.loops_open.write_text(
            f"""---
id: open-loops
created_at: {iso}
updated_at: {iso}
tags: []
---

# Open Loops

## [{iso}] Example: Send Alice the API estimate

- **Who:** Alice
- **What:** Provide architecture proposal and timeline estimate
- **Due:** {iso}
- **Status:** Open
- **Next:** Draft estimate and send by end of week

""",
            encoding="utf-8",
        )

    # Seed today's daily note
    create_daily_note(today, settings)

    # Seed one active project if active/ is empty
    if not any(settings.active_dir.iterdir()):
        create_project("example-project", title="Example Project", backlog=False, settings=settings)

    # Seed one weekly review if reviews/ is empty
    if not any(settings.reviews_dir.iterdir()):
        _seed_review(today, settings)

    # Seed one knowledge note if knowledge/ is empty
    if not any(settings.knowledge_dir.iterdir()):
        _seed_knowledge_note(iso, settings)

    return settings.workspace


def _seed_review(today: date, settings: Settings) -> None:
    """Create an example weekly review file."""
    iso = today.isoformat()
    week_num = today.isocalendar()[1]
    year = today.year
    review_id = f"{year}-W{week_num:02d}"
    path = settings.reviews_dir / f"{review_id}.md"

    path.write_text(
        f"""---
id: "{review_id}"
created_at: {iso}
updated_at: {iso}
tags: []
---

# Weekly Review -- {year} Week {week_num:02d}

## Open Loops
- Review all loops in `loops/open.md`
- For each: act on it, schedule it, or close it

## Active Projects
- Check progress on each project in `projects/active/`
- Any project stale for >7 days? Kill, defer, or commit.

## Decisions
- What am I saying no to this week?
- What trade-offs am I not admitting to myself?

## Reflection
- What drained me this week?
- What energized me?
- What will I stop doing next week?
""",
        encoding="utf-8",
    )


def _seed_knowledge_note(iso: str, settings: Settings) -> None:
    """Create an example knowledge note."""
    path = settings.knowledge_dir / "example-note.md"

    path.write_text(
        f"""---
id: example-note
created_at: {iso}
updated_at: {iso}
tags:
  - example
---

# Example Knowledge Note

Evergreen notes capture ideas you want to keep and revisit.

Write one concept per file. Use `updated_at` to track when you last reviewed it.
Link to related notes with [[wikilinks]].
""",
        encoding="utf-8",
    )


def create_daily_note(
    target_date: date | None = None,
    settings: Settings | None = None,
) -> Path:
    """Create a daily note from the template if one doesn't exist."""
    settings = settings or get_settings()
    target_date = target_date or date.today()
    weekday = target_date.strftime("%A")
    iso = target_date.isoformat()
    path = settings.daily_dir / f"{iso}.md"

    if path.exists():
        return path

    template = f"""---
id: "{iso}"
created_at: {iso}
updated_at: {iso}
tags: []
---

# {iso} {weekday}

## Morning: Intention
- [ ] Top priority:
- [ ] Close loop:

## Log

## Evening: Reflection
- **Finished:**
- **Blocked:**
- **Tomorrow:**
"""
    path.write_text(template, encoding="utf-8")
    return path


def create_project(
    slug: str,
    title: str = "",
    backlog: bool = True,
    settings: Settings | None = None,
) -> Path:
    """Scaffold a new project directory.

    Creates README.md, tasks.md, notes.md.
    New projects go to backlog/ by default.
    """
    settings = settings or get_settings()
    parent = settings.backlog_dir if backlog else settings.active_dir
    project_dir = parent / slug
    project_dir.mkdir(parents=True, exist_ok=True)

    title = title or slug
    today = date.today().isoformat()

    readme = f"""---
id: "{slug}"
created_at: {today}
updated_at: {today}
tags: []
---

# {title}

## Context

## Goals
"""
    (project_dir / "README.md").write_text(readme, encoding="utf-8")
    (project_dir / "tasks.md").write_text(
        f"""---
id: "{slug}-tasks"
created_at: {today}
updated_at: {today}
tags: []
---

# Tasks

- [ ] Define project scope
- [ ] Set up initial structure
""",
        encoding="utf-8",
    )
    (project_dir / "notes.md").write_text(
        f"""---
id: "{slug}-notes"
created_at: {today}
updated_at: {today}
tags: []
---

# Notes

""",
        encoding="utf-8",
    )

    return project_dir
