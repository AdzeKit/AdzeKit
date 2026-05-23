"""Tests for the adapter installation helpers."""

from __future__ import annotations

from pathlib import Path

from adzekit.modules.adapters import (
    install_claude_code,
    status_claude_code,
    uninstall_claude_code,
)
from adzekit.modules.adapters_hermes import (
    build_skill_pack,
    install_hermes,
    status_hermes,
    translate_soul_to_hermes,
)


# --- Claude Code adapter ----------------------------------------------------


def test_claude_code_install_populates_target(tmp_path, workspace):
    target = tmp_path / "fake-plugin"
    result = install_claude_code(target_plugin_dir=target)
    assert result["adapter"] == "claude-code"
    assert (target / ".claude-plugin" / "plugin.json").exists()
    assert (target / "agents").is_dir()
    assert (target / "commands").is_dir()
    assert (target / "skills").is_dir()
    # All core skills present in the mirrored target.
    skill_files = list((target / "skills").glob("*.md"))
    # The README in skills/ is excluded from the skill count we copied,
    # but mirrored as part of the directory copy.
    skill_names = {p.name for p in skill_files} - {"README.md"}
    assert "daily-start.md" in skill_names
    assert "inbox-triage.md" in skill_names


def test_claude_code_status_reports_installed(tmp_path):
    target = tmp_path / "fake-plugin"
    install_claude_code(target_plugin_dir=target)
    status = status_claude_code(target_plugin_dir=target)
    assert status["installed"] is True
    assert status["skills"] > 0
    assert status["commands"] > 0
    assert status["agents"] > 0


def test_claude_code_status_reports_not_installed(tmp_path):
    status = status_claude_code(target_plugin_dir=tmp_path / "nonexistent")
    assert status["installed"] is False
    assert status["skills"] == 0


def test_claude_code_uninstall_removes_target(tmp_path):
    target = tmp_path / "fake-plugin"
    install_claude_code(target_plugin_dir=target)
    assert target.exists()
    result = uninstall_claude_code(target_plugin_dir=target)
    assert result["removed"] is True
    assert not target.exists()


def test_claude_code_install_is_idempotent(tmp_path):
    target = tmp_path / "fake-plugin"
    install_claude_code(target_plugin_dir=target)
    skills_first = sorted((target / "skills").glob("*.md"))
    install_claude_code(target_plugin_dir=target)
    skills_second = sorted((target / "skills").glob("*.md"))
    assert [p.name for p in skills_first] == [p.name for p in skills_second]


# --- Hermes SOUL.md translation --------------------------------------------


def test_translate_soul_missing_returns_none(workspace, tmp_path):
    dest = tmp_path / "SOUL.md"
    result = translate_soul_to_hermes(workspace, dest=dest)
    assert result is None
    assert not dest.exists()


def test_translate_soul_emits_canonical_sections_in_order(workspace, tmp_path):
    soul = workspace.knowledge_dir / "soul.md"
    soul.write_text(
        "# Soul\n\n"
        "## Deep work hours\n"
        "09:00-11:00 America/Edmonton\n\n"
        "## Voice\n"
        "- Direct.\n\n"
        "## Values\n"
        "Honest disagreement.\n\n"
        "## Custom Section\n"
        "Some extra content.\n",
        encoding="utf-8",
    )
    dest = tmp_path / "SOUL.md"
    result = translate_soul_to_hermes(workspace, dest=dest)
    assert result == dest
    text = dest.read_text(encoding="utf-8")
    # Voice appears before Values, which appears before Deep work hours,
    # which appears before the custom section.
    voice_idx = text.index("## Voice")
    values_idx = text.index("## Values")
    deep_idx = text.index("## Deep work hours")
    custom_idx = text.index("## Custom Section")
    assert voice_idx < values_idx < deep_idx < custom_idx
    # Hermes hints section is added when Deep work hours is present.
    assert "## Hermes hints" in text
    assert "do-not-disturb" in text


def test_translate_soul_omits_hermes_hints_without_deep_work(workspace, tmp_path):
    soul = workspace.knowledge_dir / "soul.md"
    soul.write_text("# Soul\n\n## Voice\n- Direct.\n", encoding="utf-8")
    dest = tmp_path / "SOUL.md"
    translate_soul_to_hermes(workspace, dest=dest)
    text = dest.read_text(encoding="utf-8")
    assert "## Hermes hints" not in text


# --- Hermes pack building ---------------------------------------------------


def test_build_skill_pack_copies_core_skills(tmp_path):
    pack = tmp_path / "pack"
    result = build_skill_pack(pack_dir=pack)
    assert pack.exists()
    assert (pack / "pack.toml").exists()
    manifest = (pack / "pack.toml").read_text(encoding="utf-8")
    assert 'name = "adzekit"' in manifest
    # At least the canonical skills land in the pack.
    skill_names = {p.name for p in pack.glob("*.md")}
    assert "daily-start.md" in skill_names
    assert "inbox-triage.md" in skill_names
    assert "distill.md" in skill_names


def test_build_skill_pack_rebuild_cleans_stale_files(tmp_path):
    pack = tmp_path / "pack"
    pack.mkdir()
    stale = pack / "old-skill.md"
    stale.write_text("# stale\n")
    build_skill_pack(pack_dir=pack)
    assert not stale.exists()


# --- Hermes install end-to-end ---------------------------------------------


def test_install_hermes_stages_pack(workspace, tmp_path, monkeypatch):
    # Redirect the staged pack dir + soul output so the test is hermetic.
    pack_dir = tmp_path / "stage"
    monkeypatch.setattr(
        "adzekit.modules.adapters_hermes.HERMES_PACK_DIR", pack_dir,
    )
    # Point HERMES_HOME at a non-existent dir so the installer stays in
    # stage mode (doesn't try to mirror into ~/.hermes).
    fake_home = tmp_path / "no-hermes"
    monkeypatch.setattr(
        "adzekit.modules.adapters_hermes.HERMES_HOME", fake_home,
    )
    monkeypatch.setattr(
        "adzekit.modules.adapters_hermes.HERMES_SOUL_PATH",
        fake_home / "SOUL.md",
    )

    soul = workspace.knowledge_dir / "soul.md"
    soul.write_text("# Soul\n\n## Voice\n- Direct.\n", encoding="utf-8")

    result = install_hermes(workspace)
    assert result["adapter"] == "hermes"
    assert Path(result["pack_dir"]) == pack_dir
    assert result["hermes_skills_dir"] is None  # Hermes not detected
    assert result["soul_path"] is not None
    assert (pack_dir / "SOUL.md").exists()
    assert (pack_dir / "pack.toml").exists()
    assert len(result["skills"]) > 0


def test_status_hermes_reports_unstaged_cleanly(workspace, tmp_path, monkeypatch):
    pack_dir = tmp_path / "absent-pack"
    fake_home = tmp_path / "no-hermes"
    monkeypatch.setattr(
        "adzekit.modules.adapters_hermes.HERMES_PACK_DIR", pack_dir,
    )
    monkeypatch.setattr(
        "adzekit.modules.adapters_hermes.HERMES_HOME", fake_home,
    )
    monkeypatch.setattr(
        "adzekit.modules.adapters_hermes.HERMES_SOUL_PATH",
        fake_home / "SOUL.md",
    )
    monkeypatch.setattr(
        "adzekit.modules.adapters_hermes.HERMES_SKILLS_DIR",
        fake_home / "skills" / "adzekit",
    )
    result = status_hermes(workspace)
    assert result["pack_present"] is False
    assert result["hermes_detected"] is False
    assert result["hermes_skills_installed"] is False
