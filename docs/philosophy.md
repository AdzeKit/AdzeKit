# AdzeKit Philosophy

The adze is older than writing. Your stack is younger than your phone.

Your cortex hasn't changed appreciably since the Pleistocene. The cognitive limits it imposes — working-memory capacity, attention-switching cost, the Zeigarnik effect, decision fatigue — are the same constraints that made our ancestors carry tools that fit their hands. Meanwhile your stack now executes hundreds of agent actions per minute across a context window that didn't exist three years ago. The gap between the two is the problem AdzeKit exists to bridge.

AdzeKit is a **cognitive prosthetic** for human-being functioning with agents. Not anti-AI — the opposite. The shed is the most AI-native answer to opaque chat history, vector-store memory, and session amnesia: markdown you can read, diff, and trust. The agent does the work. The shed makes the work *legible to you*.

Eight principles. Each grounded in cognitive science. Each load-bearing.

---

## 1. Cap Work-in-Progress

Taking on too much simultaneously is the default mode. Each context switch costs 23+ minutes of refocus time. Engineers juggling 3+ active threads lose up to 40% of productive capacity. Working memory holds ~4 items reliably; everything beyond that competes for the same scarce resource.

**The rule:** Maximum 3 active projects. Maximum 5 daily tasks. No exceptions — only trade-offs.

**How:** The backbone limits `projects/` to 3 active files. New work cannot enter "active" until something exits. The daily note caps intentions at 5. A single `L` task counts as 2 slots.

---

## 2. Close Every Loop

Open commitments — unanswered emails, promises made in meetings, follow-ups owed — erode trust and accumulate as invisible cognitive debt. Bluma Zeigarnik (1927) showed that incomplete tasks persist in working memory far more than completed ones. Each open loop adds a background process competing for the same limited cognitive resources. You don't just lose track of things — you lose the ability to think clearly about things you haven't lost track of.

The only way to silence the signal: close the loop. Complete it, explicitly defer it with a date, or kill it. Writing it down helps. Resolution finishes the job.

**The rule:** Every commitment gets a response within 24 hours. That response can be "I'll have this by Thursday" — but silence is never acceptable.

**How:** Every commitment becomes a tracked loop in `loops/open.md`. The `/loop-momentum` skill surfaces loops nearing SLA and detects already-completed loops from external evidence. A loop stays open until explicitly closed.

---

## 3. Protect Deep Work

A day with six 30-minute gaps isn't productive — it's six interruptions. Meaningful technical work requires 90+ uninterrupted minutes. The transition cost between contexts is wetware, not preference: prefrontal cortex needs time to re-load the working set for nontrivial cognition.

**The rule:** One 2-hour uninterrupted block daily. No meetings, no Slack, no "quick calls."

**How:** Declare deep-work hours in `knowledge/soul.md`. The cadence layer reads them and *silently writes drafts during the window* — no notifications, no popups, no interruption. The system catches you up when the window closes.

---

## 4. Review, Don't Accumulate

Task systems become digital hoarding. Old tasks stay "active" for months because deleting feels like giving up. This creates clutter, decision paralysis, and guilt. Decision fatigue compounds: each unreviewed commitment costs a fraction of the willpower needed for the next decision.

**The rule:** Weekly review is non-negotiable. Every open loop, every project, every commitment gets examined: act, schedule, or close.

**How:** The `/weekly-review` skill surfaces all open loops older than 7 days, projects without recent activity, and explicit prompts asking "Is this still worth doing?"

---

## 5. System Comes to You — On a Cadence

The best system is useless if it depends on you remembering to use it. Willpower is a finite resource; rituals anchored to circadian cues fire without prefrontal cost. The morning briefing arrives before you've made a single decision. The evening close arrives before the day's residue calcifies.

**The rule:** The system surfaces what matters on a cadence. You approve, edit, or dismiss. Two decisions a day: accept the morning briefing, approve the evening close.

**How:** launchd plists (macOS) schedule `/daily-start`, `/daily-close`, and `/weekly-review` automatically. Drafts land in `drafts/INBOX.md`. The deep-work guard suppresses notifications during your declared focus window — system writes silently, surfaces later.

---

## 6. Graph Over Similarity

Tags and keyword search find documents that *contain* a word — but your brain doesn't work that way. It navigates associative networks: Alice is a consultant, who works at Acme, who uses Databricks, which is a data platform used in the FraudAI project. Fuzzy retrieval finds individual nodes; a graph traverses the paths between them.

**The rule:** Every knowledge note declares its typed relationships explicitly. Every entity — person, project, tool, concept — is a node. Connections are first-class citizens, not implied by co-occurrence.

**How:** Knowledge notes declare typed relationships via bold headers (`**is-a:**`, `**uses:**`, `**developed-by:**`). `[[WikiLink]]` syntax auto-generates `relates-to` edges. `adzekit graph build` compiles the full graph from all backbone content; the graph is git-tracked and human-readable.

---

## 7. Legibility Over Memory

Agent work must leave a markdown trail you can read, diff, and trust. Vector stores are opaque. Session histories are throwaway. The shed is forever.

Source-monitoring research (Johnson 1993) shows humans confuse *generated* content with *retrieved* content — we can't reliably tell what we wrote from what we read from what an agent wrote for us. An external provenance trail offloads that judgment from the brittle internal monitor to the file system.

**The rule:** Every artifact an agent produces carries a provenance header — which skill, which inputs (with content hashes), which parent draft, which session. You should never have to *remember* where a draft came from to trust it.

**How:** `drafts/` files have a `<!-- adzekit-draft -->` HTML-comment header recording skill, trigger, input file SHAs, parent draft, and a body hash. Re-running the same skill on the same inputs produces the same hash — reproducibility is a checkbox. Daily notes accumulate a `> Sessions:` footer listing every agent session that touched the shed that day, identified by the runtime's native session ID.

---

## 8. The Shed Compounds

Repeated workbench patterns distill into skills. The system gets sharper from your usage, not from external prompts.

Chunking and procedural consolidation (Newell 1990; Anderson's ACT-R) describe how repeated cognitive sequences migrate from explicit working memory into compiled procedure: novices think step-by-step, experts have *moves*. AdzeKit mirrors this in software: when you keep hand-editing the same thing in drafts, that pattern wants to become a skill.

**The rule:** The system never auto-writes to `src/adzekit/skills/` or your workspace's `skills/`. But when it detects ≥3 instances of a similar edit pattern, it proposes a new skill in `drafts/skill-proposals/`. You review; you promote.

**How:** `adzekit drafts accept` preserves originals in `drafts/archive/originals/`. The `/distill` skill diffs accepted drafts against their originals to find what you keep fixing, clusters by pattern, and emits proposals. Compounding is the answer to "I keep doing this manually."

---

## Design Decisions

### Human Tools for a Stack That Outpaced Biology

The pitch isn't anti-AI. It's anti-opacity. Markdown shed > vector store. Reviewable diff > inferred user model. Adze-shaped tool that fits the hand > generic SaaS that demands the hand fit it.

### Files First. Rituals Second. AI Third. Provenance Throughout.

1. **Files first** — your real data lives in plain markdown. Any editor works. You own it. No SaaS lock-in. Git syncs it.
2. **Rituals second** — the daily/weekly ceremonies work without any AI or software. The practice survives tool changes.
3. **AI third** — AI reads the backbone, proposes in `drafts/`, and gets out of the way. The human always decides.
4. **Provenance throughout** — every agent artifact carries a receipt. Trust without remembering.

### Runtime-Agnostic by Design

Skills are plain markdown (Goal / Inputs / Process / Outputs format). Adapters translate to host-runtime primitives. Claude Code is the runtime; the adapter pattern lets future runtimes (or new integrations like Telegram, Gmail, Calendar) plug in without changing core skill text.

### Your Kit Is Yours

The core ships only generic, cognitively-shaped skills. Domain skills (Salesforce, Databricks, your specific Slack channels) live in *your* workspace, not in the repo. The core works for a researcher, a lawyer, a founder, a developer — anyone whose job is high-stakes cognitive work in an LLM-saturated world.

### Why No YAML Frontmatter in Backbone

Identity comes from file paths. Timestamps come from git. Tags come from inline `#kebab-case` tokens. No metadata layer to maintain, no schema to keep in sync, no parsing overhead. Drafts (workbench) get an HTML-comment provenance header — that's the *only* metadata layer, and it's machine-readable without being human-hostile.

### Why Inline Dates on Loops

Loops live in shared files (`open.md`, `closed.md`) that get rewritten on every sweep, destroying `git blame` history for individual lines. Inline `[YYYY-MM-DD]` dates survive rewrites and make loop age visible at a glance.

### Why Two Access Zones (Three Counting Graph)

The backbone/workbench split exists to enforce one rule: AI never writes to your real data. When an agent wants to suggest something — a new loop, a knowledge update, a daily note — it writes to `drafts/`. You review and apply, or discard. This prevents AI from accumulating invisible state in your system. The graph is a derived, agent-compiled middle layer — git-tracked because it's reproducible, agent-writable because it's regenerated by `adzekit graph build`.

---

## Influences

- **Bullet Journal** — rapid logging, intentionality, reflection cycles
- **Getting Things Done** — capture everything, process to zero, weekly review
- **Deep Work (Cal Newport)** — protect uninterrupted blocks; chronobiology beats discipline
- **Zeigarnik Effect** — open commitments consume cognitive resources until resolved
- **Karpathy LLM Wiki / Graphify** — compile knowledge into an explicit graph; query structure, not similarity
- **Associative memory** — the brain stores knowledge as typed relational networks, not keyword indexes
- **Skill distillation, persistent session lineage, voice/values config (`soul.md`), cadence-based always-on patterns** — borrowed from prior art on long-running agent runtimes; implemented natively against markdown rather than a runtime-specific schema
- **Woodworking** — the adze shapes wood by removing what doesn't belong. The shed is your workshop, the stock is raw lumber, the adze is your hand-tool.

---

## Voice (this document)

Direct. Citing where it matters. The shed is the substrate; this document is the why.
