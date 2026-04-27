# AdzeKit Backbone Specification v1

A short, versioned contract. Any folder that conforms to this spec is an AdzeKit-compatible shed.

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
  stock/                      # git-ignored, synced via rclone
    <project-slug>/
  drafts/                     # git-ignored, agent-writable
    <any file>
```

## Access Zones

| Zone | Directories | Who writes | Purpose |
|------|-------------|-----------|---------|
| **Backbone** | `daily/`, `loops/`, `projects/`, `knowledge/`, `reviews/`, `skills/` | Human | Your real data |
| **Workbench** | `drafts/`, `stock/` | Agent | Proposals and raw materials |

Agents read the backbone but never write to it. All agent output goes to `drafts/`. The human reviews and applies — or discards.

## Marker / Config

**Path:** `.adzekit`

```
backbone_version = 1
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
- AI behavior (tool concern, not backbone concern)
