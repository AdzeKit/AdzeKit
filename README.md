# AdzeKit

Prehistoric tools, modern brains, future-proof productivity.

## Mission

Make productivity human in the age of AI. Protect Type 2 thinking -- the slow, deep, deliberate cognition that produces real insight. Help programmers survive the AI-driven input explosion.

A **loop** is any commitment that would continue to nag at you if you didn't write it down -- especially promises to other people.

## Two Things

**The Backbone** -- a specification for how your vault is organized. Folder layout, file naming, inline `#tags`. No YAML frontmatter -- just plain markdown. Any folder that follows the spec is a vault. See [backbone-spec/schema.md](backbone-spec/schema.md).

**The Package** -- Python tools that operate on any conforming vault. Point it at a folder and go.

```bash
export ADZEKIT_WORKSPACE=~/my-vault
adzekit today
```

## Getting Started

```bash
uv pip install -e ".[dev]"
uv run adzekit init ~/my-vault
uv run adzekit --vault ~/my-vault today
uv run adzekit --vault ~/my-vault add-loop "Send estimate" --who Alice --what "API estimate"
uv run adzekit --vault ~/my-vault status
uv run pytest
```

## Configuration

Settings come from environment variables (prefixed `ADZEKIT_`) or a `.env` file:

| Variable | Default | Purpose |
|----------|---------|---------|
| `ADZEKIT_WORKSPACE` | `~/adzekit` | Vault path |
| `ADZEKIT_GIT_REPO` | -- | Git remote URL (optional) |
| `ADZEKIT_GIT_BRANCH` | `main` | Branch to sync |

## Mantra

Files first, rituals second, AI third.
