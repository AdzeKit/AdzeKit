# Loop Momentum Skill

Cross-reference every open loop against real evidence from connected systems — sent emails,
Slack messages, Jira tickets, and daily logs — to automatically detect loops that are
**already done** (you just forgot to check them off), loops that are **losing momentum**
(no activity in days), and loops that are **blocked silently** (you stopped working on them
without writing it down).

The human backbone stays sacred. This skill only *proposes* — it writes a momentum report
to `drafts/` with copy-paste-ready sweep lines and a velocity dashboard. You decide what
to close, escalate, or kill.

## Why this exists

The hardest part of any loop system isn't adding loops — it's closing them. Most people's
open loop lists grow monotonically because the friction of checking things off exceeds the
friction of ignoring them. Meanwhile, the evidence that a loop is *done* already exists
somewhere: you sent the email, you posted in Slack, the Jira ticket moved to Done. This
skill bridges the gap between your analog backbone and your digital exhaust.

---

## Prerequisites

MCP servers running:
- `adzekit-mcp-backbone` — backbone read + drafts write
- `adzekit-mcp-gmail` — Gmail read (sent mail search)
- Slack MCP — Slack read access

Optional:
- Jira MCP — Jira ticket status lookup
- Confluence MCP — document/page evidence

---

## Workflow

### Step 1 — Load all open loops and project context

Call in parallel:
- `backbone_get_open_loops()` → all open loops
- `backbone_get_projects()` → active projects
- `backbone_get_week_notes()` → current week's dailies
- `backbone_get_week_notes(PRIOR_WEEK)` → prior week's dailies

### Step 2 — Search for closure evidence

For each open loop, search connected systems for evidence that the work is done.

**Evidence sources:**

- **Sent Gmail** — sent emails matching loop keywords + recipient
- **Slack** — messages you posted matching loop topic
- **Jira** — ticket status for any Jira keys in the loop title
- **Daily logs** — finished sections and completed intentions
- **Project logs** — dated entries mentioning loop keywords

**Confidence scoring:**
- `HIGH` — Sent email to the right person, or Jira ticket resolved
- `MEDIUM` — Slack message with relevant content, or daily note finished entry
- `LOW` — Keyword match only, indirect evidence

### Step 3 — Classify momentum

| State | Criteria |
|-------|----------|
| **DONE** | HIGH confidence evidence of closure |
| **LIKELY DONE** | MEDIUM confidence evidence |
| **ACTIVE** | Recent work (last 3 days) but not closed |
| **COOLING** | Last evidence 4-7 days old |
| **STALE** | No evidence 7+ days, loop age > 7 days |
| **OVERDUE** | Past due date with no evidence |
| **FRESH** | Created < 3 days ago |

### Step 4 — Compute velocity metrics

- Loops opened/closed this week vs. last week
- Net change (accumulating or clearing?)
- Momentum score: `(loops_with_recent_evidence / total_open) * 100`
- Average loop age, oldest loop, WIP pressure

### Step 5 — Write momentum report

Write to `drafts/loop-momentum-YYYY-MM-DD.md` with:
- Dashboard table with all metrics
- Ready-to-sweep list with evidence
- Verify-and-sweep list (medium confidence)
- Stale loops requiring decisions
- Overdue loops requiring immediate action
- Suggested nudge drafts for stale loops involving other people

### Step 6 — Terminal output

Print momentum dashboard, ready-to-sweep items, and items needing attention.

---

## Degraded Mode

Works with reduced scope when connected systems aren't available. The momentum score
adjusts based on available evidence sources.

---

## Safety Rules

- NEVER modify loops/open.md — only propose changes in the report
- NEVER send emails or messages — only draft nudge suggestions
- NEVER write to backbone directories — drafts/ only
- Read-only access to all connected systems
- When evidence is ambiguous, prefer LIKELY DONE over DONE (human verifies)

ARGUMENTS: $ARGUMENTS
