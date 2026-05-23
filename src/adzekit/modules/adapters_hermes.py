"""Hermes adapter: skill pack + SOUL.md translator + cron installer.

Per the locked Hermes-integration decisions:
  1. AdzeKit owns knowledge/soul.md schema; Hermes adapter translates on
     install to ~/.hermes/SOUL.md.
  2. Skills are bundled as a Hermes skill pack at adapters/hermes/pack/
     and (when Hermes is detected on disk) mirrored into
     ~/.hermes/skills/adzekit/.
  3. Session lineage flows through daily-note > Sessions: footers, not
     draft frontmatter.
  4. Multi-machine git conflicts are accepted; the -HHMM-host suffix in
     draft filenames minimizes them.
  5. Secrets live in Hermes' own config, never in the shed.

This module is deliberately conservative about touching Hermes itself —
when Hermes isn't installed locally, the pack is staged but not loaded.
The user copies the staged pack into ~/.hermes/skills/ when they're ready.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from adzekit.config import Settings, get_settings
from adzekit.preprocessor import load_soul

_REPO_ROOT = Path(__file__).resolve().parents[3]
HERMES_PACK_DIR = _REPO_ROOT / "adapters" / "hermes" / "pack"
CORE_SKILLS_DIR = _REPO_ROOT / "src" / "adzekit" / "skills"

HERMES_HOME = Path.home() / ".hermes"
HERMES_SOUL_PATH = HERMES_HOME / "SOUL.md"
HERMES_SKILLS_DIR = HERMES_HOME / "skills" / "adzekit"
HERMES_CONTEXTS_DIR = HERMES_HOME / "contexts"
HERMES_KNOWLEDGE_CONTEXT = HERMES_CONTEXTS_DIR / "adzekit-knowledge.md"

# Path Hermes' export integration (when it exists) writes user-inferred
# facts to. Today this is a placeholder — Hermes doesn't currently publish
# a stable export schema. The pull direction reads this file when present
# and produces draft proposals from it.
HERMES_INFERRED_EXPORT = HERMES_HOME / "exports" / "user-inferences.md"


# --- SOUL.md translation ----------------------------------------------------


def translate_soul_to_hermes(
    settings: Settings | None = None,
    *,
    dest: Path | None = None,
) -> Path | None:
    """Read knowledge/soul.md and emit a Hermes-compatible SOUL.md.

    Returns the destination path on success, or None when knowledge/soul.md
    is missing. When ``dest`` is None and ~/.hermes/ doesn't exist, writes
    to the staged pack dir instead so the translation isn't lost.

    Hermes' SOUL.md schema isn't formally published; we use a reasonable
    superset that Hermes can read (it parses markdown loosely) and that
    preserves the original AdzeKit sections verbatim. The translation is
    additive — no information is dropped.
    """
    settings = settings or get_settings()
    sections = load_soul(settings)
    if not sections:
        return None

    lines = [
        "# SOUL",
        "",
        "_Generated from AdzeKit `knowledge/soul.md` by `adzekit adapter install hermes`._",
        "_Edit the AdzeKit source and re-run install; this file is overwritten._",
        "",
    ]
    # Standard sections in a canonical order; unknown sections appended after.
    canonical = ["Voice", "Values", "Non-negotiables", "Deep work hours"]
    seen: set[str] = set()
    for name in canonical:
        if name in sections:
            lines.append(f"## {name}")
            lines.append("")
            lines.append(sections[name])
            lines.append("")
            seen.add(name)
    for name, body in sections.items():
        if name in seen:
            continue
        lines.append(f"## {name}")
        lines.append("")
        lines.append(body)
        lines.append("")

    # Hermes-specific hint: surface the deep-work window as a top-level
    # directive Hermes can read for its own scheduler-gating logic.
    if "Deep work hours" in sections:
        lines.append("## Hermes hints")
        lines.append("")
        lines.append(
            "When my declared `Deep work hours` window is active, treat me as "
            "do-not-disturb: write drafts, defer notifications, and surface "
            "results after the window closes."
        )
        lines.append("")

    target = dest if dest is not None else (
        HERMES_SOUL_PATH if HERMES_HOME.exists() else HERMES_PACK_DIR / "SOUL.md"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return target


# --- Skill pack building ----------------------------------------------------


def build_skill_pack(*, pack_dir: Path | None = None) -> dict[str, Any]:
    """Copy core skills into the Hermes pack layout.

    The pack format follows Hermes' skill registry convention: a directory
    where each `<skill>.md` is a top-level Hermes Skill row. AdzeKit core
    skills already use a runtime-agnostic format (Goal / Inputs / Process
    / Outputs / Safety / Notes for adapters), so the copy is verbatim.

    Returns metadata about the build.
    """
    pack_dir = pack_dir or HERMES_PACK_DIR
    pack_dir.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    if CORE_SKILLS_DIR.exists():
        # Clean out any prior pack contents except a manifest if present.
        for existing in pack_dir.glob("*.md"):
            existing.unlink()
        for src in sorted(CORE_SKILLS_DIR.glob("*.md")):
            dest = pack_dir / src.name
            dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            copied.append(src.name)

    # Write a pack manifest so Hermes can identify the pack source.
    manifest = pack_dir / "pack.toml"
    manifest.write_text(
        (
            'name = "adzekit"\n'
            f'version = "0.4.0"\n'
            'description = "AdzeKit cognitive-prosthetic skills (capture, daily-start, '
            'inbox-triage, slack-capture, loop-momentum, weekly-review, graph-update, '
            'distill). Backed by a markdown shed at ~/Repos/adzekit-workspace/."\n'
            'author = "AdzeKit"\n'
            'homepage = "https://github.com/AdzeKit/AdzeKit"\n'
            'tags = ["productivity", "knowledge-graph", "cadence", "files-first"]\n'
        ),
        encoding="utf-8",
    )

    return {
        "pack_dir": str(pack_dir),
        "skills": copied,
        "manifest": str(manifest),
    }


# --- Install / uninstall / status ------------------------------------------


def install_hermes(settings: Settings | None = None) -> dict[str, Any]:
    """Build the Hermes pack and translate SOUL.md.

    When ~/.hermes/ exists on the local machine, also mirror the pack into
    ~/.hermes/skills/adzekit/ so Hermes picks it up automatically. When
    Hermes isn't detected, the pack stays staged at adapters/hermes/pack/
    and the user can copy it when they install Hermes.

    Cron installation is left as a manual follow-up — Hermes' cron schema
    isn't published yet, and we don't want to write speculative config
    into the user's ~/.hermes/ tree.
    """
    settings = settings or get_settings()
    pack_info = build_skill_pack()
    soul_path = translate_soul_to_hermes(settings)

    hermes_skills_dir = None
    if HERMES_HOME.exists():
        HERMES_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        # Mirror the pack into ~/.hermes/skills/adzekit/
        for existing in HERMES_SKILLS_DIR.glob("*"):
            if existing.is_file():
                existing.unlink()
            elif existing.is_dir():
                shutil.rmtree(existing)
        for src in Path(pack_info["pack_dir"]).iterdir():
            if src.is_file():
                shutil.copy(src, HERMES_SKILLS_DIR / src.name)
        hermes_skills_dir = str(HERMES_SKILLS_DIR)

    return {
        "adapter": "hermes",
        "pack_dir": pack_info["pack_dir"],
        "skills": pack_info["skills"],
        "soul_path": str(soul_path) if soul_path else None,
        "hermes_skills_dir": hermes_skills_dir,
    }


def uninstall_hermes() -> dict[str, Any]:
    """Remove the staged pack and any installed Hermes skills/SOUL.md."""
    pack_removed = False
    if HERMES_PACK_DIR.exists():
        shutil.rmtree(HERMES_PACK_DIR)
        pack_removed = True

    hermes_skills_removed = None
    if HERMES_SKILLS_DIR.exists():
        shutil.rmtree(HERMES_SKILLS_DIR)
        hermes_skills_removed = str(HERMES_SKILLS_DIR)

    # Leave ~/.hermes/SOUL.md in place by default — the user may have edited
    # it. Removing requires explicit --purge in a future iteration.

    return {
        "adapter": "hermes",
        "pack_dir": str(HERMES_PACK_DIR),
        "pack_removed": pack_removed,
        "hermes_skills_removed": hermes_skills_removed,
    }


# --- Bidirectional knowledge bridge -----------------------------------------
#
# Why we bridge rather than replace:
#
# The user asked whether AdzeKit could replace its knowledge/ store with
# Hermes' Honcho user model entirely. The answer is no — Honcho is an
# opaque embedding store; the shed's markdown knowledge is the principled
# answer to agent opacity (Principle 7: Legibility Over Memory). Replacing
# knowledge/ with Honcho would discard the substrate.
#
# Instead: bridge, in both directions.
#
#   Push (knowledge/ → Hermes): every knowledge/*.md file is exposed to
#     Hermes via a single concatenated context file at
#     ~/.hermes/contexts/adzekit-knowledge.md. Hermes reads it as
#     persistent context on every session. The shed is the source of
#     truth; Hermes is the consumer.
#
#   Pull (Hermes → AdzeKit): when Hermes' export integration drops a
#     user-inferences markdown at ~/.hermes/exports/user-inferences.md,
#     the bridge ingests it as a *proposal* draft in drafts/knowledge/.
#     The human reviews and promotes via `adzekit drafts accept`. Hermes
#     never writes directly to knowledge/; its inferences are subject to
#     the same approval gate as any other agent output.


def push_knowledge_to_hermes(
    settings: Settings | None = None,
    *,
    dest: Path | None = None,
) -> dict[str, Any]:
    """Concatenate knowledge/*.md into a Hermes context file.

    Returns metadata about what was pushed. Returns an empty result when
    knowledge/ has no .md files.
    """
    settings = settings or get_settings()
    knowledge = settings.knowledge_dir
    if not knowledge.exists():
        return {"pushed": False, "reason": "knowledge_dir_missing"}

    files = sorted(knowledge.glob("*.md"))
    if not files:
        return {"pushed": False, "reason": "no_knowledge_files", "files": []}

    target = dest if dest is not None else (
        HERMES_KNOWLEDGE_CONTEXT if HERMES_HOME.exists()
        else HERMES_PACK_DIR / "contexts" / "adzekit-knowledge.md"
    )
    target.parent.mkdir(parents=True, exist_ok=True)

    parts: list[str] = [
        "# AdzeKit Knowledge Context",
        "",
        "_Concatenated from `knowledge/*.md` by AdzeKit's Hermes adapter._",
        "_Edit the AdzeKit source notes; this file is regenerated on push._",
        "",
    ]
    for path in files:
        # Skip soul.md (translated separately via SOUL.md) and role-context
        # (workspace-local identity facts — exposed via SOUL.md hints, not here).
        if path.name in ("soul.md", "role-context.md"):
            continue
        slug = path.stem
        parts.append(f"## {slug}")
        parts.append("")
        parts.append(f"_Source: `knowledge/{path.name}`_")
        parts.append("")
        parts.append(path.read_text(encoding="utf-8").strip())
        parts.append("")
    target.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")

    return {
        "pushed": True,
        "target": str(target),
        "files": [p.name for p in files if p.name not in ("soul.md", "role-context.md")],
    }


def pull_inferences_from_hermes(
    settings: Settings | None = None,
    *,
    export_path: Path | None = None,
) -> dict[str, Any]:
    """Ingest Hermes-inferred facts as a draft proposal.

    Reads from ``export_path`` (defaults to ~/.hermes/exports/user-inferences.md)
    and writes the contents to a draft at
    drafts/knowledge/hermes-inferred-YYYY-MM-DD-HHMM-{host}.md with full
    provenance. The draft surfaces in INBOX for human review.

    Returns metadata; when the export is missing, returns
    {pulled: False, reason: ...} without raising.
    """
    settings = settings or get_settings()
    src = export_path or HERMES_INFERRED_EXPORT
    if not src.exists():
        return {"pulled": False, "reason": "no_export_file", "src": str(src)}

    body_text = src.read_text(encoding="utf-8").strip()
    if not body_text:
        return {"pulled": False, "reason": "empty_export", "src": str(src)}

    # Lazy import: avoid circulars.
    from adzekit.preprocessor import write_draft_with_frontmatter

    # We deliberately route the draft into drafts/knowledge/ so it sits
    # alongside the slack-capture knowledge drafts.
    knowledge_drafts = settings.drafts_dir / "knowledge"
    knowledge_drafts.mkdir(parents=True, exist_ok=True)

    body = (
        "# Hermes-inferred user model\n\n"
        f"_Imported from `{src}` by `adzekit adapter sync hermes --pull`._\n\n"
        "**Review before promoting.** These are Hermes' *inferences* about you "
        "from session history, not facts you wrote. Read critically. Reject "
        "anything that doesn't ring true. Promote the rest to `knowledge/` via "
        "`adzekit drafts accept`.\n\n"
        "---\n\n"
        + body_text
        + "\n"
    )

    written = write_draft_with_frontmatter(
        "hermes-inferred",
        body=body,
        settings=settings,
        inputs=[src],
        trigger="manual",
        summary="Hermes user-model inferences",
    )
    # Relocate from drafts/ root into drafts/knowledge/ so it lives with
    # other knowledge captures.
    target = knowledge_drafts / written.name
    target.write_text(written.read_text(encoding="utf-8"), encoding="utf-8")
    written.unlink()
    _retarget_inbox(settings, written.name, target)

    return {
        "pulled": True,
        "src": str(src),
        "draft": str(target),
    }


def _retarget_inbox(settings: Settings, filename: str, new_path: Path) -> None:
    """Rewrite the INBOX entry so it points at the new draft path.

    Updates the per-entry sidecar at drafts/INBOX.d/{stem}.entry (the post-B1
    authoritative storage) and regenerates the INBOX.md view. Falls back to a
    naive str.replace on the legacy INBOX.md when no sidecar is present.
    """
    old_marker = f"`drafts/{filename}`"
    try:
        rel = str(new_path.resolve().relative_to(settings.shed.resolve()))
    except ValueError:
        rel = str(new_path)
    new_marker = f"`{rel}`"

    sidecar = settings.drafts_dir / "INBOX.d" / f"{Path(filename).stem}.entry"
    if sidecar.exists():
        text = sidecar.read_text(encoding="utf-8")
        sidecar.write_text(text.replace(old_marker, new_marker), encoding="utf-8")
        from adzekit.preprocessor import _regenerate_inbox_view
        _regenerate_inbox_view(settings)
        return

    inbox = settings.drafts_dir / "INBOX.md"
    if not inbox.exists():
        return
    text = inbox.read_text(encoding="utf-8")
    inbox.write_text(text.replace(old_marker, new_marker), encoding="utf-8")


def sync_hermes(
    settings: Settings | None = None,
    *,
    direction: str = "both",
) -> dict[str, Any]:
    """Run the bidirectional bridge.

    direction: 'push' | 'pull' | 'both'. Default 'both'.
    """
    settings = settings or get_settings()
    result: dict[str, Any] = {"adapter": "hermes", "direction": direction}
    if direction in ("push", "both"):
        result["push"] = push_knowledge_to_hermes(settings)
    if direction in ("pull", "both"):
        result["pull"] = pull_inferences_from_hermes(settings)
    return result


def status_hermes(settings: Settings | None = None) -> dict[str, Any]:
    """Report the install state of the Hermes adapter."""
    settings = settings or get_settings()
    pack_present = HERMES_PACK_DIR.exists() and (HERMES_PACK_DIR / "pack.toml").exists()
    soul_translated = (HERMES_PACK_DIR / "SOUL.md").exists() or HERMES_SOUL_PATH.exists()
    soul_path = HERMES_SOUL_PATH if HERMES_SOUL_PATH.exists() else HERMES_PACK_DIR / "SOUL.md"
    hermes_present = HERMES_HOME.exists()
    hermes_skills_installed = HERMES_SKILLS_DIR.exists() and any(
        HERMES_SKILLS_DIR.glob("*.md")
    )

    return {
        "adapter": "hermes",
        "pack_dir": str(HERMES_PACK_DIR),
        "pack_present": pack_present,
        "soul_path": str(soul_path),
        "soul_translated": soul_translated,
        "hermes_detected": hermes_present,
        "hermes_skills_installed": hermes_skills_installed,
    }
