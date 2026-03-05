# Slack Daily Digest

Surface what matters from Slack DMs and channels, prioritized by role context. Fetches unread
messages, classifies by relevance, and outputs a structured digest with up to 10 action items
to `drafts/`. Read-only — never posts or reacts on Slack.

## Prerequisites

MCP servers must be running:
- `adzekit-mcp-backbone` — backbone read + drafts write
- Slack MCP (`mcp__slack__slack_read_api_call`) — Slack read access

---

## Workflow

### Step 1 — Load context

Call all in parallel:
- `backbone_get_today_context()` — today's note, active projects, open loops
- `backbone_search("", ["knowledge"])` or read `knowledge/role-context.md` directly — role context (customers, channels, keywords)
- `backbone_get_email_patterns()` — reuse customer domain knowledge

Build a working context block:
```
CUSTOMER ACCOUNTS: ovintiv, otpp, aer, sobeys, rogers, bruce power, citco, edc, co-operators, nova, exo
CUSTOMER KEYWORDS: <from role-context.md>
SPECIALTY KEYWORDS: <from role-context.md>
PRIORITY CHANNELS: <from role-context.md>
SKIP CHANNELS: <from role-context.md>
OPEN LOOPS WITH: <who values from open loops>
ACTIVE PROJECTS: <project slugs>
```

### Step 2 — Fetch Slack activity

Use `mcp__slack__slack_read_api_call` for all API calls. All calls are GET/read-only.

**a) Unread DMs:**
1. `conversations.list` with `types=im` — get all DM conversations
2. Filter for conversations with `unread_count > 0`
3. For each unread DM: `conversations.history` with `oldest=<last_read timestamp>` to fetch new messages
4. For each message, resolve the sender via `users.info` (cache user lookups)

**b) Channel mentions:**
1. `search.messages` with `query="to:me after:YESTERDAY"` — catches @mentions across all channels

**c) Priority channels:**
For each channel in role-context.md's watch list:
1. `conversations.list` with `types=public_channel` — find channel IDs (or use cached IDs)
2. `conversations.info` for each to check `unread_count`
3. If unread: `conversations.history` with `oldest=<last_read timestamp>`

**d) Customer keyword search:**
For each active customer name/project slug:
1. `search.messages` with `query="KEYWORD after:YESTERDAY"` — catches discussions about accounts even when not @mentioned
2. Batch keywords where possible (e.g. `"ovintiv OR otpp OR aer after:YESTERDAY"`)

### Step 3 — Classify messages

For each message/thread, assign exactly one category:

| Category | When | Priority |
|----------|------|----------|
| **CUSTOMER** | References an active customer/project from shed | 1 (highest) |
| **DIRECT ASK** | DM or @mention with a clear question/request | 2 |
| **BU-RELEVANT** | Canada BU discussion, regional announcement | 3 |
| **SPECIALTY** | ML/AI/GenAI/MLOps content matching specialty keywords | 4 |
| **FYI** | Interesting but no action needed | 5 |
| **NOISE** | Channel in skip list, bot messages, automated alerts | skip |

**Classification rules:**
- If a message appears in multiple fetches (DM + search), keep the highest-priority classification
- Deduplicate by message `ts` (timestamp) — Slack timestamps are unique per channel
- Bot messages (`subtype: bot_message`) → NOISE unless they reference a customer account
- Messages from skip-list channels → NOISE
- Customer keyword match + direct ask → CUSTOMER (not DIRECT ASK)
- If unsure between CUSTOMER and DIRECT ASK, prefer CUSTOMER
- If unsure between BU-RELEVANT and FYI, prefer BU-RELEVANT

### Step 4 — Select top 10 actions

From all non-NOISE messages, rank by:
1. Customer-specific items (match against active projects)
2. Direct asks requiring a response
3. Canada BU items
4. ML/AI specialty relevance
5. General FYI

Select up to 10 actions. Each action gets:
- **Source**: channel name or DM sender
- **Summary**: one-line description of what's being discussed
- **Action verb**: Reply, Read, Follow up, Join thread, Review, etc.
- **Link**: Slack message permalink if available (construct from channel + ts)

### Step 5 — Write digest draft

Call `backbone_write_draft("slack-digest-YYYY-MM-DD-HHMM.md", content)` with today's date and current time in 24h format.

**Report format:**

```markdown
# Slack Digest — YYYY-MM-DD HH:MM

## Action Items (N)

1. [CUSTOMER] #channel — @sender: summary of ask
   → Reply: suggested response or next step
2. [DIRECT] DM from @sender: summary
   → Follow up: what to do
3. [BU] #channel — summary
   → Read: why it matters
...

## Customer Activity (N threads)
- **#channel**: summary (customer tag)
- **DM from @sender**: summary (customer tag)

## BU & Specialty (N threads)
- **#channel**: summary (BU-RELEVANT or SPECIALTY tag)

## FYI (N)
> Brief summary of interesting-but-not-actionable items

## Skipped (N channels, M messages)
> Noise summary — bot messages, skip-list channels, automated alerts
```

### Step 6 — Terminal output

Print a compact summary followed by the action items:

```
Slack Digest — YYYY-MM-DD HH:MM

  Customer       N
  Direct Ask     N
  BU-Relevant    N
  Specialty      N
  FYI            N
  Noise          N   (skipped)
  ─────────────────────────────
  Total          N

Report: drafts/slack-digest-YYYY-MM-DD-HHMM.md
```

Then print the top 10 action items as copy-paste-ready text:

```
Action items:

1. [CUSTOMER] #channel — @sender: summary
   → Reply: suggested next step
2. [DIRECT] DM @sender: summary
   → Follow up: what to do
...
```

Then print suggested loop lines for any action items that need follow-up beyond a quick reply:

```
Suggested loops (copy to loops/open.md):

- [ ] (S) [YYYY-MM-DD] Reply to #Ovintiv thread in #canada-ai re: gateway config
- [ ] (M) [YYYY-MM-DD] Follow up with @colleague on #AER POC timeline
```

Sizing guide:
- `(XS)` — single reply or quick decision, < 5 min
- `(S)` — short task, one interaction, < 30 min
- `(M)` — requires preparation or multiple steps, < 2 hours
- `(L)` — significant effort, review, or multi-day work

---

## Safety Rules

- NEVER post Slack messages — all replies are suggestions in the digest only
- NEVER react to messages, mark as read, or modify any Slack state
- NEVER write to backbone directories — drafts/ only via `backbone_write_draft`
- Read-only Slack access: no `chat.postMessage`, no `reactions.add`, no `conversations.mark`
- Skip bot/app messages unless they reference a customer account
- If Slack API returns rate limit errors, back off and retry with smaller batches
- If a channel is inaccessible (not a member), skip it silently and note in the report

---

## MCP Configuration

Requires Slack MCP server configured in `.claude/settings.json`. The backbone MCP server
must also be running for context loading and draft writing.

ARGUMENTS: $ARGUMENTS
