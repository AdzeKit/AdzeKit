# Slack Knowledge

Extract evergreen knowledge from Slack threads and propose updates to the shed's
`knowledge/` files. Complements `slack-digest` (what happened today?) by answering
"what should I remember forever?" Output goes to `drafts/` — a single patch file
for batch review, plus per-file drafts ready to promote with `cp`.

## Prerequisites

- Slack MCP (`mcp__slack__slack_read_api_call`) — Slack read access

---

## Shed Access

All backbone reads use the `Read` tool directly on shed files. Writes use `Write` to `{SHED}/drafts/`.

| Data | Path |
|------|------|
| Role context | `{SHED}/knowledge/role-context.md` |
| Knowledge files | `{SHED}/knowledge/*.md` (Glob, then Read) |
| Watermark | `{SHED}/drafts/slack-knowledge-watermark.md` |
| Recent digests | `{SHED}/drafts/slack-digest-*.md` (Glob — reuse if fresh) |
| Patch output | `{SHED}/drafts/knowledge-patch-YYYY-MM-DD.md` (Write) |
| Per-file drafts | `{SHED}/drafts/knowledge/<slug>.md` (Write) |
| Watermark output | `{SHED}/drafts/slack-knowledge-watermark.md` (Write) |

---

## Arguments

Parse `$ARGUMENTS` for optional scope controls:

- **Time window**: `3d`, `1w` (default), `2w`, or ISO date like `2026-04-01`
- **Channel filter**: `channel:<name>` to scope to a single channel
- **Full rescan**: `full` ignores watermark and processes the full window

Examples: `/slack-knowledge`, `/slack-knowledge 2w`, `/slack-knowledge channel:ml-sme`

---

## Workflow

### Step 1 — Load context

Read all in parallel:

1. `{SHED}/knowledge/role-context.md` — priority channels list, skip channels, technical interests
2. Glob `{SHED}/knowledge/*.md` — read each file, extract:
   - Filename (slug)
   - Title (first `# ` heading)
   - Tags (all `#kebab-case` tokens)
   - Content summary (first paragraph after tags, if present)
3. `{SHED}/drafts/slack-knowledge-watermark.md` — if it exists, parse `channel_id: timestamp` pairs
4. Glob `{SHED}/drafts/slack-digest-*.md` — if a digest exists within the time window, parse its Technical Desk and Announcements sections to pre-seed thread summaries

Build an internal index:

```
KNOWLEDGE_INDEX: {
  "machine-learning.md": {
    title: "Machine Learning",
    tags: ["machine-learning", "ml", "mlops", "mlflow", "feature-engineering"],
    summary: "ML on Databricks — MLflow, Feature Store..."
  },
  ...
}
CHANNEL_LIST: [from role-context.md priority channels]
WATERMARK: {channel_id: last_processed_timestamp} or empty
WINDOW_START: max(watermark, now - time_window)
```

### Step 2 — Fetch Slack threads

Use `mcp__slack__slack_read_api_call` for all API calls. All calls are **read-only**.

For each channel in CHANNEL_LIST (skip if `channel:` argument excludes it):

1. **Resolve channel ID** via `conversations.list` (paginate if needed, cache results across channels)
2. **Fetch messages** via `conversations.history(channel=ID, oldest=WINDOW_START, limit=200)`
3. **Filter for knowledge-worthy threads** — a thread qualifies if ANY of:
   - 3+ replies (substantive discussion)
   - 2+ reactions (community signal)
   - Contains links to docs, repos, or external resources
   - From a known authoritative sender (team leads, product managers)
   - Skip: bot-only messages (unless substantive announcements), social chatter, your own messages with no replies
4. **Fetch full threads** via `conversations.replies(channel=ID, ts=thread_ts)` for each qualifying thread
5. **Resolve senders** via `users.info` — batch and cache across channels

**Rate limiting:** If any call returns a rate limit error, back off for the suggested duration and retry with smaller batches.

Record the latest message timestamp per channel for the watermark.

### Step 3 — Extract and classify

For each qualifying thread, extract:

- **Key facts/decisions** — concrete technical information worth remembering long-term
- **Topics** — what knowledge domains does this touch?
- **Problems & solutions** — issues raised, workarounds or fixes shared
- **Links** — docs, repos, blog posts, recordings shared in the thread
- **Source** — channel name, date, key participants

**Match to knowledge files** using three tiers (stop at first match):

1. **Tag overlap** — thread content contains terms matching `#tags` from knowledge files. Score by number of matching tags.
2. **Channel heuristic** — channel name maps to knowledge file tags (e.g., `automl` channel content → files tagged `#automl` or `#machine-learning`)
3. **Semantic match** — thread topic is conceptually related to a knowledge file's title/summary even without exact tag matches

**Assign confidence:**

| Level | Criteria | Display |
|-------|----------|---------|
| HIGH | 3+ tag matches AND substantive thread (5+ messages or links) | Prominent in patch |
| MEDIUM | 1-2 tag matches OR channel heuristic match | Normal in patch |
| LOW | Semantic match only, or thin thread content | Listed in Skipped section |

**New topic detection:** If 2+ unmatched threads (no HIGH or MEDIUM match to any existing file) converge on the same subject, propose a new knowledge file. Single unmatched threads go to Skipped.

**Direct asks / action items:** While classifying, also detect messages that are **direct asks to the user** — @mentions requesting help, questions directed at you, requests for reviews, follow-ups owed, or commitments made by you in threads. These become suggested loops in the output. Classify each ask:
- **Who** — who is asking / who do you owe a response to
- **What** — the specific ask or commitment
- **Where** — channel and thread link
- **Urgency** — based on recency, explicit deadlines, or escalation language
- **Size** — (S) for quick replies, (M) for research/work needed, (L) for multi-step deliverables

### Step 4 — Synthesize updates

Group all extractions by target knowledge file. For each file:

1. **Read existing content** from backbone `{SHED}/knowledge/<slug>.md`
2. **Deduplicate** — if the extracted fact is already present in the file (same event, same link, same concept), skip it
3. **Generate dated entry blocks** matching the format already used in knowledge files:

   ```
   **Topic/Event (YYYY-MM-DD):** 2-4 sentence synthesis with key takeaway. Source: #channel-name thread.
   ```

4. **Merge** — existing content + new entries appended at the bottom of the file
5. **Write complete merged file** to `{SHED}/drafts/knowledge/<slug>.md`

For **new knowledge files**:

1. Generate standard knowledge file format:
   ```markdown
   # Topic Title

   #relevant-tags

   Brief description of the topic area.

   **First Entry (YYYY-MM-DD):** Synthesis of the threads that triggered this file. Source: #channel threads.
   ```
2. Write to `{SHED}/drafts/knowledge/<new-slug>.md`

### Step 5 — Write outputs

Create `{SHED}/drafts/knowledge/` directory if it doesn't exist (use Bash `mkdir -p`).

Write three outputs:

**1. Patch file** — `{SHED}/drafts/knowledge-patch-YYYY-MM-DD.md`:

```markdown
# Knowledge Patch — YYYY-MM-DD

Processed N threads from M channels (window: YYYY-MM-DD to YYYY-MM-DD)

## Updates to Existing Files

### machine-learning.md (HIGH)
**What's new:** 2-sentence summary of what was added
**From:** #ml-sme (3 threads), #automl (1 thread)
**Apply:** `cp drafts/knowledge/machine-learning.md knowledge/machine-learning.md`

### gen-ai.md (MEDIUM)
**What's new:** ...
**From:** ...
**Apply:** `cp drafts/knowledge/gen-ai.md knowledge/gen-ai.md`

## New Knowledge Files Proposed

### lakebase.md (HIGH)
**Why:** 4 threads across 2 channels discussing Lakebase — no existing knowledge file covers this
**Tags:** #lakebase #postgres #database
**Apply:** `cp drafts/knowledge/lakebase.md knowledge/lakebase.md`

## Direct Asks (loops needed)

- [ ] (S) [YYYY-MM-DD] Reply to @alice-chen in #ml-sme re: MLflow 3 migration timeline
- [ ] (M) [YYYY-MM-DD] Prepare vector search sizing for @bob in #canada-ai (due Friday)
- [ ] (S) [YYYY-MM-DD] Review @carol's agent notebook shared in #agents

## Skipped (LOW confidence)
- Thread in #canada-sa about office logistics — not technical
- Single thread on topic X — needs more signal before creating a file
```

**2. Per-file drafts** — `{SHED}/drafts/knowledge/<slug>.md` for each updated or new file. These are complete, ready-to-promote files.

**3. Watermark** — `{SHED}/drafts/slack-knowledge-watermark.md`:

```markdown
# Slack Knowledge Watermark
# Last updated: YYYY-MM-DD HH:MM

channel_id_1: 1712345678.000000
channel_id_2: 1712345679.000000
```

### Step 6 — Terminal output

Print a summary dashboard directly to the terminal:

```
Slack Knowledge — YYYY-MM-DD
Processed: 47 threads from 12 channels (window: 7d)
Updates: 6 existing files, 1 new file proposed
Skipped: 14 threads (low signal)

Review: {SHED}/drafts/knowledge-patch-YYYY-MM-DD.md

Quick apply (run from shed root):
  cp drafts/knowledge/machine-learning.md knowledge/machine-learning.md
  cp drafts/knowledge/ai-evaluation.md knowledge/ai-evaluation.md
  cp drafts/knowledge/mcp.md knowledge/mcp.md
  cp drafts/knowledge/lakebase.md knowledge/lakebase.md

Suggested loops (copy to loops/active.md):
- [ ] (S) [YYYY-MM-DD] Review knowledge patch and promote updates
- [ ] (S) [YYYY-MM-DD] Reply to @alice-chen in #ml-sme re: MLflow 3 migration
- [ ] (M) [YYYY-MM-DD] Prepare vector search sizing for @bob in #canada-ai
```

---

## Safety Rules

- NEVER post Slack messages — all output is in drafts only
- NEVER react to messages, mark as read, or modify any Slack state
- NEVER write to backbone directories (`knowledge/`, `daily/`, `loops/`, etc.) — `drafts/` only
- Read-only Slack access only
- If rate limited, back off and retry with smaller batches
- Watermark updates go to `drafts/` (agent-writable zone)
- If no knowledge-worthy threads are found, say so and skip file creation

ARGUMENTS: $ARGUMENTS
