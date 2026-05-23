# AdzeKit Hermes Adapter

The Hermes execution profile for AdzeKit. Wraps the runtime-agnostic core
skills (`src/adzekit/skills/*.md`) as a Hermes skill pack, translates
`knowledge/soul.md` into `~/.hermes/SOUL.md`, and (when Hermes is detected
on the local machine) installs the pack into Hermes' skill registry.

## Layout

```
adapters/hermes/
├── README.md           — this file
└── pack/               — Hermes skill pack (built by `adzekit adapter install hermes`)
    ├── pack.toml       — pack manifest (name, version, tags)
    ├── SOUL.md         — translated from knowledge/soul.md (staged if ~/.hermes/ absent)
    └── *.md            — one file per core skill
```

The `pack/` directory is rebuilt from scratch by the installer; don't
hand-edit files inside it. Edit the canonical skill at
`src/adzekit/skills/<name>.md` and re-run install.

## Install

```bash
adzekit adapter install hermes
```

The installer:

1. Builds the skill pack at `adapters/hermes/pack/` from
   `src/adzekit/skills/`.
2. Writes `pack/pack.toml` with the pack manifest.
3. Translates `knowledge/soul.md` → `pack/SOUL.md` (or directly to
   `~/.hermes/SOUL.md` if Hermes is installed). The translation is
   additive — every section from soul.md appears verbatim, plus a
   `## Hermes hints` section that surfaces the deep-work window as a
   directive Hermes can act on.
4. If `~/.hermes/` exists, mirrors the pack into `~/.hermes/skills/adzekit/`
   so Hermes picks it up automatically.

When Hermes isn't installed locally, the pack stays staged at
`adapters/hermes/pack/` — copy it into `~/.hermes/skills/` when you
install Hermes on this machine.

## Cron / cadence (manual today)

Hermes' cron schema isn't published yet, so the cadence layer is not
installed automatically. The canonical AdzeKit cadence (morning / evening
/ weekly) lives in `src/adzekit/modules/automate.py` as launchd plists.

For Hermes you'd want roughly:

```
07:30 weekdays  → /daily-start
17:30 weekdays  → /daily-close   (workspace-owned)
16:00 Fridays   → /weekly-review
16:00 Fridays   → /distill
09:00 Sundays   → drafts gc
```

Once Hermes' cron format is stable, the installer will write these
entries automatically.

## SOUL.md translation

Per the locked Hermes-integration decision: AdzeKit owns the canonical
`knowledge/soul.md` schema (Voice / Values / Non-negotiables / Deep work
hours). The Hermes adapter translates on install. Not a symlink — a
translated copy. Edit the AdzeKit source and re-run `adzekit adapter
install hermes` to refresh.

The translation preserves every section verbatim and appends a `## Hermes
hints` section if `Deep work hours` is declared, so Hermes' scheduler can
respect the do-not-disturb window without needing to parse AdzeKit's
schema.

## Per-skill execution model

In the Claude Code adapter, orchestrator+worker fan-out is implemented
via the `Agent` tool and plugin-agent `subagent_type`s. In the Hermes
adapter, the equivalent primitive is Hermes' `delegate_tool` with
`role="leaf"` and `inherit_mcp_toolsets` for selective context.

The canonical contract is the same — see `docs/delegation-pattern.md`.
Workers have read-only tools, return JSON, and the orchestrator owns all
side effects. Concurrency cap 5. Worker depth 1.

## Status

```bash
adzekit adapter status hermes
```

Reports whether the pack is built, whether SOUL.md was translated, and
whether Hermes is detected on the machine.

## Uninstall

```bash
adzekit adapter uninstall hermes
```

Removes the staged pack and any skills mirrored into
`~/.hermes/skills/adzekit/`. Leaves `~/.hermes/SOUL.md` in place (it may
have been edited); remove explicitly if you want it gone.
