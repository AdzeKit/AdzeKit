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

## Project Structure

Every project is a single markdown file with three sections: **Context**, **Log**, and **Notes**.

- **Context** is the stable *why*: purpose, stakeholders, success criteria, constraints. It gives anyone enough background to pick the file up cold. It rarely changes after the first week.
- **Log** is the chronological *what*: dated events, decisions, blockers, and task checkboxes all interleaved in reverse-chronological order. Keeping tasks and narrative in one stream avoids the drift that happens when a separate task list stops matching reality.
- **Notes** is the unstructured *everything else*: reference links, scratch calculations, meeting snippets, half-formed ideas. It exists so Context stays clean and Log stays chronological.

The parser extracts checklist items (`- [ ]` / `- [x]`) from the Log section to compute project progress.

## Testing

Tests use `pytest` with a `workspace` fixture that creates a temporary vault in `tmp_path`. No mocks for file I/O.
