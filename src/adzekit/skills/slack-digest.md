# Slack Daily Digest

A daily newspaper for Slack — surfaces what matters from priority channels, @mentions, and
technical discussions across the org. Reads `knowledge/` files to personalize topic matching.
Output is a concise (< 2 page) digest to `drafts/`. Read-only — never posts or reacts.

## Prerequisites

MCP servers must be running:
- `adzekit-mcp-backbone` — backbone read + drafts write
- Slack MCP — Slack read access

---

## Workflow

### Step 1 — Load interests

Call in parallel:
- `backbone_search("", ["knowledge"])` — discover all knowledge files, extract tags and topics
- `backbone_get_today_context()` — today's loops/meetings for the header line
- Read `knowledge/role-context.md` directly — priority channels list, technical interests

Build an interest profile:
```
PRIORITY CHANNELS: <from role-context.md>
SKIP CHANNELS: <from role-context.md>
TECHNICAL INTERESTS: <merged from role-context.md + tags from all knowledge/ files>
SEARCH KEYWORDS: <derived from technical interests, batched for OR queries>
```

### Step 2 — Fetch Slack (two tiers)

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

Call `backbone_write_draft("slack-digest-YYYY-MM-DD-HHMM.md", content)`.

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
