"""Tool registry for the AdzeKit agent.

Tools are plain functions decorated with @tool. The decorator captures the
function's name, docstring, and type-annotated parameters, then registers
them so the orchestrator can expose them to the LLM as callable tools.
"""

import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Callable, get_type_hints


@dataclass
class ToolParam:
    """A single parameter for a tool."""

    name: str
    type: str
    description: str
    required: bool = True
    enum: list[str] | None = None


@dataclass
class ToolDef:
    """A registered tool with its callable and schema."""

    name: str
    description: str
    parameters: list[ToolParam]
    fn: Callable[..., Any]

    def to_anthropic_schema(self) -> dict:
        """Convert to Anthropic tool-use schema."""
        properties = {}
        required = []
        for p in self.parameters:
            prop: dict[str, Any] = {"type": p.type, "description": p.description}
            if p.enum:
                prop["enum"] = p.enum
            properties[p.name] = prop
            if p.required:
                required.append(p.name)
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }


class ToolRegistry:
    """Collects tool definitions and dispatches calls."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDef] = {}

    def register(
        self,
        fn: Callable[..., Any] | None = None,
        *,
        name: str = "",
        description: str = "",
        param_descriptions: dict[str, str] | None = None,
    ) -> Callable:
        """Register a function as an agent tool.

        Can be used as a decorator:
            @registry.register
            def my_tool(query: str) -> str: ...

        Or with arguments:
            @registry.register(name="search", description="Search emails")
            def search_emails(query: str) -> str: ...
        """
        def decorator(func: Callable) -> Callable:
            tool_name = name or func.__name__
            tool_desc = description or (func.__doc__ or "").strip().split("\n")[0]
            hints = get_type_hints(func)
            sig = inspect.signature(func)
            params = []
            descs = param_descriptions or {}

            for pname, param in sig.parameters.items():
                if pname in ("self", "cls"):
                    continue
                ptype = _python_type_to_json(hints.get(pname, str))
                pdesc = descs.get(pname, pname)
                required = param.default is inspect.Parameter.empty
                params.append(ToolParam(
                    name=pname,
                    type=ptype,
                    description=pdesc,
                    required=required,
                ))

            self._tools[tool_name] = ToolDef(
                name=tool_name,
                description=tool_desc,
                parameters=params,
                fn=func,
            )
            return func

        if fn is not None:
            return decorator(fn)
        return decorator

    def get(self, name: str) -> ToolDef | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDef]:
        return list(self._tools.values())

    def to_anthropic_tools(self) -> list[dict]:
        return [t.to_anthropic_schema() for t in self._tools.values()]

    def call(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool by name with the given arguments. Returns a string result."""
        tool = self._tools.get(name)
        if tool is None:
            return json.dumps({"error": f"Unknown tool: {name}"})
        try:
            result = tool.fn(**arguments)
            if isinstance(result, str):
                return result
            return json.dumps(result, default=str)
        except Exception as exc:
            return json.dumps({"error": f"{type(exc).__name__}: {exc}"})


def _python_type_to_json(t: type) -> str:
    """Map Python types to JSON Schema types."""
    mapping = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }
    origin = getattr(t, "__origin__", None)
    if origin is not None:
        t = origin
    return mapping.get(t, "string")


# Global registry -- tools register themselves on import
registry = ToolRegistry()
