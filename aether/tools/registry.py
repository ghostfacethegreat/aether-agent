import json
from dataclasses import dataclass

from aether.errors import ToolError
from aether.utils import truncate


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: object
    risk: str = "low"
    parallel_safe: bool = False
    timeout: float | None = None

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self, max_result_chars=16000):
        self.tools: dict[str, Tool] = {}
        self.max_result_chars = int(max_result_chars)

    def register(self, tool: Tool) -> None:
        if tool.name in self.tools:
            raise ToolError(f"Tool '{tool.name}' is already registered")
        self.tools[tool.name] = tool

    def definitions(self, enabled=None) -> list[dict]:
        names = enabled if enabled is not None else list(self.tools)
        return [self.tools[name].schema() for name in names if name in self.tools]

    def get(self, name: str) -> Tool:
        tool = self.tools.get(name)
        if not tool:
            raise ToolError(f"Unknown tool '{name}'. Available tools: {', '.join(sorted(self.tools))}")
        return tool

    def execute(self, name: str, args: dict, context: dict) -> str:
        tool = self.get(name)
        if not isinstance(args, dict):
            raise ToolError(f"Arguments for '{name}' must be a JSON object")
        for required in tool.parameters.get("required", []):
            if required not in args:
                raise ToolError(f"Tool '{name}' requires argument '{required}'")
        try:
            result = tool.handler(args, context)
        except ToolError:
            raise
        except Exception as exc:
            raise ToolError(f"Tool '{name}' failed: {type(exc).__name__}: {exc}") from exc
        if isinstance(result, (dict, list)):
            result = json.dumps(result, ensure_ascii=False, indent=2)
        return truncate(str(result), self.max_result_chars)
