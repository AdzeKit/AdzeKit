"""Tests for the AdzeKit web UI API endpoints.

Uses the FastAPI test client with a real temp shed.
"""

import pytest


@pytest.fixture
def client(workspace, monkeypatch):
    """FastAPI test client backed by a temporary shed."""
    monkeypatch.setenv("ADZEKIT_SHED", str(workspace.shed))

    from fastapi.testclient import TestClient

    from adzekit.ui.app import app

    return TestClient(app)


def test_index_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "ADZEKIT" in response.text


def test_agent_page(client):
    response = client.get("/agent")
    assert response.status_code == 200
    assert "agent" in response.text.lower()


def test_api_status(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "open_loops" in data
    assert "active_projects" in data


def test_api_loops(client):
    response = client.get("/api/loops")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_api_projects(client):
    response = client.get("/api/projects")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_api_today(client):
    response = client.get("/api/today")
    assert response.status_code == 200
    data = response.json()
    assert "exists" in data


def test_api_bench(client):
    response = client.get("/api/bench")
    assert response.status_code == 200
    data = response.json()
    assert "content" in data


def test_api_agent_chat_no_message(client):
    response = client.post("/api/agent/chat", json={})
    assert response.status_code == 400


def test_resolve_file_rejects_prefix_escape(workspace):
    from fastapi import HTTPException

    from adzekit.ui.app import _resolve_file

    (workspace.shed / "projects-copy").mkdir(exist_ok=True)
    with pytest.raises(HTTPException) as exc:
        _resolve_file("projects", "../projects-copy/secret.md", workspace)

    assert exc.value.status_code == 403
