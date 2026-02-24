"""Markdown parser for AdzeKit.

Reads structured markdown formats and returns typed model objects.
"""

import re
from datetime import date
from pathlib import Path

from adzekit.models import (
    DailyNote,
    LogEntry,
    Loop,
    Project,
    ProjectState,
    Task,
)


# --- Loop parsing ---

# Flat checklist format: - [ ] (SIZE) [DATE] title (DUE-DATE)
_FLAT_LOOP_RE = re.compile(
    r"^-\s+\[([ xX])\]\s+"        # checkbox
    r"(?:\(([A-Z]{1,2})\)\s+)?"   # optional (SIZE)
    r"(?:\[(\d{4}-\d{2}-\d{2})\]\s+)?"  # optional [DATE created]
    r"(.+)$"                       # title (rest of line, may end with due date)
)
# Trailing due date: (YYYY-MM-DD) at end of title
_TRAILING_DUE_RE = re.compile(r"\((\d{4}-\d{2}-\d{2})\)\s*$")

# Legacy structured format header: ## [DATE] Title
_LOOP_HEADER = re.compile(
    r"^##\s+\[(\d{4}-\d{2}-\d{2})\]\s+(.+)$"
)
_LOOP_FIELD = re.compile(
    r"^-\s+\*\*(\w[\w\s]*):\*\*\s*(.+)$"
)


def parse_loops(text: str) -> list[Loop]:
    """Parse loops from markdown. Supports both flat checklist and structured formats.

    Flat format:   - [ ] (XS) [2026-02-17] Sync on Altus work
    Structured:    ## [2026-02-17] Title  + field lines
    """
    loops: list[Loop] = []
    current: dict | None = None

    for line in text.split("\n"):
        stripped = line.strip()

        # Try flat checklist format first
        flat = _FLAT_LOOP_RE.match(stripped)
        if flat:
            # Flush any pending structured loop
            if current:
                loops.append(_dict_to_loop(current))
                current = None

            done = flat.group(1).lower() == "x"
            size = flat.group(2) or ""
            loop_date = flat.group(3)
            title = flat.group(4).strip()

            # Extract trailing due date (YYYY-MM-DD) from title
            due = None
            due_match = _TRAILING_DUE_RE.search(title)
            if due_match:
                try:
                    due = date.fromisoformat(due_match.group(1))
                    title = title[:due_match.start()].strip()
                except ValueError:
                    pass

            loops.append(Loop(
                date=date.fromisoformat(loop_date) if loop_date else date.today(),
                title=title,
                who="",
                what="",
                due=due,
                status="Closed" if done else "Open",
                size=size,
            ))
            continue

        # Try structured header format
        header = _LOOP_HEADER.match(stripped)
        if header:
            if current:
                loops.append(_dict_to_loop(current))
            current = {
                "date": header.group(1),
                "title": header.group(2).strip(),
            }
            continue

        if current is not None:
            field_match = _LOOP_FIELD.match(stripped)
            if field_match:
                key = field_match.group(1).strip().lower()
                value = field_match.group(2).strip()
                current[key] = value

    if current:
        loops.append(_dict_to_loop(current))

    return loops


def _dict_to_loop(d: dict) -> Loop:
    due = None
    if "due" in d and d["due"]:
        try:
            due = date.fromisoformat(d["due"])
        except ValueError:
            pass
    return Loop(
        date=date.fromisoformat(d["date"]),
        title=d.get("title", ""),
        who=d.get("who", ""),
        what=d.get("what", ""),
        due=due,
        status=d.get("status", "Open"),
        next_action=d.get("next", ""),
        project=d.get("project", ""),
    )


def format_loop(loop: Loop) -> str:
    """Serialize a Loop to flat checklist markdown with inline date."""
    check = "[x]" if loop.status.lower() == "closed" else "[ ]"
    parts = [f"- {check}"]
    if loop.size:
        parts.append(f"({loop.size})")
    parts.append(f"[{loop.date.isoformat()}]")
    parts.append(loop.title)
    if loop.due:
        parts.append(f"({loop.due.isoformat()})")
    return " ".join(parts)


def format_loops(loops: list[Loop]) -> str:
    """Serialize a list of loops to markdown lines."""
    return "\n".join(format_loop(l) for l in loops)


# --- Task parsing ---

_TASK_RE = re.compile(r"^-\s+\[([ xX])\]\s+(.+)$")


def parse_tasks(text: str) -> list[Task]:
    """Parse markdown checklist items into Task objects."""
    tasks: list[Task] = []
    for line in text.split("\n"):
        m = _TASK_RE.match(line.strip())
        if m:
            tasks.append(Task(description=m.group(2), done=m.group(1).lower() == "x"))
    return tasks


def format_tasks(tasks: list[Task]) -> str:
    """Serialize tasks back to markdown checklist."""
    lines = []
    for t in tasks:
        check = "[x]" if t.done else "[ ]"
        lines.append(f"- {check} {t.description}")
    return "\n".join(lines)


# --- Project parsing ---


def parse_project(project_path: Path, state: ProjectState) -> Project:
    """Parse a single project markdown file into a Project object.

    Tasks are extracted from the ``## Log`` section where checklist items
    and dated events are interleaved.
    """
    slug = project_path.stem
    text = project_path.read_text(encoding="utf-8")
    title = slug
    tasks: list[Task] = []

    in_log = False
    for line in text.split("\n"):
        stripped = line.strip()

        # Title from the first top-level heading
        if stripped.startswith("# ") and not stripped.startswith("## "):
            title = stripped.lstrip("# ").strip()
            continue

        # Detect section boundaries
        if stripped.lower() == "## log":
            in_log = True
            continue
        if stripped.startswith("## "):
            in_log = False
            continue

        if in_log:
            m = _TASK_RE.match(stripped)
            if m:
                tasks.append(Task(description=m.group(2), done=m.group(1).lower() == "x"))

    return Project(
        slug=slug,
        state=state,
        title=title,
        tasks=tasks,
        raw_content=text,
    )


# --- Daily note parsing ---

_LOG_ENTRY_RE = re.compile(r"^-\s+(\d{1,2}:\d{2})\s+(.+)$")
_BOLD_ITEM_RE = re.compile(r"^-\s+\*\*(\w+):\*\*\s*(.+)$")


def parse_daily_note(text: str, note_date: date) -> DailyNote:
    """Parse a daily note markdown file into a DailyNote object."""
    intentions: list[Task] = []
    log: list[LogEntry] = []
    finished: list[str] = []
    blocked: list[str] = []
    tomorrow: list[str] = []

    section = ""
    for line in text.split("\n"):
        stripped = line.strip()

        lower = stripped.lower()
        if "morning" in lower and "intention" in lower:
            section = "intention"
            continue
        elif lower.startswith("## log") or lower == "## log":
            section = "log"
            continue
        elif "evening" in lower and "reflection" in lower:
            section = "reflection"
            continue

        if section == "intention":
            m = _TASK_RE.match(stripped)
            if m:
                intentions.append(Task(description=m.group(2), done=m.group(1).lower() == "x"))

        elif section == "log":
            m = _LOG_ENTRY_RE.match(stripped)
            if m:
                log.append(LogEntry(time=m.group(1), text=m.group(2)))

        elif section == "reflection":
            m = _BOLD_ITEM_RE.match(stripped)
            if m:
                key = m.group(1).lower()
                value = m.group(2)
                if key == "finished":
                    finished.append(value)
                elif key == "blocked":
                    blocked.append(value)
                elif key == "tomorrow":
                    tomorrow.append(value)

    return DailyNote(
        date=note_date,
        intentions=intentions,
        log=log,
        finished=finished,
        blocked=blocked,
        tomorrow=tomorrow,
        raw_content=text,
    )
