from aether.config import Config
from aether.routing import ModelRouter, RoutingDecision, TaskRequirements, classify_task

TASKS = (
    {"text": "What is a Python list?", "category": "simple_question", "context_tokens": 512},
    {"text": "Implement a small Python function with tests", "category": "software_development", "context_tokens": 2048},
    {"text": "Debug this traceback and explain the root cause", "category": "debugging", "context_tokens": 4096},
    {"text": "Review this patch for security and regressions", "category": "code_review", "context_tokens": 8192},
    {"text": "Research these docs and return citations", "category": "research", "context_tokens": 16384},
    {"text": "Analyze the attached CSV and summarize the statistics", "category": "data_analysis", "context_tokens": 8192},
    {"text": "Write concise README documentation from the repository", "category": "documentation", "context_tokens": 8192},
    {"text": "Summarize this long transcript into decisions and risks", "category": "summarization", "context_tokens": 16384},
    {"text": "Plan a backward-compatible migration with acceptance checks", "category": "planning", "context_tokens": 8192},
    {"text": "Run deterministic checks and report exact commands", "category": "tool_automation", "context_tokens": 2048},
)

MODELS = {
    "mock/bench-fast": {
        "context_window": 4096,
        "pricing": [0.0, 0.0],
        "capabilities": {
            "credentials_configured": True,
            "local": True,
            "tool_calling": True,
            "coding": True,
            "reasoning": False,
            "research": False,
            "structured_output": False,
            "context_handling": False,
            "latency_ms": 20,
            "estimated_memory_mb": 2048,
        },
        "evidence": {"context_window": "verified", "pricing": "provider-reported"},
        "source": "benchmark fixture",
        "freshness": "deterministic",
    },
    "mock/bench-balanced": {
        "context_window": 16384,
        "pricing": [0.0005, 0.0015],
        "capabilities": {
            "credentials_configured": True,
            "local": False,
            "tool_calling": True,
            "coding": True,
            "reasoning": True,
            "research": True,
            "structured_output": True,
            "context_handling": True,
            "latency_ms": 180,
        },
        "evidence": {"context_window": "provider-reported", "pricing": "provider-reported"},
        "source": "benchmark fixture",
        "freshness": "deterministic",
    },
    "mock/bench-long": {
        "context_window": 131072,
        "pricing": [0.003, 0.015],
        "capabilities": {
            "credentials_configured": True,
            "local": False,
            "tool_calling": True,
            "coding": True,
            "reasoning": True,
            "research": True,
            "structured_output": True,
            "context_handling": True,
            "latency_ms": 420,
        },
        "evidence": {"context_window": "verified", "pricing": "provider-reported"},
        "source": "benchmark fixture",
        "freshness": "deterministic",
    },
    "mock/bench-reasoning": {
        "context_window": 32768,
        "pricing": [0.01, 0.03],
        "capabilities": {
            "credentials_configured": True,
            "local": False,
            "tool_calling": True,
            "coding": True,
            "reasoning": True,
            "research": False,
            "structured_output": True,
            "context_handling": True,
            "latency_ms": 650,
        },
        "evidence": {"context_window": "provider-reported", "pricing": "provider-reported"},
        "source": "benchmark fixture",
        "freshness": "deterministic",
    },
}


class MemoryPerformanceStore:
    def __init__(self):
        self.rows = []

    def save_model_performance(self, item: dict) -> None:
        self.rows.append(dict(item))

    def list_model_performance(self, category=None, provider=None, model=None, verified_only=False, limit=None):
        rows = list(self.rows)
        if category:
            rows = [row for row in rows if row.get("category") == category]
        if provider:
            rows = [row for row in rows if row.get("provider") == provider]
        if model:
            rows = [row for row in rows if row.get("model") == model]
        if verified_only:
            rows = [row for row in rows if row.get("verified")]
        rows.reverse()
        return rows[:limit] if limit is not None else rows


def _config(base=None, strategy="capability"):
    raw = base.as_dict() if isinstance(base, Config) else dict(base or {})
    raw.setdefault("costs", {})["confirm_paid"] = False
    routing = raw.setdefault("routing", {})
    routing.update(
        {
            "enabled": True,
            "strategy": strategy,
            "prefer_local": strategy == "cost",
            "strict_capabilities": strategy == "capability",
            "context_safety_margin": 0.1,
            "max_candidates": 5,
            "learned_min_samples": 2,
            "learned_weight": 18.0,
            "roles": {},
            "avoid_models": [],
        }
    )
    raw.setdefault("models", {})["metadata"] = dict(MODELS)
    return Config(raw)


def _requirements(task: dict) -> TaskRequirements:
    requirement = classify_task(task["text"], None, None)
    requirement.category = task["category"]
    requirement.context_tokens = task["context_tokens"]
    requirement.expected_tokens = task["context_tokens"] + 2048
    capability_map = {
        "software_development": ["coding", "tool_calling"],
        "debugging": ["coding", "reasoning", "tool_calling"],
        "code_review": ["coding", "reasoning", "structured_output"],
        "research": ["research", "tool_calling", "structured_output"],
        "data_analysis": ["reasoning", "tool_calling"],
        "planning": ["reasoning"],
        "tool_automation": ["tool_calling"],
    }
    requirement.required_capabilities = capability_map.get(task["category"], [])
    return requirement


def _selected_decision(router: ModelRouter, requirement: TaskRequirements, strategy: str) -> RoutingDecision:
    if strategy == "fixed":
        return RoutingDecision(provider="mock", model="bench-balanced", eligible=True, score=0.0, reasons=["fixed baseline"])
    ranked = router.rank(requirement, role=requirement.role)
    eligible = [item for item in ranked if item.eligible]
    return eligible[0] if eligible else RoutingDecision(reasons=["no eligible model"])


def _score(requirement: TaskRequirements, decision: RoutingDecision, router: ModelRouter) -> dict:
    if not decision.eligible or not decision.provider:
        return {"success": False, "cost_usd": 0.0, "latency_ms": 0.0, "tokens": 0, "fallback": False, "recovery": 0, "reason": "no-route"}
    caps = router.registry.for_model(decision.provider, decision.model)
    window = caps.context_window or 0
    needed = int(requirement.context_tokens * 1.1)
    success = window >= needed
    for name in requirement.required_capabilities:
        if not caps.has(name, True):
            success = False
    pricing = caps.pricing
    cost = 0.0 if pricing is None else (pricing[0] * requirement.context_tokens + pricing[1] * 2048) / 1_000_000
    return {
        "success": bool(success),
        "cost_usd": round(cost, 6),
        "latency_ms": float(caps.value("latency_ms") or 0),
        "tokens": requirement.expected_tokens,
        "fallback": not success and bool(decision.alternatives),
        "recovery": 1 if not success and decision.alternatives else 0,
        "reason": "fixture-eligible" if success else "fixture-ineligible",
    }


def _summarize(rows: list[dict]) -> dict:
    count = len(rows) or 1
    successes = sum(1 for row in rows if row["success"])
    return {
        "tasks": len(rows),
        "success_rate": round(successes / count, 3),
        "total_cost_usd": round(sum(row["cost_usd"] for row in rows), 6),
        "cost_per_success_usd": round(sum(row["cost_usd"] for row in rows) / max(1, successes), 6),
        "mean_latency_ms": round(sum(row["latency_ms"] for row in rows) / count, 1),
        "total_tokens": sum(row["tokens"] for row in rows),
        "fallbacks": sum(1 for row in rows if row["fallback"]),
        "recoveries": sum(row["recovery"] for row in rows),
    }


def run_benchmark(config=None, samples: int = 5) -> dict:
    results = {}
    for strategy in ("fixed", "capability", "cost", "learned"):
        store = MemoryPerformanceStore()
        if strategy == "learned":
            store.rows.extend(
                [
                    {
                        "category": "software_development",
                        "provider": "mock",
                        "model": "bench-balanced",
                        "success": 1,
                        "verified": 1,
                        "sources": ["tests"],
                        "tokens": 100,
                    },
                    {
                        "category": "code_review",
                        "provider": "mock",
                        "model": "bench-reasoning",
                        "success": 1,
                        "verified": 1,
                        "sources": ["verification"],
                        "tokens": 100,
                    },
                ]
            )
        router = ModelRouter(_config(config, strategy), store=store)
        rows = []
        for _ in range(max(1, int(samples))):
            for task in TASKS:
                requirement = _requirements(task)
                decision = _selected_decision(router, requirement, strategy)
                outcome = _score(requirement, decision, router)
                rows.append(
                    {
                        "task": task["category"],
                        "selected": decision.key,
                        **outcome,
                    }
                )
                router.record_performance(
                    requirement,
                    decision,
                    success=outcome["success"],
                    usage={"prompt_tokens": requirement.context_tokens, "estimated_cost": outcome["cost_usd"], "cost_known": True},
                    verification={"status": "verified", "sources": ["deterministic"], "verified": True},
                )
        results[strategy] = {
            "summary": _summarize(rows),
            "selected_models": sorted({row["selected"] for row in rows}),
        }
    return {
        "kind": "deterministic routing simulation",
        "samples": max(1, int(samples)),
        "live_model_calls": 0,
        "network_calls": 0,
        "assumptions": [
            "Task requirements and model capabilities come from checked-in fixtures.",
            "Success means the fixture context window and declared capabilities cover the task requirement.",
            "Costs use checked-in fixture prices, never live provider pricing.",
            "Latency, tokens, fallback, and recovery are deterministic fixture measures, not measured production performance.",
        ],
        "results": results,
    }
