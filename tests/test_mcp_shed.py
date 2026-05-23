"""Tests for the Shed MCP server.

Tests call the pure tool functions directly — no MCP transport spin-up.
The MCP server is a thin wrapper around these functions, so this catches
the business-logic bugs that matter without depending on the MCP SDK.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from adzekit.mcp.shed import (
    _dispatch,
    tool_get_knowledge,
    tool_get_loops,
    tool_get_projects,
    tool_get_today,
    tool_list_inbox,
    tool_propose_draft,
    tool_show_draft,
)


# --- shed_get_loops --------------------------------------------------------


def test_get_loops_empty(workspace):
    result = json.loads(tool_get_loops(workspace))
    assert result == []


def test_get_loops_returns_entries(workspace):
    workspace.loops_active.write_text(
        "# Active Loops\n\n"
        "- [ ] (S) [2026-05-22] Send POC summary (2026-05-25)\n"
        "- [ ] (M) [2026-05-20] Review architecture doc\n",
        encoding="utf-8",
    )
    result = json.loads(tool_get_loops(workspace))
    assert len(result) == 2
    titles = {loop["title"] for loop in result}
    assert "Send POC summary" in titles


# --- shed_get_today --------------------------------------------------------


def test_get_today_missing_returns_hint(workspace):
    result = tool_get_today(workspace)
    assert "No daily note" in result
    assert "/daily-start" in result


def test_get_today_returns_note_content(workspace):
    from datetime import date
    today = date.today().isoformat()
    note = workspace.daily_dir / f"{today}.md"
    note.write_text(f"# {today}\n\n## Intention\n- [ ] thing\n", encoding="utf-8")
    result = tool_get_today(workspace)
    assert "## Intention" in result
    assert "- [ ] thing" in result


# --- shed_get_projects -----------------------------------------------------


def test_get_projects_unknown_state_returns_error(workspace):
    result = json.loads(tool_get_projects(state="garbage", settings=workspace))
    assert "error" in result


def test_get_projects_active(workspace):
    (workspace.active_dir / "demo.md").write_text(
        "# Demo Project\n\n## Context\n## Log\n", encoding="utf-8",
    )
    result = json.loads(tool_get_projects(state="active", settings=workspace))
    assert len(result) == 1
    assert result[0]["slug"] == "demo"


# --- shed_get_knowledge ----------------------------------------------------


def test_get_knowledge_missing(workspace):
    result = tool_get_knowledge("nope", settings=workspace)
    assert result == "No knowledge note: nope"


def test_get_knowledge_returns_body(workspace):
    (workspace.knowledge_dir / "vector-search.md").write_text(
        "# Vector Search\n\nA retrieval method.\n", encoding="utf-8",
    )
    result = tool_get_knowledge("vector-search", settings=workspace)
    assert "Vector Search" in result
    assert "retrieval method" in result


# --- shed_list_inbox -------------------------------------------------------


def test_list_inbox_empty(workspace):
    result = json.loads(tool_list_inbox(workspace))
    assert result == []


def test_list_inbox_after_writes(workspace):
    from adzekit.preprocessor import write_draft_with_frontmatter
    write_draft_with_frontmatter("alpha", body="x", settings=workspace, summary="one")
    write_draft_with_frontmatter("beta", body="y", settings=workspace, summary="two")
    result = json.loads(tool_list_inbox(workspace))
    assert len(result) == 2
    skills = {e["skill"] for e in result}
    assert skills == {"alpha", "beta"}


# --- shed_show_draft -------------------------------------------------------


def test_show_draft_missing_index_returns_error(workspace):
    result = json.loads(tool_show_draft(99, settings=workspace))
    assert "error" in result


def test_show_draft_returns_body_and_provenance(workspace):
    from adzekit.preprocessor import write_draft_with_frontmatter
    write_draft_with_frontmatter(
        "daily-start", body="# Day\nstuff\n", settings=workspace, summary="3 carried",
    )
    result = json.loads(tool_show_draft(1, settings=workspace))
    assert result["skill"] == "daily-start"
    assert result["summary"] == "3 carried"
    assert "# Day" in result["body"]
    # Frontmatter is stripped from the shown body.
    assert "<!--" not in result["body"]


# --- shed_propose_draft ----------------------------------------------------


def test_propose_draft_writes_to_drafts(workspace):
    result = json.loads(tool_propose_draft(
        skill="mcp-test",
        body="# Proposed\nbody text\n",
        summary="from mcp",
        settings=workspace,
    ))
    assert "path" in result
    rel = result["path"]
    # CRITICAL invariant: the path is inside drafts/, NEVER backbone.
    assert rel.startswith("drafts/")
    # The draft file exists.
    target = workspace.shed / rel
    assert target.exists()
    body = target.read_text(encoding="utf-8")
    assert body.startswith("<!-- adzekit-draft")
    assert "trigger: mcp" in body
    assert "summary: from mcp" in body
    assert "# Proposed" in body


def test_propose_draft_never_writes_backbone(workspace):
    """The propose tool MUST NOT write to loops/, projects/, knowledge/,
    daily/, or reviews/, even when the caller tries to inject a tricky skill name."""
    # Try a skill name that might be parsed weirdly.
    result = json.loads(tool_propose_draft(
        skill="../knowledge/sneaky",
        body="malicious",
        settings=workspace,
    ))
    # Either errors out or writes inside drafts; never outside.
    if "error" not in result:
        rel = result["path"]
        assert rel.startswith("drafts/")
        assert "../" not in rel
    # Verify the backbone dirs are untouched.
    assert not any(workspace.knowledge_dir.glob("*sneaky*"))
    assert not any(workspace.loops_dir.glob("*sneaky*"))


# --- _dispatch (the async router) ------------------------------------------


def test_dispatch_unknown_tool_returns_error():
    result = asyncio.run(_dispatch("unknown_tool", {}))
    assert "unknown tool" in result


def test_dispatch_propose_missing_required_arg():
    result = asyncio.run(_dispatch("shed_propose_draft", {"skill": "x"}))
    payload = json.loads(result)
    assert "error" in payload


def test_dispatch_get_loops(workspace, monkeypatch):
    # The pure functions read from get_settings(); the test fixture
    # workspace IS a Settings object. Patch get_settings to point at it.
    monkeypatch.setattr(
        "adzekit.config.get_settings", lambda *a, **k: workspace,
    )
    workspace.loops_active.write_text(
        "# Active Loops\n\n- [ ] (S) [2026-05-22] X (2026-05-25)\n", encoding="utf-8",
    )
    result = asyncio.run(_dispatch("shed_get_loops", {}))
    assert "X" in result
