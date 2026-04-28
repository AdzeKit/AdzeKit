"""Tests for deterministic duplicate detection and merge."""

from __future__ import annotations

from fastapi.testclient import TestClient

from adzekit.modules.graph import build_graph, save_graph
from adzekit.modules.graph_dedup import apply_merges, find_duplicates
from adzekit.ui import app as ui_app


def _seed_graph(workspace, notes: dict[str, str]):
    for name, content in notes.items():
        (workspace.knowledge_dir / f"{name}.md").write_text(content)
    save_graph(build_graph(workspace), workspace)


class TestFindDuplicates:
    def test_typo_one_char_off(self, workspace):
        _seed_graph(workspace, {
            "alpha": "# alpha\n\n**uses:** [[adam-guary]]\n",
            "beta":  "# beta\n\n**uses:** [[adam-gurary]]\n",
        })
        from adzekit.modules.graph import load_graph
        groups = find_duplicates(load_graph(workspace))
        names = {tuple(sorted(m.name for m in g.members)) for g in groups}
        assert ("adam-guary", "adam-gurary") in names

    def test_substring_inclusion(self, workspace):
        _seed_graph(workspace, {
            "alpha": "# alpha\n\n**uses:** [[aer-compliance]]\n",
            "beta":  "# beta\n\n**uses:** [[aer-compliancemanagement]]\n",
        })
        from adzekit.modules.graph import load_graph
        groups = find_duplicates(load_graph(workspace))
        names = {tuple(sorted(m.name for m in g.members)) for g in groups}
        assert ("aer-compliance", "aer-compliancemanagement") in names

    def test_short_first_name_vs_full(self, workspace):
        _seed_graph(workspace, {
            "alpha": "# alpha\n\n**uses:** [[rob-signoretti]]\n",
            "beta":  "# beta\n\n**uses:** [[robert-signoretti]]\n",
        })
        from adzekit.modules.graph import load_graph
        groups = find_duplicates(load_graph(workspace))
        names = {tuple(sorted(m.name for m in g.members)) for g in groups}
        assert ("rob-signoretti", "robert-signoretti") in names

    def test_no_false_positive_on_shared_prefix(self, workspace):
        # 'mike-foo' and 'mike-bar' are clearly different people.
        _seed_graph(workspace, {
            "alpha": "# alpha\n\n**uses:** [[mike-foo]]\n",
            "beta":  "# beta\n\n**uses:** [[mike-bar]]\n",
        })
        from adzekit.modules.graph import load_graph
        groups = find_duplicates(load_graph(workspace))
        names = {tuple(sorted(m.name for m in g.members)) for g in groups}
        assert ("mike-bar", "mike-foo") not in names

    def test_canonical_is_most_connected(self, workspace):
        # 'adam-gurary' has a backlink; 'adam-guary' does not.
        _seed_graph(workspace, {
            "alpha": "# alpha\n\n**uses:** [[adam-gurary]]\n",
            "beta":  "# beta\n\n**uses:** [[adam-gurary]]\n",
            "gamma": "# gamma\n\n**uses:** [[adam-guary]]\n",
        })
        from adzekit.modules.graph import load_graph
        groups = find_duplicates(load_graph(workspace))
        target = next(g for g in groups
                      if {m.name for m in g.members} == {"adam-guary", "adam-gurary"})
        assert target.suggested_canonical == "adam-gurary"

    def test_groups_only_within_entity_type(self, workspace):
        # A 'foo-bar' concept and a 'foo-bar' tool name shouldn't merge,
        # but in this codebase entity_type comes from the registry, so we
        # just verify the dedup respects the type partition.
        from adzekit.models import KnowledgeGraph, Entity, EntityType
        from datetime import date
        graph = KnowledgeGraph(built_at=date.today())
        graph.entities["foo-bar"] = Entity(name="foo-bar", entity_type=EntityType.CONCEPT, sources=[])
        graph.entities["foo-baz"] = Entity(name="foo-baz", entity_type=EntityType.PROJECT, sources=[])
        groups = find_duplicates(graph)
        assert groups == []


class TestApplyMerges:
    def test_replaces_wikilinks_in_backbone(self, workspace):
        kfile = workspace.knowledge_dir / "alpha.md"
        kfile.write_text("# Alpha\n\nWe use [[adam-guary]]'s tool. Also [[adam-guary|Adam G]].\n")
        result = apply_merges([("adam-guary", "adam-gurary")], workspace)
        assert result["dry_run"] is False
        assert result["total_replacements"] == 2
        text = kfile.read_text()
        assert "[[adam-gurary]]" in text
        assert "[[adam-gurary|Adam G]]" in text
        assert "adam-guary" not in text

    def test_replaces_tags_with_word_boundaries(self, workspace):
        dfile = workspace.daily_dir / "2026-01-01.md"
        dfile.write_text("# day\n\nMet with #adam-guary. Note: #adam-guary-team should NOT change.\n")
        result = apply_merges([("adam-guary", "adam-gurary")], workspace)
        # Only the standalone #adam-guary should change; #adam-guary-team is a
        # different tag and must be preserved.
        text = dfile.read_text()
        assert "#adam-gurary." in text
        assert "#adam-guary-team" in text
        assert result["total_replacements"] == 1

    def test_dry_run_does_not_write(self, workspace):
        kfile = workspace.knowledge_dir / "alpha.md"
        original = "# Alpha\n\n[[adam-guary]]\n"
        kfile.write_text(original)
        result = apply_merges([("adam-guary", "adam-gurary")], workspace, dry_run=True)
        assert result["dry_run"] is True
        assert result["total_replacements"] == 1
        assert kfile.read_text() == original

    def test_does_not_touch_drafts_or_stock(self, workspace):
        # Manually drop a draft and a stock file with [[adam-guary]] —
        # they should be untouched.
        (workspace.drafts_dir).mkdir(parents=True, exist_ok=True)
        (workspace.stock_dir).mkdir(parents=True, exist_ok=True)
        d = workspace.drafts_dir / "x.md"
        s = workspace.stock_dir / "y.md"
        d.write_text("[[adam-guary]]")
        s.write_text("[[adam-guary]]")
        # Also a backbone file that SHOULD change
        k = workspace.knowledge_dir / "alpha.md"
        k.write_text("[[adam-guary]]")
        result = apply_merges([("adam-guary", "adam-gurary")], workspace)
        assert d.read_text() == "[[adam-guary]]"
        assert s.read_text() == "[[adam-guary]]"
        assert k.read_text() == "[[adam-gurary]]"
        # Only the backbone replacement counts.
        assert result["total_replacements"] == 1


class TestDedupAPI:
    def test_duplicates_endpoint_unbuilt(self, workspace, monkeypatch):
        monkeypatch.setattr("adzekit.ui.app._settings", lambda: workspace)
        client = TestClient(ui_app.app)
        r = client.get("/api/graph/duplicates")
        assert r.status_code == 200
        assert r.json() == {"built": False, "groups": []}

    def test_duplicates_returns_groups(self, workspace, monkeypatch):
        _seed_graph(workspace, {
            "alpha": "# alpha\n\n**uses:** [[adam-guary]]\n",
            "beta":  "# beta\n\n**uses:** [[adam-gurary]]\n",
        })
        monkeypatch.setattr("adzekit.ui.app._settings", lambda: workspace)
        client = TestClient(ui_app.app)
        r = client.get("/api/graph/duplicates")
        assert r.status_code == 200
        body = r.json()
        assert body["built"] is True
        groups = body["groups"]
        assert any(
            {m["name"] for m in g["members"]} == {"adam-guary", "adam-gurary"}
            for g in groups
        )

    def test_merge_endpoint_dry_run(self, workspace, monkeypatch):
        kfile = workspace.knowledge_dir / "alpha.md"
        kfile.write_text("[[adam-guary]] and [[adam-guary]]\n")
        monkeypatch.setattr("adzekit.ui.app._settings", lambda: workspace)
        client = TestClient(ui_app.app)
        r = client.post("/api/graph/duplicates/merge", json={
            "merges": [{"from": "adam-guary", "to": "adam-gurary"}],
            "dry_run": True,
        })
        assert r.status_code == 200
        body = r.json()
        assert body["dry_run"] is True
        assert body["total_replacements"] == 2
        # File was not written.
        assert "[[adam-guary]]" in kfile.read_text()

    def test_merge_endpoint_applies(self, workspace, monkeypatch):
        kfile = workspace.knowledge_dir / "alpha.md"
        kfile.write_text("[[adam-guary]]\n")
        monkeypatch.setattr("adzekit.ui.app._settings", lambda: workspace)
        client = TestClient(ui_app.app)
        r = client.post("/api/graph/duplicates/merge", json={
            "merges": [{"from": "adam-guary", "to": "adam-gurary"}],
            "dry_run": False,
        })
        assert r.status_code == 200
        body = r.json()
        assert body["dry_run"] is False
        assert "[[adam-gurary]]" in kfile.read_text()
        assert "[[adam-guary]]" not in kfile.read_text()

    def test_merge_endpoint_rejects_empty(self, workspace, monkeypatch):
        monkeypatch.setattr("adzekit.ui.app._settings", lambda: workspace)
        client = TestClient(ui_app.app)
        r = client.post("/api/graph/duplicates/merge", json={"merges": []})
        assert r.status_code == 400
