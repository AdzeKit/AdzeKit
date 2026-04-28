# Inbox Zero Skill

Reach inbox zero by classifying, acting on, and summarizing up to 100 inbox emails. Stars and
labels REVIEW emails, outputs copy-paste-ready loops for ACTION emails, and writes a triage report
to `drafts/`.

## Prerequisites

- `gcloud auth application-default print-access-token` must return a valid token
- Shed directory available (ADZEKIT_SHED env var or default `~/adzekit`)

---

## Shed Access

All backbone reads use the `Read` tool directly on shed files. All writes go to `{SHED}/drafts/`
using the `Write` tool.

| Data | Path |
|------|------|
| Active loops | `{SHED}/loops/active.md` |
| Projects | `{SHED}/projects/*.md` (Glob, then Read each) |
| Draft output | `{SHED}/drafts/{filename}` (Write tool) |

## Gmail Access

All Gmail operations use `gcloud` + `curl` via Bash. Obtain a token once per run:

```bash
TOKEN=$(gcloud auth application-default print-access-token)
BASE="https://gmail.googleapis.com/gmail/v1/users/me"
```

Use Python scripts via Bash for batch operations (concurrent requests with urllib).

| Operation | Method |
|-----------|--------|
| List inbox | `GET $BASE/messages?q=in:inbox&maxResults=100` |
| Get metadata | `GET $BASE/messages/{id}?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date&metadataHeaders=To&metadataHeaders=Cc` |
| Get full body | `GET $BASE/messages/{id}?format=full` (decode payload body from base64url) |
| Archive | `POST $BASE/messages/{id}/modify` body: `{"removeLabelIds":["INBOX"]}` |
| Mark read | `POST $BASE/messages/{id}/modify` body: `{"removeLabelIds":["UNREAD"]}` |
| Star | `POST $BASE/messages/{id}/modify` body: `{"addLabelIds":["STARRED"]}` |
| Add label | `POST $BASE/messages/{id}/modify` body: `{"addLabelIds":["LABEL_ID"]}` |
| Batch modify | `POST $BASE/messages/batchModify` body: `{"ids":[...],"addLabelIds":[...],"removeLabelIds":[...]}` |
| List labels | `GET $BASE/labels` (cache label IDs on first lookup) |
| Create draft | `POST $BASE/drafts` body: `{"message":{"raw":"BASE64","threadId":"THREAD_ID"}}` |

---

## Workflow

### Step 1 — Load context

Read all in parallel:
- Glob `{SHED}/projects/*.md` (skip `archive/` and `backlog/` subdirs), then Read each active project file
- Read `{SHED}/loops/active.md`

**From project files**, build a CUSTOMER TABLE. For each project file, extract:
- **slug** — from filename (e.g., `aer-compliance`)
- **customer org** — from the title or Context section
- **domain(s)** — scan Context and Log for `@domain.com` patterns; extract the external domain(s)
- **key contacts** — names and emails mentioned in the Log
- **Scott's role** — primary SA (To:) or supporting/CC-only — look for language like "Scott is CC only", "Scott appears CC only", or absence of Scott being directly named in customer-facing actions

**From `loops/active.md`**, note which #slugs have open loops — these are hot accounts where email is more likely DIRECT.

Build a working context block:
```
CUSTOMER TABLE:
| slug | org | domain(s) | contacts | Scott's role |
|------|-----|-----------|----------|--------------|
| aer-compliance | AER | aer.ca | Mouhannad Oweis, Harvinder Sohi | primary |
...

OPEN LOOPS (hot accounts): #aer-compliance, #otpp-vectorsearch, ...
```

### Step 2 — Fetch inbox

Use a Python script via Bash to fetch all inbox messages efficiently:

```python
# Run via Bash tool
import urllib.request, json, subprocess, base64

token = subprocess.run(["gcloud", "auth", "application-default", "print-access-token"],
                       capture_output=True, text=True).stdout.strip()
base = "https://gmail.googleapis.com/gmail/v1/users/me"
headers = {"Authorization": f"Bearer {token}", "x-goog-user-project": "gcp-sandbox-field-eng"}

# 1. Get message IDs
req = urllib.request.Request(f"{base}/messages?q=in:inbox&maxResults=100", headers=headers)
ids = [m["id"] for m in json.loads(urllib.request.urlopen(req).read()).get("messages", [])]

# 2. Fetch metadata for all IDs
for mid in ids:
    url = f"{base}/messages/{mid}?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date&metadataHeaders=To&metadataHeaders=Cc"
    req = urllib.request.Request(url, headers=headers)
    m = json.loads(urllib.request.urlopen(req).read())
    hdrs = {h["name"]: h["value"] for h in m.get("payload", {}).get("headers", [])}
    print(json.dumps({"id": m["id"], "from": hdrs.get("From",""), "to": hdrs.get("To",""),
                       "cc": hdrs.get("Cc",""), "subject": hdrs.get("Subject",""),
                       "date": hdrs.get("Date",""), "snippet": m.get("snippet",""),
                       "labels": m.get("labelIds",[]), "threadId": m.get("threadId","")}))
```

For emails whose snippet suggests they are DIRECT, URGENT, or REVIEW, fetch the full body
using `?format=full` and decode `payload.body.data` or `payload.parts[].body.data` from base64url.

### Step 3 — Classify all emails

For each email, assign exactly one category. Cross-reference sender domain against the CUSTOMER
TABLE built in Step 1. Apply temporal and grading rules below before assigning a final category.

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
| **REVIEW** | Pertinent information you should read but need not reply to | Industry news relevant to active projects; important internal announcements; customer signals; significant competitive intelligence |
| **CHATTER** | Internal discussion or FYI with no personal action | Mailing list, announcement, internal thread where you are CC'd but not asked anything |
| **NOTIFICATION** | Automated system email | GitHub, Jira, CI/CD, calendar invites (always — even from real people), Slack digests, newsletters from known services |
| **JUNK** | Marketing or unsubscribe-eligible | Bulk mail headers, prominent unsubscribe link, no personal relevance |

**Grading rules (prevent over-escalation):**
- Keyword signals ("urgent", "ASAP", "deadline", "today") only count if the email was sent **today**
  and the referenced deadline is **in the future**. Stale urgency keywords → ignore them.
- **Customer domain match** (sender domain in CUSTOMER TABLE) → minimum DIRECT, but NOT URGENT
  unless there is also a clear active blocker or explicit escalation language.
  - EXCEPTION: if Scott's role for that project is CC-only, prefer CHATTER unless Scott is
    explicitly addressed or in the To: field.
- Calendar invites → always NOTIFICATION, regardless of sender. Never draft a reply to a calendar invite.
- Meeting invites for **past meetings** → STALE, not DIRECT. Calendar noise → NOTIFICATION.
- If genuinely unsure between URGENT and DIRECT, prefer DIRECT.
- If genuinely unsure between DIRECT and CHATTER, prefer DIRECT only if user is in To (not just CC).
- If genuinely unsure between REVIEW and CHATTER, prefer REVIEW only if genuinely novel and relevant.

**Sender-specific elevation rules (baked in):**
- `christopher.chalcraft@databricks.com` with Scott in To → DIRECT (AE who delegates ASQs)
- `rob.signoretti@databricks.com` with AER/WCB customer content → DIRECT
- `rowan.sciban@databricks.com` with NOVA customer content → DIRECT
- `noreply@microsoft.com` (Teams) with customer name or project content in snippet → DIRECT
- `equity.admin@databricks.com` → DIRECT (RSU/equity grant, action required)
- `dse@camail.docusign.net` or any DocuSign sender → DIRECT (signature required)
- `notifications@mail.morganstanleyatwork.com` with ACTION REQUIRED → DIRECT
- `sfdc.user@databricks.com` where Scott is personally mentioned → DIRECT
- `noreply.ca@mail.egencia.ca` → NOTIFICATION (booking confirmations)
- `no-reply@greenhouse.io` → NOTIFICATION (STALE if event date is past)
- `azure-noreply@microsoft.com` PAT expiry within 7 days → URGENT

Process in batches of ~20 emails at a time for manageable context. Keep a running tally.

### Step 4 — Apply Gmail actions

Cache label IDs from `GET $BASE/labels` first. Known labels:
- `Label_2` = AdzeKit/ActionRequired
- `Label_3` = AdzeKit/Urgent
- `Label_4` = AdzeKit/Review

Use batch operations where possible.

**JUNK, NOTIFICATION, and CHATTER:**
```bash
curl -s -X POST "$BASE/messages/batchModify" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"ids":["ID1","ID2",...],"removeLabelIds":["INBOX","UNREAD"]}'
```

**REVIEW — MANDATORY: star + label every REVIEW email, no exceptions:**
Combine into one modify call per message:
```bash
curl -s -X POST "$BASE/messages/{id}/modify" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"addLabelIds":["STARRED","Label_4"],"removeLabelIds":["INBOX"]}'
```

**STALE** — archive silently, no label, no draft:
```bash
# Batch with JUNK/NOTIFICATION/CHATTER
```

**DIRECT:**
- Add ActionRequired label + archive: `{"addLabelIds":["Label_2"],"removeLabelIds":["INBOX"]}`
- Draft a reply **only if** the email contains a clear, specific ask. Skip for status updates,
  courtesy "let me know", FYIs with a soft ask, or anything that reading alone resolves.

**URGENT:**
- Add Urgent label, do NOT archive: `{"addLabelIds":["Label_3"]}`
- Draft a reply.

**Draft reply creation** — build RFC 2822 message in Python:
```python
import base64, email.message
msg = email.message.EmailMessage()
msg["To"] = original_sender  # reply to sender only, never reply-all
msg["Subject"] = f"Re: {original_subject}"
msg["In-Reply-To"] = original_message_id_header
msg["References"] = original_message_id_header
msg.set_content(body_text)
raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
# POST to $BASE/drafts with {"message": {"raw": raw, "threadId": thread_id}}
```

Draft reply stub format:
```
Hi [Name],

[1-2 sentences acknowledging the email and indicating next step or timeline.]

Thanks,
[Your name]
```

### Step 5 — Write triage report

Use the `Write` tool to create `{SHED}/drafts/inbox-zero-YYYY-MM-DD-HHMM.md`.

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

Then print the action queue as **loop-ready lines** for `loops/active.md`.

**Generate one loop line for EVERY URGENT and DIRECT email** — no exceptions.
```
- [ ] (SIZE) [YYYY-MM-DD] Verb + description, embed #customer-slug in text
```

Rules:
- Date = today (triage date), NOT email send date
- Customer/project slug embedded as `#hashtag` in description
- No trailing punctuation, no extra metadata

Sizing: `(XS)` < 5min, `(S)` < 30min, `(M)` < 2hr, `(L)` significant effort.

---

## Safety Rules

- NEVER send emails — draft only
- NEVER delete or trash emails — archive only
- NEVER write to backbone directories: loops/, projects/, daily/, knowledge/, reviews/
- NEVER reply-all — drafts go to the original sender only, no CC recipients
- NEVER draft a reply to a calendar invite — classify as NOTIFICATION and archive
- NEVER draft a reply unless there is a clear, specific ask requiring a personal response
- Proposed loops go in the triage report and terminal output only — human copies them
- If unsure about classification, prefer DIRECT over CHATTER (false positive is safer)
- If unsure about urgency, prefer URGENT over DIRECT for external emails

ARGUMENTS: $ARGUMENTS
