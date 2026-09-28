# Philosophy

The adze is older than writing. It shapes wood by taking away what doesn't
belong.

Your mind works under fixed limits. Working memory holds about four things.
Every unfinished commitment keeps nagging in the background (the Zeigarnik
effect). Every context switch costs minutes of refocusing. Meanwhile, agents
now read and write far faster than you can follow. Adding more software doesn't
close that gap. A few habits kept in files, which both you and every tool can
read, does.

**Markdown is the interface between you and every tool.**

## Five habits

These five habits are the whole method. They work on paper, and AdzeKit only
makes them cheaper to keep.

1. **Write the day down.** Each day's note has at most five intentions, a
   log of what happened, and a short reflection. If you write it down, you
   don't have to carry it in your head.
2. **Close every loop.** Every commitment you make to someone becomes one line
   in `loops/active.md`, and stays there until it's done, rescheduled, or
   dropped on purpose. An open loop you can see nags less than one you're
   trying to remember.
3. **Cap work in progress.** Only a few projects can be active at once. New
   work has to push something else out, as a deliberate trade-off.
4. **Review, don't accumulate.** Once a week, every stale loop and every quiet
   project gets a decision. Things left undecided pile up into guilt and
   clutter.
5. **Keep what lasts.** Durable ideas go in knowledge notes, linked with
   `[[wikilinks]]`, so they survive the project that produced them.

## Three rules for tools

1. **Plain files are the source of truth.** No database, no hidden agent
   memory, no required metadata. If AdzeKit disappeared tomorrow, the
   workspace would work just as well in any editor.
2. **One set of instructions for every agent.** `AGENTS.md` describes the
   workspace once. Runtime-specific files only import it. Routines are
   Markdown steps in `skills/`, not code tied to one runtime.
3. **Agents edit, git remembers.** Changes go straight into the files, kept
   small and in the usual formats. The diff is the review, `git revert` is the
   undo, and `adzekit sync` carries everything to your other devices.

## What AdzeKit is not

It is not an agent runtime, an integration hub, a scheduler, or a knowledge
graph. Earlier versions tried all of these (see the `legacy-v0` tag). Each one
cost more attention to maintain than it saved. Integrations belong to
whichever agent you use. AdzeKit only owns the formats those agents read and
write.

## Test for new features

Before adding anything, ask:

1. **Does it still work if I edit the files by hand?** If not, it's too
   clever.
2. **Does it reduce what I have to hold in my head?** If not, it's clutter.
3. **Could it be a skill (Markdown steps) instead of code?** If so, write
   the skill.

Code is only for what should be exact and repeatable: dates, carry-forward,
sweeping, limits, and sync. Everything that needs judgment belongs in a
skill, where any agent (or you) can follow it.
