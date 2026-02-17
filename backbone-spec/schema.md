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
      <slug>/
        README.md
        tasks.md
        notes.md
    backlog/
      <slug>/
    archive/
      <slug>/
  knowledge/
    <slug>.md
  reviews/
    YYYY-WNN.md
  inbox.md
```

## File Encoding

All files are UTF-8 Markdown. No proprietary formats.

## Frontmatter

Every file may begin with a YAML frontmatter block. When present, it uses this universal schema:

```yaml
---
id: unique-identifier
created_at: YYYY-MM-DD
updated_at: YYYY-MM-DD
tags:
  - tag-one
  - tag-two
---
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique identifier for the file |
| `created_at` | date | yes | Date the file was created |
| `updated_at` | date | no | Date of last meaningful edit |
| `tags` | list | no | Freeform tags |

No file type has special frontmatter fields. The schema is the same everywhere.

## Daily Notes

**Path:** `daily/YYYY-MM-DD.md`

One file per calendar day. The `id` is the date string.

```markdown
---
id: "2026-02-16"
created_at: 2026-02-16
updated_at: 2026-02-16
tags: []
---

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

**Path:** `projects/active/<slug>/`, `projects/backlog/<slug>/`, `projects/archive/<slug>/`

Each project is a directory containing:

| File | Purpose |
|------|---------|
| `README.md` | Context and goals |
| `tasks.md` | Checklist of work items |
| `notes.md` | Freeform project notes |

```markdown
---
id: "project-slug"
created_at: 2026-02-16
updated_at: 2026-02-16
tags: []
---

# Project Title

## Context

## Goals
```

WIP limit: maximum 3 projects in `active/` at any time.

## Knowledge Notes

**Path:** `knowledge/<slug>.md`

Evergreen notes. The `id` is the slug. `updated_at` tracks review freshness.

```markdown
---
id: "topic-slug"
created_at: 2026-02-16
updated_at: 2026-02-16
tags:
  - topic
---

# Topic Title

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
---
id: "2026-W07"
created_at: 2026-02-16
updated_at: 2026-02-16
tags: []
---

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
| `- [x]` | Completed task |

## What This Spec Does Not Cover

- Where the vault lives (local, git, Dropbox -- user's choice)
- Which editor is used (Obsidian, VS Code, Vim -- all work)
- How tools are run (CLI, UI, scripts -- package concern)
- AI behavior (tool concern, not backbone concern)
- Link conventions, knowledge graphs, or indices (tool concern)
