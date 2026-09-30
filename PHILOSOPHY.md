# Philosophy

The adze shapes wood by taking away what doesn't belong. So does this.

Your mind runs on fixed limits: working memory holds a few things, every open
commitment nags until it's closed, every context switch costs minutes. Agents
have the opposite problem — they read and write faster than you can follow. Put
those together and the risk is obvious: the agent does more and more, and you
understand less and less of it.

A shed closes that gap. It's a folder of Markdown that a person and their
agents both read and write. Nothing the agent does is hidden in a chat log or a
vector store; it lands in a file you can open, diff, and correct.

## The model

A shed holds two things and is worked by two others.

**Records — your state.** Daily notes, open loops, projects, knowledge,
reviews. Plain Markdown, no database, no required metadata. This is the half
that makes agent work *legible*: everything is a file you can read and a diff
you can trust.

**Skills — your repeatable work.** A skill is compiled judgment: how you want a
recurring job done, written once as plain steps, so any agent can replay it
against your records. Triaging the inbox, scoring a request, sweeping loops for
lost momentum. This is the half that gives you *leverage* — you describe the
procedure once instead of re-explaining it every time.

Records without skills is just a notebook. Skills without records is an agent
with nowhere to stand. The shed is both.

**The agent does the work.** It reads your records, follows your skills, and
edits the files. Reasoning, tool use, and integrations (email, chat, calendar)
belong to whatever agent you use — not to the shed. The shed is what the agent
stands on, not the agent.

**The CLI and git keep it honest.** Five commands do the parts that must be
exact: create today's note and carry forward, sweep ticked loops, report health
against your limits, scaffold the weekly review, and sync. Git is the memory:
the diff is the review, `revert` is the undo, and sync carries everything to
your phone, your other machines, and cloud agents. Sync is where the code earns
its keep. It merges concurrent edits to records instead of stopping, and it
never leaves the repository half-merged.

## The habits the records assume

The record formats aren't arbitrary. Each encodes a habit worth keeping:

- **Write the day down** — a daily note with at most five intentions. What's on
  the page isn't in your head.
- **Close every loop** — each commitment is one line in `loops/active.md` until
  it's done, rescheduled, or dropped on purpose.
- **Cap work in progress** — only a few projects are active; new work pushes
  something out, as a deliberate trade-off.
- **Review, don't accumulate** — weekly, every stale loop and quiet project gets
  a decision, so nothing rots into guilt.
- **Keep what lasts** — durable ideas become `[[linked]]` knowledge notes that
  outlive the project that produced them.

They work on paper. The shed just makes them cheap, and lets an agent keep them
with you.

## Three rules for tools

1. **Plain files are the source of truth.** No database, no hidden memory, no
   mandatory schema. If AdzeKit vanished, the shed would still work in any
   editor.
2. **One set of instructions for every agent.** `AGENTS.md` describes the shed
   once, generated from the same definitions the code parses, so the two can't
   drift. Runtime files (`CLAUDE.md`, `GEMINI.md`) only import it. Skills
   describe formats, not commands, so they outlive any runtime or CLI version.
3. **Agents edit, git remembers.** Changes go straight into the files, kept
   small and in the usual formats. The diff is the review; git is the undo.

## What AdzeKit is not

It is not an agent runtime, an integration hub, a scheduler, or a knowledge
graph. Earlier versions were all four (see the `legacy-v0` tag); each cost more
attention to maintain than it saved. Integrations belong to your agent. The
shed owns only the formats — records and skills — that agents read and write.

## Test for anything new

1. **Does it still work if I edit the files by hand?** If not, it's too clever.
2. **Does it reduce what I hold in my head?** If not, it's clutter.
3. **Is it a recurring procedure?** Then it's a skill (Markdown steps), not a
   feature. Code is only for what must be exact and repeatable: dates,
   carry-forward, sweeping, health checks, sync. Everything that needs judgment
   is a skill, where you or any agent can read and change it.
