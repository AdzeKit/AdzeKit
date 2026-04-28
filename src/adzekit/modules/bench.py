"""Bench triage: surface draft proposals and clear processed items.

The bench (bench.md) is the human-facing triage queue for agent proposals.
Agents write to drafts/; the cull command scans that directory and populates
the ## Pending section of bench.md with entries the human hasn't processed yet.

Lifecycle:
  1. Agent writes a file to drafts/
  2. `adzekit cull` adds an entry to ## Pending (if not already listed)
  3. Human reads the draft, copies loops, discards -- marks the entry [x]
  4. Next `adzekit cull` clears [x] items from ## Pending
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from adzekit.config import Settings, get_settings

PENDING_RE = re.compile(r"^\- \[[ x]\] .+\((.+?)\)\s*$")


def _extract_title(path: Path) -> str:
    """Read the first markdown heading from a draft file, or fall back to the stem."""
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line.lstrip("# ").strip()
    except OSError:
        pass
    return path.stem


def _file_timestamp(path: Path) -> datetime:
    """Return the file's modification time as a datetime."""
    return datetime.fromtimestamp(path.stat().st_mtime)


def _format_pending_entry(draft: Path) -> str:
    """Build a pending-queue line for a draft file."""
    title = _extract_title(draft)
    ts = _file_timestamp(draft)
    ts_str = ts.strftime("%Y-%m-%d %H:%M")
    return f"- [ ] [{ts_str}] {title} ({draft.name})"


def _parse_bench(text: str) -> tuple[list[str], list[str], list[str]]:
    """Split bench.md into (header, pending_lines, rest).

    header: lines before ## Pending (including the heading itself)
    pending_lines: the checklist lines under ## Pending
    rest: everything from the next heading onward (## Quick Capture, etc.)
    """
    lines = text.splitlines()
    header: list[str] = []
    pending: list[str] = []
    rest: list[str] = []

    section = "header"
    for line in lines:
        if line.strip() == "## Pending":
            header.append(line)
            section = "pending"
            continue

        if section == "pending" and line.startswith("## "):
            section = "rest"

        if section == "header":
            header.append(line)
        elif section == "pending":
            pending.append(line)
        else:
            rest.append(line)

    return header, pending, rest


def _referenced_filenames(pending_lines: list[str]) -> set[str]:
    """Extract draft filenames already referenced in ## Pending."""
    names: set[str] = set()
    for line in pending_lines:
        m = PENDING_RE.match(line)
        if m:
            names.add(m.group(1).strip())
    return names


def _list_draft_files(settings: Settings) -> list[Path]:
    """List triageable draft files (top-level .md, excluding special files)."""
    drafts = settings.drafts_dir
    if not drafts.exists():
        return []
    return sorted(
        (f for f in drafts.iterdir() if f.is_file() and f.suffix == ".md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


_BENCH_TS_RE = re.compile(r"^- \[ \] \[(\d{4}-\d{2}-\d{2})(?: \d{2}:\d{2})?\] (.+?)(?:\s*\([^)]+\))?$")


def stale_bench_items(
    settings: Settings | None = None,
    days: int | None = None,
) -> list[dict]:
    """Return open ('- [ ]') bench items older than N days.

    Each item is a {"text": ..., "date": "YYYY-MM-DD", "days": int} dict, oldest first.
    """
    from datetime import date as _date

    settings = settings or get_settings()
    threshold = days if days is not None else settings.stale_loop_days
    bench = settings.bench_path
    if not bench.exists():
        return []

    today = _date.today()
    results: list[dict] = []

    for line in bench.read_text(encoding="utf-8").splitlines():
        m = _BENCH_TS_RE.match(line.strip())
        if not m:
            continue
        try:
            d = _date.fromisoformat(m.group(1))
        except ValueError:
            continue
        age = (today - d).days
        if age >= threshold:
            results.append({"text": m.group(2).strip(), "date": d.isoformat(), "days": age})

    results.sort(key=lambda x: -x["days"])
    return results


def cull(settings: Settings | None = None) -> tuple[int, int]:
    """Scan drafts/ and update bench.md.

    1. Remove [x] (processed) items from ## Pending.
    2. Add entries for draft files not yet listed.

    Returns (added_count, cleared_count).
    """
    settings = settings or get_settings()
    bench = settings.bench_path

    if not bench.exists():
        bench.write_text("# Bench\n\n## Pending\n\n## Quick Capture\n", encoding="utf-8")

    text = bench.read_text(encoding="utf-8")
    header, pending_lines, rest = _parse_bench(text)

    # If the file has no ## Pending section, inject one before ## Quick Capture
    if not any(line.strip() == "## Pending" for line in header):
        header = ["# Bench", "", "## Pending"]
        if not rest:
            rest = ["## Quick Capture"]

    cleared = 0
    kept: list[str] = []
    for line in pending_lines:
        if line.strip().startswith("- [x]"):
            cleared += 1
        elif line.strip():
            kept.append(line)

    already_listed = _referenced_filenames(kept)
    drafts = _list_draft_files(settings)

    added = 0
    for draft in drafts:
        if draft.name not in already_listed:
            kept.append(_format_pending_entry(draft))
            added += 1

    # Rebuild bench.md
    result_lines = header + [""] + kept + [""] + rest
    bench.write_text("\n".join(result_lines) + "\n", encoding="utf-8")

    return added, cleared
