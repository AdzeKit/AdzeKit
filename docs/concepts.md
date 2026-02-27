# AdzeKit Core Concepts

AdzeKit exists because high-output technical professionals -- people who consult, code, architect solutions, and present -- systematically fail at five things. These aren't character flaws; they're system failures. AdzeKit is the system.

Every backbone convention and every package feature traces back to one of these principles.

## Principle 1: Cap Work-in-Progress

**The problem:** Taking on too much simultaneously. Context switching between coding, consulting, solution development, and presentations destroys deep cognitive work. Research shows each task switch costs 23+ minutes of refocus time, and engineers juggling 3+ active threads lose up to 40% of productive capacity.

**The rule:** Maximum 3 active projects. Maximum 5 daily focus tasks. No exceptions -- only trade-offs.

**How AdzeKit enforces it:** The backbone limits `projects/active/` to 3 files. The `wip` module maintains a physical WIP count. New work cannot enter "active" status until something exits. The LLM acts as a gatekeeper, running a 4-question filter before any new commitment is accepted.

## Principle 2: Close Every Loop

**The problem:** Open commitments -- unanswered emails, promises made in meetings, follow-ups owed -- erode trust and accumulate as invisible cognitive debt. Every open loop occupies mental RAM whether you're conscious of it or not.

**The Zeigarnik effect:** Psychologist Bluma Zeigarnik demonstrated that incomplete tasks persist in working memory far more than completed ones. The brain treats an unresolved commitment as an open thread that demands periodic re-processing -- creating intrusive thoughts, low-grade anxiety, and a constant sense of "I'm forgetting something." The effect compounds: each additional open loop adds another background process competing for the same limited cognitive resources. You don't just lose track of things; you lose the ability to think clearly about the things you haven't lost track of. The only reliable way to silence the signal is to close the loop -- either by completing it, explicitly deferring it with a concrete date, or killing it outright. Writing it down helps (externalization reduces the Zeigarnik load), but the tension doesn't fully resolve until the commitment has a clear outcome.

**The rule:** Every commitment gets a response within 24 hours. That response can be "I'll have this by Thursday" -- but silence is never acceptable.

**How AdzeKit enforces it:** Every commitment becomes a tracked loop in `loops/open.md`. The `loops` module surfaces loops nearing 24 hours old and can draft acknowledgment messages. A loop stays open until explicitly closed with evidence (sent email, delivered work, documented decision). The system makes every open loop visible and countable -- turning the Zeigarnik effect from a source of ambient dread into a concrete, actionable list.

## Principle 3: Protect Deep Work

**The problem:** Calendar fragmentation. A day with six 30-minute gaps isn't a productive day -- it's six interruptions with no room for serious thinking. Research shows that meaningful creative or technical work requires uninterrupted blocks of 90+ minutes.

**The rule:** Schedule at least one 2-hour uninterrupted block daily. No meetings, no Slack, no "quick calls."

**How AdzeKit enforces it:** The daily note template includes a dedicated deep work slot. The weekly review asks whether you actually got uninterrupted blocks. The system makes fragmentation visible so you can push back on meeting sprawl.

## Principle 4: Review, Don't Accumulate

**The problem:** Task systems become digital hoarding. Old tasks stay "active" for months because deleting them feels like giving up. This creates clutter, decision paralysis, and guilt.

**The rule:** Weekly review is non-negotiable. Every open loop, every project, every commitment gets examined and either: (1) acted on, (2) explicitly scheduled, or (3) closed/archived.

**How AdzeKit enforces it:** The `review` module generates a weekly review document with: all open loops older than 7 days, projects without recent activity, calendar conflicts ahead, and explicit prompts asking "Is this still worth doing?" The LLM can draft kill decisions with reasoning.

## Principle 5: Report Out Regularly

**The problem:** People who depend on your work don't know what you're working on until you're done -- or stuck. This creates surprise, misalignment, and unnecessary urgency.

**The rule:** Weekly status updates to anyone waiting on you. The update can be two sentences -- but it must exist.

**How AdzeKit enforces it:** The weekly review surfaces all active projects and open loops. You see who you owe updates to and can draft a brief, honest status message during the review ritual.

## AdzeKit and Bullet Journal

Bullet journaling at its core is about:

- Rapid logging: short, atomic bullets instead of long narratives.
- Intentionality: regularly asking "Does this still matter?" and killing what doesn't.
- Reflection cycles: daily log + monthly review + migration.
- Analog focus: the act of writing is part of the thinking.

AdzeKit's backbone mirrors this:
- Short markdown bullets instead of big documents.
- Weekly reviews that force you to decide what to drop or defer.
- A single loops file tracking what actually still matters.
- A "workbench" / workshop metaphor instead of a SaaS dashboard.

Conceptually, AdzeKit is a Bullet Journal-compatible digital workshop for people who love the analog ritual but want better searchability, automation, and integration.

## Neurological Principles

**N1: Externalize Working Memory.** Writing quick, short notes takes ideas out of your head and puts them where you can see them. `inbox.md` is the digital rapid-log -- zero structure, zero overhead. Keeping your real memory clear is the goal. Anything important from your paper notebook should be migrated in each night.

**N2: Handwriting for Encoding, Markdown for Search.** Writing by hand helps you understand and remember better. Think on paper, then add key points to markdown files for easy retrieval. The backbone stores distilled insights, not raw scans.

**N3: Spaced Review.** Regularly reviewing notes keeps knowledge fresh. Knowledge notes get tagged with review dates. The `knowledge` module lists what to review each day based on a spaced schedule (+2d, +7d, +30d).

**N4: AI as Filter, Not Firehose.** AI can overwhelm or help. AdzeKit uses AI for focused summaries, drafts, or sorting -- never for broad sweeping changes. LLMs only see what you choose (the pre-processor assembles explicit context), and any AI output is a draft needing your approval.

**N5: Rituals as Structure.** Daily and weekly checklists keep you organized and reflective -- even as tools change. Morning and evening templates guide planning and review. The practice works without any software at all.

**N6: Human Always Decides.** Critical choices -- like accepting new work or sending updates -- are always yours. AI provides drafts and suggestions, but humans make the final call.
