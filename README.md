# AdzeKit

Prehistoric tools, modern brains, future-proof productivity.

## Mission

Make productivity human in the age of AI. Protect Type 2 thinking -- the slow, deep, deliberate cognition that produces real insight. Help knowledge workers survive the AI-driven input explosion without losing agency over their own work.

A **loop** is any commitment that would continue to nag at you if you didn't write it down -- especially promises to other people.

## Two Things

**The Backbone** -- a specification for how your shed is organized. Folder layout, file naming, inline `#tags`, and typed knowledge-graph relationships. No YAML frontmatter -- just plain markdown. Any folder that follows the spec is a shed. See [backbone-spec/schema.md](backbone-spec/schema.md).

**The Package** -- Python tools that operate on any conforming shed. Point it at a folder and go.

```bash
export ADZEKIT_SHED=~/my-shed
adzekit today
```

## Getting Started

### 1. Install AdzeKit

```bash
git clone https://github.com/AdzeKit/AdzeKit.git
cd AdzeKit
uv pip install -e ".[dev]"
```

### 2. Initialize your shed

```bash
uv run adzekit init ~/my-shed
export ADZEKIT_SHED=~/my-shed
```

This creates the backbone directory structure including `graph/`. Your shed is a plain folder -- edit files with any editor, sync with git, back up however you like.

### 3. Basic commands

```bash
adzekit today              # Open/create today's daily note
adzekit add-loop "Send estimate" --who Alice --what "API estimate"
adzekit status             # Show shed health summary
adzekit sweep              # Move completed loops to closed archive
adzekit graph build        # Compile the knowledge graph from all backbone content
adzekit graph query vector-search  # Query graph context for an entity
adzekit graph stats        # Entity counts and relationship totals
adzekit graph orphans      # Find knowledge notes with no connections
```

### 4. Run tests

```bash
uv run pytest
```

## Architecture

```
+----------------------------------------------+
|  Skills (Claude Code commands in your shed)  |
+----------------------------------------------+
|  AI Layer (agent/)                           |
|  shed_get_graph_context() — graph-first      |
+----------------------------------------------+
|  Feature Layer (modules/)                    |
|  graph.py — build / save / load / query      |
+----------------------------------------------+
|  Access Layer (config, models, parser,       |
|                preprocessor, workspace)       |
+----------------------------------------------+
|  Backbone (your shed — plain markdown)       |
|  + graph/ (compiled layer, git-tracked)      |
+----------------------------------------------+
```

**Access Layer** -- Reads and writes the backbone. All markdown I/O lives here.

**Feature Layer** (`modules/`) -- Loop lifecycle, WIP limits, git timestamps, tag scanning, export, and the knowledge graph builder.

**AI Layer** (`agent/`) -- LLM client, tool registry, orchestrator. The agent reads the backbone, queries the graph, and writes proposals to `drafts/`.

**Skills** -- Claude Code slash commands (markdown files) that orchestrate agent capabilities into repeatable workflows. Skills live in your shed, not in the package.

## Access Zones

| Zone | Directories | Who writes | Git-tracked | Purpose |
|------|-------------|-----------|-------------|---------|
| **Backbone** | `daily/`, `loops/`, `projects/`, `knowledge/`, `reviews/`, `bench.md` | Human only | Yes | Your real data -- plans, commitments, reflections |
| **Graph** | `graph/` | Agent (CLI) | Yes | Compiled entity-relationship index; travels with the shed |
| **Workbench** | `drafts/`, `stock/` | Agent-writable | No | Proposals awaiting review, raw materials |

When an AI agent wants to suggest a backbone change, it writes a proposal to `drafts/`. You review and apply -- or discard. The human always decides. The graph is the one exception: it is agent-compiled but git-tracked as permanent computed metadata.

## Knowledge Graph

AdzeKit v2 adds a native knowledge graph layer following Graphify's graph-over-similarity approach and Karpathy's LLM Wiki pattern: backbone files are immutable source code; an LLM compiles them into a structured, interlinked graph that reduces context assembly costs by orders of magnitude compared to file-dumping.

### How it works

1. **Declare relationships in knowledge notes** using typed headers (no YAML):
   ```markdown
   # Vector Search

   #vector-search #concept

   **is-a:** [[retrieval-method]]
   **part-of:** [[retrieval-augmented-generation]]
   **used-by:** [[fourseasons-rag]], [[td-fraudai]]
   **relates-to:** [[knowledge-graphs]], [[feature-store]]
   **developed-by:** [[pinecone]], [[weaviate]]

   Approximate nearest-neighbour search over dense embedding vectors...
   ```

2. **Compile the graph** from all backbone content:
   ```bash
   adzekit graph build
   ```
   Writes `graph/entities.md`, `graph/relations.md`, `graph/index.md`.

3. **Query for compressed context** instead of dumping raw files:
   ```bash
   adzekit graph query vector-search --depth 2
   ```
   Returns: entity type, sources, all typed relationships within 2 hops, connected entities.

4. **Agents use the graph** via `shed_get_graph_context(entity, depth)` -- the graph tool replaces file-dumping with structured traversal.

5. **Run `/graph-update`** in Claude Code to let the agent enrich your knowledge notes with inferred relationships and surface orphans.

### Entity Ontology

Every entity has one canonical type. When ambiguous, apply these rules in order:

| Type | Definition | Canonical source | Detection |
|------|-----------|-----------------|-----------|
| `person` | Named individual (client, colleague, contact) | Any backbone file | `#firstname-lastname` tag (2+ hyphen-separated segments) |
| `organization` | Company, team, client, or institution | Any backbone file | `#org-name` + `#organization` hint tag |
| `project` | Active, backlog, or archived work item with scope and log | `projects/` filename | Auto-detected from directory |
| `concept` | Abstract idea, pattern, methodology, framework, domain area | `knowledge/<slug>.md` | Knowledge note without `#tool` tag |
| `tool` | Software product, platform, API, or service | `knowledge/<slug>.md` | Knowledge note with `#tool` tag |
| `loop` | Tracked commitment to a person with a deadline | `loops/active.md` | Auto-detected from loop entries |
| `event` | Specific time-bound occurrence | `knowledge/<slug>.md` | Knowledge note with `#event` tag |

**Disambiguation rule:** If an entity is both a company and a product (e.g. Databricks), tag its knowledge note with both `#organization` and `#tool`. The graph builder uses `#tool` as the canonical type when both are present.

**Person tag pattern:** `#[a-z]+-[a-z]+(-[a-z]+)*` -- at least two hyphen-separated lowercase words. Examples: `#alice-chen`, `#ryan-bondaria`, `#andrey-karpathy`. Single-word tags are never auto-classified as persons.

### Relationship Ontology

All relationships are directed. Use the most specific type that applies; fall back to `relates-to` only when nothing more precise fits.

| Relation | Direction | Semantics | When to use | Example |
|----------|-----------|-----------|-------------|---------|
| `is-a` | specific → general | Taxonomic subsumption. Transitive: if A is-a B and B is-a C then A is-a C. | A is a subtype or instance of B | `genie is-a databricks-tool` |
| `part-of` | component → whole | Compositional membership. Not transitive by default. | A is a module, sub-element, or feature of B | `genie part-of databricks` |
| `uses` | consumer → provider | Dependency or employment relationship | A depends on or employs B in its operation | `td-fraudai uses databricks` |
| `relates-to` | symmetric | General semantic association. Auto-generated from `[[WikiLinks]]`. | No stronger typed relation fits | `vector-search relates-to knowledge-graphs` |
| `owned-by` | artifact → owner | Accountability and stewardship | A project or work product is owned by a person/org | `td-fraudai owned-by ryan-bondaria` |
| `assigned-to` | loop → person | Commitment target | A loop is owed to or from a person (extracted from `--who`) | `send-estimate assigned-to alice-chen` |
| `mentioned-in` | entity → document | Co-occurrence | Entity appears in a project log or daily note | `databricks mentioned-in td-fraudai` |
| `developed-by` | artifact → creator | Creation provenance | A tool or concept was published or created by a person/org | `claude developed-by anthropic` |
| `contradicts` | A → B | Logical or practical opposition. Treat as symmetric. | A and B are in tension or incompatible | `data-mesh contradicts centralized-platform` |
| `extends` | extension → base | Augmentation or specialisation | A builds on, refines, or is a superset of B | `software-3-0 extends software-2-0` |

### Inline syntax

In knowledge notes, declare typed relationships as bold headers before the main content:

```markdown
**<relation-type>:** [[Target One]], [[Target Two]]
```

or with plain text targets (comma-separated):

```markdown
**is-a:** retrieval-method, similarity-search
```

`[[WikiLink]]` anywhere else in the body (outside typed headers) auto-generates a `relates-to` edge. Standard markdown links (`[text](path)`) are not parsed by the graph builder.

## Skills & Claude Code Integration

AdzeKit skills are Claude Code [slash commands](https://docs.anthropic.com/en/docs/claude-code/slash-commands) that automate productivity workflows. They live in your shed's `.claude/commands/` directory.

### Included skill templates

| Skill | What it does |
|-------|-------------|
| `graph-update` | Compile the knowledge graph; enrich notes with inferred typed relationships; surface orphans. (Karpathy LLM Wiki pattern) |
| `inbox-zero` | Classify, label, and triage up to 100 emails. Draft replies, propose loops. |
| `daily-start` | Pre-populate today's daily note from carried intentions and due loops. |
| `weekly-review` | Generate a review draft with pulse summary from the week's data. |
| `slack-digest` | Surface what matters from Slack channels, mentions, and discussions. |
| `asq-lookup` | Cross-reference Salesforce ARs against your shed for tracking gaps. |
| `loop-momentum` | Detect closed loops from digital evidence, surface stale commitments. |

### Setting up skills in your shed

```bash
mkdir -p ~/my-shed/.claude/commands
cp src/adzekit/skills/graph-update.md ~/my-shed/.claude/commands/graph-update.md
cp src/adzekit/skills/daily-start.md ~/my-shed/.claude/commands/daily-start.md
# ... etc.
```

Personalize the skills for your workflow. Your shed is yours; the repo stays generic.

## Configuration

Per-shed settings in `.adzekit`:

| Key | Default | Purpose |
|-----|---------|---------|
| `backbone_version` | 2 | Spec version (set by `adzekit init`) |
| `max_active_projects` | 3 | WIP cap for active projects |
| `max_daily_tasks` | 5 | Max intention items per daily note |
| `loop_sla_hours` | 24 | Hours before a loop is flagged |
| `stale_loop_days` | 7 | Days before a loop is flagged as stale |
| `rclone_remote` | -- | rclone base path for stock/drafts sync |

Environment variables (prefixed `ADZEKIT_`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `ADZEKIT_SHED` | `~/adzekit` | Shed path |
| `ADZEKIT_GIT_REPO` | -- | Git remote URL (optional) |
| `ADZEKIT_GIT_BRANCH` | `main` | Branch to sync |

## Core Principles

1. **Cap Work-in-Progress** -- Maximum 3 active projects. Maximum 5 daily tasks. No exceptions, only trade-offs.
2. **Close Every Loop** -- Every commitment gets a response within 24 hours. Silence is never acceptable.
3. **Protect Deep Work** -- Schedule uninterrupted blocks. Make calendar fragmentation visible.
4. **Review, Don't Accumulate** -- Weekly review is non-negotiable. Act, schedule, or close.
5. **Report Out Regularly** -- Weekly status to anyone waiting on you.
6. **Graph over Similarity** -- Explicit typed connections over fuzzy keyword matching. Entities are first-class citizens. Compile once, query cheap.

See [docs/concepts.md](docs/concepts.md) for the full philosophy including neurological principles N1--N7.

## Mantra

Files first, rituals second, AI third.
