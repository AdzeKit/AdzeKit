"""Core data models for AdzeKit.

Plain dataclasses for in-memory representations. On disk everything is markdown.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


# ---------------------------------------------------------------------------
# Knowledge Graph Ontology
# ---------------------------------------------------------------------------


class EntityType(str, Enum):
    """Canonical entity types in the AdzeKit knowledge graph.

    Person       Named individual — detected from #firstname-lastname tags.
    Organization Company, team, client, or institution.
    Project      Active/backlog/archive work item from projects/.
    Concept      Abstract idea, pattern, methodology, or domain area.
    Tool         Software product, platform, API, or service.
    Loop         Tracked commitment from loops/active.md.
    Event        Specific time-bound occurrence.
    """

    PERSON = "person"
    ORGANIZATION = "organization"
    PROJECT = "project"
    CONCEPT = "concept"
    TOOL = "tool"
    LOOP = "loop"
    EVENT = "event"


class RelationType(str, Enum):
    """Typed edge labels in the AdzeKit knowledge graph.

    is-a          Taxonomic: A is a subtype/instance of B. Transitive.
    part-of       Compositional: A is a component of B.
    uses          Dependency: A employs or depends on B.
    relates-to    General association (symmetric). Auto-generated from [[WikiLinks]].
    owned-by      Accountability: project/work owned by person/org.
    assigned-to   Commitment: loop owed to/from a person.
    mentioned-in  Co-occurrence: entity appears in a document.
    developed-by  Provenance: tool/concept created by person/org.
    contradicts   Opposition: A conflicts with B (symmetric in practice).
    extends       Augmentation: A builds on or specialises B.
    """

    IS_A = "is-a"
    PART_OF = "part-of"
    USES = "uses"
    RELATES_TO = "relates-to"
    OWNED_BY = "owned-by"
    ASSIGNED_TO = "assigned-to"
    MENTIONED_IN = "mentioned-in"
    DEVELOPED_BY = "developed-by"
    CONTRADICTS = "contradicts"
    EXTENDS = "extends"


@dataclass
class Entity:
    """A node in the knowledge graph."""

    name: str
    entity_type: EntityType
    sources: list[str] = field(default_factory=list)


@dataclass
class Relationship:
    """A typed directed edge in the knowledge graph."""

    source: str
    target: str
    relation_type: RelationType
    source_file: str = ""


@dataclass
class KnowledgeGraph:
    """In-memory knowledge graph for a shed."""

    entities: dict[str, Entity] = field(default_factory=dict)
    relationships: list[Relationship] = field(default_factory=list)
    built_at: date | None = None


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
    size: str = ""


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
