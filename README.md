# AdzeKit

Prehistoric tools, LLM-disrupted world.

An adze shapes wood by removing what doesn't belong. AdzeKit shapes your workday the same way — cap the work, close the loops, protect the deep hours.

## What It Is

**The Backbone** — a spec for organizing your work as plain markdown. Any folder that follows it is a *shed*. See [backbone-spec/schema.md](backbone-spec/schema.md).

**The Package** — Python tools that operate on any conforming shed.

**The Skills** — Claude Code slash commands that automate workflows. Skills live in your shed, not the package.

## Install

```bash
git clone https://github.com/AdzeKit/AdzeKit.git
cd AdzeKit
uv pip install -e ".[dev]"
```

## Quick Start

```bash
adzekit init ~/my-shed           # Create a shed
export ADZEKIT_SHED=~/my-shed    # Point to it

adzekit today                    # Open today's daily note
adzekit add-loop "Send estimate" # Track a commitment
adzekit status                   # Shed health at a glance
adzekit sweep                    # Archive completed loops
adzekit tags                     # List all #tags

adzekit graph build              # Compile the knowledge graph
adzekit graph query vector-search  # Query compressed entity context
adzekit graph orphans            # Find unlinked knowledge notes
```

## Six Principles

1. **Cap work-in-progress.** 3 active projects. 5 daily tasks. No exceptions, only trade-offs.
2. **Close every loop.** Every commitment gets a response within 24 hours. Silence is never acceptable.
3. **Protect deep work.** One 2-hour uninterrupted block daily. Non-negotiable.
4. **Review, don't accumulate.** Weekly review: act, schedule, or close. No hoarding.
5. **System comes to you.** Morning briefing arrives automatically. Evening close pre-fills itself. You decide, not remember.
6. **Graph over similarity.** Explicit typed connections over fuzzy keyword matching. Compile once, query cheap.

## Architecture

```
Skills      Claude Code commands in your shed
AI Layer    LLM reads backbone + graph, writes to drafts/ only
Features    Loop lifecycle, WIP limits, tags, graph builder
Access      Config, parser, models — all markdown I/O
Backbone    Your shed — plain markdown, git-synced
Graph       graph/ — compiled entity-relationship index, git-tracked
```

The shed has three zones: the **backbone** (human-owned), the **graph** (`graph/`, agent-compiled but git-tracked), and the **workbench** (`drafts/`, `stock/`, agent-writable, git-ignored). AI proposes, you decide.

## Knowledge Graph

AdzeKit v2 adds a native knowledge graph layer. Backbone files are immutable source code; an LLM compiles them into a structured, interlinked graph (Karpathy's LLM Wiki pattern). Graph traversal replaces file-dumping for context assembly.

Declare relationships in knowledge notes using typed headers (no YAML):

```markdown
# Vector Search

#vector-search #concept

**is-a:** [[retrieval-method]]
**part-of:** [[retrieval-augmented-generation]]
**used-by:** [[fourseasons-rag]], [[td-fraudai]]
**relates-to:** [[knowledge-graphs]], [[feature-store]]
**developed-by:** [[pinecone]], [[weaviate]]
```

`[[WikiLink]]` anywhere in the body auto-generates a `relates-to` edge.

### Entity Ontology

| Type | Definition | Detection |
|------|-----------|-----------|
| `person` | Named individual | `#firstname-lastname` (2+ hyphen-separated words) |
| `organization` | Company, team, client | `#org-name` + `#organization` hint tag |
| `project` | Active/backlog/archived work | Filename in `projects/` |
| `concept` | Abstract idea, pattern, methodology | Knowledge note without `#tool` tag |
| `tool` | Software product, platform, API | Knowledge note with `#tool` tag |
| `loop` | Tracked commitment | Entry in `loops/active.md` |
| `event` | Time-bound occurrence | Knowledge note with `#event` tag |

### Relationship Ontology

| Relation | Direction | When to use |
|----------|-----------|-------------|
| `is-a` | specific → general | A is a subtype or instance of B |
| `part-of` | component → whole | A is a module or feature of B |
| `uses` | consumer → provider | A depends on or employs B |
| `relates-to` | symmetric | General association; auto from `[[WikiLinks]]` |
| `owned-by` | artifact → owner | Project owned by person/org |
| `assigned-to` | loop → person | Commitment owed to a person |
| `mentioned-in` | entity → document | Entity appears in a project/note |
| `developed-by` | artifact → creator | Tool/concept created by person/org |
| `contradicts` | A → B | A and B are in tension |
| `extends` | extension → base | A builds on or refines B |

## Skills

Skills are Claude Code slash commands registered in `.claude/commands/`. They point to full skill definitions in `skills/`.

| Skill | What it does |
|-------|-------------|
| `/daily-start` | Morning briefing with focus line, carried tasks, stale draft alerts |
| `/daily-close` | Evening wrap-up — pre-fill reflection, sweep loops, auto-commit |
| `/log` | Quick-capture a timestamped entry to today's note |
| `/graph-update` | Compile knowledge graph; enrich notes; surface orphans |
| `/inbox-zero` | Classify, label, triage email. Draft replies, propose loops. |
| `/slack` | Digest + knowledge extraction + unread actions in one pass |
| `/weekly-review` | Generate review from loops, projects, and daily logs |
| `/loop-momentum` | Cross-reference loops against email, Slack, Jira for closure evidence |
| `/asq-lookup` | Cross-reference Salesforce ARs against shed for tracking gaps |

## Docs

- [Backbone Spec](backbone-spec/schema.md) — the contract your shed follows
- [Philosophy](docs/philosophy.md) — why these principles, why this design
- [Roadmap](docs/roadmap.md) — what's done, what's next

## Mantra

Files first. Rituals second. AI third.
