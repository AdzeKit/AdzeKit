"""Tests for backbone MCP server tools."""

import json

from adzekit.mcp.backbone_server import backbone_get_week_notes


def test_backbone_get_week_notes_rejects_invalid_week_value():
    response = backbone_get_week_notes("2026-W99")
    data = json.loads(response)

    assert "error" in data
    assert "Invalid ISO week value" in data["error"]
