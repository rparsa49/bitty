from __future__ import annotations

import inspect
import typing
from dataclasses import dataclass
from typing import Any, Callable

_JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean"}


@dataclass
class Tool:
    name: str
    description: str
    fn: Callable[..., Any]
    schema: dict
    tier: str = "safe"
    state: str = "working"


def _schema(fn: Callable) -> dict:
    hints = typing.get_type_hints(fn)
    props, required = {}, []
    for name, param in inspect.signature(fn).parameters.items():
        props[name] = {"type": _JSON_TYPES.get(hints.get(name, str), "string")}
        if param.default is inspect.Parameter.empty:
            required.append(name)
    return {"type": "object", "properties": props, "required": required}


def tool(fn: Callable | None = None, *, tier: str = "safe", state: str = "working"):
    def wrap(f: Callable) -> Callable:
        doc = (inspect.getdoc(f) or "").split("\n\n")[0].replace("\n", " ")
        f.tool = Tool(f.__name__, doc, f, _schema(f), tier, state)
        return f

    return wrap(fn) if fn else wrap


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, fn: Callable) -> None:
        t: Tool = fn.tool
        self._tools[t.name] = t

    def discover(self, module) -> "ToolRegistry":
        for obj in vars(module).values():
            if callable(obj) and hasattr(obj, "tool"):
                self.register(obj)
        return self

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def schemas(self) -> list[dict]:
        """Anthropic tool-definition format."""
        return [
            {"name": t.name, "description": t.description, "input_schema": t.schema}
            for t in self._tools.values()
        ]
