"""Shed tools for the AdzeKit agent.

The agent can READ the backbone (daily, loops, projects, knowledge, reviews,
inbox) but CANNOT WRITE to it. The backbone is the human's domain.

The agent CAN WRITE to two areas:
  - stock/   Raw materials, transcripts, downloads.
  - drafts/  Agent-generated proposals awaiting human approval.

When the agent wants to suggest a loop, inbox item, or any backbone change,
it writes a proposal to drafts/ for the human to review and apply.
"""

import json
from datetime import date
from pathlib import Path

from adzekit.agent.tools import registry
from adzekit.config import Settings, get_settings
from adzekit.models import Loop
from adzekit.parser import format_loop
from adzekit.preprocessor import load_daily_note, load_open_loops, load_projects


def _settings() -> Settings:
    return get_settings()


# ---------------------------------------------------------------------------
# READ-ONLY backbone tools
# ---------------------------------------------------------------------------


@registry.register(
    name="shed_get_open_loops",
    description="Get all open loops (commitments) from the shed. Read-only.",
)
def shed_get_open_loops() -> str:
    loops = load_open_loops(_settings())
    if not loops:
        return json.dumps({"count": 0, "loops": []})
    result = []
    for loop in loops:
        result.append({
            "title": loop.title,
            "date": loop.date.isoformat(),
            "size": loop.size,
            "due": loop.due.isoformat() if loop.due else None,
            "status": loop.status,
            "who": loop.who,
        })
    return json.dumps({"count": len(result), "loops": result})


@registry.register(
    name="shed_get_today",
    description="Get today's daily note content. Read-only.",
)
def shed_get_today() -> str:
    note = load_daily_note(settings=_settings())
    if note is None:
        return json.dumps({"exists": False})
    return json.dumps({
        "exists": True,
        "date": note.date.isoformat(),
        "intentions": [{"desc": t.description, "done": t.done} for t in note.intentions],
        "log_entries": [{"time": e.time, "text": e.text} for e in note.log],
        "finished": note.finished,
        "blocked": note.blocked,
        "tomorrow": note.tomorrow,
    })


@registry.register(
    name="shed_get_inbox",
    description="Read the shed inbox (quick capture items). Read-only.",
)
def shed_get_inbox() -> str:
    settings = _settings()
    if not settings.inbox_path.exists():
        return json.dumps({"content": ""})
    content = settings.inbox_path.read_text(encoding="utf-8")
    return json.dumps({"content": content})


@registry.register(
    name="shed_get_projects",
    description="List active and backlog projects with their progress. Read-only.",
)
def shed_get_projects() -> str:
    projects = load_projects(settings=_settings())
    result = []
    for p in projects:
        result.append({
            "slug": p.slug,
            "title": p.title,
            "state": p.state.value,
            "progress": round(p.progress, 2),
            "total_tasks": len(p.tasks),
            "done_tasks": sum(1 for t in p.tasks if t.done),
        })
    return json.dumps({"count": len(result), "projects": result})


# ---------------------------------------------------------------------------
# WRITABLE tools: drafts/ (proposals for human review)
# ---------------------------------------------------------------------------


@registry.register(
    name="shed_propose_loop",
    description=(
        "Propose a new loop to add to the shed. Writes a proposal to drafts/ "
        "for the human to review and approve. Does NOT modify open.md."
    ),
    param_descriptions={
        "title": "Short description of the commitment.",
        "who": "Person this commitment is with (optional).",
        "size": "T-shirt size: XS, S, M, L, XL (optional).",
        "due_date": "Due date in YYYY-MM-DD format (optional).",
        "reason": "Why this loop should be added (context for the human).",
    },
)
def shed_propose_loop(
    title: str,
    who: str = "",
    size: str = "",
    due_date: str = "",
    reason: str = "",
) -> str:
    settings = _settings()
    due = date.fromisoformat(due_date) if due_date else None
    loop = Loop(
        date=date.today(),
        title=title,
        who=who,
        what="",
        due=due,
        status="Open",
        size=size,
    )
    formatted = format_loop(loop)

    # Write proposal to drafts/
    drafts = settings.drafts_dir
    drafts.mkdir(parents=True, exist_ok=True)
    proposal_path = drafts / f"loop-{date.today().isoformat()}-{_slug(title)}.md"

    content = f"""# Proposed Loop

{formatted}

## Reason
{reason or 'Agent-suggested loop.'}

## To apply
Copy the line above into `loops/open.md`.
"""
    proposal_path.write_text(content, encoding="utf-8")

    return json.dumps({
        "action": "propose_add_loop",
        "formatted": formatted,
        "proposal_file": str(proposal_path.name),
        "note": "Proposal saved to drafts/. Human must review and apply.",
    })


@registry.register(
    name="shed_propose_inbox_item",
    description=(
        "Propose an item to add to the shed inbox. Writes a proposal to drafts/ "
        "for the human to review. Does NOT modify inbox.md."
    ),
    param_descriptions={
        "text": "The text to propose adding to the inbox.",
    },
)
def shed_propose_inbox_item(text: str) -> str:
    settings = _settings()
    entry = f"- [{date.today().isoformat()}] {text}"

    drafts = settings.drafts_dir
    drafts.mkdir(parents=True, exist_ok=True)
    proposal_path = drafts / f"inbox-{date.today().isoformat()}-{_slug(text[:40])}.md"

    content = f"""# Proposed Inbox Item

{entry}

## To apply
Copy the line above into `inbox.md`.
"""
    proposal_path.write_text(content, encoding="utf-8")

    return json.dumps({
        "action": "propose_inbox_item",
        "formatted": entry,
        "proposal_file": str(proposal_path.name),
        "note": "Proposal saved to drafts/. Human must review and apply.",
    })


@registry.register(
    name="shed_save_summary",
    description=(
        "Save an agent-generated summary or analysis to drafts/. Use this "
        "to persist triage results, email summaries, or status reports."
    ),
    param_descriptions={
        "filename": "Name for the file (e.g. 'email-triage-2026-02-26.md').",
        "content": "The markdown content to save.",
    },
)
def shed_save_summary(filename: str, content: str) -> str:
    settings = _settings()
    drafts = settings.drafts_dir
    drafts.mkdir(parents=True, exist_ok=True)

    # Sanitize filename
    safe_name = "".join(c if c.isalnum() or c in "-_." else "-" for c in filename)
    if not safe_name.endswith(".md"):
        safe_name += ".md"

    path = drafts / safe_name
    path.write_text(content, encoding="utf-8")

    return json.dumps({
        "status": "saved",
        "path": f"drafts/{safe_name}",
        "note": "Summary saved to drafts/ for review.",
    })


# ---------------------------------------------------------------------------
# WRITABLE tools: stock/ (raw materials)
# ---------------------------------------------------------------------------


@registry.register(
    name="shed_save_to_stock",
    description=(
        "Save raw material (transcripts, notes, exports) to stock/<project>/. "
        "Stock is for unprocessed input that supports a project."
    ),
    param_descriptions={
        "project_slug": "Project slug for the subdirectory.",
        "filename": "File name (e.g. 'meeting-notes-2026-02-26.md').",
        "content": "The content to save.",
    },
)
def shed_save_to_stock(project_slug: str, filename: str, content: str) -> str:
    settings = _settings()
    stock_project = settings.stock_dir / project_slug
    stock_project.mkdir(parents=True, exist_ok=True)

    safe_name = "".join(c if c.isalnum() or c in "-_." else "-" for c in filename)
    path = stock_project / safe_name
    path.write_text(content, encoding="utf-8")

    return json.dumps({
        "status": "saved",
        "path": f"stock/{project_slug}/{safe_name}",
    })


@registry.register(
    name="shed_list_drafts",
    description="List all files in drafts/ awaiting human review.",
)
def shed_list_drafts() -> str:
    settings = _settings()
    drafts = settings.drafts_dir
    if not drafts.exists():
        return json.dumps({"count": 0, "files": []})
    files = sorted(f.name for f in drafts.iterdir() if f.is_file())
    return json.dumps({"count": len(files), "files": files})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slug(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    return "".join(c if c.isalnum() or c == "-" else "-" for c in text.lower().strip())[:50].strip("-")
