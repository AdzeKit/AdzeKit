"""Core data models for AdzeKit.

Plain dataclasses for in-memory representations. On disk everything is markdown.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class LoopStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


@dataclass
class Loop:
    """A commitment to another person requiring closure."""

    date: date
    title: str
    who: str
    what: str
    due: date | None = None
    status: str = "Open"
    next_action: str = ""
    project: str = ""


class ProjectState(str, Enum):
    BACKLOG = "backlog"
    ACTIVE = "active"
    ARCHIVE = "archive"


@dataclass
class Task:
    """A single checklist item."""

    description: str
    done: bool = False


@dataclass
class Project:
    """A single project markdown file parsed into structured data."""

    slug: str
    state: ProjectState
    title: str = ""
    tasks: list[Task] = field(default_factory=list)
    raw_content: str = ""

    @property
    def progress(self) -> float:
        if not self.tasks:
            return 0.0
        return sum(1 for t in self.tasks if t.done) / len(self.tasks)


@dataclass
class LogEntry:
    """A timestamped log entry from the daily note."""

    time: str
    text: str


@dataclass
class DailyNote:
    """A single day's note with morning intentions, log, and reflection."""

    date: date
    intentions: list[Task] = field(default_factory=list)
    log: list[LogEntry] = field(default_factory=list)
    finished: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    tomorrow: list[str] = field(default_factory=list)
    raw_content: str = ""
