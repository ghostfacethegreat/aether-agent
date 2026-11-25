# Feature Matrix

Legend for Aether status:

- **Done** — implemented and covered by at least one automated test or local smoke check.
- **Partial** — usable baseline with documented limits.
- **Planned** — not implemented yet at the time this table was written.
- **N/A** — deliberately out of scope for Aether's local-first design.

Upstream columns describe what exists in the audited Hermes commit; they are not claims that every path is free or bug-free.

## Intelligence and agent execution

| Capability | AETHER status on parity-foundation branch | Notes |
|---|---|---|
| Repository context files | Implemented baseline | Bounded workspace-root AGENTS.md-compatible context; no recursion, symlinks, or network fetches. |
| Dynamic specialist planning | Implemented baseline | Dependency-aware planner/researcher/architect/developer/tester/verifier/reviewer chain, with debugging, documentation, and security variants. |
| Structured role contracts | Implemented baseline | Deterministic required-field/type/enum checks; strict validation for other specialist roles is opt-in. |
| Independent verification | Implemented bounded baseline | Requires verifier's own successful recognized test/check command in terminal log; not formal proof or task-quality benchmark. |
| Parallel agent profiles | Prepared | Four custom Copilot profiles and workstream instructions are included; they do not start automatically. |
| Task-quality evaluation | Planned | CI and unit checks are added on this branch; no comparable live-model task-quality benchmark is claimed. |

## Intelligence and agent execution

| Capability | AETHER status on parity-foundation branch | Notes |
|---|---|---|
| Repository context files | Implemented baseline | Bounded workspace-root AGENTS.md-compatible context; no recursion, symlinks, or network fetches. |
| Dynamic specialist planning | Implemented baseline | Dependency-aware planner/researcher/architect/developer/tester/verifier/reviewer chain, with debugging, documentation, and security variants. |
| Structured role contracts | Implemented baseline | Deterministic required-field/type/enum checks; strict validation for other specialist roles is opt-in. |
| Independent verification | Implemented bounded baseline | Requires verifier's own successful recognized test/check command in terminal log; not formal proof or task-quality benchmark. |
| Parallel agent profiles | Prepared | Four custom Copilot profiles and workstream instructions are included; they do not start automatically. |
| Task-quality evaluation | Planned | CI and unit checks are added on this branch; no comparable live-model task-quality benchmark is claimed. |

## AI core

| Capability | Upstream Hermes | Aether | Notes |
|---|---|---|---|
| Multi-provider model support | Extensive profile/plugin catalog | Done | Local, free-tier optional, paid optional, generic OpenAI-compatible. |
| Local inference | Ollama, LM Studio, llama.cpp, managed local | Done | Ollama, LM Studio, llama.cpp OpenAI-compatible endpoints. |
| Free model integrations | Nous free tier, OpenRouter free models, many vendor free tiers | Done | Groq, Cerebras, Hugging Face Router, Gemini, OpenRouter `:free` IDs; all optional and rate-limited by their operators. |
| Custom OpenAI-compatible endpoint | `providers:` / `custom_providers:` config | Done | `aether config set providers.custom.base_url ...`; requires `base_url`. |
| Model switching without restart | `/model` picker and host APIs | Done | In-chat `/model` and `/provider` commands rebuild the provider in place. Switching resets to the new provider's default model. |
| Streaming responses | SSE with interrupt/single-writer fence | Partial | urllib SSE parsers, delta callback, synthetic SSE accumulation test; live provider streams not exercised. |
| Conversation context management | Prompt tiers, preflight compression, cache planning | Partial | Prompt is rebuilt each turn from current files; token estimate, summary/truncate strategy, and M2.1 role-alternation repair exist. No frozen snapshot or provider cache breakpoints yet. |
| Reasoning / planning modes | Reasoning params, trust gates, planning prompts | Partial | `reasoning_effort` forwarding, `/plan` mode, `todo` tool. Model must support reasoning. |
| Reliable tool calling | Schema repair, retries, role alternation repair | Partial | Required-key validation, unknown-tool error message, ordered parallel results, M2.1 role-alternation repair, and M2.2 executor-level timeouts. No full JSON Schema validation yet. |
| Provider fallback and error recovery | Credential pools, cooldowns, fallback chain | Done | Ordered fallback with retryable classification and cooldown per provider. |
| Capability-aware model routing | Provider routing and fallback providers | Done | Evidence-aware capability facts, deterministic classifier, scored `capability`/`cost`/`fixed` strategies, explicit provider/model authority, health cooldowns, and offline diagnostics; benchmark is a deterministic routing simulation, not task-quality evidence. |
| Cost and limit transparency | Catalog pricing, usage guards, account usage | Partial | Every provider has a cost annotation in `aether providers`; no per-turn dollar estimate or account-balance scraping. |

## Agent system

| Capability | Upstream Hermes | Aether | Notes |
|---|---|---|---|
| Autonomous task planning | Multi-step loop, todo tool | Done | Bounded iterative loop with visible task list. |
| Multi-step execution | Phase-oriented loop | Done | Up to `max_iterations` tool rounds per turn. |
| Subagents | Durable delegate tool with resumable children | Partial | Parallel sync subagents with isolated history and reduced toolset. Task-ledger integration, durable resume, steer/stop, output schemas, and CLI resume are incomplete. |
| File read/write/edit | Rich file tools with guards | Done | `read_file`, `write_file`, `edit_file`, `list_directory`. |
| Terminal execution | Sandboxed/backed terminal tool | Done | `terminal` with timeout, output cap, approval for destructive commands. Not a sandbox. |
| Git integration | Several git helpers | Done | `git status/diff/log/add/commit` through one tool; git actions require approval by default. |
| Web research | Exa/Firecrawl/Parallel plus fetch | Partial | Key-free `web_fetch` and DuckDuckGo HTML `web_search`; optional paid keys supported but not required. M2.2 rejects private URL targets and unsafe redirects. |
| Browser automation | Local CDP, cloud Browserbase, desktop control | Partial | Configurable `browser` command template; no bundled browser runtime. Disabled by default. |
| Code generation / debugging | Full coding agent | Done | Tool-driven editing plus built-in `debug` and `code-review` skills. |
| Task history and recovery | Durable sessions, delegation ledgers | Done | SQLite `tasks` table with `/tasks` and in-chat `/resume`; M2.1 preserves assistant tool calls and tool result IDs across reload. |
| Local scheduling | Cron jobs with delivery and audit logs | Partial | M2.3 executes due prompts in-process, claims jobs before runs, records `cron/executions.jsonl`, reports due/executed/skipped/failed, and supports update/pause/resume/cancel. No daemon, delivery targets, or cron syntax. |

## Memory and learning

| Capability | Upstream Hermes | Aether | Notes |
|---|---|---|---|
| Persistent conversation memory | SQLite sessions | Done | SQLite sessions and messages. |
| Long-term user preferences | `USER.md` | Done | Editable `USER.md` surfaced to the system prompt. |
| Searchable conversation history | SQLite FTS | Done | FTS5 when available, substring fallback. |
| Editable memory | Memory tool and files | Done | Tool actions plus direct file editing. |
| Skills created and improved | Skill manager, curator, hub | Partial | `skill` tool create/edit/view/list with usage counts. No deterministic curator, rollback, background review, or cloud hub. |
| Memory import/export | Admin export/import | Done | JSON export/import via `memory export|import`. |
| Local storage by default | `~/.hermes` | Done | `~/.aether`, overridable with `AETHER_HOME`. |

## Customization

| Capability | Upstream Hermes | Aether | Notes |
|---|---|---|---|
| Custom system prompts | SOUL.md, prompt fragments, config | Done | `system_prompt` config appended to personality. |
| Configurable personality | SOUL.md | Done | `personality` config. |
| Custom model selection | Model picker | Done | Config plus `/model`. |
| Tool permissions | Approval config, policy layers | Done | `standard`, `strict`, `local-dev` modes with explicit approval for risky tools. |
| Optional unrestricted local-dev mode | YOLO mode, approvals off | Partial | `local-dev` relaxes non-destructive checks only; destructive operations still require approval. No model-level restriction removal is claimed. |
| Explicit destructive approval | Approval gate | Done | Terminal/git/write risk classification and fail-closed non-interactive mode. |
| Easy integration config | Many provider/env knobs | Done | Config file, `.env` loading, `aether doctor`, provider/config guides. |

## Interface

| Capability | Upstream Hermes | Aether | Notes |
|---|---|---|---|
| Clean terminal dashboard | Rich CLI and Ink TUI | Done | ANSI dashboard via `aether status` and `/status`. |
| Streaming output | Rich stream renderer | Done | Token deltas printed as received. |
| Colored status indicators | Rich/Ink | Partial | ANSI colors with `NO_COLOR` support; not unit-tested individually. |
| Model and provider info | Status bars | Done | Dashboard, `/status`, and `aether providers`. |
| Tool execution logs | Tool progress events | Done | Colored `[tool]` lines with duration or error. |
| Loading animations | Ink spinners | Partial | Braille spinner while waiting for first token; not unit-tested. |
| Command autocomplete | Ink prompt | Partial | `readline` completer for slash commands; not unit-tested. |
| Conversation history | Session search | Done | `/history` plus SQLite-backed sessions. |
| Clear error messages | Extensive classifier | Done | Typed errors with actionable remediation. |
| Graphical interface | Desktop/Electron/web dashboard | N/A | Omitted to keep core lean and free. |

## Installation and release

| Capability | Upstream Hermes | Aether | Notes |
|---|---|---|---|
| One-command installer | Hosted shell installer | Partial | `scripts/install.sh` exists and passed a local git-remote install test; no hosted URL published. |
| Dependency checks | PM + doctor | Partial | Installer checks Python; `aether doctor` checks runtime, config, state DB, and binaries. |
| Apple Silicon | Supported | Partial | Tested on a macOS environment; no CI matrix. |
| Isolated dependencies | PM-managed venv | Done | Installer creates `AETHER_HOME/venv`; Aether has no third-party runtime dependencies. |
| Configuration setup | Interactive setup | Done | First-run config generation and `aether setup`. |
| Clear installation errors | Extensive installer | Partial | Fail-fast messages exist; not unit-tested. |
| Uninstall | `hermes uninstall` | Partial | `scripts/uninstall.sh` removes wrapper and venv; `--data` deletion is interactive and not unit-tested. |
| Update | `hermes update` | Partial | `aether update` runs git pull and editable install; not network-tested. |
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

## Phase 2 audit note

The four-status table above is a quick summary. The authoritative source-level comparison is [PHASE2_FEATURE_COMPARISON.md](PHASE2_FEATURE_COMPARISON.md), and the staged gap work is in [PHASE2_ROADMAP.md](PHASE2_ROADMAP.md). A `Done` status here means implemented and locally checked within Aether's narrower scope, not Hermes parity.
