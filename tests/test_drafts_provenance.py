"""Tests for Phase 2: draft frontmatter, INBOX queue, accept/dismiss/gc."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from adzekit.modules.drafts import (
    InboxEntryNotFoundError,
    accept_draft,
    dismiss_draft,
    gc_drafts,
    parse_inbox,
)
from adzekit.preprocessor import (
    load_soul,
    read_draft_frontmatter,
    short_hostname,
    strip_draft_frontmatter,
    write_draft_with_frontmatter,
)


# --- short_hostname ---------------------------------------------------------


def test_short_hostname_is_kebab_safe():
    h = short_hostname()
    assert h
    assert all(c.isalnum() or c == "-" for c in h)
    assert h == h.lower()


# --- write_draft_with_frontmatter -------------------------------------------


def test_write_draft_creates_file_with_header(workspace):
    fixed = datetime(2026, 5, 22, 8, 14, 3, tzinfo=timezone.utc)
    path = write_draft_with_frontmatter(
        "inbox-triage",
        body="# Report\nbody text\n",
        settings=workspace,
        timestamp=fixed,
        summary="14 emails, 3 reply drafts",
    )
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert text.startswith("<!-- adzekit-draft")
    assert "skill: inbox-triage" in text
    assert "triggered: 2026-05-22T08:14:03+00:00" in text
    assert "host:" in text
    assert "hash: sha256:" in text
    assert "# Report" in text


def test_write_draft_filename_includes_host_and_time(workspace):
    fixed = datetime(2026, 5, 22, 8, 14, 0, tzinfo=timezone.utc)
    path = write_draft_with_frontmatter(
        "daily-start",
        body="hello",
        settings=workspace,
        timestamp=fixed,
    )
    assert path.name.startswith("daily-start-2026-05-22-0814-")
    assert path.name.endswith(".md")


def test_write_draft_appends_to_inbox(workspace):
    fixed = datetime(2026, 5, 22, 8, 14, tzinfo=timezone.utc)
    write_draft_with_frontmatter(
        "inbox-triage",
        body="body",
        settings=workspace,
        timestamp=fixed,
        summary="14 emails",
    )
    inbox = workspace.drafts_dir / "INBOX.md"
    assert inbox.exists()
    content = inbox.read_text(encoding="utf-8")
    assert "# Draft Inbox" in content
    assert "2026-05-22 08:14 inbox-triage" in content
    assert "14 emails" in content


def test_write_multiple_drafts_appends_multiple_inbox_lines(workspace):
    for skill, ts in [
        ("daily-start", datetime(2026, 5, 22, 7, 30, tzinfo=timezone.utc)),
        ("inbox-triage", datetime(2026, 5, 22, 8, 14, tzinfo=timezone.utc)),
        ("weekly-review", datetime(2026, 5, 22, 16, 0, tzinfo=timezone.utc)),
    ]:
        write_draft_with_frontmatter(
            skill, body=f"body for {skill}", settings=workspace, timestamp=ts,
        )
    entries = parse_inbox(workspace)
    assert len(entries) == 3
    assert [e.skill for e in entries] == ["daily-start", "inbox-triage", "weekly-review"]


def test_write_draft_records_inputs_with_relpath(workspace):
    soul = workspace.knowledge_dir / "soul.md"
    soul.write_text("# Soul\n", encoding="utf-8")
    path = write_draft_with_frontmatter(
        "inbox-triage",
        body="body",
        settings=workspace,
        inputs=[soul],
    )
    parsed = read_draft_frontmatter(path)
    assert "inputs" in parsed
    # Even with no git sha, the relpath is recorded.
    assert any("knowledge/soul.md" in entry for entry in parsed["inputs"])


def test_write_draft_records_parent(workspace):
    parent_path = workspace.drafts_dir / "inbox-triage-2026-05-21-0814-host.md"
    parent_path.parent.mkdir(parents=True, exist_ok=True)
    parent_path.write_text("placeholder\n", encoding="utf-8")
    new_path = write_draft_with_frontmatter(
        "inbox-triage",
        body="body",
        settings=workspace,
        parent=parent_path,
    )
    parsed = read_draft_frontmatter(new_path)
    assert parsed["parent"].endswith("inbox-triage-2026-05-21-0814-host.md")


# --- read_draft_frontmatter / strip_draft_frontmatter -----------------------


def test_read_draft_frontmatter_roundtrip(workspace):
    path = write_draft_with_frontmatter(
        "inbox-triage",
        body="# Body\nstuff\n",
        settings=workspace,
        summary="14 emails",
        confidence=0.87,
    )
    parsed = read_draft_frontmatter(path)
    assert parsed["skill"] == "inbox-triage"
    assert parsed["summary"] == "14 emails"
    assert parsed["confidence"] == "0.87"


def test_strip_draft_frontmatter_returns_body_only(workspace):
    path = write_draft_with_frontmatter(
        "daily-start",
        body="# Body\nline1\nline2\n",
        settings=workspace,
    )
    body = strip_draft_frontmatter(path)
    assert not body.startswith("<!--")
    assert body.startswith("# Body")


def test_read_draft_frontmatter_no_header_returns_empty(workspace, tmp_path):
    p = tmp_path / "no-header.md"
    p.write_text("# Just body\n", encoding="utf-8")
    assert read_draft_frontmatter(p) == {}


# --- load_soul --------------------------------------------------------------


def test_load_soul_missing_returns_empty(workspace):
    assert load_soul(workspace) == {}


def test_load_soul_parses_sections(workspace):
    soul = workspace.knowledge_dir / "soul.md"
    soul.write_text(
        "# Soul\n\n"
        "## Voice\n"
        "- Direct.\n"
        "- No throat-clearing.\n\n"
        "## Values\n"
        "Honest disagreement > polite agreement.\n\n"
        "## Deep work hours\n"
        "09:00-11:00 America/Edmonton\n",
        encoding="utf-8",
    )
    sections = load_soul(workspace)
    assert "Voice" in sections
    assert "Values" in sections
    assert "Deep work hours" in sections
    assert "Direct." in sections["Voice"]
    assert "09:00-11:00" in sections["Deep work hours"]


# --- accept_draft -----------------------------------------------------------


def test_accept_draft_promotes_and_preserves_original(workspace):
    path = write_draft_with_frontmatter(
        "weekly-review",
        body="# Week 21\nReview body\n",
        settings=workspace,
    )
    promoted, original = accept_draft(1, settings=workspace)
    assert promoted.parent == workspace.shed / "reviews"
    assert promoted.exists()
    body = promoted.read_text(encoding="utf-8")
    # Frontmatter is stripped from the promoted copy.
    assert not body.startswith("<!--")
    assert "Week 21" in body
    # Original is preserved with frontmatter intact.
    assert original.exists()
    assert original.read_text(encoding="utf-8").startswith("<!--")
    # Source draft is gone.
    assert not path.exists()
    # INBOX line is removed.
    assert parse_inbox(workspace) == []


def test_accept_draft_default_destination_per_skill(workspace):
    write_draft_with_frontmatter(
        "daily-start", body="# Day\n", settings=workspace,
    )
    promoted, _ = accept_draft(1, settings=workspace)
    assert promoted.parent == workspace.shed / "daily"


def test_accept_draft_with_override_destination(workspace, tmp_path):
    write_draft_with_frontmatter(
        "inbox-triage", body="body", settings=workspace,
    )
    override = tmp_path / "elsewhere"
    promoted, _ = accept_draft(1, settings=workspace, target=override)
    assert promoted.parent == override


def test_accept_draft_no_preserve(workspace):
    write_draft_with_frontmatter(
        "weekly-review", body="body", settings=workspace,
    )
    _, original = accept_draft(1, settings=workspace, preserve_original=False)
    assert original == Path()
    originals_dir = workspace.drafts_dir / "archive" / "originals"
    assert not originals_dir.exists() or not any(originals_dir.iterdir())


def test_accept_draft_missing_index_raises(workspace):
    with pytest.raises(InboxEntryNotFoundError):
        accept_draft(1, settings=workspace)


# --- dismiss_draft ----------------------------------------------------------


def test_dismiss_draft_moves_to_archive_and_clears_inbox(workspace):
    path = write_draft_with_frontmatter(
        "inbox-triage", body="body", settings=workspace,
    )
    archived = dismiss_draft(1, settings=workspace)
    assert archived.parent == workspace.drafts_dir / "archive"
    assert archived.exists()
    assert not path.exists()
    assert parse_inbox(workspace) == []


def test_dismiss_draft_missing_index_raises(workspace):
    with pytest.raises(InboxEntryNotFoundError):
        dismiss_draft(99, settings=workspace)


# --- gc_drafts --------------------------------------------------------------


def test_gc_drafts_archives_stale_and_cleans_inbox(workspace):
    fresh = write_draft_with_frontmatter(
        "inbox-triage", body="fresh", settings=workspace,
    )
    stale = write_draft_with_frontmatter(
        "weekly-review", body="stale", settings=workspace,
    )
    # Backdate the stale draft.
    stale_mtime = (datetime.now() - timedelta(days=30)).timestamp()
    import os
    os.utime(stale, (stale_mtime, stale_mtime))

    archived = gc_drafts(days=7, settings=workspace)
    assert len(archived) == 1
    assert archived[0].name == stale.name
    assert not stale.exists()
    assert fresh.exists()
    # INBOX retains only the fresh entry.
    remaining = parse_inbox(workspace)
    assert len(remaining) == 1
    assert remaining[0].skill == "inbox-triage"


# --- parse_inbox edge cases -------------------------------------------------


def test_parse_inbox_skips_malformed_lines(workspace):
    inbox = workspace.drafts_dir / "INBOX.md"
    workspace.drafts_dir.mkdir(parents=True, exist_ok=True)
    inbox.write_text(
        "# Draft Inbox\n\n"
        "this is not a valid line\n"
        "- [ ] 2026-05-22 08:14 inbox-triage · summary · `drafts/foo.md`\n"
        "another junk line\n"
        "- [ ] 2026-05-22 09:00 daily-start · `drafts/bar.md`\n",
        encoding="utf-8",
    )
    entries = parse_inbox(workspace)
    assert len(entries) == 2
    assert entries[0].skill == "inbox-triage"
    assert entries[1].skill == "daily-start"


def test_parse_inbox_no_file_returns_empty(workspace):
    assert parse_inbox(workspace) == []
