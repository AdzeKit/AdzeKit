# Weekly Review Skill

Generate a weekly review draft and a copy-pasteable pulse summary from this week's daily logs,
active projects, and open loops. Writes two sections to a single file in `drafts/`:
`weekly-review-YYYY-WNN.md`.

Never writes to backbone directories (loops/, projects/, daily/, reviews/).

## Prerequisites

The `adzekit-backbone` MCP server should be running. If not, fall back to direct file reads
from the shed (default: `~/Repos/adzekit-workspace/`).

---

## Workflow

### Step 1 — Determine the week

Compute the ISO week to review. Default: the **current ISO week** (Mon–Sun containing today).
Accept an optional argument `$ARGUMENTS` — if provided, interpret as an ISO week string
(e.g. `2026-W09`) or a YYYY-MM-DD date within the target week.

```
TODAY = today's date
ISO_WEEK = current ISO week (e.g. "2026-W09")
MONDAY = Monday of that week
SUNDAY = Sunday of that week
WEEK_LABEL = "YYYY-WNN (Mon DD Mon – Sun DD Mon)"
```

### Step 2 — Load backbone context (all in parallel)

**Via MCP (preferred):**
```
backbone_get_week_notes(iso_week=ISO_WEEK)
  → days[]: date, intentions (planned/done), log entries, finished/blocked/tomorrow
  → review_stub: existing reviews/YYYY-WNN.md content if present

backbone_get_projects()
  → project slugs, titles, states, progress %, total/done tasks

backbone_get_open_loops()
  → open commitments with title, size, date, due, who
```

**Via direct file reads (fallback):**
- Daily notes: `{shed}/daily/YYYY-MM-DD.md` for each day Mon–Sun
- Open loops: `{shed}/loops/open.md`
- Projects: `{shed}/projects/*.md` (active) and `{shed}/projects/backlog/*.md`
- Review stub: `{shed}/reviews/YYYY-WNN.md`

### Step 3 — Read active project files for weekly activity

For each active project (state=active from Step 2), read the full project markdown file.
Look for **Log entries** dated within Mon–Sun of the target week. These confirm project
work that may not appear in daily notes.

Use the raw_content from backbone_get_projects or read directly from:
`{shed}/projects/{slug}.md`

### Step 4 — Synthesize the review

Build a structured summary by extracting the following from the loaded data:

**Completed work (for pulse bullets):**
- Intentions marked `[x]` in daily notes (done=True)
- Significant log entries from daily notes (skip trivial ones like "swept loops")
- Project log entries dated this week

**Proud-of candidates:** Look for customer wins, shipped work, difficult problems solved,
new relationships, positive feedback, meaningful progress on active projects.

**Blockers/challenges:** Look for `blocked:` sections in daily notes, loops marked overdue,
project friction notes.

**Next-week focus:** Derive from open loops (especially M/L/XL sized), upcoming project
milestones, and `tomorrow:` / intentions carried forward.

**Project pulse:** For each active project, note if it moved this week (log entry present),
is stale (no log entries this week), or completed tasks.

### Step 5 — Write the review draft

Call `backbone_write_draft('weekly-review-YYYY-WNN.md', content)` where content follows
this format:

```markdown
# Weekly Review — YYYY-WNN
_(Mon YYYY-MM-DD → Sun YYYY-MM-DD)_

---

## Pulse Summary
> Copy-paste this section for standups, Slack, or manager check-ins.

✅ **What I got done this week that I'm proud of:**
- [bullet 1 — specific customer/project win or shipped work]
- [bullet 2]
- [bullet 3 — optional]

🎯 **Top focus for next week:**
- [bullet 1 — most important commitment or project milestone]
- [bullet 2]
- [bullet 3 — optional]

⚠️ **Blockers or challenges:**
- [bullet — or "Nothing critical to flag this week"]

---

## Day-by-Day Log

### Monday YYYY-MM-DD
**Planned:** [intentions from daily note, or "(no note)"]
**Completed:** [done intentions]
**Log:** [key log entries]

### Tuesday YYYY-MM-DD
...

[repeat for Wed, Thu, Fri]

### Weekend (Sat–Sun)
[brief if any log entries, otherwise omit]

---

## Active Projects

| Project | Progress | Moved this week? | Notes |
|---------|----------|------------------|-------|
| [slug]  | [X%]     | ✅ Yes / ⬜ No   | [brief] |

**Backlog projects to promote or kill:**
- [slugs at risk of going stale, or ready to activate]

---

## Open Loops

**Due this week / overdue:**
- [loop lines from loops/open.md, formatted as existing task lines]

**Coming up next week:**
- [loops with due dates next week]

**All open loops:** N total

---

## Decisions

- What am I saying no to next week?
  → [your answer, or leave blank for human to fill]
- Any trade-offs I'm not admitting to myself?
  → [your answer, or leave blank]

---

## Reflection

- **What drained me this week?**
  → [from finished/blocked/log notes, or leave blank]
- **What energized me?**
  → [from log notes, or leave blank]
- **What will I stop doing next week?**
  → [your answer, or leave blank]

---
Generated: YYYY-MM-DD HH:MM
Week: YYYY-WNN (Mon YYYY-MM-DD → Sun YYYY-MM-DD)
Projects checked: N active, N backlog · Open loops: N · Daily notes found: N/7
```

### Step 6 — Print terminal summary

```
Weekly Review complete — YYYY-WNN
  Week:        Mon YYYY-MM-DD → Sun YYYY-MM-DD
  Daily notes: N/7 days found
  Projects:    N active, N backlog
  Open loops:  N
  Draft:       drafts/weekly-review-YYYY-WNN.md
```

---

## Pulse Summary Guidelines

**✅ Proud-of bullets** — be specific, not generic:
- Name the customer or project: "Ran Sobeys Vibecoding Hackathon — 20+ engineers shipped demos"
- Mention shipped work: "Delivered Citco column-mapping shadow dataset and design doc"
- Or a process win: "Cleared 8 open loops across Ovintiv and OTPP"
- AVOID: "Worked on various projects", "Had good meetings"

**🎯 Focus bullets** — name the highest-leverage thing:
- Active project milestone: "Complete AER CMP Phase 0 onsite working session"
- Customer commitment: "Ship OTPP risk use case demo"
- AVOID: "Keep doing good work"

**⚠️ Blockers** — be honest:
- Technical: "OTPP blocked on Gemini API gating — Databricks engineering followup needed"
- Capacity: "TKO travel week — low-bandwidth for async work"
- If nothing: "Nothing critical to flag this week"

---

## Safety Rules

- NEVER write to backbone directories: loops/, projects/, daily/, knowledge/, reviews/
- Draft goes to drafts/ only — human promotes to reviews/ if they want
- Do NOT close or modify open loops
- Pulse bullets are suggestions — human should edit before sharing externally
- If a daily note is missing, note "(no note)" rather than inventing content

---

## MCP Configuration

```json
{
  "mcpServers": {
    "adzekit-backbone": {
      "command": "adzekit-mcp-backbone",
      "env": {
        "ADZEKIT_SHED": "/Users/scott.mckean/Repos/adzekit-workspace"
      }
    }
  }
}
```

Restart Claude Code after updating MCP servers to pick up the new `backbone_get_week_notes` tool.

ARGUMENTS: $ARGUMENTS
