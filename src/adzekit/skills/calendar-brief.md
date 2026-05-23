# Calendar Brief

## Goal

Generate a one-glance briefing of the user's day from Google Calendar.
Feeds `/daily-start` and any other skill that wants situational awareness
of today's commitments. Output is concise — designed to fit in a Telegram
chunk or a daily-note Triage section.

Requires the Google Calendar adapter installed (`adzekit adapter install
google-calendar`).

## Inputs

- `{SHED}/knowledge/soul.md` — voice (default: terse)
- The user's primary calendar (configurable via `--calendar` flag in
  the CLI, or `calendar_id` argument when invoked from another skill)
- Optional `{SHED}/drafts/.adapters/calendar-list.json` — the cached
  calendar list from `adzekit adapter install google-calendar`

## Process

1. **Run the deterministic helper.** Either:
   - `adzekit calendar today` (writes a terminal block; capture stdout), or
   - Call `adzekit.modules.adapters_calendar.list_today_events()` from
     Python.
2. **Group and prune.** Drop events with `status: cancelled`. Group
   recurring events with the same title. Highlight any event with >4
   attendees as "broadcast" (read-only attendance).
3. **Add prep notes.** For each event with a `location` (Zoom, in-person)
   or a project-aligned title, add a one-line prep note. Don't invent
   prep notes for events with no context — terse > made-up.
4. **Render.** Three-section briefing:
   ```markdown
   # Today — {date}, {N} event(s)

   ## Schedule
   {compact list with times + summaries}

   ## Heads-up
   {1-3 lines: longest event, biggest meeting, any conflicts}

   ## Prep
   {2-4 short prep items, or "(no prep needed)"}
   ```

## Outputs

- **Standalone mode**: a draft at
  `{SHED}/drafts/calendar-brief-YYYY-MM-DD-HHMMSS-{host}.md`,
  surfaced in INBOX.
- **Embedded mode**: the briefing string returned to the caller skill
  (e.g., `/daily-start`) for inclusion in its own draft.

## Safety Rules

- Never auto-create, modify, or decline calendar events.
- Attendee emails are private; surface counts, not lists, unless the
  user explicitly asks.
- If the Calendar adapter isn't installed or auth fails, print a clear
  error and stop — don't fabricate a fake briefing.

## Notes for adapters

- The skill is data-thin; most of the heavy lifting is in the adapter's
  `list_today_events`. The skill layer is mostly formatting + voice.
- For the Telegram gateway, calendar-brief is a high-value reactive
  command: "what's on my plate today?" → briefing in one round-trip.
