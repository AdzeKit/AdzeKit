"""Tests for Phase C drafts commands: show + rollback."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from adzekit.modules.drafts import (
    InboxEntryNotFoundError,
    accept_draft,
    parse_inbox,
    rollback_draft,
    show_draft,
)
from adzekit.preprocessor import write_draft_with_frontmatter


# --- show_draft -------------------------------------------------------------


def test_show_strips_frontmatter_by_default(workspace):
    write_draft_with_frontmatter(
        "inbox-triage",
        body="# Triage Report\nBody content here.\n",
        settings=workspace,
        summary="14 emails",
    )
    result = show_draft(1, settings=workspace)
    assert result["skill"] == "inbox-triage"
    assert result["summary"] == "14 emails"
    # Body has the heading but NOT the frontmatter.
    assert "# Triage Report" in result["body"]
    assert "Body content here." in result["body"]
    assert "<!-- adzekit-draft" not in result["body"]


def test_show_with_frontmatter_includes_header(workspace):
    write_draft_with_frontmatter(
        "daily-start", body="# Day\nbody\n", settings=workspace,
    )
    result = show_draft(1, settings=workspace, include_frontmatter=True)
    assert result["body"].startswith("<!-- adzekit-draft")
    assert "# Day" in result["body"]


def test_show_unknown_index_raises(workspace):
    with pytest.raises(InboxEntryNotFoundError):
        show_draft(99, settings=workspace)


def test_show_extracts_provenance_fields(workspace):
    fixed = datetime(2026, 5, 22, 8, 14, 0, tzinfo=timezone.utc)
    write_draft_with_frontmatter(
        "weekly-review",
        body="# Week\nstuff\n",
        settings=workspace,
        timestamp=fixed,
        confidence=0.85,
        summary="3 stale, 2 closed",
    )
    result = show_draft(1, settings=workspace)
    assert result["triggered"].startswith("2026-05-22T08:14")
    assert result["confidence"] == "0.85"
    assert result["hash"].startswith("sha256:")


# --- rollback_draft ---------------------------------------------------------


def test_rollback_restores_most_recent_accepted_draft(workspace):
    """The canonical flow: write -> accept -> regret -> rollback."""
    write_draft_with_frontmatter(
        "weekly-review", body="# Week 21\nbody\n", settings=workspace,
    )
    src_before_accept_path_name = (
        workspace.drafts_dir / "weekly-review-2026-05-22-081400-host.md"
    )  # placeholder; the real name comes from accept
    promoted, original_archive = accept_draft(1, settings=workspace)
    # Now the user changes their mind.
    assert promoted.exists()
    assert original_archive.exists()

    result = rollback_draft(settings=workspace)
    # Original is restored to drafts/ root.
    restored = workspace.drafts_dir / original_archive.name
    assert restored.exists()
    # Backbone copy is removed (because we hadn't edited it).
    assert not promoted.exists()
    # INBOX has the entry back.
    entries = parse_inbox(workspace)
    assert len(entries) == 1
    assert entries[0].skill == "weekly-review"
    # The archived original is gone (it was moved back, not copied).
    assert not original_archive.exists()
    # Result dict has the right keys.
    assert result["restored"].endswith(original_archive.name)
    assert result["removed_from_backbone"] is not None


def test_rollback_preserves_backbone_when_user_edited_it(workspace):
    """If the user edited the promoted file after accept, leave it alone."""
    write_draft_with_frontmatter(
        "weekly-review", body="# Original body\n", settings=workspace,
    )
    promoted, original_archive = accept_draft(1, settings=workspace)
    # Simulate the user editing the promoted backbone copy.
    promoted.write_text("# Original body\nEdited line.\n", encoding="utf-8")

    result = rollback_draft(settings=workspace)
    # The drafts/ copy is restored (the conservative path).
    restored = workspace.drafts_dir / original_archive.name
    assert restored.exists()
    # The (edited) backbone copy is preserved — the user invested work in it.
    assert promoted.exists()
    assert "Edited line." in promoted.read_text()
    assert result["removed_from_backbone"] is None


def test_rollback_with_no_originals_archive_raises(workspace):
    """Plain shed with no accepted drafts: rollback is a no-op error."""
    with pytest.raises(FileNotFoundError):
        rollback_draft(settings=workspace)


def test_rollback_refuses_to_clobber_a_draft_with_the_same_name(workspace):
    """If somehow a draft with the same filename already exists, refuse."""
    write_draft_with_frontmatter(
        "weekly-review", body="# x\n", settings=workspace,
    )
    promoted, original = accept_draft(1, settings=workspace)

    # Re-create a draft with the same filename at drafts/ root (simulating
    # the user running the skill again and getting a fresh draft of the
    # same name — extremely unlikely with HHMMSS-host, but defensively
    # handled).
    duplicate = workspace.drafts_dir / original.name
    duplicate.write_text("conflicting content", encoding="utf-8")

    with pytest.raises(FileExistsError):
        rollback_draft(settings=workspace)


def test_rollback_by_specific_filename(workspace):
    """Roll back a specific archived original, not just the most recent."""
    write_draft_with_frontmatter("alpha", body="# A\n", settings=workspace)
    accept_draft(1, settings=workspace)
    write_draft_with_frontmatter("beta", body="# B\n", settings=workspace)
    _, beta_original = accept_draft(1, settings=workspace)

    # Older draft is the "most recent" by mtime depending on order; we want
    # to roll back the *beta* one explicitly.
    result = rollback_draft(settings=workspace, filename=beta_original.name)
    restored = workspace.drafts_dir / beta_original.name
    assert restored.exists()
    entries = parse_inbox(workspace)
    skills = {e.skill for e in entries}
    assert "beta" in skills
    assert result["restored"].endswith(beta_original.name)
