# Weekly Review

## Goal

Generate a weekly review draft from open loops, active projects, and daily logs across the
ISO week. Surfaces stale items, repeated themes, and unfinished commitments — the kindling
for the human's actual review session, not the review itself. The review is a prompt to act,
schedule, or close every open commitment.

Never writes to backbone directories (`loops/`, `projects/`, `daily/`, `reviews/`).

## Inputs

- `{SHED}/knowledge/soul.md` — voice
- `{SHED}/loops/open.md` (or `loops/active.md` — adapter resolves) — all open loops
- `{SHED}/projects/*.md` — project files (skip `archive/` and `backlog/` subdirs)
- `{SHED}/daily/YYYY-MM-DD.md` — every day Mon–Sun of the target week
- Optional argument: an ISO week string (e.g. `2026-W21`) or a date within the target week.
  Defaults to the current ISO week.

## Process

1. **Determine the week.** Compute the ISO week to review (default: current). Resolve the
   Monday and Sunday dates for the target week.

2. **Load backbone context.** Read all daily notes for the week, the loops file, and every
   active project file. Parallelism: all reads independent.

3. **Synthesize the review.**
   - **Loops section**: List every loop from `loops/open.md`. For each, note whether it
     was acted on this week (check daily notes for mentions of the loop's slug or title;
     check project logs for related entries). Flag overdue loops. The review is a prompt
     to act / schedule / close each one.
   - **Projects section**: For each project file (excluding archive/backlog), check for
     log entries dated within the target week. Classify as:
     - **Moved** — has log entries or daily mentions this week
     - **Stale (>7 days)** — last log entry older than 7 days
     The review is a prompt to kill / defer / commit on stale projects.
   - **Decisions & Reflection**: Leave as prompts for the human to fill in. Pre-populate
     with observations harvested from daily reflections (low-energy days, repeated themes,
     things that drained or energized).

4. **Write the draft.** Create `{SHED}/drafts/weekly-review-YYYY-WNN-{host}.md`:
   ```markdown
   # YYYY Week NN Review (week ending YYYY-MM-DD)

   ## Open Loops
   > Review all loops in `loops/open.md`
   > For each: act on it, schedule it, or close it

   [List each loop with status: acted on / overdue / upcoming]

   ## Active Projects
   > Check progress on each project in `projects/`
   > Any project stale for >7 days? Kill, defer, or commit.

   | Project | Last Activity | Status | This Week |
   |---------|--------------|--------|-----------|
   | [slug] | YYYY-MM-DD | Moved / Stale | [brief summary or "no activity"] |

   ## Decisions
   - What am I saying no to this week?
   - What trade-offs am I not admitting to myself?
   [Pre-populated observations]

   ## Reflection
   - What drained me?
   - What energized me?
   - What will I stop doing next week?
   [Pre-populated observations]
   ```

5. **Print terminal summary.** Counts (loops reviewed, projects classified, stale count)
   and the draft path.

## Outputs

- `{SHED}/drafts/weekly-review-YYYY-WNN-{host}.md` (with `<!-- adzekit-draft -->` provenance
  header once Phase 2 lands)
- Terminal summary

## Parallelism notes

This skill is **synthesis-bound**, not fan-out-bound. The value comes from one context
seeing the full week — patterns across days, themes that repeat. Splitting the synthesis
across workers would erode that coherence. Leave as a single-context skill. The cost is
roughly one Sonnet-grade turn at ~60 seconds; not a bottleneck.

The only fan-out worth considering is the *reads* — Claude Code adapters already do this
implicitly (parallel `Read` tool calls in a single turn).

## Safety Rules

- Never write to backbone directories (`loops/`, `projects/`, `daily/`, `knowledge/`,
  `reviews/`). Draft goes to `drafts/` only — human promotes to `reviews/` if desired.
- Do not close or modify open loops. The review proposes; the human decides.
- If a daily note is missing for a day, write `(no note)` rather than inventing content.
- Never auto-close projects classified Stale. Surface them; let the human act.

## Notes for adapters

- Single-context skill: adapters should not fan out to workers. The review benefits from
  one mind seeing the whole week.
- Loop file naming: workspace uses `open.md`/`closed.md`; older spec uses
  `active.md`/`archive.md`. Adapter resolves which is present.
- For Hermes adapter: invoke as a single delegation with leaf role; no children.
- Argument parsing: adapters decide how to surface the optional week argument. Claude Code
  uses `$ARGUMENTS`; Hermes uses positional/named parameters per its CLI convention.
