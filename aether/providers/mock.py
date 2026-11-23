from aether.errors import ProviderError
from aether.utils import make_id

from .base import BaseProvider, ModelResponse, ToolCall


class MockProvider(BaseProvider):
    name = "mock"
    label = "Aether Mock"
    kind = "local"
    cost = "Free. In-process test provider."
    limits = "No external limits."
    default_model = "mock-standard"

    def __init__(self, config, model=None, spec=None, script=None, fail_times=0):
        super().__init__(config, model, spec)
        if self.spec:
            self.name = self.spec.name
            self.label = self.spec.label
            self.kind = self.spec.kind
            self.cost = self.spec.cost
            self.limits = self.spec.limits
        self.script = list(script or [])
        self.fail_times = int(fail_times)
        self.calls = 0

    def _next_scripted(self):
        if not self.script:
            return None
        item = self.script.pop(0)
        if isinstance(item, str):
            return {"content": item}
        if isinstance(item, ModelResponse):
            return {
                "content": item.content,
                "tool_calls": [
                    {"name": call.name, "arguments": call.arguments, "id": call.id} for call in item.tool_calls
                ],
            }
        return item

    def chat(self, messages, tools=None, stream=False, on_delta=None, options=None):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise ProviderError("Mock transient failure", provider=self.name, retryable=True)
        scripted = self._next_scripted() or {}
        if scripted.get("error"):
            raise ProviderError(str(scripted["error"]), provider=self.name, retryable=bool(scripted.get("retryable")))
        last_user = ""
        for message in reversed(messages or []):
            if message.get("role") == "user":
                last_user = str(message.get("content") or "")
                break
        content = str(scripted.get("content") or "")
        if not content:
            if "tool" in last_user.lower() and tools:
                content = "I'll inspect the current directory with a tool."
            else:
                content = (
                    "Aether mock provider is active. No network request was made.\n"
                    "Use /provider ollama (or another configured provider) for real inference."
                )
        calls = []
        for call in scripted.get("tool_calls") or []:
            arguments = call.get("arguments") or {}
            if isinstance(arguments, str):
                import json

                try:
                    arguments = json.loads(arguments)
                except ValueError:
                    arguments = {}
            calls.append(
                ToolCall(
                    id=str(call.get("id") or make_id("call")),
                    name=str(call.get("name") or ""),
                    arguments=arguments,
                    raw_arguments="",
                )
            )
        response = ModelResponse(
            content=content,
            tool_calls=calls,
            reasoning=str(scripted.get("reasoning") or ""),
            usage=scripted.get("usage") or {"prompt_tokens": 10, "completion_tokens": len(content) // 4},
            finish_reason="tool_calls" if calls else "stop",
        )
        if stream and on_delta:
            size = max(1, len(content) // 6)
            for index in range(0, len(content), size):
                on_delta(content[index : index + size], "content")
        return response

    def list_models(self) -> list[str]:
        return ["mock-standard", "mock-tools", "mock-error"]

    def describe(self) -> dict:
        result = super().describe()
        result["api_key"] = "not needed"
        return result
