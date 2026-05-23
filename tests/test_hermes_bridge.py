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


def test_pull_with_no_export_skips(workspace, tmp_path):
    missing = tmp_path / "no-export.md"
    result = pull_inferences_from_hermes(workspace, export_path=missing)
    assert result["pulled"] is False
    assert result["reason"] == "no_export_file"


def test_pull_empty_export_skips(workspace, tmp_path):
    empty = tmp_path / "empty.md"
    empty.write_text("   \n  \n", encoding="utf-8")
    result = pull_inferences_from_hermes(workspace, export_path=empty)
    assert result["pulled"] is False
    assert result["reason"] == "empty_export"


def test_pull_emits_knowledge_draft_with_provenance(workspace, tmp_path):
    export = tmp_path / "user-inferences.md"
    export.write_text(
        "## Working hours\n\nUsually 8am-6pm Mountain.\n\n"
        "## Communication style\n\nPrefers terse responses.\n",
        encoding="utf-8",
    )
    result = pull_inferences_from_hermes(workspace, export_path=export)
    assert result["pulled"] is True
    draft = Path(result["draft"])
    assert draft.exists()
    # Draft lives under drafts/knowledge/
    assert draft.parent == workspace.drafts_dir / "knowledge"
    body = draft.read_text(encoding="utf-8")
    assert body.startswith("<!-- adzekit-draft")
    assert "skill: hermes-inferred" in body
    assert "Working hours" in body
    assert "Communication style" in body
    # The "review before promoting" disclaimer must be present.
    assert "Review before promoting" in body


def test_pull_surfaces_draft_in_inbox(workspace, tmp_path):
    export = tmp_path / "user-inferences.md"
    export.write_text("## Some fact\n\nDetail.\n", encoding="utf-8")
    pull_inferences_from_hermes(workspace, export_path=export)
    entries = parse_inbox(workspace)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.skill == "hermes-inferred"
    # INBOX line points at the drafts/knowledge/ subdirectory, not drafts/ root.
    assert entry.path.startswith("drafts/knowledge/")


# --- sync orchestration ----------------------------------------------------


def test_sync_both_runs_push_and_pull(workspace, tmp_path, monkeypatch):
    # Stage a knowledge file (push input).
    (workspace.knowledge_dir / "concept.md").write_text(
        "# Concept\n\nA fact.\n", encoding="utf-8",
    )
    # Stage a Hermes export (pull input).
    export = tmp_path / "user-inferences.md"
    export.write_text("## Inferred\n\nSomething Hermes learned.\n", encoding="utf-8")
    pack_dir = tmp_path / "pack"
    fake_home = tmp_path / "no-hermes"
    monkeypatch.setattr(
        "adzekit.modules.adapters_hermes.HERMES_HOME", fake_home,
    )
    monkeypatch.setattr(
        "adzekit.modules.adapters_hermes.HERMES_PACK_DIR", pack_dir,
    )
    monkeypatch.setattr(
        "adzekit.modules.adapters_hermes.HERMES_KNOWLEDGE_CONTEXT",
        fake_home / "contexts" / "adzekit-knowledge.md",
    )
    monkeypatch.setattr(
        "adzekit.modules.adapters_hermes.HERMES_INFERRED_EXPORT", export,
    )

    result = sync_hermes(workspace, direction="both")
    assert result["direction"] == "both"
    assert result["push"]["pushed"] is True
    assert result["pull"]["pulled"] is True


def test_sync_push_only(workspace, tmp_path, monkeypatch):
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


def test_sync_pull_only(workspace, tmp_path, monkeypatch):
    export = tmp_path / "user-inferences.md"
    export.write_text("## fact\n\nbody\n", encoding="utf-8")
    monkeypatch.setattr(
        "adzekit.modules.adapters_hermes.HERMES_INFERRED_EXPORT", export,
    )
    result = sync_hermes(workspace, direction="pull")
    assert "pull" in result
    assert "push" not in result
    assert result["pull"]["pulled"] is True
