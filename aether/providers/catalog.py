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
