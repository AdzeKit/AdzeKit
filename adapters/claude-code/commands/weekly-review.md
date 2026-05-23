---
description: Generate a weekly review draft from open loops, active projects, and daily logs
argument-hint: Optional ISO week (e.g. 2026-W21) or any date within the week
---

Execute the AdzeKit `weekly-review` skill (canonical:
`src/adzekit/skills/weekly-review.md`).

This is a synthesis-bound skill — do NOT fan out to workers. One context
sees the whole week.

Output: `{SHED}/drafts/weekly-review-YYYY-WNN-{host}.md` with sections for
Open Loops, Active Projects, Decisions, Reflection. The review surfaces
loops nearing SLA, stale projects, and repeated themes from the week's
daily reflections.

ARGUMENTS: $ARGUMENTS
