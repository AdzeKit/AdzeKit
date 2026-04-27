# AdzeKit Backbone Specification v2

A short, versioned contract. Any folder that conforms to this spec is an AdzeKit-compatible shed. The backbone is a specification, not a codebase.

**v2 changes from v1:** Added `graph/` compiled layer (git-tracked, agent-maintained). Added typed relationship syntax for knowledge notes. Updated access zones.

## Shed Layout

```
<shed-root>/
  .adzekit                # marker + config file
  daily/
    YYYY-MM-DD.md
  loops/
    active.md
    backlog.md
    archive.md
    archive/
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
  bench.md
  graph/                  # git-tracked, agent-maintained compiled graph
    entities.md
    relations.md
    index.md
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

Backbone directories: `daily/`, `loops/`, `projects/`, `knowledge/`, `reviews/`, `bench.md`.

### Graph (compiled layer, agent-maintained, git-tracked)

**`graph/`** -- The compiled knowledge graph. Built by `adzekit graph build` (or the `graph-update` skill) from all backbone content. Agent-written but git-tracked so the compiled graph travels with the shed.

- **`graph/entities.md`** -- Entity registry: every discovered person, project, concept, tool, organization, loop, and event.
- **`graph/relations.md`** -- Typed relationship index: every edge in the graph, grouped by relation type.
- **`graph/index.md`** -- Summary: entity counts, most-connected nodes, orphans.

The graph is compiled metadata, not raw content. Humans should not edit it manually -- run `adzekit graph build` to regenerate.

### Workbench (agent-writable, git-ignored)

Two directories where the agent can freely create and modify files:

- **`stock/`** -- Raw material that hasn't been shaped yet (transcripts, PDFs, exports). Synced via rclone.
- **`drafts/`** -- Agent-generated proposals awaiting human review. When the agent wants to suggest a new loop, bench item, or any backbone change, it writes a proposal here. The human reviews and applies (or discards) the draft.

Both directories are git-ignored.

## Marker / Config File

**Path:** `.adzekit`

Every initialized shed contains a `.adzekit` file at the root. It identifies the directory as an AdzeKit shed, declares the backbone spec version, and holds per-shed tuning parameters:

```
backbone_version = 2
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

Agent-generated proposals awaiting human review. The agent writes here when it wants to suggest changes to the backbone (new loops, bench items, triage summaries, etc.). The human reviews each draft and either applies it to the backbone or discards it.

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
- **Tags:** Use inline `#tags` anywhere in the document. A tag is any `#word` or `#hyphenated-word` token (kebab-case). Tags are **case-insensitive** -- `#Acme`, `#acme`, and `#ACME` all resolve to the same tag (`acme`). For compound words always use hyphens: `#vector-search`, not `#vectorSearch` or `#vector_search`. Place tags wherever they read naturally -- after headings, in bullets, or on their own line.

### Tag conventions

Tags are a flat, case-insensitive namespace. There is no tag registry, no controlled vocabulary, and no separate index file. All tags are lowercased at extraction, so writers never need to worry about casing consistency.

**Why no index?** A maintained tag list rots the moment someone forgets to update it. Instead, the tag index is computed on the fly by scanning every `.md` file for `#word` tokens -- the filesystem is the source of truth. Tooling can build an in-memory `dict[str, list[Path]]` in milliseconds, even at thousands of files.

**Why no namespacing?** Prefixes like `#p-alice` or `#t-machine-learning` add friction to typing and reading. In practice, tag types distinguish themselves naturally:

- **People:** `#alice-chen`, `#ryan-bondaria`
- **Topics:** `#vector-search`, `#machine-learning`
- **Clients/orgs:** `#acme`, `#nova`, `#globex`
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

A loop is any commitment to another person that requires closure. Loops use the same active/backlog/archive lifecycle as projects.

**Paths:**
- `loops/active.md` -- loops you are actively working on
- `loops/backlog.md` -- future commitments not currently top of mind
- `loops/archive.md` -- completed loops (flat log)
- `loops/archive/YYYY-WNN.md` -- weekly archive snapshots (optional)

Loops use a flat checklist format with an inline created date in square brackets:

```markdown
- [ ] (SIZE) [YYYY-MM-DD] Loop title (DUE-DATE)
```

- `(SIZE)` -- optional t-shirt size (`XS`, `S`, `M`, `L`, `XL`)
- `[YYYY-MM-DD]` -- the date the loop was created
- `(YYYY-MM-DD)` at end -- optional due date / deadline

Example:

```markdown
# Active Loops

- [ ] (XS) [2026-02-17] Follow up with Alice on API estimate
- [ ] (M) [2026-02-18] Start column mapping work with Jas (2026-03-01)
- [ ] (S) [2026-02-19] Get Acme docs for gateway diagnosis
```

Backlog loops follow the same format but live in `backlog.md`:

```markdown
# Backlog Loops

- [ ] (M) [2026-02-20] Research new API framework options (2026-06-01)
- [ ] (S) [2026-02-21] Plan team offsite logistics
```

Move loops between `active.md` and `backlog.md` by cutting and pasting lines. When a backlog loop becomes urgent, promote it to active. When an active loop can wait, demote it to backlog.

### Closing loops

Mark a loop done by flipping `[ ]` to `[x]` in `active.md`, then run `adzekit sweep`. Sweep:

1. Removes all `[x]` lines from `active.md`.
2. Overwrites each loop's inline `[YYYY-MM-DD]` with today's date (the **closure date**).
3. Appends them to `archive.md`.

```markdown
- [x] (L) [2026-02-23] Gartner DSML Survey (2026-02-18)
```

The original creation date is not lost -- it is preserved in git history as the commit that first added the line to `active.md`. The inline date shifts meaning from "when was this opened?" to "when was this closed?" because the file it lives in already answers which state it's in.

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

### Typed Relationship Syntax

Knowledge notes declare entity relationships using bold headers on their own lines. This is the only frontmatter-free way to encode typed edges that `adzekit graph build` can parse.

```markdown
# Vector Search

#vector-search #concept

**is-a:** [[retrieval-method]], [[similarity-search]]
**part-of:** [[retrieval-augmented-generation]]
**used-by:** [[fourseasons-rag]], [[td-fraudai]]
**relates-to:** [[knowledge-graphs]], [[feature-store]]
**developed-by:** [[pinecone]], [[weaviate]]

Approximate nearest-neighbour search over dense embedding vectors...
```

Format: `**<relation-type>:** [[target1]], [[target2]]` or plain comma-separated text.

`[[WikiLink]]` syntax anywhere in the body (outside typed headers) auto-generates a `relates-to` edge.

### Entity Ontology

Every entity has exactly one canonical type. When a tag or note is ambiguous, apply these rules in order:

| Type | When to use | Tag / source pattern |
|------|-------------|----------------------|
| `person` | Named individual | `#firstname-lastname` (two+ hyphen-separated words) |
| `organization` | Company, team, client, institution | `#org-name` in any file; `#organization` hint tag |
| `project` | Active/backlog/archived work item | Filename in `projects/` |
| `concept` | Abstract idea, pattern, methodology | Knowledge note without `#tool` tag |
| `tool` | Software product, platform, API, service | Knowledge note with `#tool` tag |
| `loop` | Tracked commitment | Entry in `loops/active.md` |
| `event` | Specific time-bound occurrence | Knowledge note with `#event` tag |

**Disambiguation:** If a name is both a company and a product (e.g. Databricks), create one knowledge note and tag it with both `#organization` and `#tool`. The graph builder uses the note's tags to pick the canonical type (tool wins over organization when both are present).

### Relationship Ontology

All relationships are directed. Inverses are not stored separately.

| Relation | Direction | Description | Example |
|----------|-----------|-------------|---------|
| `is-a` | specific → general | Taxonomic subsumption. Transitive. | `genie is-a databricks-tool` |
| `part-of` | component → whole | Compositional membership | `genie part-of databricks` |
| `uses` | consumer → provider | Dependency or employment | `td-fraudai uses databricks` |
| `relates-to` | symmetric | General association; auto-generated from `[[WikiLinks]]` | `vector-search relates-to knowledge-graphs` |
| `owned-by` | artifact → owner | Project/work owned by person/org | `td-fraudai owned-by ryan-bondaria` |
| `assigned-to` | loop → person | Commitment owed to/from a person; extracted from loop `--who` | `send-estimate assigned-to alice-chen` |
| `mentioned-in` | entity → document | Entity appears in a project/note | `databricks mentioned-in td-fraudai` |
| `developed-by` | artifact → creator | Tool/concept created by person/org | `claude developed-by anthropic` |
| `contradicts` | A → B | Logical/practical opposition (symmetric in practice) | `data-mesh contradicts centralized-platform` |
| `extends` | extension → base | Builds on or specialises | `software-3-0 extends software-2-0` |

Use the most specific relation that applies. Fall back to `relates-to` only when no typed relation fits.

## Bench

**Path:** `bench.md`

The bench is the workbench where you lay out agent proposals and decide
what to do with each one. In woodworking, the bench is the
decision-making surface -- you bring pieces here to evaluate, route, or
discard. In AdzeKit, the bench surfaces pending items from `drafts/` for
human processing.

The bench replaced the original `inbox.md` (a freeform capture bucket
that went unused because daily `## Log` already handles quick capture
and loops handle commitments directly).

```markdown
# Bench

## Pending
- [ ] [2026-03-05 14:30] inbox-zero -- 13 actions, 2 drafts (drafts/inbox-zero-2026-03-05-1430.md)
- [ ] [2026-03-05 17:00] slack-digest -- 7 DMs, 4 threads (drafts/slack-digest-2026-03-05-1700.md)

## Quick Capture
- [2026-03-05] Unrouted thought that needs a home
```

### Processing rules

1. The agent appends an entry to `## Pending` whenever it writes a new
   file to `drafts/`. The entry links to the draft file and summarizes
   what needs human action.
2. The human marks items `[x]` after processing (copying loops, reading
   starred emails, applying proposals).
3. `adzekit sweep` clears checked items from `## Pending` and optionally
   deletes the corresponding draft file.
4. `## Quick Capture` retains the original inbox role for the rare
   orphan thought, but it is a secondary purpose.

### CLI: `adzekit cull`

`adzekit cull` scans `drafts/` for files not yet listed in `## Pending`
and appends entries for them. It is idempotent -- running it twice
produces no duplicates.

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
- AI behavior beyond graph/ write access (tool concern, not backbone concern)
