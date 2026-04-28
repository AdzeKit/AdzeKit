"""Knowledge graph builder and querier for AdzeKit sheds.

Extracts entities and typed relationships from backbone content and
serializes them to graph/ for efficient, compressed context retrieval.

Extraction sources (in priority order):
  1. Typed relationship headers in knowledge notes
     (**is-a:**, **uses:**, etc.)
  2. [[WikiLink]] syntax → relates-to
  3. #tag patterns → entity discovery (person, tool, org)
  4. projects/ filenames → Project entities
  5. loops/active.md entries → Loop entities + assigned-to

Output files (git-tracked, agent-maintained):
  graph/entities.md   Entity registry by type
  graph/relations.md  Typed relationship index
  graph/index.md      Summary: counts, top nodes, orphans
"""

import re
from datetime import date
from pathlib import Path

from adzekit.config import Settings
from adzekit.models import Entity, EntityType, KnowledgeGraph, Relationship, RelationType


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# [[WikiLink]] or [[WikiLink|display text]]
_WIKI_LINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")

# **relation-type:** targets on a single line
_TYPED_REL_HEADER = re.compile(
    r"^\*\*("
    r"is-a|part-of|uses|relates-to|owned-by|assigned-to"
    r"|mentioned-in|developed-by|contradicts|extends"
    r"):\*\*\s+(.+)$",
    re.MULTILINE | re.IGNORECASE,
)

# #tag token — lowercase letters, digits, hyphens; must start with a letter
_TAG = re.compile(r"#([a-z][a-z0-9-]{0,49})", re.IGNORECASE)

# Person tag heuristic: two or more hyphen-separated lowercase word segments
# e.g. alice-chen, ryan-bondaria, andrey-karpathy
_PERSON_TAG = re.compile(r"^[a-z]+-[a-z]+(-[a-z]+)*$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _parse_rel_type(raw: str) -> RelationType | None:
    try:
        return RelationType(raw.lower())
    except ValueError:
        return None


def _extract_wikilink_targets(content: str) -> list[str]:
    return [_slugify(m.group(1)) for m in _WIKI_LINK.finditer(content)]


def _extract_typed_rels(content: str, source_slug: str, source_file: str) -> list[Relationship]:
    rels: list[Relationship] = []
    for m in _TYPED_REL_HEADER.finditer(content):
        rel = _parse_rel_type(m.group(1))
        if rel is None:
            continue
        targets_raw = m.group(2)
        # Prefer [[WikiLink]] targets; fall back to comma-separated plain text
        targets = [_slugify(t) for t in _WIKI_LINK.findall(targets_raw)]
        if not targets:
            targets = [_slugify(t) for t in targets_raw.split(",") if t.strip()]
        for target in targets:
            if target and target != source_slug:
                rels.append(Relationship(
                    source=source_slug,
                    target=target,
                    relation_type=rel,
                    source_file=source_file,
                ))
    return rels


def _infer_entity_type(tags: list[str]) -> EntityType:
    """Infer entity type from hint tags; default to Concept."""
    tag_set = {t.lower() for t in tags}
    if "tool" in tag_set or "platform" in tag_set or "service" in tag_set:
        return EntityType.TOOL
    if "person" in tag_set or "contact" in tag_set:
        return EntityType.PERSON
    if "organization" in tag_set or "org" in tag_set or "client" in tag_set:
        return EntityType.ORGANIZATION
    if "event" in tag_set:
        return EntityType.EVENT
    return EntityType.CONCEPT


# ---------------------------------------------------------------------------
# Graph mutation helpers
# ---------------------------------------------------------------------------


def _add_entity(
    graph: KnowledgeGraph,
    name: str,
    entity_type: EntityType,
    source: str,
) -> None:
    name = name.lower()
    if name in graph.entities:
        if source and source not in graph.entities[name].sources:
            graph.entities[name].sources.append(source)
    else:
        graph.entities[name] = Entity(
            name=name,
            entity_type=entity_type,
            sources=[source] if source else [],
        )


def _ensure_entity(
    graph: KnowledgeGraph,
    name: str,
    default_type: EntityType,
) -> None:
    name = name.lower()
    if name not in graph.entities:
        graph.entities[name] = Entity(name=name, entity_type=default_type, sources=[])


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def build_graph(settings: Settings) -> KnowledgeGraph:
    """Build a fresh KnowledgeGraph by scanning all backbone content."""
    graph = KnowledgeGraph(built_at=date.today())
    shed = settings.shed

    _extract_knowledge_notes(graph, settings, shed)
    _extract_projects(graph, settings, shed)
    _extract_person_tags(graph, settings, shed)
    _extract_loops(graph, settings)
    # Run prose extraction last so the entity registry is fully populated
    # before we scan free-form text for mentions of registered entities.
    _extract_prose_mentions(graph, settings, shed)

    return graph


def _extract_knowledge_notes(
    graph: KnowledgeGraph,
    settings: Settings,
    shed: Path,
) -> None:
    for path in sorted(settings.knowledge_dir.glob("*.md")):
        slug = path.stem
        rel_path = str(path.relative_to(shed))
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue

        tags = [m.group(1).lower() for m in _TAG.finditer(content)]
        entity_type = _infer_entity_type(tags)
        _add_entity(graph, slug, entity_type, rel_path)

        # Typed relationship headers
        for rel in _extract_typed_rels(content, slug, rel_path):
            _ensure_entity(graph, rel.target, EntityType.CONCEPT)
            graph.relationships.append(rel)

        # [[WikiLinks]] → relates-to
        for target in _extract_wikilink_targets(content):
            if target and target != slug:
                _ensure_entity(graph, target, EntityType.CONCEPT)
                graph.relationships.append(Relationship(
                    source=slug,
                    target=target,
                    relation_type=RelationType.RELATES_TO,
                    source_file=rel_path,
                ))


def _extract_projects(
    graph: KnowledgeGraph,
    settings: Settings,
    shed: Path,
) -> None:
    project_dirs = [
        settings.active_dir,
        settings.backlog_dir,
        settings.archive_dir,
    ]
    for dir_path in project_dirs:
        if not dir_path.exists():
            continue
        for path in sorted(dir_path.glob("*.md")):
            slug = path.stem
            rel_path = str(path.relative_to(shed))
            _add_entity(graph, slug, EntityType.PROJECT, rel_path)

            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                continue

            for m in _TAG.finditer(content):
                tag = m.group(1).lower()
                if tag == slug:
                    continue  # self-tag (project file references its own slug)
                if _PERSON_TAG.match(tag):
                    _ensure_entity(graph, tag, EntityType.PERSON)
                    graph.relationships.append(Relationship(
                        source=slug,
                        target=tag,
                        relation_type=RelationType.MENTIONED_IN,
                        source_file=rel_path,
                    ))

            # Typed relationship headers in project files (**uses:**, **part-of:**, etc.)
            for rel in _extract_typed_rels(content, slug, rel_path):
                _ensure_entity(graph, rel.target, EntityType.CONCEPT)
                graph.relationships.append(rel)

            # [[WikiLinks]] in project files → relates-to
            for target in _extract_wikilink_targets(content):
                if target and target != slug:
                    _ensure_entity(graph, target, EntityType.CONCEPT)
                    graph.relationships.append(Relationship(
                        source=slug,
                        target=target,
                        relation_type=RelationType.RELATES_TO,
                        source_file=rel_path,
                    ))


def _extract_person_tags(
    graph: KnowledgeGraph,
    settings: Settings,
    shed: Path,
) -> None:
    scan_dirs = [settings.daily_dir, settings.loops_dir]
    for dir_path in scan_dirs:
        if not dir_path.exists():
            continue
        for path in sorted(dir_path.rglob("*.md")):
            rel_path = str(path.relative_to(shed))
            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for m in _TAG.finditer(content):
                tag = m.group(1).lower()
                if _PERSON_TAG.match(tag):
                    _add_entity(graph, tag, EntityType.PERSON, rel_path)


def _extract_prose_mentions(
    graph: KnowledgeGraph,
    settings: Settings,
    shed: Path,
) -> None:
    """Find prose mentions of known concept/project/tool/org entities and add
    ``mentioned-in`` edges.

    Why: external processes (e.g. the Slack ingestion skill) append rich text
    to knowledge notes without using ``[[wikilinks]]`` or typed headers. That
    content references Lakebase, MLflow, MCP, etc. in plain prose — invisible
    to the typed-relationship and wikilink extractors. This pass closes the
    gap by case-insensitive whole-word matching against the registry.

    Constraints (to avoid false positives):
    - Only matches against entities of type ``concept``, ``project``, ``tool``,
      ``organization`` — skips ``person`` and ``loop``.
    - Slugs shorter than 4 characters are skipped.
    - Matches are deduplicated against existing relationships.
    - Self-mentions (a knowledge note matching its own slug) are skipped.
    - Only knowledge/ and projects/ files are scanned — files with a clear
      ``source`` entity (the file's own slug). Daily/reviews don't have a
      single owning entity so we skip them here.
    """
    # Build a lookup: slug → compiled regex. Hyphens in slugs match either a
    # space or a hyphen in prose, so "knowledge-assistant" finds "Knowledge
    # Assistant" or "knowledge-assistant".
    candidates: dict[str, re.Pattern[str]] = {}
    for entity in graph.entities.values():
        if entity.entity_type.value not in ("concept", "project", "tool", "organization"):
            continue
        if len(entity.name) < 4:
            continue
        words = entity.name.split("-")
        if len(words) == 1:
            pat = re.compile(rf"\b{re.escape(words[0])}\b", re.IGNORECASE)
        else:
            sep = r"[\s\-]+"
            pat = re.compile(rf"\b{sep.join(re.escape(w) for w in words)}\b", re.IGNORECASE)
        candidates[entity.name] = pat

    if not candidates:
        return

    # Dedupe on (source, target) regardless of relation type. If a structured
    # extractor already linked these two entities (uses / part-of / relates-to /
    # wikilink → relates-to), don't add a redundant mentioned-in edge from
    # prose. The prose pass only fires when nothing structural saw the link.
    existing_pairs: set[tuple[str, str]] = {
        (r.source, r.target) for r in graph.relationships
    }

    scan_dirs = [settings.knowledge_dir, settings.projects_dir]
    for d in scan_dirs:
        if not d.exists():
            continue
        for path in sorted(d.rglob("*.md")):
            if not path.is_file():
                continue
            source_slug = path.stem
            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                continue
            rel_path = str(path.relative_to(shed))

            for target, pat in candidates.items():
                if target == source_slug:
                    continue
                if (source_slug, target) in existing_pairs:
                    continue
                if pat.search(content):
                    graph.relationships.append(Relationship(
                        source=source_slug,
                        target=target,
                        relation_type=RelationType.MENTIONED_IN,
                        source_file=rel_path,
                    ))
                    existing_pairs.add((source_slug, target))


def _extract_loops(graph: KnowledgeGraph, settings: Settings) -> None:
    if not settings.loops_active.exists():
        return
    rel_path = str(settings.loops_active.relative_to(settings.shed))
    try:
        from adzekit.preprocessor import load_active_loops
        loops = load_active_loops(settings)
    except Exception:
        return

    for loop in loops:
        slug = _slugify(loop.title)
        if not slug:
            continue
        _add_entity(graph, slug, EntityType.LOOP, rel_path)
        if loop.who:
            person = _slugify(loop.who)
            _ensure_entity(graph, person, EntityType.PERSON)
            graph.relationships.append(Relationship(
                source=slug,
                target=person,
                relation_type=RelationType.ASSIGNED_TO,
                source_file=rel_path,
            ))


# ---------------------------------------------------------------------------
# Serialise
# ---------------------------------------------------------------------------


def save_graph(graph: KnowledgeGraph, settings: Settings) -> None:
    """Write graph/entities.md, graph/relations.md, graph/index.md."""
    graph_dir = settings.graph_dir
    graph_dir.mkdir(parents=True, exist_ok=True)
    _write_entities(graph, graph_dir)
    _write_relations(graph, graph_dir)
    _write_index(graph, graph_dir)


def _write_entities(graph: KnowledgeGraph, graph_dir: Path) -> None:
    built = graph.built_at.isoformat() if graph.built_at else "unknown"
    lines = [f"# Entity Registry\n\n<!-- Built: {built} -->\n"]

    by_type: dict[EntityType, list[Entity]] = {}
    for entity in graph.entities.values():
        by_type.setdefault(entity.entity_type, []).append(entity)

    for etype in EntityType:
        entities = sorted(by_type.get(etype, []), key=lambda e: e.name)
        if not entities:
            continue
        lines.append(f"\n## {etype.value.title()}s\n")
        for e in entities:
            sources_str = ", ".join(f"`{s}`" for s in e.sources[:3])
            lines.append(f"- `{e.name}` [{sources_str}]\n")

    (graph_dir / "entities.md").write_text("".join(lines), encoding="utf-8")


def _write_relations(graph: KnowledgeGraph, graph_dir: Path) -> None:
    built = graph.built_at.isoformat() if graph.built_at else "unknown"
    lines = [f"# Relationship Index\n\n<!-- Built: {built} -->\n"]

    by_type: dict[RelationType, list[Relationship]] = {}
    for rel in graph.relationships:
        by_type.setdefault(rel.relation_type, []).append(rel)

    for rtype in RelationType:
        rels = sorted(by_type.get(rtype, []), key=lambda r: (r.source, r.target))
        if not rels:
            continue
        lines.append(f"\n## {rtype.value}\n")
        for r in rels:
            lines.append(f"- `{r.source}` → `{r.target}`\n")

    (graph_dir / "relations.md").write_text("".join(lines), encoding="utf-8")


def _write_index(graph: KnowledgeGraph, graph_dir: Path) -> None:
    built = graph.built_at.isoformat() if graph.built_at else "unknown"
    stats = graph_stats(graph)

    # Degree centrality
    degree: dict[str, int] = {}
    for rel in graph.relationships:
        degree[rel.source] = degree.get(rel.source, 0) + 1
        degree[rel.target] = degree.get(rel.target, 0) + 1
    top = sorted(degree.items(), key=lambda x: -x[1])[:5]

    connected = (
        {r.source for r in graph.relationships}
        | {r.target for r in graph.relationships}
    )
    orphan_names = sorted(n for n in graph.entities if n not in connected)

    lines = [
        "# Knowledge Graph Index\n\n",
        f"Built: {built}\n",
        f"Entities: {stats['total_entities']}",
        f" ({stats['people']} people, {stats['organizations']} orgs,",
        f" {stats['projects']} projects, {stats['concepts']} concepts,",
        f" {stats['tools']} tools, {stats['loops']} loops)\n",
        f"Relationships: {stats['total_relationships']}\n",
    ]

    if top:
        lines.append("\n## Most Connected\n")
        for name, count in top:
            lines.append(f"- `{name}` ({count} connections)\n")

    if orphan_names:
        lines.append("\n## Orphans (no connections)\n")
        for name in orphan_names[:15]:
            lines.append(f"- `{name}`\n")

    (graph_dir / "index.md").write_text("".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------


def load_graph(settings: Settings) -> KnowledgeGraph | None:
    """Load graph from graph/entities.md + graph/relations.md. Returns None if not built."""
    entities_path = settings.graph_dir / "entities.md"
    relations_path = settings.graph_dir / "relations.md"
    if not entities_path.exists() or not relations_path.exists():
        return None

    graph = KnowledgeGraph()
    _load_entities(graph, entities_path)
    _load_relations(graph, relations_path)
    return graph


def _load_entities(graph: KnowledgeGraph, path: Path) -> None:
    content = path.read_text(encoding="utf-8")
    current_type: EntityType | None = None

    # "## Concepts" → EntityType.CONCEPT, etc.
    heading_map: dict[str, EntityType] = {}
    for etype in EntityType:
        heading_map[f"{etype.value.title()}s"] = etype

    for line in content.splitlines():
        if line.startswith("## "):
            current_type = heading_map.get(line[3:].strip())
        elif line.startswith("- `") and current_type is not None:
            m = re.match(r"- `([^`]+)`\s*\[([^\]]*)\]", line)
            if m:
                name = m.group(1)
                sources = [
                    s.strip().strip("`")
                    for s in m.group(2).split(",")
                    if s.strip()
                ]
                graph.entities[name] = Entity(
                    name=name,
                    entity_type=current_type,
                    sources=sources,
                )


def _load_relations(graph: KnowledgeGraph, path: Path) -> None:
    content = path.read_text(encoding="utf-8")
    current_type: RelationType | None = None

    for line in content.splitlines():
        if line.startswith("## "):
            try:
                current_type = RelationType(line[3:].strip())
            except ValueError:
                current_type = None
        elif line.startswith("- `") and current_type is not None:
            m = re.match(r"- `([^`]+)` → `([^`]+)`", line)
            if m:
                graph.relationships.append(Relationship(
                    source=m.group(1),
                    target=m.group(2),
                    relation_type=current_type,
                ))


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


def get_context(entity_name: str, graph: KnowledgeGraph, depth: int = 2) -> str:
    """Return a compressed context string for entity_name, traversing up to depth hops."""
    name = entity_name.lower()
    if name not in graph.entities:
        return f"Entity '{entity_name}' not found in graph. Run: adzekit graph build"

    visited: set[str] = set()
    frontier = {name}
    all_nodes: set[str] = {name}

    for _ in range(depth):
        next_layer: set[str] = set()
        for node in frontier:
            for rel in graph.relationships:
                if rel.source == node and rel.target not in visited:
                    next_layer.add(rel.target)
                if rel.target == node and rel.source not in visited:
                    next_layer.add(rel.source)
        visited |= frontier
        frontier = next_layer - visited
        all_nodes |= frontier

    relevant_rels = [
        r for r in graph.relationships
        if r.source in all_nodes and r.target in all_nodes
    ]

    entity = graph.entities[name]
    parts = [f"## Graph context: {name} ({entity.entity_type.value})"]
    if entity.sources:
        parts.append(f"Sources: {', '.join(entity.sources[:3])}")

    if relevant_rels:
        parts.append("Relationships:")
        for rel in sorted(relevant_rels, key=lambda r: (r.relation_type.value, r.source)):
            parts.append(f"  {rel.source} --[{rel.relation_type.value}]--> {rel.target}")

    neighbors = sorted(all_nodes - {name})
    if neighbors:
        parts.append(f"Connected: {', '.join(neighbors)}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def graph_stats(graph: KnowledgeGraph) -> dict:
    counts: dict[str, int] = {t.value: 0 for t in EntityType}
    for e in graph.entities.values():
        counts[e.entity_type.value] += 1
    return {
        "total_entities": len(graph.entities),
        "total_relationships": len(graph.relationships),
        "people": counts.get("person", 0),
        "organizations": counts.get("organization", 0),
        "projects": counts.get("project", 0),
        "concepts": counts.get("concept", 0),
        "tools": counts.get("tool", 0),
        "loops": counts.get("loop", 0),
        "events": counts.get("event", 0),
    }
