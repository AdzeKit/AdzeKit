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

## Frontmatter

All files use the same universal schema:

```yaml
---
id: unique-identifier
created_at: YYYY-MM-DD
updated_at: YYYY-MM-DD
tags: []
---
```

## Testing

Tests use `pytest` with a `workspace` fixture that creates a temporary vault in `tmp_path`. No mocks for file I/O.
