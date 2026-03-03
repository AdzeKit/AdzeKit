"""Backbone MCP server for AdzeKit.

Exposes the AdzeKit backbone (shed) as a set of MCP tools that any MCP-compatible
client (Claude Code, Cursor, Claude Desktop, etc.) can call over stdio.

Access zones (enforced):
  READ:  daily/, loops/, projects/, knowledge/, reviews/, inbox.md
  WRITE: drafts/ only (backbone is human-owned, never agent-written)

The shed path is read from ADZEKIT_SHED environment variable (or defaults to ~/adzekit).

Usage:
    adzekit-mcp-backbone
    uv run python -m adzekit.mcp.backbone_server
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from fastmcp import FastMCP

from adzekit.config import get_settings

mcp = FastMCP("AdzeKit Backbone")

EMAIL_PATTERNS_FILENAME = "email-patterns.md"


def _drafts_dir() -> Path:
    settings = get_settings()
    d = settings.drafts_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_draft_path(filename: str) -> Path:
    """Return a resolved path inside drafts/, raising ValueError if it escapes."""
    drafts = _drafts_dir()
    safe_name = "".join(c if c.isalnum() or c in "-_." else "-" for c in filename)
    if not safe_name.endswith(".md"):
        safe_name += ".md"
    resolved = (drafts / safe_name).resolve()
    if not str(resolved).startswith(str(drafts.resolve())):
        raise ValueError(f"Filename {filename!r} would escape the drafts/ directory.")
    return resolved


# ---------------------------------------------------------------------------
# READ-ONLY backbone tools
# ---------------------------------------------------------------------------


@mcp.tool
def backbone_get_projects() -> str:
    """List active and backlog projects with their slugs and progress.

    Returns a JSON object with project slugs, titles, states, and task counts.
    Use slug names as customer context hints when classifying emails.
    """
    from adzekit.preprocessor import load_projects

    settings = get_settings()
    projects = load_projects(settings=settings)
    result = [
        {
            "slug": p.slug,
            "title": p.title,
            "state": p.state.value,
            "progress": round(p.progress, 2),
            "total_tasks": len(p.tasks),
            "done_tasks": sum(1 for t in p.tasks if t.done),
        }
        for p in projects
    ]
    return json.dumps({"count": len(result), "projects": result})


@mcp.tool
def backbone_get_open_loops() -> str:
    """Get all open loops (commitments) from the shed.

    Returns a JSON object with loop titles, dates, sizes, and who they involve.
    Use this for active customer context when classifying emails.
    """
    from adzekit.preprocessor import load_open_loops

    settings = get_settings()
    loops = load_open_loops(settings)
    if not loops:
        return json.dumps({"count": 0, "loops": []})
    result = [
        {
            "title": loop.title,
            "date": loop.date.isoformat(),
            "size": loop.size,
            "due": loop.due.isoformat() if loop.due else None,
            "status": loop.status,
            "who": loop.who,
        }
        for loop in loops
    ]
    return json.dumps({"count": len(result), "loops": result})


@mcp.tool
def backbone_get_today() -> str:
    """Get today's daily note content.

    Returns intentions, log entries, and reflection sections for today's date.
    """
    from adzekit.preprocessor import load_daily_note

    settings = get_settings()
    note = load_daily_note(settings=settings)
    if note is None:
        return json.dumps({"exists": False, "date": date.today().isoformat()})
    return json.dumps({
        "exists": True,
        "date": note.date.isoformat(),
        "intentions": [{"desc": t.description, "done": t.done} for t in note.intentions],
        "log_entries": [{"time": e.time, "text": e.text} for e in note.log],
        "finished": note.finished,
        "blocked": note.blocked,
        "tomorrow": note.tomorrow,
    })


@mcp.tool
def backbone_get_week_notes(iso_week: str | None = None) -> str:
    """Get all daily notes and the review stub for a specific ISO week.

    Args:
        iso_week: ISO week string like '2026-W09'. Defaults to the current week.
                  Week runs Monday–Sunday.
    """
    from adzekit.preprocessor import load_daily_note

    if iso_week is None:
        today = date.today()
        iso_week = f"{today.isocalendar()[0]}-W{today.isocalendar()[1]:02d}"

    # Parse year and week number
    try:
        year_str, week_str = iso_week.split("-W")
        year, week_num = int(year_str), int(week_str)
    except ValueError:
        return json.dumps({"error": f"Invalid iso_week format: {iso_week!r}. Use 'YYYY-WNN'."})

    # Compute Monday of the given ISO week.
    # fromisocalendar() raises ValueError for out-of-range week numbers.
    try:
        monday = date.fromisocalendar(year, week_num, 1)
    except ValueError:
        return json.dumps({"error": f"Invalid ISO week value: {iso_week!r}. Use a valid calendar week."})

    week_dates = [monday + timedelta(days=i) for i in range(7)]

    settings = get_settings()
    days = []
    for d in week_dates:
        note = load_daily_note(target_date=d, settings=settings)
        if note is None:
            days.append({"date": d.isoformat(), "exists": False})
        else:
            days.append({
                "date": d.isoformat(),
                "exists": True,
                "intentions": [
                    {"desc": t.description, "done": t.done} for t in note.intentions
                ],
                "log": [{"time": e.time, "text": e.text} for e in note.log],
                "raw_log": "\n".join(e.text for e in note.log) if note.log else "",
                "finished": note.finished,
                "blocked": note.blocked,
                "tomorrow": note.tomorrow,
                "raw_content": note.raw_content,
            })

    # Read the existing review stub for this week (reviews/YYYY-WNN.md)
    review_stub_path = settings.shed / "reviews" / f"{iso_week}.md"
    review_stub = review_stub_path.read_text(encoding="utf-8") if review_stub_path.exists() else None

    return json.dumps({
        "iso_week": iso_week,
        "monday": monday.isoformat(),
        "sunday": week_dates[-1].isoformat(),
        "days": days,
        "review_stub": review_stub,
    })


@mcp.tool
def backbone_get_today_context() -> str:
    """One-shot context load for starting any agent session.

    Returns today's daily note, loops due within 24 hours, overdue loops,
    and a compact active-project summary — all in a single call.

    Use this at the start of every skill instead of calling backbone_get_today(),
    backbone_get_open_loops(), and backbone_get_projects() separately.
    """
    from adzekit.preprocessor import load_daily_note, load_open_loops, load_projects
    from adzekit.models import ProjectState

    settings = get_settings()
    today = date.today()

    # Today's note
    note = load_daily_note(settings=settings)
    today_note = None
    if note is not None:
        today_note = {
            "exists": True,
            "date": note.date.isoformat(),
            "intentions": [{"desc": t.description, "done": t.done} for t in note.intentions],
            "log_entries": [{"time": e.time, "text": e.text} for e in note.log],
            "finished": note.finished,
            "blocked": note.blocked,
            "tomorrow": note.tomorrow,
        }
    else:
        today_note = {"exists": False, "date": today.isoformat()}

    # Loops: split into overdue, due-today, and upcoming
    loops = load_open_loops(settings)
    overdue, due_today, upcoming = [], [], []
    for loop in loops:
        if loop.due is None:
            upcoming.append(loop)
            continue
        delta = (loop.due - today).days
        if delta < 0:
            overdue.append(loop)
        elif delta == 0:
            due_today.append(loop)
        else:
            upcoming.append(loop)

    def _loop_dict(loop):
        return {
            "title": loop.title,
            "size": loop.size,
            "date": loop.date.isoformat(),
            "due": loop.due.isoformat() if loop.due else None,
            "who": loop.who,
        }

    # Active projects summary
    projects = load_projects(state=ProjectState.ACTIVE, settings=settings)
    project_summary = [
        {
            "slug": p.slug,
            "title": p.title,
            "progress": round(p.progress, 2),
            "done_tasks": sum(1 for t in p.tasks if t.done),
            "total_tasks": len(p.tasks),
        }
        for p in projects
    ]

    return json.dumps({
        "date": today.isoformat(),
        "today_note": today_note,
        "loops": {
            "overdue": [_loop_dict(l) for l in overdue],
            "due_today": [_loop_dict(l) for l in due_today],
            "upcoming_count": len(upcoming),
            "total_open": len(loops),
        },
        "active_projects": project_summary,
    })


@mcp.tool
def backbone_search(query: str, directories: list[str] | None = None) -> str:
    """Full-text search across backbone files.

    Searches for the query string (case-insensitive) in all readable backbone
    directories and returns matching files with the relevant lines as context.

    Args:
        query: Search string (case-insensitive, plain text — not regex).
        directories: List of subdirectories to search. Defaults to all readable
                     backbone dirs: ['daily', 'projects', 'loops', 'knowledge', 'reviews'].
                     Valid values: 'daily', 'projects', 'loops', 'knowledge', 'reviews'.
    """
    settings = get_settings()
    allowed = {
        "daily": settings.daily_dir,
        "projects": settings.projects_dir,
        "loops": settings.loops_dir,
        "knowledge": settings.knowledge_dir,
        "reviews": settings.reviews_dir,
    }

    search_dirs = directories or list(allowed.keys())
    invalid = [d for d in search_dirs if d not in allowed]
    if invalid:
        return json.dumps({"error": f"Invalid directories: {invalid}. Allowed: {list(allowed.keys())}"})

    query_lower = query.lower()
    results = []

    for dir_name in search_dirs:
        root = allowed[dir_name]
        if not root.exists():
            continue
        for md_file in sorted(root.rglob("*.md")):
            try:
                text = md_file.read_text(encoding="utf-8")
            except OSError:
                continue
            matching_lines = [
                {"line_number": i + 1, "text": line.rstrip()}
                for i, line in enumerate(text.splitlines())
                if query_lower in line.lower()
            ]
            if matching_lines:
                results.append({
                    "file": str(md_file.relative_to(settings.shed)),
                    "matches": matching_lines[:10],  # cap at 10 lines per file
                    "total_matches": len(matching_lines),
                })

    return json.dumps({
        "query": query,
        "result_count": len(results),
        "results": results,
    })


@mcp.tool
def backbone_get_inbox() -> str:
    """Read the shed inbox.md (quick capture items).

    Returns the raw text of inbox.md — the lightweight capture bucket.
    """
    settings = get_settings()
    if not settings.inbox_path.exists():
        return json.dumps({"content": ""})
    content = settings.inbox_path.read_text(encoding="utf-8")
    return json.dumps({"content": content})


@mcp.tool
def backbone_list_drafts() -> str:
    """List all files in drafts/ awaiting human review."""
    drafts = _drafts_dir()
    files = sorted(f.name for f in drafts.iterdir() if f.is_file())
    return json.dumps({"count": len(files), "files": files})


# ---------------------------------------------------------------------------
# WRITE tools: drafts/ only
# ---------------------------------------------------------------------------


@mcp.tool
def backbone_write_draft(filename: str, content: str) -> str:
    """Write a markdown file to drafts/ for human review.

    Only writes inside the drafts/ directory. Cannot write to backbone directories
    (loops/, projects/, daily/, knowledge/, reviews/).

    Args:
        filename: Name of the draft file (e.g. 'inbox-zero-2026-02-28.md').
                  Will be sanitized and .md appended if missing.
        content: Markdown content to write.
    """
    path = _safe_draft_path(filename)
    path.write_text(content, encoding="utf-8")
    return json.dumps({
        "status": "written",
        "path": f"drafts/{path.name}",
        "note": "Draft saved. Human must review.",
    })


# ---------------------------------------------------------------------------
# EMAIL MEMORY tools (read/write drafts/email-patterns.md)
# ---------------------------------------------------------------------------


@mcp.tool
def backbone_get_email_patterns() -> str:
    """Read the email patterns memory file (drafts/email-patterns.md).

    Returns the raw markdown content. This file contains known junk senders,
    notification sources, customer domains, and learned classification notes.
    Returns empty content if the file does not exist yet (first run).
    """
    path = _drafts_dir() / EMAIL_PATTERNS_FILENAME
    if not path.exists():
        return json.dumps({"exists": False, "content": ""})
    content = path.read_text(encoding="utf-8")
    return json.dumps({"exists": True, "content": content})


@mcp.tool
def backbone_update_email_patterns(
    new_junk_senders: list[str] | None = None,
    new_notification_sources: list[str] | None = None,
    new_customer_domains: list[str] | None = None,
    notes: list[str] | None = None,
) -> str:
    """Append newly learned patterns to the email patterns memory file.

    Creates drafts/email-patterns.md if it does not exist. Appends new entries
    to the relevant sections. Updates the 'Last updated' timestamp.

    Args:
        new_junk_senders: Email addresses or domains to add under 'Known Junk Senders'.
        new_notification_sources: Senders to add under 'Known Notification Sources'.
        new_customer_domains: Domains with project context under 'Customer Domains'.
        notes: Free-form notes to append (each prefixed with today's date).
    """
    today = date.today().isoformat()
    path = _drafts_dir() / EMAIL_PATTERNS_FILENAME

    if path.exists():
        content = path.read_text(encoding="utf-8")
        # Update last updated line
        lines = content.splitlines()
        updated_lines = []
        for line in lines:
            if line.startswith("Last updated:"):
                updated_lines.append(f"Last updated: {today}")
            else:
                updated_lines.append(line)
        content = "\n".join(updated_lines)
    else:
        content = f"""# Email Patterns Memory
Last updated: {today}

## Known Junk Senders

## Known Notification Sources

## Customer Domains

## Notes
"""

    def _append_to_section(text: str, section_header: str, items: list[str]) -> str:
        """Insert items after a section header."""
        if not items:
            return text
        lines = text.splitlines()
        result = []
        in_section = False
        inserted = False
        for i, line in enumerate(lines):
            if line.strip() == section_header:
                in_section = True
                result.append(line)
                continue
            if in_section and not inserted:
                # Insert items before the next section or end
                if line.startswith("## ") or i == len(lines) - 1:
                    for item in items:
                        result.append(f"- {item}")
                    in_section = False
                    inserted = True
                elif line.strip():
                    result.append(line)
                    continue
                elif not line.strip():
                    result.append(line)
                    continue
            result.append(line)
        # If section was last in file and items weren't inserted yet
        if in_section and not inserted:
            for item in items:
                result.append(f"- {item}")
        return "\n".join(result)

    content = _append_to_section(content, "## Known Junk Senders", new_junk_senders or [])
    content = _append_to_section(
        content, "## Known Notification Sources", new_notification_sources or []
    )
    content = _append_to_section(content, "## Customer Domains", new_customer_domains or [])

    # Append notes with date prefix
    if notes:
        dated_notes = [f"[{today}] {note}" for note in notes]
        content = _append_to_section(content, "## Notes", dated_notes)

    path.write_text(content, encoding="utf-8")

    added = sum([
        len(new_junk_senders or []),
        len(new_notification_sources or []),
        len(new_customer_domains or []),
        len(notes or []),
    ])
    return json.dumps({
        "status": "updated",
        "path": f"drafts/{EMAIL_PATTERNS_FILENAME}",
        "entries_added": added,
    })


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
