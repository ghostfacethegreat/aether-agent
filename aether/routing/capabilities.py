import os
from dataclasses import dataclass, field

from aether.providers.catalog import ProviderSpec, provider_spec
from aether.utils import redact

EVIDENCE_LEVELS = ("verified", "provider-reported", "inferred", "unknown")
CAPABILITY_FIELDS = (
    "model_version",
    "context_window",
    "input_pricing",
    "output_pricing",
    "cached_pricing",
    "tool_calling",
    "structured_output",
    "streaming",
    "coding",
    "reasoning",
    "research",
    "context_handling",
    "vision",
    "local",
    "estimated_memory_mb",
    "concurrency",
    "latency_ms",
    "credentials_configured",
)
SOURCE = "aether code audit: 2026-11-24"


def _fact(value=None, evidence="unknown", source="", freshness="") -> dict:
    if value is None:
        evidence = "unknown"
    if evidence not in EVIDENCE_LEVELS:
        evidence = "unknown"
    return {
        "value": value,
        "evidence": evidence,
        "source": str(source or ""),
        "freshness": str(freshness or ""),
    }


@dataclass
class CapabilityFact:
    value: object = None
    evidence: str = "unknown"
    source: str = ""
    freshness: str = ""

    @classmethod
    def from_dict(cls, payload) -> "CapabilityFact":
        payload = payload if isinstance(payload, dict) else {}
        return cls(
            value=payload.get("value"),
            evidence=str(payload.get("evidence") or "unknown"),
            source=str(payload.get("source") or ""),
            freshness=str(payload.get("freshness") or ""),
        )

    def to_dict(self) -> dict:
        return _fact(self.value, self.evidence, self.source, self.freshness)

    @property
    def known(self) -> bool:
        return self.value is not None and self.evidence != "unknown"

    def satisfied(self, required: bool = True) -> bool:
        return not bool(required) or (self.value is True and self.evidence != "unknown")

    def blocks(self, required: bool = True) -> bool:
        return bool(required) and self.value is False and self.evidence != "unknown"


@dataclass
class ModelCapabilities:
    provider: str
    model: str
    facts: dict[str, CapabilityFact] = field(default_factory=dict)
    restrictions: list[str] = field(default_factory=list)

    def __post_init__(self):
        for name in CAPABILITY_FIELDS:
            self.facts.setdefault(name, CapabilityFact())

    def fact(self, name: str) -> CapabilityFact:
        return self.facts.get(name, CapabilityFact())

    def value(self, name: str):
        return self.fact(name).value

    def has(self, name: str, required: bool = True) -> bool:
        return self.fact(name).satisfied(required)

    def blocks(self, name: str, required: bool = True) -> bool:
        return self.fact(name).blocks(required)

    @property
    def context_window(self) -> int | None:
        value = self.value("context_window")
        return int(value) if isinstance(value, (int, float)) and value > 0 else None

    @property
    def pricing(self) -> tuple[float, float] | None:
        input_price = self.value("input_pricing")
        output_price = self.value("output_pricing")
        if not isinstance(input_price, (int, float)) or not isinstance(output_price, (int, float)):
            return None
        return float(input_price), float(output_price)

    @property
    def local(self) -> bool:
        return bool(self.value("local"))

    @property
    def key(self) -> str:
        return f"{self.provider}/{self.model}"

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "facts": {name: fact.to_dict() for name, fact in self.facts.items()},
            "restrictions": list(self.restrictions),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "ModelCapabilities":
        payload = payload if isinstance(payload, dict) else {}
        item = cls(str(payload.get("provider") or ""), str(payload.get("model") or ""))
        raw = payload.get("facts") or {}
        if isinstance(raw, dict):
            for name, value in raw.items():
                item.facts[str(name)] = CapabilityFact.from_dict(value)
        item.restrictions = [str(value) for value in (payload.get("restrictions") or [])]
        return item


class CapabilityRegistry:
    def __init__(self, config=None):
        self.config = config

    @staticmethod
    def _get(config, key, default=None):
        return config.get(key, default) if config is not None else default

    @staticmethod
    def _spec(provider: str, config=None) -> ProviderSpec:
        spec = provider_spec(provider)
        if spec is not None:
            return spec
        options = CapabilityRegistry._provider_options(config, provider)
        return ProviderSpec(
            name=provider,
            label=provider,
            kind="custom",
            base_url="",
            api_key_env="",
            api_mode="openai",
            default_model=str(options.get("model") or "local-model"),
            cost="Unknown.",
            limits="Unknown.",
            requires_base_url=True,
        )

    @staticmethod
    def _provider_options(config, provider: str) -> dict:
        value = CapabilityRegistry._get(config, f"providers.{provider}", {}) or {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _credentials_ready(spec: ProviderSpec, options: dict) -> bool:
        if spec.kind == "local" or spec.api_mode == "mock":
            return True
        if options.get("api_key") or options.get("key") or options.get("token"):
            return True
        key_env = options.get("key_env") or options.get("api_key_env") or spec.api_key_env
        if not key_env:
            return False
        return bool(os.environ.get(str(key_env)))

    def for_model(self, provider: str, model: str) -> ModelCapabilities:
        spec = self._spec(provider, self.config)
        options = self._provider_options(self.config, provider)
        freshness = str(self._get(self.config, "models.freshness", SOURCE) or SOURCE)
        facts: dict[str, CapabilityFact] = {}
        restrictions = []

        facts["model_version"] = CapabilityFact(**_fact(None, "unknown", SOURCE, freshness))
        facts["context_window"] = CapabilityFact(**_fact(None, "unknown", SOURCE, freshness))
        facts["input_pricing"] = CapabilityFact(**_fact(None, "unknown", SOURCE, freshness))
        facts["output_pricing"] = CapabilityFact(**_fact(None, "unknown", SOURCE, freshness))
        facts["cached_pricing"] = CapabilityFact(**_fact(None, "unknown", SOURCE, freshness))
        facts["tool_calling"] = CapabilityFact(
            **_fact(True, "verified" if spec.api_mode == "mock" else "inferred", SOURCE, freshness)
        )
        facts["structured_output"] = CapabilityFact(**_fact(None, "unknown", SOURCE, freshness))
        facts["streaming"] = CapabilityFact(**_fact(True, "verified", SOURCE, freshness))
        for name in ("coding", "reasoning", "research", "context_handling", "vision"):
            facts[name] = CapabilityFact(**_fact(None, "unknown", SOURCE, freshness))
        facts["local"] = CapabilityFact(**_fact(spec.kind == "local", "verified", SOURCE, freshness))
        facts["estimated_memory_mb"] = CapabilityFact(**_fact(None, "unknown", SOURCE, freshness))
        facts["concurrency"] = CapabilityFact(**_fact(None, "unknown", SOURCE, freshness))
        facts["latency_ms"] = CapabilityFact(**_fact(0 if spec.kind == "local" else None, "verified" if spec.kind == "local" else "unknown", SOURCE, freshness))
        facts["credentials_configured"] = CapabilityFact(
            **_fact(self._credentials_ready(spec, options), "verified", "config and environment presence only", freshness)
        )

        price = spec.model_prices.get(model) or spec.price_per_1m
        if price and len(price) >= 2:
            facts["input_pricing"] = CapabilityFact(**_fact(float(price[0]), "provider-reported", "aether/providers/catalog.py", freshness))
            facts["output_pricing"] = CapabilityFact(**_fact(float(price[1]), "provider-reported", "aether/providers/catalog.py", freshness))
        cache_price = spec.model_cache_prices.get(model) or spec.cache_price_per_1m
        if cache_price and len(cache_price) >= 2:
            facts["cached_pricing"] = CapabilityFact(
                **_fact((float(cache_price[0]), float(cache_price[1])), "provider-reported", "aether/providers/catalog.py", freshness)
            )
        for note in (spec.limits, spec.pricing_note, spec.docs):
            text = redact(str(note or "")).strip()
            if text and text.lower() != "unknown." and text not in restrictions:
                restrictions.append(text)

        self._apply_user_metadata(provider, model, facts, restrictions)
        return ModelCapabilities(provider=provider, model=model, facts=facts, restrictions=restrictions)

    def _apply_user_metadata(self, provider: str, model: str, facts: dict, restrictions: list) -> None:
        metadata = self._get(self.config, "models.metadata", {}) or {}
        if not isinstance(metadata, dict):
            return
        keys = (f"{provider}/{model}", model)
        raw = None
        for key in keys:
            if key in metadata and isinstance(metadata[key], dict):
                raw = metadata[key]
                break
        if raw is None:
            return
        source = str(raw.get("source") or "user config")
        freshness = str(raw.get("freshness") or "")
        raw_evidence = raw.get("evidence")
        evidence = raw_evidence if isinstance(raw_evidence, dict) else {}
        default_evidence = (
            str(evidence.get("default") or "provider-reported")
            if isinstance(raw_evidence, dict)
            else str(raw_evidence or "provider-reported")
        )
        aliases = {
            "context_window": "context_window",
            "model_version": "model_version",
            "estimated_memory_mb": "estimated_memory_mb",
            "concurrency": "concurrency",
            "latency_ms": "latency_ms",
        }
        for key, name in aliases.items():
            if key not in raw:
                continue
            facts[name] = CapabilityFact(**_fact(raw[key], str(evidence.get(name, default_evidence)), source, freshness))
        capabilities = raw.get("capabilities") or {}
        if isinstance(capabilities, dict):
            for name, value in capabilities.items():
                name = str(name)
                if name not in facts and name not in {"coding", "reasoning", "research", "context_handling", "vision", "tool_calling", "structured_output", "streaming", "local"}:
                    continue
                if isinstance(value, dict):
                    facts[name] = CapabilityFact(
                        **_fact(value.get("value"), str(value.get("evidence", default_evidence)), str(value.get("source", source)), str(value.get("freshness", freshness)))
                    )
                else:
                    facts[name] = CapabilityFact(**_fact(value, str(evidence.get(name, default_evidence)), source, freshness))
        pricing = raw.get("pricing")
        if isinstance(pricing, (list, tuple)) and len(pricing) >= 2:
            pricing_evidence = str(evidence.get("pricing", default_evidence))
            facts["input_pricing"] = CapabilityFact(
                **_fact(float(pricing[0]), str(evidence.get("input_pricing", pricing_evidence)), source, freshness)
            )
            facts["output_pricing"] = CapabilityFact(
                **_fact(float(pricing[1]), str(evidence.get("output_pricing", pricing_evidence)), source, freshness)
            )
        cache_pricing = raw.get("cache_pricing")
        if isinstance(cache_pricing, (list, tuple)) and len(cache_pricing) >= 2:
            facts["cached_pricing"] = CapabilityFact(
                **_fact((float(cache_pricing[0]), float(cache_pricing[1])), str(evidence.get("cached_pricing", default_evidence)), source, freshness)
            )
        for item in (raw.get("restrictions") or []):
            text = redact(str(item)).strip()
            if text and text not in restrictions:
                restrictions.append(text)

    def configured_entries(self, manager=None, role: str | None = None) -> list[tuple[str, str]]:
        entries: list[tuple[str, str]] = []

        def add(provider: str, model: str = "") -> None:
            provider = str(provider or "").strip()
            if not provider:
                return
            model = str(model or "").strip() or self._configured_model(provider)
            entry = (provider, model)
            if entry not in entries:
                entries.append(entry)

        if manager is not None:
            add(getattr(manager, "active_name", ""), getattr(manager, "model", ""))
            for name in (getattr(manager, "fallback_names", lambda: [])() or []):
                add(name)
        else:
            add(str(self._get(self.config, "provider", "") or ""), str(self._get(self.config, "model", "") or ""))
            for name in (self._get(self.config, "fallback_providers", []) or []):
                add(name)
        if role:
            role_cfg = {}
            for section in (f"orchestrator.roles.{role}", f"routing.roles.{role}"):
                value = self._get(self.config, section, {}) or {}
                if isinstance(value, dict):
                    role_cfg.update(value)
            add(str(role_cfg.get("provider") or ""), str(role_cfg.get("model") or ""))
            preferred = str(role_cfg.get("preferred") or "")
            if preferred and "/" in preferred:
                add(*preferred.split("/", 1))
            fallbacks = role_cfg.get("fallbacks") or []
            if isinstance(fallbacks, (list, tuple)):
                for fallback in fallbacks:
                    text = str(fallback)
                    if "/" in text:
                        add(*text.split("/", 1))
                    else:
                        add(text)
        metadata = self._get(self.config, "models.metadata", {}) or {}
        if isinstance(metadata, dict):
            for key in metadata:
                text = str(key)
                if "/" in text and isinstance(metadata[key], dict):
                    provider, model = text.split("/", 1)
                    add(provider, model)
        return entries

    def _configured_model(self, provider: str) -> str:
        options = self._provider_options(self.config, provider)
        if options.get("model"):
            return str(options["model"])
        return self._spec(provider, self.config).default_model
