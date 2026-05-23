# AdzeKit × Hermes Integration

## Current status (as of 2026-05-22)

| Piece | Status |
|---|---|
| SOUL.md translator | **Shipped, grounded.** Concatenates `knowledge/soul.md` + `knowledge/role-context.md` verbatim. Hermes treats SOUL.md as a plain markdown file with no schema — earlier "structured sections + hermes-hints block" code was speculative and has been replaced. |
| Skill pack (`~/.hermes/skills/adzekit/<name>/SKILL.md`) | **Shipped, grounded.** Per agentskills.io standard: each skill is a directory containing `SKILL.md` with YAML frontmatter (`name`, `description`, `version`, `author`, `license`, `platforms`). Older `pack.toml` + flat layout was speculative and has been dropped. |
| Knowledge push (`adzekit adapter sync hermes --direction push`) | **Shipped, grounded.** Concatenates `knowledge/*.md` (excluding soul/role-context) into `~/.hermes/contexts/adzekit-knowledge.md`. |
| Knowledge pull (Hermes-inferred → drafts/) | **Stubbed.** Raises `HermesExportNotImplementedError`. Hermes doesn't publish a documented export schema; wire it up here when it does (likely via Honcho). The draft-proposal contract is defined below — implementation is the only missing piece. |
| Cron installer | **Deferred.** Hermes has a documented cron CLI (`hermes cron create/list/pause/resume/remove`); installing entries automatically is feasible but requires Hermes installed locally to validate. The launchd plists (`adzekit cadence install`) cover macOS today. |
| MCP config sync | **Deferred.** Hermes uses `~/.hermes/config.yaml` under `mcp_servers`. Same workspace MCPs (Slack, Jira) need to be declared there for skills to work fully. Not auto-edited yet — propose-via-draft is the planned shape. |
| Wheel-install path resolution | **Deferred.** `_REPO_ROOT` assumes a git checkout; AdzeKit isn't on PyPI yet. Revisit when shipping a wheel. |

Design exploration sections below are kept for the architectural rationale.
The shipped code matches the verified Hermes facts; only deferred items are
speculative.

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

## Knowledge: bridge, not replace

> Question raised mid-design: "Could AdzeKit just replace its knowledge/ store with
> Hermes' Honcho user model entirely?"

The answer is **no, bridge**. Two reasons:

1. **Honcho is an opaque embedding store.** AdzeKit's `knowledge/` is markdown —
   readable, diffable, editable in any text editor, recoverable from `git log`.
   Replacing it with Honcho violates Principle 7 (Legibility Over Memory) and
   Principle 1 (Files First). You couldn't `git blame` a Honcho row to find when
   a fact entered your worldview.
2. **The two stores serve different epistemic purposes.** AdzeKit's knowledge is
   what you've *written down* — claims you stand behind. Hermes' Honcho is what
   Hermes has *inferred about you* from session history. Conflating them collapses
   the distinction between "I said this" and "the agent thinks this about me."

### The bridge

Two directions, each implemented via the adapter:

```bash
adzekit adapter sync hermes --direction push   # knowledge/ → ~/.hermes/contexts/adzekit-knowledge.md
adzekit adapter sync hermes --direction pull   # ~/.hermes/exports/user-inferences.md → drafts/knowledge/hermes-inferred-*.md
adzekit adapter sync hermes                    # both (default)
```

**Push** concatenates `knowledge/*.md` (excluding `soul.md` and `role-context.md`,
which surface through SOUL.md instead) into a single Hermes context file at
`~/.hermes/contexts/adzekit-knowledge.md`. Hermes loads it as persistent context
on every session. The shed is canonical; Hermes is the consumer. Re-push after
editing any knowledge note.

**Pull** ingests Hermes' exported user-inferences markdown (at
`~/.hermes/exports/user-inferences.md` — Hermes' export integration writes there;
today that path is a placeholder until Hermes ships an export schema) as a
**draft proposal** at `drafts/knowledge/hermes-inferred-YYYY-MM-DD-HHMM-{host}.md`.
The draft carries the full provenance header. The human reviews via
`adzekit drafts list` and promotes via `adzekit drafts accept`. Hermes never
writes directly to `knowledge/`; its inferences pass through the same approval
gate as any other agent output.

### What this preserves

- The shed remains canonical, legible, and editable.
- The human stays in the loop on what enters their identity/knowledge layer.
- Multi-machine sync still works through git (inferred drafts land in the
  workspace, get reviewed, migrate to `knowledge/` only after human approval).
- Hermes can run on a $5 VPS without becoming the source of truth — pull it
  offline tomorrow and your shed is unchanged.

## Still deferred (now with clear reasons)

- **agentskills.io publication** — defer until the install flow is validated
  end-to-end with Hermes actually running on the user's machine.
- **Hermes cron installer** — Hermes' cron schema isn't published yet. AdzeKit's
  launchd plists remain the canonical cadence layer until the schema stabilizes.
- **Conflict tooling for multi-machine drafts** — wait for the user to actually
  encounter a problem. If it never happens, don't build for it.
