"""Tests for the Google Workspace adapters (Gmail + Calendar).

All gcloud invocations and HTTP calls are mocked; tests don't touch the
network or require gcloud to be installed.
"""

from __future__ import annotations

import json
import subprocess
from datetime import date

import pytest

from adzekit.modules import adapters_calendar, adapters_gmail, google_auth
from adzekit.modules.google_auth import GoogleAuthError


# --- google_auth -----------------------------------------------------------


def test_get_access_token_missing_gcloud(monkeypatch):
    monkeypatch.setattr("adzekit.modules.google_auth.shutil.which", lambda _: None)
    with pytest.raises(GoogleAuthError, match="not on PATH"):
        google_auth.get_access_token()


def test_get_access_token_happy_path(monkeypatch):
    monkeypatch.setattr(
        "adzekit.modules.google_auth.shutil.which", lambda _: "/usr/bin/gcloud",
    )

    class R:
        returncode = 0
        stdout = "ya29.fake-token\n"
        stderr = ""

    monkeypatch.setattr(
        "adzekit.modules.google_auth.subprocess.run",
        lambda *a, **kw: R(),
    )
    token = google_auth.get_access_token()
    assert token == "ya29.fake-token"


def test_get_access_token_nonzero_rc(monkeypatch):
    monkeypatch.setattr(
        "adzekit.modules.google_auth.shutil.which", lambda _: "/usr/bin/gcloud",
    )

    class R:
        returncode = 1
        stdout = ""
        stderr = "ERROR: not logged in"

    monkeypatch.setattr(
        "adzekit.modules.google_auth.subprocess.run", lambda *a, **kw: R(),
    )
    with pytest.raises(GoogleAuthError, match="not logged in"):
        google_auth.get_access_token()


def test_get_access_token_empty_token(monkeypatch):
    monkeypatch.setattr(
        "adzekit.modules.google_auth.shutil.which", lambda _: "/usr/bin/gcloud",
    )

    class R:
        returncode = 0
        stdout = "   \n"
        stderr = ""

    monkeypatch.setattr(
        "adzekit.modules.google_auth.subprocess.run", lambda *a, **kw: R(),
    )
    with pytest.raises(GoogleAuthError, match="empty token"):
        google_auth.get_access_token()


def test_get_access_token_timeout(monkeypatch):
    monkeypatch.setattr(
        "adzekit.modules.google_auth.shutil.which", lambda _: "/usr/bin/gcloud",
    )

    def raise_timeout(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="gcloud", timeout=10.0)

    monkeypatch.setattr(
        "adzekit.modules.google_auth.subprocess.run", raise_timeout,
    )
    with pytest.raises(GoogleAuthError, match="did not respond"):
        google_auth.get_access_token()


# --- Gmail adapter ---------------------------------------------------------


def test_install_gmail_no_gcloud(workspace, monkeypatch):
    monkeypatch.setattr(
        "adzekit.modules.adapters_gmail.get_access_token",
        lambda **kw: (_ for _ in ()).throw(GoogleAuthError("gcloud missing")),
    )
    result = adapters_gmail.install_gmail(workspace)
    assert result["installed"] is False
    assert "gcloud missing" in result["reason"]


def test_install_gmail_happy_path(workspace, monkeypatch):
    monkeypatch.setattr(
        "adzekit.modules.adapters_gmail.get_access_token",
        lambda **kw: "token-xyz",
    )
    monkeypatch.setattr(
        "adzekit.modules.adapters_gmail.list_labels",
        lambda token: [
            {"id": "Label_1", "name": "AdzeKit/ActionRequired", "type": "user"},
            {"id": "Label_2", "name": "AdzeKit/Urgent", "type": "user"},
            {"id": "Label_3", "name": "Other", "type": "user"},
            {"id": "INBOX", "name": "INBOX", "type": "system"},
        ],
    )
    result = adapters_gmail.install_gmail(workspace)
    assert result["installed"] is True
    assert result["labels_total"] == 4
    assert result["missing_labels"] == []
    # Cache file written.
    cache = workspace.drafts_dir / ".adapters" / "gmail-labels.json"
    assert cache.exists()
    data = json.loads(cache.read_text())
    assert data["labels"]["AdzeKit/ActionRequired"] == "Label_1"


def test_install_gmail_reports_missing_labels(workspace, monkeypatch):
    monkeypatch.setattr(
        "adzekit.modules.adapters_gmail.get_access_token",
        lambda **kw: "token-xyz",
    )
    monkeypatch.setattr(
        "adzekit.modules.adapters_gmail.list_labels",
        lambda token: [
            {"id": "INBOX", "name": "INBOX", "type": "system"},
        ],
    )
    result = adapters_gmail.install_gmail(workspace)
    assert result["installed"] is True
    assert set(result["missing_labels"]) == {"AdzeKit/ActionRequired", "AdzeKit/Urgent"}


def test_status_gmail_no_gcloud(workspace, monkeypatch):
    monkeypatch.setattr(
        "adzekit.modules.adapters_gmail.gcloud_available", lambda: False,
    )
    result = adapters_gmail.status_gmail(workspace)
    assert result["ready"] is False
    assert "gcloud" in result["reason"]


def test_status_gmail_ready_with_cache(workspace, monkeypatch):
    monkeypatch.setattr(
        "adzekit.modules.adapters_gmail.gcloud_available", lambda: True,
    )
    monkeypatch.setattr(
        "adzekit.modules.adapters_gmail.get_access_token", lambda **kw: "tok",
    )
    cache_dir = workspace.drafts_dir / ".adapters"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "gmail-labels.json").write_text(json.dumps({
        "labels": {"AdzeKit/Urgent": "L_3"},
        "missing": ["AdzeKit/ActionRequired"],
    }))
    result = adapters_gmail.status_gmail(workspace)
    assert result["ready"] is True
    assert result["cache_present"] is True
    assert "AdzeKit/ActionRequired" in result["missing_labels"]


def test_uninstall_gmail_removes_cache(workspace):
    cache_dir = workspace.drafts_dir / ".adapters"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "gmail-labels.json"
    cache_path.write_text("{}")
    result = adapters_gmail.uninstall_gmail(workspace)
    assert result["removed_cache"] is True
    assert not cache_path.exists()


def test_uninstall_gmail_no_cache(workspace):
    result = adapters_gmail.uninstall_gmail(workspace)
    assert result["removed_cache"] is False


# --- Calendar adapter ------------------------------------------------------


def test_install_calendar_no_auth(workspace, monkeypatch):
    monkeypatch.setattr(
        "adzekit.modules.adapters_calendar.get_access_token",
        lambda **kw: (_ for _ in ()).throw(GoogleAuthError("nope")),
    )
    result = adapters_calendar.install_calendar(workspace)
    assert result["installed"] is False


def test_install_calendar_happy_path(workspace, monkeypatch):
    monkeypatch.setattr(
        "adzekit.modules.adapters_calendar.get_access_token",
        lambda **kw: "tok",
    )
    monkeypatch.setattr(
        "adzekit.modules.adapters_calendar.list_calendars",
        lambda token: [
            {"id": "primary", "summary": "Me", "primary": True, "accessRole": "owner"},
            {"id": "work@x.com", "summary": "Work", "primary": False, "accessRole": "reader"},
        ],
    )
    result = adapters_calendar.install_calendar(workspace)
    assert result["installed"] is True
    assert result["calendars_total"] == 2
    assert result["primary_id"] == "primary"
    cache = workspace.drafts_dir / ".adapters" / "calendar-list.json"
    assert cache.exists()


def test_list_today_events_formats_request(monkeypatch):
    """Ensure list_today_events passes a sane query (timeMin/timeMax bounds)."""
    captured = {}

    def fake_calendar_get(path, token):
        captured["path"] = path
        captured["token"] = token
        return {
            "items": [
                {
                    "summary": "Standup",
                    "start": {"dateTime": "2026-05-22T09:00:00-06:00"},
                    "end": {"dateTime": "2026-05-22T09:30:00-06:00"},
                    "attendees": [{"email": "a@x.com"}, {"email": "b@x.com"}],
                    "status": "confirmed",
                },
            ],
        }

    monkeypatch.setattr(
        "adzekit.modules.adapters_calendar._calendar_get", fake_calendar_get,
    )
    events = adapters_calendar.list_today_events(
        token="fake",
        target_date=date(2026, 5, 22),
    )
    assert "timeMin=" in captured["path"]
    assert "timeMax=" in captured["path"]
    assert "/calendars/primary/events" in captured["path"]
    assert captured["token"] == "fake"
    assert len(events) == 1
    assert events[0]["summary"] == "Standup"
    assert events[0]["attendees"] == ["a@x.com", "b@x.com"]


def test_list_today_events_handles_all_day(monkeypatch):
    """All-day events use `date` instead of `dateTime`."""
    def fake_get(path, token):
        return {
            "items": [
                {
                    "summary": "Conference",
                    "start": {"date": "2026-05-22"},
                    "end": {"date": "2026-05-23"},
                    "status": "confirmed",
                },
            ],
        }
    monkeypatch.setattr(
        "adzekit.modules.adapters_calendar._calendar_get", fake_get,
    )
    events = adapters_calendar.list_today_events(token="x", target_date=date(2026, 5, 22))
    assert events[0]["start"] == "2026-05-22"


def test_format_today_briefing_no_events(monkeypatch):
    monkeypatch.setattr(
        "adzekit.modules.adapters_calendar.list_today_events",
        lambda **kw: [],
    )
    out = adapters_calendar.format_today_briefing(
        token="fake", target_date=date(2026, 5, 22),
    )
    assert "No events" in out


def test_format_today_briefing_renders_events(monkeypatch):
    monkeypatch.setattr(
        "adzekit.modules.adapters_calendar.list_today_events",
        lambda **kw: [
            {
                "summary": "Standup",
                "start": "2026-05-22T09:00:00-06:00",
                "end": "2026-05-22T09:30:00-06:00",
                "attendees": ["a@x.com"],
                "location": "",
                "status": "confirmed",
            },
            {
                "summary": "POC review",
                "start": "2026-05-22T11:00:00-06:00",
                "end": "2026-05-22T12:00:00-06:00",
                "attendees": ["a@x.com", "b@x.com", "c@x.com"],
                "location": "Zoom",
                "status": "confirmed",
            },
        ],
    )
    out = adapters_calendar.format_today_briefing(
        token="fake", target_date=date(2026, 5, 22),
    )
    assert "Friday 2026-05-22" in out
    assert "2 event(s)" in out
    assert "Standup" in out
    assert "POC review" in out
    assert "Zoom" in out
    assert "with 3 attendees" in out


def test_format_today_briefing_handles_auth_error(monkeypatch):
    def boom(**kw):
        raise GoogleAuthError("token expired")
    monkeypatch.setattr(
        "adzekit.modules.adapters_calendar.list_today_events", boom,
    )
    out = adapters_calendar.format_today_briefing(token=None)
    assert "Calendar unavailable" in out
    assert "token expired" in out


def test_status_calendar_no_gcloud(workspace, monkeypatch):
    monkeypatch.setattr(
        "adzekit.modules.adapters_calendar.gcloud_available", lambda: False,
    )
    result = adapters_calendar.status_calendar(workspace)
    assert result["ready"] is False


def test_uninstall_calendar_removes_cache(workspace):
    cache_dir = workspace.drafts_dir / ".adapters"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "calendar-list.json"
    cache_path.write_text("{}")
    result = adapters_calendar.uninstall_calendar(workspace)
    assert result["removed_cache"] is True
    assert not cache_path.exists()
