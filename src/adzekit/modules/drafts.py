"""Stale draft pruning.

Deletes markdown files in drafts/ older than a configurable threshold.
Watermark files are included -- deleting them forces a rescan per the
backbone spec.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from adzekit.config import Settings, get_settings


def _list_md_files(settings: Settings) -> list[Path]:
    """List all top-level .md files in drafts/."""
    drafts = settings.drafts_dir
    if not drafts.exists():
        return []
    return [f for f in drafts.iterdir() if f.is_file() and f.suffix == ".md"]


def prune_drafts(
    days: int | None = None,
    settings: Settings | None = None,
) -> list[Path]:
    """Delete .md files in drafts/ older than ``days`` days.

    Defaults to ``settings.stale_draft_days`` (7) when days is None.
    Returns list of deleted file paths.
    """
    settings = settings or get_settings()
    days = days if days is not None else settings.stale_draft_days
    cutoff = datetime.now() - timedelta(days=days)

    deleted: list[Path] = []
    for path in _list_md_files(settings):
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        if mtime < cutoff:
            path.unlink()
            deleted.append(path)

    return deleted
