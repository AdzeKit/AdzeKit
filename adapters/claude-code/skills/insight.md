# Insight

## Goal

Synthesize accumulated shed data over a window (weekly / monthly / quarterly)
into a reviewable markdown draft. The deterministic extractors (run via
`adzekit insight --period <P>`) produce the raw numbers — velocity, carry-
forward patterns, energy, tags, raw reflections. The skill layer reads the
deterministic draft and polishes it with synthesis the extractors can't do:
themes across reflections, suggested experiments, narrative.

Output goes to `drafts/insights/insight-<period>-<id>-<host>.md` and surfaces
in INBOX. The human reviews via `adzekit drafts show N` and promotes with
`accept`.

## Inputs

- `{SHED}/knowledge/soul.md` — voice for the synthesis
- The deterministic draft produced by `adzekit insight --period <P>` (the
  skill is invoked AFTER the CLI runs and reads the draft body verbatim,
  then polishes the final two sections)
- `{SHED}/daily/YYYY-MM-DD.md` for each day in the window (already
  summarized in the deterministic draft's `## Reflections (per day)` block)
- `{SHED}/loops/open.md` (or `active.md`) — for cross-reference

## Process

1. **Read the deterministic draft.** The CLI has already run; the body
   includes the data sections (Velocity, Carry-forward, Energy, Top tags,
   Reflections). Don't re-extract.

2. **Read soul.md** for voice and any explicit "things to notice" hints.

3. **Synthesize themes from reflections.** Across the per-day reflection
   bullets, find phrases / topics / feelings that repeat ≥3 times. The
   deterministic extractor doesn't do text similarity — this is the
   skill's job. Be specific: "morning email overwhelm mentioned Mon, Wed,
   Fri" beats "feels overwhelmed."

4. **Connect velocity to reflections.** The data says "5 opened, 2 closed,
   closure rate 40%" — what does the human say in their reflections about
   it? If they mentioned being interrupted, surface that connection.

5. **Suggest experiments for next period.** 2-3 small things. Concrete,
   reversible, time-boxed. Examples:
   - "Try blocking 09:00-11:00 every day next week; you mentioned
     interruptions 3 days running."
   - "Send the Acme summary by Tuesday EOD; it's carried 4 days now."
   - "Tag #deep-work on log entries to get a hit-rate signal next month."

6. **Rewrite the `## Themes & suggested experiments` section** of the
   draft (currently a placeholder). Replace the placeholder text with
   the synthesis. Leave the rest of the draft alone — the deterministic
   sections are the source of truth.

7. **Re-save the draft** in place. Provenance hash will change but the
   sidecar entry stays.

## Outputs

- Modified `{SHED}/drafts/insights/insight-<period>-<id>-<host>.md`:
  the data sections remain unchanged; the final synthesis section is
  populated with themes + experiments + narrative.

## Safety Rules

- Never invent reflection content the human didn't write. If the
  reflections are sparse, say so and stop short.
- Never modify the deterministic data sections (Velocity, Carry-forward,
  Energy, Top tags, Reflections per day). Those are facts.
- Promote nothing autonomously; the draft stays in `drafts/insights/`
  until the human accepts it.
- Voice from soul.md is suggestive, not prescriptive — if soul.md is
  empty, default to direct + concise.

## Notes for adapters

- The CLI does the heavy lifting (file I/O, extraction, draft writing).
  The skill layer adds LLM polish on top of an already-complete draft.
- Cadence: weekly default Fri 16:00 (after weekly-review and distill).
  Monthly default last Friday of month. Quarterly manual.
- For Claude Code: the slash command should be a thin pointer that
  invokes `adzekit insight --period <P>` first via Bash, then reads the
  resulting draft and polishes the synthesis section in-place.
