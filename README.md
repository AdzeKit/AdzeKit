# AdzeKit

Markdown habits for people and their agents.

A **shed** is a folder of Markdown that you, your AI agents, and your phone all
read and edit. It holds two things: **records** (your days, commitments,
projects, and notes) and **skills** (how you want recurring work done). The
agent does the work against them; a tiny CLI and git keep the mechanics honest.

The CLI has no dependencies, makes no AI calls, and never touches the network
(except `git`, when you run `sync`). Read [PHILOSOPHY.md](PHILOSOPHY.md) for the
reasoning; the short version is: plain files are the source of truth, one
`AGENTS.md` instructs every agent, and agents edit while git remembers.

## Install

```bash
uv tool install git+https://github.com/AdzeKit/AdzeKit   # or: pipx install ...
adzekit init ~/shed
```

## The shed

```text
shed/
├── AGENTS.md            instructions every agent reads
├── CLAUDE.md, GEMINI.md one-line imports of AGENTS.md
├── .adzekit             limits: max_active_projects, max_daily_tasks, ...
│
│   # records — your state
├── daily/2026-09-28.md  ## Intention (≤5) · ## Log · ## Reflection
├── loops/active.md      - [ ] (S) [2026-09-28] What I owe, to whom (2026-10-01)
├── loops/archive.md     closed loops, grouped by sweep date
├── projects/*.md        active projects; backlog/ and archive/ for the rest
├── knowledge/*.md       durable notes, [[linked]] and #tagged
├── reviews/2026-W40.md  weekly reviews
│
│   # skills — your repeatable work
└── skills/*.md          procedures any agent can follow
```

Every file is ordinary Markdown with no required frontmatter. The folder says
what state a project is in; dates are written inline.

## Skills: repeatable work

A skill is a plain-Markdown procedure — *how* you want a recurring job done,
written once so any agent replays it the same way. `init` ships four starters:

| Skill | What it does |
|---|---|
| `daily-start` | Build today's note: triage due loops, choose ≤5 intentions |
| `daily-close` | Tick what's done, capture new loops, reflect, sweep |
| `weekly-review` | Walk every stale loop and quiet project to a decision |
| `capture` | Turn a messy dump (thread, notes, memo) into the right lines |

Tell any agent "run daily start" and it reads `skills/daily-start.md` and
follows it. Add your own by dropping a numbered Markdown file in `skills/` —
that's the whole mechanism. Skills that need email, chat, Salesforce, or
calendars lean on your agent's own tools; the shed just holds the procedure.

## A day at the CLI

The CLI does the mechanical parts a skill would otherwise spell out:

```bash
adzekit today                       # create today's note, carrying unfinished intentions
adzekit log "Demoed MCP to CN"      # append to today's Log
adzekit loop add "Send Ana the estimate" --size S --due 2026-10-01
adzekit loop                        # numbered list with age and due flags
adzekit loop close 3                # by number or unique text
adzekit loop sweep                  # move ticked loops to the archive
adzekit status                      # one-screen health check
adzekit review                      # scaffold this week's review
adzekit project new acme-poc        # refuses past the active cap (--force to override)
adzekit project move acme-poc archive
adzekit sync                        # git commit, pull --rebase, push
```

The shed is found from `--workspace`, then `$ADZEKIT_WORKSPACE`, then the folder
you're standing in, then `~/.config/adzekit/config`.

## Across agents

`AGENTS.md` is the single source of instructions. Codex, Cursor, and other tools
that follow the AGENTS.md convention read it directly. Claude Code and Gemini
CLI read their own file, which `init` writes as a one-line `@AGENTS.md` import.
Put runtime-specific notes below that line.

## Across devices

The shed is a git repository. `adzekit sync` on a laptop, plus a git-capable
Markdown app on a phone (Obsidian with the Obsidian Git plugin, or Working Copy
on iOS), keeps them in step. Obsidian understands `[[wikilinks]]`, `#tags`, and
checkboxes natively, so the phone needs no AdzeKit code at all. Raw material
(transcripts, PDFs) goes under `stock/`, which stays out of git.

## Python

```python
from datetime import date
from adzekit import Workspace, loops

ws = Workspace.find()               # or Workspace("/path/to/shed")
for loop in loops.open_loops(ws):
    print(loop.title, loop.age(date.today()))
```

## Coming from 0.x

`adzekit init <existing-shed>` adds `AGENTS.md`, starter skills, and any missing
folders. It never overwrites a file. Then move what's in your `CLAUDE.md` into
the `## About me` section of `AGENTS.md`, and make `CLAUDE.md` just `@AGENTS.md`.

| 0.x | 1.0 |
|---|---|
| `daily-start`, `daily-close` | `today`, plus `skills/daily-*.md` |
| `add-loop`, `sweep` | `loop add`, `loop sweep` |
| `weekly-review` | `review`, plus `skills/weekly-review.md` |
| `graph`, `drafts`, `gateway`, `mcp`, `insight`, `distill`, `export`, launchd cadence | removed; see the `legacy-v0` tag |

Existing `.adzekit` settings, `ADZEKIT_SHED`, `--shed`, and the `shed =` global
config keep working.

## Development

```bash
uv pip install -e ".[dev]"
pytest -q && ruff check src tests
```
