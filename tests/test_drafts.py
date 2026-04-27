"""Tests for draft pruning."""

import os
from datetime import datetime, timedelta

from adzekit.cli import main
from adzekit.modules.drafts import prune_drafts


def _age_file(path, days):
    """Set a file's mtime to ``days`` days ago."""
    old_time = (datetime.now() - timedelta(days=days)).timestamp()
    os.utime(path, (old_time, old_time))


def test_deletes_old_files(workspace):
    old = workspace.drafts_dir / "old-draft.md"
    old.write_text("# Old\n")
    _age_file(old, 10)

    deleted = prune_drafts(days=7, settings=workspace)
    assert len(deleted) == 1
    assert deleted[0].name == "old-draft.md"
    assert not old.exists()


def test_keeps_recent_files(workspace):
    recent = workspace.drafts_dir / "recent-draft.md"
    recent.write_text("# Recent\n")

    deleted = prune_drafts(days=7, settings=workspace)
    assert len(deleted) == 0
    assert recent.exists()


def test_prunes_watermark_files(workspace):
    wm = workspace.drafts_dir / "inbox-watermark.md"
    wm.write_text("latest = 2026-01-01\n")
    _age_file(wm, 10)

    deleted = prune_drafts(days=7, settings=workspace)
    assert any(p.name == "inbox-watermark.md" for p in deleted)


def test_respects_days_argument(workspace):
    draft = workspace.drafts_dir / "draft.md"
    draft.write_text("# Draft\n")
    _age_file(draft, 3)

    assert prune_drafts(days=7, settings=workspace) == []
    assert draft.exists()

    deleted = prune_drafts(days=2, settings=workspace)
    assert len(deleted) == 1


def test_uses_config_default(workspace):
    draft = workspace.drafts_dir / "draft.md"
    draft.write_text("# Draft\n")
    _age_file(draft, 10)

    deleted = prune_drafts(settings=workspace)
    assert len(deleted) == 1


def test_ignores_non_md_files(workspace):
    json_file = workspace.drafts_dir / "data.json"
    json_file.write_text("{}")
    _age_file(json_file, 10)

    deleted = prune_drafts(days=7, settings=workspace)
    assert len(deleted) == 0
    assert json_file.exists()


def test_ignores_subdirectories(workspace):
    sub = workspace.drafts_dir / "sessions"
    sub.mkdir()
    draft = sub / "old.md"
    draft.write_text("# Sub\n")
    _age_file(draft, 10)

    deleted = prune_drafts(days=7, settings=workspace)
    assert len(deleted) == 0
    assert draft.exists()


def test_empty_drafts(workspace):
    deleted = prune_drafts(settings=workspace)
    assert deleted == []


def test_cli_prune_drafts(tmp_path, capsys):
    main(["init", str(tmp_path / "shed")])
    main(["--shed", str(tmp_path / "shed"), "prune-drafts"])
    output = capsys.readouterr().out
    assert "No stale drafts" in output
