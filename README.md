# AdzeKit

Prehistoric tools, LLM-disrupted world.

An adze shapes wood by removing what doesn't belong. AdzeKit shapes your workday the same way — cap the work, close the loops, protect the deep hours.

## What It Is

**The Backbone** — a spec for organizing your work as plain markdown. Any folder that follows it is a *shed*. See [backbone-spec/schema.md](backbone-spec/schema.md).

**The Package** — Python tools that operate on any conforming shed.

**The Skills** — Claude Code slash commands that automate workflows. Skills live in your shed, not the package.

## Install

```bash
git clone https://github.com/AdzeKit/AdzeKit.git
cd AdzeKit
uv pip install -e ".[dev]"
```

## Quick Start

```bash
adzekit init ~/my-shed           # Create a shed
export ADZEKIT_SHED=~/my-shed    # Point to it

adzekit today                    # Open today's daily note
adzekit add-loop "Send estimate" # Track a commitment
adzekit status                   # Shed health at a glance
adzekit sweep                    # Archive completed loops
adzekit tags                     # List all #tags
```

## Five Principles

1. **Cap work-in-progress.** 3 active projects. 5 daily tasks. No exceptions, only trade-offs.
2. **Close every loop.** Every commitment gets a response within 24 hours. Silence is never acceptable.
3. **Protect deep work.** One 2-hour uninterrupted block daily. Non-negotiable.
4. **Review, don't accumulate.** Weekly review: act, schedule, or close. No hoarding.
5. **System comes to you.** Morning briefing arrives automatically. Evening close pre-fills itself. You decide, not remember.

## Architecture

```
Skills      Claude Code commands in your shed
AI Layer    LLM reads backbone, writes to drafts/ only
Features    Loop lifecycle, WIP limits, tags, git timestamps
Access      Config, parser, models — all markdown I/O
Backbone    Your shed — plain markdown, git-synced
```

The shed has two zones: the **backbone** (human-owned: `daily/`, `loops/`, `projects/`, `knowledge/`, `reviews/`) and the **workbench** (agent-writable: `drafts/`, `stock/`). AI proposes, you decide.

## Skills

Skills are Claude Code slash commands registered in `.claude/commands/`. They point to full skill definitions in `skills/`.

| Skill | What it does |
|-------|-------------|
| `/daily-start` | Morning briefing with focus line, carried tasks, stale draft alerts |
| `/daily-close` | Evening wrap-up — pre-fill reflection, sweep loops, auto-commit |
| `/log` | Quick-capture a timestamped entry to today's note |
| `/inbox-zero` | Classify, label, triage email. Draft replies, propose loops. |
| `/slack` | Digest + knowledge extraction + unread actions in one pass |
| `/weekly-review` | Generate review from loops, projects, and daily logs |
| `/loop-momentum` | Cross-reference loops against email, Slack, Jira for closure evidence |
| `/asq-lookup` | Cross-reference Salesforce ARs against shed for tracking gaps |

## Docs

- [Backbone Spec](backbone-spec/schema.md) — the contract your shed follows
- [Philosophy](docs/philosophy.md) — why these principles, why this design
- [Roadmap](docs/roadmap.md) — what's done, what's next

## Mantra

Files first. Rituals second. AI third.
