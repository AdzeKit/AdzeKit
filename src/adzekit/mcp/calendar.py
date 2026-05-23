"""Calendar MCP server: exposes Google Calendar capabilities as MCP tools.

Same architecture as `mcp/shed.py` and `mcp/gmail.py`. Read-only by design
— calendar mutations (create/update/delete events) are intentionally NOT
exposed, per the calendar-brief skill's safety rule. If you need to add
events, do it in Calendar's UI; the assistant only reads.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from typing import Any

from adzekit.config import Settings, get_settings
from adzekit.modules.adapters_calendar import (
    format_today_briefing,
    list_calendars,
    list_today_events,
)
from adzekit.modules.google_auth import GoogleAuthError, get_access_token


# --- Pure tool functions ---------------------------------------------------


def tool_list_calendars(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    try:
        token = get_access_token()
        calendars = list_calendars(token)
    except GoogleAuthError as exc:
        return json.dumps({"error": str(exc)})
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        return json.dumps({"error": f"Calendar API error: {exc}"})
    return json.dumps(calendars, indent=2)


def tool_today_events(
    calendar_id: str = "primary",
    settings: Settings | None = None,
) -> str:
    """Return today's events on `calendar_id` as JSON."""
    settings = settings or get_settings()
    try:
        events = list_today_events(calendar_id=calendar_id)
    except GoogleAuthError as exc:
        return json.dumps({"error": str(exc)})
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        return json.dumps({"error": f"Calendar API error: {exc}"})
    return json.dumps(events, indent=2)


def tool_today_brief(
    calendar_id: str = "primary",
    settings: Settings | None = None,
) -> str:
    """Return today's events as a compact human-readable string."""
    settings = settings or get_settings()
    return format_today_briefing(calendar_id=calendar_id)


def tool_list_events(
    calendar_id: str = "primary",
    *,
    target_date: str | None = None,
    settings: Settings | None = None,
) -> str:
    """List events on `calendar_id` for a specific date (YYYY-MM-DD; default today)."""
    settings = settings or get_settings()
    try:
        d = date.fromisoformat(target_date) if target_date else date.today()
    except ValueError as exc:
        return json.dumps({"error": f"invalid target_date: {exc}"})
    try:
        events = list_today_events(calendar_id=calendar_id, target_date=d)
    except GoogleAuthError as exc:
        return json.dumps({"error": str(exc)})
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        return json.dumps({"error": f"Calendar API error: {exc}"})
    return json.dumps(events, indent=2)


# --- MCP wiring ------------------------------------------------------------


_TOOL_DESCRIPTORS: list[dict[str, Any]] = [
    {
        "name": "calendar_list_calendars",
        "description": "List the user's Google Calendars (primary + secondary).",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "calendar_today_events",
        "description": (
            "Return today's events on the named calendar as a JSON array "
            "of {summary, start, end, attendees, location, status}."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "calendar_id": {"type": "string", "default": "primary"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "calendar_today_brief",
        "description": (
            "Return today's events as a compact human-readable briefing "
            "string (the same format as `adzekit calendar today`)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "calendar_id": {"type": "string", "default": "primary"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "calendar_list_events",
        "description": (
            "List events on a specific date (YYYY-MM-DD; default today). "
            "Useful for `what's on my plate Thursday` kinds of questions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "calendar_id": {"type": "string", "default": "primary"},
                "target_date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "additionalProperties": False,
        },
    },
]


async def _dispatch(name: str, arguments: dict[str, Any]) -> str:
    try:
        if name == "calendar_list_calendars":
            return tool_list_calendars()
        if name == "calendar_today_events":
            return tool_today_events(
                calendar_id=arguments.get("calendar_id", "primary"),
            )
        if name == "calendar_today_brief":
            return tool_today_brief(
                calendar_id=arguments.get("calendar_id", "primary"),
            )
        if name == "calendar_list_events":
            return tool_list_events(
                calendar_id=arguments.get("calendar_id", "primary"),
                target_date=arguments.get("target_date"),
            )
        return json.dumps({"error": f"unknown tool: {name}"})
    except KeyError as exc:
        return json.dumps({"error": f"missing required argument: {exc}"})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"})


async def _run_server() -> None:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool

    app = Server("adzekit-calendar")

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
    import asyncio
    asyncio.run(_run_server())


if __name__ == "__main__":
    main()
