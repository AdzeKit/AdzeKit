# ASQ Alignment Audit

Cross-reference active Salesforce Approval Requests (ASQs) against the shed backbone to surface
gaps in project tracking, stale ARs, missing loops, and date/sizing mismatches. Writes a gap
report to `drafts/` and drafts project stubs for unmatched ARs.

## Prerequisites

- Salesforce CLI (`sf`) installed and authenticated
- `adzekit-mcp-backbone` MCP server running

---

## Workflow

### Step 1 — Authenticate Salesforce

```bash
SF_STATUS=$(sf org display --json 2>/dev/null | jq -r '.result.connectedStatus')
```

If not `Connected`:
```bash
sf org login web --set-default
```

### Step 2 — Pull active ARs from Salesforce

Determine your Salesforce email from `sf org display --json`.

Fetch all ARs you own that are not terminal:
```bash
sf data query --target-org "$SF_TARGET_ORG" --json \
  -q "SELECT Id, Name, Status__c, Request_Type__c, Urgency__c,
             Support_Type__c, Start_Date__c, End_Date__c,
             Account__r.Name, Requestor__r.Name,
             Request_Description__c, Situation_Details__c,
             Hours_Consumed__c, Remaining_Hours_of_Investment__c,
             Total_Hours__c, ApprovalStatus__c, JIRA_link__c
      FROM ApprovalRequest__c
      WHERE OwnerId IN (SELECT Id FROM User WHERE Email = '$USER_EMAIL')
      AND Status__c NOT IN ('Complete', 'Closed', 'Relegated', 'Rejected')
      ORDER BY Urgency__c DESC, Start_Date__c ASC"
```

### Step 3 — Load shed context

Call all in parallel:
- `backbone_get_projects()` → active projects with slugs, progress, task counts
- `backbone_get_open_loops()` → all open loops
- `backbone_get_week_notes()` → current week's dailies
- `backbone_get_week_notes(PRIOR_WEEK)` → prior week's dailies

### Step 4 — Match ARs to projects

For each AR, attempt to match a project slug:
1. **Exact slug match** — normalize account name to slug form and check project slugs
2. **Keyword search** — use `backbone_search(account_name, ["projects"])`
3. **Unmatched** — flag as MISSING for stub generation

### Step 5 — Run audit checks

For each AR, evaluate:

- **[MISSING]** — no matched project slug (high severity)
- **[OVERDUE]** — end date passed, still "In Progress"
- **[STALE]** — no daily mentions in 14 days
- **[AT RISK]** — deadline within 7 days, progress < 50%
- **[HOURS UNLOGGED]** — 0h consumed but daily mentions found
- **[UNDERSIZED]** — many open tasks relative to remaining hours
- **[SIZING MISMATCH]** — loop sizes don't match AR urgency
- **[NO LOOPS]** — active AR with zero open loops
- **[ORPHAN LOOP]** — loop references a completed/closed AR
- **[UNTRACKED WORK]** — daily mentions with no loop

### Step 6 — Draft project stubs for unmatched ARs

For each `[MISSING]` AR, generate a stub via `backbone_write_draft("SLUG.md", content)`.

### Step 7 — Write audit report

Call `backbone_write_draft("asq-alignment-YYYY-MM-DD.md", content)` with summary table,
detailed issues, project stubs created, and copy-paste `sf` update commands.

### Step 8 — Terminal output

Print compact summary with AR table, issue list, and suggested loop lines.

---

## Safety Rules

- NEVER modify Salesforce records automatically — suggest `sf` commands only
- NEVER write to backbone directories: loops/, projects/, daily/, knowledge/, reviews/
- Project stubs and reports go to `drafts/` only — human moves to `projects/`
- If unsure about an AR-to-project match, flag as MISSING rather than guessing wrong

---

## Reference

- Salesforce object: `ApprovalRequest__c`
- `Name` field = AR number (auto-generated, e.g. `AR-000105855`)
- Status values: New, Unassigned, Assigned, Ready to Assign, In Progress, On Hold, Complete, Closed, Relegated, Draft, Delivered, Rejected
- Urgency: Low, Normal, High, Critical
- Use OwnerId subquery to find your ARs

ARGUMENTS: $ARGUMENTS
