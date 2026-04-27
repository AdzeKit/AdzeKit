# Slack

Single-pass Slack sweep: daily digest + evergreen knowledge extraction + unread action
items. Replaces `slack-digest` and `slack-knowledge` with one command.

**Three outputs, one fetch cycle:**

| Output | Purpose | Path |
|--------|---------|------|
| Terminal digest | What happened today — read and move on | stdout |
| Knowledge patch | Evergreen facts to promote into `knowledge/` | `{SHED}/drafts/knowledge-patch-YYYY-MM-DD.md` |
| Per-file drafts | Ready-to-promote knowledge files | `{SHED}/drafts/knowledge/<slug>.md` |

## Prerequisites

- Slack MCP (`mcp__slack__slack_read_api_call`) — read-only access

---

## Shed Access

All backbone reads use the `Read` tool directly. Writes go to `{SHED}/drafts/` only.

| Data | Path |
|------|------|
| Role context | `{SHED}/knowledge/role-context.md` |
| Knowledge files | `{SHED}/knowledge/*.md` (Glob, then Read) |
| Today's note | `{SHED}/daily/YYYY-MM-DD.md` |
| Open loops | `{SHED}/loops/active.md` |
| Watermark | `{SHED}/drafts/slack-watermark.md` |
| Knowledge patch | `{SHED}/drafts/knowledge-patch-YYYY-MM-DD.md` |
| Per-file drafts | `{SHED}/drafts/knowledge/<slug>.md` |

---

## Arguments

Parse `$ARGUMENTS` for optional controls:

- **Time window**: `1d` (default), `3d`, `1w`, `2w`, or ISO date like `2026-04-01`
- **Channel filter**: `channel:<name>` — scope to a single channel
- **Mode**: `digest` (digest only, skip knowledge), `knowledge` (knowledge only, skip digest), omit for both
- **Full rescan**: `full` — ignore watermark

Examples: `/slack`, `/slack 3d`, `/slack channel:ml-sme`, `/slack 1w knowledge`

---

## Workflow

### Step 1 — Load context

Read all in parallel:

1. `{SHED}/knowledge/role-context.md` — priority channels, skip channels, interests
2. Glob `{SHED}/knowledge/*.md` — read each, extract slug, title (`# ` heading), tags (`#kebab-case` tokens), first-paragraph summary
3. `{SHED}/daily/{today}.md` + `{SHED}/loops/active.md` — today's context
4. `{SHED}/drafts/slack-watermark.md` — if exists, parse `channel_id: timestamp` pairs

Build internal indices:

```
PRIORITY_CHANNELS: [from role-context.md]
SKIP_CHANNELS: [from role-context.md]
TOPICS: [merged tags from all knowledge/ files]
SEARCH_KEYWORDS: [derived from topics, batched for OR queries]
KNOWLEDGE_INDEX: {
  "machine-learning.md": {title, tags, summary},
  ...
}
WINDOW_START: max(watermark, now - time_window)
```

### Step 2 — Fetch Slack

Use `mcp__slack__slack_read_api_call` for all calls. **All calls are read-only.**

**2a — Priority channels (unread messages):**

For each channel in PRIORITY_CHANNELS (skip if `channel:` argument excludes it):

1. Resolve channel ID via `conversations.list` (paginate if needed, cache results)
2. `conversations.info(channel=ID)` → get `last_read` timestamp
3. `conversations.history(channel=ID, oldest=WINDOW_START, limit=200)` → messages
4. For threaded messages with 2+ replies or 2+ reactions: fetch full thread via `conversations.replies`
5. Resolve sender names via `users.info` (batch, cache across channels)
6. Tag each message: `is_unread = (ts > last_read)`

**2b — Search (DMs + keyword matches):**

Scan via `search.messages`:

1. `"to:me"` — @mentions and DMs in the window
2. Interest keywords batched with OR: `"mlflow OR feature-store OR automl"` etc.
3. `"announcement OR launch OR release"` — company happenings

**Rate limiting:** If any call returns a rate limit error, back off for the suggested duration and retry with smaller batches.

Record the latest message timestamp per channel for the watermark.

### Step 3 — Classify every message/thread

Each item appears in exactly **one** section. Priority order:

| Section | Criteria |
|---------|----------|
| **Action Required** | Unread DMs + @mentions needing your response, review requests, questions directed at you, commitments you made with no follow-up yet. Must be `is_unread = true`. |
| **Technical Desk** | Threads matching knowledge/ topics (by tag overlap, channel heuristic, or semantic match) |
| **Announcements** | Releases, launches, org-wide posts, anything relevant not in above |
| **Skip** | Bot noise, social chatter, skip-list channels, your own messages with no replies |

**For Action Required items, also classify:**

- **Who** — who is asking
- **What** — the specific ask
- **Where** — channel + thread link
- **Urgency** — based on recency, explicit deadlines, escalation language
- **Size** — (S) quick reply, (M) research/work needed, (L) multi-step deliverable

### Step 4 — Extract knowledge

Skip this step if mode is `digest`.

For each Technical Desk thread, extract:

- **Key facts/decisions** — concrete info worth remembering long-term
- **Problems & solutions** — issues raised, workarounds shared
- **Links** — docs, repos, blog posts, recordings
- **Source** — channel name, date, key participants

**Match to knowledge files** (stop at first match):

1. **Tag overlap** — thread content matches `#tags` from knowledge files. Score by count.
2. **Channel heuristic** — channel name maps to knowledge file tags
3. **Semantic match** — topic relates conceptually to a file's title/summary

**Confidence levels:**

| Level | Criteria |
|-------|----------|
| HIGH | 3+ tag matches AND substantive thread (5+ messages or links) |
| MEDIUM | 1-2 tag matches OR channel heuristic match |
| LOW | Semantic match only, or thin content |

**New topic detection:** If 2+ unmatched threads converge on the same subject, propose a new knowledge file. Single unmatched threads go to Skipped.

### Step 5 — Synthesize knowledge updates

Skip this step if mode is `digest`.

Group extractions by target knowledge file. For each:

1. Read existing content from `{SHED}/knowledge/<slug>.md`
2. Deduplicate — skip facts already present
3. Generate dated entry blocks:
   ```
   **Topic/Event (YYYY-MM-DD):** 2-4 sentence synthesis with key takeaway. Source: #channel-name thread.
   ```
4. Merge — existing content + new entries appended at bottom
5. Write complete merged file to `{SHED}/drafts/knowledge/<slug>.md`

For **new knowledge files**:
```markdown
# Topic Title

#relevant-tags

Brief description of the topic area.

**First Entry (YYYY-MM-DD):** Synthesis. Source: #channel threads.
```

Write to `{SHED}/drafts/knowledge/<new-slug>.md`.

### Step 6 — Write outputs

Create `{SHED}/drafts/knowledge/` directory if needed (`mkdir -p`).

**1. Knowledge patch** (skip if mode is `digest`) — `{SHED}/drafts/knowledge-patch-YYYY-MM-DD.md`:

```markdown
# Knowledge Patch — YYYY-MM-DD

Processed N threads from M channels (window: start → end)

## Updates to Existing Files

### slug.md (CONFIDENCE)
**What's new:** 2-sentence summary
**From:** #channel (N threads)
**Apply:** `cp drafts/knowledge/slug.md knowledge/slug.md`

## New Knowledge Files Proposed

### new-slug.md (CONFIDENCE)
**Why:** N threads across M channels — no existing file covers this
**Tags:** #tag1 #tag2
**Apply:** `cp drafts/knowledge/new-slug.md knowledge/new-slug.md`

## Skipped (LOW confidence)
- Thread in #channel about X — reason skipped
```

**2. Per-file drafts** — `{SHED}/drafts/knowledge/<slug>.md` for each updated or new file.

**3. Watermark** — `{SHED}/drafts/slack-watermark.md`:

```markdown
# Slack Watermark
# Last updated: YYYY-MM-DD HH:MM

channel_id_1: 1712345678.000000
channel_id_2: 1712345679.000000
```

### Step 7 — Print terminal summary

Print a single combined dashboard. This is the primary output.

```
═══════════════════════════════════════════
  Slack — YYYY-MM-DD (window: Nd)
  Channels: M scanned | Threads: N processed
═══════════════════════════════════════════

🔴 ACTION REQUIRED (N items)
  (S) @alice in #ml-sme — "Can you review the MLflow 3 migration doc?"
  (M) @bob in #canada-ai — "Need vector search sizing by Friday"
  (L) @carol in #agents — shared agent notebook for your review

📡 TECHNICAL DESK
  ML & MLOps
    #ml-sme — MLflow 3 GA timeline confirmed for Q3, migration guide shared
    #automl — New AutoML API for time series, early benchmarks promising
  Agents & GenAI
    #agents — LangGraph vs CrewAI comparison thread, consensus on LangGraph
  Data Platform
    #apa-unity-catalog — Lineage API v2 rolling out, breaking change in permissions

📢 ANNOUNCEMENTS
  #general — Q2 all-hands recording posted
  #canada-ai — Toronto office meetup April 18

📚 KNOWLEDGE UPDATES (N files updated, M new proposed)
  Updated: machine-learning.md, agents.md
  New:     lakebase.md
  Review:  drafts/knowledge-patch-YYYY-MM-DD.md

Quick apply:
  cp drafts/knowledge/machine-learning.md knowledge/machine-learning.md
  cp drafts/knowledge/agents.md knowledge/agents.md
  cp drafts/knowledge/lakebase.md knowledge/lakebase.md

Suggested loops:
  - [ ] (S) [YYYY-MM-DD] Reply to @alice in #ml-sme re: MLflow 3 migration
  - [ ] (M) [YYYY-MM-DD] Vector search sizing for @bob — due Friday
  - [ ] (S) [YYYY-MM-DD] Review knowledge patch and promote updates
```

**Formatting rules:**
- Action Required comes FIRST, always — this is the "inbox zero" section
- Technical Desk groups threads by topic (matched knowledge file), not by channel
- Announcements are one-liners only
- Knowledge section only appears if mode is not `digest`
- Entire terminal output fits on one screen when possible — be ruthlessly concise

---

## Safety Rules

- NEVER post Slack messages — all output is in drafts or stdout only
- NEVER react to messages, mark as read, or modify any Slack state
- NEVER write to backbone directories (`knowledge/`, `daily/`, `loops/`) — `drafts/` only
- Read-only Slack access only
- If rate limited, back off and retry with smaller batches
- If no noteworthy content is found, say so and skip file creation

ARGUMENTS: $ARGUMENTS
