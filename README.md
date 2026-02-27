# AdzeKit

Prehistoric tools, modern brains, future-proof productivity.

## Mission

Make productivity human in the age of AI. Protect Type 2 thinking -- the slow, deep, deliberate cognition that produces real insight. Help programmers survive the AI-driven input explosion.

A **loop** is any commitment that would continue to nag at you if you didn't write it down -- especially promises to other people.

## Two Things

**The Backbone** -- a specification for how your shed is organized. Folder layout, file naming, inline `#tags`. No YAML frontmatter -- just plain markdown. Any folder that follows the spec is a shed. See [backbone-spec/schema.md](backbone-spec/schema.md).

**The Package** -- Python tools that operate on any conforming shed. Point it at a folder and go.

```bash
export ADZEKIT_SHED=~/my-shed
adzekit today
```

## Getting Started

```bash
uv pip install -e ".[dev]"
uv run adzekit init ~/my-shed
uv run adzekit --shed ~/my-shed today
uv run adzekit --shed ~/my-shed add-loop "Send estimate" --who Alice --what "API estimate"
uv run adzekit --shed ~/my-shed status
uv run pytest
```

## Configuration

Settings come from environment variables (prefixed `ADZEKIT_`) or a `.env` file:

| Variable | Default | Purpose |
|----------|---------|---------|
| `ADZEKIT_SHED` | `~/adzekit` | Shed path |
| `ADZEKIT_GIT_REPO` | -- | Git remote URL (optional) |
| `ADZEKIT_GIT_BRANCH` | `main` | Branch to sync |

## Mantra

Files first, rituals second, AI third.
