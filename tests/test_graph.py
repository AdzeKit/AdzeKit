"""Tests for the knowledge graph module (modules/graph.py)."""

import pytest

from adzekit.config import Settings
from adzekit.models import EntityType, RelationType
from adzekit.modules.graph import (
    build_graph,
    get_context,
    graph_stats,
    load_graph,
    save_graph,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace(tmp_path):
    settings = Settings(shed=tmp_path)
    settings.write_marker()
    settings.ensure_shed()
    return settings


def _write_knowledge(settings: Settings, slug: str, content: str) -> None:
    (settings.knowledge_dir / f"{slug}.md").write_text(content, encoding="utf-8")


def _write_project(settings: Settings, slug: str, content: str) -> None:
    (settings.active_dir / f"{slug}.md").write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------


class TestEntityExtraction:
    def test_knowledge_note_becomes_concept_entity(self, workspace):
        _write_knowledge(workspace, "vector-search", "# Vector Search\n\n#concept\n\nContent.\n")
        graph = build_graph(workspace)
        assert "vector-search" in graph.entities
        assert graph.entities["vector-search"].entity_type == EntityType.CONCEPT

    def test_tool_tag_sets_entity_type(self, workspace):
        _write_knowledge(workspace, "databricks", "# Databricks\n\n#tool\n\nContent.\n")
        graph = build_graph(workspace)
        assert graph.entities["databricks"].entity_type == EntityType.TOOL

    def test_organization_tag_sets_entity_type(self, workspace):
        _write_knowledge(workspace, "anthropic", "# Anthropic\n\n#organization\n\nContent.\n")
        graph = build_graph(workspace)
        assert graph.entities["anthropic"].entity_type == EntityType.ORGANIZATION

    def test_project_file_becomes_project_entity(self, workspace):
        _write_project(workspace, "my-project", "# My Project\n\n## Context\n\nWhy.\n")
        graph = build_graph(workspace)
        assert "my-project" in graph.entities
        assert graph.entities["my-project"].entity_type == EntityType.PROJECT

    def test_person_tag_in_project_detected(self, workspace):
        _write_project(workspace, "acme-migration", "# Acme\n\n#alice-chen #project\n\nContent.\n")
        graph = build_graph(workspace)
        assert "alice-chen" in graph.entities
        assert graph.entities["alice-chen"].entity_type == EntityType.PERSON

    def test_single_word_tag_not_classified_as_person(self, workspace):
        _write_knowledge(workspace, "rag", "# RAG\n\n#rag\n\nContent.\n")
        graph = build_graph(workspace)
        # "rag" is a single-segment tag — should be a concept from the note, not a person
        assert "rag" in graph.entities
        assert graph.entities["rag"].entity_type != EntityType.PERSON

    def test_source_path_recorded(self, workspace):
        _write_knowledge(workspace, "mcp", "# MCP\n\n#tool\n\nContent.\n")
        graph = build_graph(workspace)
        entity = graph.entities["mcp"]
        assert any("knowledge/mcp.md" in s for s in entity.sources)


# ---------------------------------------------------------------------------
# Relationship extraction
# ---------------------------------------------------------------------------


class TestRelationshipExtraction:
    def test_typed_header_is_a(self, workspace):
        _write_knowledge(
            workspace, "vector-search",
            "# Vector Search\n\n#concept\n\n**is-a:** [[retrieval-method]]\n\nContent.\n",
        )
        graph = build_graph(workspace)
        rels = [r for r in graph.relationships if r.relation_type == RelationType.IS_A]
        assert any(r.source == "vector-search" and r.target == "retrieval-method" for r in rels)

    def test_typed_header_part_of(self, workspace):
        _write_knowledge(
            workspace, "genie",
            "# Genie\n\n#tool\n\n**part-of:** [[databricks]]\n\nContent.\n",
        )
        graph = build_graph(workspace)
        rels = [r for r in graph.relationships if r.relation_type == RelationType.PART_OF]
        assert any(r.source == "genie" and r.target == "databricks" for r in rels)

    def test_typed_header_multiple_targets(self, workspace):
        _write_knowledge(
            workspace, "rag",
            "# RAG\n\n#concept\n\n**uses:** [[vector-search]], [[llm]]\n\nContent.\n",
        )
        graph = build_graph(workspace)
        rels = [r for r in graph.relationships if r.relation_type == RelationType.USES]
        targets = {r.target for r in rels if r.source == "rag"}
        assert "vector-search" in targets
        assert "llm" in targets

    def test_wikilink_generates_relates_to(self, workspace):
        _write_knowledge(
            workspace, "vector-search",
            "# Vector Search\n\n#concept\n\nSee also [[knowledge-graphs]].\n",
        )
        graph = build_graph(workspace)
        rels = [r for r in graph.relationships if r.relation_type == RelationType.RELATES_TO]
        assert any(r.source == "vector-search" and r.target == "knowledge-graphs" for r in rels)

    def test_wikilink_does_not_self_loop(self, workspace):
        _write_knowledge(
            workspace, "rag",
            "# RAG\n\n#concept\n\nSee [[rag]] for details.\n",
        )
        graph = build_graph(workspace)
        self_loops = [
            r for r in graph.relationships if r.source == "rag" and r.target == "rag"
        ]
        assert len(self_loops) == 0

    def test_typed_header_extends(self, workspace):
        _write_knowledge(
            workspace, "software-3-0",
            "# Software 3.0\n\n#concept\n\n**extends:** [[software-2-0]]\n\nContent.\n",
        )
        graph = build_graph(workspace)
        rels = [r for r in graph.relationships if r.relation_type == RelationType.EXTENDS]
        assert any(r.source == "software-3-0" and r.target == "software-2-0" for r in rels)

    def test_project_person_tag_creates_mentioned_in(self, workspace):
        _write_project(
            workspace, "fourseasons-rag",
            "# Four Seasons RAG\n\n#ryan-bondaria\n\n## Context\n\nWhy.\n",
        )
        graph = build_graph(workspace)
        rels = [r for r in graph.relationships if r.relation_type == RelationType.MENTIONED_IN]
        assert any(r.source == "fourseasons-rag" and r.target == "ryan-bondaria" for r in rels)

    def test_plain_text_targets_in_typed_header(self, workspace):
        _write_knowledge(
            workspace, "rag",
            "# RAG\n\n#concept\n\n**relates-to:** vector-search, llm\n\nContent.\n",
        )
        graph = build_graph(workspace)
        rels = [r for r in graph.relationships if r.relation_type == RelationType.RELATES_TO]
        targets = {r.target for r in rels if r.source == "rag"}
        assert "vector-search" in targets
        assert "llm" in targets


# ---------------------------------------------------------------------------
# Serialisation round-trip
# ---------------------------------------------------------------------------


class TestSerialisation:
    def test_save_and_load_round_trip(self, workspace):
        _write_knowledge(
            workspace, "vector-search",
            "# Vector Search\n\n#concept\n\n**is-a:** [[retrieval-method]]\n",
        )
        _write_knowledge(workspace, "retrieval-method", "# Retrieval Method\n\n#concept\n\n")
        original = build_graph(workspace)
        save_graph(original, workspace)

        loaded = load_graph(workspace)
        assert loaded is not None
        assert "vector-search" in loaded.entities
        assert loaded.entities["vector-search"].entity_type == EntityType.CONCEPT
        rels = [r for r in loaded.relationships if r.relation_type == RelationType.IS_A]
        assert any(r.source == "vector-search" and r.target == "retrieval-method" for r in rels)

    def test_load_returns_none_when_no_graph_built(self, workspace):
        result = load_graph(workspace)
        assert result is None

    def test_entities_file_written(self, workspace):
        _write_knowledge(workspace, "mcp", "# MCP\n\n#tool\n\n")
        graph = build_graph(workspace)
        save_graph(graph, workspace)
        assert (workspace.graph_dir / "entities.md").exists()

    def test_relations_file_written(self, workspace):
        _write_knowledge(
            workspace, "rag",
            "# RAG\n\n#concept\n\n**uses:** [[vector-search]]\n",
        )
        graph = build_graph(workspace)
        save_graph(graph, workspace)
        assert (workspace.graph_dir / "relations.md").exists()

    def test_index_file_written(self, workspace):
        _write_knowledge(workspace, "rag", "# RAG\n\n#concept\n\n")
        graph = build_graph(workspace)
        save_graph(graph, workspace)
        assert (workspace.graph_dir / "index.md").exists()

    def test_multiple_sources_preserved(self, workspace):
        _write_knowledge(workspace, "databricks", "# Databricks\n\n#tool\n\n")
        _write_project(workspace, "td-fraudai", "# TD FraudAI\n\n#databricks\n\n## Context\n\n")
        original = build_graph(workspace)
        save_graph(original, workspace)
        loaded = load_graph(workspace)
        assert loaded is not None
        # databricks should appear as entity
        assert "databricks" in loaded.entities


# ---------------------------------------------------------------------------
# Graph query
# ---------------------------------------------------------------------------


class TestGraphQuery:
    def test_get_context_for_known_entity(self, workspace):
        _write_knowledge(
            workspace, "vector-search",
            "# Vector Search\n\n#concept\n\n**is-a:** [[retrieval-method]]\n",
        )
        _write_knowledge(workspace, "retrieval-method", "# Retrieval Method\n\n#concept\n\n")
        graph = build_graph(workspace)
        ctx = get_context("vector-search", graph, depth=1)
        assert "vector-search" in ctx
        assert "concept" in ctx
        assert "retrieval-method" in ctx

    def test_get_context_for_unknown_entity(self, workspace):
        graph = build_graph(workspace)
        ctx = get_context("nonexistent-entity", graph, depth=1)
        assert "not found" in ctx.lower()

    def test_get_context_depth_zero_no_neighbors(self, workspace):
        _write_knowledge(
            workspace, "rag",
            "# RAG\n\n#concept\n\n**uses:** [[vector-search]]\n",
        )
        graph = build_graph(workspace)
        ctx = get_context("rag", graph, depth=0)
        assert "rag" in ctx
        # depth=0 means only the entity itself; neighbors from depth>0 hops not included
        assert "Connected:" not in ctx


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestGraphStats:
    def test_stats_counts_entities(self, workspace):
        _write_knowledge(workspace, "rag", "# RAG\n\n#concept\n\n")
        _write_knowledge(workspace, "databricks", "# Databricks\n\n#tool\n\n")
        _write_project(workspace, "my-project", "# My Project\n\n## Context\n\n")
        graph = build_graph(workspace)
        stats = graph_stats(graph)
        assert stats["concepts"] >= 1
        assert stats["tools"] >= 1
        assert stats["projects"] >= 1
        assert stats["total_entities"] >= 3

    def test_stats_counts_relationships(self, workspace):
        _write_knowledge(
            workspace, "rag",
            "# RAG\n\n#concept\n\n**uses:** [[vector-search]]\n",
        )
        graph = build_graph(workspace)
        stats = graph_stats(graph)
        assert stats["total_relationships"] >= 1

    def test_stats_zero_when_empty_shed(self, workspace):
        graph = build_graph(workspace)
        stats = graph_stats(graph)
        assert stats["total_entities"] == 0
        assert stats["total_relationships"] == 0


# ---------------------------------------------------------------------------
# Prose mention extraction (Slack ingestion)
# ---------------------------------------------------------------------------


class TestProseMentions:
    def test_prose_mention_creates_mentioned_in_edge(self, workspace):
        # The agent-bricks note is the source; the lakebase note is the target.
        # Plain prose mention of "Lakebase" should create a mentioned-in edge.
        _write_knowledge(workspace, "lakebase", "# Lakebase\n\n#lakebase\n")
        _write_knowledge(
            workspace, "agent-bricks",
            "# Agent Bricks\n\n#agent-bricks\n\n"
            "Customers building MAS apps want Lakebase Agent Memory in production.\n"
        )
        graph = build_graph(workspace)
        edges = [(r.source, r.target, r.relation_type)
                 for r in graph.relationships
                 if r.source == "agent-bricks" and r.target == "lakebase"]
        assert (("agent-bricks", "lakebase", RelationType.MENTIONED_IN)) in edges

    def test_prose_mention_handles_multi_word_slug(self, workspace):
        # "Knowledge Assistant" (with a space) should match the slug "knowledge-assistant".
        _write_knowledge(workspace, "knowledge-assistant", "# KA\n\n#concept\n")
        _write_knowledge(
            workspace, "agent-bricks",
            "# Agent Bricks\n\nProduct includes the Knowledge Assistant.\n"
        )
        graph = build_graph(workspace)
        targets = {r.target for r in graph.relationships if r.source == "agent-bricks"}
        assert "knowledge-assistant" in targets

    def test_prose_mention_skips_self(self, workspace):
        _write_knowledge(workspace, "lakebase", "# Lakebase\n\nLakebase is great.\n")
        graph = build_graph(workspace)
        edges = [(r.source, r.target) for r in graph.relationships
                 if r.source == "lakebase" and r.target == "lakebase"]
        assert edges == []

    def test_prose_mention_skipped_when_structured_edge_exists(self, workspace):
        # If a structured extractor (typed header / wikilink) already linked
        # source→target, prose extraction should NOT add a redundant edge.
        _write_knowledge(workspace, "lakebase", "# Lakebase\n")
        _write_knowledge(
            workspace, "ai-functions",
            "# AI Functions\n\n**uses:** [[lakebase]]\n\nWe rely on Lakebase here.\n"
        )
        graph = build_graph(workspace)
        types = sorted(r.relation_type.value for r in graph.relationships
                       if r.source == "ai-functions" and r.target == "lakebase")
        # Only the structured edges (uses + relates-to from the wikilink) —
        # no mentioned-in from prose.
        assert "mentioned-in" not in types
        assert "uses" in types

    def test_prose_mention_skips_short_slugs(self, workspace):
        # 3-char slug "rag" — should NOT be auto-extracted from prose ("rag")
        # because slugs <4 chars match too many false positives in real prose.
        _write_knowledge(workspace, "rag", "# RAG\n")
        _write_knowledge(workspace, "alpha", "# Alpha\n\nWe build a rag pipeline.\n")
        graph = build_graph(workspace)
        edges = [(r.source, r.target) for r in graph.relationships
                 if r.source == "alpha" and r.target == "rag"]
        assert edges == []

    def test_prose_mention_only_concept_project_tool_org(self, workspace):
        # Person entities should NOT be matched in prose — too noisy.
        _write_knowledge(workspace, "alice-chen", "# Alice\n\n#person\n")
        _write_knowledge(
            workspace, "alpha",
            "# Alpha\n\nThanks to Alice Chen for the help.\n"
        )
        graph = build_graph(workspace)
        # Even though "Alice Chen" appears in prose, no edge should be created
        # because alice-chen is type=person.
        edges = [(r.source, r.target) for r in graph.relationships
                 if r.source == "alpha" and r.target == "alice-chen"]
        assert edges == []
