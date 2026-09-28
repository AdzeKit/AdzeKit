# Philosophy

AdzeKit exists to keep collaboration with software legible.

The problem is not that people need a more elaborate productivity system. The
problem is that tools can read and generate more than a person can inspect. If
their work disappears into chat history, hidden memory, or a vendor database,
the person loses context and control.

AdzeKit uses ordinary files and a review queue to prevent that.

## Three principles

### 1. Keep the source ordinary

Human context lives in Markdown. It can be opened with any editor, searched
without AdzeKit, versioned with Git, copied to another machine, and read years
after the current agent runtime disappears.

AdzeKit may index or transform those files, but derived data is never the only
copy. Portability is a property of the storage format, not a promise made by an
adapter.

### 2. Separate proposals from decisions

Tools may read the workspace. They put suggested changes in `drafts/`. A person
accepts, edits, or dismisses them.

This boundary matters more than model choice, prompting style, or orchestration.
It makes automation reversible and gives generated work an obvious place to
wait. Small, explicitly authorized actions may write directly; generation does
not silently become truth.

### 3. Keep the core smaller than its integrations

The core knows Markdown, workspace paths, and proposals. It does not know
Claude, Gmail, Telegram, FastAPI, launchd, or a particular knowledge method.
Those are optional extensions.

A feature belongs in the core only when a workspace becomes non-portable or
unsafe without it. Everything else should be possible to remove.

## Consequences

- **Local-first, not local-only.** A workspace can be served by a web app or
  synced through any mechanism. Local files remain the source of truth.
- **Agent-neutral.** Any runtime that can read context and submit a proposal can
  use AdzeKit. Sub-agents and MCP are capabilities, not requirements.
- **No mandatory method.** Daily notes, projects, loops, reviews, graphs, and
  cadence are useful conventions. They are not the definition of AdzeKit.
- **No invented certainty.** Proposals identify their workflow and source. The
  person should be able to see what was generated and decide whether it belongs.
- **Progressive complexity.** A new workspace starts nearly empty. Features add
  structure when the person chooses them; initialization does not manufacture a
  project, review, graph, or knowledge base.

## The product test

When considering a change, ask:

1. Does it make the files more portable?
2. Does it make generated work easier to review or reverse?
3. Can it live outside the core?

If the first two answers are no, or the third is yes, the change probably does
not belong in the core.

## What AdzeKit is not

AdzeKit is not an agent runtime, a task-management doctrine, an autonomous
memory system, a web framework, or an integration bundle. It can support those
things without owning them.

The name can keep the woodworking metaphor. The architecture does not require
the user to learn it.
