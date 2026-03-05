# ASQ Alignment Audit

Cross-reference active Salesforce Approval Requests (ASQs) against the shed backbone to surface
gaps in project tracking, stale ARs, missing loops, and date/sizing mismatches. Writes a gap
report to `drafts/` and drafts project stubs for unmatched ARs.

## Prerequisites

- Salesforce CLI (`sf`) installed and authenticated
- Both AdzeKit MCP servers running: `adzekit-mcp-backbone`, `adzekit-mcp-gmail` (gmail optional)

---

## Workflow

### Step 1 — Authenticate Salesforce

```bash
SF_STATUS=$(sf org display --json 2>/dev/null | jq -r '.result.connectedStatus')
```

If not `Connected`:
```bash
sf org login web --instance-url=https://databricks.my.salesforce.com/ --set-default
```

Store the target org:
```bash
SF_TARGET_ORG=$(sf org display --json 2>/dev/null | jq -r '.result.username // empty')
```

### Step 2 — Pull active ARs from Salesforce

Fetch all ARs owned by Scott that are not terminal:
```bash
sf data query --target-org "$SF_TARGET_ORG" --json \
  -q "SELECT Id, Name, Status__c, Request_Type__c, Urgency__c,
             Support_Type__c, Start_Date__c, End_Date__c,
             Account__r.Name, Requestor__r.Name,
             Request_Description__c, Situation_Details__c,
             Hours_Consumed__c, Remaining_Hours_of_Investment__c,
             Total_Hours__c, ApprovalStatus__c, JIRA_link__c
      FROM ApprovalRequest__c
      WHERE OwnerId IN (SELECT Id FROM User WHERE Email = 'scott.mckean@databricks.com')
      AND Status__c NOT IN ('Complete', 'Closed', 'Relegated', 'Rejected')
      ORDER BY Urgency__c DESC, Start_Date__c ASC"
```

Parse the JSON result into a working list of ARs with fields:
`ar_number`, `status`, `urgency`, `account`, `start_date`, `end_date`,
`hours_consumed`, `hours_total`, `hours_remaining`, `description`, `situation`.

### Step 3 — Load shed context

Call all in parallel:
- `backbone_get_projects()` → active projects with slugs, progress, task counts
- `backbone_get_open_loops()` → all open loops with titles, sizes, dates, due dates
- `backbone_get_week_notes()` → current week's dailies (raw content for keyword search)
- `backbone_get_week_notes(PRIOR_WEEK)` → prior week's dailies

Build working context:
```
PROJECTS: [{slug, title, progress, total_tasks, done_tasks}]
LOOPS: [{title, size, date, due, status}]
DAILIES: [{date, raw_content}] — from both weeks
```

### Step 4 — Match ARs to projects

For each AR, attempt to match a project slug:

1. **Exact slug match** — normalize account name to slug form (lowercase, hyphenated) and check
   against project slugs. Examples:
   - "Alberta Energy Regulator" → look for slugs containing `aer`
   - "Ontario Teachers' Pension Plan" → look for slugs containing `otpp`
   - "Export Development Canada" → look for slugs containing `edc`

2. **Keyword search** — search project titles and raw content for the account name or fragments.
   Use `backbone_search(account_name, ["projects"])` for unresolved matches.

3. **Unmatched** — flag as MISSING. Collect these for stub generation in Step 6.

Build a mapping: `{ar_number: project_slug | null}`

### Step 5 — Run audit checks

For each AR, evaluate all checks and collect issues. Today's date is used as the reference.

#### a) Missing Project
- AR has no matched project slug → `[MISSING]`
- Severity: **high** — an active engagement with no tracking

#### b) Staleness & Date Checks
- AR `End_Date__c` is in the past AND status is still "In Progress" → `[OVERDUE]`
  - Suggested action: update AR status to Complete or extend end date
- AR is "In Progress" but matched project has no mentions in dailies from the last 14 days
  → `[STALE]`
  - Check by searching both weeks of dailies for the project slug or account name fragments
  - Suggested action: log activity or close out the AR
- AR `Start_Date__c` is in the future but project already has log entries → `[EARLY]` (info only)

#### c) Date & Sizing Mismatches
- AR `End_Date__c` is approaching (within 7 days) and project progress < 50% → `[AT RISK]`
- AR `Hours_Consumed__c` is 0 but dailies mention the project multiple times → `[HOURS UNLOGGED]`
  - Count daily mentions as a rough proxy; suggest updating Hours_Consumed__c
- AR `Total_Hours__c` is set but project has many open tasks relative to remaining hours → `[UNDERSIZED]`
- Open loops for this AR's project are all `(XS)` or `(S)` but AR urgency is `High` or `Critical`
  → `[SIZING MISMATCH]`

#### d) Loop & Daily Alignment
- AR is active but zero open loops reference its project slug or account keywords → `[NO LOOPS]`
  - Suggested action: create loops for the engagement
- Open loops reference a project slug whose AR is Complete/Closed → `[ORPHAN LOOP]`
  - Check against ALL ARs (including terminal ones) for this
- Recent dailies mention the account but no open loop exists for it → `[UNTRACKED WORK]`

### Step 6 — Draft project stubs for unmatched ARs

For each AR flagged as `[MISSING]`, generate a project stub and write it via:
```
backbone_write_draft("SLUG.md", content)
```

Derive the slug from the account name + a short engagement keyword from the AR description.
For example: AR for "Bruce Power" about document parsing → `brucepower-docparsing`.

**Stub format:**
```markdown
# Account Name — Engagement Title

#slug-tag

AR: AR-XXXXXXXXX | Status: In Progress | Urgency: Normal
Dates: YYYY-MM-DD → YYYY-MM-DD
Hours: X consumed / Y total

## Context

[Request_Description__c content, cleaned up]

[Situation_Details__c content, cleaned up]

## Log

```

Tell the user which stubs were created and that they should review and move to `projects/` to activate.

### Step 7 — Write audit report

Call `backbone_write_draft("asq-alignment-YYYY-MM-DD.md", content)` with today's date.

**Report format:**

```markdown
# ASQ Alignment Audit — YYYY-MM-DD

## Summary

| AR# | Account | Status | Urgency | Project | Issues |
|-----|---------|--------|---------|---------|--------|
| AR-000109889 | AER | In Progress | High | aer-compliance | — |
| AR-000105855 | Citco | In Progress | Normal | citco-columnmapping | OVERDUE |
| AR-000112316 | NOVA | In Progress | Normal | — | MISSING |

Active ARs: N · Matched: N · Issues found: N

---

## Issues

### [MISSING] No project file (N)

- **AR-000112316** (NOVA Chemicals) — no project file
  → Stub drafted: `drafts/new-project-nova-contractclass.md` — move to `projects/` to activate

### [OVERDUE] AR end date passed (N)

- **AR-000105855** (Citco) — end date 2026-02-28 passed, still In Progress
  → Update AR status to Complete, or extend End_Date__c if work continues
  ```bash
  sf data update record -s ApprovalRequest__c -i RECORD_ID -v "End_Date__c='2026-04-30'"
  ```

### [STALE] No activity in 14 days (N)

- **AR-000107197** (Bruce Power) — last daily mention: 2026-02-18
  → Log recent work or close out the AR if engagement ended

### [NO LOOPS] Active AR with no open loops (N)

- **AR-000108145** (Industrielle Alliance) — no loops reference #ia or #industrielle
  → Create loops:
  ```
  - [ ] (S) [YYYY-MM-DD] Follow up on #ia-snowflakemigration re: next steps
  ```

### [HOURS UNLOGGED] Salesforce hours don't match activity (N)

- **AR-000109761** (OTPP) — 0h consumed / 20h total, but 5 daily mentions found
  → Update Hours_Consumed__c in Salesforce
  ```bash
  sf data update record -s ApprovalRequest__c -i RECORD_ID -v "Hours_Consumed__c=8"
  ```

### [AT RISK] Approaching deadline with low progress (N)

- **AR-000107047** (EXO) — ends 2026-04-30, project at 20% (2/10 tasks)
  → Prioritize or request extension

### [SIZING MISMATCH] Loop sizes don't match AR urgency (N)

- **AR-000111552** (EDC) — High urgency but loops are all (XS)
  → Review if effort is properly scoped

### [ORPHAN LOOP] Loop for completed/closed AR (N)

- Loop: "Follow up on #nova-contractanalysis" — AR-000110152 is Complete
  → Close the loop or reassign to a new AR

### [UNTRACKED WORK] Daily mentions with no loop (N)

- Account "Altus Group" mentioned in 2026-03-03 daily but no open loop exists
  → Create a loop or link to existing AR

---

## Project Stubs Created

| File | Account | AR# |
|------|---------|-----|
| drafts/new-project-brucepower-docparsing.md | Bruce Power | AR-000107197 |
| drafts/new-project-ia-migration.md | Industrielle Alliance | AR-000108145 |

Move to `projects/` to activate tracking.

---

## Suggested SF Updates

Copy-paste ready `sf` commands for all updates identified above:

```bash
# AR-000105855 (Citco) — extend end date
sf data update record -s ApprovalRequest__c -i aEJ... -v "End_Date__c='2026-04-30'"

# AR-000109761 (OTPP) — log hours
sf data update record -s ApprovalRequest__c -i aEJ... -v "Hours_Consumed__c=8"
```

---
Run: YYYY-MM-DD HH:MM
```

### Step 8 — Terminal output

Print a compact summary:

```
ASQ Alignment Audit — YYYY-MM-DD

| AR# | Account | Status | Project | Issues |
|-----|---------|--------|---------|--------|
| AR-000109889 | AER | In Progress | aer-compliance | — |
| AR-000105855 | Citco | In Progress | citco-columnmapping | OVERDUE |
| AR-000107197 | Bruce Power | In Progress | — | MISSING, STALE |

Active: N  ·  Matched: N/N  ·  Issues: N  ·  Stubs created: N

Issues:
1. [MISSING] AR-000112316 (NOVA) — no project file → stub in drafts/
2. [OVERDUE] AR-000105855 (Citco) — end date 2026-02-28 passed
3. [STALE] AR-000107197 (Bruce Power) — no activity in 14 days
4. [NO LOOPS] AR-000108145 (iA) — no open loops
5. [HOURS] AR-000109761 (OTPP) — 0h consumed, 5 daily mentions
6. [ORPHAN] Loop "#nova-contractanalysis" — AR Complete
7. [SIZING] AR-000111552 (EDC) — High urgency, XS loops

Report: drafts/asq-alignment-YYYY-MM-DD.md
Stubs: drafts/new-project-brucepower-docparsing.md, drafts/new-project-ia-migration.md
```

Then print any suggested loop lines for ARs with `[NO LOOPS]`:
```
Suggested loops (copy to loops/open.md):

- [ ] (M) [YYYY-MM-DD] Continue #ia-migration Snowflake evaluation POC
- [ ] (S) [YYYY-MM-DD] Follow up on #brucepower-docparsing agent deployment
```

---

## Safety Rules

- NEVER send emails or modify Salesforce records automatically — suggest `sf` commands only
- NEVER write to backbone directories: loops/, projects/, daily/, knowledge/, reviews/
- Project stubs and audit reports go to `drafts/` only — human moves to `projects/`
- SF update commands are printed for copy-paste — human runs them
- If unsure about an AR ↔ project match, flag it as MISSING rather than guessing wrong

---

## Reference

- Salesforce object: `ApprovalRequest__c`
- `Name` field = AR number (auto-generated, e.g. `AR-000105855`)
- Status values: New, Unassigned, Assigned, Ready to Assign, In Progress, On Hold, Complete, Closed, Relegated, Draft, Delivered, Rejected
- Urgency (ASQ): Low, Normal, High, Critical
- Owner-based query (Resource__r.Email returns empty for Scott — use OwnerId subquery)

ARGUMENTS: $ARGUMENTS
