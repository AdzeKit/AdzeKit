# AdzeKit

Prehistoric tools, modern brains, future-proof productivity.

## Mission

Make productivity human in the age of AI. Protect Type 2 thinking -- the slow, deep, deliberate cognition that produces real insight. Help knowledge workers survive the AI-driven input explosion without losing agency over their own work.

A **loop** is any commitment that would continue to nag at you if you didn't write it down -- especially promises to other people.

## Two Things

**The Backbone** -- a specification for how your shed is organized. Folder layout, file naming, inline `#tags`. No YAML frontmatter -- just plain markdown. Any folder that follows the spec is a shed. See [backbone-spec/schema.md](backbone-spec/schema.md).

**The Package** -- Python tools that operate on any conforming shed. Point it at a folder and go.

```bash
export ADZEKIT_SHED=~/my-shed
adzekit today
```

## Getting Started

### 1. Install AdzeKit

```bash
git clone https://github.com/AdzeKit/AdzeKit.git
cd AdzeKit
uv pip install -e ".[dev]"
```

### 2. Initialize your shed

```bash
uv run adzekit init ~/my-shed
export ADZEKIT_SHED=~/my-shed
```

This creates the backbone directory structure. Your shed is a plain folder -- edit files with any editor, sync with git, back up however you like.

### 3. Basic commands

```bash
adzekit today              # Open/create today's daily note
adzekit add-loop "Send estimate" --who Alice --what "API estimate"
adzekit status             # Show shed health summary
adzekit sweep              # Move completed loops to closed archive
```

### 4. Run tests

```bash
uv run pytest
```

## Architecture

```
+----------------------------------------------+
|  Skills (Claude Code commands in your shed)  |
+----------------------------------------------+
|  AI Layer (agent/)                           |
+----------------------------------------------+
|  MCP Servers (mcp/)                          |
+----------------------------------------------+
|  Feature Layer (modules/)                    |
+----------------------------------------------+
|  Access Layer (config, models, parser,       |
|                preprocessor, workspace)       |
+----------------------------------------------+
|  Backbone (your shed — plain markdown)       |
+----------------------------------------------+
```

**Access Layer** -- Reads and writes the backbone. All markdown I/O lives here.

**Feature Layer** (`modules/`) -- Loop lifecycle, WIP limits, git timestamps, tag scanning, export.

**MCP Servers** (`mcp/`) -- Expose backbone and Gmail operations as MCP tools for Claude Code and other LLM agents.

**AI Layer** (`agent/`) -- LLM client, tool registry, orchestrator. The agent can READ the backbone but CANNOT WRITE to it directly -- output goes to `drafts/`.

**Skills** -- Claude Code slash commands (markdown files) that orchestrate MCP tools and agent capabilities into repeatable workflows. Skills live in your shed, not in the package.

## Access Zones

The shed has two access zones that enforce human control:

| Zone | Directories | Who writes | Purpose |
|------|-------------|-----------|---------|
| **Backbone** | `daily/`, `loops/`, `projects/`, `knowledge/`, `reviews/`, `inbox.md` | Human only | Your real data -- plans, commitments, reflections |
| **Workbench** | `drafts/`, `stock/` | Agent-writable | Proposals awaiting review, raw materials |

When an AI agent wants to suggest a backbone change (new loop, triage summary, daily note), it writes a proposal to `drafts/`. You review and apply -- or discard. The human always decides.

## Skills & Claude Code Integration

AdzeKit skills are Claude Code [slash commands](https://docs.anthropic.com/en/docs/claude-code/slash-commands) that combine MCP tools with AI reasoning to automate productivity workflows. They live in your shed's `.claude/commands/` directory.

### How it works

1. **MCP servers** expose your backbone as structured tools (read projects, get loops, write drafts)
2. **Skills** are markdown files that tell Claude Code how to orchestrate those tools
3. **The backbone stays human-protected** -- skills can only write to `drafts/`
4. **You review everything** -- skills propose, you decide

### Included skill templates

| Skill | What it does |
|-------|-------------|
| `inbox-zero` | Classify, label, and triage up to 100 emails. Draft replies, propose loops. |
| `daily-start` | Pre-populate today's daily note from carried intentions and due loops. |
| `weekly-review` | Generate a review draft with pulse summary from the week's data. |
| `slack-digest` | Surface what matters from Slack channels, mentions, and discussions. |
| `asq-lookup` | Cross-reference Salesforce ARs against your shed for tracking gaps. |

### Setting up skills in your shed

Skills are templates in `src/adzekit/skills/`. To use them:

```bash
# Create the commands directory in your shed
mkdir -p ~/my-shed/.claude/commands

# Copy and personalize each skill
cp src/adzekit/skills/inbox-zero.md ~/my-shed/.claude/commands/inbox-zero.md
cp src/adzekit/skills/daily-start.md ~/my-shed/.claude/commands/daily-start.md
# ... etc.
```

Then add frontmatter to each command file:
```yaml
---
description: Short description for the command palette
argument-hint: Optional argument description
---
```

Personalize the skills for your workflow -- add your name to draft reply signatures, configure your priority Slack channels in `knowledge/role-context.md`, set up email pattern files, etc. Your shed is yours; the repo stays generic.

### MCP server setup

Add these to your `.claude/settings.json`:

```json
{
  "mcpServers": {
    "adzekit-backbone": {
      "command": "uv",
      "args": ["--directory", "/path/to/AdzeKit", "run", "adzekit-mcp-backbone"],
      "env": { "ADZEKIT_SHED": "/path/to/your/shed" }
    },
    "adzekit-gmail": {
      "command": "uv",
      "args": ["--directory", "/path/to/AdzeKit", "run", "adzekit-mcp-gmail"],
      "env": { "ADZEKIT_SHED": "/path/to/your/shed" }
    }
  }
}
```

Restart Claude Code to pick up the MCP servers.

## Configuration

Settings come from environment variables (prefixed `ADZEKIT_`) or the `.adzekit` config file in your shed:

| Variable | Default | Purpose |
|----------|---------|---------|
| `ADZEKIT_SHED` | `~/adzekit` | Shed path |
| `ADZEKIT_GIT_REPO` | -- | Git remote URL (optional) |
| `ADZEKIT_GIT_BRANCH` | `main` | Branch to sync |

Per-shed settings in `.adzekit`:

| Key | Default | Purpose |
|-----|---------|---------|
| `max_active_projects` | 3 | WIP cap for active projects |
| `max_daily_tasks` | 5 | Max intention items per daily note |
| `loop_sla_hours` | 24 | Hours before a loop is flagged |
| `stale_loop_days` | 7 | Days before a loop is flagged as stale |

## Core Principles

1. **Cap Work-in-Progress** -- Maximum 3 active projects. Maximum 5 daily tasks. No exceptions, only trade-offs.
2. **Close Every Loop** -- Every commitment gets a response within 24 hours. Silence is never acceptable.
3. **Protect Deep Work** -- Schedule uninterrupted blocks. Make calendar fragmentation visible.
4. **Review, Don't Accumulate** -- Weekly review is non-negotiable. Act, schedule, or close.
5. **Report Out Regularly** -- Weekly status to anyone waiting on you.

See [docs/concepts.md](docs/concepts.md) for the full philosophy.

## Mantra

Files first, rituals second, AI third.
