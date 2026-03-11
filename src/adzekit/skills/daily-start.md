# Daily Start Skill

Generate today's daily note pre-populated with real context: yesterday's carried intentions,
loops due today or overdue, and a proposed set of 3-5 focus tasks for the day. Removes the
blank-page problem at the start of each morning.

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
| Draft output | `{SHED}/drafts/daily-YYYY-MM-DD.md` (Write tool) |

---

## Workflow

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
Today's note already exists at daily/YYYY-MM-DD.md. Use `adzekit today` to open it.
```

### Step 2 — Load yesterday's note

Compute yesterday's date. Read `{SHED}/daily/{yesterday}.md`.

Extract from yesterday:
- **Carried intentions**: `[ ]` (undone) tasks from `## Morning: Intention`
- **Tomorrow items**: text from `## Evening: Reflection` → `**Tomorrow:**` section
- **Blocked items**: text from `## Evening: Reflection` → `**Blocked:**` section

If yesterday's note doesn't exist (weekend, travel), try the day before. Go back up to 3 days.

### Step 3 — Compose the proposed intentions

Build a ranked, de-duplicated list of proposed focus tasks from:

**Source 1 — Loops due today or overdue** (highest priority):
- All due-today loops: `- [ ] ({size}) [{due_date}] {title}  <- due today`
- Up to 2 overdue loops: `- [ ] ({size}) [{due_date}] {title}  <- OVERDUE`

**Source 2 — Yesterday's `Tomorrow:` items:**
- Format as task lines, skip if already covered by a loop from Source 1

**Source 3 — Yesterday's uncompleted intentions:**
- Include any `[ ]` intentions not in Source 1 or 2

**Ranking and capping:**
- Sort: overdue → due today → tomorrow items → carried intentions
- Hard cap: max 5 total tasks
- Size-weight: a single `L` or `XL` loop counts as 2 slots

### Step 4 — Write the draft daily note

Use the `Write` tool to create `{SHED}/drafts/daily-YYYY-MM-DD.md`:

```markdown
# YYYY-MM-DD {Day of Week}

## Morning: Intention
{proposed task list from Step 3}

## Log

## Evening: Reflection
- **Energy:** /5
- **Deep work:**  min
- **Finished:**
- **Blocked:**
- **Tomorrow:**
```

### Step 5 — Print terminal summary

```
Daily Start — YYYY-MM-DD ({Day of Week})
  Proposed tasks: N (from N loops due, N carried, N tomorrow items)
  Overdue loops:  N (oldest: TITLE — N days overdue)
  Active loops:     N total
  Active projects: N
  Draft:          drafts/daily-YYYY-MM-DD.md

To use: mv {SHED}/drafts/daily-YYYY-MM-DD.md {SHED}/daily/YYYY-MM-DD.md
```

---

## Intention Quality Guidelines

**Prefer specificity over vagueness:**
- `- [ ] (S) [2026-03-03] Kick off #acme Phase 0 onsite session` <- good
- `- [ ] Work on projects` <- bad

**For carried intentions, add context:**
- If yesterday's blocked section mentioned it: append `  <- blocked: {reason}`

**Respect the WIP cap:** 5 tasks maximum. Better to finish 3 than to plan 5 and feel behind.

**Energy-aware scheduling:** If yesterday's energy score was <= 2/5, open with:
`> Low energy day — consider 2 tasks max and one clear win.`

---

## Safety Rules

- NEVER write to `daily/` directly — output goes to `drafts/daily-YYYY-MM-DD.md` only
- NEVER overwrite an existing daily note
- Do NOT close loops or modify loop data — read only
- Do NOT add new loops — this is a read-then-draft operation
- Carried intentions are *suggestions* — the human edits before using

ARGUMENTS: $ARGUMENTS
