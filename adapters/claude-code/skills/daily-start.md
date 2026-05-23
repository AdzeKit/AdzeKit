# Daily Start

## Goal

Generate today's daily note pre-populated with real context: yesterday's carried focus, loops
due today or overdue, and a proposed focus line. Also surfaces stale drafts so nothing festers
in the processing queue.

Output goes to `{SHED}/drafts/daily-YYYY-MM-DD.md` for human review. The human moves it into
`{SHED}/daily/YYYY-MM-DD.md`. Never writes directly to `daily/`. Human always decides.

## Inputs

- `{SHED}/knowledge/soul.md` — voice, deep-work hours
- `{SHED}/daily/{today}.md` — to check whether today's note already exists
- `{SHED}/daily/{yesterday}.md` — to extract carried intentions and tomorrow-line
- `{SHED}/loops/open.md` (or `loops/active.md` — adapter resolves which exists) — active loops
- `{SHED}/projects/*.md` — for project context
- `{SHED}/drafts/*.md` — to detect stale drafts (age > 3 days)

## Process

1. **Optional triage pass.** If the adapter has an inbox triage skill installed
   (`{SHED}/skills/inbox-triage.md` or a workspace override) and mail credentials are
   available, the adapter may run it first so DIRECT/URGENT signals from email feed into the
   carried-context computation. If unavailable, skip silently and continue.

2. **Load today's context.** Read all inputs above. Parallelism: all reads are independent.
   Parse loops using the canonical flat format:
   `- [ ] (SIZE) [YYYY-MM-DD] Title (DUE-DATE)`
   Compute overdue, due-today, and upcoming counts.

   If `{SHED}/daily/{today}.md` already exists, print:
   `Today's note already exists at daily/YYYY-MM-DD.md.`
   and stop. Daily-start never overwrites.

3. **Load yesterday's note.** Compute yesterday's date. Read `{SHED}/daily/{yesterday}.md`.
   If it doesn't exist (weekend, travel), try the day before. Go back up to 3 days. Extract:
   - **Tomorrow line**: text after `> End:` blockquote, looking for `Tomorrow:` content
   - **Unchecked items**: any `- [ ]` lines (carried intentions)
   - **Focus line**: text after `> Focus:` (for pattern reference)

4. **Compose focus line and task list.** Build the `> Focus:` line from the highest-priority
   source in this order:
   1. Yesterday's Tomorrow items (if any) — use the first as focus
   2. Most overdue loop (if any)
   3. Most due-today loop (if any)
   4. Blank — let the human fill it

   Build a ranked task list capped at 5 items:
   - All due-today loops: `- [ ] ({size}) [{due_date}] {title}  <- due today`
   - Up to 2 overdue loops: `- [ ] ({size}) [{due_date}] {title}  <- OVERDUE`
   - Yesterday's Tomorrow items (skip if already covered by a loop)
   - Yesterday's unchecked items (skip if already covered)

   Ranking: overdue → due-today → tomorrow → carried. Size-weight: a single `L` or `XL` loop
   counts as 2 slots toward the cap.

5. **Write the draft.** Create `{SHED}/drafts/daily-YYYY-MM-DD-HHMM-{host}.md` with the
   four canonical sections:
   ```markdown
   # YYYY-MM-DD {Day of Week}

   ## Triage
   > Resolve each line before daily-close.
   {triage lines: overdue loops, stale projects, stale bench — empty body if none}

   ## Intention
   {task list from Step 4, one bullet per line}

   ## Log

   ## Reflection
   - **Finished:**
   - **Blocked:**
   - **Tomorrow:**
   ```
   Always include all four headings, even when sections are empty. The structure is the
   product — predictable layout is what makes the day scannable. Daily entries get
   appended to `## Log` later via `/capture` or manual editing.

6. **Scan for stale drafts.** Glob `{SHED}/drafts/*.md`. For each file, compute age in days
   from file modification time. If age > 3 days, add to stale list.

7. **Print terminal summary.**
   ```
   Daily Start — YYYY-MM-DD ({Day of Week})
     Focus: {focus line}
     Tasks: N (from N loops due, N carried, N tomorrow items)
     Overdue loops: N (oldest: TITLE — N days overdue)
     Active loops: N total
     Active projects: N
     Draft: drafts/daily-YYYY-MM-DD.md

   To use: cp {SHED}/drafts/daily-YYYY-MM-DD.md {SHED}/daily/YYYY-MM-DD.md
   ```
   If there are stale drafts:
   ```
   ⚠️  STALE DRAFTS ({count} files, oldest {N} days)
     {filename} — {age}d old
   Process or delete:
     rm {SHED}/drafts/{filename}
   ```

## Outputs

- `{SHED}/drafts/daily-YYYY-MM-DD.md` (with `<!-- adzekit-draft -->` provenance header once
  Phase 2 lands)
- Terminal summary

## Intention quality guidelines

- Prefer specificity: `- [ ] (S) Kick off #acme Phase 0` not `- [ ] Work on projects`
- Respect the WIP cap: 5 tasks maximum. Better to finish 3 than plan 5.
- If yesterday's energy was low (mentioned in `> End:` line), open the focus with:
  `> Low energy carry-over — consider 2 tasks max and one clear win.`

## Safety Rules

- Never write to `daily/` directly — output goes to `drafts/daily-YYYY-MM-DD.md` only
- Never overwrite an existing daily note
- Do not close loops or modify loop data — read only
- Do not add new loops — this is a read-then-draft operation
- Carried intentions are *suggestions* — the human edits before using
- Never delete stale drafts — only surface them for human decision

## Notes for adapters

- Loop file naming varies: `loops/open.md` (workspace convention) or `loops/active.md` (older
  spec). The adapter resolves which is present and reads accordingly.
- Yesterday lookup may need to skip weekends — the "go back up to 3 days" rule handles this.
- Step 1 (optional triage) is the natural point for adapters to demonstrate skill chaining.
  Hermes adapter may use `delegate_tool` to invoke triage as a child agent; Claude Code
  adapter invokes the `/inbox-triage` slash command. Either way, daily-start does not block
  on triage if it's unavailable.
