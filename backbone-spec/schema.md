# AdzeKit Backbone Specification v1

A short, versioned contract. Any folder that conforms to this spec is an AdzeKit-compatible vault. The backbone is a specification, not a codebase.

## Vault Layout

```
<vault-root>/
  daily/
    YYYY-MM-DD.md
  loops/
    open.md
    closed/
      YYYY-WNN.md
  projects/
    active/
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
```

## File Encoding

All files are UTF-8 Markdown. No proprietary formats.

## Stock

**Path:** `stock/<project-slug>/`

Raw material that hasn't been shaped yet -- transcripts, PDFs, spreadsheets, exports, recordings. The name follows the woodworking metaphor: stock is the unworked lumber that the adze shapes into the finished piece.

Stock is **not tracked by git**. These files are often large, binary, or in proprietary formats -- none of which git handles well. Instead, `stock/` syncs via rclone to a cloud remote (Google Drive, SharePoint, S3, etc.). Set `ADZEKIT_RCLONE_REMOTE` to configure the remote.

Subdirectories inside `stock/` match project slugs so LLM adapters can find the raw material for a given project and summarize it into that project's `## Log`.

## Metadata

Files carry no YAML frontmatter. All metadata is derived from the filesystem and git:

- **Identity:** The file path is the unique identifier.
- **Timestamps:** Creation and modification dates come from git history.
- **Tags:** Use inline `#tags` anywhere in the document. A tag is any `#word` or `#hyphenated-word` token (kebab-case). For compound words always use hyphens: `#vector-search`, not `#vectorSearch` or `#vector_search`. Place tags wherever they read naturally -- after headings, in bullets, or on their own line.

### Tag conventions

Tags are a flat namespace. There is no tag registry, no controlled vocabulary, and no separate index file.

**Why no index?** A maintained tag list rots the moment someone forgets to update it. Instead, the tag index is computed on the fly by scanning every `.md` file for `#word` tokens -- the filesystem is the source of truth. Tooling can build an in-memory `dict[str, list[Path]]` in milliseconds, even at thousands of files.

**Why no namespacing?** Prefixes like `#p-alice` or `#t-machine-learning` add friction to typing and reading. In practice, tag types distinguish themselves naturally:

- **People:** `#alice-chen`, `#ryan-bondaria`
- **Topics:** `#vector-search`, `#machine-learning`
- **Clients/orgs:** `#citco`, `#nova`, `#otpp`
- **Reference IDs:** `#AR-000109761`

If programmatic classification is ever needed, the tooling layer can infer type from pattern (names vs concepts vs IDs) without burdening the writer.

**Contacts are just tags.** There is no separate contacts system. Mention `#firstname-lastname` wherever a person appears -- in daily notes, loops, project logs. Querying the tag index for that tag produces a complete interaction history across the vault.

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

```markdown
## [YYYY-MM-DD] Loop title

- **Who:** Person or group
- **What:** The commitment
- **Due:** YYYY-MM-DD
- **Status:** Open | Closed
- **Next:** Concrete next action
- **Project:** optional-project-slug
```

Closed loops move to `loops/closed/YYYY-WNN.md`.

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

Content goes here. Use [[wikilinks]] to connect to other notes.
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
# Weekly Review -- 2026 Week 07

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

## What This Spec Does Not Cover

- Where the vault lives (local, git, Dropbox -- user's choice)
- Which editor is used (Obsidian, VS Code, Vim -- all work)
- How tools are run (CLI, UI, scripts -- package concern)
- AI behavior (tool concern, not backbone concern)
- Link conventions, knowledge graphs, or indices (tool concern)
