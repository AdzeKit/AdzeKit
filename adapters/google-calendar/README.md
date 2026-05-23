# Google Calendar adapter

Auth + cached calendar list + a `list_today_events` helper. Feeds the
`/calendar-brief` skill and the `adzekit calendar today` terminal command.

## Install

```bash
gcloud auth application-default login          # if not done already
adzekit adapter install google-calendar
```

The install:
- Verifies gcloud + Calendar API access.
- Caches the user's calendar list at
  `{shed}/drafts/.adapters/calendar-list.json`.
- Reports the primary calendar ID (skills default to `primary`; pass
  a calendar ID explicitly to use a sub-calendar).

## Quick briefing

```bash
adzekit calendar today
```

Prints today's events in a compact terminal block:

```
# Monday 2026-05-25 — 3 event(s)
  09:00–09:30  Standup · with 5 attendees
  11:00–12:00  Acme POC review @ Zoom · with 2 attendees
  15:30–16:00  1:1 with manager
```

## Wiring into the daily ritual

The `/daily-start` skill can fold in the calendar brief when the adapter
is installed. From a Claude Code session:

```
You: /daily-start
Claude: [runs daily-start, then optionally calls calendar-brief, then
        composes the morning briefing draft]
```

## Status / Uninstall

```bash
adzekit adapter status google-calendar      # token + cached calendars
adzekit adapter uninstall google-calendar   # remove the cache
```
