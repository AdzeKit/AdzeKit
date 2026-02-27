"""Gmail service for AdzeKit.

Handles OAuth2 authentication and provides functions for reading, searching,
labeling, archiving, and drafting replies to Gmail messages.

Setup:
    1. Create a Google Cloud project and enable the Gmail API.
    2. Create OAuth2 credentials (Desktop App type).
    3. Download the credentials JSON and save as credentials.json
       (or set ADZEKIT_GMAIL_CREDENTIALS_PATH).
    4. On first run, a browser window opens for authorization.
       The token is cached at ~/.adzekit/gmail_token.json.
"""

import base64
import json
import os
from dataclasses import dataclass, field
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.labels",
]


class GmailSettings(BaseSettings):
    """Gmail integration configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ADZEKIT_GMAIL_",
        extra="ignore",
    )

    credentials_path: str = Field(
        default="credentials.json",
        description="Path to Google OAuth2 credentials JSON.",
    )
    token_path: str = Field(
        default="",
        description="Path to cached OAuth token. Defaults to ~/.adzekit/gmail_token.json.",
    )
    max_results: int = Field(
        default=50,
        description="Max emails to fetch per query.",
    )

    @property
    def resolved_token_path(self) -> Path:
        if self.token_path:
            return Path(self.token_path)
        return Path.home() / ".adzekit" / "gmail_token.json"


@dataclass
class EmailMessage:
    """A parsed Gmail message."""

    id: str
    thread_id: str
    subject: str
    sender: str
    to: str
    date: str
    snippet: str
    body: str = ""
    labels: list[str] = field(default_factory=list)
    is_unread: bool = False

    def summary(self) -> str:
        """One-line summary for LLM context."""
        status = "[UNREAD]" if self.is_unread else "[READ]"
        return f"{status} From: {self.sender} | Subject: {self.subject} | Date: {self.date}"


class GmailService:
    """Wrapper around the Gmail API with OAuth2 authentication."""

    def __init__(self, settings: GmailSettings | None = None) -> None:
        self.settings = settings or GmailSettings()
        self._service = None

    def _get_service(self):
        """Lazily build and cache the Gmail API service."""
        if self._service is not None:
            return self._service

        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds = None
        token_path = self.settings.resolved_token_path

        # Load cached token
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        # Refresh or re-authorize
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                cred_path = self.settings.credentials_path
                if not Path(cred_path).exists():
                    raise FileNotFoundError(
                        f"Gmail credentials not found at {cred_path}. "
                        "Download OAuth2 credentials from Google Cloud Console "
                        "and save them, then set ADZEKIT_GMAIL_CREDENTIALS_PATH."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(cred_path, SCOPES)
                creds = flow.run_local_server(port=0)

            # Cache the token
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json(), encoding="utf-8")

        self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def list_messages(
        self,
        query: str = "is:inbox",
        max_results: int | None = None,
    ) -> list[dict]:
        """List message IDs matching a Gmail search query."""
        service = self._get_service()
        max_results = max_results or self.settings.max_results
        results = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        return results.get("messages", [])

    def get_message(self, msg_id: str, format: str = "full") -> EmailMessage:
        """Fetch a single message by ID and parse it into an EmailMessage."""
        service = self._get_service()
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=msg_id, format=format)
            .execute()
        )
        return _parse_message(msg)

    def get_inbox(self, max_results: int | None = None) -> list[EmailMessage]:
        """Fetch all inbox messages, parsed."""
        msg_refs = self.list_messages("is:inbox", max_results)
        messages = []
        for ref in msg_refs:
            messages.append(self.get_message(ref["id"]))
        return messages

    def get_unread(self, max_results: int | None = None) -> list[EmailMessage]:
        """Fetch unread inbox messages."""
        msg_refs = self.list_messages("is:inbox is:unread", max_results)
        messages = []
        for ref in msg_refs:
            messages.append(self.get_message(ref["id"]))
        return messages

    def search(self, query: str, max_results: int | None = None) -> list[EmailMessage]:
        """Search emails with a Gmail query string."""
        msg_refs = self.list_messages(query, max_results)
        messages = []
        for ref in msg_refs:
            messages.append(self.get_message(ref["id"]))
        return messages

    def archive(self, msg_id: str) -> None:
        """Archive a message (remove INBOX label)."""
        service = self._get_service()
        service.users().messages().modify(
            userId="me",
            id=msg_id,
            body={"removeLabelIds": ["INBOX"]},
        ).execute()

    def mark_read(self, msg_id: str) -> None:
        """Mark a message as read."""
        service = self._get_service()
        service.users().messages().modify(
            userId="me",
            id=msg_id,
            body={"removeLabelIds": ["UNREAD"]},
        ).execute()

    def add_label(self, msg_id: str, label_name: str) -> None:
        """Add a label to a message. Creates the label if it doesn't exist."""
        service = self._get_service()
        label_id = self._get_or_create_label(label_name)
        service.users().messages().modify(
            userId="me",
            id=msg_id,
            body={"addLabelIds": [label_id]},
        ).execute()

    def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        in_reply_to: str | None = None,
        thread_id: str | None = None,
    ) -> str:
        """Create a draft email. Returns the draft ID."""
        service = self._get_service()
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
            message["References"] = in_reply_to

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        draft_body: dict[str, Any] = {"message": {"raw": raw}}
        if thread_id:
            draft_body["message"]["threadId"] = thread_id

        draft = (
            service.users()
            .drafts()
            .create(userId="me", body=draft_body)
            .execute()
        )
        return draft["id"]

    def get_labels(self) -> list[dict]:
        """List all labels."""
        service = self._get_service()
        results = service.users().labels().list(userId="me").execute()
        return results.get("labels", [])

    def _get_or_create_label(self, name: str) -> str:
        """Get a label ID by name, creating it if needed."""
        labels = self.get_labels()
        for label in labels:
            if label["name"].lower() == name.lower():
                return label["id"]

        service = self._get_service()
        new_label = (
            service.users()
            .labels()
            .create(
                userId="me",
                body={
                    "name": name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                },
            )
            .execute()
        )
        return new_label["id"]


def _parse_message(msg: dict) -> EmailMessage:
    """Parse a raw Gmail API message dict into an EmailMessage."""
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}

    body = ""
    payload = msg.get("payload", {})
    body = _extract_body(payload)

    labels = msg.get("labelIds", [])

    return EmailMessage(
        id=msg["id"],
        thread_id=msg.get("threadId", ""),
        subject=headers.get("subject", "(no subject)"),
        sender=headers.get("from", ""),
        to=headers.get("to", ""),
        date=headers.get("date", ""),
        snippet=msg.get("snippet", ""),
        body=body,
        labels=labels,
        is_unread="UNREAD" in labels,
    )


def _extract_body(payload: dict) -> str:
    """Recursively extract the plain-text body from a message payload."""
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    parts = payload.get("parts", [])
    for part in parts:
        result = _extract_body(part)
        if result:
            return result

    return ""
