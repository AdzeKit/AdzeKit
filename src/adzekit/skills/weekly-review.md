# Weekly Review Skill

Generate a weekly review draft and a copy-pasteable pulse summary from this week's daily logs,
active projects, and active loops. Writes to `drafts/weekly-review-YYYY-WNN.md`.

Never writes to backbone directories (loops/, projects/, daily/, reviews/).

---

## Shed Access

All reads use the `Read` tool directly on shed files. Writes use `Write` to `{SHED}/drafts/`.

| Data | Path |
|------|------|
| Daily notes | `{SHED}/daily/YYYY-MM-DD.md` (for each day Mon-Sun) |
| Active loops | `{SHED}/loops/active.md` |
| Projects | `{SHED}/projects/*.md` (Glob, then Read each) |
| Review stub | `{SHED}/reviews/YYYY-WNN.md` |
| Draft output | `{SHED}/drafts/weekly-review-YYYY-WNN.md` (Write tool) |

---

## Workflow

### Step 1 — Determine the week

Compute the ISO week to review. Default: the **current ISO week** (Mon-Sun containing today).
Accept an optional argument `$ARGUMENTS` — if provided, interpret as an ISO week string
(e.g. `2026-W09`) or a YYYY-MM-DD date within the target week.

### Step 2 — Load backbone context (all in parallel)

Read directly:
- Daily notes: `{SHED}/daily/YYYY-MM-DD.md` for each day Mon-Sun of the target week
- Active loops: `{SHED}/loops/active.md`
- Projects: Glob `{SHED}/projects/*.md`, then Read each
- Review stub: `{SHED}/reviews/YYYY-WNN.md` (if it exists)

### Step 3 — Read active project files for weekly activity

For each active project, read the full project markdown file. Look for **Log entries** dated
within Mon-Sun of the target week. These confirm project work that may not appear in daily notes.

### Step 4 — Synthesize the review

Build a structured summary by extracting:

**Completed work (for pulse bullets):**
- Intentions marked `[x]` in daily notes
- Significant log entries from daily notes
- Project log entries dated this week

**Proud-of candidates:** Customer wins, shipped work, difficult problems solved, meaningful progress.

**Blockers/challenges:** `blocked:` sections in daily notes, overdue loops, project friction.

**Next-week focus:** Active loops (especially M/L/XL), upcoming milestones, carried intentions.

**Project pulse:** For each active project, note if it moved this week or is stale.

### Step 5 — Write the review draft

Use the `Write` tool to create `{SHED}/drafts/weekly-review-YYYY-WNN.md`:

```markdown
# Weekly Review — YYYY-WNN
_(Mon YYYY-MM-DD → Sun YYYY-MM-DD)_

---

## Pulse Summary
> Copy-paste this section for standups, Slack, or manager check-ins.

**What I got done this week that I'm proud of:**
- [bullet 1 — specific win or shipped work]
- [bullet 2]

**Top focus for next week:**
- [bullet 1 — most important commitment]
- [bullet 2]

**Blockers or challenges:**
- [bullet — or "Nothing critical to flag this week"]

---

## Day-by-Day Log

### Monday YYYY-MM-DD
**Planned:** [intentions from daily note, or "(no note)"]
**Completed:** [done intentions]
**Log:** [key log entries]

[repeat for each weekday]

---

## Active Projects

| Project | Progress | Moved this week? | Notes |
|---------|----------|------------------|-------|
| [slug]  | [X%]     | Yes / No         | [brief] |

---

## Active Loops

**Due this week / overdue:**
- [loop lines]

**Coming up next week:**
- [loops with due dates next week]

**All active loops:** N total

---

## Decisions

- What am I saying no to next week?
- Any trade-offs I'm not admitting to myself?

---

## Reflection

- **What drained me this week?**
- **What energized me?**
- **What will I stop doing next week?**

---
Generated: YYYY-MM-DD HH:MM
```

### Step 6 — Print terminal summary

```
Weekly Review complete — YYYY-WNN
  Daily notes: N/7 days found
  Projects:    N active, N backlog
  Active loops:  N
  Draft:       drafts/weekly-review-YYYY-WNN.md
```

---

## Safety Rules

- NEVER write to backbone directories: loops/, projects/, daily/, knowledge/, reviews/
- Draft goes to drafts/ only — human promotes to reviews/ if they want
- Do NOT close or modify active loops
- If a daily note is missing, note "(no note)" rather than inventing content

ARGUMENTS: $ARGUMENTS
