---
description: Compile the shed knowledge graph from all backbone content (Karpathy LLM Wiki pattern)
---

# graph-update

You are running the AdzeKit `graph-update` skill. Your job is to compile the knowledge graph by reading all backbone content and inferring entities and typed relationships. This follows Karpathy's LLM Wiki pattern: backbone files are immutable source code; you compile them into a structured, interlinked graph.

## What you will do

1. **Read the backbone** — scan knowledge notes, projects, loops, and daily notes for entities and relationships.
2. **Enrich typed relationships** — for each knowledge note that lacks typed headers, propose enriched versions with inferred relationships.
3. **Identify orphans** — find entities with no connections and surface them for the human to link up.
4. **Write proposals to drafts/** — never touch backbone files directly.
5. **Run the build** — use the CLI to regenerate graph/ from the current backbone.

## Step 1: Survey what's in the shed

Read these files:
- `knowledge/*.md` — all knowledge notes (entities + existing typed relationships)
- `projects/*.md`, `projects/backlog/*.md` — active and backlog projects
- `loops/active.md` — open commitments (loop entities + people)
- `graph/index.md` — current graph state (if it exists)

## Step 2: Compile graph via CLI

The graph is built deterministically from backbone content. Run the CLI rather than writing graph files manually:

```
adzekit graph build
```

This writes `graph/entities.md`, `graph/relations.md`, and `graph/index.md`.

After building, run:

```
adzekit graph stats
adzekit graph orphans
```

Report the output to the user.

## Step 3: Enrich knowledge notes (propose to drafts/)

For each knowledge note that has no typed relationship headers:

1. Read the note content.
2. Infer what relationships it should declare based on the note's content and its connections to other entities in the shed.
3. Propose an enriched version of the note with typed headers added.
4. Write the proposal to `drafts/graph-enrich-<slug>-<date>.md`.

**Typed relationship syntax:**
```markdown
**is-a:** [[broader-concept]]
**part-of:** [[system-or-platform]]
**uses:** [[tool-or-service]]
**relates-to:** [[adjacent-concept]]
**developed-by:** [[person-or-org]]
**extends:** [[base-concept]]
```

Use `[[WikiLink]]` format for targets. Multiple targets are comma-separated on the same line.

## Step 4: Surface orphans

For each entity in `graph/index.md` under `## Orphans`, explain why it has no connections and suggest at least one typed relationship to add. Write suggestions to `drafts/graph-orphans-<date>.md`.

## Step 5: Report to the user

Summarise:
- Graph stats (entities by type, total relationships)
- How many knowledge notes were enriched (proposed to drafts/)
- Orphan count and top suggestions
- Any new entities discovered that don't have knowledge notes yet (candidates for new notes)

## Rules

- **Never write to backbone files** (`knowledge/`, `projects/`, `loops/`, `daily/`, `reviews/`, `bench.md`).
- **graph/ is agent-writable** — `adzekit graph build` writes there; you don't need to write it manually.
- **drafts/ only** for all proposals.
- Use the most specific relation type. Fall back to `relates-to` only when nothing more precise applies.
- A knowledge note should have at least one typed relationship. An isolated note is a missed connection.
- Do not invent entities that don't appear anywhere in the backbone. Ground everything in what you read.

## Ontology reference

**Entity types:** `person`, `organization`, `project`, `concept`, `tool`, `loop`, `event`

**Relation types and when to use each:**

| Relation | Use when |
|----------|----------|
| `is-a` | A is a subtype or instance of B |
| `part-of` | A is a component of B |
| `uses` | A depends on or employs B |
| `relates-to` | General association; no stronger type fits |
| `owned-by` | A project is owned by a person/org |
| `assigned-to` | A loop is owed to a person |
| `mentioned-in` | Entity co-occurs in a document |
| `developed-by` | A tool/concept was created by person/org |
| `contradicts` | A and B are in tension or opposition |
| `extends` | A builds on or refines B |
