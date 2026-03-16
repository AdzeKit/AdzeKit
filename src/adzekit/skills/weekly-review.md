# Weekly Review Skill

Generate a weekly review from active loops, active projects, and daily logs.
Writes to `drafts/weekly-review-YYYY-WNN.md`.

Never writes to backbone directories (loops/, projects/, daily/, reviews/).

---

## Shed Access

All reads use the `Read` tool directly on shed files. Writes use `Write` to `{SHED}/drafts/`.

| Data | Path |
|------|------|
| Daily notes | `{SHED}/daily/YYYY-MM-DD.md` (for each day Mon-Sun) |
| Active loops | `{SHED}/loops/active.md` |
| Projects | `{SHED}/projects/*.md` (Glob, then Read each — skip archive/ and backlog/) |
| Draft output | `{SHED}/drafts/weekly-review-YYYY-WNN.md` (Write tool) |

---

## Workflow

### Step 1 — Determine the week

Compute the ISO week to review. Default: the **current ISO week** (Mon-Sun containing today).
Accept an optional argument `$ARGUMENTS` — if provided, interpret as an ISO week string
(e.g. `2026-W09`) or a YYYY-MM-DD date within the target week.

Determine the date of the Sunday ending the week for the header.

### Step 2 — Load backbone context (all in parallel)

Read directly:
- Daily notes: `{SHED}/daily/YYYY-MM-DD.md` for each day Mon-Sun of the target week
- Active loops: `{SHED}/loops/active.md`
- Projects: Glob `{SHED}/projects/*.md` (skip archive/ and backlog/), then Read each

### Step 3 — Synthesize the review

For each section below, extract the relevant information from daily notes, project logs, and loops.

**Active Loops:** List every loop from `loops/active.md`. For each, note whether it was acted on this week (check daily notes and project logs). Flag overdue loops. The review is a prompt to act, schedule, or close each one.

**Active Projects:** For each project file (not archive/backlog), check for log entries dated within this week. Classify as:
- **Moved** — has log entries or daily note mentions this week
- **Stale (>7 days)** — last log entry is older than 7 days

The review is a prompt to kill, defer, or commit to stale projects.

**Decisions & Reflection:** Leave these as prompts for the human to fill in. Pre-populate with observations from the week (e.g., patterns in daily reflections, repeated themes).

### Step 4 — Write the review draft

Use the `Write` tool to create `{SHED}/drafts/weekly-review-YYYY-WNN.md`:

```markdown
# YYYY Week NN Review (YYYY-MM-DD)

## Active Loops
> Review all loops in `loops/active.md`
> For each: act on it, schedule it, or close it

[List each loop with status: acted on / overdue / upcoming]

## Active Projects
> Check progress on each project in `projects/`
> Any project stale for >7 days? Kill, defer, or commit.

| Project | Last Activity | Status | This Week |
|---------|--------------|--------|-----------|
| [slug] | YYYY-MM-DD | Moved / Stale | [brief summary of what happened or "no activity"] |

## Decisions
- What am I saying no to this week?
- What trade-offs am I not admitting to myself?

[Pre-populate with observations from daily reflections if available]

## Reflection
- What drained me this week?
- What energized me?
- What will I stop doing next week?

[Pre-populate with observations from daily reflections if available]
```

### Step 5 — Print terminal summary

Print the review directly to terminal, then note the draft location:

```
Draft saved: drafts/weekly-review-YYYY-WNN.md
```

---

## Safety Rules

- NEVER write to backbone directories: loops/, projects/, daily/, knowledge/, reviews/
- Draft goes to drafts/ only — human promotes to reviews/ if they want
- Do NOT close or modify active loops
- If a daily note is missing, note "(no note)" rather than inventing content

ARGUMENTS: $ARGUMENTS
