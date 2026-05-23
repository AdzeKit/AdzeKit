# AdzeKit Claude Code Adapter

The Claude Code execution profile for AdzeKit. Wraps the runtime-agnostic core skills
(`src/adzekit/skills/*.md`) in Claude Code's plugin primitives: slash commands, plugin
agents, the `Agent` tool for sub-agent fan-out.

Claude Code is AdzeKit's runtime. Sibling `adapters/<integration>/` directories host
*integration* adapters (Telegram bridge, Gmail, Calendar, etc.) — composable plugins
that the Claude Code session can consume via MCP or skill-side tools.

## Layout

```
adapters/claude-code/
├── README.md           — this file
├── agents/             — plugin agents (workers for the orchestrator+worker pattern)
│   ├── email-triage-worker.md
│   ├── slack-capture-worker.md
│   └── loop-evidence-worker.md
└── commands/           — slash command pointers (TBD; deferred until distribution model is decided)
```

## How a skill runs

Take `inbox-triage` as the canonical example:

1. User invokes `/inbox-triage` (slash command, defined in `commands/`).
2. Claude Code's main agent reads `src/adzekit/skills/inbox-triage.md` and executes
   the orchestrator role described there:
   - Loads context (soul.md, contacts, open loops) via parallel `Read` calls
   - Fetches all email metadata via `Bash` + `curl` to Gmail API in one pass
   - Shards messages into chunks of ~25
3. The main agent emits multiple `Agent` tool calls in a single message — one per
   chunk, with `subagent_type: "email-triage-worker"`. Claude Code runs these in
   parallel.
4. Each `email-triage-worker` runs in its own isolated context with `Bash, Read` only.
   It classifies its chunk and returns a JSON array.
5. The main agent collects all worker JSON, applies Gmail batch-modify and
   drafts.create in one place, then writes the single review report to
   `{SHED}/drafts/inbox-triage-YYYY-MM-DD-HHMM-{host}.md`.

## Why workers have no Write tool

Files-first is enforced by tool absence, not by convention. If a worker doesn't have
`Write`, it physically cannot create a draft or modify a loop file. The orchestrator
is the only chokepoint that mutates the shed. See `docs/delegation-pattern.md` for the
full contract.

## Status (as of Phase 1)

- Three plugin agents authored (`email-triage-worker`, `slack-capture-worker`,
  `loop-evidence-worker`).
- Delegation pattern contract documented in `docs/delegation-pattern.md`.
- `commands/` directory exists but is empty — the slash command distribution model
  needs a user decision (publish as a Claude Code plugin via the marketplace? ship as
  workspace overrides? both?).
- `plugin.json` / `marketplace.json` manifest: deferred to the distribution decision.

## Installation (preview — not yet implemented)

The eventual flow will look like:

```
$ pip install adzekit
$ adzekit adapter install claude-code
  → copies adapters/claude-code/agents/ into your Claude Code plugin directory
  → writes commands/ into ~/.claude/commands/ (or your workspace's .claude/commands/)
  → reports next-steps for invoking the skills
```

For now, the workspace at `~/Repos/adzekit-workspace/.claude/commands/` is the
hand-maintained equivalent — thin slash-command pointers that read the workspace's
own copies of skills. After Phase 1 completes, those will instead point to the core
skills under `src/adzekit/skills/`.
