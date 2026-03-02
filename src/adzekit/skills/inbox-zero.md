# Inbox Zero Skill

Reach inbox zero by classifying, acting on, and summarizing up to 100 inbox emails. Writes a
structured triage report to `drafts/` and updates the email patterns memory file. Never writes to
backbone directories (loops/, projects/, daily/).

## Prerequisites

Both AdzeKit MCP servers must be running and configured in `.claude/settings.json`:
- `adzekit-mcp-backbone` — backbone read + drafts write
- `adzekit-mcp-gmail` — Gmail read + archive + label + draft

If not using MCP, authenticate with: `TOKEN=$(gcloud auth application-default print-access-token)`
and use the Gmail API directly (see Step 2b below).

---

## Workflow

### Step 1 — Load context

Call all three in parallel:
- `backbone_get_projects()` → extract project slugs and titles as customer context hints
- `backbone_get_open_loops()` → extract who/titles as active customer context
- `backbone_get_email_patterns()` → load known junk senders, notification sources, customer domains, and notes

Build a working context block:
```
CUSTOMER HINTS: birchcliff, citco, ovintiv, exo, brucePower, aer, <project slugs>
OPEN LOOPS WITH: <who values from open loops>
KNOWN JUNK: <senders from email-patterns.md>
KNOWN NOTIFICATIONS: <senders from email-patterns.md>
CUSTOMER DOMAINS: <domains from email-patterns.md>
NOTES: <notes from email-patterns.md>
```

### Step 2 — Fetch inbox

**Via MCP (preferred):**
```
gmail_get_inbox(max_results=100)
```

**Via Gmail API (fallback if MCP not available):**
```bash
TOKEN=$(gcloud auth application-default print-access-token)
# Fetch 100 message IDs
curl -s "https://gmail.googleapis.com/gmail/v1/users/me/messages?q=in:inbox&maxResults=100" \
  -H "Authorization: Bearer $TOKEN" \
  -H "x-goog-user-project: gcp-sandbox-field-eng"

# Fetch metadata for all IDs
for ID in <ids>; do
  curl -s "https://gmail.googleapis.com/gmail/v1/users/me/messages/${ID}?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date" \
    -H "Authorization: Bearer $TOKEN" \
    -H "x-goog-user-project: gcp-sandbox-field-eng"
done
```

For emails whose snippet suggests they are DIRECT or URGENT, fetch the full body:
- MCP: `gmail_read_email(message_id)`
- API: `?format=full` then decode `payload.body.data` from base64

### Step 3 — Classify all emails

For each email, assign exactly one category using the table below. Apply the context from Step 1:
known junk/notification senders skip straight to their categories. Customer signals elevate an
email to minimum DIRECT.

| Category | When to use | Key signals |
|----------|-------------|-------------|
| **URGENT** | Customer escalation, time-critical, senior sender | External domain + customer project hint; words: "urgent", "ASAP", "blocked", "down", "today", "deadline"; sender is VP/Director/C-level (e.g. ali@databricks.com, CEO, exec); LLM judges high urgency |
| **DIRECT** | Addressed specifically to user, response needed | User's name in To/CC, clear ask, meeting invite requiring RSVP, external domain with customer context |
| **CHATTER** | Internal group discussion, no action required | Databricks mailing list, internal announcement, FYI thread, promotion request with no personal ask |
| **NOTIFICATION** | Automated system email | GitHub, Jira, CI/CD alerts, calendar invites (auto-generated), Slack digests, product newsletters from known services |
| **JUNK** | Marketing, newsletter, unsubscribe-eligible | Bulk mail headers, "unsubscribe" link prominent, no personal relevance |

**Customer elevation rule:** If the LLM judges an email as customer-related (sender from external
domain AND content relates to a project slug, customer name, or open loop) → minimum DIRECT,
even if it looks like a notification.

Process in batches of ~20 emails at a time for manageable context. Keep a running tally.

### Step 4 — Apply Gmail actions

Apply actions in batches where possible.

**JUNK and NOTIFICATION and CHATTER:**
- MCP: `gmail_archive_batch([list of IDs])` then `gmail_mark_read` for each (or batch if available)
- API: `POST /messages/batchModify` with `removeLabelIds: ["INBOX", "UNREAD"]`

**DIRECT:**
- MCP: `gmail_add_label(id, "AdzeKit/ActionRequired")` then `gmail_archive(id)`
- MCP: `gmail_draft_reply(id, <draft stub>)` — write a 2-3 sentence acknowledgement stub
- API: POST `/messages/{id}/modify` to add label; POST `/messages/{id}` to archive

**URGENT:**
- MCP: `gmail_add_label(id, "AdzeKit/Urgent")` — stays in inbox, do NOT archive
- MCP: `gmail_draft_reply(id, <draft stub>)` — write a responsive, appropriately urgent stub
- API: POST `/messages/{id}/modify` to add label only

Draft reply stub format:
```
Hi [Name],

[1-2 sentences acknowledging the email and indicating next step or timeline.]

Thanks,
Scott
```

### Step 5 — Write triage report

Call `backbone_write_draft(filename, content)` with filename `inbox-zero-YYYY-MM-DD.md`
(use today's date).

**Report format:**

```markdown
# Inbox Zero — YYYY-MM-DD

## Urgent (N)
- **[CUSTOMER]** From: sender@domain.com | Subject line here
  Signals: customer escalation, time keyword "today"
  → Draft reply: draft ID abc123
  → `- [ ] (S) [YYYY-MM-DD] Respond to <topic> #tag1 #tag2`

- From: ali@databricks.com | Subject line here
  Signals: senior sender (CEO)
  → Draft reply: draft ID def456
  → `- [ ] (S) [YYYY-MM-DD] Action re: <topic>`

## Direct — Action Required (N)
- From: name@domain.com | Subject line here
  → Draft reply: draft ID ghi789
  → `- [ ] (M) [YYYY-MM-DD] <action> #tag`

## Notifications (N)
> <1-3 sentence summary of what notifications arrived: which systems, what actions if any>
> Example: GitHub sent 2 PR review requests and 1 CI failure on adzekit. Jira updated 3 tickets.
> Calendar: 1 new invite (BrucePower Document Parsing, Mon Mar 2, 10:30am EST).

## Chatter (N)
> <1-2 sentence summary of what internal colleagues are discussing>
> Example: Colleagues are discussing the FGAC external engines private preview launch,
> promoting the Lakebase Autoscaling Deep Dive community event, and an ongoing
> "Selling Genie" strategy thread led by Alistair and Garrett.

## Junk Archived (N)
(archived silently)

---
Actions: N processed · N archived · N labeled Urgent · N labeled ActionRequired · N drafts created
Run: YYYY-MM-DD HH:MM
```

Proposed loop lines (in Urgent and Direct sections) are copy-paste ready for `loops/open.md`.

### Step 6 — Update email patterns memory

Call `backbone_update_email_patterns(...)` with any NEW patterns learned from this run:
- `new_junk_senders`: senders confirmed as junk this run (not already in memory)
- `new_notification_sources`: automated senders newly identified
- `new_customer_domains`: external domains matched to customer projects
- `notes`: any learned classification rules worth remembering (e.g. recurring threads)

Only add entries that aren't already in the memory file. Don't re-add known senders.

---

## Output Summary

Print to terminal after completing:
```
Inbox Zero complete — YYYY-MM-DD
  Processed: N emails
  Archived:  N (junk: N, notification: N, chatter: N)
  Labeled:   N urgent, N action-required
  Drafts:    N created
  Report:    drafts/inbox-zero-YYYY-MM-DD.md
```

---

## Safety Rules

- NEVER send emails — draft only
- NEVER delete or trash emails — archive only
- NEVER write to backbone directories: loops/, projects/, daily/, knowledge/, reviews/
- Proposed loops go in the triage report only — human copies them to loops/open.md
- If unsure about a classification, prefer DIRECT over CHATTER (false positive is safer)
- If unsure about urgency, prefer URGENT over DIRECT for external/customer emails

---

## MCP Configuration

Add to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "adzekit-backbone": {
      "command": "adzekit-mcp-backbone",
      "env": {
        "ADZEKIT_SHED": "/Users/<you>/Repos/adzekit-workspace"
      }
    },
    "adzekit-gmail": {
      "command": "adzekit-mcp-gmail"
    }
  }
}
```

Restart Claude Code after adding MCP servers to pick up the new tools.

ARGUMENTS: $ARGUMENTS
