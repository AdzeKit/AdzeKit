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

    The filename schema is `{skill}-YYYY-MM-DD-HHMM-{host}.md`. Returns the
    written path. Also appends a single line to drafts/INBOX.md.

    Side-effects:
      - creates drafts/ if it does not exist
      - writes the draft file
      - appends to drafts/INBOX.md (creating it with a header line if absent)
    """
    settings = settings or get_settings()
    settings.drafts_dir.mkdir(parents=True, exist_ok=True)

    ts = timestamp or datetime.now().astimezone()
    date_part = ts.strftime("%Y-%m-%d")
    time_part = ts.strftime("%H%M")
    host = short_hostname()
    safe_skill = re.sub(r"[^a-z0-9-]", "-", skill_name.lower()).strip("-")
    filename = f"{safe_skill}-{date_part}-{time_part}-{host}.md"
    path = settings.drafts_dir / filename

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

    path.write_text(header + body if body.endswith("\n") else header + body + "\n",
                    encoding="utf-8")

    _append_to_inbox(settings, ts, skill_name, summary, filename)
    return path


def _append_to_inbox(
    settings: Settings,
    ts: datetime,
    skill_name: str,
    summary: str,
    filename: str,
) -> None:
    """Append a single line to drafts/INBOX.md."""
    inbox = settings.drafts_dir / "INBOX.md"
    line_summary = f" · {summary}" if summary else ""
    line = (
        f"- [ ] {ts.strftime('%Y-%m-%d %H:%M')} {skill_name}{line_summary}"
        f" · `drafts/{filename}`\n"
    )
    if not inbox.exists():
        inbox.write_text("# Draft Inbox\n\n" + line, encoding="utf-8")
        return
    existing = inbox.read_text(encoding="utf-8")
    if not existing.endswith("\n"):
        existing += "\n"
    inbox.write_text(existing + line, encoding="utf-8")


_DRAFT_HEADER_RE = re.compile(
    r"\A<!--\s*adzekit-draft\s*\n(.*?)\n-->\s*\n?",
    re.DOTALL,
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
