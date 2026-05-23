---
description: Detect repeated draft-edit patterns and propose new skills
argument-hint: Optional --min-occurrences N (default 3) or --window-days N (default 60)
---

Execute the AdzeKit `distill` skill (canonical:
`src/adzekit/skills/distill.md`).

The deterministic pattern detection lives in the CLI:
```
adzekit distill [--min-occurrences 3] [--window-days 60]
```

This scans `drafts/archive/originals/` against `drafts/archive/`, clusters
diffs by structural signature, and emits proposals to
`drafts/skill-proposals/{slug}.md` with provenance and INBOX entries.

The skill layer (optionally) adds LLM polish on top of the deterministic
proposal: nicer human-readable summary, suggested rule additions to the
target skill, and a confidence rationale. Run the CLI first; the proposal
markdown is already useful without LLM polish.

Promote a proposal:
```
adzekit drafts list
adzekit drafts accept <N>
```

ARGUMENTS: $ARGUMENTS
