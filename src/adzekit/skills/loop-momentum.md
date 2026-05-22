# Loop Momentum

## Goal

Cross-reference every open loop against real evidence from configured external systems —
sent emails, git commits, chat messages, ticket trackers, calendar events — to detect loops
that are already effectively done (waiting on the human to mark them closed) and loops that
have gone cold despite their stated commitment. Emit a velocity report and propose
status updates.

The Zeigarnik effect makes open loops cognitively expensive. This skill closes the gap
between "the work is done" and "the loop reflects that the work is done."

Generic skill. Evidence source connectors (Gmail, git, Slack, Jira, Linear, Asana, etc.)
are adapter-installed plugins. A user with no connectors configured still gets a useful
sanity sweep from the default sources (Gmail + git log on workspace repos).

## Inputs

- `{SHED}/knowledge/soul.md` — voice, deep-work hours
- `{SHED}/loops/open.md` (or `loops/active.md` — adapter resolves) — all open loops
- `{SHED}/loops/closed.md` (or `loops/archive.md` — for context on recent closures)
- `{SHED}/projects/*.md` — project files referenced by loops
- `{SHED}/daily/*.md` for the last 14 days — to detect loops mentioned in daily logs
- Default evidence sources (always available):
  - **Gmail** — sent messages in the last 7 days
  - **Git log** — commits in the workspace repo and any project repos declared in projects/
- Optional configured evidence sources (workspace-declared):
  - Slack messages (via Slack adapter)
  - Jira/Linear/Asana tickets (via respective adapters)
  - Calendar events (via calendar adapter)

## Process

1. **Load loops and context.** Read all loop and project files plus the 14-day daily window.
   Build a list of `(loop_title, size, start_date, due_date, mentioned_in_recent_dailies)`
   records. Parallelism: all reads independent.

2. **Compute baseline signals** from shed alone:
   - **Mentioned recently** — loop title or its slug appears in dailies within last 7 days
   - **Stale** — no mentions in last 14 days
   - **Approaching SLA** — due within 7 days
   - **Overdue** — due date passed

3. **Search evidence sources per loop.** For each loop, search each configured evidence
   source for the loop's title, slug, and any associated identifiers (project slug, ticket
   IDs declared in the project file). Parallelism: per-loop fan-out is the dominant
   speedup — see the parallelism note below.

   Per evidence source, return a typed evidence record:
   - `email_sent: {timestamp, to, subject, excerpt}` — sent message referencing the loop
   - `commit: {sha, timestamp, message}` — commit message mentioning the loop
   - `chat: {permalink, channel, timestamp, excerpt}` — chat message mentioning the loop
   - `ticket: {url, status, last_updated}` — ticket linked to the loop
   - `calendar: {event_title, timestamp, attendees}` — calendar event referencing the loop

4. **Classify each loop's momentum.**
   - **Likely closed** — high-confidence evidence of completion in the last 7 days (sent
     email with deliverable, commit message saying "complete", ticket status = Done)
   - **In motion** — recent evidence but not completion (commits, chat discussions, drafts)
   - **Cold** — no evidence in last 14 days; the loop is forgotten
   - **Unverified** — too little signal to classify; flag for human review

5. **Emit proposed updates.** For each loop, propose a status update line for the report.
   Loops classified "Likely closed" get a proposed close line:
   `- [x] (S) [2026-04-18] Send POC summary to Acme (2026-04-25) — evidence: sent
   2026-04-22 14:03 to john@acme.com`
   Loops classified "Cold" get a proposed nudge or close line with the human's choice
   surfaced as the question.

6. **Write the report.** Create
   `{SHED}/drafts/loop-momentum-YYYY-MM-DD-HHMM-{host}.md` containing:
   - Velocity dashboard (loops opened / closed in last 7 days, average loop age, oldest
     open loop)
   - Likely-closed loops with evidence and proposed close lines
   - In-motion loops (informational — no action proposed)
   - Cold loops with proposed actions
   - Unverified loops with a one-line question
   - Copy-paste-ready batch update commands for `loops/open.md`

7. **Print terminal summary.** Top-line counts (`5 likely closed, 3 cold, 12 in motion`)
   and the report path.

## Outputs

- `{SHED}/drafts/loop-momentum-YYYY-MM-DD-HHMM-{host}.md` (with `<!-- adzekit-draft -->`
  provenance header once Phase 2 lands)
- Terminal summary

## Parallelism notes

For N loops and M evidence sources, the naive sequential cost is O(N × M) reasoning turns.
Recommended adapter pattern:
- Orchestrator loads all loops and context.
- Orchestrator partitions loops into chunks of ~5–10 per worker, fans out workers with
  concurrency cap 5.
- Each worker searches all M evidence sources for its loop slice. Workers may run their M
  searches in parallel within their own context.
- Workers return JSON arrays of `(loop_title, classification, evidence_records,
  confidence)`. Workers have read-only tools.
- Orchestrator computes velocity metrics deterministically, merges worker output, writes
  the single report.

Speed budget: 30 loops with 4 evidence sources should complete in ~60–90 seconds vs. ~3–5
minutes monolithic. The bigger the loop set, the bigger the win.

## Safety Rules

- Never modify `loops/open.md` or `loops/closed.md` directly. All proposed updates land in
  the report for human application.
- Never close a loop based on weak evidence. "Likely closed" requires at least one direct
  artifact (sent email, completion commit, ticket Done status). Pattern-matching the loop
  title in unrelated chatter is not enough.
- Never reach into external systems destructively. Evidence search is read-only —
  no marking emails read, no closing tickets, no creating calendar events.
- Confidence threshold for auto-promote: a loop classified "Likely closed" with confidence
  > 0.9 (multiple independent artifacts) MAY be auto-closed via `adzekit drafts accept
  --auto`. Below that, human reviews.

## Notes for adapters

- The evidence source registry is workspace state. Default config includes Gmail + git;
  workspace overrides may add Slack, Jira, etc. A skill author should not assume any
  specific source beyond the defaults.
- Loop file naming: workspace convention is `open.md`/`closed.md`; older spec is
  `active.md`/`archive.md`. Adapter resolves which is present.
- Project-repo discovery: project files may declare a `> Repo:` blockquote with a git
  remote URL. Loop-momentum searches `git log` in those repos for evidence. Without that
  declaration, only the workspace repo is searched.
- For Hermes adapter: each evidence source becomes a Hermes MCP server connection. Workers
  are spawned via `delegate_tool` with selective MCP inheritance — a worker handling 5
  loops only gets the MCPs it needs, not the full registry.
