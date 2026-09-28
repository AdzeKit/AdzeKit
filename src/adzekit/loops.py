"""Loops: open commitments, one checkbox line each, in ``loops/active.md``.

    - [ ] (S) [2026-09-08] Send Dana the MCP notes (2026-09-12)
          size  opened      what, to whom                due

Only top-level checkbox lines are loops. Every other line in the file is left
exactly as written, so people and agents can annotate freely.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from adzekit.workspace import Workspace, WorkspaceError, write_atomic

_LINE = re.compile(r"^- \[(?P<mark>[ xX])\] (?P<body>.+)$")
_BODY = re.compile(
    r"^(?:\((?P<size>[A-Z]{1,2})\)\s+)?"
    r"(?:\[(?P<opened>\d{4}-\d{2}-\d{2})\]\s+)?"
    r"(?P<title>.+?)"
    r"(?:\s+\((?P<due>\d{4}-\d{2}-\d{2})\))?\s*$"
)


def _date(text: str | None) -> date | None:
    try:
        return date.fromisoformat(text) if text else None
    except ValueError:
        return None


@dataclass
class Loop:
    line: int
    done: bool
    title: str
    size: str = ""
    opened: date | None = None
    due: date | None = None

    def age(self, today: date) -> int | None:
        return (today - self.opened).days if self.opened else None

    def overdue(self, today: date) -> bool:
        return bool(self.due and self.due < today and not self.done)


def parse(text: str) -> list[Loop]:
    loops = []
    for i, line in enumerate(text.splitlines()):
        match = _LINE.match(line)
        if not match:
            continue
        body = _BODY.match(match["body"])
        loops.append(
            Loop(
                line=i,
                done=match["mark"] != " ",
                title=body["title"],
                size=body["size"] or "",
                opened=_date(body["opened"]),
                due=_date(body["due"]),
            )
        )
    return loops


def _read(ws: Workspace) -> str:
    if not ws.loops_file.is_file():
        raise WorkspaceError(f"Missing {ws.loops_file}. Run `adzekit init`.")
    return ws.loops_file.read_text(encoding="utf-8")


def open_loops(ws: Workspace) -> list[Loop]:
    return [loop for loop in parse(_read(ws)) if not loop.done]


def format_line(title: str, opened: date, size: str = "", due: date | None = None) -> str:
    parts = ["- [ ]"]
    if size:
        parts.append(f"({size.upper()})")
    parts += [f"[{opened.isoformat()}]", title.strip()]
    if due:
        parts.append(f"({due.isoformat()})")
    return " ".join(parts)


def add(ws: Workspace, title: str, *, today: date, size: str = "", due: date | None = None) -> str:
    """Insert a loop after the last existing loop line. Returns the new line."""
    text = _read(ws)
    lines = text.splitlines()
    new = format_line(title, today, size, due)
    existing = parse(text)
    if existing:
        lines.insert(existing[-1].line + 1, new)
    else:
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ["", new] if lines else [new]
    write_atomic(ws.loops_file, "\n".join(lines) + "\n")
    return new


def resolve(ws: Workspace, ref: str) -> Loop:
    """Find an open loop by its list number (1-based) or a unique text match."""
    candidates = open_loops(ws)
    if ref.isdigit():
        index = int(ref) - 1
        if not 0 <= index < len(candidates):
            raise WorkspaceError(f"No open loop #{ref} (there are {len(candidates)}).")
        return candidates[index]
    matches = [loop for loop in candidates if ref.lower() in loop.title.lower()]
    if not matches:
        raise WorkspaceError(f"No open loop matches {ref!r}.")
    if len(matches) > 1:
        titles = "\n".join(f"  - {m.title}" for m in matches)
        raise WorkspaceError(f"{len(matches)} loops match {ref!r}; be more specific:\n{titles}")
    return matches[0]


def close(ws: Workspace, ref: str) -> Loop:
    """Tick a loop in place. ``sweep`` later moves it to the archive."""
    loop = resolve(ws, ref)
    lines = _read(ws).splitlines()
    lines[loop.line] = lines[loop.line].replace("- [ ]", "- [x]", 1)
    write_atomic(ws.loops_file, "\n".join(lines) + "\n")
    loop.done = True
    return loop


def sweep(ws: Workspace, *, today: date) -> list[str]:
    """Move ticked loops to ``loops/archive.md`` under today's heading."""
    lines = _read(ws).splitlines()
    done_rows = {loop.line for loop in parse("\n".join(lines)) if loop.done}
    if not done_rows:
        return []
    swept = [lines[i] for i in sorted(done_rows)]
    kept = [line for i, line in enumerate(lines) if i not in done_rows]
    write_atomic(ws.loops_file, "\n".join(kept) + "\n")

    heading = f"## {today.isoformat()}"
    archive = (
        ws.loops_archive.read_text(encoding="utf-8").rstrip()
        if ws.loops_archive.is_file()
        else "# Archived Loops"
    )
    last_heading = next(
        (line for line in reversed(archive.splitlines()) if line.startswith("## ")), None
    )
    if last_heading != heading:
        archive += f"\n\n{heading}"
    write_atomic(ws.loops_archive, archive + "\n" + "\n".join(swept) + "\n")
    return swept
