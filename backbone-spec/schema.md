# AdzeKit workspace format

Version 2 remains the on-disk compatibility version. The format is deliberately
small: an initialized workspace has a `.adzekit` marker and uses UTF-8 Markdown.

## Required contract

```text
workspace/
├── .adzekit       configuration and format version
└── drafts/        review queue for generated proposals
```

Tools may read files in the workspace. Generated content must go to `drafts/`
unless the person explicitly authorizes a direct write. This read/propose split
is the only behavioral rule required by the core.

## Conventional folders

AdzeKit's bundled workflows understand these optional conventions:

```text
daily/             dated notes: YYYY-MM-DD.md
loops/             short commitments
projects/          one Markdown file per project
knowledge/         durable notes
reviews/           periodic reviews
graph/             rebuildable derived index
stock/             unprocessed source material
skills/            workspace-specific workflow instructions
```

An integration must tolerate unused or empty conventional folders. A generic
AdzeKit integration should use the public `Workspace` API instead of depending
on every convention.

## Marker

`.adzekit` is a line-oriented `key = value` file:

```text
backbone_version = 2
max_active_projects = 3
max_daily_tasks = 5
```

Only `backbone_version` identifies the format. Other keys configure optional
workflows and may be ignored by clients that do not implement them.

## Proposals

A proposal is a Markdown file below `drafts/`. AdzeKit may prefix an invisible
HTML comment containing workflow, source, input hashes, confidence, and body
hash. The Markdown body remains usable without parsing that metadata.

`drafts/INBOX.md` is an implementation index, not the source of truth. It can be
rebuilt from proposal files. Accepting a proposal copies its body to a
human-owned destination; dismissing it archives the proposal.

## Optional formats

Bundled workflows currently recognize:

- daily files named `YYYY-MM-DD.md`;
- checklist items written as `- [ ]` and `- [x]`;
- loop dates written inline as `[YYYY-MM-DD]`;
- projects identified by their filename;
- tags written as `#kebab-case`;
- links written as Markdown links or `[[WikiLinks]]`.

These are extension contracts, not requirements for a generic workspace.
Detailed examples belong with the workflow that consumes them.

## Compatibility

“Shed,” “backbone,” and “workbench” are legacy names retained in environment
variables and Python attributes. New interfaces should say “workspace,”
“files,” and “proposals.” No storage migration is required.
