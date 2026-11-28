from dataclasses import dataclass, field

from aether.utils import estimate_tokens

CATEGORIES = (
    "general",
    "simple_question",
    "complex_reasoning",
    "software_development",
    "debugging",
    "code_review",
    "research",
    "data_analysis",
    "documentation",
    "summarization",
    "planning",
    "tool_automation",
    "long_context",
    "orchestration",
)

CATEGORY_KEYWORDS = {
    "simple_question": ("what is", "who is", "define", "explain briefly", "hello", "hi there"),
    "complex_reasoning": ("analyze tradeoffs", "compare architectures", "prove", "derive", "reason carefully", "ambiguous"),
    "software_development": ("build", "implement", "write code", "create a python", "refactor", "function", "api", "class", "script"),
    "debugging": ("debug", "error", "traceback", "failing test", "exception", "why does this fail", "fix the bug"),
    "code_review": ("review this code", "code review", "audit this diff", "review the patch", "security review"),
    "research": ("research", "find sources", "citations", "compare docs", "investigate", "web search", "look up"),
    "data_analysis": ("analyze data", "csv", "dataset", "statistics", "chart", "spreadsheet", "regression analysis"),
    "documentation": ("document", "readme", "write docs", "changelog", "usage guide", "api docs"),
    "summarization": ("summarize", "summary of", "condense", "tldr", "brief recap"),
    "planning": ("plan", "roadmap", "design a", "break down", "steps to", "milestones"),
    "tool_automation": ("run tests", "execute", "terminal", "schedule", "automate", "tool call", "workflow"),
    "long_context": ("long document", "entire repository", "large file", "full transcript", "many pages", "whole codebase"),
    "orchestration": ("multi-agent", "delegate", "parallel agents", "team of agents", "orchestrate", "specialist agents"),
}

CATEGORY_CAPABILITIES = {
    "complex_reasoning": ("reasoning",),
    "software_development": ("coding", "tool_calling"),
    "debugging": ("coding", "reasoning", "tool_calling"),
    "code_review": ("coding", "reasoning", "structured_output"),
    "research": ("research", "tool_calling", "structured_output"),
    "data_analysis": ("reasoning", "tool_calling"),
    "documentation": (),
    "summarization": (),
    "planning": ("reasoning",),
    "tool_automation": ("tool_calling",),
    "long_context": ("context_handling",),
    "orchestration": ("tool_calling", "structured_output"),
}

TOOL_KEYWORDS = {
    "web_search": ("search", "web", "source", "citation", "research"),
    "web_fetch": ("url", "http", "documentation", "article", "page"),
    "read_file": ("file", "repository", "codebase", "script", "diff"),
    "write_file": ("write", "create", "edit", "implement", "refactor"),
    "terminal": ("run", "test", "command", "execute", "build", "git"),
    "python": ("python", "data", "csv", "script"),
}


def _config_get(config, key, default=None):
    return config.get(key, default) if config is not None else default


@dataclass
class TaskRequirements:
    text: str
    category: str = "general"
    complexity: str = "moderate"
    context_tokens: int = 2048
    expected_tokens: int = 4096
    tool_names: list[str] = field(default_factory=list)
    accuracy: str = "normal"
    required_capabilities: list[str] = field(default_factory=list)
    explicit_provider: str = ""
    explicit_model: str = ""
    role: str = ""
    avoid_models: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "category": self.category,
            "complexity": self.complexity,
            "context_tokens": self.context_tokens,
            "expected_tokens": self.expected_tokens,
            "tool_names": list(self.tool_names),
            "accuracy": self.accuracy,
            "required_capabilities": list(self.required_capabilities),
            "explicit_provider": self.explicit_provider,
            "explicit_model": self.explicit_model,
            "role": self.role,
            "avoid_models": list(self.avoid_models),
            "signals": list(self.signals),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "TaskRequirements":
        payload = payload if isinstance(payload, dict) else {}
        return cls(
            text=str(payload.get("text") or ""),
            category=str(payload.get("category") or "general"),
            complexity=str(payload.get("complexity") or "moderate"),
            context_tokens=int(payload.get("context_tokens") or 2048),
            expected_tokens=int(payload.get("expected_tokens") or 4096),
            tool_names=[str(item) for item in (payload.get("tool_names") or [])],
            accuracy=str(payload.get("accuracy") or "normal"),
            required_capabilities=[str(item) for item in (payload.get("required_capabilities") or [])],
            explicit_provider=str(payload.get("explicit_provider") or ""),
            explicit_model=str(payload.get("explicit_model") or ""),
            role=str(payload.get("role") or ""),
            avoid_models=[str(item) for item in (payload.get("avoid_models") or [])],
            signals=[str(item) for item in (payload.get("signals") or [])],
        )


def classify_task(
    text: str,
    config=None,
    execution_plan=None,
    role: str | None = None,
    explicit_provider: str = "",
    explicit_model: str = "",
    avoid_models=None,
) -> TaskRequirements:
    text = str(text or "").strip()
    lowered = text.lower()
    signals: list[str] = []
    scores = {category: 0 for category in CATEGORIES}
    for category, keywords in CATEGORY_KEYWORDS.items():
        custom = _config_get(config, f"routing.category_keywords.{category}", []) or []
        for keyword in tuple(keywords) + tuple(str(item) for item in custom):
            if keyword and keyword.lower() in lowered:
                scores[category] += 2
                if category not in signals:
                    signals.append(category)
    plan_text = ""
    if execution_plan is not None:
        if hasattr(execution_plan, "to_dict"):
            plan_text = str(execution_plan.to_dict())
        else:
            plan_text = str(execution_plan)
    if plan_text:
        for category in CATEGORIES:
            if category in plan_text.lower():
                scores[category] += 1
    category = max(CATEGORIES, key=lambda item: (scores[item], item == "general"))
    if scores[category] == 0:
        category = "simple_question" if len(lowered) <= 120 and "?" in text else "general"
        signals.append(category)

    length = len(lowered)
    high_risk = any(token in lowered for token in ("production", "delete", "deploy", "payment", "security", "secret", "password"))
    multi_step = any(token in lowered for token in ("then", "after", "finally", "step", "first", "next", "before"))
    if high_risk:
        complexity = "high"
        signals.append("high-risk")
    elif length > 2000 or multi_step or category in {"complex_reasoning", "orchestration", "code_review"}:
        complexity = "complex"
    elif length > 300 or category in {"software_development", "debugging", "research", "data_analysis", "long_context"}:
        complexity = "moderate"
    elif category == "simple_question":
        complexity = "simple"
    else:
        complexity = "moderate"

    context_tokens = max(256, int(estimate_tokens(text) * 1.25))
    if category == "long_context":
        context_tokens = max(context_tokens, int(_config_get(config, "routing.long_context_tokens", 16384) or 16384))
    expected_tokens = context_tokens + int(_config_get(config, "max_tokens", 2048) or 2048)
    tool_names = [name for name, keywords in TOOL_KEYWORDS.items() if any(keyword in lowered for keyword in keywords)]
    required = list(CATEGORY_CAPABILITIES.get(category, ()))
    if complexity in {"complex", "high"} and "reasoning" not in required:
        required.append("reasoning")
    accuracy = "high" if category in {"code_review", "debugging", "research", "data_analysis", "complex_reasoning"} or high_risk else "normal"

    requirement = TaskRequirements(
        text=text,
        category=category,
        complexity=complexity,
        context_tokens=context_tokens,
        expected_tokens=expected_tokens,
        tool_names=tool_names,
        accuracy=accuracy,
        required_capabilities=required,
        explicit_provider=str(explicit_provider or ""),
        explicit_model=str(explicit_model or ""),
        role=str(role or ""),
        avoid_models=[str(item) for item in (avoid_models or [])],
        signals=signals,
    )
    _apply_overrides(requirement, config)
    if explicit_provider:
        requirement.explicit_provider = str(explicit_provider)
    if explicit_model:
        requirement.explicit_model = str(explicit_model)
    if avoid_models:
        requirement.avoid_models = [str(item) for item in avoid_models]
    return requirement


def _apply_overrides(requirement: TaskRequirements, config) -> None:
    overrides = _config_get(config, "routing.overrides", {}) or {}
    if not isinstance(overrides, dict):
        return
    values = overrides.get(requirement.category) if requirement.category in overrides else overrides
    if not isinstance(values, dict):
        return
    if values.get("category"):
        requirement.category = str(values["category"])
    if values.get("complexity"):
        requirement.complexity = str(values["complexity"])
    if values.get("context_tokens"):
        requirement.context_tokens = int(values["context_tokens"])
    if values.get("tools"):
        requirement.tool_names = [str(item) for item in values["tools"]]
    if values.get("accuracy"):
        requirement.accuracy = str(values["accuracy"])
    capabilities = values.get("capabilities") or values.get("required_capabilities")
    if capabilities is not None:
        requirement.required_capabilities = [str(item) for item in capabilities]
    if values.get("provider"):
        requirement.explicit_provider = str(values["provider"])
    if values.get("model"):
        requirement.explicit_model = str(values["model"])
