"""Tests for the adapter installation helpers."""

from __future__ import annotations

from pathlib import Path

from adzekit.modules.adapters import (
    install_claude_code,
    status_claude_code,
    uninstall_claude_code,
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
