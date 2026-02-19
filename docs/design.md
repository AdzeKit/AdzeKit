# AdzeKit Package Architecture

For the backbone spec: [../backbone-spec/schema.md](../backbone-spec/schema.md).

## Layers

```
+---------------------------------------------+
|  Feature Layer (modules/)                    |
+---------------------------------------------+
|  Access Layer (config, models, parser,       |
|                preprocessor, workspace)       |
+---------------------------------------------+
|  Backbone (user's vault)                     |
+---------------------------------------------+
```

**Access Layer** -- Knows the backbone schema. All markdown I/O lives here. `config.py` resolves the vault path. `parser.py` reads/writes markdown. `models.py` defines data structures. `preprocessor.py` loads files into typed objects.

**Feature Layer** (`modules/`) -- Implements commands using access layer primitives. `loops.py` manages the loop lifecycle. `wip.py` enforces WIP limits.

## Vault Discovery

1. Explicit `Settings(workspace=...)` in code
2. `ADZEKIT_WORKSPACE` environment variable
3. `.env` file
4. Default: `~/adzekit`

When `ADZEKIT_GIT_REPO` is set, `sync_workspace()` clones or pulls, `commit_workspace()` pushes.

## Metadata

Files carry no YAML frontmatter. Identity comes from file paths, timestamps from git, and tags from inline `#tags` in the document body. Tags use kebab-case for compound words (`#vector-search`). See the backbone spec for details.

### Tags at scale

Tags are a flat, unregistered namespace. There is no `tags.json` or `tags.md` to maintain -- a maintained index drifts the moment someone writes a new tag and forgets to update the list. Instead, the tag index is always computed from the filesystem: scan every `.md` file for `#word` tokens and build `dict[str, list[Path]]` in memory. This stays fast even at thousands of files because it's a single-pass regex over small text files.

Contacts, topics, clients, and reference IDs all use the same `#kebab-case` tag syntax. No namespace prefixes -- types are self-evident from context (names vs concepts vs alphanumeric IDs). If tooling ever needs to classify tags programmatically, it can infer type from pattern without adding structure to the writing surface.

The tag index supports: contact lookup ("where have I mentioned `#alice-chen`?"), co-occurrence analysis (which tags cluster together), orphan detection (tags used only once, likely typos), and autocomplete for CLI or editor integrations.

## Project Structure

Every project is a single markdown file with three sections: **Context**, **Log**, and **Notes**.

- **Context** is the stable *why*: purpose, stakeholders, success criteria, constraints. It gives anyone enough background to pick the file up cold. It rarely changes after the first week.
- **Log** is the chronological *what*: dated events, decisions, blockers, and task checkboxes all interleaved in reverse-chronological order. Keeping tasks and narrative in one stream avoids the drift that happens when a separate task list stops matching reality.
- **Notes** is the unstructured *everything else*: reference links, scratch calculations, meeting snippets, half-formed ideas. It exists so Context stays clean and Log stays chronological.

The parser extracts checklist items (`- [ ]` / `- [x]`) from the Log section to compute project progress.

## Stock

The `stock/` directory holds raw artifacts -- transcripts, PDFs, spreadsheets, recordings -- that support projects but don't belong in the curated markdown backbone. The name comes from the woodworking metaphor: stock is unworked lumber that the adze shapes into a finished piece.

Stock is git-ignored because these files are typically large, binary, or in proprietary formats that git handles poorly. Instead, `stock/` syncs to a cloud remote via rclone. The `ADZEKIT_RCLONE_REMOTE` setting points to the remote (Google Drive, SharePoint, S3, etc.). `sync_stock()` pulls from the remote, `push_stock()` pushes local changes up.

Subdirectories inside `stock/` match project slugs (`stock/otpp-vectorsearch/`). This gives LLM adapters a clear input path: read from `stock/<slug>/`, summarize into the project's `## Log`.

## Estimation

AdzeKit uses t-shirt sizes -- `(S)`, `(M)`, `(L)`, `(XL)` -- appended to tasks for relative effort. No story points or hour tracking; just enough signal to eyeball whether a week is overloaded. Tasks can also carry inline deadlines as `(YYYY-MM-DD)` when tied to hard dates. Both annotations are optional. Estimation tooling will parse these markers to surface workload summaries and forecast throughput.

## Testing

Tests use `pytest` with a `workspace` fixture that creates a temporary vault in `tmp_path`. No mocks for file I/O.
