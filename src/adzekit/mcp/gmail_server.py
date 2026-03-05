"""Gmail MCP server for AdzeKit.

Exposes the GmailService as a set of MCP tools that any MCP-compatible client
(Cursor, Claude Desktop, etc.) can call over stdio.

Safety: no send, delete, or trash tools are exposed. The underlying GmailService
also blocks these operations with PermissionError guards.

Usage:
    adzekit mcp-gmail
    uv run python -m adzekit.mcp.gmail_server
"""

from __future__ import annotations

import json

from fastmcp import FastMCP

from adzekit.services.gmail import GmailService

mcp = FastMCP("AdzeKit Gmail")

_gmail: GmailService | None = None


def _get_gmail() -> GmailService:
    global _gmail
    if _gmail is None:
        _gmail = GmailService()
    return _gmail


@mcp.tool
def gmail_get_inbox(max_results: int = 20) -> str:
    """Fetch messages currently in the Gmail inbox.

    Args:
        max_results: Maximum number of emails to return.
    """
    gmail = _get_gmail()
    messages = gmail.get_inbox(max_results=max_results)
    if not messages:
        return json.dumps({"count": 0, "messages": [], "note": "Inbox is empty."})
    result = [
        {
            "id": msg.id,
            "thread_id": msg.thread_id,
            "subject": msg.subject,
            "from": msg.sender,
            "date": msg.date,
            "snippet": msg.snippet,
            "is_unread": msg.is_unread,
            "labels": msg.labels,
        }
        for msg in messages
    ]
    return json.dumps({"count": len(result), "messages": result})


@mcp.tool
def gmail_get_unread(max_results: int = 20) -> str:
    """Fetch unread messages in the Gmail inbox.

    Args:
        max_results: Maximum number of emails to return.
    """
    gmail = _get_gmail()
    messages = gmail.get_unread(max_results=max_results)
    if not messages:
        return json.dumps({"count": 0, "messages": [], "note": "No unread messages."})
    result = [
        {
            "id": msg.id,
            "thread_id": msg.thread_id,
            "subject": msg.subject,
            "from": msg.sender,
            "date": msg.date,
            "snippet": msg.snippet,
            "labels": msg.labels,
        }
        for msg in messages
    ]
    return json.dumps({"count": len(result), "messages": result})


@mcp.tool
def gmail_read_email(message_id: str) -> str:
    """Read the full content of a specific email by its message ID.

    Args:
        message_id: The Gmail message ID to read.
    """
    gmail = _get_gmail()
    msg = gmail.get_message(message_id)
    return json.dumps({
        "id": msg.id,
        "thread_id": msg.thread_id,
        "subject": msg.subject,
        "from": msg.sender,
        "to": msg.to,
        "date": msg.date,
        "body": msg.body[:3000],
        "labels": msg.labels,
        "is_unread": msg.is_unread,
    })


@mcp.tool
def gmail_search(query: str, max_results: int = 10) -> str:
    """Search Gmail with a query string (same syntax as the Gmail search bar).

    Args:
        query: Gmail search query, e.g. 'from:alice subject:API' or 'is:unread older_than:2d'.
        max_results: Maximum number of results.
    """
    gmail = _get_gmail()
    messages = gmail.search(query, max_results=max_results)
    result = [
        {
            "id": msg.id,
            "subject": msg.subject,
            "from": msg.sender,
            "date": msg.date,
            "snippet": msg.snippet,
        }
        for msg in messages
    ]
    return json.dumps({"count": len(result), "messages": result})


@mcp.tool
def gmail_archive(message_id: str) -> str:
    """Archive an email (remove it from the inbox).

    Args:
        message_id: The Gmail message ID to archive.
    """
    gmail = _get_gmail()
    gmail.archive(message_id)
    return json.dumps({"status": "archived", "message_id": message_id})


@mcp.tool
def gmail_mark_read(message_id: str) -> str:
    """Mark an email as read.

    Args:
        message_id: The Gmail message ID to mark as read.
    """
    gmail = _get_gmail()
    gmail.mark_read(message_id)
    return json.dumps({"status": "marked_read", "message_id": message_id})


@mcp.tool
def gmail_star(message_id: str) -> str:
    """Star an email (add the Gmail STARRED system label).

    Args:
        message_id: The Gmail message ID to star.
    """
    gmail = _get_gmail()
    gmail.star(message_id)
    return json.dumps({"status": "starred", "message_id": message_id})


@mcp.tool
def gmail_add_label(message_id: str, label_name: str) -> str:
    """Add a label to an email. Creates the label if it does not exist.

    Args:
        message_id: The Gmail message ID.
        label_name: Label to add (e.g. 'AdzeKit/ActionRequired').
    """
    gmail = _get_gmail()
    gmail.add_label(message_id, label_name)
    return json.dumps({"status": "labeled", "message_id": message_id, "label": label_name})


@mcp.tool
def gmail_draft_reply(message_id: str, body: str) -> str:
    """Create a draft reply to an email, with the original thread quoted below.
    The draft is saved in Gmail Drafts for the user to review before sending --
    never sends directly.

    Args:
        message_id: The original message ID to reply to.
        body: The reply body text (stub only; original thread is appended automatically).
    """
    gmail = _get_gmail()
    original = gmail.get_message(message_id)

    subject = original.subject
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    # Append quoted original thread below the reply stub
    quote_header = f"On {original.date}, {original.sender} wrote:"
    quoted = "\n".join(f"> {line}" for line in original.body.splitlines())
    full_body = f"{body}\n\n{quote_header}\n{quoted}" if original.body else body

    draft_id = gmail.create_draft(
        to=original.sender,
        subject=subject,
        body=full_body,
        in_reply_to=original.message_id_header or None,
        thread_id=original.thread_id,
    )
    return json.dumps({
        "status": "draft_created",
        "draft_id": draft_id,
        "to": original.sender,
        "subject": subject,
        "note": "Draft saved. User must review and send manually.",
    })


@mcp.tool
def gmail_archive_batch(message_ids: list[str]) -> str:
    """Archive multiple emails at once.

    Args:
        message_ids: List of Gmail message IDs to archive.
    """
    gmail = _get_gmail()
    archived = []
    errors = []
    for mid in message_ids:
        try:
            gmail.archive(mid)
            archived.append(mid)
        except Exception as exc:
            errors.append({"id": mid, "error": str(exc)})
    return json.dumps({
        "archived_count": len(archived),
        "error_count": len(errors),
        "errors": errors,
    })


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
