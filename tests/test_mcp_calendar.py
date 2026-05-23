"""Tests for the Calendar MCP server tool dispatchers."""

from __future__ import annotations

import asyncio
import json
from datetime import date

from adzekit.mcp import calendar as cal_mcp


def test_today_events_happy_path(workspace, monkeypatch):
    monkeypatch.setattr(
        "adzekit.mcp.calendar.list_today_events",
        lambda **kw: [
            {
                "summary": "Standup",
                "start": "2026-05-22T09:00:00-06:00",
                "end": "2026-05-22T09:30:00-06:00",
                "attendees": ["a@x.com"],
                "location": "",
                "status": "confirmed",
            }
        ],
    )
    result = json.loads(cal_mcp.tool_today_events(settings=workspace))
    assert len(result) == 1
    assert result[0]["summary"] == "Standup"


def test_today_events_auth_error(workspace, monkeypatch):
    from adzekit.modules.google_auth import GoogleAuthError

    def boom(**kw):
        raise GoogleAuthError("token expired")
    monkeypatch.setattr("adzekit.mcp.calendar.list_today_events", boom)
    result = json.loads(cal_mcp.tool_today_events(settings=workspace))
    assert "error" in result
    assert "token expired" in result["error"]


def test_today_brief_returns_string(workspace, monkeypatch):
    monkeypatch.setattr(
        "adzekit.mcp.calendar.format_today_briefing",
        lambda **kw: "# Friday — 0 events",
    )
    out = cal_mcp.tool_today_brief(settings=workspace)
    assert out.startswith("# Friday")


def test_list_events_with_target_date(workspace, monkeypatch):
    captured = {}

    def fake_list(**kw):
        captured.update(kw)
        return []

    monkeypatch.setattr("adzekit.mcp.calendar.list_today_events", fake_list)
    cal_mcp.tool_list_events(target_date="2026-05-22", settings=workspace)
    assert captured["target_date"] == date(2026, 5, 22)


def test_list_events_invalid_date(workspace, monkeypatch):
    result = json.loads(
        cal_mcp.tool_list_events(target_date="not-a-date", settings=workspace),
    )
    assert "error" in result


def test_list_calendars_happy_path(workspace, monkeypatch):
    monkeypatch.setattr(
        "adzekit.mcp.calendar.get_access_token", lambda **kw: "tok",
    )
    monkeypatch.setattr(
        "adzekit.mcp.calendar.list_calendars",
        lambda token: [{"id": "primary", "summary": "Me", "primary": True}],
    )
    result = json.loads(cal_mcp.tool_list_calendars(settings=workspace))
    assert result[0]["id"] == "primary"


def test_dispatch_unknown_tool():
    result = asyncio.run(cal_mcp._dispatch("garbage", {}))
    assert "unknown tool" in result


def test_dispatch_today_events(workspace, monkeypatch):
    monkeypatch.setattr(
        "adzekit.config.get_settings", lambda *a, **k: workspace,
    )
    monkeypatch.setattr(
        "adzekit.mcp.calendar.list_today_events", lambda **kw: [],
    )
    result = asyncio.run(cal_mcp._dispatch("calendar_today_events", {}))
    # Empty list serializes as "[]".
    assert result.strip() == "[]"
