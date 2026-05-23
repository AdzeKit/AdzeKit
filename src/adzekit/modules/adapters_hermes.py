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
