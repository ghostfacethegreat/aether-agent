# Feature Matrix

Legend for Aether status:

- **Done** — implemented and covered by at least one automated test.
- **Partial** — usable baseline with documented limits.
- **Planned** — not implemented yet at the time this table was written.
- **N/A** — deliberately out of scope for Aether's local-first design.

Upstream columns describe what exists in the audited Hermes commit; they are not claims that every path is free or bug-free.

## AI core

| Capability | Upstream Hermes | Aether | Notes |
|---|---|---|---|
| Multi-provider model support | Extensive profile/plugin catalog | Done | Local, free-tier optional, paid optional, generic OpenAI-compatible. |
| Local inference | Ollama, LM Studio, llama.cpp, managed local | Done | Ollama, LM Studio, llama.cpp OpenAI-compatible endpoints. |
| Free model integrations | Nous free tier, OpenRouter free models, many vendor free tiers | Done | Groq, Cerebras, Hugging Face Router, Gemini, OpenRouter `:free` IDs; all optional and rate-limited by their operators. |
| Custom OpenAI-compatible endpoint | `providers:` / `custom_providers:` config | Done | `aether config set provider custom ... base_url ...`. |
| Model switching without restart | `/model` picker and host APIs | Done | In-chat `/model` and `/provider` commands rebuild the provider in place. |
| Streaming responses | SSE with interrupt/single-writer fence | Done | urllib SSE parser, delta callback, single writer. |
| Conversation context management | Prompt tiers, preflight compression, cache planning | Partial | Stable prompt prefix, token estimate, summary/truncate strategy. No provider prompt-cache breakpoints yet. |
| Reasoning / planning modes | Reasoning params, trust gates, planning prompts | Partial | `reasoning_effort` forwarding, `/plan` mode, `todo` tool. Model must support reasoning. |
| Reliable tool calling | Schema repair, retries, role alternation repair | Done | Strict JSON validation, unknown-tool repair message, role alternation preserved. |
| Provider fallback and error recovery | Credential pools, cooldowns, fallback chain | Done | Ordered fallback with retryable classification and cooldown per provider. |
| Cost and limit transparency | Catalog pricing, usage guards, account usage | Partial | Every provider has a cost annotation in `aether providers`; per-turn estimated cost shown when a price is known. No account-balance scraping. |

## Agent system

| Capability | Upstream Hermes | Aether | Notes |
|---|---|---|---|
| Autonomous task planning | Multi-step loop, todo tool | Done | Bounded iterative loop with visible task list. |
| Multi-step execution | Phase-oriented loop | Done | Up to `max_iterations` tool rounds per turn. |
| Subagents | Durable delegate tool with resumable children | Done | Parallel sync subagents with isolated history and reduced toolset; resumable ledger planned extension. |
| File read/write/edit | Rich file tools with guards | Done | `read_file`, `write_file`, `edit_file`, `list_directory`. |
| Terminal execution | Sandboxed/backed terminal tool | Done | `terminal` with timeout, output cap, approval for destructive commands. Not a sandbox. |
| Git integration | Several git helpers | Done | `git status/diff/log/add/commit` through one tool; commit requires approval. |
| Web research | Exa/Firecrawl/Parallel plus fetch | Partial |Key-free `web_fetch` and DuckDuckGo HTML `web_search`; optional paid keys supported but not required. |
| Browser automation | Local CDP, cloud Browserbase, desktop control | Partial | Configurable `browser` command template; no bundled browser runtime. Disabled by default. |
| Code generation / debugging | Full coding agent | Done | Tool-driven editing plus built-in `debug` and `code-review` skills. |
| Task history and recovery | Durable sessions, delegation ledgers | Done | SQLite `tasks` table with `/tasks` and `/resume`. |

## Memory and learning

| Capability | Upstream Hermes | Aether | Notes |
|---|---|---|---|
| Persistent conversation memory | SQLite sessions | Done | SQLite sessions and messages. |
| Long-term user preferences | `USER.md` | Done | Editable `USER.md` surfaced to the system prompt. |
| Searchable conversation history | SQLite FTS | Done | FTS5 when available, substring fallback. |
| Editable memory | Memory tool and files | Done | Tool actions plus direct file editing. |
| Skills created and improved | Skill manager, curator, hub | Done | `skill` tool create/edit/view/list with usage tracking. No cloud hub. |
| Memory import/export | Admin export/import | Done | JSON export/import via `memory export|import`. |
| Local storage by default | `~/.hermes` | Done | `~/.aether`, overridable with `AETHER_HOME`. |

## Customization

| Capability | Upstream Hermes | Aether | Notes |
|---|---|---|---|
| Custom system prompts | SOUL.md, prompt fragments, config | Done | `system_prompt` config appended to personality. |
| Configurable personality | SOUL.md | Done | `personality` config. |
| Custom model selection | Model picker | Done | Config plus `/model`. |
| Tool permissions | Approval config, policy layers | Done | `standard`, `strict`, `local-dev` modes with explicit approval for destructive operations. |
| Optional unrestricted local-dev mode | YOLO mode, approvals off | Partial | `local-dev` relaxes non-destructive checks only; destructive operations still require approval. No model-level restriction removal is claimed. |
| Explicit destructive approval | Approval gate | Done | Terminal/git/write risk classification and fail-closed non-interactive mode. |
| Easy integration config | Many provider/env knobs | Done | Config file, `.env` example, `aether doctor`. |

## Interface

| Capability | Upstream Hermes | Aether | Notes |
|---|---|---|---|
| Clean terminal dashboard | Rich CLI and Ink TUI | Done | ANSI dashboard with provider/model/session/cost/status. |
| Streaming output | Rich stream renderer | Done | Token deltas printed as received. |
| Colored status indicators | Rich/Ink | Done | ANSI colors with `NO_COLOR` support. |
| Model and provider info | Status bars | Done | Dashboard and `/status`. |
| Tool execution logs | Tool progress events | Done | Colored `[tool]` lines with duration and result size. |
| Loading animations | Ink spinners | Done | Braille spinner while waiting for first token. |
| Command autocomplete | Ink prompt | Done | `readline` completer for slash commands. |
| Conversation history | Session search | Done | `/history` plus SQLite-backed sessions. |
| Clear error messages | Extensive classifier | Done | Typed errors with actionable remediation. |
| Graphical interface | Desktop/Electron/web dashboard | N/A | Omitted to keep core lean and free. |

## Installation and release

| Capability | Upstream Hermes | Aether | Notes |
|---|---|---|---|
| One-command installer | Hosted shell installer | Done | `scripts/install.sh`; public `curl` command withheld until hosted URL is tested. |
| Dependency checks | PM + doctor | Done | Installer checks macOS/arch/Python/git; `aether doctor` checks runtime. |
| Apple Silicon | Supported | Done | Native Python, universal shell scripts, no compiled deps. |
| Isolated dependencies | PM-managed venv | Done | Dedicated venv under `AETHER_HOME/venv`. |
| Configuration setup | Interactive setup | Done | First-run config generation and `aether setup`. |
| Clear installation errors | Extensive installer | Done | Fail-fast with descriptive messages and nonzero exit. |
| Uninstall | `hermes uninstall` | Done | `scripts/uninstall.sh` with optional `--data`. |
| Update | `hermes update` | Done | `aether update` runs git pull and reinstall. |
| Diagnostics | `hermes doctor` | Done | `aether doctor`. |
| MIT license + upstream attribution | MIT, Nous Research | Done | Root MIT license plus NOTICE and upstream license copy. |

## Paid-service exposure

| Feature | Requires paid account? | Aether behavior |
|---|---|---|
| Local inference (Ollama/LM Studio/llama.cpp) | No | Default recommendation. No account, no network. |
| Mock provider | No | Built in for tests and demos. |
| Groq / Cerebras / Gemini / Hugging Face free tiers | No, but account + quotas usually required | Optional. Quotas and data policies are the operator's responsibility and are shown in `aether providers`. |
| OpenRouter | Free models exist; many models paid | Optional key. Free IDs use `:free`; cost note shown. |
| OpenAI / Anthropic / xAI-compatible | Yes for most models | Optional. Explicitly labelled paid. |
| Web search fallback | No key, but rate-limited | Best-effort DuckDuckGo HTML; may fail without notice. Use a paid search API only if configured. |
| Browser automation provider | Depends on provider | Disabled unless a command template is configured. |
| Messaging gateways | Depends on platform | Planned optional adapters; core does not require them. |
