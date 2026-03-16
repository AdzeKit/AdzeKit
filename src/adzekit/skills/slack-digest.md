# Slack Digest

A daily digest for Slack — surfaces DMs, technical discussions, and announcements
from priority channels and keyword searches. Reads `knowledge/` files to personalize
topic matching. Output is a concise (< 2 page) digest to `drafts/`. Read-only — never posts or reacts.

## Prerequisites

- Slack MCP (`mcp__slack__slack_read_api_call`) — Slack read access

---

## Shed Access

All backbone reads use the `Read` tool directly on shed files. Writes use `Write` to `{SHED}/drafts/`.

| Data | Path |
|------|------|
| Role context | `{SHED}/knowledge/role-context.md` |
| Knowledge files | `{SHED}/knowledge/*.md` (Glob, then Read) |
| Today's note | `{SHED}/daily/YYYY-MM-DD.md` |
| Open loops | `{SHED}/loops/open.md` |
| Draft output | `{SHED}/drafts/slack-digest-YYYY-MM-DD-HHMM.md` (Write tool) |

---

## Workflow

### Step 1 — Load interests

Read all in parallel:
- `{SHED}/knowledge/role-context.md` — priority channels list, skip channels
- Glob `{SHED}/knowledge/*.md` — discover all knowledge files, extract tags and topics
- `{SHED}/daily/{today}.md` + `{SHED}/loops/open.md` — today's context for the header line

Build an interest profile:
```
PRIORITY_CHANNELS: <from role-context.md>
SKIP_CHANNELS: <from role-context.md>
TOPICS: <merged from all knowledge/ file tags>
SEARCH_KEYWORDS: <derived from topics, batched for OR queries>
```

### Step 2 — Fetch Slack (since last read)

Use `mcp__slack__slack_read_api_call` for all API calls. All calls are read-only.

**Tier 1 — Priority channels (since last read):**

For each priority channel:
1. Find channel ID via `conversations.list` (paginate if needed, cache results)
2. `conversations.info(channel=ID)` → get `last_read` timestamp
3. `conversations.history(channel=ID, oldest=last_read, limit=50)` → unread messages
4. Fetch thread replies for threaded messages with 3+ replies or reactions
5. Resolve sender names via `users.info` (cache across channels)

**Tier 2 — Search (DMs + keyword matches):**

Scan via `search.messages`:
1. `"to:me"` — @mentions and DMs since last read
2. Interest keywords from knowledge/ file tags, batched with OR (e.g. `"mlflow OR feature-store OR automl"`)
3. `"announcement OR launch OR release"` — company happenings

### Step 3 — Classify & dedupe

Each message appears in exactly one section. Classification priority:

1. **Direct For You** — DMs + @mentions needing your response
2. **Technical Desk** — Threads matching knowledge/ topics
3. **Announcements** — Releases, launches, org-wide, anything relevant not in above

**Skip:** Bot messages (unless substantive), skip-list channels, social chatter, your own messages.

### Step 4 — Write digest

Use the `Write` tool to create `{SHED}/drafts/slack-digest-YYYY-MM-DD-HHMM.md`.

Format:

```markdown
# Slack Digest — YYYY-MM-DD

## Direct For You
- **@sender** in #channel — topic summary → *action verb* (reply / review / approve)
- ...

## Technical Desk
### Topic Name
- **#channel** — 1-2 sentence summary of thread (link if available)
- ...

### Another Topic
- ...

## Announcements
- **#channel** — brief description
- ...
```

**Target: < 2 pages.** Be ruthlessly concise.

### Step 5 — Terminal output

Print the digest directly. Print suggested loops for items needing follow-up:

```
Suggested loops (copy to loops/open.md):

- [ ] (S) [YYYY-MM-DD] Reply to @sender in #channel re: topic
```

---

## Safety Rules

- NEVER post Slack messages — all replies are suggestions in the digest only
- NEVER react to messages, mark as read, or modify any Slack state
- NEVER write to backbone directories — drafts/ only
- Read-only Slack access only
- If rate limited, back off and retry with smaller batches

ARGUMENTS: $ARGUMENTS
