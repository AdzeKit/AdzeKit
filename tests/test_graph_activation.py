"""Tests for graph activation surfaces: API endpoints, daily ritual integration."""

from __future__ import annotations

from fastapi.testclient import TestClient

from adzekit.modules.graph import build_graph, save_graph
from adzekit.ui import app as ui_app


def _client_with_settings(settings):
    """Override get_settings so the FastAPI app uses the test shed."""
    from adzekit.config import get_settings as _real
    ui_app.app.dependency_overrides = {}
    # The app uses adzekit.config.get_settings via _settings(); monkeypatch by
    # reassigning the cached function output.
    import adzekit.config as cfg
    cfg.get_settings.cache_clear() if hasattr(cfg.get_settings, "cache_clear") else None
    cfg._settings_override = settings  # not really used; rely on env

    return TestClient(ui_app.app)


class TestGraphAPI:
    def test_stats_unbuilt(self, workspace, monkeypatch):
        monkeypatch.setattr("adzekit.ui.app._settings", lambda: workspace)
        client = TestClient(ui_app.app)
        r = client.get("/api/graph/stats")
        assert r.status_code == 200
        assert r.json() == {"built": False}

    def test_build_then_stats(self, workspace, monkeypatch):
        monkeypatch.setattr("adzekit.ui.app._settings", lambda: workspace)
        # Seed a knowledge note with a wikilink so the graph isn't empty.
        (workspace.knowledge_dir / "alpha.md").write_text(
            "# Alpha\n\n**uses:** [[beta]]\n"
        )
        client = TestClient(ui_app.app)
        r = client.post("/api/graph/build")
        assert r.status_code == 200
        stats = r.json()["stats"]
        assert stats["total_entities"] >= 2
        assert stats["total_relationships"] >= 1

        r2 = client.get("/api/graph/stats")
        body = r2.json()
        assert body["built"] is True
        assert "alpha" in body["entities_by_type"].get("concept", []) \
            or any(e["name"] == "alpha" for v in body["entities_by_type"].values() for e in v)

    def test_entities_endpoint(self, workspace, monkeypatch):
        monkeypatch.setattr("adzekit.ui.app._settings", lambda: workspace)
        (workspace.knowledge_dir / "gamma.md").write_text("# Gamma\n\n**is-a:** [[delta]]\n")
        save_graph(build_graph(workspace), workspace)
        client = TestClient(ui_app.app)
        r = client.get("/api/graph/entities")
        assert r.status_code == 200
        names = r.json()
        assert "gamma" in names
        assert "delta" in names

    def test_entity_context_404_when_unbuilt(self, workspace, monkeypatch):
        monkeypatch.setattr("adzekit.ui.app._settings", lambda: workspace)
        client = TestClient(ui_app.app)
        r = client.get("/api/graph/entity/anything")
        assert r.status_code == 404

    def test_network_unbuilt_returns_empty(self, workspace, monkeypatch):
        monkeypatch.setattr("adzekit.ui.app._settings", lambda: workspace)
        client = TestClient(ui_app.app)
        r = client.get("/api/graph/network")
        assert r.status_code == 200
        body = r.json()
        assert body == {"built": False, "nodes": [], "edges": []}

    def test_network_returns_cytoscape_shape(self, workspace, monkeypatch):
        # Seed two knowledge notes that link to each other.
        (workspace.knowledge_dir / "alpha.md").write_text(
            "# Alpha\n\n**uses:** [[beta]]\n"
        )
        (workspace.knowledge_dir / "beta.md").write_text(
            "# Beta\n\n**relates-to:** [[gamma]]\n"
        )
        save_graph(build_graph(workspace), workspace)

        monkeypatch.setattr("adzekit.ui.app._settings", lambda: workspace)
        client = TestClient(ui_app.app)
        r = client.get("/api/graph/network")
        assert r.status_code == 200
        body = r.json()
        assert body["built"] is True
        ids = {n["data"]["id"] for n in body["nodes"]}
        assert {"alpha", "beta", "gamma"} <= ids

        for n in body["nodes"]:
            d = n["data"]
            assert "entity_type" in d
            assert "degree" in d
            assert isinstance(d["degree"], int)

        for e in body["edges"]:
            d = e["data"]
            assert "source" in d and "target" in d and "relation" in d
            # Self-loops should be filtered.
            assert d["source"] != d["target"]


class TestWIPBlockOnCreate:
    def test_create_active_blocked_at_cap(self, workspace, monkeypatch):
        from adzekit.workspace import create_project
        for i in range(workspace.max_active_projects):
            create_project(f"existing-{i}", title=f"Existing {i}",
                           backlog=False, settings=workspace)

        monkeypatch.setattr("adzekit.ui.app._settings", lambda: workspace)
        client = TestClient(ui_app.app)
        r = client.post("/api/files/projects/create",
                        json={"slug": "newone", "state": "active"})
        assert r.status_code == 409
        assert "WIP limit" in r.json()["detail"]

    def test_create_backlog_unaffected_by_cap(self, workspace, monkeypatch):
        from adzekit.workspace import create_project
        for i in range(workspace.max_active_projects):
            create_project(f"e-{i}", title=f"E {i}", backlog=False, settings=workspace)

        monkeypatch.setattr("adzekit.ui.app._settings", lambda: workspace)
        client = TestClient(ui_app.app)
        r = client.post("/api/files/projects/create",
                        json={"slug": "later", "state": "backlog"})
        assert r.status_code == 200


class TestDemoteAPI:
    def test_demote_endpoint(self, workspace, monkeypatch):
        from adzekit.workspace import create_project
        create_project("toDemote", title="To Demote", backlog=False, settings=workspace)

        monkeypatch.setattr("adzekit.ui.app._settings", lambda: workspace)
        client = TestClient(ui_app.app)
        r = client.post("/api/files/projects/toDemote/demote")
        assert r.status_code == 200
        assert (workspace.backlog_dir / "toDemote.md").exists()
        assert not (workspace.active_dir / "toDemote.md").exists()
