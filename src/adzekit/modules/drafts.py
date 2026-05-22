"""Draft lifecycle.

Phase 2:
- Stale draft pruning (existing).
- INBOX queue parsing and mutation.
- accept / dismiss flows that preserve originals for distillation.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

from adzekit.config import Settings, get_settings

# --- Existing: stale pruning ------------------------------------------------


def _list_md_files(settings: Settings) -> list[Path]:
    """List all top-level .md files in drafts/ (excluding INBOX.md)."""
    drafts = settings.drafts_dir
    if not drafts.exists():
        return []
    return [
        f for f in drafts.iterdir()
        if f.is_file() and f.suffix == ".md" and f.name != "INBOX.md"
    ]


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


# --- INBOX parsing ----------------------------------------------------------


_INBOX_LINE_RE = re.compile(
    r"^- \[(?P<state>[ xX])\]\s+"
    r"(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2})\s+"
    r"(?P<skill>\S+)"
    r"(?:\s+·\s+(?P<summary>.+?))?"
    r"\s+·\s+`(?P<path>drafts/[^`]+)`\s*$"
)


class InboxEntry:
    __slots__ = ("index", "raw", "state", "date", "time", "skill", "summary", "path")

    def __init__(
        self,
        *,
        index: int,
        raw: str,
        state: str,
        date: str,
        time: str,
        skill: str,
        summary: str,
        path: str,
    ) -> None:
        self.index = index
        self.raw = raw
        self.state = state
        self.date = date
        self.time = time
        self.skill = skill
        self.summary = summary
        self.path = path

    def as_path(self, settings: Settings) -> Path:
        return settings.shed / self.path


class InboxNotFoundError(RuntimeError):
    """Raised when there is no INBOX.md to operate on."""


class InboxEntryNotFoundError(IndexError):
    """Raised when accept/dismiss is called with an index that doesn't exist."""


def parse_inbox(settings: Settings | None = None) -> list[InboxEntry]:
    """Parse drafts/INBOX.md into a list of entries.

    The 1-based index corresponds to the position of the entry as a user would
    see it (skipping header lines, blank lines, and any malformed lines).
    """
    settings = settings or get_settings()
    inbox = settings.drafts_dir / "INBOX.md"
    if not inbox.exists():
        return []
    entries: list[InboxEntry] = []
    index = 0
    for raw in inbox.read_text(encoding="utf-8").splitlines():
        m = _INBOX_LINE_RE.match(raw)
        if not m:
            continue
        index += 1
        entries.append(
            InboxEntry(
                index=index,
                raw=raw,
                state=m.group("state"),
                date=m.group("date"),
                time=m.group("time"),
                skill=m.group("skill"),
                summary=(m.group("summary") or "").strip(),
                path=m.group("path"),
            )
        )
    return entries


def _rewrite_inbox(settings: Settings, kept: list[str]) -> None:
    inbox = settings.drafts_dir / "INBOX.md"
    if not kept:
        inbox.write_text("# Draft Inbox\n\n", encoding="utf-8")
        return
    inbox.write_text("# Draft Inbox\n\n" + "\n".join(kept) + "\n", encoding="utf-8")


def _read_inbox_lines(settings: Settings) -> list[str]:
    inbox = settings.drafts_dir / "INBOX.md"
    if not inbox.exists():
        raise InboxNotFoundError(f"No INBOX at {inbox}")
    return inbox.read_text(encoding="utf-8").splitlines()


def _drop_entry_from_inbox(settings: Settings, target_raw: str) -> None:
    lines = _read_inbox_lines(settings)
    kept = [line for line in lines if line != target_raw and not line.startswith("# ") and line.strip()]
    _rewrite_inbox(settings, kept)


# --- accept / dismiss / gc --------------------------------------------------


_DEFAULT_PROMOTION_TARGETS: dict[str, str] = {
    # skill name -> target backbone subdir (relative to shed root)
    "daily-start": "daily",
    "daily-close": "daily",
    "weekly-review": "reviews",
    "graph-update": "knowledge",
    "graph-connect": "knowledge",
    "graph-enrich": "knowledge",
    "slack-capture": "knowledge",
    "inbox-triage": "drafts/archive",  # triage reports don't promote; they archive on accept
    "loop-momentum": "drafts/archive",  # same; the loop updates have already been applied manually
}


def _resolve_promotion_target(
    skill: str,
    target_override: Path | None,
    settings: Settings,
) -> Path:
    """Decide where an accepted draft should land in the backbone."""
    if target_override is not None:
        return target_override
    subdir = _DEFAULT_PROMOTION_TARGETS.get(skill, "drafts/archive")
    return settings.shed / subdir


def accept_draft(
    index: int,
    *,
    settings: Settings | None = None,
    target: Path | None = None,
    preserve_original: bool = True,
) -> tuple[Path, Path]:
    """Promote draft #index from INBOX to its backbone destination.

    The frontmatter HTML comment is stripped during promotion (backbone is
    human-owned; provenance comments belong in workbench only).

    The original draft (with frontmatter intact) is moved to
    drafts/archive/originals/ when preserve_original=True. This is what the
    distill skill reads to detect repeated edit patterns.

    Returns (promoted_path, archived_original_path or empty Path).
    """
    settings = settings or get_settings()
    entries = parse_inbox(settings)
    entry = next((e for e in entries if e.index == index), None)
    if entry is None:
        raise InboxEntryNotFoundError(f"No INBOX entry at index {index}")

    src = entry.as_path(settings)
    if not src.exists():
        raise FileNotFoundError(f"Draft referenced by INBOX is missing: {src}")

    # Strip the provenance comment for the promoted copy. We import lazily to
    # avoid a circular import (preprocessor depends on Settings; this module
    # depends on Settings; preprocessor imports from this module would loop).
    from adzekit.preprocessor import strip_draft_frontmatter

    promoted_body = strip_draft_frontmatter(src)
    dest_dir = _resolve_promotion_target(entry.skill, target, settings)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    dest.write_text(promoted_body, encoding="utf-8")

    archived_original = Path()
    if preserve_original:
        originals_dir = settings.drafts_dir / "archive" / "originals"
        originals_dir.mkdir(parents=True, exist_ok=True)
        archived_original = originals_dir / src.name
        archived_original.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    src.unlink()
    _drop_entry_from_inbox(settings, entry.raw)
    return dest, archived_original


def dismiss_draft(
    index: int,
    *,
    settings: Settings | None = None,
) -> Path:
    """Discard draft #index: move to drafts/archive/ (no original preserved).

    Returns the archived path.
    """
    settings = settings or get_settings()
    entries = parse_inbox(settings)
    entry = next((e for e in entries if e.index == index), None)
    if entry is None:
        raise InboxEntryNotFoundError(f"No INBOX entry at index {index}")

    src = entry.as_path(settings)
    if not src.exists():
        # File already gone; still drop the INBOX line so it's not stuck.
        _drop_entry_from_inbox(settings, entry.raw)
        raise FileNotFoundError(f"Draft referenced by INBOX is missing: {src}")

    archive_dir = settings.drafts_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    dest = archive_dir / src.name
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    src.unlink()
    _drop_entry_from_inbox(settings, entry.raw)
    return dest


def gc_drafts(
    days: int | None = None,
    *,
    settings: Settings | None = None,
) -> list[Path]:
    """Move stale drafts older than ``days`` to drafts/archive/.

    Differs from prune_drafts (which deletes) by archiving instead, and by
    cleaning up the INBOX entries that pointed at the gc'd files.
    Returns list of archived paths.
    """
    settings = settings or get_settings()
    days = days if days is not None else settings.stale_draft_days
    cutoff = datetime.now() - timedelta(days=days)

    archive_dir = settings.drafts_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    archived: list[Path] = []
    archived_names: set[str] = set()
    for path in _list_md_files(settings):
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        if mtime < cutoff:
            dest = archive_dir / path.name
            dest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            path.unlink()
            archived.append(dest)
            archived_names.add(path.name)

    if archived_names:
        # Drop matching INBOX lines.
        entries = parse_inbox(settings)
        keep_raw = [
            e.raw for e in entries if Path(e.path).name not in archived_names
        ]
        _rewrite_inbox(settings, keep_raw)

    return archived
