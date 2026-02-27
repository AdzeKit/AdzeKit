"""Tests for the agent tool registry."""

import json

from adzekit.agent.tools import ToolRegistry


def test_register_and_list():
    reg = ToolRegistry()

    @reg.register
    def greet(name: str) -> str:
        """Say hello."""
        return f"Hello, {name}"

    tools = reg.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "greet"
    assert tools[0].description == "Say hello."


def test_register_with_args():
    reg = ToolRegistry()

    @reg.register(name="my_tool", description="A custom tool.")
    def something(x: int, y: str = "default") -> str:
        return f"{x}-{y}"

    tool = reg.get("my_tool")
    assert tool is not None
    assert tool.description == "A custom tool."
    assert len(tool.parameters) == 2
    assert tool.parameters[0].name == "x"
    assert tool.parameters[0].required is True
    assert tool.parameters[1].name == "y"
    assert tool.parameters[1].required is False


def test_call_tool():
    reg = ToolRegistry()

    @reg.register
    def add(a: int, b: int) -> str:
        return str(a + b)

    result = reg.call("add", {"a": 3, "b": 4})
    assert result == "7"


def test_call_returns_dict_as_json():
    reg = ToolRegistry()

    @reg.register
    def info() -> dict:
        """Get info."""
        return {"status": "ok", "count": 42}

    result = reg.call("info", {})
    parsed = json.loads(result)
    assert parsed["status"] == "ok"
    assert parsed["count"] == 42


def test_call_unknown_tool():
    reg = ToolRegistry()
    result = reg.call("nonexistent", {})
    parsed = json.loads(result)
    assert "error" in parsed
    assert "Unknown tool" in parsed["error"]


def test_call_handles_exception():
    reg = ToolRegistry()

    @reg.register
    def fail() -> str:
        """Always fails."""
        raise ValueError("broken")

    result = reg.call("fail", {})
    parsed = json.loads(result)
    assert "error" in parsed
    assert "ValueError" in parsed["error"]


def test_to_anthropic_tools():
    reg = ToolRegistry()

    @reg.register(
        name="search",
        description="Search for things.",
        param_descriptions={"query": "The search query."},
    )
    def search(query: str, limit: int = 10) -> str:
        return query

    schemas = reg.to_anthropic_tools()
    assert len(schemas) == 1
    schema = schemas[0]
    assert schema["name"] == "search"
    assert schema["description"] == "Search for things."
    assert "query" in schema["input_schema"]["properties"]
    assert "limit" in schema["input_schema"]["properties"]
    assert "query" in schema["input_schema"]["required"]
    assert "limit" not in schema["input_schema"]["required"]


def test_to_anthropic_schema_types():
    reg = ToolRegistry()

    @reg.register
    def typed(name: str, count: int, ratio: float, flag: bool) -> str:
        """Test type mapping."""
        return "ok"

    schema = reg.to_anthropic_tools()[0]
    props = schema["input_schema"]["properties"]
    assert props["name"]["type"] == "string"
    assert props["count"]["type"] == "integer"
    assert props["ratio"]["type"] == "number"
    assert props["flag"]["type"] == "boolean"
