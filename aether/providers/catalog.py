from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    label: str
    kind: str
    base_url: str
    api_key_env: str
    api_mode: str
    default_model: str
    cost: str
    limits: str
    sample_models: tuple = field(default_factory=tuple)
    requires_base_url: bool = False
    docs: str = ""
    pricing_note: str = ""
    price_per_1m: tuple[float, float] | None = None
    model_prices: dict[str, tuple[float, float]] = field(default_factory=dict)
    cache_price_per_1m: tuple[float, float] | None = None
    model_cache_prices: dict[str, tuple[float, float]] = field(default_factory=dict)


PROVIDERS = {
    spec.name: spec
    for spec in [
        ProviderSpec(
            "mock",
            "Aether Mock",
            "local",
            "",
            "",
            "mock",
            "mock-standard",
            "Free. Runs in-process; no network.",
            "No external limits. Intended for tests and demos.",
            ("mock-standard", "mock-tools", "mock-error"),
            docs="Built into Aether.",
            pricing_note="No external billing.",
            price_per_1m=(0.0, 0.0),
        ),
        ProviderSpec(
            "ollama",
            "Ollama (local)",
            "local",
            "http://127.0.0.1:11434/v1",
            "",
            "openai",
            "llama3.2:3b",
            "Free. Uses your own hardware and electricity.",
            "No provider quota; limited by local RAM and CPU/GPU.",
            ("llama3.2:3b", "qwen2.5:3b", "phi4-mini", "gemma3:4b"),
            docs="Install Ollama and run 'ollama pull llama3.2:3b'.",
            pricing_note="Uses local hardware; no provider bill.",
            price_per_1m=(0.0, 0.0),
        ),
        ProviderSpec(
            "lmstudio",
            "LM Studio (local)",
            "local",
            "http://127.0.0.1:1234/v1",
            "",
            "openai",
            "local-model",
            "Free. Uses your own hardware.",
            "No provider quota; limited by local resources.",
            ("local-model",),
            docs="Start the LM Studio local server.",
            pricing_note="Uses local hardware; no provider bill.",
            price_per_1m=(0.0, 0.0),
        ),
        ProviderSpec(
            "llamacpp",
            "llama.cpp server (local)",
            "local",
            "http://127.0.0.1:8080/v1",
            "",
            "openai",
            "local-model",
            "Free. Uses your own hardware.",
            "No provider quota; limited by local resources.",
            ("local-model",),
            docs="Start llama-server with --host 127.0.0.1 --port 8080.",
            pricing_note="Uses local hardware; no provider bill.",
            price_per_1m=(0.0, 0.0),
        ),
        ProviderSpec(
            "groq",
            "Groq",
            "free-tier",
            "https://api.groq.com/openai/v1",
            "GROQ_API_KEY",
            "openai",
            "llama-3.3-70b-versatile",
            "Free tier available; paid rates may apply above quota.",
            "Rate-limited per account and per model. Check your provider dashboard.",
            ("llama-3.3-70b-versatile", "llama-3.1-8b-instant"),
            docs="Create a free API key at https://console.groq.com/keys.",
        ),
        ProviderSpec(
            "cerebras",
            "Cerebras",
            "free-tier",
            "https://api.cerebras.ai/v1",
            "CEREBRAS_API_KEY",
            "openai",
            "llama-3.3-70b",
            "Free tier available; quota applies.",
            "Rate-limited per account. Check your provider dashboard.",
            ("llama-3.3-70b", "qwen-3-235b-a22b-instruct-2507"),
            docs="Create a free API key at https://cloud.cerebras.ai/.",
        ),
        ProviderSpec(
            "huggingface",
            "Hugging Face Router",
            "free-tier",
            "https://router.huggingface.co/v1",
            "HF_TOKEN",
            "openai",
            "Qwen/Qwen2.5-7B-Instruct",
            "Some models are free; others are billed to your account.",
            "Free inference is rate-limited and provider-dependent.",
            ("Qwen/Qwen2.5-7B-Instruct", "meta-llama/Llama-3.1-8B-Instruct"),
            docs="Use a Hugging Face token with inference permissions.",
        ),
        ProviderSpec(
            "gemini",
            "Google Gemini (OpenAI-compatible)",
            "free-tier",
            "https://generativelanguage.googleapis.com/v1beta/openai",
            "GEMINI_API_KEY",
            "openai",
            "gemini-2.5-flash",
            "Free tier available; paid tiers exist.",
            "Daily request and token limits vary by model and account.",
            ("gemini-2.5-flash", "gemini-2.5-pro"),
            docs="Create a key in Google AI Studio.",
        ),
        ProviderSpec(
            "openrouter",
            "OpenRouter",
            "mixed",
            "https://openrouter.ai/api/v1",
            "OPENROUTER_API_KEY",
            "openai",
            "meta-llama/llama-3.3-70b-instruct:free",
            "Free and paid models. IDs ending in :free are usually no-charge.",
            "Free models have per-minute and per-day limits and may change without notice.",
            ("meta-llama/llama-3.3-70b-instruct:free", "deepseek/deepseek-chat"),
            docs="Create a key at https://openrouter.ai/keys and review model pricing.",
            pricing_note="Model-dependent. Only listed :free IDs are treated as zero-cost.",
            model_prices={"meta-llama/llama-3.3-70b-instruct:free": (0.0, 0.0)},
        ),
        ProviderSpec(
            "openai",
            "OpenAI",
            "paid",
            "https://api.openai.com/v1",
            "OPENAI_API_KEY",
            "openai",
            "gpt-4o-mini",
            "Paid. Usage is billed by tokens.",
            "Subject to account limits and model availability.",
            ("gpt-4o-mini", "gpt-4o", "o4-mini"),
            docs="Create a key at https://platform.openai.com/api-keys.",
            pricing_note="Rough estimate for gpt-4o-mini standard text; verify current provider pricing.",
            model_prices={"gpt-4o-mini": (0.15, 0.60)},
            model_cache_prices={"gpt-4o-mini": (0.075, 0.15)},
        ),
        ProviderSpec(
            "anthropic",
            "Anthropic",
            "paid",
            "https://api.anthropic.com/v1",
            "ANTHROPIC_API_KEY",
            "anthropic",
            "claude-3-5-haiku-latest",
            "Paid. Usage is billed by tokens.",
            "Subject to account limits and model availability.",
            ("claude-3-5-haiku-latest", "claude-sonnet-4-5"),
            docs="Create a key at https://console.anthropic.com/settings/keys.",
            pricing_note="Rough estimate for Claude Haiku 3.5 standard text; verify current provider pricing.",
            model_prices={"claude-3-5-haiku-latest": (0.80, 4.00)},
            model_cache_prices={"claude-3-5-haiku-latest": (0.08, 1.00)},
        ),
        ProviderSpec(
            "custom",
            "Custom OpenAI-compatible endpoint",
            "custom",
            "",
            "AETHER_API_KEY",
            "openai",
            "local-model",
            "Depends entirely on the endpoint you configure.",
            "Depends on the provider; Aether cannot report external quotas.",
            (),
            requires_base_url=True,
            docs="Set base_url in config or AETHER_BASE_URL.",
        ),
    ]
}


def provider_spec(name: str) -> ProviderSpec | None:
    return PROVIDERS.get(name)


def provider_names() -> list[str]:
    return list(PROVIDERS)


def rough_cost(provider_name: str, model: str, usage: dict) -> float | None:
    spec = provider_spec(provider_name)
    if spec is None:
        return None
    if spec.model_prices:
        price = spec.model_prices.get(model)
        cache_price = spec.model_cache_prices.get(model) if spec.model_cache_prices else None
    else:
        price = spec.price_per_1m
        cache_price = spec.cache_price_per_1m
    if price is None:
        return None
    source = usage or {}
    prompt = int(source.get("prompt_tokens") or source.get("input_tokens") or 0)
    completion = int(source.get("completion_tokens") or source.get("output_tokens") or 0)
    details = source.get("prompt_tokens_details") or {}
    cached = int(details.get("cached_tokens") or source.get("cache_read_input_tokens") or 0)
    cache_write = int(source.get("cache_creation_input_tokens") or 0)
    if cache_price is None:
        return round((prompt * price[0] + completion * price[1]) / 1_000_000, 6)
    if "prompt_tokens" in source:
        prompt_total = prompt
    else:
        prompt_total = prompt + cached + cache_write
    base_prompt = max(0, prompt_total - cached - cache_write)
    total = base_prompt * price[0] + cached * cache_price[0] + cache_write * cache_price[1] + completion * price[1]
    return round(total / 1_000_000, 6)


def provider_is_billable(provider_name: str, model: str) -> bool:
    spec = provider_spec(provider_name)
    if spec is None:
        return True
    if spec.kind == "local" and not spec.model_prices:
        return False
    if spec.model_prices:
        price = spec.model_prices.get(model)
    else:
        price = spec.price_per_1m
    return price is None or price != (0.0, 0.0)
