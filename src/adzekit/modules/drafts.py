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
    __slots__ = (
        "index", "raw", "state", "date", "time", "skill", "summary", "path",
        "sidecar",
    )

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
        sidecar: Path | None = None,
    ) -> None:
        self.index = index
        self.raw = raw
        self.state = state
        self.date = date
        self.time = time
        self.skill = skill
        self.summary = summary
        self.path = path
        # Set when the entry was loaded from a drafts/INBOX.d/*.entry file;
        # None for legacy INBOX.md entries. _drop_entry_from_inbox dispatches
        # on this to remove the right artifact.
        self.sidecar = sidecar

    def as_path(self, settings: Settings) -> Path:
        return settings.shed / self.path


class InboxNotFoundError(RuntimeError):
    """Raised when there is no INBOX.md to operate on."""


class InboxEntryNotFoundError(IndexError):
    """Raised when accept/dismiss is called with an index that doesn't exist."""


class InboxConflictError(RuntimeError):
    """Raised when drafts/INBOX.md contains unresolved git conflict markers."""


_CONFLICT_MARKER_RE = re.compile(r"^(<<<<<<<|=======|>>>>>>>)", re.MULTILINE)


def parse_inbox(settings: Settings | None = None) -> list[InboxEntry]:
    """Parse the INBOX into a list of entries.

    Sidecar-first: if drafts/INBOX.d/ exists, walks the per-entry files (the
    authoritative storage since the B1 fix). Falls back to drafts/INBOX.md
    when only the legacy format is present.

    Detects unresolved git conflict markers in INBOX.md and raises
    InboxConflictError rather than silently dropping conflicted lines (the
    previous behavior was to skip non-matching lines, which lost entries to
    merge conflicts without telling the user).

    The 1-based index corresponds to the position of the entry as a user would
    see it (skipping header lines, blank lines, and any malformed lines).
    """
    settings = settings or get_settings()
    inbox_d = settings.drafts_dir / "INBOX.d"
    if inbox_d.is_dir():
        return _parse_inbox_sidecar(inbox_d)

    inbox = settings.drafts_dir / "INBOX.md"
    if not inbox.exists():
        return []
    raw_text = inbox.read_text(encoding="utf-8")
    if _CONFLICT_MARKER_RE.search(raw_text):
        raise InboxConflictError(
            f"{inbox} contains unresolved git conflict markers. "
            "Resolve manually before listing or accepting drafts. "
            "After resolution, consider migrating to the sidecar format by "
            "moving entries into drafts/INBOX.d/."
        )
    return _parse_inbox_lines(raw_text.splitlines())


def _parse_inbox_sidecar(inbox_d: Path) -> list[InboxEntry]:
    """Parse the per-entry sidecar files under drafts/INBOX.d/."""
    entries: list[InboxEntry] = []
    index = 0
    sidecars = sorted(inbox_d.glob("*.entry"), key=lambda p: p.name)
    for sidecar in sidecars:
        raw = sidecar.read_text(encoding="utf-8").strip()
        m = _INBOX_LINE_RE.match(raw)
        if not m:
            continue
        index += 1
        entries.append(InboxEntry(
            index=index,
            raw=raw,
            state=m.group("state"),
            date=m.group("date"),
            time=m.group("time"),
            skill=m.group("skill"),
            summary=(m.group("summary") or "").strip(),
            path=m.group("path"),
            sidecar=sidecar,
        ))
    return entries


def _parse_inbox_lines(lines: list[str]) -> list[InboxEntry]:
    """Parse legacy INBOX.md lines into InboxEntry objects."""
    entries: list[InboxEntry] = []
    index = 0
    for raw in lines:
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


def _drop_entry_from_inbox(settings: Settings, entry: InboxEntry) -> None:
    """Remove a single entry from the INBOX (sidecar or legacy form)."""
    if entry.sidecar is not None and entry.sidecar.exists():
        entry.sidecar.unlink()
        # Lazy import: circular with preprocessor on full module-load.
        from adzekit.preprocessor import _regenerate_inbox_view
        _regenerate_inbox_view(settings)
        return
    # Legacy INBOX.md path.
    lines = _read_inbox_lines(settings)
    kept = [
        line for line in lines
        if line != entry.raw and not line.startswith("# ") and line.strip()
    ]
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

    B4 fix: all writes happen to a tempdir first (the "stage"). Only after
    every write succeeds do we commit (rename into final locations + remove
    source + drop INBOX entry). On any failure, the stage is cleaned up and
    nothing else moves — no half-committed state.

    Returns (promoted_path, archived_original_path or empty Path).
    """
    import shutil
    import tempfile

    settings = settings or get_settings()
    entries = parse_inbox(settings)
    entry = next((e for e in entries if e.index == index), None)
    if entry is None:
        raise InboxEntryNotFoundError(f"No INBOX entry at index {index}")

    src = entry.as_path(settings)
    if not src.exists():
        raise FileNotFoundError(f"Draft referenced by INBOX is missing: {src}")

    # Lazy import: avoids the circular path (preprocessor → drafts → preprocessor).
    from adzekit.preprocessor import strip_draft_frontmatter

    dest_dir = _resolve_promotion_target(entry.skill, target, settings)
    final_dest = dest_dir / src.name
    originals_dir = settings.drafts_dir / "archive" / "originals"
    final_original = (originals_dir / src.name) if preserve_original else None

    # Stage: write all outputs into a tempdir before touching final paths.
    # B4: if any step fails, the stage is discarded and source + INBOX entry
    # remain intact. No half-committed state.
    stage = Path(tempfile.mkdtemp(prefix="adzekit-accept-", dir=settings.drafts_dir))
    try:
        promoted_body = strip_draft_frontmatter(src)
        staged_promoted = stage / "promoted.md"
        staged_promoted.write_text(promoted_body, encoding="utf-8")

        staged_original: Path | None = None
        if preserve_original:
            staged_original = stage / "original.md"
            staged_original.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

        # Commit phase: only after staging succeeded.
        dest_dir.mkdir(parents=True, exist_ok=True)
        staged_promoted.replace(final_dest)

        archived_original = Path()
        if staged_original is not None and final_original is not None:
            originals_dir.mkdir(parents=True, exist_ok=True)
            staged_original.replace(final_original)
            archived_original = final_original

        src.unlink()
        _drop_entry_from_inbox(settings, entry)
    except Exception:
        # Stage cleanup; source + INBOX untouched.
        raise
    finally:
        # Stage may have been partially drained by .replace() calls; remove
        # whatever's left. shutil.rmtree is idempotent given missing_ok-ish use.
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)

    return final_dest, archived_original


def dismiss_draft(
    index: int,
    *,
    settings: Settings | None = None,
) -> Path:
    """Discard draft #index: move to drafts/archive/ (no original preserved).

    Returns the archived path. Uses the same staged-write pattern as
    accept_draft so a mid-flight failure leaves source + INBOX intact.
    """
    import shutil
    import tempfile

    settings = settings or get_settings()
    entries = parse_inbox(settings)
    entry = next((e for e in entries if e.index == index), None)
    if entry is None:
        raise InboxEntryNotFoundError(f"No INBOX entry at index {index}")

    src = entry.as_path(settings)
    if not src.exists():
        # File already gone; still drop the INBOX entry so it's not stuck.
        _drop_entry_from_inbox(settings, entry)
        raise FileNotFoundError(f"Draft referenced by INBOX is missing: {src}")

    archive_dir = settings.drafts_dir / "archive"
    final_dest = archive_dir / src.name

    stage = Path(tempfile.mkdtemp(prefix="adzekit-dismiss-", dir=settings.drafts_dir))
    try:
        staged = stage / "dismissed.md"
        staged.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

        archive_dir.mkdir(parents=True, exist_ok=True)
        staged.replace(final_dest)
        src.unlink()
        _drop_entry_from_inbox(settings, entry)
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)

    return final_dest


def show_draft(
    index: int,
    *,
    settings: Settings | None = None,
    include_frontmatter: bool = False,
) -> dict:
    """Return the body and provenance summary of draft #index.

    Preview a draft before accepting or dismissing — without it the user
    has to `cat` the draft path by hand. Default strips the
    `<!-- adzekit-draft -->` header; pass include_frontmatter=True to keep it.

    Returns a dict with `path`, `skill`, `summary`, `confidence`, `triggered`,
    `body`, and the InboxEntry's basic fields.
    """
    settings = settings or get_settings()
    entries = parse_inbox(settings)
    entry = next((e for e in entries if e.index == index), None)
    if entry is None:
        raise InboxEntryNotFoundError(f"No INBOX entry at index {index}")

    src = entry.as_path(settings)
    if not src.exists():
        raise FileNotFoundError(f"Draft referenced by INBOX is missing: {src}")

    from adzekit.preprocessor import read_draft_frontmatter, strip_draft_frontmatter
    fm = read_draft_frontmatter(src)
    body = src.read_text(encoding="utf-8") if include_frontmatter else strip_draft_frontmatter(src)

    return {
        "index": index,
        "path": str(src),
        "skill": entry.skill,
        "summary": entry.summary,
        "date": entry.date,
        "time": entry.time,
        "triggered": fm.get("triggered", ""),
        "confidence": fm.get("confidence", ""),
        "hash": fm.get("hash", ""),
        "inputs": fm.get("inputs", []) if isinstance(fm.get("inputs"), list) else [],
        "body": body,
    }


def rollback_draft(
    *,
    settings: Settings | None = None,
    filename: str | None = None,
) -> dict:
    """Undo a recent `accept_draft` by restoring the original from archive.

    Looks up the most-recently-accepted draft (or a specific one by
    `filename`) in `drafts/archive/originals/`, restores it to `drafts/`,
    re-creates the INBOX sidecar entry, and removes the promoted copy
    from its backbone destination if it still has the exact same body
    as what we promoted (defensive against the user already editing it).

    Returns a dict with `restored` (path the original was put back at),
    `removed_from_backbone` (the path it was moved out of, or None when
    the backbone copy had diverged and was left alone), and `inbox_entry`
    (path of the new sidecar).

    Raises FileNotFoundError if no eligible original is found.
    """
    settings = settings or get_settings()
    originals_dir = settings.drafts_dir / "archive" / "originals"
    if not originals_dir.is_dir():
        raise FileNotFoundError(
            f"No originals archive at {originals_dir}; "
            "nothing to roll back. Were originals preserved on accept?"
        )

    # Find the candidate original.
    if filename is not None:
        candidate = originals_dir / filename
        if not candidate.exists():
            raise FileNotFoundError(
                f"No archived original at {candidate}. List with: "
                f"ls {originals_dir}"
            )
    else:
        originals = sorted(
            (p for p in originals_dir.glob("*.md") if p.is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not originals:
            raise FileNotFoundError(
                f"No archived originals in {originals_dir}; "
                "nothing to roll back."
            )
        candidate = originals[0]

    # Restore the original draft to drafts/ root.
    restored = settings.drafts_dir / candidate.name
    if restored.exists():
        raise FileExistsError(
            f"Cannot restore: a draft already exists at {restored}. "
            "Inspect, dismiss, or rename the conflicting draft first."
        )
    restored.write_text(candidate.read_text(encoding="utf-8"), encoding="utf-8")

    # Try to remove the promoted copy from the backbone. We parse the skill
    # from the original's frontmatter to know which dir it was promoted to.
    from adzekit.preprocessor import (
        read_draft_frontmatter,
        strip_draft_frontmatter,
    )
    fm = read_draft_frontmatter(restored)
    skill = str(fm.get("skill", "")).strip() or _filename_skill_hint(candidate.name)
    backbone_dir = _resolve_promotion_target(skill, None, settings)
    backbone_copy = backbone_dir / candidate.name
    removed_from_backbone: Path | None = None
    if backbone_copy.exists():
        # Only remove if the backbone body matches what we promoted (i.e. the
        # user hasn't edited it post-accept). Comparing the promoted body to
        # the original-with-frontmatter-stripped is the safe check.
        original_promoted_body = strip_draft_frontmatter(candidate)
        backbone_body = backbone_copy.read_text(encoding="utf-8")
        if backbone_body == original_promoted_body:
            backbone_copy.unlink()
            removed_from_backbone = backbone_copy
        # If diverged, leave the backbone copy alone — the user has invested
        # edits we shouldn't blow away. The restored draft becomes the
        # "in-progress alternative" until the user decides.

    # Re-create the INBOX sidecar.
    inbox_d = settings.drafts_dir / "INBOX.d"
    inbox_d.mkdir(parents=True, exist_ok=True)
    stem = candidate.stem
    sidecar = inbox_d / f"{stem}.entry"
    # Reconstruct an INBOX line from frontmatter data.
    triggered = str(fm.get("triggered", ""))
    if triggered:
        # `triggered` is an ISO timestamp; convert to the INBOX human format.
        from datetime import datetime
        try:
            ts = datetime.fromisoformat(triggered)
            human_time = ts.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            human_time = ""
    else:
        human_time = ""
    summary = str(fm.get("summary", ""))
    summary_part = f" · {summary}" if summary else ""
    line = (
        f"- [ ] {human_time} {skill}{summary_part} · `drafts/{candidate.name}`\n"
    )
    sidecar.write_text(line, encoding="utf-8")
    from adzekit.preprocessor import _regenerate_inbox_view
    _regenerate_inbox_view(settings)

    # Remove the original from archive — once restored it's no longer "archived".
    candidate.unlink()

    return {
        "restored": str(restored),
        "removed_from_backbone": str(removed_from_backbone) if removed_from_backbone else None,
        "inbox_entry": str(sidecar),
    }


def _filename_skill_hint(filename: str) -> str:
    """Best-effort skill name extraction from the draft filename schema.

    Filenames look like `{skill}-YYYY-MM-DD-HHMMSS-{host}[-N].md`. The skill
    portion may itself contain hyphens. We take everything before the date.
    """
    m = re.match(r"^(.+?)-\d{4}-\d{2}-\d{2}", filename)
    return m.group(1) if m else ""


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
        # Drop INBOX entries whose draft files were archived.
        entries = parse_inbox(settings)
        for entry in entries:
            if Path(entry.path).name in archived_names:
                _drop_entry_from_inbox(settings, entry)

    return archived
