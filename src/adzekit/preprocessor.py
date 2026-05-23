"""Loaders for AdzeKit.

Thin wrappers that read backbone files and return typed objects.
"""

from __future__ import annotations

import hashlib
import re
import socket
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Any

from adzekit.config import Settings, get_settings
from adzekit.models import DailyNote, Loop, Project, ProjectState
from adzekit.parser import parse_daily_note, parse_loops, parse_project


def load_active_loops(settings: Settings | None = None) -> list[Loop]:
    """Load all loops from loops/active.md."""
    settings = settings or get_settings()
    if not settings.loops_active.exists():
        return []
    text = settings.loops_active.read_text(encoding="utf-8")
    if not text.strip():
        return []
    return parse_loops(text)


def load_backlog_loops(settings: Settings | None = None) -> list[Loop]:
    """Load all loops from loops/backlog.md."""
    settings = settings or get_settings()
    if not settings.loops_backlog.exists():
        return []
    text = settings.loops_backlog.read_text(encoding="utf-8")
    if not text.strip():
        return []
    return parse_loops(text)


def load_projects(
    state: ProjectState | None = None,
    settings: Settings | None = None,
) -> list[Project]:
    """Load projects, optionally filtered by state."""
    settings = settings or get_settings()
    projects: list[Project] = []
    state_dirs = {
        ProjectState.ACTIVE: settings.active_dir,
        ProjectState.BACKLOG: settings.backlog_dir,
        ProjectState.ARCHIVE: settings.archive_dir,
    }

    targets = {state: state_dirs[state]} if state and state in state_dirs else state_dirs

    for proj_state, parent in targets.items():
        if not parent.exists():
            continue
        for f in sorted(parent.iterdir()):
            if f.is_file() and f.suffix == ".md":
                projects.append(parse_project(f, proj_state))

    return projects


def load_daily_note(
    target_date: date | None = None,
    settings: Settings | None = None,
) -> DailyNote | None:
    """Load a single daily note by date."""
    settings = settings or get_settings()
    target_date = target_date or date.today()
    path = settings.daily_dir / f"{target_date.isoformat()}.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    return parse_daily_note(text, target_date)


# --- soul.md ----------------------------------------------------------------


def load_soul(settings: Settings | None = None) -> dict[str, str]:
    """Read knowledge/soul.md and return its sections as a dict.

    Sections are level-2 headings (`## Section Name`). Returns an empty dict
    if the file does not exist or has no sections. The body of each section
    is preserved verbatim, including code blocks and lists.
    """
    settings = settings or get_settings()
    path = settings.knowledge_dir / "soul.md"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    sections: dict[str, str] = {}
    current_name: str | None = None
    current_lines: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if current_name is not None:
                sections[current_name] = "\n".join(current_lines).strip()
            current_name = m.group(1).strip()
            current_lines = []
        elif current_name is not None:
            current_lines.append(line)
    if current_name is not None:
        sections[current_name] = "\n".join(current_lines).strip()
    return sections


# --- Draft provenance & INBOX -----------------------------------------------


_HOSTNAME_SAFE_RE = re.compile(r"[^a-z0-9-]")


def short_hostname() -> str:
    """Return the first DNS label of hostname, sanitized to kebab-case."""
    label = socket.gethostname().split(".")[0].lower()
    label = _HOSTNAME_SAFE_RE.sub("-", label).strip("-")
    return label or "host"


def _git_sha_for(path: Path, settings: Settings) -> str | None:
    """Return the short git SHA of the last commit that touched path.

    Best-effort: returns None if path is outside a git repo, untracked, or
    git is unavailable. The shed must be at the repo root for this to work.
    """
    try:
        rel = path.resolve().relative_to(settings.shed.resolve())
    except ValueError:
        return None
    try:
        result = subprocess.run(
            ["git", "log", "-n", "1", "--pretty=format:%h", "--", str(rel)],
            cwd=str(settings.shed),
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    sha = result.stdout.strip()
    return sha or None


def _format_inputs(inputs: list[Path], settings: Settings) -> list[str]:
    """Format a list of input paths as `relpath@sha` lines for the header."""
    lines: list[str] = []
    for raw in inputs:
        p = Path(raw)
        try:
            rel = str(p.resolve().relative_to(settings.shed.resolve()))
        except ValueError:
            rel = str(p)
        sha = _git_sha_for(p, settings)
        lines.append(f"{rel}@{sha}" if sha else rel)
    return lines


def write_draft_with_frontmatter(
    skill_name: str,
    body: str,
    *,
    settings: Settings | None = None,
    inputs: list[Path] | None = None,
    parent: Path | None = None,
    trigger: str = "user",
    confidence: float | None = None,
    summary: str = "",
    timestamp: datetime | None = None,
) -> Path:
    """Write a draft to {SHED}/drafts/ with a provenance HTML-comment header.

    The filename schema is `{skill}-YYYY-MM-DD-HHMMSS-{host}.md`. The seconds
    precision protects against same-minute collisions; on a sub-second collision
    (rare but possible under cron + manual invocation in the same second on the
    same host), a `-N` counter is appended via O_EXCL retry.

    Returns the written path. Also writes a per-entry INBOX sidecar file at
    drafts/INBOX.d/{stem}.entry containing the one-line INBOX text, and
    regenerates drafts/INBOX.md as a human-readable view of all sidecar entries.

    Side-effects:
      - creates drafts/ and drafts/INBOX.d/ if they do not exist
      - writes the draft file (with sub-second collision-safe filename)
      - writes one sidecar file to drafts/INBOX.d/
      - regenerates drafts/INBOX.md from the sidecar dir
    """
    settings = settings or get_settings()
    settings.drafts_dir.mkdir(parents=True, exist_ok=True)

    ts = timestamp or datetime.now().astimezone()
    host = short_hostname()
    safe_skill = re.sub(r"[^a-z0-9-]", "-", skill_name.lower()).strip("-")

    body_hash = "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    input_lines = _format_inputs(inputs or [], settings)

    header_lines = [
        "<!-- adzekit-draft",
        f"skill: {skill_name}",
        f"triggered: {ts.isoformat(timespec='seconds')}",
        f"trigger: {trigger}",
        f"host: {host}",
    ]
    if input_lines:
        header_lines.append("inputs:")
        for line in input_lines:
            header_lines.append(f"  - {line}")
    if parent is not None:
        try:
            parent_rel = str(Path(parent).resolve().relative_to(settings.shed.resolve()))
        except ValueError:
            parent_rel = str(parent)
        header_lines.append(f"parent: {parent_rel}")
    if confidence is not None:
        header_lines.append(f"confidence: {confidence:.2f}")
    if summary:
        header_lines.append(f"summary: {summary}")
    header_lines.append(f"hash: {body_hash}")
    header_lines.append("-->")
    header = "\n".join(header_lines) + "\n"
    full_content = header + (body if body.endswith("\n") else body + "\n")

    # Atomic O_EXCL create with collision retry. The seconds-precision filename
    # already prevents the common collision (cron + manual invocation in the
    # same minute); the -N suffix handles same-second collisions defensively.
    path = _atomic_create_draft(
        settings.drafts_dir, safe_skill, ts, host, full_content,
    )

    _write_inbox_entry(settings, ts, skill_name, summary, path.name)
    return path


def _atomic_create_draft(
    drafts_dir: Path,
    safe_skill: str,
    ts: datetime,
    host: str,
    content: str,
) -> Path:
    """Create a draft file with O_EXCL; on EEXIST, append -1, -2, ... until unique.

    Filename: {skill}-YYYY-MM-DD-HHMMSS-{host}[-N].md
    """
    import os
    date_part = ts.strftime("%Y-%m-%d")
    time_part = ts.strftime("%H%M%S")
    base = f"{safe_skill}-{date_part}-{time_part}-{host}"
    encoded = content.encode("utf-8")
    for suffix in ("",) + tuple(f"-{i}" for i in range(1, 1000)):
        candidate = drafts_dir / f"{base}{suffix}.md"
        try:
            fd = os.open(
                str(candidate),
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o644,
            )
        except FileExistsError:
            continue
        try:
            os.write(fd, encoded)
        finally:
            os.close(fd)
        return candidate
    raise RuntimeError(
        f"Could not create unique draft filename for {base} after 1000 attempts"
    )


def _write_inbox_entry(
    settings: Settings,
    ts: datetime,
    skill_name: str,
    summary: str,
    filename: str,
) -> None:
    """Write a per-entry sidecar to drafts/INBOX.d/ + regenerate INBOX.md view.

    Each new draft gets its own sidecar file `drafts/INBOX.d/{stem}.entry`
    containing the one-line INBOX text. This eliminates the shared-mutation
    race that plagued the old `drafts/INBOX.md` append. Cross-machine git
    merges are conflict-free: per-entry files have unique names (HHMMSS-host
    suffix), so two machines writing the same morning produce two distinct
    sidecar files that merge cleanly.

    `drafts/INBOX.md` is regenerated from the sidecar dir each time as a
    human-readable view. It is intentionally NOT the source of truth.
    """
    inbox_d = settings.drafts_dir / "INBOX.d"
    inbox_d.mkdir(parents=True, exist_ok=True)

    line_summary = f" · {summary}" if summary else ""
    line = (
        f"- [ ] {ts.strftime('%Y-%m-%d %H:%M')} {skill_name}{line_summary}"
        f" · `drafts/{filename}`\n"
    )
    stem = Path(filename).stem
    entry_path = inbox_d / f"{stem}.entry"
    entry_path.write_text(line, encoding="utf-8")

    _regenerate_inbox_view(settings)


def _regenerate_inbox_view(settings: Settings) -> None:
    """Atomically rewrite drafts/INBOX.md from sidecar entries.

    The view is sorted by the entry's date/time prefix so newer drafts
    appear later, matching the original append order. If no sidecar
    entries exist, INBOX.md is removed.

    Each call writes to a per-call unique tempfile and atomically renames
    onto INBOX.md so concurrent regenerations don't race on a shared tmp
    name. The final state may be a stale-but-consistent view (last
    rename wins); the underlying sidecar files are the source of truth so
    no data is lost — only the rendered view might lag for one tick.
    """
    import os
    import tempfile

    inbox_d = settings.drafts_dir / "INBOX.d"
    inbox_md = settings.drafts_dir / "INBOX.md"

    if not inbox_d.exists():
        return

    entries = sorted(inbox_d.glob("*.entry"), key=lambda p: p.name)
    if not entries:
        if inbox_md.exists():
            try:
                inbox_md.unlink()
            except FileNotFoundError:
                pass
        return

    lines = ["# Draft Inbox", ""]
    for entry in entries:
        try:
            text = entry.read_text(encoding="utf-8")
        except FileNotFoundError:
            # Another thread just removed this sidecar; skip it.
            continue
        lines.append(text.rstrip("\n"))
    rendered = "\n".join(lines) + "\n"

    fd, tmp_name = tempfile.mkstemp(
        prefix="INBOX.", suffix=".tmp", dir=str(settings.drafts_dir),
    )
    try:
        os.write(fd, rendered.encode("utf-8"))
    finally:
        os.close(fd)
    Path(tmp_name).replace(inbox_md)


# B3: the closing `-->` must appear on its own line (with optional whitespace),
# not embedded inside a header field. This prevents truncation when a `summary:`
# or `parent:` field happens to contain the literal `-->` substring, and it
# correctly excludes body content (the body comes after the closing line, so
# any `-->` in a markdown code block is never reached because the parser stops
# at the FIRST line that is just `-->`).
_DRAFT_HEADER_RE = re.compile(
    r"\A<!--[ \t]*adzekit-draft[ \t]*\n"
    r"((?:.*\n)*?)"
    r"-->[ \t]*(?:\n|\Z)",
)


def read_draft_frontmatter(path: Path) -> dict[str, Any]:
    """Parse the `<!-- adzekit-draft ... -->` header from a draft.

    Returns a dict with the parsed fields. `inputs` is returned as a list of
    strings. Returns an empty dict if no header is present.
    """
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    m = _DRAFT_HEADER_RE.match(text)
    if not m:
        return {}
    body = m.group(1)
    result: dict[str, Any] = {}
    inputs: list[str] = []
    in_inputs = False
    for line in body.splitlines():
        if not line.strip():
            in_inputs = False
            continue
        if line.startswith("  - ") and in_inputs:
            inputs.append(line[4:].strip())
            continue
        in_inputs = False
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if key == "inputs":
                in_inputs = True
                if val:
                    # single-line variant: inputs: [a, b]
                    inputs.append(val)
            else:
                result[key] = val
    if inputs:
        result["inputs"] = inputs
    return result


def strip_draft_frontmatter(path: Path) -> str:
    """Return draft body with the `<!-- adzekit-draft ... -->` header removed."""
    text = path.read_text(encoding="utf-8")
    return _DRAFT_HEADER_RE.sub("", text, count=1)
