# Weekly Review

## Goal

Run the mechanical weekly ritual: cull drafts into bench, archive daily notes
older than 14 days, and write a pulse summary to `reviews/YYYY-WNN-pulse.md`.

The pulse answers three check-in questions with bullets pre-populated from the
week's daily notes, loops, and projects. Edit the file before sharing.

For the full narrative review (loops table, stale projects, decisions), use
the Claude Code `/weekly-review` skill on top of this pulse draft.

## CLI

```bash
adzekit weekly-review
adzekit weekly-review --date 2026-06-01
```

Cadence: Friday 17:30 via `adzekit cadence install` (`com.adzekit.weekly-review`).

## Pulse sections

1. **What did you get done this week that you're proud of?** — completed
   intentions and reflection finished items
2. **What's your top focus for next week?** — overdue loops, due-soon loops,
   carry-forward intentions, open tasks from the latest daily note
3. **Any blockers or challenges?** — reflection blockers, overdue loops,
   stale active projects (optional — omitted when nothing is flagged)

## Safety

- Writes `reviews/YYYY-WNN-pulse.md` (mechanical ritual output, like `review`)
- Does not modify loops, projects, or daily notes except archiving old dailies
