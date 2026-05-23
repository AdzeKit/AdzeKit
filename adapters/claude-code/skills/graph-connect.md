---
description: Propose typed relationships to connect orphan and under-connected entities into the knowledge graph
---

# graph-connect

You are running the AdzeKit `graph-connect` skill. Your job is to read the current knowledge graph, find entities that are orphaned (zero connections) or under-connected (≤ 2 connections), and propose **typed relationships** that would integrate them into the existing structure.

This is the connection-building counterpart to `/graph-update`. Where graph-update enriches *all* knowledge notes broadly, graph-connect is **focused, per-entity, and orphan-driven** — its only job is to reduce the orphan count by surfacing concrete linking suggestions backed by what's already in the backbone.

## What you will do

1. Build the graph fresh, then read the orphan list and the entity registry.
2. For each orphan (or top-N under-connected entities), read the source files where it appears.
3. Propose 1–3 typed relationships per entity, grounded in evidence from those source files and in entities that already exist in the registry.
4. Write all proposals to `drafts/graph-connect-{date}.md` as a single, scan-able batch the human can review.
5. Never write to backbone files. Never invent target entities that don't appear in the registry.

## Step 1: Refresh the graph

```
adzekit graph build
adzekit graph orphans
adzekit graph stats
```

Then read:
- `graph/index.md` — orphan list and most-connected nodes
- `graph/entities.md` — full registry by type
- `graph/relations.md` — every existing edge so you understand the current shape

## Step 2: Pick targets

Prioritise in this order:
1. **Hard orphans** (degree 0) of type `concept`, `tool`, `project` — these are the ones the user *cares about*; person orphans are mostly extracted from name tags and are noisy.
2. **Under-connected entities** (degree 1–2) of the same types.
3. Skip person orphans unless explicitly asked. Skip orphans whose name looks like a typo (you will see these in the duplicates panel).

Cap your batch at **15 entities** — small enough to review in one sitting.

## Step 3: For each target, gather evidence

Read every source file referenced by that entity in `graph/entities.md`:
- For a `concept` orphan, read the knowledge note(s) it appears in.
- For a `project` orphan, read `projects/active/{slug}.md` (or backlog/, archive/).
- Look at adjacent entities that **do** appear in the registry. Don't invent targets.

Look for evidence of:
- **is-a** — A is a kind of B. ("Liquid clustering is-a clustering technique.")
- **part-of** — A is a component inside B. ("ai-functions part-of databricks-aiepl.")
- **uses** — A depends on or employs B. ("airmiles-semanticsearch uses vector-search, mlflow.")
- **relates-to** — general association, fallback when nothing more precise fits.
- **owned-by** — projects to people. ("aer-compliance owned-by mouhannad-oweis.")
- **assigned-to** — loops to people.
- **developed-by** — tools/concepts to people/orgs.
- **extends** — refines another concept. ("rag extends information-retrieval.")
- **contradicts** — A and B are in tension.
- **mentioned-in** — already auto-extracted; do *not* propose.

## Step 4: Compose the draft

Write a single markdown file to `drafts/graph-connect-{YYYY-MM-DD}.md` with this shape:

```markdown
# Graph Connect Proposals — {date}

Built from {orphan_count} orphans. Reviewed {N} entities; proposing {M} edges.

## Apply notes

- Each proposal block names a target file under `knowledge/`, `projects/`, or — if a knowledge note doesn't yet exist for a concept — suggests creating one.
- All [[targets]] below already exist in the entity registry. No invented entities.
- After reviewing, copy the typed-header lines into the named source file. The next `adzekit graph build` (or any editor save) will pick them up.

---

## {entity-name} ({entity_type}, currently {N} connections)

**Source(s):** `path/to/source.md`

**Evidence:** quote 1–2 lines from the source(s) that justify the proposed edges.

**Proposed additions to** `knowledge/{slug}.md`:

```markdown
**uses:** [[existing-target-1]], [[existing-target-2]]
**part-of:** [[existing-parent]]
```

**Note (optional):** any caveat — e.g. "ambiguous between part-of and uses; pick whichever matches the user's mental model."

---

## ... (next entity)
```

## Step 5: Surface near-duplicates separately

While you're scanning the graph, you will likely notice entities that are clearly the same thing under near-identical names. These are the deterministic-dedup agent's job — do **not** try to merge them in your draft. Instead, add a short closing section:

```markdown
## Likely duplicates (handle in the /graph dedup panel)

- `adam-guary` ↔ `adam-gurary` — confirm typo
- `rob-signoretti` ↔ `robert-signoretti` — short vs full first name

These should be merged with the deterministic deduper in the AdzeKit `/graph` page (Possible Duplicates → Merge), not in this draft. The graph will be cleaner before you re-run /graph-connect.
```

## Step 6: Report to the user

Print, in chat:
- Total orphans before / after the proposed changes (assuming all proposals are applied)
- Top 5 entities you proposed to connect, by potential degree gain
- Path to the draft

## Rules

- **Never write to backbone files** (`knowledge/`, `projects/`, `loops/`, `daily/`, `reviews/`, `bench.md`).
- **drafts/ only** for proposals.
- Ground every proposed edge in evidence from a source file. If you can't quote evidence, drop the proposal.
- Use the most specific relation type. `relates-to` is a fallback, not a default.
- Only propose targets that already exist in `graph/entities.md`. If the right target doesn't exist yet, mention it as a "missing entity" candidate at the bottom of the draft, not as a proposed edge.
- Keep the draft scan-able. Aim for ≤ 15 entities per run; the user must be able to review the whole thing in 5 minutes.

## Ontology reference (for quick recall)

| Relation | Use when |
|----------|----------|
| `is-a` | A is a subtype or instance of B |
| `part-of` | A is a component of B |
| `uses` | A depends on or employs B |
| `relates-to` | General association; no stronger type fits |
| `owned-by` | A project is owned by a person/org |
| `assigned-to` | A loop is owed to a person |
| `developed-by` | A tool/concept was created by person/org |
| `extends` | A builds on or refines B |
| `contradicts` | A and B are in tension or opposition |
| `mentioned-in` | Auto-extracted only — do NOT propose |
