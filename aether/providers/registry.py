import os
import time

from aether.config import Config
from aether.errors import ConfigError

from .anthropic import AnthropicProvider
from .base import BaseProvider
from .catalog import ProviderSpec, provider_spec
from .mock import MockProvider
from .openai_compatible import OpenAICompatibleProvider


def _provider_options(config: Config, name: str) -> dict:
    result = config.get(f"providers.{name}", {}) or {}
    return result if isinstance(result, dict) else {}


def build_provider(config: Config, name: str | None = None, model: str | None = None) -> BaseProvider:
    name = name or config.get("provider", "ollama")
    spec: ProviderSpec | None = provider_spec(name)
    options = _provider_options(config, name)
    if spec is None:
        spec = ProviderSpec(
            name=name,
            label=name,
            kind="custom",
            base_url="",
            api_key_env="AETHER_API_KEY",
            api_mode="openai",
            default_model=model or "local-model",
            cost="Unknown. Verify with your endpoint operator.",
            limits="Unknown.",
            requires_base_url=True,
        )
    base_url = options.get("base_url") or os.environ.get(f"{name.upper().replace('-', '_')}_BASE_URL", "") or spec.base_url
    if spec.requires_base_url and not base_url:
        raise ConfigError(f"Provider '{name}' requires base_url. Set providers.{name}.base_url in config or use the documented env var.")
    key_env = options.get("key_env") or options.get("api_key_env") or spec.api_key_env
    api_key = options.get("api_key") or (os.environ.get(key_env, "") if key_env else "")
    selected_model = model or options.get("model") or spec.default_model
    if spec.api_mode == "mock":
        return MockProvider(config, selected_model, spec, script=options.get("script"), fail_times=int(options.get("fail_times", 0)))
    if spec.api_mode == "anthropic":
        return AnthropicProvider(config, selected_model, spec, base_url, api_key)
    return OpenAICompatibleProvider(config, selected_model, spec, base_url, api_key)


class ProviderManager:
    def __init__(self, config: Config):
        self.config = config
        self.active_name = config.get("provider", "ollama")
        self.model = config.get("model") or None
        self.active: BaseProvider = build_provider(config, self.active_name, self.model)
        self.model = self.active.model
        self._cooldown: dict[str, float] = {}

    def activate(self, name: str, model: str | None = None) -> BaseProvider:
        provider = build_provider(self.config, name, model)
        self.active = provider
        self.active_name = name
        self.model = provider.model
        self.config.set("provider", name)
        self.config.set("model", provider.model)
        return provider

    def set_model(self, model: str) -> BaseProvider:
        return self.activate(self.active_name, model)

    def fallback_names(self) -> list[str]:
        names = [str(name) for name in (self.config.get("fallback_providers") or [])]
        return [name for name in names if name != self.active_name]

    def mark_failed(self, name: str, seconds: float = 60.0) -> None:
        self._cooldown[name] = time.monotonic() + seconds

    def _cooling(self, name: str) -> bool:
        until = self._cooldown.get(name)
        return bool(until and time.monotonic() < until)

    def candidates(self) -> list[BaseProvider]:
        result = [self.active]
        for name in self.fallback_names():
            if self._cooling(name):
                continue
            try:
                result.append(build_provider(self.config, name, self.model if name == self.active_name else None))
            except (ConfigError, ValueError):
                continue
        return result

    def describe_active(self) -> dict:
        return self.active.describe()

    def close(self) -> None:
        self.active.close()
