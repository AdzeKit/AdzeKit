---
description: Cross-reference open loops against email, git, Slack, and tickets for closure evidence
argument-hint: Optional loop slice (e.g. project slug) to restrict the search
---

Execute the AdzeKit `loop-momentum` skill (canonical:
`src/adzekit/skills/loop-momentum.md`).

Fan-out skill. Use the `loop-evidence-worker` plugin agent. Shard loops in
chunks of ~5–10 per worker, concurrency cap 5.

Default evidence sources: Gmail (sent in last 7 days) + git log on the
workspace repo and any related project repos. Workspace may add Slack
(via Slack MCP) and Jira (via Jira MCP).

Each worker classifies loops as:
- **Likely closed** — high-confidence completion evidence in last 7 days
- **In motion** — recent activity but not completion
- **Cold** — no evidence in last 14 days
- **Unverified** — insufficient signal

Orchestrator computes velocity metrics deterministically (loops opened
vs closed, average age, oldest open loop) and writes the report draft.
Workers never modify loop files; the orchestrator emits proposed close
lines for the human to apply via `adzekit drafts accept`.

ARGUMENTS: $ARGUMENTS
