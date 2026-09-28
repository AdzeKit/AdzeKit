# Simplification review

## Decision

AdzeKit is a **portable Markdown workspace with a proposal inbox**.

Its core loop is:

```text
capture human context -> let tools read it -> propose a change -> human decides
```

Everything else—CLI commands, MCP, Claude Code, Telegram, Gmail, graph building,
cadence, and document export—is an optional interface or extension.

## What made the project hard to communicate

The repository presented four products at once: a personal operating philosophy,
a filesystem specification, a large productivity CLI, and a Claude-oriented
agent system. Terms such as “shed,” “backbone,” “workbench,” “stock,” “loops,”
and “skills” all appeared before a reader encountered the basic user loop.
The metaphor was memorable but raised the cost of explaining the product.

The README also claimed a local web UI and agent command that are not registered
by the current CLI. Those claims made the package boundary unclear. The roadmap
said the UI was done, while the source tree contained no web application.

## Portability findings

- The Markdown data is genuinely portable.
- The Python parsing and workflow modules do not call an LLM.
- MCP is a useful runtime-neutral bridge, but its public names and setup docs use
  `shed_*` and point specifically at Claude settings.
- Skill documents say they are runtime-neutral while several prescribe Claude
  slash commands, Claude sub-agent behavior, or host-specific tools.
- `Settings` can discover a global workspace, which is convenient for a CLI but
  unsuitable as the primary API for servers handling more than one workspace.
- The only coherent agent write boundary is excellent: agents propose to
  `drafts/`; people promote to human-owned files. That should be the headline.

## Web findings

The domain code is synchronous filesystem code, which is acceptable for local
and small web applications, but it previously exposed parser dataclasses and
text-encoded JSON through transport modules. A web handler had to know which
internal module to call and how to serialize dates, enums, paths, and errors.

The base install also pulled in MCP and DOCX libraries even when an application
only needed Markdown operations. Framework dependencies should not live in the
core package, and AdzeKit should not own a web server.

## Changes made

- Added `adzekit.Workspace`, an explicit-root, transport-neutral facade.
- Added a versioned, JSON-safe `snapshot()` for agents and web handlers.
- Added safe read methods and one `propose()` mutation that stays in `drafts/`.
- Added path validation for knowledge-note lookup.
- Made MCP and DOCX dependencies optional and added the neutral `adzekit-mcp`
  executable name while retaining the old entry point.
- Defined a four-rule agent contract and a framework-agnostic web example.
- Reframed “shed” as legacy/internal vocabulary; public communication uses
  “workspace.” Existing config, commands, and files remain compatible.

## Recommended next cuts

1. Split the CLI into command modules; keep `cli.py` as registration only.
2. Make MCP call `Workspace` instead of duplicating serialization logic.
3. Rename MCP tools to `workspace_*`, keeping `shed_*` aliases for one release.
4. Move Gmail, Calendar, Telegram, Claude SDK, DOCX, and launchd code into extras
   or separately versioned adapters.
5. Rewrite skills as input/output contracts. Put runtime execution details only
   in adapter directories.
6. Choose three primary concepts—workspace, proposal, workflow—and introduce
   specialized terms only where the feature requires them.
7. Add optimistic concurrency (content hash or revision) before supporting
   accepting proposals from multi-user web applications.

## Compatibility policy

This simplification does not require a storage migration. `.adzekit`,
`ADZEKIT_SHED`, `Settings.shed`, `shed_*` MCP tools, and the current CLI remain
valid compatibility surfaces. New code should prefer `Workspace(path)` and the
word “workspace.”
