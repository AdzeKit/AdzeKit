# AdzeKit Backbone Specification v1

A short, versioned contract. Any folder that conforms to this spec is an AdzeKit-compatible shed. The backbone is a specification, not a codebase.

## Shed Layout

```
<shed-root>/
  .adzekit                # marker + config file
  daily/
    YYYY-MM-DD.md
  loops/
    open.md
    closed/
      YYYY-WNN.md
  projects/               # .md files here are active projects
    <slug>.md
    backlog/
      <slug>.md
    archive/
      <slug>.md
  knowledge/
    <slug>.md
  reviews/
    YYYY-WNN.md
  inbox.md
  stock/                  # git-ignored, synced separately
    <project-slug>/
      <any file>
  drafts/                 # git-ignored, agent-writable
    <any file>
```

## Access Zones

The shed has two access zones:

### Backbone (human-owned, read-only for agents)

Everything above except `stock/` and `drafts/`. The backbone is the human's domain -- agents can read it but never write to it. All backbone changes go through the human via the CLI or editor.

Backbone directories: `daily/`, `loops/`, `projects/`, `knowledge/`, `reviews/`, `inbox.md`.

### Workbench (agent-writable)

Two directories where the agent can freely create and modify files:

- **`stock/`** -- Raw material that hasn't been shaped yet (transcripts, PDFs, exports). Synced via rclone.
- **`drafts/`** -- Agent-generated proposals awaiting human review. When the agent wants to suggest a new loop, inbox item, or any backbone change, it writes a proposal here. The human reviews and applies (or discards) the draft.

Both directories are git-ignored.

## Marker / Config File

**Path:** `.adzekit`

Every initialized shed contains a `.adzekit` file at the root. It identifies the directory as an AdzeKit shed, declares the backbone spec version, and holds per-shed tuning parameters:

```
backbone_version = 1
max_active_projects = 3
max_daily_tasks = 5
loop_sla_hours = 24
stale_loop_days = 7
rclone_remote = gdrive:adzekit
```

| Key | Default | Purpose |
|-----|---------|---------|
| `backbone_version` | 1 | Spec version (read-only, set by `init`) |
| `max_active_projects` | 3 | WIP cap: max projects in `projects/` root |
| `max_daily_tasks` | 5 | Max intention items per daily note |
| `loop_sla_hours` | 24 | Hours before a loop is flagged as approaching SLA |
| `stale_loop_days` | 7 | Days before a loop is flagged as stale |
| `rclone_remote` | *(empty)* | rclone base path for stock/drafts sync (e.g. `gdrive:adzekit`) |
| `git_repo` | *(empty)* | Git remote URL for shed sync |
| `git_branch` | `main` | Git branch for shed sync |

All configuration lives in this single file. Edit values directly to tune the shed. `adzekit init` writes defaults; subsequent `init` calls preserve your edits. `adzekit setup-sync` writes the `rclone_remote` key here.

**Why a marker?** Without it, any mis-configured `ADZEKIT_SHED` path would silently create a full directory tree in the wrong place. The marker is a gate: `adzekit init` writes it, and every other command checks for it before operating. If the marker is missing, the CLI prints an error and exits instead of creating files.

The version number allows future spec revisions to detect and migrate older sheds. There is no migration logic today -- version 1 is the only version.

## File Encoding

All files are UTF-8 Markdown. No proprietary formats.

## Stock

**Path:** `stock/<project-slug>/`

Raw material that hasn't been shaped yet -- transcripts, PDFs, spreadsheets, exports, recordings. The name follows the woodworking metaphor: stock is the unworked lumber that the adze shapes into the finished piece.

Stock is **not tracked by git**. These files are often large, binary, or in proprietary formats -- none of which git handles well. Instead, `stock/` syncs via rclone to a cloud remote (Google Drive, SharePoint, S3, etc.). Set `rclone_remote` in `.adzekit` (or run `adzekit setup-sync`) to configure the remote.

Subdirectories inside `stock/` match project slugs so LLM adapters can find the raw material for a given project and summarize it into that project's `## Log`.

## Drafts

**Path:** `drafts/`

Agent-generated proposals awaiting human review. The agent writes here when it wants to suggest changes to the backbone (new loops, inbox items, triage summaries, etc.). The human reviews each draft and either applies it to the backbone or discards it.

Drafts are **not tracked by git**. They are ephemeral by nature -- once applied or discarded, they can be deleted.

## Metadata

Files carry no YAML frontmatter. All metadata is derived from the filesystem, git, and inline annotations:

- **Identity:** The file path is the unique identifier.
- **File timestamps:** Creation and modification dates come from git history. The `git_age` module queries these on demand for staleness tracking in projects and reviews.
- **Loop timestamps:** Loops carry an inline `[YYYY-MM-DD]` date. The meaning of this date changes over a loop's lifecycle:
  - In `open.md`, the date is the **creation date** -- stamped when the loop is first added.
  - When `adzekit sweep` moves a closed loop to `closed.md`, the date is **overwritten with the closure date** (today).
  - Git history records both transitions: `git log -p -- loops/open.md` shows when the line appeared (creation) and disappeared (sweep); `git log -p -- loops/closed.md` shows when it arrived (closure). The inline date in each file gives the same information without requiring git archaeology.
  - This dual-use works because a loop only ever lives in one file at a time, and the relevant question differs by context: "how old is this open commitment?" vs "when did I close this?"
- **Tags:** Use inline `#tags` anywhere in the document. A tag is any `#word` or `#hyphenated-word` token (kebab-case). Tags are **case-insensitive** -- `#Citco`, `#citco`, and `#CITCO` all resolve to the same tag (`citco`). For compound words always use hyphens: `#vector-search`, not `#vectorSearch` or `#vector_search`. Place tags wherever they read naturally -- after headings, in bullets, or on their own line.

### Tag conventions

Tags are a flat, case-insensitive namespace. There is no tag registry, no controlled vocabulary, and no separate index file. All tags are lowercased at extraction, so writers never need to worry about casing consistency.

**Why no index?** A maintained tag list rots the moment someone forgets to update it. Instead, the tag index is computed on the fly by scanning every `.md` file for `#word` tokens -- the filesystem is the source of truth. Tooling can build an in-memory `dict[str, list[Path]]` in milliseconds, even at thousands of files.

**Why no namespacing?** Prefixes like `#p-alice` or `#t-machine-learning` add friction to typing and reading. In practice, tag types distinguish themselves naturally:

- **People:** `#alice-chen`, `#ryan-bondaria`
- **Topics:** `#vector-search`, `#machine-learning`
- **Clients/orgs:** `#citco`, `#nova`, `#otpp`
- **Reference IDs:** `#AR-000109761`

If programmatic classification is ever needed, the tooling layer can infer type from pattern (names vs concepts vs IDs) without burdening the writer.

**Contacts are just tags.** There is no separate contacts system. Mention `#firstname-lastname` wherever a person appears -- in daily notes, loops, project logs. Querying the tag index for that tag produces a complete interaction history across the shed.

## Daily Notes

**Path:** `daily/YYYY-MM-DD.md`

One file per calendar day. The date is the filename.

```markdown
# 2026-02-16 Monday

## Morning: Intention
- [ ] Top priority:
- [ ] Close loop:

## Log

## Evening: Reflection
- **Finished:**
- **Blocked:**
- **Tomorrow:**
```

## Loops

A loop is any commitment to another person that requires closure.

**Path:** `loops/open.md`

Loops use a flat checklist format with an inline created date in square brackets:

```markdown
- [ ] (SIZE) [YYYY-MM-DD] Loop title (DUE-DATE)
```

- `(SIZE)` -- optional t-shirt size (`XS`, `S`, `M`, `L`, `XL`)
- `[YYYY-MM-DD]` -- the date the loop was created
- `(YYYY-MM-DD)` at end -- optional due date / deadline

Example:

```markdown
# Open Loops

- [ ] (XS) [2026-02-17] Follow up with Alice on API estimate
- [ ] (M) [2026-02-18] Start column mapping work with Jas (2026-03-01)
- [ ] (S) [2026-02-19] Get Ovintiv docs for gateway diagnosis
```

### Closing loops

Mark a loop done by flipping `[ ]` to `[x]` in `open.md`, then run `adzekit sweep`. Sweep:

1. Removes all `[x]` lines from `open.md`.
2. Overwrites each loop's inline `[YYYY-MM-DD]` with today's date (the **closure date**).
3. Appends them to `closed.md`.

```markdown
- [x] (L) [2026-02-23] Gartner DSML Survey (2026-02-18)
```

The original creation date is not lost -- it is preserved in git history as the commit that first added the line to `open.md`. The inline date shifts meaning from "when was this opened?" to "when was this closed?" because the file it lives in already answers which state it's in.

### Loop identity and git traceability

Loops have no stable identifier (no UUID, no sequential number). Their identity is the combination of their title text and creation date. This is a deliberate simplicity trade-off:

- **Reconstructing lifecycle from git:** `git log -p --all -S "Loop title"` will find every commit that added or removed a line containing that title, across all files. This recovers creation, edits, and closure timestamps from commit metadata. The `git_age` module could be extended to automate this.
- **Fragility:** If a user edits a loop's title (e.g. fixing a typo, adding detail), the old and new versions are different strings. Git diff will show the change within a single commit, but programmatic matching across commits requires fuzzy string comparison -- which AdzeKit does not currently do.
- **Mitigation:** In practice this works because (a) loops are short-lived commitments, not long-running records, (b) most edits happen before any state transition, and (c) the cost of a broken link in the closed archive is low. If stable identity ever becomes important (e.g. for metrics dashboards), the format can be extended with an inline ID like `{#a1b2c3}` without breaking existing loops.

## Projects

**Path:** `projects/active/<slug>.md`, `projects/backlog/<slug>.md`, `projects/archive/<slug>.md`

One markdown file per project. The slug is the filename. Move the file between `active/`, `backlog/`, and `archive/` to change its state.

Every project has exactly three sections:

```markdown
# Project Title #tag

## Context
Why this project exists, who it serves, what success looks like, and any
constraints or dependencies. Write just enough that someone (including
future-you) can pick the file up cold and understand the stakes.

## Log
- YYYY-MM-DD: Reverse-chronological entries -- decisions, progress,
  blockers, and tasks. The most recent entry is always on top.
- [ ] Pending tasks live here too, interleaved with dated events.

## Notes
Freeform scratch space. Paste reference links, sketch ideas, capture
meeting snippets -- anything that supports the project but doesn't
belong in the running Log.
```

**Why these three and only three?**

- **Context** pins down *why* the project matters once and stays mostly
  stable. Without it every re-read starts with "wait, what was this?"
- **Log** captures *what happened and what's next* in time order. Mixing
  tasks and events in a single stream keeps the narrative honest --
  priorities and progress live side by side.
- **Notes** is the pressure-relief valve. Anything that doesn't fit the
  structured sections goes here instead of cluttering Context or Log.

WIP limit: maximum 3 files in `active/` at any time.

## Knowledge Notes

**Path:** `knowledge/<slug>.md`

Evergreen notes. The slug is the filename.

```markdown
# Topic Title

#topic

Content goes here. Use standard [markdown links](../knowledge/other-note.md) to connect to other notes.
```

## Inbox

**Path:** `inbox.md`

Zero-structure capture bucket:

```markdown
# Inbox

- [YYYY-MM-DD] Raw thought or commitment
```

## Reviews

**Path:** `reviews/YYYY-WNN.md`

Weekly review output. One file per ISO week.

```markdown
# 2026 Week 07 Review (2026-02-15)

## Open Loops

## Active Projects

## Decisions
- Kill, defer, or commit?

## Reflection
- What drained me this week?
- What energized me?
- What will I stop doing next week?
```

## Task Markers

| Marker | Meaning |
|--------|---------|
| `- [ ]` | Open task |
| `- [x]` | Closed task |

Tasks support optional inline annotations for sizing and deadlines:

- **T-shirt sizes** -- append `(S)`, `(M)`, `(L)`, or `(XL)` to signal relative effort. No story points, no hour estimates -- just enough to eyeball a week's capacity.
- **Deadlines** -- append a date in `(YYYY-MM-DD)` when a task is tied to a hard date.

Both annotations are optional and can be combined:

```markdown
- [ ] Draft API proposal (M)
- [ ] Submit compliance report (L) (2026-03-20)
- [ ] Quick fix for login bug (S)
```

Estimation tooling will be built around these sizes to surface workload and forecast throughput.

## Export

AdzeKit uses pandoc to convert markdown to `.docx`. This is the primary path for sharing documents with stakeholders who work in Word or Google Docs.

- `adzekit export <file.md>` converts any markdown file to `.docx` alongside the source.
- `adzekit export <file.md> -o path/to/output.docx` writes to a specific path.
- `adzekit poc-init <slug> --docx` generates a POC template and converts it in one step.

For Google Docs: export to `.docx`, then upload to Google Drive which auto-converts on import.

Pandoc is an external dependency (`brew install pandoc`) and is not bundled with AdzeKit.

## What This Spec Does Not Cover

- Where the shed lives (local, git, Dropbox -- user's choice)
- Which editor is used (Obsidian, VS Code, Vim -- all work)
- How tools are run (CLI, UI, scripts -- package concern)
- AI behavior (tool concern, not backbone concern)
- Link conventions, knowledge graphs, or indices (tool concern)
