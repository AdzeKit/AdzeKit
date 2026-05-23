# Distill

## Goal

Detect repeated patterns in `drafts/archive/` where the human has consistently hand-edited
agent proposals the same way, and emit a new skill proposal that bakes the pattern in. The
shed compounds: usage sharpens the system.

This is the **eighth principle in action** — repeated workbench patterns distill into skills.
The system never writes to `src/adzekit/skills/` or `{SHED}/skills/` autonomously. Proposals
land in `drafts/skill-proposals/`; the human reviews and promotes.

## Inputs

- `{SHED}/knowledge/soul.md` — voice for the proposed skill
- `{SHED}/drafts/archive/` — accepted drafts (the result of `adzekit drafts accept`)
- `{SHED}/drafts/archive/originals/` — original drafts as proposed by skills, preserved at
  acceptance time so the diff with the accepted draft is recoverable
- `{SHED}/skills/` — existing skills, so distill doesn't propose duplicates

## Process

1. **Load history.** List `drafts/archive/originals/*.md`. For each original, locate the
   corresponding accepted draft in `drafts/archive/` by matching filename. The diff between
   the two is the "what the human kept fixing" signal. Pair them up.

2. **Group by skill+pattern.** For each (original, accepted) pair, identify which skill
   produced the original (from the `<!-- adzekit-draft -->` header `skill:` field). Within
   each skill, cluster diffs by structural similarity:
   - Same section being edited consistently (always rewriting the focus line)
   - Same classification being overridden (always reclassifying sender X from JUNK to DIRECT)
   - Same wording being substituted (always replacing "I'd be happy to" with "Sure")

3. **Filter for distillation candidates.** A cluster qualifies if it has ≥3 instances
   within a rolling 60-day window AND the diffs are structurally similar (not just
   incidental edits). Reject clusters where the edits are too varied to encode as a rule.

4. **Generate proposals.** For each qualifying cluster, write a proposal to
   `{SHED}/drafts/skill-proposals/{pattern-slug}.md`:
   - **Pattern summary**: one-line description of what the human keeps fixing
   - **Evidence**: links to the 3+ prior (original, accepted) pairs with the diff snippets
   - **Proposed implementation**: either a delta to an existing skill (one section update,
     one rule added) OR a brand-new skill if the pattern is large enough to deserve one
   - **Suggested command name** (if a new skill): kebab-case slug
   - **Confidence**: 0.0–1.0 based on cluster tightness and instance count

5. **Surface in INBOX.** Append a line to `{SHED}/drafts/INBOX.md`:
   `- [ ] {today} skill-proposal: {pattern-slug} ({N} occurrences, confidence {C}) ·
   drafts/skill-proposals/{pattern-slug}.md`

6. **Print terminal summary.** Number of proposals emitted and paths.

## Outputs

- Zero or more `{SHED}/drafts/skill-proposals/*.md` files (with `<!-- adzekit-draft -->`
  provenance header)
- Updated `{SHED}/drafts/INBOX.md`
- Terminal summary

## Safety Rules

- Never write to `{SHED}/skills/` or `src/adzekit/skills/`. Distill produces *proposals* in
  drafts/skill-proposals/. Promotion happens via `adzekit drafts accept <N>` which moves the
  proposal to the appropriate skills directory.
- Never propose a skill that duplicates an existing one. Check `{SHED}/skills/` and
  `src/adzekit/skills/` for matching command names and similar descriptions.
- Never modify accepted drafts in `drafts/archive/`. Distill is read-only on history.
- Confidence < 0.7 proposals are still emitted but marked `confidence: low` and excluded
  from `adzekit drafts accept --auto`.

## Notes for adapters

- The pattern-detection logic does not require an LLM for the clustering step — it's
  text-similarity on diffs. The LLM is only useful when writing the human-readable
  proposal markdown.
- Workspace overrides: a workspace can declare custom distillation rules in
  `knowledge/distillation-rules.md` (e.g., "ignore edits to my email signature; that's
  noise, not a pattern"). Skill reads this file if present.
- Cadence: distill runs weekly by default (Friday afternoon, alongside weekly-review). The
  cadence layer wires this up.
- Distill is a low-frequency, batch-style skill. No sub-agent delegation needed; one
  session handles the full run.
