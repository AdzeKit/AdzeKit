# AdzeKit × Hermes Integration

Design exploration. Not a commitment.

## The user's ask

> I want to take my workspace, log on to my personal computer, and have it seamlessly interact with Hermes.

Unpacked, that's four requirements:

1. **Portable state** — the workspace travels with the user. A `git clone` on any machine and the loops, projects, drafts, soul.md are there.
2. **Hermes as runtime** — when sitting at the personal computer, Hermes (not Claude Code) is the agent the user talks to.
3. **Seamless** — no glue rituals. Open terminal, type a command, the shed and the agent already know each other.
4. **Bidirectional** — Hermes reads from the shed (loops, projects, soul.md); Hermes writes to the shed (drafts/, daily/ logs). Cron-fired Hermes runs respect the same shed contract.

## Three plausible integration models

### Model A — AdzeKit as a Hermes skill pack

AdzeKit's generic skills (`inbox-triage`, `daily-start`, `weekly-review`, etc.) are repackaged as **Hermes Skill rows** and installed into Hermes' skill registry. The shed is just a workspace Hermes operates on via its built-in filesystem tools.

- **Distribution**: `pip install adzekit` (CLI) + `hermes skills install adzekit-skills` (skill pack via [agentskills.io](https://agentskills.io) or similar).
- **Skill execution**: Hermes loads the AdzeKit skill, executes it using its own delegation tool and lazy-loaded MCPs.
- **State**: shed at `~/Repos/adzekit-workspace/`, git-synced. Hermes' SQLite session DB at `~/.hermes/` is independent.
- **SOUL.md**: AdzeKit's `knowledge/soul.md` IS Hermes' SOUL.md — symlinked, or one of them is the source. Single voice, one file.
- **Cadence**: Hermes' built-in cron schedules the morning/evening/weekly rituals. No launchd.

**Pros**: ride Hermes' UX (lazy loading, streaming, provider switching, delegation). No bespoke runtime. Skills become shareable on agentskills.io.

**Cons**: AdzeKit skills must conform to Hermes' Skill row format. If Hermes changes that format, AdzeKit follows. Hermes-specific delegation patterns leak into skill authoring.

### Model B — AdzeKit as MCP server

AdzeKit exposes its CLI as an MCP server. Hermes (and Claude Code, and Cursor) connect to it. Tools: `adzekit_get_loops`, `adzekit_propose_draft`, `adzekit_accept_draft`, etc.

- **Distribution**: `pip install adzekit` (ships with MCP server entry point). User adds `adzekit` to `~/.hermes/mcp_servers.json`.
- **Skill execution**: Hermes asks the LLM to call AdzeKit MCP tools. The skill *logic* lives in Hermes prompts or Hermes-side skill files.
- **State**: shed managed by AdzeKit MCP server. Hermes never touches files directly — only through tools.
- **SOUL.md**: Hermes' SOUL.md is canonical. AdzeKit pulls voice via MCP if needed.
- **Cadence**: Hermes cron.

**Pros**: Truly cross-runtime — any MCP-speaking agent (Claude Desktop, Cursor, etc.) gets AdzeKit for free.

**Cons**: This is the v1 model that was abandoned because MCP-server flakiness in Claude Code. Hermes' MCP integration is reportedly more solid, but we'd be re-betting on a model that already failed. Also: MCP tool overhead per call (JSON-RPC roundtrips) eats into the 100x speed gains.

### Model C — Hermes as an AdzeKit adapter (symmetric)

Mirror the planned `adapters/claude-code/` structure: build `adapters/hermes/` containing Hermes-specific wrappers around the runtime-agnostic core skills. Each adapter knows how to translate the generic Goal/Inputs/Process/Outputs skill spec into its host runtime's primitives.

- **Distribution**: `pip install adzekit[hermes]` installs the Hermes adapter. `adzekit adapter install hermes` writes the Hermes skill pack into Hermes' skill dir.
- **Skill execution**: Same skill spec, two execution profiles. Claude Code adapter uses `Agent` tool with `subagent_type` for delegation. Hermes adapter uses `delegate_tool` with role hierarchies.
- **State**: shed canonical. Both adapters read/write the same `drafts/INBOX.md`, same draft frontmatter, same soul.md.
- **SOUL.md**: AdzeKit's `knowledge/soul.md` is the source. Hermes adapter copies or symlinks it into Hermes' expected SOUL.md path on install.
- **Cadence**: AdzeKit CLI's `adzekit cadence install --runtime hermes` generates Hermes cron entries (vs `--runtime claude-code` generating launchd plists).

**Pros**: Cleanest separation — AdzeKit owns the substrate spec, adapters own the runtime mechanics. New runtimes (Cursor, Aider, codex) just need an adapter. Skills don't drift toward any one runtime's quirks.

**Cons**: More structural work upfront. Two adapters to maintain. Risk that the "generic skill spec" becomes a lowest-common-denominator that doesn't fully exploit either runtime.

## Recommendation: Model C, with a Hermes-favored bias

Reasoning:

- **C matches AdzeKit's identity.** AdzeKit is *the substrate*. Its skills are markdown for any agent to read. Tying skill semantics to one runtime (A) or one transport (B) erodes that identity.
- **C is the only path that preserves runtime-agnosticism while still letting each runtime shine.** A leaks Hermes' shape into skills; B kneecaps performance and re-bets on MCP. C says "the spec is mine; the execution is yours."
- **Hermes-favored bias** because of the user's stated goal: Hermes is the target runtime on the personal computer. The Hermes adapter should be richer than the Claude Code adapter — wire into SOUL.md, use Hermes' cron, use Hermes' delegate_tool with role hierarchies, register skills on agentskills.io.
- **Claude Code adapter ships first** because that's what the user is using today. Validates the adapter pattern, then Hermes adapter copies the shape.

## The "seamless personal computer" flow under Model C

```
$ git clone git@github.com:scottmckean/adzekit-workspace.git ~/Repos/adzekit-workspace
$ pip install "adzekit[hermes]"            # core CLI + Hermes adapter
$ adzekit init --shed ~/Repos/adzekit-workspace
$ adzekit adapter install hermes
  → writes AdzeKit skill pack into ~/.hermes/skills/
  → symlinks ~/Repos/adzekit-workspace/knowledge/soul.md to ~/.hermes/SOUL.md
  → registers AdzeKit MCP/tools with Hermes if needed
$ adzekit cadence install --runtime hermes
  → writes Hermes cron entries for morning/evening/weekly rituals
$ hermes
> /daily-start
[Hermes loads the AdzeKit skill, reads soul.md, reads loops/open.md,
 fans out via delegate_tool, writes drafts/daily-start-2026-05-22.md]
```

The "seamless" comes from three things:
1. **One file, two readers** — `knowledge/soul.md` is read identically by Claude Code and Hermes (symlinked into `~/.hermes/SOUL.md`).
2. **One workspace, git-synced** — every machine has the same shed via `git clone` + `git pull`.
3. **One skill spec, two execution profiles** — both adapters wrap the same `src/adzekit/skills/*.md`.

## Locked decisions (answered 2026-05-22)

1. **SOUL.md** — *Hermes translates.* AdzeKit defines its own `knowledge/soul.md` schema
   (Voice / Values / Non-negotiables / Deep work hours). The Hermes adapter's install step
   reads `knowledge/soul.md` and emits a Hermes-compatible SOUL.md into `~/.hermes/SOUL.md`.
   Not a symlink — a translated copy. Re-translation hook: `adzekit adapter sync hermes`
   (manual) and an optional file-watcher on `knowledge/soul.md` writes (auto, off by default).

2. **Skill pack hosting** — *Publish to agentskills.io.* AdzeKit's generic core skills ship as
   a Hermes skill pack via the adapter. New CLI: `adzekit adapter publish hermes` builds and
   uploads the pack. Pack metadata lives in `adapters/hermes/pack.toml`.

3. **Session lineage** — *Not in draft frontmatter; track at the daily-note level.* Hermes
   session IDs do NOT appear in individual draft headers (drafts already carry a `parent:`
   field for cross-draft lineage). Instead, each daily note gets a `> Sessions:` blockquote
   footer that records every agent session that touched the shed that day:
   ```markdown
   > Sessions:
   > - hermes:abc123 08:14-08:42 /daily-start -> drafts/daily-start-2026-05-22.md
   > - hermes:def456 11:02-11:05 /capture
   > - claude-code:session-7f3a 14:20-14:45 /weekly-review -> drafts/weekly-2026-W21.md
   ```
   This puts session lineage at the same granularity AdzeKit already uses for cognition (the
   day). The Hermes adapter appends one line on each invocation; the Claude Code adapter does
   the same with its own session ID format.

4. **Multi-machine git conflicts** — *Accept the friction; git is the resolution.* AdzeKit
   does not build merge logic. Mitigations:
   - Draft filenames carry a `-{HHMM}-{shortHostname}` suffix to minimize same-second
     collisions: `drafts/daily-start-2026-05-22-0814-laptop.md`. The host suffix is the
     first DNS label of `hostname`, sanitized to kebab-case.
   - `drafts/INBOX.md` is the most conflict-prone file (append-heavy). The Phase 2 helper
     `write_draft_with_frontmatter` appends with atomic file locks and tolerates rebase
     fix-ups (lines reordered are still valid; duplicates get gc'd).
   - Daily notes: same date on two machines = expected merge. Conventional resolution: keep
     both `> Sessions:` lines, dedupe task list by content, append unique log entries.

5. **Secrets** — *Hermes' own config.* Never in the shed. `~/.hermes/config` on each machine
   holds the LLM provider keys. Workspace is git-synced and public-domain-safe by design.
   `.adzekit` config marker (in shed root) explicitly excludes any secret fields — a CI check
   in the AdzeKit repo will reject secrets-shaped values committed to a shed-marker file.

## What this unblocks

- Phase 1+ proceeds with full architectural clarity.
- Draft filename schema gains `-{HHMM}-{host}` suffix (small but pervasive change; lands in
  `write_draft_with_frontmatter` helper in Phase 2).
- Daily-note schema gains a `> Sessions:` footer convention. Update `backbone-spec/schema.md`
  when Phase 3 lands.
- Build `adapters/hermes/` with confidence: SOUL.md translation, skill pack publication,
  cadence install via Hermes cron, session-line append.

## Still deferred (now with clear reasons)

- **Building `adapters/hermes/`** — defer until the Claude Code adapter is shipped and
  validates the adapter contract. Hermes adapter copies the shape, doesn't invent it.
- **agentskills.io publication** — defer until generic core skills are stable (Phase 1a
  complete) and `adapters/hermes/pack.toml` schema is known.
- **Conflict tooling** — wait for the user to actually encounter a multi-machine git
  conflict in `drafts/`. If it never happens, don't build for it. If it happens often,
  build minimal helpers then.
