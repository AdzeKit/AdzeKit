# AdzeKit Package Architecture

For the backbone spec: [../backbone-spec/schema.md](../backbone-spec/schema.md).

## Layers

```
+---------------------------------------------+
|  AI Layer (agent/)                           |
+---------------------------------------------+
|  Feature Layer (modules/)                    |
+---------------------------------------------+
|  Access Layer (config, models, parser,       |
|                preprocessor, workspace)       |
+---------------------------------------------+
|  Backbone (user's shed)                      |
+---------------------------------------------+
```

**Access Layer** -- Knows the backbone schema. All markdown I/O lives here. `config.py` resolves the shed path. `parser.py` reads/writes markdown. `models.py` defines data structures. `preprocessor.py` loads files into typed objects.

**Feature Layer** (`modules/`) -- Implements commands using access layer primitives. `loops.py` manages the loop lifecycle. `wip.py` enforces WIP limits. `git_age.py` queries git for file-level timestamps. `tags.py` scans for inline `#tags`.

**AI Layer** (`agent/`) -- LLM client, tool registry, and orchestrator. The agent can READ the backbone but CANNOT WRITE to it. Agent output goes to `drafts/` and `stock/` (the workbench).

## Shed Discovery

1. Explicit `Settings(shed=...)` in code
2. `ADZEKIT_SHED` environment variable
3. `.env` file
4. Default: `~/adzekit`

When `ADZEKIT_GIT_REPO` is set, `sync_shed()` clones or pulls, `commit_shed()` pushes.

## Access Zones

The shed has two access zones:

- **Backbone** (human-owned): `daily/`, `loops/`, `projects/`, `knowledge/`, `reviews/`, `inbox.md`. The agent reads but never writes.
- **Workbench** (agent-writable): `stock/` (raw materials) and `drafts/` (proposals awaiting human review). Both are git-ignored.

When the agent wants to suggest a backbone change (new loop, inbox item, etc.), it writes a proposal to `drafts/`. The human reviews and applies or discards.

## Metadata

Files carry no YAML frontmatter. Identity comes from file paths, timestamps from git, and tags from inline `#tags` in the document body. Tags use kebab-case for compound words (`#vector-search`). See the backbone spec for details.

### Timestamps

Two timestamp mechanisms coexist for different reasons:

- **File-level timestamps** (projects, reviews, knowledge notes) come from git history. The `git_age` module queries `git log` for creation and last-modified dates per file. This works because each of these is its own file with stable git history.
- **Loop timestamps** are inline `[YYYY-MM-DD]` dates. Loops live in a shared file (`open.md`) that gets rewritten on every sweep, which destroys `git blame` history for individual lines. Inline dates survive rewrites and make loop age visible at a glance.

The `status` command surfaces both: loop ages from inline dates, project staleness from git.

#### Loop date lifecycle

The inline `[YYYY-MM-DD]` date has a dual meaning depending on which file the loop is in:

| File | Date meaning | Set by |
|------|-------------|--------|
| `open.md` | Creation date | `add-loop` CLI or manual entry |
| `closed.md` | Closure date | `sweep` command (overwrites with today) |

This works because the relevant question is different in each context. In `open.md` you want to know "how long has this been sitting here?" -- the creation date answers that. In `closed.md` you want to know "when did I actually close this?" -- the closure date answers that.

The creation date is not destroyed: git history preserves it. `git log -p -- loops/open.md` shows every commit that added or removed lines, so the original creation commit is always recoverable. The sweep commit itself records both sides: the line disappearing from `open.md` (with its creation date) and appearing in `closed.md` (with its closure date).

#### Identity and the rename problem

Loops have no stable identifier -- no UUID, no auto-incrementing number. Identity is the title string plus its date. This is a deliberate trade-off:

**What works:** If a user never edits a loop's title, `git log -p --all -S "title text"` reconstructs the full lifecycle: creation commit, any intermediate rewrites, and the closure commit. The `git_age` module could be extended to automate this kind of loop archaeology.

**What breaks:** If a user changes "Follow up with Alice" to "Follow up with Alice on the API estimate", git sees a line removed and a different line added. Within a single commit this is fine (git shows it as a modification), but across commits, programmatic tools cannot reliably match the old string to the new one without fuzzy comparison.

**Why this is acceptable:** Loops are meant to be short-lived commitments (hours to days, not months). Most title edits happen right after creation, before any state transitions. The closed archive is a reference log, not an audit trail -- if a link between an open and closed loop is lost because of a rename, the practical cost is negligible.

**Escape hatch:** If stable identity ever becomes important (e.g. for cycle-time metrics or compliance tracking), the format can be extended with an inline hash like `{#a1b2}` after the title. The parser and `format_loop` would need a one-line addition, and existing loops without IDs would still parse correctly. This is deferred because the added friction is not worth the benefit for most sheds.

### Tags at scale

Tags are a flat, case-insensitive, unregistered namespace. All tags are lowercased at extraction (`extract_tags` calls `.lower()`), so `#Citco` and `#citco` always match. There is no `tags.json` or `tags.md` to maintain -- a maintained index drifts the moment someone writes a new tag and forgets to update the list. Instead, the tag index is always computed from the filesystem: scan every `.md` file for `#word` tokens and build `dict[str, list[Path]]` in memory. This stays fast even at thousands of files because it's a single-pass regex over small text files.

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

## Drafts

The `drafts/` directory is the agent's output area. When the agent wants to propose a backbone change -- a new loop, an inbox item, a triage summary -- it writes a proposal file here. The human reviews each draft and either applies it (copying content into the appropriate backbone file) or discards it.

Drafts are git-ignored and ephemeral. They are not part of the backbone spec.

## Estimation

AdzeKit uses t-shirt sizes -- `(S)`, `(M)`, `(L)`, `(XL)` -- appended to tasks for relative effort. No story points or hour tracking; just enough signal to eyeball whether a week is overloaded. Tasks can also carry inline deadlines as `(YYYY-MM-DD)` when tied to hard dates. Both annotations are optional. Estimation tooling will parse these markers to surface workload summaries and forecast throughput.

## Export

`adzekit export <file>` converts any markdown file to `.docx` via pandoc. This is the standard path for sharing POC documents, proposals, or project summaries with stakeholders who expect Word/Google Docs format. Pandoc is an external dependency (not bundled) and must be installed on the host.

The `poc-init` command also accepts `--docx` to generate the POC template and convert it in one step.

For Google Docs: export to `.docx`, then upload -- Google Drive auto-converts `.docx` on import with full fidelity.

## Testing

Tests use `pytest` with a `workspace` fixture that creates a temporary shed in `tmp_path`. No mocks for file I/O.
