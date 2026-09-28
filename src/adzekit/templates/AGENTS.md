# Workspace instructions

This folder is an AdzeKit workspace: plain Markdown shared by a person and any
agent that helps them. These instructions apply to every tool that works here.

## About me

<!-- Who you are, what you work on, and how you like answers.
     Every agent reads this at the start of every session. Keep it short. -->

## Layout

- `daily/YYYY-MM-DD.md` — one note per day: `## Intention` (at most 5
  checkboxes), `## Log` (what happened), `## Reflection` (end of day).
- `loops/active.md` — open commitments, one line each:
  `- [ ] (S) [YYYY-MM-DD opened] What I owe, to whom (YYYY-MM-DD due)`.
  Size and due date are optional.
- `loops/archive.md` — closed loops, grouped by the date they were swept.
- `projects/*.md` — active projects, capped by `max_active_projects` in
  `.adzekit`. Parked work lives in `projects/backlog/`, finished work in
  `projects/archive/`. Each file has `## Context` and a `## Log` with dated
  entries, newest first.
- `knowledge/*.md` — durable notes. Link with `[[note-name]]`; tag with
  `#kebab-case`.
- `reviews/YYYY-Www.md` — weekly reviews.
- `skills/*.md` — routines. When I name one ("daily start",
  "/weekly-review"), read `skills/<name>.md` and follow it.

## Rules

1. **Edit the files directly.** Git is the undo button. Keep each change
   small and in the formats above so it reads well in a diff.
2. **Keep the formats plain.** Checkboxes, ISO dates, and filenames carry the
   meaning. Don't add frontmatter, IDs, or new folders unless I ask.
3. **Don't invent.** If something isn't in these files or a source you
   checked, say so. Note where each fact came from.
4. **Date what you add.** Log entries start with `YYYY-MM-DD:`.
5. **Respect the limits.** At most 5 daily intentions and the active project
   cap. When something new arrives, propose a trade-off instead of exceeding
   them.
6. **Close loops explicitly.** Mark a loop `[x]` when it's done, or rewrite it
   with a new date and a reason. Never delete one silently.
7. **Be brief.** I may be reading on a phone.

## CLI

If the `adzekit` command is installed, it handles the mechanical parts:
`today`, `log`, `loop`, `project`, `status`, `review`, and `sync`. It never
calls an AI and never touches the network, except `sync` (git). When it isn't
installed, edit the files by hand. The formats above are the whole contract.
