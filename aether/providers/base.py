from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict = field(default_factory=dict)
    raw_arguments: str = ""


@dataclass
class ModelResponse:
    content: str = ""
    tool_calls: list = field(default_factory=list)
    reasoning: str = ""
    usage: dict = field(default_factory=dict)
    finish_reason: str = "stop"
    raw: dict = field(default_factory=dict)


class BaseProvider(ABC):
    name = "base"
    label = "Base"
    kind = "custom"
    cost = "Unknown"
    limits = "Unknown"
    default_model = ""

    def __init__(self, config, model=None, spec=None):
        self.config = config
        self.model = model or self.default_model
        self.spec = spec
        self.timeout = int(config.get("request_timeout", 60) or 60)
        self.retry_attempts = max(0, int(config.get("retry_attempts", 2) or 0))

    @abstractmethod
    def chat(self, messages, tools=None, stream=False, on_delta=None, options=None) -> ModelResponse:
        raise NotImplementedError

    def list_models(self) -> list[str]:
        return []

    def close(self) -> None:
        return None

    def describe(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "kind": self.kind,
            "model": self.model,
            "cost": self.cost,
            "cost_note": str(getattr(self.spec, "pricing_note", "") or "Rough estimates only; verify provider billing."),
            "limits": self.limits,
        }
