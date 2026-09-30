# AdzeKit

Markdown habits for people and their agents.

A **shed** is a folder of Markdown that you, your AI agents, and your phone all
read and edit. It holds **records** (your days, commitments, projects, notes)
and **skills** (how you want recurring work done). Agents do the work; git
carries it between devices. The CLI has five commands, no dependencies, and no
AI. Read [PHILOSOPHY.md](PHILOSOPHY.md) for why.

## Start

```bash
uv tool install git+https://github.com/AdzeKit/AdzeKit
adzekit init ~/shed --remote git@github.com:you/shed.git   # private repo
adzekit sync
```

On every other computer, run the same `init` command. An empty folder gets a
clone of your shed. Then open the folder in any agent (Claude Code, Codex,
Cursor, Gemini CLI) and say "run daily start".

## Commands

| Command | Does |
|---|---|
| `adzekit init [PATH] [--remote URL] [--name NAME]` | Create, join, or refresh a shed. Safe to re-run. |
| `adzekit today` | Create today's note, carry unfinished intentions forward, sweep ticked loops. |
| `adzekit status` | One-screen health: loops open/overdue/stale, projects vs. cap. |
| `adzekit review` | Write this week's review scaffold with the decisions to make. |
| `adzekit sync` | Commit, rebase onto the remote, push. |

Inside a shed, a command acts on that shed. Anywhere else, it acts on every shed
registered on this machine; `-w NAME` picks one. Everything else (adding a loop,
logging, moving a project) is an ordinary edit to a Markdown file, made by you or
an agent.

## The shed

```text
shed/
├── AGENTS.md            the contract every agent reads (generated block + your notes)
├── CLAUDE.md, GEMINI.md import AGENTS.md
├── .adzekit             your limits: max_active_projects, max_daily_tasks, ...
├── daily/2026-09-29.md  ## Intention · ## Log · ## Reflection
├── loops/active.md      - [ ] (S) [2026-09-29] What I owe, to whom (2026-10-01)
├── loops/archive.md     ticked loops, grouped by the day they were swept
├── projects/*.md        active projects; backlog/ and archive/ for the rest
├── knowledge/*.md       durable notes, [[linked]] and #tagged
├── reviews/             weekly reviews and reports
└── skills/*.md          your repeatable procedures
```

Folders appear when they first get a file.

**What `init` owns.** `init` writes a marked block into `AGENTS.md`,
`CLAUDE.md`, `GEMINI.md`, `.gitignore`, and `.gitattributes`. The block is
generated from the same constants and settings the CLI uses, so the
instructions agents read always match the formats the code parses. Re-running
`init` (for example after an upgrade, or after changing `.adzekit`) rewrites
only those blocks. Everything outside them is yours. Starter skills are copied
once and are yours from then on.

## Skills

A skill is a Markdown procedure: *how* you want a recurring job done, written
once so any agent can do it the same way. `init` starts you with
`daily-start`, `daily-close`, `weekly-review`, and `capture`. To add one, drop
a file in `skills/`. Skills describe file formats, not CLI commands, so they
keep working whatever runtime reads them. When a skill needs email, chat, a CRM
or a calendar, it uses your agent's own tools.

## Several sheds

One system doesn't have to mean one repository. Data has owners: your employer
owns customer work, and you own the rest of your life. Keep a shed for each, with
the same format, the same skills habit, and the same CLI:

```bash
adzekit init ~/sheds/life --name life --remote git@github.com:you/life.git
adzekit init ~/sheds/work --name work --remote <your employer's approved git host>
adzekit status        # both sheds
adzekit -w work sync  # just one
```

Each shed's name is stored in its `.adzekit` file, so it travels to every device.
Each shed's `AGENTS.md` tells agents to keep records in the shed they belong to.
Cloud agents open one repository at a time, which enforces the boundary for you.
When something you learned at work generalizes, rewrite it without customer
detail into your life shed's `knowledge/`. That's the part you keep when you
change jobs.

## Sync

Your shed has to reach three kinds of client:

| Client | Examples | Sees the shed through |
|---|---|---|
| Local agents | Claude Code, Codex CLI, Cursor, Gemini CLI | the folder itself |
| Phone | Obsidian + Obsidian Git plugin; Working Copy on iOS | a git clone |
| Cloud agents | Claude Code on the web, Codex cloud | the hosted repository |

Git is the one channel all three understand, so a private git remote is the
hub. `adzekit sync` is built so it can run unattended:

- **Concurrent edits merge.** Record folders (`daily/`, `loops/`, `projects/`,
  `knowledge/`, `reviews/`) use git's `union` merge. When your phone and your
  laptop both append to today's log, both lines are kept. The one cost: if
  both change the *same* loop, you'll see both versions as two lines, and you
  delete one.
- **It never leaves a mess.** If git truly can't combine two changes (say, both
  devices rewrote the same skill), sync aborts, keeps your work committed
  locally, and names the file. The repository is never left mid-rebase.
- **Agents sync themselves.** `AGENTS.md` tells every agent to run
  `adzekit sync` before starting and after finishing. On your phone, turn on
  the Git plugin's auto pull and push.

Cloud agents usually work on a branch and open a pull request instead of
pushing to `main`. Merge it from your phone, and the next sync brings it home.

Two things to avoid:

- **Don't put the shed inside iCloud Drive, Dropbox, or Google Drive.** Those
  services sync the files under `.git` independently and can corrupt the
  repository. Git already does the syncing.
- **Keep raw material out of git.** Transcripts, PDFs, and exports go in
  `stock/`, which is ignored. Make `stock` a symlink into a synced drive folder
  (for example `ln -s ~/Library/CloudStorage/<drive>/shed-stock stock`), so the
  files sync through the drive, stay out of git, and are still readable by
  local agents. Only `stock/` lives in the drive; the repository never does.

## Development

```bash
uv pip install -e ".[dev]"
pytest -q && ruff check src tests
```

Versions before 1.0 (graph, drafts, MCP servers, Telegram gateway) are
available at the `legacy-v0` tag.
