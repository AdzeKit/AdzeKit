# Daily Start

Generate today's daily note pre-populated with real context: yesterday's carried focus,
loops due today or overdue, and a proposed focus line. Also surfaces stale drafts so
nothing festers in the processing queue.

Output goes to `drafts/daily-YYYY-MM-DD.md` for human review. The human then moves it into
`daily/YYYY-MM-DD.md`. Never writes directly to `daily/`. Human always decides.

---

## Shed Access

All reads use the `Read` tool directly on shed files. Writes use `Write` to `{SHED}/drafts/`.

| Data | Path |
|------|------|
| Today's note | `{SHED}/daily/YYYY-MM-DD.md` |
| Yesterday's note | `{SHED}/daily/YYYY-MM-DD.md` (previous day) |
| Active loops | `{SHED}/loops/active.md` |
| Projects | `{SHED}/projects/*.md` (Glob, then Read each) |
| Stale drafts | `{SHED}/drafts/*.md` (Glob for age check) |
| Draft output | `{SHED}/drafts/daily-YYYY-MM-DD.md` (Write tool) |

---

## Workflow

### Step 0 — Run inbox-zero first

Invoke the inbox-zero skill (`{SHED}/skills/inbox-zero.md`) and let it complete fully before
moving on. inbox-zero processes up to 100 inbox emails, archives noise, stars REVIEW items, and
writes a triage report + DIRECT loop lines into `drafts/`. Daily-start then picks up those
fresh loop lines as carried context in the steps below.

Keep going across passes if the inbox isn't empty after one batch — inbox-zero is safe to run
repeatedly until the inbox reaches zero or until 5 passes have run (whichever comes first), to
bound runtime.

If gcloud auth or the Gmail API is unavailable (e.g., running in a remote environment without
Gmail credentials), skip Step 0, print a one-line note, and continue with the rest of the
workflow.

### Step 1 — Load today's context

Read all in parallel:
- `{SHED}/daily/{today}.md` — check if today's note already exists
- `{SHED}/loops/active.md` — parse active loops, identify overdue and due-today
- `{SHED}/projects/*.md` — Glob to list, then Read each for slugs, titles, progress

Parse loops from `active.md` using the flat format:
`- [ ] (SIZE) [YYYY-MM-DD] Title (DUE-DATE)`

Compute overdue (due date < today), due-today (due date = today), and upcoming counts.

**If today's note already exists**: print a message and stop:
```
Today's note already exists at daily/YYYY-MM-DD.md.
```

### Step 2 — Load yesterday's note

Compute yesterday's date. Read `{SHED}/daily/{yesterday}.md`.

Extract from yesterday:
- **Tomorrow line**: text after `> End:` → look for `Tomorrow:` content
- **Unchecked items**: any `- [ ]` lines (carried intentions)
- **Focus line**: text after `> Focus:` (for pattern reference)

If yesterday's note doesn't exist (weekend, travel), try the day before. Go back up to 3 days.

### Step 3 — Compose the focus line and task list

Build the `> Focus:` line from the highest-priority source:

1. **Yesterday's Tomorrow items** (if any) — use the first one as focus
2. **Overdue loop** (if any) — use the most overdue as focus
3. **Due-today loop** (if any) — use as focus
4. If nothing: leave blank for human to fill

Build a ranked task list (max 5 items):

**Source 1 — Loops due today or overdue** (highest priority):
- All due-today loops: `- [ ] ({size}) [{due_date}] {title}  <- due today`
- Up to 2 overdue loops: `- [ ] ({size}) [{due_date}] {title}  <- OVERDUE`

**Source 2 — Yesterday's Tomorrow items:**
- Format as task lines, skip if already covered by a loop

**Source 3 — Yesterday's unchecked items:**
- Include any `- [ ]` items not in Source 1 or 2

**Ranking and capping:**
- Sort: overdue → due today → tomorrow items → carried items
- Hard cap: max 5 total tasks
- Size-weight: a single `L` or `XL` loop counts as 2 slots

### Step 4 — Write the draft daily note

Use the `Write` tool to create `{SHED}/drafts/daily-YYYY-MM-DD.md`:

```markdown
# YYYY-MM-DD {Day of Week}

> Focus: {focus line from Step 3}

{task list from Step 3, one bullet per line}

```

That's it. No sections, no ceremony. A focus line and a short task list. The rest of the
day's entries get appended via `/log` or manual editing.

### Step 5 — Scan for stale drafts

Glob `{SHED}/drafts/*.md`. For each file:
- Compute age in days from file modification time (use `ls -la` via Bash)
- If age > 3 days, add to stale list

### Step 6 — Print terminal summary

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

If there are stale drafts, print after the summary:

```
⚠️  STALE DRAFTS ({count} files, oldest {N} days)
  {filename} — {age}d old
  {filename} — {age}d old
  ...

Process or delete:
  rm {SHED}/drafts/{filename}
```

**Intention quality guidelines:**
- Prefer specificity: `- [ ] (S) Kick off #acme Phase 0` not `- [ ] Work on projects`
- Respect the WIP cap: 5 tasks maximum. Better to finish 3 than plan 5.
- If yesterday's energy was low (mentioned in `> End:` line), open with:
  `> Low energy carry-over — consider 2 tasks max and one clear win.`

---

## Safety Rules

- NEVER write to `daily/` directly — output goes to `drafts/daily-YYYY-MM-DD.md` only
- NEVER overwrite an existing daily note
- Do NOT close loops or modify loop data — read only
- Do NOT add new loops — this is a read-then-draft operation
- Carried intentions are *suggestions* — the human edits before using
- NEVER delete stale drafts — only surface them for human decision

ARGUMENTS: $ARGUMENTS
