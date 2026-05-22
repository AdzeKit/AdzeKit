# AdzeKit

**Human tools for a stack that outpaced biology.**

The adze is older than writing. Your stack is younger than your phone. AdzeKit bridges them — a markdown-native, runtime-agnostic substrate for human-being functioning with agents.

You haven't evolved much since the Pleistocene. The cortex still chokes on parallel commitments, decision fatigue, opaque tool history. Meanwhile your agents can fan out across a hundred contexts in a single turn. AdzeKit is the prosthetic that keeps you legible to yourself while they work.

## What It Is

**The Backbone** — a spec for organizing your work as plain markdown. Any folder that follows it is a *shed*. See [backbone-spec/schema.md](backbone-spec/schema.md).

**The Package** — Python tools (a CLI, no LLM coupling) that operate on any conforming shed.

**The Skills** — runtime-agnostic markdown skill specs in `src/adzekit/skills/`. Each skill describes *what* needs to happen (Goal / Inputs / Process / Outputs); adapters describe *how* their host runtime executes it.

**The Adapters** — `adapters/claude-code/` is the first execution profile. A Hermes adapter is planned (see [docs/hermes-integration.md](docs/hermes-integration.md)). Any agent runtime that supports isolated sub-agent execution and structured-output workers can wrap the same core skills.

## Install

```bash
git clone https://github.com/AdzeKit/AdzeKit.git
cd AdzeKit
uv pip install -e ".[dev]"
```

## Quick Start

```bash
adzekit init ~/my-shed             # Create a shed
export ADZEKIT_SHED=~/my-shed      # Point to it

adzekit today                      # Open today's daily note
adzekit add-loop "Send estimate"   # Track a commitment
adzekit status                     # Shed health at a glance
adzekit sweep                      # Archive completed loops

adzekit drafts list                # Review pending agent proposals
adzekit drafts accept 1            # Promote draft #1 to backbone
adzekit drafts dismiss 2           # Discard draft #2
adzekit drafts gc                  # Archive stale drafts

adzekit graph build                # Compile the knowledge graph
adzekit graph orphans              # Find unlinked knowledge notes
```

## Eight Principles

1. **Cap work-in-progress.** 3 active projects. 5 daily tasks. No exceptions, only trade-offs. *(Context-switching has measurable cortical cost.)*
2. **Close every loop.** Every commitment gets a response within 24 hours. Silence is never acceptable. *(Zeigarnik: open loops consume working memory.)*
3. **Protect deep work.** One 90+ minute uninterrupted block daily. *(Attention-switching cost is wetware, not preference.)*
4. **Review, don't accumulate.** Weekly review: act, schedule, or close. *(Decision fatigue compounds with backlog.)*
5. **System comes to you — on a cadence.** Morning briefing, evening close, weekly review — anchored to circadian cues, not willpower. *(Rituals beat reminders; chronobiology beats discipline.)*
6. **Graph over similarity.** Explicit typed connections over fuzzy keyword matching. *(Associative memory beats keyword retrieval.)*
7. **Legibility over memory.** Agent work leaves a markdown trail you can read, diff, trust. Opaque sessions and vector stores are the failure mode this prevents. *(Source monitoring; Johnson 1993.)*
8. **The shed compounds.** Repeated workbench patterns distill into skills. The system sharpens from your usage. *(Chunking / procedural consolidation — repeated cognitive sequences migrate from working memory into compiled procedure.)*

## Architecture

```
adzekit/
├── src/adzekit/skills/        runtime-agnostic skill specs (markdown)
├── src/adzekit/                pure-Python CLI, parser, modules — zero LLM calls
├── adapters/claude-code/       Claude Code execution profile (plugin agents, slash commands)
├── adapters/hermes/            (planned) Hermes execution profile
├── backbone-spec/              the shed contract — file layout, frontmatter, provenance
└── docs/                       philosophy, roadmap, integration designs
```

The shed has three zones:

- **Backbone** (human-owned, git-tracked) — `daily/`, `loops/`, `projects/`, `knowledge/`, `reviews/`, `skills/`. The agent never writes here directly.
- **Graph** (agent-compiled, git-tracked) — `graph/entities.md`, `graph/relations.md`, `graph/index.md`. Derived from the backbone via `adzekit graph build`.
- **Workbench** (agent-writable, git-ignored) — `drafts/`, `stock/`. AI proposes here. The human promotes via `adzekit drafts accept`.

Drafts carry a provenance header (skill, trigger, input hashes, parent draft, body SHA). `drafts/INBOX.md` is the protocol queue — every pending decision in one file.

## Your Kit Is Yours

The core ships **only** generic cognitive-prosthetic skills — `capture`, `daily-start`, `daily-close`, `weekly-review`, `inbox-triage`, `slack-capture`, `loop-momentum`, `graph-update`, `distill`. No customer tables, no Salesforce, no Databricks, no domain assumptions.

Domain skills — the persona-specific ones for *your* job — live in *your* workspace at `.claude/commands/` (or your adapter's equivalent). They extend the generics by injecting context (your customer table, your priority channels, your evidence sources). The skill spec doesn't care.

That separation is the difference between *a tool that fits you* and *a tool that you fit yourself to.*

## Knowledge Graph

Backbone files are immutable source code; the graph layer compiles them into a structured, interlinked index ([Karpathy's LLM Wiki pattern](https://karpathy.ai/)). Declare typed relationships in knowledge notes:

```markdown
# Vector Search

#vector-search #concept

**is-a:** [[retrieval-method]]
**part-of:** [[retrieval-augmented-generation]]
**uses:** [[embedding-model]], [[ann-index]]
**relates-to:** [[knowledge-graphs]], [[feature-store]]
```

`[[WikiLink]]` anywhere in the body auto-generates a `relates-to` edge. `adzekit graph build` compiles the full graph; `adzekit graph query <slug>` returns compressed entity context.

## Skills

Skills live in `src/adzekit/skills/` as runtime-agnostic markdown. The Claude Code adapter at `adapters/claude-code/` translates each into a slash command + plugin agent workers.

| Skill | What it does |
|-------|-------------|
| `/capture` | Append a timestamped line to today's daily note |
| `/daily-start` | Morning briefing with focus line, carried loops, stale drafts |
| `/daily-close` | Evening wrap — what closed, what carries (workspace skill) |
| `/weekly-review` | Generate review from loops, projects, and daily logs |
| `/inbox-triage` | Classify, label, draft replies for inbox messages |
| `/slack-capture` | Durable knowledge sweep over configured chat channels |
| `/loop-momentum` | Cross-reference loops against configured evidence sources |
| `/graph-update` | Compile the knowledge graph; enrich notes; surface orphans |
| `/distill` | Detect repeated draft-edit patterns, propose new skills |

## Docs

- [Backbone Spec](backbone-spec/schema.md) — the contract your shed follows
- [Philosophy](docs/philosophy.md) — why these principles, why this design
- [Roadmap](docs/roadmap.md) — what's done, what's next
- [Delegation Pattern](docs/delegation-pattern.md) — the adapter contract
- [Hermes Integration](docs/hermes-integration.md) — designing the multi-runtime setup

## Mantra

Files first. Rituals second. AI third. Provenance throughout.
