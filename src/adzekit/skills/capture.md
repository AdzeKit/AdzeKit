# Capture

## Goal

Append a single line to today's daily note. The smallest possible interaction with the shed —
one thought, one line, zero ceremony. Used throughout the day to log decisions, observations,
and one-line notes without breaking flow.

## Inputs

- `{SHED}/daily/{today}.md` — today's daily note (existence required; capture does not create
  the daily note, only appends to it)
- The line to append (provided as an argument)

## Process

1. Resolve `{today}` as `YYYY-MM-DD` in the local timezone.
2. Read `{SHED}/daily/{today}.md`. If it doesn't exist, print:
   ```
   No daily note for {today}. Run /daily-start first.
   ```
   and stop. Capture never creates daily notes — that's daily-start's job.
3. Determine the insertion point: the end of the `## Log` section. If the daily note follows
   the four-section format (Triage / Intention / Log / Reflection), insert immediately after
   the last existing line within `## Log` and before the start of `## Reflection`. If the
   note lacks a `## Log` heading (legacy format), fall back to inserting before any `> End:`
   blockquote, or at end-of-file when no bookend is present.
4. Format the line with a timestamp prefix: `- [HH:MM] {text}` (24-hour local time).
5. Append the formatted line to the daily note.
6. Print one line to terminal confirming the capture.

## Outputs

- Modified `{SHED}/daily/{today}.md` (append-only; no other section touched)
- One-line terminal confirmation: `Captured: [HH:MM] {text}`

## Safety Rules

- Capture writes directly to `daily/` because the append is single-line, traceable in git,
  and reversible by deleting one line. This is the only skill in core that writes to backbone
  without going through `drafts/`. The justification: the act of capture IS the decision — there
  is nothing for the human to review later that wasn't reviewed at capture time.
- Never modify existing lines. Append only.
- Never write to a daily note that doesn't exist. Stop and tell the human to run daily-start.
- If the line argument is empty or whitespace-only, stop and print a usage hint.

## Notes for adapters

This skill is intentionally trivial — most adapters can implement it as a pure file operation
with no LLM call at all. The shell equivalent is roughly:

```bash
# Naive append (no section-awareness):
echo "- $(date +%H:%M) $TEXT" >> "$SHED/daily/$(date +%Y-%m-%d).md"
```

The CLI `adzekit log "..."` (already present in workspace as `/log`) is the canonical
non-agent implementation; it inserts at the end of `## Log` rather than at EOF. Agent-based
adapters should route to the CLI rather than re-implementing the section-aware insert.
