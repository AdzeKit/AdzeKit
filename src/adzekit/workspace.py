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
            f"""# Inbox

Capture anything here. No structure needed.

- [{iso}] Example: remember to follow up with Alice about the API estimate
""",
            encoding="utf-8",
        )

    # Seed loops/open.md with an example loop if empty
    if settings.loops_open.stat().st_size == 0:
        settings.loops_open.write_text(
            f"""# Open Loops

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
        _seed_knowledge_note(settings)

    return settings.workspace


def _seed_review(today: date, settings: Settings) -> None:
    """Create an example weekly review file."""
    week_num = today.isocalendar()[1]
    year = today.year
    review_id = f"{year}-W{week_num:02d}"
    path = settings.reviews_dir / f"{review_id}.md"

    path.write_text(
        f"""# Weekly Review -- {year} Week {week_num:02d}

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


def _seed_knowledge_note(settings: Settings) -> None:
    """Create an example knowledge note."""
    path = settings.knowledge_dir / "example-note.md"

    path.write_text(
        """# Example Knowledge Note

#example

Evergreen notes capture ideas you want to keep and revisit.

Write one concept per file. Link to related notes with [[wikilinks]].
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

    template = f"""# {iso} {weekday}

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
    """Create a new project markdown file.

    New projects go to backlog/ by default.
    """
    settings = settings or get_settings()
    parent = settings.backlog_dir if backlog else settings.active_dir
    path = parent / f"{slug}.md"

    if path.exists():
        return path

    title = title or slug

    template = f"""# {title}

## Tasks
- [ ] Define project scope

## Log

"""
    path.write_text(template, encoding="utf-8")
    return path
