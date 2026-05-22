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

## Open questions for the user

1. **SOUL.md format compatibility**: Hermes has its own SOUL.md schema. Should AdzeKit's `knowledge/soul.md` conform to Hermes' schema (so the symlink works directly), or should the Hermes adapter translate on install? Need to read Hermes' SOUL.md docs before answering.

2. **Skill pack hosting**: agentskills.io is Hermes' community skill hub. Should AdzeKit's generic skills (capture, daily-start, weekly-review, inbox-triage, etc.) be published there as a pack? Or kept in the AdzeKit repo only?

3. **Sessions and lineage**: Hermes' SQLite session DB tracks parent/child lineage across compressions. Does the AdzeKit adapter need to participate (e.g., draft frontmatter could include Hermes session ID), or is the daily-note-as-session-record sufficient (AdzeKit's existing model)?

4. **Shed-as-git-repo**: If the workspace is git-synced across machines, what's the conflict-resolution story when both machines write drafts at the same time? AdzeKit currently doesn't address this — it's a Phase 6+ concern.

5. **Where does the personal computer get its secrets?** Hermes runs locally and needs LLM API keys. Are those in the user's shell env, in `~/.hermes/config`, or somewhere shared with the workspace? The shed can't hold secrets (git-synced), so this is a separate concern.

## Concretely deferred

- Building `adapters/hermes/` — defer until the Claude Code adapter is shipped and validated.
- Hermes SOUL.md schema research — defer until Phase 3 (when AdzeKit's `knowledge/soul.md` is being designed).
- agentskills.io publication — defer until generic core skills are stable and the pack format is clear.

For now, Phase 1 work proceeds as planned: author generic core skills with adapter-agnostic spec, then build the Claude Code adapter as the first execution profile. Every choice in Phase 1+ should be evaluated against "would this also work for the Hermes adapter?" If not, fix it now, not later.
