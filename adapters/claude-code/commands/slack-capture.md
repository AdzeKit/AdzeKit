---
description: Sweep configured Slack channels for durable knowledge; attach captures to graph entities
argument-hint: Optional channel list or watermark override
---

Execute the AdzeKit `slack-capture` skill (canonical:
`src/adzekit/skills/slack-capture.md`).

Fan-out skill. Use the `slack-capture-worker` plugin agent for Pass B
(reasoning over candidate messages). Pass A (string-match against entity
aliases) is deterministic and stays in the orchestrator.

Orchestrator responsibilities:
- Load context (soul.md, role-context, graph entities)
- Determine sweep range from `drafts/slack-watermark.md`
- Pass A: fetch messages, string-match candidates
- Pass B: shard candidates, spawn workers with selective entity-registry
  inheritance (workers see only the entities matched in their batches)
- Collect worker JSON, dedupe/cluster, write per-entity captures to
  `drafts/knowledge/<slug>.md` and a run report to
  `drafts/slack-capture-YYYY-MM-DD-HHMM-{host}.md`
- Update the watermark atomically per channel

Workers use `mcp__slack__slack_read_api_call` (read-only). No mark-as-read,
no replies, no reactions.

ARGUMENTS: $ARGUMENTS
