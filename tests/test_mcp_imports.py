"""Smoke tests for MCP server entrypoint imports."""


def test_backbone_mcp_module_imports():
    import adzekit.mcp.backbone_server  # noqa: F401


def test_gmail_mcp_module_imports():
    import adzekit.mcp.gmail_server  # noqa: F401
