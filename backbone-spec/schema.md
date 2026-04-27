# AdzeKit Backbone Specification v2

A short, versioned contract. Any folder that conforms to this spec is an AdzeKit-compatible shed.

**v2 changes from v1:** Added `graph/` compiled layer (git-tracked, agent-maintained). Added typed relationship syntax for knowledge notes. Updated access zones.

## Shed Layout

```
<shed-root>/
  .adzekit                    # marker + config
  daily/
    YYYY-MM-DD.md
  loops/
    active.md
    backlog.md
    archive.md
    archive/
      YYYY-WNN.md             # weekly snapshots (optional)
  projects/
    <slug>.md                 # active projects live at root
    backlog/
      <slug>.md
    archive/
      <slug>.md
  knowledge/
    <slug>.md
  reviews/
    YYYY-WNN.md
  skills/                     # skill definitions (human-editable)
    <name>.md
  graph/                      # compiled knowledge graph (git-tracked, agent-maintained)
    entities.md
    relations.md
    index.md
  stock/                      # git-ignored, synced via rclone
    <project-slug>/
  drafts/                     # git-ignored, agent-writable
    <any file>
```

## Access Zones

| Zone | Directories | Who writes | Git-tracked | Purpose |
|------|-------------|-----------|-------------|---------|
| **Backbone** | `daily/`, `loops/`, `projects/`, `knowledge/`, `reviews/`, `skills/` | Human | Yes | Your real data |
| **Graph** | `graph/` | Agent (CLI) | Yes | Compiled entity-relationship index |
| **Workbench** | `drafts/`, `stock/` | Agent | No | Proposals and raw materials |

Agents read the backbone but never write to it. All agent output goes to `drafts/`. The human reviews and applies — or discards. The graph is the exception: agent-compiled, git-tracked as permanent computed metadata.

## Marker / Config

**Path:** `.adzekit`

```
backbone_version = 2
max_active_projects = 3
max_daily_tasks = 5
loop_sla_hours = 24
stale_loop_days = 7
rclone_remote = gdrive:adzekit
```

The marker identifies a directory as a shed. Every command checks for it before operating. `adzekit init` writes it; subsequent `init` calls preserve your edits.

## File Encoding

All files are UTF-8 Markdown. No proprietary formats, no YAML frontmatter.

## Metadata

- **Identity:** file path
- **Timestamps:** git history (creation, modification)
- **Loop dates:** inline `[YYYY-MM-DD]` (survives file rewrites)
- **Tags:** inline `#kebab-case` tokens, case-insensitive, no registry

---

## Daily Notes

**Path:** `daily/YYYY-MM-DD.md`

One file per calendar day.

```markdown
# 2026-04-09 Wednesday

> Focus: finish ARC batch sizing, review knowledge patch

- [ ] (S) [2026-04-09] Get ARC an answer on batch inference costs <- due today
- [ ] (XS) [2026-04-07] Work AI Gateway data privacy talking point <- carried

- 09:00 Started ARC batch pricing research
- 10:30 Call with @alice re: MLflow migration timeline
- [x] (S) Responded to @bob on vector search sizing
- 14:00 Deep work: Model Lens feature store integration

> End: Energy 3/5. 1 done, 1 open. Tomorrow: finish ARC sizing.
```

**Structure:**
- `> Focus:` — blockquote bookend. 2-3 word focus from yesterday's Tomorrow or top loop.
- Task list — proposed intentions, max 5 items.
- Log entries — timestamped bullets, appended throughout the day via `/log` or manual editing. Completed loops inline as `- [x]`.
- `> End:` — blockquote bookend. Energy score, done/open count, tomorrow items.

The bookends replace formal sections. They're faster to write and scan.

## Loops

A loop is any commitment that would nag at you if you didn't write it down — especially promises to other people.

**Paths:**
- `loops/active.md` — top-of-mind commitments
- `loops/backlog.md` — future commitments
- `loops/archive.md` — completed loops (flat log)

**Format:**
```markdown
- [ ] (SIZE) [YYYY-MM-DD] Loop title (DUE-DATE)
```

- `(SIZE)` — optional: `XS`, `S`, `M`, `L`, `XL`
- `[YYYY-MM-DD]` — creation date (in active), closure date (in archive)
- `(YYYY-MM-DD)` at end — optional due date

**Closing loops:** Mark `[x]` in active.md, run `adzekit sweep`. Sweep removes checked lines, overwrites the inline date with today, appends to archive.md.

**Identity:** No UUIDs. Identity is title + date. `git log -p --all -S "title"` recovers the full lifecycle. This works because loops are short-lived commitments, not long-running records.

## Projects

**Path:** `projects/<slug>.md` (active), `projects/backlog/`, `projects/archive/`

One file per project. Maximum 3 active at any time.

```markdown
# Project Title #tag

## Context
Why this exists, who it serves, what success looks like.

## Log
- YYYY-MM-DD: Reverse-chronological. Decisions, progress, blockers, tasks.
- [ ] Pending tasks interleaved with dated events.

## Notes
Freeform scratch. Links, sketches, meeting snippets.
```

**Why three sections:** Context pins down *why* once. Log captures *what happened* in time order. Notes is the pressure-relief valve so the other two stay clean.

## Knowledge Notes

**Path:** `knowledge/<slug>.md`

Evergreen notes that grow as you learn.

```markdown
# Topic Title

#topic #related-tags

Content. Use [markdown links](../knowledge/other-note.md) to connect notes.

**Event (YYYY-MM-DD):** Dated entries appended as knowledge accumulates.
```

### Typed Relationship Syntax

Declare entity relationships as bold headers on their own lines — no YAML, parseable by `adzekit graph build`:

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

Format: `**<relation-type>:** [[Target]], [[Target2]]` or comma-separated plain text.

`[[WikiLink]]` anywhere else in the body auto-generates a `relates-to` edge.

## Knowledge Graph

**Path:** `graph/`

The compiled entity-relationship index. Built by `adzekit graph build` from all backbone content. Git-tracked so the graph travels with the shed.

- `graph/entities.md` — entity registry by type
- `graph/relations.md` — typed relationship index
- `graph/index.md` — summary: counts, top nodes, orphans

Do not edit manually. Regenerate with `adzekit graph build`.

### Entity Ontology

Every entity has one canonical type. When ambiguous, apply these rules in order:

| Type | When to use | Detection |
|------|-------------|-----------|
| `person` | Named individual | `#firstname-lastname` (2+ hyphen-separated segments) |
| `organization` | Company, team, client, institution | `#org-name` + `#organization` hint tag |
| `project` | Active/backlog/archived work item | Filename in `projects/` |
| `concept` | Abstract idea, pattern, methodology | Knowledge note without `#tool` tag |
| `tool` | Software product, platform, API, service | Knowledge note with `#tool` tag |
| `loop` | Tracked commitment | Entry in `loops/active.md` |
| `event` | Time-bound occurrence | Knowledge note with `#event` tag |

**Disambiguation:** If ambiguous between Organization and Tool (e.g. Databricks), tag the knowledge note with both `#organization` and `#tool`. The graph builder uses `#tool` as canonical when both are present.

### Relationship Ontology

All relationships are directed. Use the most specific type that applies; fall back to `relates-to` only when nothing more precise fits.

| Relation | Direction | Semantics | Example |
|----------|-----------|-----------|---------|
| `is-a` | specific → general | Taxonomic subsumption. Transitive. | `genie is-a databricks-tool` |
| `part-of` | component → whole | Compositional membership | `genie part-of databricks` |
| `uses` | consumer → provider | Dependency or employment | `td-fraudai uses databricks` |
| `relates-to` | symmetric | General association; auto from `[[WikiLinks]]` | `vector-search relates-to knowledge-graphs` |
| `owned-by` | artifact → owner | Accountability | `td-fraudai owned-by ryan-bondaria` |
| `assigned-to` | loop → person | Commitment target | `send-estimate assigned-to alice-chen` |
| `mentioned-in` | entity → document | Co-occurrence | `databricks mentioned-in td-fraudai` |
| `developed-by` | artifact → creator | Provenance | `claude developed-by anthropic` |
| `contradicts` | A → B | Opposition (treat as symmetric) | `data-mesh contradicts centralized-platform` |
| `extends` | extension → base | Augmentation | `software-3-0 extends software-2-0` |

## Reviews

**Path:** `reviews/YYYY-WNN.md`

Weekly review output. One file per ISO week.

```markdown
# 2026 Week 15 Review (2026-04-13)

## Active Loops
[List each: acted on / overdue / upcoming]

## Active Projects
[Table: slug, last activity, status, this week summary]

## Decisions
- What am I saying no to?
- What trade-offs am I hiding from myself?

## Reflection
- What drained me?
- What energized me?
- What will I stop doing next week?
```

## Skills

**Path:** `skills/<name>.md`

Skill definitions that Claude Code slash commands point to. Skills are full markdown documents describing a workflow: prerequisites, shed access patterns, step-by-step instructions, safety rules.

Commands in `.claude/commands/` are thin pointers:
```yaml
---
description: Short description
argument-hint: Optional args
---
Read and execute the skill defined in `{SHED}/skills/<name>.md`.
```

This keeps skill logic in the shed (committable, editable, diffable) while registering them as slash commands.

## Tags

Tags are `#word` or `#hyphenated-word` tokens anywhere in a document. Case-insensitive (`#Acme` = `#acme`). No registry — the filesystem is the source of truth.

Tag types distinguish themselves naturally:
- People: `#alice-chen`
- Topics: `#vector-search`
- Clients: `#acme`
- References: `#AR-000109761`

## Stock

**Path:** `stock/<project-slug>/`

Raw materials — transcripts, PDFs, recordings. Git-ignored, synced via rclone.

## Drafts

**Path:** `drafts/`

Agent proposals awaiting human review. Git-ignored, ephemeral.

**Batch patch pattern:** Skills producing many proposals consolidate into a single patch file (`drafts/<skill>-patch-YYYY-MM-DD.md`) with per-file drafts and `cp` commands. One file to review, batch decisions to make.

**Watermarks:** `drafts/<skill>-watermark.md` tracks latest processed timestamp per source. Delete to force rescan.

## What This Spec Does Not Cover

- Where the shed lives (local, git, Dropbox)
- Which editor (Obsidian, VS Code, Vim)
- How tools run (CLI, skills, scripts)
- AI behavior beyond graph/ write access
