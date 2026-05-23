"""Gmail MCP server: exposes Gmail capabilities as MCP tools.

Same architecture as `mcp/shed.py`: pure tool functions + a thin server
shell. Tools delegate to gmail-side helpers in `modules/adapters_gmail`
(label-list cache, list_labels) and to the shared `google_auth` for tokens.

Tool surface:
  gmail_list_labels        — read; returns cached or live label list
  gmail_list_unread        — read; metadata of unread messages
  gmail_get_message        — read; full payload of one message
  gmail_archive            — write (mail-side); removes INBOX label
  gmail_label_add          — write (mail-side); applies a label by name
  gmail_draft_reply        — write (mail-side); creates a Gmail draft

"Write" here means Gmail-side mutation (archive, label, draft). All such
mutations are scoped to the user's inbox via OAuth and never touch the
shed — backbone invariants are preserved.

The MCP server runs as a subprocess launched by Claude Code (or any other
MCP-speaking client). ADZEKIT_SHED is expected to be set by the launcher
so the cached label map is locatable.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from email.mime.text import MIMEText
from typing import Any

from adzekit.config import Settings, get_settings
from adzekit.modules.adapters_gmail import (
    GMAIL_API_BASE,
    _gmail_get,
    list_labels,
)
from adzekit.modules.google_auth import GoogleAuthError, get_access_token


# --- Helpers ---------------------------------------------------------------


def _gmail_post(path: str, token: str, body: dict[str, Any]) -> dict[str, Any]:
    """Authenticated POST against the Gmail REST API."""
    req = urllib.request.Request(
        f"{GMAIL_API_BASE}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _load_cached_labels(settings: Settings) -> dict[str, str]:
    """Read the gmail-labels.json cache. Returns {label_name: label_id}."""
    cache_path = settings.drafts_dir / ".adapters" / "gmail-labels.json"
    if not cache_path.exists():
        return {}
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data.get("labels", {})


def _resolve_label_id(
    label_name: str,
    token: str,
    settings: Settings,
) -> str | None:
    """Best-effort label-name → label-id lookup.

    Checks the local cache first; falls back to a live API list if absent.
    Returns None if the label doesn't exist.
    """
    cached = _load_cached_labels(settings)
    if label_name in cached:
        return cached[label_name]
    # Live lookup.
    for label in list_labels(token):
        if label["name"] == label_name:
            return label["id"]
    return None


# --- Pure tool functions ---------------------------------------------------


def tool_list_labels(settings: Settings | None = None) -> str:
    """List the user's Gmail labels."""
    settings = settings or get_settings()
    try:
        token = get_access_token()
        labels = list_labels(token)
    except (GoogleAuthError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps(labels, indent=2)


def tool_list_unread(
    *,
    max_results: int = 25,
    query: str = "is:unread",
    settings: Settings | None = None,
) -> str:
    """List metadata for unread messages.

    `query` is a Gmail search expression (default `is:unread`). `max_results`
    caps the response. Each entry has id, threadId, snippet, From, Subject,
    Date.
    """
    settings = settings or get_settings()
    try:
        token = get_access_token()
        params = urllib.parse.urlencode({
            "q": query,
            "maxResults": str(max_results),
        })
        ids_payload = _gmail_get(f"/messages?{params}", token)
    except GoogleAuthError as exc:
        return json.dumps({"error": str(exc)})
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        return json.dumps({"error": f"Gmail API error: {exc}"})

    out: list[dict[str, Any]] = []
    for stub in ids_payload.get("messages", [])[:max_results]:
        try:
            meta = _gmail_get(
                f"/messages/{stub['id']}?format=metadata"
                "&metadataHeaders=From"
                "&metadataHeaders=Subject"
                "&metadataHeaders=Date",
                token,
            )
        except (urllib.error.URLError, urllib.error.HTTPError):
            continue
        headers = {
            h["name"]: h["value"]
            for h in meta.get("payload", {}).get("headers", [])
        }
        out.append({
            "id": stub["id"],
            "threadId": stub.get("threadId", ""),
            "snippet": meta.get("snippet", ""),
            "from": headers.get("From", ""),
            "subject": headers.get("Subject", ""),
            "date": headers.get("Date", ""),
        })
    return json.dumps(out, indent=2)


def tool_get_message(message_id: str, settings: Settings | None = None) -> str:
    """Return the full body + headers of a single message."""
    settings = settings or get_settings()
    try:
        token = get_access_token()
        payload = _gmail_get(f"/messages/{message_id}?format=full", token)
    except GoogleAuthError as exc:
        return json.dumps({"error": str(exc)})
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        return json.dumps({"error": f"Gmail API error: {exc}"})

    headers = {
        h["name"]: h["value"]
        for h in payload.get("payload", {}).get("headers", [])
    }
    body = _extract_body(payload.get("payload", {}))
    return json.dumps(
        {
            "id": payload.get("id"),
            "threadId": payload.get("threadId"),
            "from": headers.get("From", ""),
            "to": headers.get("To", ""),
            "cc": headers.get("Cc", ""),
            "subject": headers.get("Subject", ""),
            "date": headers.get("Date", ""),
            "body": body,
            "labelIds": payload.get("labelIds", []),
        },
        indent=2,
    )


def _extract_body(payload: dict[str, Any]) -> str:
    """Walk a Gmail payload, prefer text/plain, fall back to text/html."""
    if not payload:
        return ""
    mime = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")
    if mime == "text/plain" and body_data:
        return _decode_b64(body_data)
    parts = payload.get("parts", [])
    if parts:
        # Prefer the first text/plain part.
        for part in parts:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data")
                if data:
                    return _decode_b64(data)
        # Fall back to first text/html.
        for part in parts:
            if part.get("mimeType") == "text/html":
                data = part.get("body", {}).get("data")
                if data:
                    return _decode_b64(data)
        # Recurse into nested multipart.
        for part in parts:
            nested = _extract_body(part)
            if nested:
                return nested
    if body_data:
        return _decode_b64(body_data)
    return ""


def _decode_b64(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(data.encode("ascii")).decode(
            "utf-8", errors="replace",
        )
    except Exception:
        return ""


def tool_archive(message_id: str, settings: Settings | None = None) -> str:
    """Remove the INBOX label from a message (Gmail's "archive")."""
    settings = settings or get_settings()
    try:
        token = get_access_token()
        _gmail_post(
            f"/messages/{message_id}/modify",
            token,
            {"removeLabelIds": ["INBOX"]},
        )
    except GoogleAuthError as exc:
        return json.dumps({"error": str(exc)})
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        return json.dumps({"error": f"Gmail API error: {exc}"})
    return json.dumps({"id": message_id, "archived": True})


def tool_label_add(
    message_id: str,
    label_name: str,
    settings: Settings | None = None,
) -> str:
    """Apply a label by name (resolved via cache or live lookup)."""
    settings = settings or get_settings()
    try:
        token = get_access_token()
        label_id = _resolve_label_id(label_name, token, settings)
        if label_id is None:
            return json.dumps({
                "error": f"unknown label: {label_name!r}; "
                         "create it in Gmail's UI or re-run "
                         "`adzekit adapter install gmail` to refresh the cache."
            })
        _gmail_post(
            f"/messages/{message_id}/modify",
            token,
            {"addLabelIds": [label_id]},
        )
    except GoogleAuthError as exc:
        return json.dumps({"error": str(exc)})
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        return json.dumps({"error": f"Gmail API error: {exc}"})
    return json.dumps({"id": message_id, "label": label_name, "labelId": label_id})


def tool_draft_reply(
    message_id: str,
    body: str,
    *,
    settings: Settings | None = None,
) -> str:
    """Create a Gmail draft in reply to a message.

    The draft is linked to the original thread so it appears nested in
    Gmail's UI. The reply uses the original's Subject (with "Re: " prefix
    if not present) and replies to the original's From/Reply-To.
    """
    settings = settings or get_settings()
    try:
        token = get_access_token()
        original = _gmail_get(
            f"/messages/{message_id}?format=metadata"
            "&metadataHeaders=From&metadataHeaders=Reply-To"
            "&metadataHeaders=Subject&metadataHeaders=Message-ID",
            token,
        )
    except GoogleAuthError as exc:
        return json.dumps({"error": str(exc)})
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        return json.dumps({"error": f"Gmail API error: {exc}"})

    headers = {
        h["name"]: h["value"]
        for h in original.get("payload", {}).get("headers", [])
    }
    to_addr = headers.get("Reply-To") or headers.get("From", "")
    subject = headers.get("Subject", "")
    if subject and not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"
    in_reply_to = headers.get("Message-ID", "")

    msg = MIMEText(body, "plain", "utf-8")
    msg["To"] = to_addr
    msg["Subject"] = subject
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")

    try:
        result = _gmail_post(
            "/drafts",
            token,
            {"message": {"raw": raw, "threadId": original.get("threadId", "")}},
        )
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        return json.dumps({"error": f"Gmail API error: {exc}"})

    return json.dumps({
        "draft_id": result.get("id", ""),
        "to": to_addr,
        "subject": subject,
    })


# --- MCP wiring ------------------------------------------------------------


_TOOL_DESCRIPTORS: list[dict[str, Any]] = [
    {
        "name": "gmail_list_labels",
        "description": "List the user's Gmail labels.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "gmail_list_unread",
        "description": (
            "List metadata for unread messages (id, from, subject, date, snippet). "
            "Pass `query` to use a custom Gmail search; default `is:unread`."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
                "query": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "gmail_get_message",
        "description": "Return the full body + headers of a single message by id.",
        "inputSchema": {
            "type": "object",
            "properties": {"message_id": {"type": "string"}},
            "required": ["message_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "gmail_archive",
        "description": (
            "Remove the INBOX label from a message (Gmail's 'archive'). "
            "Does NOT delete; the message moves out of the inbox but remains searchable."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"message_id": {"type": "string"}},
            "required": ["message_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "gmail_label_add",
        "description": "Apply a label by name (resolved via the adapter's cached label map).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string"},
                "label_name": {"type": "string"},
            },
            "required": ["message_id", "label_name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "gmail_draft_reply",
        "description": (
            "Create a Gmail draft replying to `message_id`. The draft is "
            "linked to the original thread and uses Re: <subject>. Does NOT "
            "send — the user reviews and sends from Gmail's UI."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["message_id", "body"],
            "additionalProperties": False,
        },
    },
]


async def _dispatch(name: str, arguments: dict[str, Any]) -> str:
    try:
        if name == "gmail_list_labels":
            return tool_list_labels()
        if name == "gmail_list_unread":
            return tool_list_unread(
                max_results=int(arguments.get("max_results", 25)),
                query=str(arguments.get("query", "is:unread")),
            )
        if name == "gmail_get_message":
            return tool_get_message(message_id=arguments["message_id"])
        if name == "gmail_archive":
            return tool_archive(message_id=arguments["message_id"])
        if name == "gmail_label_add":
            return tool_label_add(
                message_id=arguments["message_id"],
                label_name=arguments["label_name"],
            )
        if name == "gmail_draft_reply":
            return tool_draft_reply(
                message_id=arguments["message_id"],
                body=arguments["body"],
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

    app = Server("adzekit-gmail")

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
