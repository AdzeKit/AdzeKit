# Inbox Zero Skill

Reach inbox zero by classifying, acting on, and summarizing up to 100 inbox emails. Stars and
labels REVIEW emails, outputs copy-paste-ready loops for ACTION emails, writes a triage report
to `drafts/`, and updates the email patterns memory file.

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
CUSTOMER HINTS: <project slugs from backbone_get_projects()>
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
  -H "Authorization: Bearer $TOKEN"

# Fetch metadata for all IDs
for ID in <ids>; do
  curl -s "https://gmail.googleapis.com/gmail/v1/users/me/messages/${ID}?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date" \
    -H "Authorization: Bearer $TOKEN"
done
```

For emails whose snippet suggests they are DIRECT, URGENT, or REVIEW, fetch the full body:
- MCP: `gmail_read_email(message_id)`
- API: `?format=full` then decode `payload.body.data` from base64

### Step 3 — Classify all emails

For each email, assign exactly one category. Apply context from Step 1. Use the temporal check
and grading rules below before assigning a final category.

**Temporal check — apply first:**
Before classifying, compare the email's Date header to today's date. If the email refers to a
specific event, meeting, deadline, or time-sensitive ask:
- If the referenced date/event is **in the past** → downgrade to **STALE** regardless of other signals
- If no specific deadline is mentioned → classify normally, but do not use time-keyword signals
  ("today", "deadline", etc.) to elevate to URGENT unless the email itself was sent today

**STALE** is not a final category — it maps to a special archive action (see Step 4).

| Category | When to use | Key signals |
|----------|-------------|-------------|
| **URGENT** | Active escalation or something genuinely blocked right now | Sender explicitly says something is broken/blocked/down today; executive sender with a direct ask; high confidence of immediate impact |
| **DIRECT** | Clear personal ask requiring a reply or decision | Your name in To, explicit question or request, external email with a genuine open ask |
| **REVIEW** | Pertinent information you should read but need not reply to | Industry news relevant to active projects; important internal announcements; customer signals; significant competitive or market intelligence |
| **CHATTER** | Internal discussion or FYI with no personal action | Mailing list, announcement, internal thread where you are CC'd but not asked anything |
| **NOTIFICATION** | Automated system email | GitHub, Jira, CI/CD, calendar invites (always — even from real people), Slack digests, newsletters from known services |
| **JUNK** | Marketing or unsubscribe-eligible | Bulk mail headers, prominent unsubscribe link, no personal relevance |

**Grading rules (prevent over-escalation):**
- Keyword signals ("urgent", "ASAP", "deadline", "today") only count if the email was sent **today**
  and the referenced deadline is **in the future**. Stale urgency keywords → ignore them.
- Customer elevation (external domain + project hint) → minimum DIRECT, but NOT URGENT unless
  there is also a clear active blocker or explicit escalation language.
- Calendar invites → always NOTIFICATION, regardless of sender. Never draft a reply to a calendar invite.
- Meeting invites for **past meetings** → STALE, not DIRECT. Calendar noise → NOTIFICATION.
- If genuinely unsure between URGENT and DIRECT, prefer DIRECT.
- If genuinely unsure between DIRECT and CHATTER, prefer DIRECT only if user is in To (not just CC).
- If genuinely unsure between REVIEW and CHATTER, prefer REVIEW only if the content is genuinely novel and relevant to active work — don't star noise.

Process in batches of ~20 emails at a time for manageable context. Keep a running tally.

### Step 4 — Apply Gmail actions

Apply actions in batches where possible.

**JUNK, NOTIFICATION, and CHATTER:**
- MCP: `gmail_archive_batch([list of IDs])` then `gmail_mark_read` for each
- API: `POST /messages/batchModify` with `removeLabelIds: ["INBOX", "UNREAD"]`

**REVIEW — MANDATORY: star + label every REVIEW email, no exceptions:**
1. `gmail_add_label(id, "AdzeKit/Review")` — tag it
2. `gmail_star(id)` — star it for visibility
3. `gmail_archive(id)` — remove from inbox

All three calls are REQUIRED for every REVIEW email. Do NOT skip starring or labeling.
API fallback: `POST /messages/{id}/modify` with `addLabelIds: ["STARRED", "<AdzeKit/Review label ID>"]` and `removeLabelIds: ["INBOX"]`
No draft — label + star are the signals.

**STALE** (past event/deadline, nothing actionable remaining):
- MCP: `gmail_archive_batch([list of IDs])` — archive silently, no label, no draft
- Note in the report under a "Stale / Past Events" section so the user can spot anything missed

**DIRECT:**
- MCP: `gmail_add_label(id, "AdzeKit/ActionRequired")` then `gmail_archive(id)`
- Draft a reply **only if** the email contains a clear, specific question or explicit request. Skip the draft for: status updates framed as questions, informational emails with a courtesy "let me know", FYIs with a soft ask, or anything that reading alone resolves.
- MCP: `gmail_draft_reply(id, <draft stub>)` — reply to sender only, never reply-all
- API: POST `/messages/{id}/modify` to add label; POST `/messages/{id}` to archive
**URGENT:**
- MCP: `gmail_add_label(id, "AdzeKit/Urgent")` — stays in inbox, do NOT archive
- MCP: `gmail_draft_reply(id, <draft stub>)` — reply to sender only, never reply-all
- API: POST `/messages/{id}/modify` to add label only

Draft reply stub format (reply to sender only — never CC or include other thread recipients):
```
Hi [Name],

[1-2 sentences acknowledging the email and indicating next step or timeline.]

Thanks,
[Your name]
```

### Step 5 — Write triage report

Call `backbone_write_draft(filename, content)` with filename `inbox-zero-YYYY-MM-DD-HHMM.md`
(use today's date and current time in 24h format, e.g. `inbox-zero-2026-03-02-0914.md`).

**Report format:**

```markdown
# Inbox Zero — YYYY-MM-DD HH:MM

## Summary

| Category          | Count | Action            |
|-------------------|-------|-------------------|
| Urgent            |     N | labeled + draft   |
| Direct            |     N | labeled (drafts: N, no-draft: N) |
| Review            |     N | starred           |
| Stale             |     N | archived silently |
| Chatter           |     N | archived          |
| Notifications     |     N | archived          |
| Junk              |     N | archived          |
| **Total**         | **N** |                   |

Drafts created: N  ·  Emails starred: N  ·  Emails archived: N

---

## Urgent (N)
- **[CUSTOMER]** From: sender@domain.com | Subject line here
  Signals: customer escalation, time keyword "today"
  → Draft reply: draft ID abc123
  → `- [ ] (S) [YYYY-MM-DD] Respond to #customer re: <topic>`

## Direct — Action Required (N)
- From: name@domain.com | Subject line here
  → Draft reply: draft ID ghi789
  → `- [ ] (M) [YYYY-MM-DD] Follow up with #customer re: <topic>`

## Review — Starred for Reading (N)
- From: name@domain.com | Subject line here
  Why: <1 sentence on why this is worth reading>

## Stale / Past Events (N)
> Archived silently. Listed here so you can confirm nothing was missed.

## Notifications (N)
> <1-3 sentence summary of what notifications arrived>

## Chatter (N)
> <1-2 sentence summary of internal discussions>

## Junk Archived (N)
(archived silently)

---
Actions: N processed · N archived · N labeled Urgent · N labeled ActionRequired · N starred for review · N drafts created
Run: YYYY-MM-DD HH:MM
```

Loop lines in Urgent and Direct sections are copy-paste ready for `loops/open.md`.

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
Inbox Zero complete — YYYY-MM-DD HH:MM

  Urgent        N   (drafts: N)
  Direct        N   (drafts: N, labeled only: N)
  Review        N   (starred)
  Stale         N   (archived silently)
  Chatter       N   (archived)
  Notifications N   (archived)
  Junk          N   (archived)
  ─────────────────────────────
  Total         N

  Archived:  N   Starred: N   Drafts: N

Report: drafts/inbox-zero-YYYY-MM-DD-HHMM.md
```

Then print the action queue as **loop-ready lines** that can be copied directly into `loops/open.md`.

**Generate one loop line for EVERY URGENT and DIRECT email** — no exceptions. Each email that
stays labeled (Urgent or ActionRequired) gets exactly one line.

Use the AdzeKit backbone loop format:
```
- [ ] (SIZE) [YYYY-MM-DD] Verb + description, embed #customer-slug in text
```

Rules:
- Date = today (the date the triage ran), NOT the email's send date
- Customer/project slug is embedded as a `#hashtag` in the description text
- No trailing punctuation, no extra metadata

Sizing guide:
- `(XS)` — single reply or quick decision, < 5 min
- `(S)` — short task, one interaction, < 30 min
- `(M)` — requires preparation or multiple steps, < 2 hours
- `(L)` — significant effort, review, or multi-day work

---

## Safety Rules

- NEVER send emails — draft only
- NEVER delete or trash emails — archive only
- NEVER write to backbone directories: loops/, projects/, daily/, knowledge/, reviews/
- NEVER reply-all — drafts go to the original sender only, no CC recipients
- NEVER draft a reply to a calendar invite — classify as NOTIFICATION and archive
- NEVER draft a reply unless there is a clear, specific ask requiring a personal response
- Proposed loops go in the triage report and terminal output only — human copies them to loops/open.md
- If unsure about a classification, prefer DIRECT over CHATTER (false positive is safer)
- If unsure about urgency, prefer URGENT over DIRECT for external emails

---

## MCP Configuration

Both `adzekit-mcp-backbone` and `adzekit-mcp-gmail` MCP servers must be running and configured
in `.claude/settings.json` with `ADZEKIT_SHED` pointing to your workspace directory.

ARGUMENTS: $ARGUMENTS
