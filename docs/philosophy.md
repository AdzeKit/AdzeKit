# AdzeKit Philosophy

AdzeKit exists because high-output technical professionals — people who consult, code, architect, and present — systematically fail at the same five things. These aren't character flaws. They're system failures. AdzeKit is the system.

---

## 1. Cap Work-in-Progress

Taking on too much simultaneously is the default mode. Each context switch costs 23+ minutes of refocus time. Engineers juggling 3+ active threads lose up to 40% of productive capacity.

**The rule:** Maximum 3 active projects. Maximum 5 daily tasks. No exceptions — only trade-offs.

**How:** The backbone limits `projects/` to 3 active files. New work cannot enter "active" until something exits. The daily note caps intentions at 5. A single `L` task counts as 2 slots.

## 2. Close Every Loop

Open commitments — unanswered emails, promises made in meetings, follow-ups owed — erode trust and accumulate as invisible cognitive debt. Psychologist Bluma Zeigarnik showed that incomplete tasks persist in working memory far more than completed ones. Each open loop adds a background process competing for the same limited cognitive resources. You don't just lose track of things — you lose the ability to think clearly about things you haven't lost track of.

The only way to silence the signal: close the loop. Complete it, explicitly defer it with a date, or kill it. Writing it down helps. Resolution finishes the job.

**The rule:** Every commitment gets a response within 24 hours. That response can be "I'll have this by Thursday" — but silence is never acceptable.

**How:** Every commitment becomes a tracked loop in `loops/active.md`. Skills surface loops nearing SLA. A loop stays open until explicitly closed with evidence.

## 3. Protect Deep Work

A day with six 30-minute gaps isn't productive — it's six interruptions. Meaningful technical work requires 90+ uninterrupted minutes.

**The rule:** One 2-hour uninterrupted block daily. No meetings, no Slack, no "quick calls."

**How:** The daily note makes fragmentation visible. The weekly review asks whether you actually got deep blocks.

## 4. Review, Don't Accumulate

Task systems become digital hoarding. Old tasks stay "active" for months because deleting feels like giving up. This creates clutter, decision paralysis, and guilt.

**The rule:** Weekly review is non-negotiable. Every open loop, every project, every commitment gets examined: act, schedule, or close.

**How:** The weekly review surfaces all open loops older than 7 days, projects without recent activity, and explicit prompts asking "Is this still worth doing?"

## 5. System Comes to You

The best productivity system is useless if it depends on you remembering to use it. Willpower is a finite resource. The system should be persistent and present — you should only need to decide, not also trigger.

**The rule:** The system surfaces what matters. You approve, edit, or dismiss. Two decisions a day: accept the morning briefing, approve the evening close.

**How:** Morning briefing arrives with proposed focus and stale draft alerts. Evening close pre-fills reflection from your log. `/log` captures from anywhere with zero navigation. Auto-commit hooks handle git. Skills push, you decide.

## 6. Graph over Similarity

Tags and keyword search find documents that *contain* a word — but your brain doesn't work that way. It navigates associative networks: Alice is a consultant, who works at Acme, who uses Databricks, which is a data platform used in the FraudAI project. Fuzzy retrieval finds individual nodes; a graph traverses the paths between them.

**The rule:** Every knowledge note declares its typed relationships explicitly. Every entity — person, project, tool, concept — is a node. Connections are first-class citizens, not implied by co-occurrence.

**The Graphify insight:** Retrieval through an explicit entity-relationship graph reduces context assembly costs by an order of magnitude compared to dumping raw files at an LLM. Compile the structure once; query it cheaply, many times.

**The Karpathy LLM Wiki pattern:** Treat backbone files as immutable source code. An LLM compiles them into a structured, interlinked knowledge graph that self-heals as sources change. This is the `/graph-update` skill.

**How:** Knowledge notes declare typed relationships via bold headers (`**is-a:**`, `**uses:**`, `**developed-by:**`). `[[WikiLink]]` syntax auto-generates `relates-to` edges. `adzekit graph build` compiles the full graph from all backbone content. Agents use `shed_get_graph_context()` instead of file-dumping.

---

## Design Decisions

### Files First, Rituals Second, AI Third

1. **Files first** — your real data lives in plain markdown. Any editor works. You own it. No SaaS lock-in. Git syncs it.
2. **Rituals second** — the daily/weekly ceremonies work without any AI or software. The practice survives tool changes.
3. **AI third** — AI reads the backbone, proposes in `drafts/`, and gets out of the way. The human always decides.

### Why No YAML Frontmatter

Identity comes from file paths. Timestamps come from git. Tags come from inline `#kebab-case` tokens. No metadata layer to maintain, no schema to keep in sync, no parsing overhead. Just markdown.

### Why Inline Dates on Loops

Loops live in shared files (`active.md`, `archive.md`) that get rewritten on every sweep, destroying `git blame` history for individual lines. Inline `[YYYY-MM-DD]` dates survive rewrites and make loop age visible at a glance.

The date shifts meaning by context: in `active.md` it's the creation date ("how old is this commitment?"); in `archive.md` it's the closure date ("when did I finish this?"). Git history preserves both transitions.

### Why Tags, Not Folders

Tags are flat, case-insensitive, and unregistered. No tag index to maintain — the filesystem is the source of truth. `#alice-chen` in a daily note, a project log, and a loop creates a queryable interaction history without any infrastructure.

### Why Two Access Zones

The backbone/workbench split exists to enforce one rule: AI never writes to your real data. When an agent wants to suggest something — a new loop, a knowledge update, a daily note — it writes to `drafts/`. You review and apply, or discard. This prevents AI from accumulating invisible state in your system.

### Why Batch Patches Over Individual Drafts

When a skill produces many proposals (10 email actions, 6 knowledge updates), writing one draft per proposal overwhelms the review surface. The batch patch pattern consolidates everything into a single file with pre-generated `cp` commands. One file to read, batch decisions to make.

---

## Influences

- **Bullet Journal** — rapid logging, intentionality, reflection cycles, migration
- **Getting Things Done** — capture everything, process to zero, weekly review
- **Deep Work (Cal Newport)** — protect uninterrupted blocks, make fragmentation visible
- **Zeigarnik Effect** — open commitments consume cognitive resources until resolved
- **Woodworking** — the shed is your workshop, stock is raw lumber, the adze shapes it
- **Graphify / Karpathy LLM Wiki** — compile knowledge into an explicit graph; query structure, not similarity
- **Associative memory** — the brain stores knowledge as typed relational networks, not keyword indexes
