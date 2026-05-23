# Claude Code adapter skills directory

This directory is populated by `adzekit adapter install claude-code` with
copies of the runtime-agnostic core skills from `src/adzekit/skills/`.

Why copies rather than symlinks: when this adapter is shipped as a Claude
Code marketplace plugin, the plugin must be a self-contained directory.
Symlinks pointing back into a sibling `src/` tree won't survive packaging.

The copy is idempotent — re-running install overwrites the skills here
with the current state of `src/adzekit/skills/`. Don't hand-edit files in
this directory; edit the canonical skill in `src/adzekit/skills/` and
re-install.
