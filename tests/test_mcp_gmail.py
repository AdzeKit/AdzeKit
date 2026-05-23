"""Tests for the Gmail MCP server tool dispatchers.

The Gmail HTTP layer is mocked end-to-end; we never touch the network.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from adzekit.mcp import gmail as gmail_mcp


def _fake_token(monkeypatch, token: str = "ya29.fake"):
    monkeypatch.setattr(
        "adzekit.mcp.gmail.get_access_token", lambda **kw: token,
    )


# --- gmail_list_labels -----------------------------------------------------


def test_list_labels_happy_path(workspace, monkeypatch):
    _fake_token(monkeypatch)
    monkeypatch.setattr(
        "adzekit.mcp.gmail.list_labels",
        lambda token: [
            {"id": "L_1", "name": "AdzeKit/Urgent", "type": "user"},
        ],
    )
    result = json.loads(gmail_mcp.tool_list_labels(workspace))
    assert len(result) == 1
    assert result[0]["name"] == "AdzeKit/Urgent"


def test_list_labels_auth_error_returned_as_json(workspace, monkeypatch):
    from adzekit.modules.google_auth import GoogleAuthError

    def boom(**kw):
        raise GoogleAuthError("gcloud missing")
    monkeypatch.setattr("adzekit.mcp.gmail.get_access_token", boom)
    result = json.loads(gmail_mcp.tool_list_labels(workspace))
    assert "error" in result
    assert "gcloud" in result["error"]


# --- gmail_list_unread -----------------------------------------------------


def test_list_unread_combines_metadata(workspace, monkeypatch):
    _fake_token(monkeypatch)

    def fake_get(path, token):
        if "/messages?" in path:
            return {
                "messages": [
                    {"id": "m1", "threadId": "t1"},
                    {"id": "m2", "threadId": "t2"},
                ],
            }
        if "/messages/m1" in path:
            return {
                "snippet": "hello there",
                "payload": {"headers": [
                    {"name": "From", "value": "alice@x.com"},
                    {"name": "Subject", "value": "first"},
                    {"name": "Date", "value": "Fri, 22 May 2026"},
                ]},
            }
        if "/messages/m2" in path:
            return {
                "snippet": "another",
                "payload": {"headers": [
                    {"name": "From", "value": "bob@x.com"},
                    {"name": "Subject", "value": "second"},
                    {"name": "Date", "value": "Fri, 22 May 2026"},
                ]},
            }
        return {}

    monkeypatch.setattr("adzekit.mcp.gmail._gmail_get", fake_get)
    result = json.loads(gmail_mcp.tool_list_unread(max_results=2, settings=workspace))
    assert len(result) == 2
    assert result[0]["from"] == "alice@x.com"
    assert result[1]["subject"] == "second"


def test_list_unread_respects_max_results(workspace, monkeypatch):
    _fake_token(monkeypatch)

    def fake_get(path, token):
        if "/messages?" in path:
            assert "maxResults=3" in path
            return {"messages": [{"id": f"m{i}", "threadId": f"t{i}"} for i in range(5)]}
        return {
            "snippet": "",
            "payload": {"headers": []},
        }

    monkeypatch.setattr("adzekit.mcp.gmail._gmail_get", fake_get)
    result = json.loads(gmail_mcp.tool_list_unread(max_results=3, settings=workspace))
    assert len(result) == 3


# --- gmail_get_message -----------------------------------------------------


def test_get_message_extracts_text_plain_body(workspace, monkeypatch):
    import base64
    _fake_token(monkeypatch)
    body_text = "Hello, this is the message body."
    encoded = base64.urlsafe_b64encode(body_text.encode()).decode("ascii")

    def fake_get(path, token):
        return {
            "id": "m1",
            "threadId": "t1",
            "labelIds": ["INBOX", "UNREAD"],
            "payload": {
                "headers": [
                    {"name": "From", "value": "alice@x.com"},
                    {"name": "Subject", "value": "Hi"},
                ],
                "mimeType": "text/plain",
                "body": {"data": encoded},
            },
        }

    monkeypatch.setattr("adzekit.mcp.gmail._gmail_get", fake_get)
    result = json.loads(gmail_mcp.tool_get_message("m1", settings=workspace))
    assert result["from"] == "alice@x.com"
    assert "message body" in result["body"]
    assert "INBOX" in result["labelIds"]


def test_get_message_prefers_text_plain_in_multipart(workspace, monkeypatch):
    import base64
    _fake_token(monkeypatch)
    plain = base64.urlsafe_b64encode(b"PLAIN BODY").decode("ascii")
    html = base64.urlsafe_b64encode(b"<p>HTML</p>").decode("ascii")

    def fake_get(path, token):
        return {
            "id": "m1",
            "threadId": "t1",
            "payload": {
                "headers": [],
                "mimeType": "multipart/alternative",
                "parts": [
                    {"mimeType": "text/html", "body": {"data": html}},
                    {"mimeType": "text/plain", "body": {"data": plain}},
                ],
            },
        }

    monkeypatch.setattr("adzekit.mcp.gmail._gmail_get", fake_get)
    result = json.loads(gmail_mcp.tool_get_message("m1", settings=workspace))
    assert "PLAIN BODY" in result["body"]
    assert "HTML" not in result["body"]


# --- gmail_archive ---------------------------------------------------------


def test_archive_sends_remove_inbox(workspace, monkeypatch):
    _fake_token(monkeypatch)
    captured = {}

    def fake_post(path, token, body):
        captured["path"] = path
        captured["body"] = body
        return {}

    monkeypatch.setattr("adzekit.mcp.gmail._gmail_post", fake_post)
    result = json.loads(gmail_mcp.tool_archive("m1", settings=workspace))
    assert result["archived"] is True
    assert "/messages/m1/modify" in captured["path"]
    assert captured["body"] == {"removeLabelIds": ["INBOX"]}


# --- gmail_label_add -------------------------------------------------------


def test_label_add_uses_cache(workspace, monkeypatch):
    _fake_token(monkeypatch)
    cache_dir = workspace.drafts_dir / ".adapters"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "gmail-labels.json").write_text(
        json.dumps({"labels": {"AdzeKit/Urgent": "L_3"}}),
    )

    captured = {}

    def fake_post(path, token, body):
        captured["body"] = body
        return {}

    monkeypatch.setattr("adzekit.mcp.gmail._gmail_post", fake_post)
    # list_labels shouldn't be called when the cache hits.
    monkeypatch.setattr(
        "adzekit.mcp.gmail.list_labels",
        lambda token: pytest.fail("should have used cache"),
    )
    result = json.loads(
        gmail_mcp.tool_label_add("m1", "AdzeKit/Urgent", settings=workspace),
    )
    assert result["label"] == "AdzeKit/Urgent"
    assert captured["body"] == {"addLabelIds": ["L_3"]}


def test_label_add_falls_back_to_live_lookup(workspace, monkeypatch):
    _fake_token(monkeypatch)
    # No cache.
    monkeypatch.setattr(
        "adzekit.mcp.gmail.list_labels",
        lambda token: [{"id": "L_9", "name": "Custom", "type": "user"}],
    )

    def fake_post(path, token, body):
        return {}

    monkeypatch.setattr("adzekit.mcp.gmail._gmail_post", fake_post)
    result = json.loads(
        gmail_mcp.tool_label_add("m1", "Custom", settings=workspace),
    )
    assert result["labelId"] == "L_9"


def test_label_add_unknown_label_errors(workspace, monkeypatch):
    _fake_token(monkeypatch)
    monkeypatch.setattr(
        "adzekit.mcp.gmail.list_labels",
        lambda token: [],
    )
    result = json.loads(
        gmail_mcp.tool_label_add("m1", "NoSuchLabel", settings=workspace),
    )
    assert "error" in result
    assert "unknown label" in result["error"]


# --- gmail_draft_reply -----------------------------------------------------


def test_draft_reply_builds_re_subject_and_threading(workspace, monkeypatch):
    _fake_token(monkeypatch)

    def fake_get(path, token):
        return {
            "threadId": "thr-1",
            "payload": {"headers": [
                {"name": "From", "value": "alice@x.com"},
                {"name": "Subject", "value": "POC question"},
                {"name": "Message-ID", "value": "<msg-id-1>"},
            ]},
        }

    captured = {}

    def fake_post(path, token, body):
        captured["path"] = path
        captured["body"] = body
        return {"id": "draft-1"}

    monkeypatch.setattr("adzekit.mcp.gmail._gmail_get", fake_get)
    monkeypatch.setattr("adzekit.mcp.gmail._gmail_post", fake_post)
    result = json.loads(
        gmail_mcp.tool_draft_reply("m1", "Replying now.", settings=workspace),
    )
    assert result["draft_id"] == "draft-1"
    assert result["subject"] == "Re: POC question"
    assert result["to"] == "alice@x.com"
    assert captured["body"]["message"]["threadId"] == "thr-1"


# --- _dispatch -------------------------------------------------------------


def test_dispatch_unknown_tool():
    result = asyncio.run(gmail_mcp._dispatch("unknown", {}))
    assert "unknown tool" in result


def test_dispatch_missing_required_arg():
    result = asyncio.run(gmail_mcp._dispatch("gmail_get_message", {}))
    assert "missing required argument" in result
