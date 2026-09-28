# Roadmap

## Now: make the small product coherent

- Use `workspace`, `workflow`, and `proposal` in every new public interface.
- Route CLI and MCP behavior through the transport-neutral `Workspace` API.
- Keep initialization empty and make optional conventions opt-in.
- Preserve version 2 workspaces without requiring a migration.
- Reduce base dependencies and move integrations behind extras.

## Next: finish the boundary

- Split the 1,600-line CLI into a small core command group and extension groups.
- Add `workspace_*` MCP tool names with temporary `shed_*` aliases.
- Move Gmail, Calendar, Telegram, DOCX, launchd, graph, and Claude-specific code
  into independently installable extension packages.
- Define an optimistic-concurrency token before enabling proposal acceptance in
  multi-user web applications.
- Replace copied runtime skill documents with a single workflow contract plus
  adapter-owned execution instructions.

## Later: improve portability

- Publish a JSON Schema for snapshots and proposals.
- Add conformance fixtures for Python, MCP, and future TypeScript clients.
- Support storage backends through an interface only after the filesystem API is
  stable and measured.

## Legacy features

Daily rituals, project WIP limits, loops, knowledge graphs, cadence, Gmail,
Calendar, Telegram, DOCX export, and the Claude adapter remain supported for
existing users. They are extensions, not milestones that define the core.
