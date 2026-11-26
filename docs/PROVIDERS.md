# Providers

Aether is provider-agnostic. Every backend is configured by a name in `config.json` plus optional per-provider settings.

## Cost classes

- `local`: no provider fee; uses your hardware. Example: `ollama`, `lmstudio`, `llamacpp`.
- `free-tier`: may be free within quota; paid usage may apply. Example: `groq`, `cerebras`, `huggingface`, `gemini`.
- `mixed`: free and paid models. Example: `openrouter`.
- `paid`: billed per token. Example: `openai`, `anthropic`.
- `custom`: entirely dependent on the endpoint you configure.

Aether reports these classes honestly but does not guarantee external pricing or quotas. Verify with the provider.

## Local providers

### Mock

No network. Intended for tests and screenshots.

```bash
aether --provider mock run "Say hello"
aether --provider mock --model mock-tools run "Use a tool"
```

### Ollama

```bash
ollama pull llama3.2:3b
aether --provider ollama --model llama3.2:3b run "Hello"
```

Default base URL: `http://127.0.0.1:11434/v1`.

### LM Studio / llama.cpp

Start your local OpenAI-compatible server, then:

```bash
aether --provider lmstudio --model local-model run "Hello"
aether --provider llamacpp --model local-model run "Hello"
```

## Hosted providers

Set a key in `~/.aether/.env` or your shell environment, then select the provider.

| Provider | Key env | Example model |
| --- | --- | --- |
| `groq` | `GROQ_API_KEY` | `llama-3.3-70b-versatile` |
| `cerebras` | `CEREBRAS_API_KEY` | `llama-3.3-70b` |
| `huggingface` | `HF_TOKEN` | `Qwen/Qwen2.5-7B-Instruct` |
| `gemini` | `GEMINI_API_KEY` | `gemini-2.5-flash` |
| `openrouter` | `OPENROUTER_API_KEY` | `meta-llama/llama-3.3-70b-instruct:free` |
| `openai` | `OPENAI_API_KEY` | `gpt-4o-mini` |
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-3-5-haiku-latest` |

For OpenRouter, IDs ending in `:free` are usually no-charge but rate-limited.

## Custom endpoint

```bash
aether config set providers.custom.base_url http://127.0.0.1:9000/v1
aether config set providers.custom.model my-model
aether --provider custom run "Hello"
```

If the endpoint needs a key, set `AETHER_API_KEY` or configure `providers.custom.key_env`.

## Fallback

```bash
aether config set fallback_providers '["lmstudio", "groq"]'
```

Failed providers receive local cooldowns; a later successful call clears the need for manual intervention. Aether never silently changes a free provider into a paid one; fallbacks are explicit in config and remain in the runtime chain. `aether models health` shows local health state and does not poll providers.

## Capability-aware routing

Aether can score configured candidates using deterministic task requirements and evidence-labeled capability facts. `routing.strategy` is `capability`, `cost`, or `fixed`; `prefer_local` and `avoid_models` refine selection, and `models.metadata` supplies user-known context windows and capabilities. Unknown prices are not free, and no capability is invented.

```bash
aether config set routing.strategy cost
aether config set routing.prefer_local true
aether config set routing.avoid_models '["openai"]'
aether models capabilities ollama qwen2.5-coder:7b
aether models routing "Debug this traceback"
aether models explain "Debug this traceback"
```

Explicit `--provider`/`--model` or `Agent(provider_name=..., model=...)` choices always win; there is no `routing.manual` setting. Diagnostics never call a model. `aether models benchmark [--samples N] [--confirm-billable]` is an offline deterministic routing simulation that prints JSON, writes no files, and makes no model/network/billable calls; `--confirm-billable` is acknowledgement only. See [MODEL_ROUTING.md](MODEL_ROUTING.md) and [CONFIGURATION.md](CONFIGURATION.md).

## Troubleshooting

For a copy-paste diagnostic flow for Ollama, LM Studio, and llama.cpp, see [Local provider troubleshooting](PROVIDER_TROUBLESHOOTING.md). It covers the offline mock-provider check, connection and model-ID errors, and safe redaction when reporting problems.
