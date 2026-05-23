"""Shed MCP server: stdio server exposing the AdzeKit shed.

The tool surface (all read-only except `shed_propose_draft`):

  shed_get_loops         → JSON list of open loops (active.md / open.md)
  shed_get_today         → today's daily note as markdown
  shed_get_projects      → JSON list of projects (state=active|backlog|archive)
  shed_get_knowledge     → a knowledge note body, by slug
  shed_list_inbox        → JSON list of pending draft proposals
  shed_show_draft        → body + provenance for INBOX entry #index
  shed_propose_draft     → write a new draft to drafts/  (NEVER backbone)

Design invariants:

1. **Two layers.** The pure tool functions (`tool_*`) take a Settings instance
   and return strings; they're the entire business logic. The MCP server
   (`_run_server`) is thin glue that maps tool names to those functions. Tests
   call the pure functions directly without spinning a transport.

2. **Write surface is one tool.** Only `shed_propose_draft` mutates. It uses
   `preprocessor.write_draft_with_frontmatter`, which always writes inside
   `drafts/` — the AdzeKit "AI proposes, human decides" invariant survives
   even when the MCP client has unrestricted access.

3. **Errors are JSON, not exceptions.** Tool functions catch and return
   structured error payloads. The MCP transport layer never raises out of a
   tool call (the spec discourages it).

The server is launched via the `adzekit-mcp-shed` console script (see
pyproject.toml). To wire it into Claude Code, run `adzekit mcp install`.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from adzekit.config import Settings, get_settings


# --- Pure tool functions (testable in isolation) ---------------------------


def tool_get_loops(settings: Settings | None = None) -> str:
    """List open loops. Returns JSON array of {title, size, start_date, due, status}."""
    from adzekit.preprocessor import load_active_loops
    settings = settings or get_settings()
    loops = load_active_loops(settings)
    return json.dumps(
        [
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
            for loop in loops
        ],
        indent=2,
    )


def tool_get_today(settings: Settings | None = None) -> str:
    """Return today's daily note as markdown, or a stub message if none exists."""
    from adzekit.preprocessor import load_daily_note
    settings = settings or get_settings()
    note = load_daily_note(settings=settings)
    if note is None:
        return (
            f"No daily note exists for {date.today().isoformat()}. "
            "Run `/daily-start` (or `adzekit daily-start`) to create one."
        )
    return note.raw_content


def tool_get_projects(state: str = "active", settings: Settings | None = None) -> str:
    """List projects. Returns JSON array of {slug, title, state}."""
    from adzekit.models import ProjectState
    from adzekit.preprocessor import load_projects
    settings = settings or get_settings()
    try:
        project_state = ProjectState(state)
    except ValueError:
        return json.dumps({
            "error": f"unknown project state '{state}'; valid: active, backlog, archive",
        })
    projects = load_projects(state=project_state, settings=settings)
    return json.dumps(
        [
            {"slug": p.slug, "title": p.title, "state": p.state.value}
            for p in projects
        ],
        indent=2,
    )


def tool_get_knowledge(slug: str, settings: Settings | None = None) -> str:
    """Return a knowledge note's body by slug, or a not-found message."""
    settings = settings or get_settings()
    path = settings.knowledge_dir / f"{slug}.md"
    if not path.exists():
        return f"No knowledge note: {slug}"
    return path.read_text(encoding="utf-8")


def tool_list_inbox(settings: Settings | None = None) -> str:
    """List pending draft proposals. Returns JSON array of entry summaries."""
    from adzekit.modules.drafts import InboxConflictError, parse_inbox
    settings = settings or get_settings()
    try:
        entries = parse_inbox(settings)
    except InboxConflictError as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps(
        [
            {
                "index": e.index,
                "date": e.date,
                "time": e.time,
                "skill": e.skill,
                "summary": e.summary,
                "path": e.path,
            }
            for e in entries
        ],
        indent=2,
    )


def tool_show_draft(index: int, settings: Settings | None = None) -> str:
    """Return draft #index's body + provenance as JSON."""
    from adzekit.modules.drafts import InboxEntryNotFoundError, show_draft
    settings = settings or get_settings()
    try:
        result = show_draft(index, settings=settings)
    except (InboxEntryNotFoundError, FileNotFoundError) as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps(result, indent=2, default=str)


def tool_propose_draft(
    skill: str,
    body: str,
    summary: str = "",
    confidence: float | None = None,
    settings: Settings | None = None,
) -> str:
    """Write a draft proposal. ALWAYS targets drafts/, NEVER backbone.

    Returns JSON with the written path (relative to shed root). The human
    reviews via `adzekit drafts list` / `adzekit drafts show N` and promotes
    with `adzekit drafts accept N`.
    """
    from adzekit.preprocessor import write_draft_with_frontmatter
    settings = settings or get_settings()
    path = write_draft_with_frontmatter(
        skill,
        body,
        settings=settings,
        summary=summary,
        confidence=confidence,
        trigger="mcp",
    )
    try:
        rel = str(path.resolve().relative_to(settings.shed.resolve()))
    except ValueError:
        rel = str(path)
    # Defensive: assert the write landed inside drafts/.
    if "drafts/" not in rel and not rel.startswith("drafts"):
        return json.dumps({
            "error": (
                f"BUG: propose_draft wrote outside drafts/: {rel}. "
                "This violates the AdzeKit invariant; please file an issue."
            ),
            "path": rel,
        })
    return json.dumps({"path": rel, "skill": skill, "summary": summary}, indent=2)


# --- MCP server wiring -----------------------------------------------------


_TOOL_DESCRIPTORS: list[dict[str, Any]] = [
    {
        "name": "shed_get_loops",
        "description": "Read all open commitments (loops) from the shed.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "shed_get_today",
        "description": "Read today's daily note as markdown.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "shed_get_projects",
        "description": "List projects. Pass `state` = active | backlog | archive (default: active).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "state": {"type": "string", "enum": ["active", "backlog", "archive"]},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "shed_get_knowledge",
        "description": "Read a knowledge note by slug (e.g. 'vector-search').",
        "inputSchema": {
            "type": "object",
            "properties": {"slug": {"type": "string"}},
            "required": ["slug"],
            "additionalProperties": False,
        },
    },
    {
        "name": "shed_list_inbox",
        "description": "List pending draft proposals in drafts/INBOX (one entry per pending draft).",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "shed_show_draft",
        "description": "Show body + provenance for INBOX entry #index. Use the index from shed_list_inbox.",
        "inputSchema": {
            "type": "object",
            "properties": {"index": {"type": "integer", "minimum": 1}},
            "required": ["index"],
            "additionalProperties": False,
        },
    },
    {
        "name": "shed_propose_draft",
        "description": (
            "Write a draft proposal to drafts/. NEVER writes to backbone — "
            "the human reviews via `adzekit drafts list` and promotes with "
            "`adzekit drafts accept N`."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "skill": {"type": "string", "description": "Skill name; will appear in INBOX and provenance."},
                "body": {"type": "string", "description": "Full markdown body of the draft."},
                "summary": {"type": "string", "description": "Short one-line summary (shown in INBOX)."},
                "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            },
            "required": ["skill", "body"],
            "additionalProperties": False,
        },
    },
]


async def _dispatch(name: str, arguments: dict[str, Any]) -> str:
    """Route a tool call to the right pure function. Returns the tool's text result."""
    try:
        if name == "shed_get_loops":
            return tool_get_loops()
        if name == "shed_get_today":
            return tool_get_today()
        if name == "shed_get_projects":
            return tool_get_projects(state=arguments.get("state", "active"))
        if name == "shed_get_knowledge":
            return tool_get_knowledge(slug=arguments["slug"])
        if name == "shed_list_inbox":
            return tool_list_inbox()
        if name == "shed_show_draft":
            return tool_show_draft(index=int(arguments["index"]))
        if name == "shed_propose_draft":
            return tool_propose_draft(
                skill=arguments["skill"],
                body=arguments["body"],
                summary=arguments.get("summary", ""),
                confidence=arguments.get("confidence"),
            )
        return json.dumps({"error": f"unknown tool: {name}"})
    except KeyError as exc:
        return json.dumps({"error": f"missing required argument: {exc}"})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"})


async def _run_server() -> None:
    """Run the stdio MCP server. Imports `mcp` lazily so module-level import
    works even in environments without the MCP SDK (tests don't need it)."""
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool

    app = Server("adzekit-shed")

    @app.list_tools()
    async def list_tools() -> list[Tool]:
        return [Tool(**d) for d in _TOOL_DESCRIPTORS]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        text = await _dispatch(name, arguments or {})
        return [TextContent(type="text", text=text)]

    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


def main() -> None:
    """Console-script entry point: run the stdio MCP server until the client closes."""
    import asyncio
    asyncio.run(_run_server())


if __name__ == "__main__":
    main()
