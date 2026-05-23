"""Google Calendar adapter: today-briefing helper for the daily-start ritual.

Like the Gmail adapter, this is a thin layer over `gcloud auth` + the
Calendar REST API. Install validates access + caches the calendar list;
the `list_today_events` helper is what skills (and `adzekit calendar today`)
call to get a one-glance briefing.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

from adzekit.config import Settings, get_settings
from adzekit.modules.google_auth import (
    GoogleAuthError,
    gcloud_available,
    get_access_token,
)

CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"


def _calendar_get(path: str, token: str) -> dict[str, Any]:
    req = urllib.request.Request(
        f"{CALENDAR_API_BASE}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def list_calendars(token: str) -> list[dict[str, str]]:
    """Return [{id, summary, primary, accessRole}, ...]."""
    payload = _calendar_get("/users/me/calendarList", token)
    return [
        {
            "id": c["id"],
            "summary": c.get("summary", ""),
            "primary": c.get("primary", False),
            "accessRole": c.get("accessRole", ""),
        }
        for c in payload.get("items", [])
    ]


def list_today_events(
    *,
    calendar_id: str = "primary",
    target_date: date | None = None,
    token: str | None = None,
) -> list[dict[str, Any]]:
    """Return today's events on `calendar_id`.

    Each event: {summary, start, end, attendees: [emails], location, status}.
    Uses local-time bounds (00:00 → 23:59:59 local). The returned timestamps
    are the raw Calendar API strings (RFC 3339).
    """
    if token is None:
        token = get_access_token()
    target_date = target_date or date.today()
    # Bound times in local timezone, then ISO-format with offset.
    tzinfo = datetime.now().astimezone().tzinfo
    start_dt = datetime.combine(target_date, time(0, 0, 0), tzinfo=tzinfo)
    end_dt = datetime.combine(target_date, time(23, 59, 59), tzinfo=tzinfo)
    params = urllib.parse.urlencode({
        "timeMin": start_dt.isoformat(),
        "timeMax": end_dt.isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
    })
    encoded_calendar = urllib.parse.quote(calendar_id, safe="")
    payload = _calendar_get(
        f"/calendars/{encoded_calendar}/events?{params}", token,
    )
    events: list[dict[str, Any]] = []
    for item in payload.get("items", []):
        events.append({
            "summary": item.get("summary", "(no title)"),
            "start": (item.get("start", {}).get("dateTime")
                      or item.get("start", {}).get("date", "")),
            "end": (item.get("end", {}).get("dateTime")
                    or item.get("end", {}).get("date", "")),
            "attendees": [
                a.get("email", "") for a in item.get("attendees", [])
                if a.get("email")
            ],
            "location": item.get("location", ""),
            "status": item.get("status", ""),
        })
    return events


def install_calendar(settings: Settings | None = None) -> dict[str, Any]:
    """Verify gcloud + Calendar API access; cache the calendar list."""
    settings = settings or get_settings()
    try:
        token = get_access_token()
    except GoogleAuthError as exc:
        return {
            "adapter": "google-calendar",
            "installed": False,
            "reason": str(exc),
        }
    try:
        calendars = list_calendars(token)
    except urllib.error.HTTPError as exc:
        return {
            "adapter": "google-calendar",
            "installed": False,
            "reason": f"Calendar API returned HTTP {exc.code}: {exc.reason}",
        }
    except urllib.error.URLError as exc:
        return {
            "adapter": "google-calendar",
            "installed": False,
            "reason": f"Calendar API unreachable: {exc.reason}",
        }

    cache_dir = settings.drafts_dir / ".adapters"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "calendar-list.json"
    cache_path.write_text(
        json.dumps({"calendars": calendars}, indent=2),
        encoding="utf-8",
    )

    primary = next((c for c in calendars if c.get("primary")), None)
    return {
        "adapter": "google-calendar",
        "installed": True,
        "calendars_total": len(calendars),
        "primary_id": primary["id"] if primary else None,
        "cache_path": str(cache_path),
    }


def status_calendar(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    if not gcloud_available():
        return {
            "adapter": "google-calendar",
            "ready": False,
            "reason": "gcloud not on PATH",
        }
    try:
        token = get_access_token()
    except GoogleAuthError as exc:
        return {
            "adapter": "google-calendar",
            "ready": False,
            "reason": str(exc),
        }
    cache_path = settings.drafts_dir / ".adapters" / "calendar-list.json"
    cached: dict[str, Any] = {}
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cached = {}
    return {
        "adapter": "google-calendar",
        "ready": True,
        "token_present": bool(token),
        "cache_present": cache_path.exists(),
        "calendars": cached.get("calendars", []),
    }


def uninstall_calendar(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    cache_path = settings.drafts_dir / ".adapters" / "calendar-list.json"
    removed = False
    if cache_path.exists():
        cache_path.unlink()
        removed = True
    return {
        "adapter": "google-calendar",
        "removed_cache": removed,
    }


def format_today_briefing(
    *,
    calendar_id: str = "primary",
    target_date: date | None = None,
    token: str | None = None,
) -> str:
    """Render today's events as a compact terminal block."""
    target_date = target_date or date.today()
    try:
        events = list_today_events(
            calendar_id=calendar_id,
            target_date=target_date,
            token=token,
        )
    except GoogleAuthError as exc:
        return f"Calendar unavailable: {exc}"

    if not events:
        return f"No events on {target_date.isoformat()}."

    lines = [f"# {target_date.strftime('%A %Y-%m-%d')} — {len(events)} event(s)"]
    for evt in events:
        start = _format_time(evt["start"])
        end = _format_time(evt["end"])
        summary = evt["summary"]
        people = (
            f" · with {len(evt['attendees'])} attendees"
            if evt["attendees"] else ""
        )
        location = f" @ {evt['location']}" if evt["location"] else ""
        lines.append(f"  {start}–{end}  {summary}{location}{people}")
    return "\n".join(lines)


def _format_time(iso: str) -> str:
    """Best-effort HH:MM extraction from an RFC 3339 timestamp."""
    if not iso:
        return "??:??"
    # All-day events have date only.
    if len(iso) == 10:
        return "all-day"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%H:%M")
    except ValueError:
        return iso[:5]
