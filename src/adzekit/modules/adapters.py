"""Adapter installation helpers.

AdzeKit ships adapter modules that wrap the runtime-agnostic core for
specific host runtimes or integrations. Each adapter has its own
install/uninstall/status contract; this module is the dispatch + shared
utilities layer.

Currently implemented adapters:
- claude-code: copies skills into the Claude Code plugin layout, links the
  plugin into the user's local plugin tree.

Planned adapters (Phase 2+):
- telegram: long-running gateway daemon bridging Telegram messages to a
  Claude Code session via the Runner abstraction (`gateway/runner.py`).
- gmail, google-calendar: thin wrappers around `gcloud auth` token + REST
  API access for the existing skill flows.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from adzekit.config import Settings, get_settings

# Repo paths — used to locate the bundled adapter directories that ship with
# the AdzeKit Python package source tree. When installed as a wheel these
# may not exist; the user should run adapter operations from a clone.
_REPO_ROOT = Path(__file__).resolve().parents[3]
ADAPTERS_DIR = _REPO_ROOT / "adapters"
CORE_SKILLS_DIR = _REPO_ROOT / "src" / "adzekit" / "skills"


# --- Claude Code adapter ----------------------------------------------------


def install_claude_code(
    *,
    settings: Settings | None = None,
    target_plugin_dir: Path | None = None,
) -> dict:
    """Install the Claude Code adapter as a local Claude Code plugin.

    Steps:
      1. Copy core skills from src/adzekit/skills/ into
         adapters/claude-code/skills/ (idempotent overwrite).
      2. Resolve the target plugin directory (default: ~/.claude/plugins/local/adzekit).
      3. Mirror the adapter contents into the plugin dir.

    Returns a summary dict with paths copied and the install location.
    """
    settings = settings or get_settings()

    adapter_dir = ADAPTERS_DIR / "claude-code"
    if not adapter_dir.exists():
        raise FileNotFoundError(
            f"Claude Code adapter not found at {adapter_dir}. "
            "Run from an AdzeKit checkout."
        )

    # 1. Populate adapter skills/ with current core skills.
    skills_dest = adapter_dir / "skills"
    skills_dest.mkdir(parents=True, exist_ok=True)
    # Preserve the README; replace the rest.
    for existing in skills_dest.iterdir():
        if existing.name == "README.md":
            continue
        if existing.is_file():
            existing.unlink()
    copied_skills: list[str] = []
    if CORE_SKILLS_DIR.exists():
        for src in sorted(CORE_SKILLS_DIR.glob("*.md")):
            dest = skills_dest / src.name
            dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            copied_skills.append(src.name)

    # 2. Resolve target plugin dir.
    target = target_plugin_dir or (
        Path.home() / ".claude" / "plugins" / "local" / "adzekit"
    )
    target.mkdir(parents=True, exist_ok=True)

    # 3. Mirror the adapter (commands/, agents/, skills/, .claude-plugin/) into the target.
    mirrored: list[str] = []
    for sub in ("commands", "agents", "skills", ".claude-plugin"):
        src_sub = adapter_dir / sub
        if not src_sub.exists():
            continue
        dest_sub = target / sub
        if dest_sub.exists():
            shutil.rmtree(dest_sub)
        shutil.copytree(src_sub, dest_sub)
        mirrored.append(sub)

    return {
        "adapter": "claude-code",
        "target": str(target),
        "skills_copied": copied_skills,
        "mirrored_dirs": mirrored,
    }


def uninstall_claude_code(
    *,
    target_plugin_dir: Path | None = None,
) -> dict:
    """Remove the Claude Code adapter from the local plugin tree."""
    target = target_plugin_dir or (
        Path.home() / ".claude" / "plugins" / "local" / "adzekit"
    )
    removed = False
    if target.exists():
        shutil.rmtree(target)
        removed = True
    return {"adapter": "claude-code", "target": str(target), "removed": removed}


def status_claude_code(
    *,
    target_plugin_dir: Path | None = None,
) -> dict:
    """Report installed state of the Claude Code adapter."""
    target = target_plugin_dir or (
        Path.home() / ".claude" / "plugins" / "local" / "adzekit"
    )
    installed = target.exists() and (target / ".claude-plugin" / "plugin.json").exists()
    skill_count = 0
    command_count = 0
    agent_count = 0
    if installed:
        skill_count = len(list((target / "skills").glob("*.md"))) if (target / "skills").exists() else 0
        command_count = len(list((target / "commands").glob("*.md"))) if (target / "commands").exists() else 0
        agent_count = len(list((target / "agents").glob("*.md"))) if (target / "agents").exists() else 0
    return {
        "adapter": "claude-code",
        "target": str(target),
        "installed": installed,
        "skills": skill_count,
        "commands": command_count,
        "agents": agent_count,
    }
