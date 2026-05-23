---
description: Append a timestamped line to today's daily note under ## Log
argument-hint: The line of text to capture (free-form)
---

Execute the AdzeKit `capture` skill defined in the skills directory of this
plugin (canonical source: `src/adzekit/skills/capture.md` in the AdzeKit
repository).

The skill appends `- [HH:MM] $ARGUMENTS` to the `## Log` section of the
current day's `daily/YYYY-MM-DD.md`. If today's daily note doesn't exist
yet, it instructs the user to run `/daily-start` first — capture never
creates a daily note.

ARGUMENTS: $ARGUMENTS
