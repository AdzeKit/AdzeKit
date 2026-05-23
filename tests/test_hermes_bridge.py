"""Tests for the bidirectional Hermes knowledge bridge."""

from __future__ import annotations

from pathlib import Path

from adzekit.modules.adapters_hermes import (
    pull_inferences_from_hermes,
    push_knowledge_to_hermes,
    sync_hermes,
)
from adzekit.modules.drafts import parse_inbox


# --- push (knowledge/ -> Hermes context) -----------------------------------


def test_push_with_no_knowledge_skips(workspace, tmp_path):
    result = push_knowledge_to_hermes(workspace, dest=tmp_path / "ctx.md")
    assert result["pushed"] is False
    assert "no_knowledge" in result["reason"]
    assert not (tmp_path / "ctx.md").exists()


def test_push_concatenates_knowledge_files(workspace, tmp_path):
    (workspace.knowledge_dir / "alpha.md").write_text(
        "# Alpha\n\n#alpha #concept\n\nAlpha body.\n", encoding="utf-8",
    )
    (workspace.knowledge_dir / "beta.md").write_text(
        "# Beta\n\n#beta #tool\n\nBeta body.\n", encoding="utf-8",
    )
    dest = tmp_path / "ctx.md"
    result = push_knowledge_to_hermes(workspace, dest=dest)
    assert result["pushed"] is True
    assert set(result["files"]) == {"alpha.md", "beta.md"}
    text = dest.read_text(encoding="utf-8")
    assert "# AdzeKit Knowledge Context" in text
    assert "## alpha" in text
    assert "## beta" in text
    assert "Alpha body." in text
    assert "Beta body." in text


def test_push_excludes_soul_and_role_context(workspace, tmp_path):
    (workspace.knowledge_dir / "soul.md").write_text(
        "# Soul\n\n## Voice\n- Direct.\n", encoding="utf-8",
    )
    (workspace.knowledge_dir / "role-context.md").write_text(
        "# Role\n\nIdentity facts.\n", encoding="utf-8",
    )
    (workspace.knowledge_dir / "vector-search.md").write_text(
        "# Vector Search\n\nReal knowledge.\n", encoding="utf-8",
    )
    dest = tmp_path / "ctx.md"
    result = push_knowledge_to_hermes(workspace, dest=dest)
    text = dest.read_text(encoding="utf-8")
    # soul + role-context are exposed via SOUL.md and shouldn't pollute the
    # general knowledge context.
    assert "Soul" not in text or "## soul" not in text.lower()
    assert "Identity facts." not in text
    assert "Real knowledge." in text
    assert result["files"] == ["vector-search.md"]


# --- pull (Hermes export -> draft proposal) --------------------------------
#
# Phase B: Hermes does not currently publish a documented export schema, so
# the pull direction raises HermesExportNotImplementedError loudly rather
# than silently no-op'ing on a missing placeholder path (the pre-fix behavior
# was indistinguishable from "Hermes has nothing for you today"). When
# Hermes ships an export schema — most likely via the optional Honcho
# integration — this is the place to wire it up.


def test_pull_raises_not_implemented(workspace, tmp_path):
    """Phase B: pull always raises now — Hermes has no export schema yet."""
    import pytest
    from adzekit.modules.adapters_hermes import HermesExportNotImplementedError
    with pytest.raises(HermesExportNotImplementedError) as exc:
        pull_inferences_from_hermes(workspace)
    msg = str(exc.value)
    # The error message points at where to wire it up when Hermes ships.
    assert "Honcho" in msg or "honcho" in msg.lower()
    assert "export" in msg.lower()


def test_pull_raises_even_with_explicit_export_path(workspace, tmp_path):
    """An explicit export path doesn't bypass the NotImplementedError."""
    import pytest
    from adzekit.modules.adapters_hermes import HermesExportNotImplementedError
    export = tmp_path / "user-inferences.md"
    export.write_text("## fact\n\nbody\n", encoding="utf-8")
    with pytest.raises(HermesExportNotImplementedError):
        pull_inferences_from_hermes(workspace, export_path=export)


# --- sync orchestration ----------------------------------------------------


def test_sync_push_only_succeeds(workspace, tmp_path, monkeypatch):
    """Push direction works on its own."""
    (workspace.knowledge_dir / "concept.md").write_text(
        "# Concept\n\nA fact.\n", encoding="utf-8",
    )
    pack_dir = tmp_path / "pack"
    monkeypatch.setattr(
        "adzekit.modules.adapters_hermes.HERMES_HOME", tmp_path / "absent",
    )
    monkeypatch.setattr(
        "adzekit.modules.adapters_hermes.HERMES_PACK_DIR", pack_dir,
    )
    result = sync_hermes(workspace, direction="push")
    assert "push" in result
    assert "pull" not in result
    assert result["push"]["pushed"] is True


def test_sync_default_direction_is_push(workspace, tmp_path, monkeypatch):
    """Default direction post-B is push-only, not both (pull raises)."""
    (workspace.knowledge_dir / "concept.md").write_text(
        "# Concept\n\nA fact.\n", encoding="utf-8",
    )
    pack_dir = tmp_path / "pack"
    monkeypatch.setattr(
        "adzekit.modules.adapters_hermes.HERMES_HOME", tmp_path / "absent",
    )
    monkeypatch.setattr(
        "adzekit.modules.adapters_hermes.HERMES_PACK_DIR", pack_dir,
    )
    result = sync_hermes(workspace)
    assert "push" in result
    assert "pull" not in result


def test_sync_pull_raises(workspace, tmp_path, monkeypatch):
    """direction=pull raises immediately."""
    import pytest
    from adzekit.modules.adapters_hermes import HermesExportNotImplementedError
    with pytest.raises(HermesExportNotImplementedError):
        sync_hermes(workspace, direction="pull")


def test_sync_both_runs_push_then_raises_on_pull(workspace, tmp_path, monkeypatch):
    """direction=both still does the push side, then fails fast on pull."""
    import pytest
    from adzekit.modules.adapters_hermes import HermesExportNotImplementedError
    (workspace.knowledge_dir / "concept.md").write_text(
        "# Concept\n\nA fact.\n", encoding="utf-8",
    )
    pack_dir = tmp_path / "pack"
    monkeypatch.setattr(
        "adzekit.modules.adapters_hermes.HERMES_HOME", tmp_path / "absent",
    )
    monkeypatch.setattr(
        "adzekit.modules.adapters_hermes.HERMES_PACK_DIR", pack_dir,
    )
    with pytest.raises(HermesExportNotImplementedError):
        sync_hermes(workspace, direction="both")
    # Push side completed before the pull raise; the context file exists.
    assert (pack_dir / "contexts" / "adzekit-knowledge.md").exists()
