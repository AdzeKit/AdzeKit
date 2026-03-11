# Slack Daily Digest

A daily newspaper for Slack — surfaces what matters from priority channels, @mentions, and
technical discussions across the org. Reads `knowledge/` files to personalize topic matching.
Output is a concise (< 2 page) digest to `drafts/`. Read-only — never posts or reacts.

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
| Active loops | `{SHED}/loops/active.md` |
| Draft output | `{SHED}/drafts/slack-digest-YYYY-MM-DD-HHMM.md` (Write tool) |

---

## Workflow

### Step 1 — Load interests

Read all in parallel:
- `{SHED}/knowledge/role-context.md` — priority channels list, technical interests
- Glob `{SHED}/knowledge/*.md` — discover all knowledge files, extract tags and topics
- `{SHED}/daily/{today}.md` + `{SHED}/loops/active.md` — today's context for the header line

Build an interest profile:
```
PRIORITY CHANNELS: <from role-context.md>
SKIP CHANNELS: <from role-context.md>
TECHNICAL INTERESTS: <merged from role-context.md + tags from all knowledge/ files>
SEARCH KEYWORDS: <derived from technical interests, batched for OR queries>
```

### Step 2 — Fetch Slack (two tiers)

Use `mcp__slack__slack_read_api_call` for all API calls. All calls are read-only.

**Tier 1 — Priority channels (detailed):**

For each priority channel:
1. Find channel ID via `conversations.list`
2. `conversations.info(channel=ID)` → get `last_read` timestamp
3. `conversations.history(channel=ID, oldest=last_read, limit=50)` → unread messages
4. Fetch thread replies for threaded messages
5. Resolve sender names via `users.info` (cache across channels)
6. Summarize each thread/conversation

**Tier 2 — Broader Slack (summary only):**

Scan via `search.messages`:
1. `"to:me after:YESTERDAY"` — @mentions and DMs
2. Interest keywords from knowledge/ files, batched with OR
3. `"announcement OR launch OR release after:YESTERDAY"` — company happenings

One-line summaries only, grouped by section.

### Step 3 — Organize into sections

| Section | Source | Treatment |
|---------|--------|-----------|
| **Front Page** | Priority channel threads | 2-3 sentence summary per thread |
| **Direct to You** | DMs + @mentions | One-line + action verb |
| **Technical Desk** | Messages matching knowledge/ topics | Grouped by topic, 1-2 sentences |
| **Around the Org** | Non-priority channel activity | 2-3 bullet summary |
| **Releases & Announcements** | Product releases, launches | Brief list |

**Skip:** Bot messages (unless substantive), skip-list channels, social chatter, your own messages.

### Step 4 — Write digest

Use the `Write` tool to create `{SHED}/drafts/slack-digest-YYYY-MM-DD-HHMM.md`.

**Target: < 2 pages.** Be ruthlessly concise.

### Step 5 — Terminal output

Print the digest directly. Print suggested loops for items needing follow-up:

```
Suggested loops (copy to loops/active.md):

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
