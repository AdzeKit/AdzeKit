---
description: Morning ritual — generate today's daily note with focus, carried loops, and triage block
argument-hint: Optional target date (YYYY-MM-DD); defaults to today
---

Execute the AdzeKit `daily-start` skill defined in the skills directory
(canonical source: `src/adzekit/skills/daily-start.md` in the AdzeKit
repository).

The skill produces a draft daily note at
`{SHED}/drafts/daily-start-YYYY-MM-DD-HHMM-{host}.md` with four canonical
sections (## Triage / ## Intention / ## Log / ## Reflection), carried
intentions from yesterday, overdue/due-today loops, and stale draft
alerts. It does NOT write to `daily/` directly — promote with
`adzekit drafts accept <N>`.

Respect deep-work hours from `knowledge/soul.md`: during a declared
deep-work window, write silently and suppress notifications until the
window closes.

ARGUMENTS: $ARGUMENTS
