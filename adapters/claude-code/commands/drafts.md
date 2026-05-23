---
description: Review pending drafts in the INBOX queue, then accept or dismiss
argument-hint: Optional `list` | `accept N` | `dismiss N` | `gc` (default: list)
---

Show the current draft INBOX and optionally promote or discard entries.
The deterministic CLI does the work:

```
adzekit drafts list                # show pending entries with their indices
adzekit drafts accept N            # promote draft #N to its backbone location;
                                   # preserves original to drafts/archive/originals/
adzekit drafts accept N --to PATH  # override destination directory
adzekit drafts accept N --no-preserve
adzekit drafts dismiss N           # discard draft #N to drafts/archive/
adzekit drafts gc                  # archive stale drafts + clean INBOX
```

When run with no arguments, this slash command runs `adzekit drafts list`
and reports the output. With arguments, it forwards them to the CLI.

Always preserve originals on accept (default behavior). The `/distill`
skill reads `drafts/archive/originals/` to detect repeated edit patterns,
so disabling preservation breaks the shed-compounds principle.

ARGUMENTS: $ARGUMENTS
