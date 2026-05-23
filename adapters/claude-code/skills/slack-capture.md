# Slack Capture

## Goal

Sweep recent Slack activity across configured channels, extract durable knowledge (decisions,
process notes, links worth remembering, contact signals), and attach captures to the right
entities in the shed's knowledge graph. The Slack channel is treated as ephemeral; the
captures are not.

Generic skill. The list of channels to monitor and the entity registry to attach captures to
come from the workspace (`knowledge/role-context.md`, `knowledge/contacts.md`, the graph
`entities.md`), not from the skill. A user with no graph yet still gets useful captures
written to a flat `drafts/slack-capture-YYYY-MM-DD.md`.

## Inputs

- `{SHED}/knowledge/soul.md` — voice, what counts as "worth capturing"
- `{SHED}/knowledge/role-context.md` — priority channels (or workspace equivalent declaring
  channel list)
- `{SHED}/graph/entities.md` — existing entities to match captures against (if present)
- `{SHED}/drafts/slack-watermark.md` — last-seen message timestamp per channel (state file;
  the skill maintains it)
- A Slack workspace the adapter can read from (the adapter resolves how — Slack MCP, a
  bot token, or another transport)

## Process

1. **Load context.** Read soul.md, role-context, the entity index. Build an alias table
   mapping channel-friendly names ("john_doe", "JD", "John") to canonical entity slugs.
   Parallelism: all reads independent.

2. **Determine sweep range.** Read `slack-watermark.md`. For each configured channel,
   compute the timestamp range to fetch: from the watermark forward to now. Cap any single
   sweep at 7 days back to bound runtime.

3. **Fetch messages.** Pull all messages in the computed range across all configured
   channels. Pass A is a deterministic string match — no LLM needed — for known entity
   aliases against message text. Build a candidate list of `(channel, message_ts,
   matched_entity, surrounding_thread_excerpt)` records.

4. **Capture pass (Pass B).** For each candidate, decide if there's durable knowledge worth
   recording:
   - **Capture**: decisions ("we'll go with X"), process explanations, links to docs,
     reusable code snippets, contact information, capability claims, deadlines stated.
   - **Skip**: status updates, social chatter, transient questions, pure links without
     framing, sentiment.
   When in doubt, capture — the human reviews. Conservative pruning at write time.

5. **Cluster restatements.** If multiple messages restate the same fact for the same
   entity, keep the clearest one and reference the others. Avoid writing 4 nearly-identical
   captures.

6. **Write captures.** For each entity with new captures, append to
   `{SHED}/drafts/knowledge/{entity-slug}.md` (creating the file if absent). Captures are
   prepended above the existing file content so newest is on top. Each capture carries:
   - Permalink to the Slack message
   - One-line restatement of the captured fact
   - Excerpt for context (max 2 lines)
   - Date

7. **Write the run report.** Create
   `{SHED}/drafts/slack-capture-YYYY-MM-DD-HHMM-{host}.md` summarizing: messages scanned,
   captures emitted, entities touched, candidates skipped with reason.

8. **Update the watermark.** Write the latest seen `message_ts` per channel back to
   `slack-watermark.md`. This is a state mutation — the skill's only persistent side
   effect outside of `drafts/`.

9. **Print terminal summary.** One-line counts and the report path.

## Outputs

- `{SHED}/drafts/knowledge/{entity-slug}.md` per affected entity (newest captures on top)
- `{SHED}/drafts/slack-capture-YYYY-MM-DD-HHMM-{host}.md` (run report with
  `<!-- adzekit-draft -->` provenance header once Phase 2 lands)
- Updated `{SHED}/drafts/slack-watermark.md`
- Optional: messages marked-read in Slack (adapter-configurable)

## Parallelism notes

The dominant cost is Pass B (reasoning per candidate). Recommended adapter pattern:
- Orchestrator does Pass A (string match) deterministically.
- Orchestrator partitions Pass B candidates into chunks (~10–20 candidates per worker) and
  fans out workers with concurrency cap 5.
- Workers receive only their candidate slice + the entity registry slice for those
  candidates (NOT the full registry — this is the selective-context-inheritance win).
- Workers return JSON arrays of `(entity, fact, excerpt, permalink, confidence)`. Workers
  have read-only tools; they do not write to drafts.
- Orchestrator collects all worker output, clusters, writes drafts.

Speed budget: 20 batches across 5 channels should complete in ~2 minutes with parallel
workers vs. ~5–8 minutes with monolithic single-context execution.

## Safety Rules

- Never write to `knowledge/` directly. All captures go to `drafts/knowledge/`. Human
  promotes to `knowledge/` after review.
- Never delete messages. Mark-as-read is the maximum mutation; even that is adapter-
  configurable and off by default.
- Never auto-react with emojis or reply in Slack. This skill is read-only on Slack.
- Watermarks are atomic per channel. If the skill fails mid-run, the watermark for
  unprocessed channels stays at the prior value — the next run picks up where this one
  left off.

## Notes for adapters

- Channel list and entity registry are workspace state, not skill state. A different user
  with a different graph gets entirely different captures from the same skill.
- The Slack-specific transport (MCP, bot token, API client) is adapter-level. The skill
  spec only says "fetch messages for a channel in a time range."
- Capture confidence threshold: drafts can declare a `confidence:` field per capture.
  High-confidence captures (e.g., explicit decisions with multi-person acknowledgment)
  can be auto-promoted to `knowledge/` via `adzekit drafts accept --auto`.
- A future variant could substitute another team chat source (Discord, Teams, Matrix). The
  skill spec is mostly source-agnostic — only the transport and the alias-format change.
