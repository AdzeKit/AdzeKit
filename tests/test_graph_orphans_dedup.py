"""Direct module tests for graph orphans + dedup behavior.

Replaces coverage lost when tests/test_graph_activation.py and
tests/test_graph_dedup.py were deleted in Phase 0 alongside the FastAPI UI
those tests exercised. These tests hit the underlying module API directly.
"""

from __future__ import annotations

from adzekit.models import Entity, EntityType, KnowledgeGraph, Relationship, RelationType
from adzekit.modules.graph import (
    build_graph,
    degree_centrality,
    find_orphans,
    graph_stats,
    load_graph,
    save_graph,
)
from adzekit.modules.graph_dedup import (
    DuplicateGroup,
    apply_merges,
    find_duplicates,
)


def _write_knowledge(settings, slug: str, content: str) -> None:
    (settings.knowledge_dir / f"{slug}.md").write_text(content, encoding="utf-8")


def _write_project(settings, slug: str, content: str) -> None:
    (settings.active_dir / f"{slug}.md").write_text(content, encoding="utf-8")


# --- find_orphans -----------------------------------------------------------


def test_find_orphans_empty_graph():
    assert find_orphans(KnowledgeGraph()) == []


def test_find_orphans_returns_zero_degree_entities():
    g = KnowledgeGraph()
    g.entities["alone"] = Entity(name="alone", entity_type=EntityType.CONCEPT)
    g.entities["a"] = Entity(name="a", entity_type=EntityType.CONCEPT)
    g.entities["b"] = Entity(name="b", entity_type=EntityType.CONCEPT)
    g.relationships.append(
        Relationship(source="a", target="b", relation_type=RelationType.RELATES_TO)
    )
    orphans = find_orphans(g)
    assert orphans == ["alone"]


def test_find_orphans_excludes_endpoints():
    g = KnowledgeGraph()
    for n in ("source-only", "target-only"):
        g.entities[n] = Entity(name=n, entity_type=EntityType.CONCEPT)
    g.relationships.append(
        Relationship(
            source="source-only",
            target="target-only",
            relation_type=RelationType.RELATES_TO,
        )
    )
    assert find_orphans(g) == []


def test_find_orphans_after_build(workspace):
    _write_knowledge(
        workspace,
        "orphan-concept",
        "# Orphan Concept\n\n#orphan-concept #concept\n\nNo links anywhere.\n",
    )
    _write_knowledge(
        workspace,
        "connected-a",
        "# Connected A\n\n#connected-a #concept\n\n**relates-to:** [[connected-b]]\n",
    )
    _write_knowledge(
        workspace,
        "connected-b",
        "# Connected B\n\n#connected-b #concept\n",
    )
    graph = build_graph(workspace)
    orphans = find_orphans(graph)
    assert "orphan-concept" in orphans
    assert "connected-a" not in orphans
    assert "connected-b" not in orphans


# --- degree_centrality + graph_stats ---------------------------------------


def test_degree_centrality_counts_both_directions():
    g = KnowledgeGraph()
    for n in ("a", "b", "c"):
        g.entities[n] = Entity(name=n, entity_type=EntityType.CONCEPT)
    g.relationships.append(
        Relationship(source="a", target="b", relation_type=RelationType.RELATES_TO)
    )
    g.relationships.append(
        Relationship(source="a", target="c", relation_type=RelationType.USES)
    )
    deg = degree_centrality(g)
    assert deg["a"] == 2
    assert deg["b"] == 1
    assert deg["c"] == 1


def test_graph_stats_after_build_with_mixed_types(workspace):
    _write_knowledge(
        workspace,
        "vector-search",
        "# Vector Search\n\n#vector-search #tool\n\n**developed-by:** [[pinecone]]\n",
    )
    _write_knowledge(
        workspace,
        "pinecone",
        "# Pinecone\n\n#pinecone #organization\n",
    )
    _write_knowledge(
        workspace,
        "rag",
        "# RAG\n\n#rag #concept\n\n**uses:** [[vector-search]]\n",
    )
    _write_project(workspace, "demo-proj", "# Demo\n\n## Context\n## Log\n")
    graph = build_graph(workspace)
    stats = graph_stats(graph)
    assert stats["tools"] >= 1
    assert stats["concepts"] >= 1
    assert stats["projects"] >= 1
    assert stats["total_entities"] >= 4
    assert stats["total_relationships"] >= 2


# --- save/load round-trip ---------------------------------------------------


def test_save_load_preserves_entities_and_relations(workspace):
    _write_knowledge(
        workspace,
        "ml-platform",
        "# ML Platform\n\n#ml-platform #tool\n\n**part-of:** [[data-platform]]\n",
    )
    _write_knowledge(
        workspace,
        "data-platform",
        "# Data Platform\n\n#data-platform #tool\n",
    )
    g1 = build_graph(workspace)
    save_graph(g1, workspace)
    g2 = load_graph(workspace)
    assert g2 is not None
    assert set(g2.entities) >= {"ml-platform", "data-platform"}
    # The part-of relationship should survive the round-trip.
    rel_pairs = {(r.source, r.target, r.relation_type) for r in g2.relationships}
    assert any(
        src == "ml-platform" and tgt == "data-platform"
        for src, tgt, _ in rel_pairs
    )


def test_load_returns_none_when_graph_unbuilt(workspace):
    assert load_graph(workspace) is None


# --- find_duplicates --------------------------------------------------------


def _add(g: KnowledgeGraph, name: str, etype: EntityType = EntityType.PERSON) -> None:
    g.entities[name] = Entity(name=name, entity_type=etype)


def test_dedup_catches_single_char_typo():
    g = KnowledgeGraph()
    _add(g, "adam-guary")
    _add(g, "adam-gurary")
    groups = find_duplicates(g)
    assert len(groups) == 1
    names = sorted(m.name for m in groups[0].members)
    assert names == ["adam-guary", "adam-gurary"]


def test_dedup_catches_short_vs_full_first_name():
    g = KnowledgeGraph()
    _add(g, "rob-signoretti")
    _add(g, "robert-signoretti")
    groups = find_duplicates(g)
    assert len(groups) == 1
    assert {m.name for m in groups[0].members} == {
        "rob-signoretti",
        "robert-signoretti",
    }


def test_dedup_catches_stem_vs_longer_suffix():
    g = KnowledgeGraph()
    _add(g, "aer-compliance", EntityType.PROJECT)
    _add(g, "aer-compliancemanagement", EntityType.PROJECT)
    groups = find_duplicates(g)
    assert len(groups) == 1
    assert {m.name for m in groups[0].members} == {
        "aer-compliance",
        "aer-compliancemanagement",
    }


def test_dedup_does_not_cross_entity_types():
    g = KnowledgeGraph()
    _add(g, "alpha", EntityType.PERSON)
    _add(g, "alpha-prime", EntityType.CONCEPT)
    # Even with similar names, different types must not cluster together.
    groups = find_duplicates(g)
    assert all(len(grp.members) <= 1 or len({m.entity_type for m in grp.members}) == 1
               for grp in groups)


def test_dedup_does_not_cluster_distinct_short_names():
    """The short-name guard rejects 'mike-foo' ↔ 'mike-bar'."""
    g = KnowledgeGraph()
    _add(g, "mike-foo")
    _add(g, "mike-bar")
    groups = find_duplicates(g)
    # With the strict short-name threshold, these should not cluster.
    long_clusters = [g for g in groups if len(g.members) > 1]
    assert long_clusters == []


def test_dedup_returns_typed_groups():
    g = KnowledgeGraph()
    _add(g, "alex-smith")
    _add(g, "alexander-smith")
    groups = find_duplicates(g)
    assert all(isinstance(grp, DuplicateGroup) for grp in groups)
    if groups:
        grp = groups[0]
        assert grp.entity_type == "person"
        assert grp.suggested_canonical in {m.name for m in grp.members}


# --- apply_merges -----------------------------------------------------------


def test_apply_merges_rewrites_wikilinks(workspace):
    _write_knowledge(
        workspace,
        "note-1",
        "# Note 1\n\nSee [[adam-guary]] for context.\n",
    )
    _write_knowledge(
        workspace,
        "note-2",
        "# Note 2\n\n**relates-to:** [[adam-guary]]\n",
    )
    result = apply_merges([("adam-guary", "adam-gurary")], workspace)
    assert result["total_replacements"] == 2
    assert (workspace.knowledge_dir / "note-1.md").read_text().count(
        "[[adam-gurary]]"
    ) == 1
    assert (workspace.knowledge_dir / "note-2.md").read_text().count(
        "[[adam-gurary]]"
    ) == 1


def test_apply_merges_dry_run_does_not_write(workspace):
    _write_knowledge(
        workspace,
        "note",
        "# Note\n\n[[adam-guary]]\n",
    )
    result = apply_merges(
        [("adam-guary", "adam-gurary")],
        workspace,
        dry_run=True,
    )
    assert result["dry_run"] is True
    assert result["total_replacements"] == 1
    # File still references the original.
    assert "[[adam-guary]]" in (workspace.knowledge_dir / "note.md").read_text()


def test_apply_merges_preserves_wikilink_alias(workspace):
    _write_knowledge(
        workspace,
        "note",
        "# Note\n\n[[adam-guary|Adam]]\n",
    )
    apply_merges([("adam-guary", "adam-gurary")], workspace)
    text = (workspace.knowledge_dir / "note.md").read_text()
    assert "[[adam-gurary|Adam]]" in text


def test_apply_merges_rewrites_tags(workspace):
    _write_knowledge(
        workspace,
        "note",
        "# Note\n\n#adam-guary is here. Also #adam-guary again.\n",
    )
    result = apply_merges([("adam-guary", "adam-gurary")], workspace)
    assert result["total_replacements"] == 2
    text = (workspace.knowledge_dir / "note.md").read_text()
    assert text.count("#adam-gurary") == 2
    assert "#adam-guary " not in text


def test_apply_merges_does_not_touch_drafts_or_graph(workspace):
    """Scope must exclude drafts/, stock/, graph/."""
    _write_knowledge(workspace, "good", "# Good\n\n[[adam-guary]]\n")
    workspace.drafts_dir.mkdir(parents=True, exist_ok=True)
    workspace.graph_dir.mkdir(parents=True, exist_ok=True)
    draft = workspace.drafts_dir / "patch.md"
    draft.write_text("# Draft\n\n[[adam-guary]] reference\n", encoding="utf-8")
    g_file = workspace.graph_dir / "entities.md"
    g_file.write_text("[[adam-guary]] in graph index\n", encoding="utf-8")

    apply_merges([("adam-guary", "adam-gurary")], workspace)
    assert "[[adam-guary]]" in draft.read_text()
    assert "[[adam-guary]]" in g_file.read_text()
    # backbone got rewritten
    assert "[[adam-gurary]]" in (workspace.knowledge_dir / "good.md").read_text()


def test_apply_merges_skips_partial_tag_matches(workspace):
    """`#adam-guary` must NOT match `#adam-guarytwo`."""
    _write_knowledge(
        workspace,
        "note",
        "# Note\n\n#adam-guary here. #adam-guarytwo should be safe.\n",
    )
    apply_merges([("adam-guary", "adam-gurary")], workspace)
    text = (workspace.knowledge_dir / "note.md").read_text()
    assert "#adam-gurary " in text or "#adam-gurary\n" in text or "#adam-gurary." in text
    assert "#adam-guarytwo" in text  # untouched


def test_apply_merges_with_empty_or_noop_merges(workspace):
    """Empty input, no-op pairs, and identity pairs should be handled cleanly."""
    _write_knowledge(workspace, "note", "# Note\n\n[[real]]\n")
    result = apply_merges([], workspace)
    assert result["total_replacements"] == 0
    result = apply_merges([("real", "real")], workspace)  # identity
    assert result["total_replacements"] == 0
    result = apply_merges([("", "x")], workspace)  # empty source
    assert result["total_replacements"] == 0
