# Loop Momentum Skill

Cross-reference every active loop against real evidence from connected systems — sent emails,
Slack messages, Jira tickets, and daily logs — to automatically detect loops that are
**already done** (you just forgot to check them off), loops that are **losing momentum**
(no activity in days), and loops that are **blocked silently** (you stopped working on them
without writing it down).

The human backbone stays sacred. This skill only *proposes* — it writes a momentum report
to `drafts/` with copy-paste-ready sweep lines and a velocity dashboard. You decide what
to close, escalate, or kill.

---

## Shed Access

All backbone reads use the `Read` tool directly on shed files. Writes use `Write` to `{SHED}/drafts/`.

| Data | Path |
|------|------|
| Active loops | `{SHED}/loops/active.md` |
| Archived loops | `{SHED}/loops/archive.md` (if exists) |
| Projects | `{SHED}/projects/*.md` (Glob, then Read each) |
| Daily notes (2 weeks) | `{SHED}/daily/YYYY-MM-DD.md` (Read each day) |
| Draft output | `{SHED}/drafts/loop-momentum-YYYY-MM-DD.md` (Write tool) |

## Gmail Access (for sent-mail evidence)

```bash
TOKEN=$(gcloud auth application-default print-access-token)
BASE="https://gmail.googleapis.com/gmail/v1/users/me"
# Search sent mail: GET $BASE/messages?q=in:sent+{keywords}+after:{date}&maxResults=5
```

## External Systems (use if available)

- Slack MCP (`mcp__slack__slack_read_api_call`) — search for messages you posted
- Jira MCP (`mcp__jira__jira_read_api_call`) — check ticket status for Jira keys in loop titles
- Confluence MCP — document/page evidence

---

## Workflow

### Step 1 — Load all active loops and project context

Read all in parallel:
- `{SHED}/loops/active.md` — all active loops with titles, sizes, dates, due dates
- Glob `{SHED}/projects/*.md`, then Read each — active projects
- `{SHED}/daily/YYYY-MM-DD.md` for each day in current and prior week (14 days of dailies)

Parse each loop into a working record:
```
LOOP: {title, size, created_date, due_date, who, age_days, project_slug_hint}
```

Extract `project_slug_hint` by scanning the loop title for `#hashtags` or known project keywords.

### Step 2 — Search for closure evidence

For each active loop, search connected systems for evidence that the work is done.

**a) Sent Gmail — "Did I already respond?"**
Search sent mail for keywords from the loop title + who:
```bash
# Via gcloud + curl
curl -s "$BASE/messages?q=in:sent+{who}+{keywords}+after:{date}&maxResults=5" \
  -H "Authorization: Bearer $TOKEN"
```
If a sent email matches with high confidence → `EVIDENCE: sent email, {date}, {subject}`

**b) Slack — "Did I already discuss this?"**
`search.messages(query="{keywords} from:me after:{loop_created_date}")`
Look for substantive messages (not just reactions).

**c) Jira — "Did the ticket close?"**
If the loop title contains a Jira key (e.g. `ES-12345`):
`jira_read_api_call(method="GET", path="/rest/api/3/issue/{key}?fields=status,resolution")`

**d) Daily logs — "Did I write that I finished this?"**
Search daily notes for loop keywords using Grep across `{SHED}/daily/`.
Scan `finished:` sections and `[x]` intention items.

**e) Project logs — "Did the project log capture this?"**
For loops with a matched project slug, read the project file's `## Log` section.

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

Use `Write` to create `{SHED}/drafts/loop-momentum-YYYY-MM-DD.md` with:
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

Works with reduced scope when connected systems aren't available:
- **No Gmail token** → skip sent-email evidence, rely on daily notes + Slack
- **No Slack MCP** → skip Slack evidence, rely on email + daily notes
- **No Jira MCP** → skip Jira evidence (Jira keys just get flagged)
- **Backbone only** → still useful: daily note analysis, age-based classification, velocity

The momentum score adjusts its denominator based on available evidence sources.

---

## Safety Rules

- NEVER modify loops/active.md — only propose changes in the report
- NEVER send emails or messages — only draft nudge suggestions
- NEVER write to backbone directories — drafts/ only
- Read-only access to all connected systems
- When evidence is ambiguous, prefer LIKELY DONE over DONE (human verifies)

ARGUMENTS: $ARGUMENTS
