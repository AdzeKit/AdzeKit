# Daily Start Skill

Generate today's daily note pre-populated with real context: yesterday's carried intentions,
loops due today or overdue, and a proposed set of 3–5 focus tasks for the day. Removes the
blank-page problem at the start of each morning.

Output goes to `drafts/daily-YYYY-MM-DD.md` for human review. The human then moves it into
`daily/YYYY-MM-DD.md` with `mv drafts/daily-YYYY-MM-DD.md daily/YYYY-MM-DD.md` (or the
`adzekit today` command to open a blank note if they prefer to start fresh).

Never writes directly to `daily/`. Human always decides.

---

## Prerequisites

The `adzekit-backbone` MCP server should be running. If not, fall back to direct file reads
from the shed (default `~/Repos/adzekit-workspace/`).

```json
{
  "mcpServers": {
    "adzekit-backbone": {
      "command": "adzekit-mcp-backbone",
      "env": { "ADZEKIT_SHED": "/Users/scott.mckean/Repos/adzekit-workspace" }
    }
  }
}
```

---

## Workflow

### Step 1 — Load today's context (one call)

```
backbone_get_today_context()
```

Returns:
- `date`: today's ISO date
- `today_note.exists`: whether today's daily note already exists
- `loops.overdue`: loops past their due date
- `loops.due_today`: loops due today
- `loops.upcoming_count`: total upcoming loops (for awareness)
- `loops.total_open`: total open loop count
- `active_projects`: slugs, titles, progress

**If `today_note.exists = true`**: the note already exists. Print a message:
```
Today's note already exists at daily/YYYY-MM-DD.md. Use `adzekit today` to open it.
```
Then stop — do not overwrite an existing daily note.

### Step 2 — Load yesterday's note

Compute yesterday's date. Read `{shed}/daily/YYYY-MM-DD.md` (the day before today).

If using MCP, use `backbone_get_week_notes()` and find yesterday's entry.
If using direct file read, read `{shed}/daily/{yesterday}.md`.

Extract from yesterday:
- **Carried intentions**: `[ ]` (undone) tasks from `## Morning: Intention`
- **Tomorrow items**: text from `## Evening: Reflection` → `**Tomorrow:**` section
- **Blocked items**: text from `## Evening: Reflection` → `**Blocked:**` section

If yesterday's note doesn't exist (weekend, travel), try the day before. Go back up to 3 days.

### Step 3 — Compose the proposed intentions

Build a ranked, de-duplicated list of proposed focus tasks from:

**Source 1 — Loops due today or overdue** (highest priority):
- Include all `loops.due_today` entries, formatted as:
  `- [ ] ({size}) [{due_date}] {loop title}  ← due today`
- Include all `loops.overdue` entries (up to 2), formatted as:
  `- [ ] ({size}) [{due_date}] {loop title}  ← OVERDUE`

**Source 2 — Yesterday's `Tomorrow:` items:**
- Format each as a new task line: `- [ ] {item}`
- Skip if already covered by a loop from Source 1 (fuzzy title match)

**Source 3 — Yesterday's uncompleted intentions:**
- Include any `[ ]` intentions from yesterday that don't appear in Source 1 or 2

**Ranking and capping:**
- Sort: overdue loops first → due today → tomorrow items → carried intentions
- Hard cap: max 5 total tasks (respects `max_daily_tasks` setting)
- If more than 5 candidates exist, include the top 5 by priority and note how many were
  deferred (e.g. `{N} additional items deferred — add them if capacity allows`)
- Size-weight the cap: a single `L` or `XL` loop counts as 2 slots

### Step 4 — Write the draft daily note

Call `backbone_write_draft('daily-YYYY-MM-DD.md', content)` with:

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

The `Energy:` and `Deep work:` fields are left blank for the human to fill in at day end.

### Step 5 — Print terminal summary

```
Daily Start — YYYY-MM-DD ({Day of Week})
  Proposed tasks: N (from N loops due, N carried, N tomorrow items)
  Overdue loops:  N (oldest: TITLE — N days overdue)
  Open loops:     N total
  Active projects: N
  Draft:          drafts/daily-YYYY-MM-DD.md

To use: mv drafts/daily-YYYY-MM-DD.md {shed}/daily/YYYY-MM-DD.md
```

---

## Intention Quality Guidelines

**Prefer specificity over vagueness:**
- `- [ ] (S) [2026-03-03] Kick off AER CMP Phase 0 onsite session` ← good
- `- [ ] Work on projects` ← bad

**For carried intentions, add context about why it didn't get done (if known):**
- If yesterday's blocked section mentioned it: append `  ← blocked: {reason}`
- Example: `- [ ] (M) Ship citco-columnmapping  ← blocked: waiting on TAR approval`

**Respect the WIP cap:** 5 tasks maximum. If today has 4+ hours of meetings (from calendar
context if available), cap at 3 tasks. Better to finish 3 than to plan 5 and feel behind.

**Energy-aware scheduling:** If yesterday's energy score was ≤ 2/5, open today's note with
a gentle note: `> Low energy day — consider 2 tasks max and one clear win.`

---

## Safety Rules

- NEVER write to `daily/` directly — output goes to `drafts/daily-YYYY-MM-DD.md` only
- NEVER overwrite an existing daily note — always check `today_note.exists` first
- Do NOT close loops or modify loop data — read only
- Do NOT add new loops — this is a read-then-draft operation
- Carried intentions are *suggestions* — the human edits before using

---

## MCP Fallback (if backbone MCP not running)

```python
# Step 1: Direct reads
import os, json
from datetime import date, timedelta

SHED = os.path.expanduser("~/Repos/adzekit-workspace")
today = date.today()
yesterday = today - timedelta(days=1)

# Read yesterday's note
note_path = f"{SHED}/daily/{yesterday.isoformat()}.md"

# Read open loops
loops_path = f"{SHED}/loops/open.md"
```

Then parse manually using the same logic described in the steps above.

ARGUMENTS: $ARGUMENTS
