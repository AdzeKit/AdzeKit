"""Gmail tools for the AdzeKit agent.

These functions are registered with the tool registry so the LLM can
call them during the agentic loop. Each tool wraps a GmailService method
and returns a string suitable for LLM consumption.
"""

import json

from adzekit.agent.tools import registry
from adzekit.services.gmail import GmailService

# Lazily initialized -- created on first tool call
_gmail: GmailService | None = None


def _get_gmail() -> GmailService:
    global _gmail
    if _gmail is None:
        _gmail = GmailService()
    return _gmail


@registry.register(
    name="gmail_get_inbox",
    description="Fetch all messages currently in the Gmail inbox. Returns a list of email summaries.",
    param_descriptions={
        "max_results": "Maximum number of emails to return (default 20).",
    },
)
def gmail_get_inbox(max_results: int = 20) -> str:
    gmail = _get_gmail()
    messages = gmail.get_inbox(max_results=max_results)
    if not messages:
        return json.dumps({"count": 0, "messages": [], "note": "Inbox is empty."})
    result = []
    for msg in messages:
        result.append({
            "id": msg.id,
            "thread_id": msg.thread_id,
            "subject": msg.subject,
            "from": msg.sender,
            "date": msg.date,
            "snippet": msg.snippet,
            "is_unread": msg.is_unread,
            "labels": msg.labels,
        })
    return json.dumps({"count": len(result), "messages": result})


@registry.register(
    name="gmail_get_unread",
    description="Fetch unread messages in the Gmail inbox.",
    param_descriptions={
        "max_results": "Maximum number of emails to return (default 20).",
    },
)
def gmail_get_unread(max_results: int = 20) -> str:
    gmail = _get_gmail()
    messages = gmail.get_unread(max_results=max_results)
    if not messages:
        return json.dumps({"count": 0, "messages": [], "note": "No unread messages."})
    result = []
    for msg in messages:
        result.append({
            "id": msg.id,
            "thread_id": msg.thread_id,
            "subject": msg.subject,
            "from": msg.sender,
            "date": msg.date,
            "snippet": msg.snippet,
            "labels": msg.labels,
        })
    return json.dumps({"count": len(result), "messages": result})


@registry.register(
    name="gmail_read_email",
    description="Read the full content of a specific email by its message ID.",
    param_descriptions={
        "message_id": "The Gmail message ID to read.",
    },
)
def gmail_read_email(message_id: str) -> str:
    gmail = _get_gmail()
    msg = gmail.get_message(message_id)
    return json.dumps({
        "id": msg.id,
        "thread_id": msg.thread_id,
        "subject": msg.subject,
        "from": msg.sender,
        "to": msg.to,
        "date": msg.date,
        "body": msg.body[:3000],  # Truncate very long emails
        "labels": msg.labels,
        "is_unread": msg.is_unread,
    })


@registry.register(
    name="gmail_search",
    description="Search Gmail with a query string (same syntax as Gmail search bar).",
    param_descriptions={
        "query": "Gmail search query, e.g. 'from:alice subject:API' or 'is:unread older_than:2d'.",
        "max_results": "Maximum number of results (default 10).",
    },
)
def gmail_search(query: str, max_results: int = 10) -> str:
    gmail = _get_gmail()
    messages = gmail.search(query, max_results=max_results)
    result = []
    for msg in messages:
        result.append({
            "id": msg.id,
            "subject": msg.subject,
            "from": msg.sender,
            "date": msg.date,
            "snippet": msg.snippet,
        })
    return json.dumps({"count": len(result), "messages": result})


@registry.register(
    name="gmail_archive",
    description="Archive an email (remove it from the inbox). Use this for emails that need no action.",
    param_descriptions={
        "message_id": "The Gmail message ID to archive.",
    },
)
def gmail_archive(message_id: str) -> str:
    gmail = _get_gmail()
    gmail.archive(message_id)
    return json.dumps({"status": "archived", "message_id": message_id})


@registry.register(
    name="gmail_mark_read",
    description="Mark an email as read.",
    param_descriptions={
        "message_id": "The Gmail message ID to mark as read.",
    },
)
def gmail_mark_read(message_id: str) -> str:
    gmail = _get_gmail()
    gmail.mark_read(message_id)
    return json.dumps({"status": "marked_read", "message_id": message_id})


@registry.register(
    name="gmail_add_label",
    description="Add a label to an email. Creates the label if it doesn't exist.",
    param_descriptions={
        "message_id": "The Gmail message ID.",
        "label_name": "Label to add (e.g. 'AdzeKit/ActionRequired', 'AdzeKit/WaitingFor').",
    },
)
def gmail_add_label(message_id: str, label_name: str) -> str:
    gmail = _get_gmail()
    gmail.add_label(message_id, label_name)
    return json.dumps({"status": "labeled", "message_id": message_id, "label": label_name})


@registry.register(
    name="gmail_draft_reply",
    description=(
        "Create a draft reply to an email. The draft is saved in Gmail Drafts "
        "for the user to review before sending. NEVER send directly -- always draft."
    ),
    param_descriptions={
        "message_id": "The original message ID to reply to.",
        "body": "The reply body text.",
    },
)
def gmail_draft_reply(message_id: str, body: str) -> str:
    gmail = _get_gmail()
    original = gmail.get_message(message_id)

    # Build reply subject
    subject = original.subject
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    draft_id = gmail.create_draft(
        to=original.sender,
        subject=subject,
        body=body,
        thread_id=original.thread_id,
    )
    return json.dumps({
        "status": "draft_created",
        "draft_id": draft_id,
        "to": original.sender,
        "subject": subject,
        "note": "Draft saved. User must review and send manually.",
    })


@registry.register(
    name="gmail_archive_batch",
    description="Archive multiple emails at once. Use for bulk cleanup.",
    param_descriptions={
        "message_ids": "List of Gmail message IDs to archive.",
    },
)
def gmail_archive_batch(message_ids: list[str]) -> str:
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
