---
description: Compile the knowledge graph from backbone; enrich notes; surface orphans
argument-hint: Optional --orphans-only or --enrich
---

Execute the AdzeKit `graph-update` skill (canonical:
`src/adzekit/skills/graph-update.md`).

The deterministic compile lives in the CLI:
```
adzekit graph build
adzekit graph stats
adzekit graph orphans
```

The skill layer adds two LLM-driven steps on top:

1. **Enrich** orphan knowledge notes — propose typed relationship headers
   (`**is-a:**`, `**uses:**`, `**part-of:**`, etc.) grounded in the note's
   content and adjacent entities already in the graph. Proposals go to
   `drafts/graph-enrich-{slug}-{date}.md` — one draft per note.

2. **Surface** orphans the deterministic compiler couldn't classify, with
   suggested links to existing entities. Proposals go to
   `drafts/graph-orphans-{date}.md`.

Files-first: never write to `knowledge/` directly. `graph/` is agent-
writable (the CLI compile populates it); skill output goes to `drafts/`.

ARGUMENTS: $ARGUMENTS
