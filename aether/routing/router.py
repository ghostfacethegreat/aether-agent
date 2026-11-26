from dataclasses import dataclass, field

from aether.providers.catalog import provider_is_billable
from aether.utils import make_id, paid_confirmation_value, utc_now

from .capabilities import CapabilityRegistry
from .classifier import TaskRequirements

EVIDENCE_SOURCES = {"tests", "check", "deterministic", "verification", "user"}


@dataclass
class RoutingDecision:
    provider: str = ""
    model: str = ""
    score: float = 0.0
    eligible: bool = False
    reasons: list[str] = field(default_factory=list)
    rejections: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)
    requirements: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.provider}/{self.model}" if self.provider else "none"

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "score": round(float(self.score), 3),
            "eligible": bool(self.eligible),
            "reasons": list(self.reasons),
            "rejections": list(self.rejections),
            "alternatives": list(self.alternatives),
            "requirements": dict(self.requirements),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "RoutingDecision":
        payload = payload if isinstance(payload, dict) else {}
        return cls(
            provider=str(payload.get("provider") or ""),
            model=str(payload.get("model") or ""),
            score=float(payload.get("score") or 0.0),
            eligible=bool(payload.get("eligible")),
            reasons=[str(item) for item in (payload.get("reasons") or [])],
            rejections=[str(item) for item in (payload.get("rejections") or [])],
            alternatives=[str(item) for item in (payload.get("alternatives") or [])],
            requirements=dict(payload.get("requirements") or {}),
        )


def _config_get(config, key, default=None):
    return config.get(key, default) if config is not None else default


def _paid_confirmed(config) -> bool:
    env = paid_confirmation_value()
    if env is not None:
        return str(env).strip().lower() in {"1", "true", "yes", "on"}
    raw = _config_get(config, "costs.confirm_paid", True)
    if raw is None:
        return False
    if isinstance(raw, bool):
        return not raw
    normalized = str(raw).strip().lower()
    if normalized in {"0", "false", "no", "off"}:
        return True
    if normalized in {"1", "true", "yes", "on"}:
        return False
    return False


class ModelRouter:
    def __init__(self, config=None, registry=None, store=None):
        self.config = config
        self.registry = registry or CapabilityRegistry(config)
        self.store = store

    @staticmethod
    def _setting(name, default):
        return None

    def _get(self, key, default=None):
        return _config_get(self.config, key, default)

    def rank(self, requirements: TaskRequirements, manager=None, role: str | None = None) -> list[RoutingDecision]:
        from aether.orchestration.roles import DEFAULT_ROLES

        role = str(role or requirements.role or "")
        role_cfg = dict(DEFAULT_ROLES.get(role, {}) or {})
        for key in (f"orchestrator.roles.{role}", f"routing.roles.{role}"):
            override = self._get(key, {}) or {}
            if isinstance(override, dict):
                role_cfg.update(override)
        extra_capabilities = [str(item) for item in (role_cfg.get("capabilities") or [])]
        needed = list(requirements.required_capabilities)
        for capability in extra_capabilities:
            if capability not in needed:
                needed.append(capability)
        role_context = int(role_cfg.get("context_tokens") or 0)
        context_tokens = max(role_context, int(requirements.context_tokens or 2048))
        preferred = str(role_cfg.get("preferred") or "")
        strict = bool(self._get("routing.strict_capabilities", False))
        strategy = str(self._get("routing.strategy", "capability") or "capability")
        prefer_local = bool(self._get("routing.prefer_local", True)) or strategy == "cost"
        margin = float(self._get("routing.context_safety_margin", 0.1) or 0.1)
        limit = max(1, int(self._get("routing.max_candidates", 5) or 5))

        entries = self.registry.configured_entries(manager, role=role or None)
        if requirements.explicit_provider:
            entries = [entry for entry in entries if entry[0] == requirements.explicit_provider]
        if requirements.explicit_model:
            entries = [entry for entry in entries if entry[1] == requirements.explicit_model]
        active_key = (
            f"{getattr(manager, 'active_name', '')}/{getattr(manager, 'model', '')}"
            if manager is not None
            else f"{self._get('provider', '')}/{self._get('model', '')}"
        )
        if strategy == "fixed":
            entries = [entry for entry in entries if f"{entry[0]}/{entry[1]}" == active_key]
        if not entries:
            return [RoutingDecision(
                eligible=False,
                reasons=["no configured model matched the explicit provider/model"],
                rejections=["no configured candidates"],
                requirements=requirements.to_dict(),
            )]

        decisions = []
        for provider, model in entries:
            decisions.append(
                self._evaluate(
                    provider,
                    model,
                    requirements,
                    needed,
                    context_tokens,
                    strict=strict,
                    prefer_local=prefer_local,
                    margin=margin,
                    preferred=preferred,
                    active_key=active_key,
                    manager=manager,
                    strategy=strategy,
                )
            )
        decisions.sort(key=lambda item: (item.eligible, item.score, item.key), reverse=True)
        result = decisions[:limit]
        alive = [item for item in result if item.eligible]
        selected = alive[0] if alive else (result[0] if result else None)
        if selected is not None:
            selected.alternatives = [item.key for item in alive if item.key != selected.key][: limit - 1]
        return result

    def route(self, requirements: TaskRequirements, manager=None, role: str | None = None) -> RoutingDecision:
        ranked = self.rank(requirements, manager=manager, role=role)
        eligible = [item for item in ranked if item.eligible]
        if not eligible:
            rejections = []
            for item in ranked:
                rejections.extend(item.rejections)
            return RoutingDecision(
                eligible=False,
                reasons=["no suitable configured model was found"],
                rejections=list(dict.fromkeys(rejections)) or [item.key for item in ranked],
                requirements=requirements.to_dict(),
            )
        decision = eligible[0]
        decision.reasons.insert(0, f"selected {decision.key} with score {decision.score:.1f}")
        return decision

    def _evaluate(
        self,
        provider: str,
        model: str,
        requirements: TaskRequirements,
        needed: list[str],
        context_tokens: int,
        strict: bool,
        prefer_local: bool,
        margin: float,
        preferred: str,
        active_key: str,
        manager=None,
        strategy: str = "capability",
    ) -> RoutingDecision:
        caps = self.registry.for_model(provider, model)
        decision = RoutingDecision(provider=provider, model=model, requirements=requirements.to_dict())
        score = 100.0

        if not caps.fact("credentials_configured").value:
            score -= 8.0
            decision.reasons.append("credentials were not detected; provider construction or call will verify access")
        health_ok, health_reason = self._health(manager, provider)
        if not health_ok:
            decision.rejections.append(health_reason)
            return decision

        if provider_is_billable(provider, model) and not _paid_confirmed(self.config):
            decision.rejections.append("billable provider is not authorized by paid-provider confirmation")
            return decision

        for capability in needed:
            if caps.blocks(capability, True):
                decision.rejections.append(f"{caps.key if hasattr(caps, 'key') else provider + '/' + model} reports {capability}=false")
                return decision
            if caps.has(capability, True):
                evidence = caps.fact(capability).evidence
                bonus = {"verified": 7.0, "provider-reported": 6.0, "inferred": 3.0}.get(evidence, 0.0)
                score += bonus
                decision.reasons.append(f"{capability} supported ({evidence})")
            else:
                if strict:
                    decision.rejections.append(f"{capability} is unknown and strict_capabilities is enabled")
                    return decision
                score -= 4.0
                decision.reasons.append(f"{capability} is unknown; not treated as proof of support")

        window = caps.context_window
        needed_window = int(context_tokens * (1.0 + margin))
        if window is not None:
            if window < needed_window:
                decision.rejections.append(f"context window {window} is below required {needed_window}")
                return decision
            score += 5.0
            decision.reasons.append(f"context window {window} covers estimated need {context_tokens}")
        elif requirements.category == "long_context":
            score -= 8.0
            decision.reasons.append("long-context task has no verified context window")
        else:
            score -= 1.0

        pricing = caps.pricing
        if pricing is None:
            score -= 3.0
            decision.reasons.append("pricing is unknown and was not treated as zero")
        else:
            input_price, output_price = pricing
            estimate = (input_price * context_tokens + output_price * int(self._get("max_tokens", 2048) or 2048)) / 1_000_000
            if estimate <= 0.01:
                price_score = 5.0
            elif estimate <= 0.1:
                price_score = 2.0
            else:
                price_score = -6.0
            if strategy == "cost":
                price_score *= 2.0
                decision.reasons.append("cost strategy weighted pricing")
            score += price_score
            decision.reasons.append(f"estimated token price ${estimate:.6f}")

        if prefer_local and caps.local:
            score += 4.0
            decision.reasons.append("local inference preferred")
        if caps.local and caps.fact("estimated_memory_mb").value is not None:
            memory = int(caps.fact("estimated_memory_mb").value)
            if memory > 8192:
                score -= 5.0
                decision.reasons.append("estimated local memory exceeds conservative 8 GB target")
        if caps.fact("latency_ms").value is not None:
            latency = float(caps.fact("latency_ms").value)
            if latency <= 50:
                score += 2.0
            elif latency > 500:
                score -= 4.0
            decision.reasons.append(f"estimated latency {latency:.0f} ms")

        if preferred and preferred == f"{provider}/{model}":
            score += 8.0
            decision.reasons.append("role preferred model")
        if f"{provider}/{model}" == active_key:
            score += 1.5
            decision.reasons.append("active model stability bonus")
        if f"{provider}/{model}" in requirements.avoid_models:
            score -= 10.0
            decision.reasons.append("avoided because another role already used this model")

        learned = self._learned_score(requirements.category, provider, model)
        score += learned[0]
        decision.reasons.extend(learned[1])

        decision.score = round(score, 3)
        decision.eligible = True
        if not decision.reasons:
            decision.reasons.append("no disqualifying capability, cost, health, or context issue")
        return decision

    def _health(self, manager, provider: str) -> tuple[bool, str]:
        if manager is None:
            return True, ""
        health = getattr(manager, "health", None)
        if callable(health):
            entry = (health() or {}).get(provider) or {}
            if entry.get("status") == "cooling":
                return False, f"{provider} is cooling after {entry.get('reason', 'a provider failure')}"
            return True, ""
        cooling = getattr(manager, "_cooling", None)
        if callable(cooling) and cooling(provider):
            return False, f"{provider} is cooling after a provider failure"
        return True, ""

    def _learned_score(self, category: str, provider: str, model: str) -> tuple[float, list[str]]:
        if self.store is None or not hasattr(self.store, "list_model_performance"):
            return 0.0, []
        rows = self.store.list_model_performance(category=category, provider=provider, model=model, limit=None) or []
        verified = [row for row in rows if bool(row.get("verified")) and row.get("sources")]
        minimum = max(1, int(self._get("routing.learned_min_samples", 3) or 3))
        if len(verified) < minimum:
            if rows and not verified:
                return 0.0, ["unverified model history was ignored"]
            return 0.0, []
        successes = sum(1 for row in verified if bool(row.get("success")))
        rate = successes / len(verified)
        confidence = min(1.0, len(verified) / (minimum * 2))
        weight = float(self._get("routing.learned_weight", 12.0) or 12.0)
        score = (rate - 0.5) * weight * confidence
        return score, [f"verified history {successes}/{len(verified)} success for this category"]

    def record_performance(
        self,
        requirements: TaskRequirements,
        decision: RoutingDecision,
        success: bool,
        usage: dict | None = None,
        duration_ms: float = 0.0,
        recovery_attempts: int = 0,
        verification: dict | None = None,
        experience_id: str = "",
    ) -> dict:
        if self.store is None or not hasattr(self.store, "save_model_performance") or not decision.key:
            return {}
        usage = usage or {}
        verification = verification or {}
        sources = [str(item) for item in (verification.get("sources") or [])]
        status = str(verification.get("status") or "").strip().lower()
        explicit = bool(verification.get("verified")) or status in {"verified", "passed", "success"}
        verified = explicit and bool(set(sources) & EVIDENCE_SOURCES)
        item = {
            "id": make_id("model-perf"),
            "category": requirements.category,
            "provider": decision.provider,
            "model": decision.model,
            "success": int(bool(success)),
            "verified": int(verified),
            "sources": sources,
            "tokens": int(usage.get("prompt_tokens", 0)) + int(usage.get("completion_tokens", 0)),
            "cost": float(usage.get("estimated_cost", 0.0) or 0.0),
            "cost_known": bool(usage.get("cost_known")),
            "duration_ms": round(float(duration_ms or 0.0), 3),
            "recovery_attempts": int(recovery_attempts or 0),
            "experience_id": str(experience_id or ""),
            "created_at": utc_now(),
        }
        self.store.save_model_performance(item)
        return item

    @staticmethod
    def explain(decision: RoutingDecision) -> str:
        if not decision.provider:
            lines = ["No suitable configured model was found."]
            lines.extend(f"- {reason}" for reason in decision.reasons)
            lines.extend(f"- rejected: {reason}" for reason in decision.rejections)
            return "\n".join(lines)
        lines = [
            f"Selected {decision.key} (score {decision.score:.1f}).",
            "Reasons:",
        ]
        lines.extend(f"- {reason}" for reason in decision.reasons)
        if decision.alternatives:
            lines.append("Fallbacks: " + ", ".join(decision.alternatives))
        if decision.rejections:
            lines.append("Rejections:")
            lines.extend(f"- {reason}" for reason in decision.rejections)
        return "\n".join(lines)
