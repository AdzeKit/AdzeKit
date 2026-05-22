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
    soul.md                   # voice / values / non-negotiables / deep-work hours
    role-context.md           # facts (priority channels, identity, interests)
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
    INBOX.md                  # protocol queue: one line per pending draft
    <skill>-YYYY-MM-DD-HHMM-<host>.md  # filename schema with host suffix
    archive/                  # accepted/dismissed/gc'd drafts
      originals/              # originals preserved on accept (distill input)
    skill-proposals/          # /distill output: proposed new skills
    knowledge/                # per-entity capture drafts from /slack-capture
    <any other file>
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

One file per calendar day. Four canonical sections, always in this order:

```markdown
# 2026-05-22 Friday

## Triage
> Resolve each line before daily-close.
- [ ] OVERDUE 12d: Manulife KARL POC ticket → kill / defer / promote
- [ ] STALE 9d: aer-compliance → kill / defer / commit

## Intention
- [ ] (S) [2026-05-22] Get ARC an answer on batch inference costs <- due today
- [ ] (XS) [2026-05-20] Work AI Gateway data privacy talking point <- carried

## Log
- 09:00 Started ARC batch pricing research
- 10:30 Call with @alice re: MLflow migration timeline
- [x] (S) Responded to @bob on vector search sizing
- 14:00 Deep work: Model Lens feature store integration

## Reflection
- **Finished:** ARC sizing summary, vector-search reply
- **Blocked:** waiting on MLflow team's response
- **Tomorrow:** finish AI Gateway talking point

> End: Energy 3/5. 1 done, 1 open. Tomorrow: finish AI Gateway talking point.

> Sessions:
> - claude-code:7f3a 07:30-07:34 /daily-start -> drafts/daily-start-2026-05-22-0730-laptop.md
> - claude-code:8e22 14:00-14:18 /capture
```

### Sections

- **`## Triage`** — pre-populated context that *must* be resolved before daily-close. Overdue loops, stale projects, stale bench items. Each line is a one-decision question: kill / defer / promote / commit / keep / drop. Always present; empty body when nothing needs triage.
- **`## Intention`** — proposed intentions for the day, max 5 items. Carries from yesterday's Tomorrow line + open loops. WIP cap applies here only.
- **`## Log`** — timestamped bullets appended throughout the day via `/capture` or manual editing. Completed loops inline as `- [x]`.
- **`## Reflection`** — end-of-day summary: Finished / Blocked / Tomorrow. Filled at daily-close (or by hand).

### Bookends and footers

- `> End:` blockquote line — appended by daily-close. Energy score, done/open counts, tomorrow suggestion. The presence of `> End:` is how daily-close detects an already-closed day.
- `> Sessions:` blockquote footer — optional. Adapters append one line per agent invocation that touched the shed. See the per-runtime mapping below.

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

## Soul

**Path:** `knowledge/soul.md`

The shed's voice file. Contains voice, values, non-negotiables, and declared deep-work hours. Adapters load this file on every skill invocation. Human writes it; agents only read it.

```markdown
# Soul

## Voice
- Direct. No throat-clearing.
- Markdown over prose; tables over bullets when comparing.
- Cite files by path when proposing edits.

## Values
- Honest disagreement > polite agreement.
- Default to opinionated; soften only when asked.

## Non-negotiables
- Never write to backbone/ — propose to drafts/.
- Deep work hours are silent — no notifications during the declared window.

## Deep work hours
09:00-11:00 America/Edmonton
```

Sections are parsed by level-2 headings (`## Section Name`). Adapters may translate `Deep work hours` into runtime-specific scheduling (Hermes adapter writes a Hermes SOUL.md; cadence layer respects the window). The schema is *suggested*, not enforced — extra sections are ignored, missing sections produce empty values.

## Stock

**Path:** `stock/<project-slug>/`

Raw materials — transcripts, PDFs, recordings. Git-ignored, synced via rclone.

## Drafts

**Path:** `drafts/`

Agent proposals awaiting human review. Git-ignored, ephemeral.

### Filename schema

```
drafts/{skill}-YYYY-MM-DD-HHMM-{host}.md
```

The HHMM and host suffix minimize multi-machine git collisions when the shed is synced across devices. `{host}` is the first DNS label of `hostname`, sanitized to kebab-case (lowercase, only `[a-z0-9-]`).

### Provenance header

Every draft begins with an HTML-comment header — parseable but non-rendering, so it doesn't violate the `no YAML in backbone` rule (drafts are workbench, not backbone, but the comment form is friendlier to readers).

```
<!-- adzekit-draft
skill: inbox-triage
triggered: 2026-05-22T08:14:03-06:00
trigger: cron|user|manual
host: laptop
inputs:
  - knowledge/soul.md@a1b2c3d
  - loops/open.md@e4f5a6b
parent: drafts/inbox-triage-2026-05-21-0814-laptop.md
confidence: 0.85
summary: 14 emails, 3 reply drafts
hash: sha256:7f3a...
-->
```

- `inputs` lists relpath-from-shed with the short git SHA at read time (when available).
- `parent` links to the prior draft from the same skill, for lineage.
- `hash` is `sha256:` + first 16 hex chars of the body content — reproducibility witness.
- `confidence` (0.0–1.0) is optional; high-confidence drafts qualify for `adzekit drafts accept --auto`.

### INBOX queue

**Path:** `drafts/INBOX.md`

A single auto-maintained file listing every pending draft, one line per draft.

```markdown
# Draft Inbox

- [ ] 2026-05-22 08:14 inbox-triage · 14 emails, 3 reply drafts · `drafts/inbox-triage-2026-05-22-0814-laptop.md`
- [ ] 2026-05-22 07:30 daily-start · focus + 3 carried loops · `drafts/daily-start-2026-05-22-0730-laptop.md`
```

Mirrors the `loops/open.md` ↔ `loops/closed.md` pattern. Manipulated via:
- `adzekit drafts list` — show pending entries
- `adzekit drafts accept N` — promote draft #N to backbone; preserve original to `drafts/archive/originals/`
- `adzekit drafts dismiss N` — move draft #N to `drafts/archive/`
- `adzekit drafts gc` — archive stale drafts and clean orphan INBOX lines

### Archive

**Path:** `drafts/archive/`

Accepted, dismissed, or gc'd drafts. `drafts/archive/originals/` preserves the agent-emitted draft *before* any human edits at promotion time — the `/distill` skill reads this directory to detect repeated edit patterns and propose new skills.

### Other workbench paths

- `drafts/skill-proposals/` — output of `/distill`. Proposed new skills awaiting human review.
- `drafts/knowledge/<entity-slug>.md` — per-entity capture drafts from `/slack-capture`.
- `drafts/<skill>-watermark.md` — latest processed timestamp per source. Delete to force rescan.

### Batch patch pattern (legacy)

Skills producing many proposals may consolidate into a single patch file (`drafts/<skill>-patch-YYYY-MM-DD.md`) with per-file drafts and `cp` commands. The INBOX queue largely supersedes this pattern; new skills should emit a single review report instead.

## Daily-Note Session Footer (optional)

Daily notes accumulate a `> Sessions:` blockquote footer that records every agent session which touched the shed that day. The Hermes adapter writes Hermes session IDs; the Claude Code adapter writes Claude Code session identifiers. This is the *only* persistent record of agent activity at the day level.

```markdown
> End: ...

> Sessions:
> - hermes:abc123 08:14-08:42 /daily-start -> drafts/daily-start-2026-05-22-0814-laptop.md
> - hermes:def456 11:02-11:05 /capture
> - claude-code:session-7f3a 14:20-14:45 /weekly-review -> drafts/weekly-2026-W21-laptop.md
```

Adapters append one line on each invocation. The line format is `- <runtime>:<session-id> <start>-<end> /<skill>[ -> <draft-path>]`. Optional, but recommended for users who want session-level traceability without per-draft session pollution.

## What This Spec Does Not Cover

- Where the shed lives (local, git, Dropbox)
- Which editor (Obsidian, VS Code, Vim)
- How tools run (CLI, skills, scripts)
- AI behavior beyond graph/ write access
