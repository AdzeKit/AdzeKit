# Slack

Wide Slack sweep for **durable knowledge**: patterns, anti-patterns, and customer signals worth
remembering in 6 months. Skip operational noise (incidents, calendar, today's bug status).
Append plain-prose paragraphs to existing `knowledge/<slug>.md` files via `drafts/`. Markdown
files are the only output — graph edges are NOT proposed (graph structure is human-curated via
typed-rel headers in knowledge notes; this skill enriches content, not structure).

**The capture bar:** _"Will this still matter in 6 months?"_ If no, discard.

**Outputs in one fetch cycle:**

| Output | Purpose | Path |
|--------|---------|------|
| Per-file knowledge drafts | Prose paragraphs appended to existing notes | `{SHED}/drafts/knowledge/<slug>.md` |
| Terminal dashboard | Action Required + what got captured | stdout |
| Watermark | Per-channel last-seen ts | `{SHED}/drafts/slack-watermark.md` |

## Prerequisites

- Slack MCP (`mcp__slack__slack_read_api_call`) — read-only access
- Slack MCP write (`mcp__slack__slack_write_api_call`) — required ONLY when `mark_read` is passed; used solely for `conversations.mark`
- Graph built: `graph/entities.md` exists (run `adzekit graph build` first if not)

---

## Shed Access

Reads via `Read` / `Glob`. Writes go to `{SHED}/drafts/` only.

| Data | Path |
|------|------|
| Entity registry | `{SHED}/graph/entities.md` (REQUIRED — used to match Slack mentions) |
| Role context | `{SHED}/knowledge/role-context.md` (skip channels, interests) |
| Knowledge notes | `{SHED}/knowledge/*.md` (Glob, then Read) |
| Today's note | `{SHED}/daily/YYYY-MM-DD.md` |
| Open loops | `{SHED}/loops/active.md` |
| Watermark | `{SHED}/drafts/slack-watermark.md` |
| Per-file knowledge drafts | `{SHED}/drafts/knowledge/<slug>.md` |

---

## Arguments

Parse `$ARGUMENTS` for optional controls:

- **Time window**: `1d` (default), `3d`, `1w`, `2w`, or ISO date `2026-04-01`
- **Channel filter**: `channel:<name>` — scope to a single channel
- **Mode**:
  - `capture` (default) — full durable-knowledge capture, writes drafts
  - `digest` — terminal-only summary (Action Required + a one-line preview), skip drafts
- **Full rescan**: `full` — ignore watermark
- **Cap**: `cap:<N>` — soft message cap per run (default 5000)
- **Batch cap**: `cap_batches:<N>` — process only the first N Pass-B batches (for dry runs). Pass A still runs over everything; Step 4–7 outputs reflect only the captured batches.
- **Dry run**: `dry-run` — print what would be written but skip all `Write` calls to `drafts/`. Useful with `cap_batches`.
- **Mark read**: `mark_read` — opt-in. After writing the watermark, also call `conversations.mark` per channel that had new messages, so Slack's per-user unread badges advance to the latest processed `ts`. Default OFF (read-only-by-default). Requires `mcp__slack__slack_write_api_call`.

Examples: `/slack`, `/slack 3d`, `/slack channel:ml-sme`, `/slack 1w digest`, `/slack 2w full`,
`/slack 1w cap_batches:2 dry-run`, `/slack 1w mark_read`

---

## Workflow

### Step 1 — Load context and build entity index

Read all in parallel:

1. `{SHED}/graph/entities.md` — parse into ENTITY_REGISTRY: `{name → (type, sources, knowledge_slug?)}`
2. `{SHED}/knowledge/role-context.md` — SKIP_CHANNELS, INTERESTS
3. Glob `{SHED}/knowledge/*.md`, read each — KNOWLEDGE_INDEX: `{slug → (title, tags, summary)}`
4. `{SHED}/daily/{today}.md` + `{SHED}/loops/active.md` — today's context (for ranking Action Required)
5. `{SHED}/drafts/slack-watermark.md` — `{channel_id → last_ts}` (or empty if `full`)

**Build the ALIAS_INDEX** (critical for fast matching):

For each entity in ENTITY_REGISTRY, generate alias forms:
- The slug itself (`vector-search`)
- Spaced form (`vector search`)
- Title-cased (`Vector Search`)
- For `person` type: `firstname lastname`, `Firstname Lastname`, `@firstname-lastname`
- For `project` type: also include the project's title from `projects/<slug>.md` heading
- For `concept` / `tool`: also include the title from `knowledge/<slug>.md` heading and any tag aliases

Index aliases as a case-folded prefix-trie or dictionary keyed on token-1 of each alias for O(N) message scanning.

```
ENTITY_REGISTRY: {
  "vector-search": {type: tool, slug: vector-search, knowledge: yes, aliases: [vector search, Vector Search, vs]},
  "ascot-claimdocparsing": {type: project, slug: ascot-claimdocparsing, aliases: [ascot, ascot group, claim doc parsing]},
  ...
}
```

### Step 2 — Discover channels and fetch messages

**Channel discovery:**

1. `users.conversations(types=public_channel,private_channel,im,mpim)` — channels Scott is a member of
2. Filter out SKIP_CHANNELS from role-context.md
3. Apply `channel:` argument filter if provided

**Per-channel fetch:**

For each channel:
1. `conversations.info(channel=ID)` → `last_read` timestamp
2. `conversations.history(channel=ID, oldest=max(watermark[ID], now-window), limit=200)` (paginate via `cursor`)
3. For threaded messages with reply_count ≥ 2 OR reaction_count ≥ 2: fetch full thread via `conversations.replies`
4. Resolve user IDs to names via `users.info` (batch, cache across the whole run)
5. Tag each message: `is_unread = (ts > last_read)`, `is_dm`, `is_mention_to_me`

**Caps and rate limits:**
- Concurrent fetch up to 8 channels at a time
- If total messages collected ≥ `cap` (default 5000), stop fetching new channels and process what's collected
- On rate limit response, back off for `Retry-After` and resume with `min(remaining, batch_size//2)`

Record latest message ts per channel for the new watermark.

### Step 3 — Two-pass entity matching

**Pass A — deterministic pre-filter (no reasoning, just string match):**

Scan every fetched message body against ALIAS_INDEX. Tokenize on word boundaries (case-folded);
match aliases as whole-word or hyphenated-slug occurrences. A message can hit multiple entities.
Track for each candidate message: `{ts, channel, sender, text, hit_entities, thread_ts, reactions, reply_count}`.

Retain a message only if at least one of:
- It hit ≥1 entity in ALIAS_INDEX
- It is a DM or @mention to Scott (always retained for Action Required)
- It is a direct reply inside a thread whose root hit ≥1 entity

Discard everything else with no further processing.

**Pass B — batched extraction (one reasoning pass per batch, NOT per message):**

Do not classify messages one at a time. Group candidate messages into batches and reason about
each batch holistically — Claude sees ~50–100 related messages plus the relevant slice of the
entity registry, then produces a structured capture array in a single pass.

**Batch construction rules:**

- Sort candidate messages by `(channel, thread_ts, ts)` so threaded discussions stay contiguous.
- Cap each batch at **~25K input tokens** (roughly 80–120 messages depending on length). If a
  single thread blows the cap, split at thread boundary.
- For each batch, attach an **entity slice** containing only the entities hit by messages in that
  batch (slug, type, knowledge title/summary if available, existing typed relations from
  `graph/relations.md` for that entity). Do not include the full 208-entity registry per batch.
- Estimate: typical run with 1000–3000 candidate messages → 10–30 batches.

**Per-batch reasoning prompt (Claude executes against itself for each batch):**

Read the batch + entity slice. **Reject ruthlessly.** The default for any given message is
DISCARD. Only capture when something durable is being said about an entity — a lesson, a pattern,
a customer signal that will hold for months.

For surviving captures, produce a structured array. Drop the raw batch from context after writing.

```json
{
  "batch_id": "b07",
  "captures": [
    {
      "entity": "agent-bricks",
      "class": "CustomerSignal",
      "channel": "canada-ai",
      "thread_root_ts": "1714000000.123",
      "permalink": "https://databricks.slack.com/archives/C.../p1714000000123",
      "insight": "Enterprise customers (Lululemon) expect a documented Dev→Prod promotion path for Knowledge Assistants and immediate-feedback UX (e.g. processing spinner) when KAs are embedded in Teams. Today this requires API recreation or UI clicks — fragile for production rollout.",
      "evidence_quote": "What is the recommended approach for promoting an Agent between environments (Dev → Prod)? ... no clear guide; recreating via API or UI is the only option.",
      "why_durable": "Promotion paths and UX-feedback expectations are baseline enterprise requirements — this gap will keep coming up across customers until the product addresses it.",
      "confidence": "HIGH"
    }
  ]
}
```

**Classification taxonomy:**

| Class | Signal | Bar |
|-------|--------|-----|
| **Pattern** | A durable approach that works — architectural decision, design principle, "when X, do Y because Z". | Reusable across customers |
| **AntiPattern** | A durable lesson about what doesn't work and *why* — not "this thing is broken today" but "this approach has a structural problem". | Useful as a cautionary note in 6 months |
| **CustomerSignal** | What customers consistently value, need, or struggle with — not specific to one ticket. | Generalizes beyond a single account |
| **Reference** | A genuinely useful external resource (Anthropic docs, blog post, repo) worth bookmarking under the entity's note. | Will still be useful when the original Slack message is gone |
| **Discard** | Default for everything else: support tickets, bug-of-the-day, scheduling, status updates, calendar items, "is this on roadmap" Q&A, broken-link reports, single-customer regressions, version bumps. **Omit from output entirely.** |

**Hard discard list** — never capture these even if they mention an entity:
- "Y customer is hitting bug X" without a structural lesson behind it
- Roadmap questions ("is this planned?") with no answer
- "How do I do X" support questions without a generalizable answer
- GA / PuPr announcements (these belong in `daily/` notes, not `knowledge/`)
- Calendar / scheduling / "can someone join us in Denver"

**Lower-bar exception — `databricks-platform.md` ephemeral log:**

Genuine platform-level bugs and limitations CAN go into `knowledge/databricks-platform.md` under
a `## Ephemeral Notes` section as a single dated bullet (one line each), with the understanding
that this section ages out and gets pruned during weekly review. Cap at 5 ephemeral notes per
sweep. This is the *only* exception to the "durable only" rule.

**Confidence guidance:**
- HIGH — corroborated across multiple threads or messages, or said by a senior/credible source
- MEDIUM — single substantive thread, plausible generalization
- LOW — only fits the bar if you squint; default to DISCARD instead

**Aggregation after all batches:**

Merge capture arrays. Dedup by `(entity, permalink)`. Cluster captures that are restatements of
the same insight ("Dev→Prod promotion gap appeared in 3 threads") and write one consolidated
paragraph rather than three separate entries.

### Step 4 — New-entity candidates (terminal only)

Do NOT propose graph edges. The graph's structure is curated manually via typed-rel headers in
`knowledge/<slug>.md` files; this skill's job is content enrichment only.

**New-entity candidates:** when an unmatched noun phrase appears in ≥4 distinct threads across
the window AND looks like a genuine concept/tool worth a future knowledge note, list it in the
dashboard as a one-liner. Do NOT write a separate file. The user decides whether to stub a new
`knowledge/<slug>.md`.

### Step 5 — Write per-file knowledge drafts (markdown prose)

For every entity that has a knowledge note (`knowledge/<slug>.md` exists) AND survived the
durable-knowledge filter:

1. Read existing `knowledge/<slug>.md`.
2. Append captures as **plain prose paragraphs** under a `## Field Notes` section (create if
   absent). Do NOT write structured JSON-style entries with permalink lines and participant
   lists. The note should read like Scott's own writing.

**Format for each capture (Pattern / AntiPattern / CustomerSignal / Reference):**

```markdown
**Pattern — what works:** One-paragraph synthesis (~2-4 sentences) of the durable insight,
framed in Scott's own voice. End with a brief source attribution in parens. _(#channel,
YYYY-MM-DD)_

**Anti-pattern:** Same shape — describe the structural problem and *why* it fails, not the
specific bug. _(#channel, YYYY-MM-DD)_

**Customer signal:** What customers consistently want / struggle with / value, generalized
across the source thread(s). _(#channel, YYYY-MM-DD)_

**Reference:** Title or one-line summary plus the link. _(via #channel, YYYY-MM-DD)_
```

Examples of *good* phrasing (durable, generalized):
- ✅ "Enterprise customers expect a documented Dev→Prod promotion path for KAs and immediate-feedback UX when KAs are embedded in chat clients. Re-creating via API/UI is fragile for production rollout."
- ✅ "OAuth client TTL on the Databricks MCP Connector is governed by the workspace browser-session limit, not the OAuth app config — set expectations accordingly when scoping production agent-to-MCP integrations."

Examples of *bad* phrasing (transient, ticket-flavored — DON'T write these):
- ❌ "ai_prep_search not resolving on serverless v3 — error: Cannot resolve routine"
- ❌ "Bug: experiments view showing 2-month-old runs"
- ❌ "Supervisor API (Beta) is now live"

**Deduplicate against existing prose** — if the same insight is already in the note (even
phrased differently), skip. Quality over volume.

**For `databricks-platform.md` ephemeral notes** (the lower-bar exception):

```markdown
## Ephemeral Notes
_Operational gotchas — prune during weekly review._

- 2026-04-27: One-line description. _(#channel)_
```

Cap at 5 lines per sweep.

**For entities with NO existing knowledge note:** do NOT auto-create a file. Surface as a
candidate in the dashboard (Step 8) only.

### Step 6 — Write watermark + (optional) mark read + Action Required

**6a. Watermark.** Update `{SHED}/drafts/slack-watermark.md`:

```markdown
# Slack Watermark
# Last updated: YYYY-MM-DD HH:MM

channel_id_1: 1712345678.000000
channel_id_2: 1712345679.000000
```

**6b. Mark read (only if `mark_read` was passed).** For each channel where the run recorded a
new watermark (i.e. fetched ≥1 message this run), issue:

```python
mcp__slack__slack_write_api_call(
    endpoint="conversations.mark",
    params={"channel": channel_id, "ts": latest_ts},  # same ts written to the watermark file
)
```

This advances Slack's per-user `last_read` cursor for that channel up to the message we
processed, clearing the unread badge in the UI to that point.

Rules:
- Skip channels with **zero new messages** this run (no point bumping).
- On per-channel failure (rate-limit, permission, network), continue with the rest. Track
  `marked` and `failed` counts for the dashboard.
- Never call `conversations.mark` for channels we did NOT fetch from this run (skip-list,
  `channel:` filter excluded). Only mark what we processed.
- This is the ONLY write call the skill is permitted to make. Never `chat.postMessage`,
  reactions, or any other modify.

**6c. Action Required.** Produce the list of DMs, @mentions, and direct questions to Scott —
same format as before, included in the terminal dashboard (Step 7).

### Step 7 — Print terminal dashboard

```
═══════════════════════════════════════════
  Slack — YYYY-MM-DD (window: Nd)
  Channels: M scanned | Messages: K fetched · R retained · C captured
  Captured: P patterns · A anti-patterns · S customer signals · R references
  Discarded: D (operational/transient/single-incident)
═══════════════════════════════════════════

🔴 ACTION REQUIRED (N items)
  (S) @alice in #ml-sme — "Can you review the MLflow 3 migration doc?"
  (M) @bob in #canada-ai — "Need vector search sizing by Friday"

📚 DURABLE CAPTURES (top by impact)
  agent-bricks (CustomerSignal) — Enterprise customers expect Dev→Prod promotion paths for KAs and
    immediate-feedback UX in chat clients. (Lululemon via #canada-ai)
  mcp (AntiPattern) — Token TTL on Databricks MCP Connector is governed by the workspace
    browser-session limit, not the OAuth app config — affects scoping prod agent-to-MCP. (#agents)
  anthropic (Reference) — "Lessons from Building Claude Code: How We Use Skills" — useful for our
    own skill design, with a flagged distribution gap. (#canada-ai)

📝 KNOWLEDGE FILES UPDATED ({N} drafts)
  Review: drafts/knowledge/{slug}.md  (one per affected entity)
  Apply:  cp drafts/knowledge/agent-bricks.md knowledge/agent-bricks.md  (etc.)

🪦 EPHEMERAL NOTES
  {N} bullets appended to drafts/knowledge/databricks-platform.md (prune at weekly review)

🆕 CANDIDATE ENTITIES (≥4 distinct threads, no current knowledge note)
  - mlflow (concept) — recurring across ml-sme + agents
  - knowledge-assistant (tool) — recurring across agents + canada-ai

✉️  MARKED READ: N channels (M skipped — zero new messages or fetch-only)
  (only printed when mark_read was passed)

Suggested loops:
  - [ ] (S) [YYYY-MM-DD] Reply to @alice in #ml-sme re: MLflow 3 migration
```

**Formatting rules:**
- Action Required FIRST — that's the inbox-zero-style top.
- Durable captures section is a small, high-quality list (3–8 items typical), each one phrased as
  the actual insight in the appended knowledge note — not as the raw thread title.
- Loud about discard rate (`Discarded: D`) so it's visible when a sweep finds little — that's a
  feature, not a failure.
- Candidate entities surfaced in the terminal only; do not auto-create files.
- The `MARKED READ` line only appears when `mark_read` was passed; if any channels failed,
  show `failed: F` after the skipped count.
- If `digest` mode, skip everything below "Action Required".

---

## Safety Rules

- NEVER post Slack messages, react, or modify any Slack state — with one explicit exception:
  `conversations.mark` is permitted only when `mark_read` was passed in `$ARGUMENTS`, and only
  for channels the run actually fetched from. Every other Slack write call is forbidden.
- NEVER write to backbone directories (`knowledge/`, `daily/`, `loops/`, `projects/`, `graph/`) — `drafts/` only.
- NEVER invent entities not in `graph/entities.md` — surface unmatched recurring noun phrases as candidates only.
- NEVER propose edges that already exist in `graph/relations.md`.
- If `graph/entities.md` is missing, stop and instruct the user to run `adzekit graph build`.
- Cap message processing at the configured `cap:` (default 5000). If hit, log and stop fetching.
- If rate limited, back off and retry with smaller batches.
- If no captures match the registry, write only the watermark and print "No graph-linkable activity in window."

ARGUMENTS: $ARGUMENTS
