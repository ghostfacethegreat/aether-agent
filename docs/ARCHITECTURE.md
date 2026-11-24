# Aether Architecture Audit and Target Design

## Scope and method

This document records the Milestone 1 audit of the upstream Hermes Agent repository:

- Upstream: <https://github.com/NousResearch/hermes-agent>
- Audited commit: `bb89ad1a feat(models): list Gemini 4 Carbon for Nous Portal and OpenRouter`
- Audit date: 2026-11-23
- Method: static source review of the full checkout (27,553 tracked files, ~437 MB), including entry points, core loop, provider catalog, tools, memory, skills, persistence, cron, delegation, CLI/TUI, gateway, tests, packaging, licensing, and security documentation. No upstream code was copied into Aether.

The audit distinguishes three things:

1. **Design ideas worth adopting** — concepts with clear value.
2. **Upstream-specific coupling** — code that assumes Nous Portal, hosted gateways, or paid provider accounts.
3. **Aether implementation** — independently written, smaller, dependency-light modules.

## Upstream map

### Entry points and common core

All hosts converge on one agent core:

- `hermes_cli/main.py` — CLI command tree and dispatch.
- `cli.py` — interactive terminal agent composed from mixins.
- `gateway/run.py` — messaging gateway runner.
- `acp_adapter/entry.py` — editor protocol adapter.
- `run_agent.py` — public Python facade (`AIAgent`, line 215).

`AIAgent.__init__` (run_agent.py:237) delegates to `agent/agent_init.py::init_agent` (line 2042). That initializer builds clients, fallback chains, tools, persistence, memory, skills, context engine, and usage tracking in a fixed order.

### One conversation turn

The upstream loop is deliberately phase-oriented rather than one monolithic function:

1. `agent/turn_facade.py::run_conversation` / `chat` (line 222) — durable lease admission and facade.
2. `agent/turn_context.py::build_turn_context` (line 1205) — copies caller history, appends user message, restores cached system prompt.
3. `agent/turn_iteration_prep.py::prepare_iteration` (line 144) — per-iteration state.
4. `agent/turn_request_assembly.py::assemble_api_request` (line 133) — decorated API copies; canonical messages stay undecorated.
5. `agent/turn_preflight_gate.py::run_preflight_gate` (line 20) — context pressure, compression, Ollama floors.
6. `agent/turn_api_call.py::perform_api_call` (line 72) — model invocation and middleware.
7. `agent/turn_response_intake.py::normalize_model_response` (line 170) and `turn_response_check.py::check_api_response` (line 93).
8. `agent/turn_tool_round.py::run_tool_round` (line 50) and `agent/tool_executor.py` — tool dispatch, including segmented parallel batches.
9. `agent/turn_final_response.py::finish_text_response` (line 106) or `turn_api_error.py::handle_api_error` (line 53).
10. `agent/turn_finalizer.py::finalize_turn` (line 649) — persistence, trajectory save, hooks, compaction.

Each phase returns a small verdict object with an action (`continue`, `break`, `return`) whose fields are copied back into `_LoopState` (`agent/conversation_loop.py:1433`). This is a useful testability pattern: phase logic can be unit tested without the full host.

### Providers and transports

Provider profiles live in `plugins/model-providers/` and are merged by `providers/__init__.py` with user plugins; user plugins can override bundled ones. `hermes_cli/provider_catalog.py:65` unifies CLI, TUI, and desktop views. `hermes_cli/runtime_provider.py::resolve_runtime_provider` (line 1215) resolves credentials, endpoints, and API modes with a long precedence ladder.

Transport normalization is in `agent/transports/`:

- `chat_completions.py::ChatCompletionsTransport` (line 530)
- `anthropic.py::AnthropicTransport` (line 33)
- `codex.py::ResponsesApiTransport` (line 642)
- `bedrock.py`

`ProviderTransport` (`agent/transports/base.py:12`) converts messages/tools, builds kwargs, normalizes responses, maps finish reasons, and extracts cache stats. Streaming is implemented in `agent/chat_completion_helpers.py` with a single-writer delivery fence in `agent/stream_delivery.py:298`.

Free tier: upstream supports an anonymous Nous welcome tier (`hermes_cli/anon_auth.py`) with a once-per-OS-user client-side claim (`welcome_trial.py:1`), plus free model listings through OpenRouter and other providers. Those paths are optional in code but prominent in onboarding. Aether must not depend on them.

### Tools, memory, skills, persistence

- Tool discovery: `tools/registry.py::discover_builtin_tools` (line 121); `ToolEntry` at line 215; `ToolRegistry.register` at line 840.
- Tool schemas and dispatch: `model_tools.py::get_tool_definitions` (line 225), `handle_function_call` (line 906).
- Approval gates: `tools/approval.py::check_dangerous_command` (line 1336), `request_tool_approval` (line 1372), `check_all_command_guards` (line 1402). Commands that cannot be safely scanned block when no human reviewer is present. Non-interactive contexts fail closed for escalated tool approvals.
- Built-ins include `terminal_tool.py`, `file_tools.py`, `file_operations.py`, `git_*`, `web_tools.py`, `browser_tool.py`, `delegate_tool.py`, `memory_tool.py`, and `skills_tool.py`.
- Memory: `MEMORY.md` and `USER.md` flat files (`tools/memory_tool_store.py`) with a frozen system-prompt snapshot and optional external providers (`agent/memory_provider.py`).
- Skills: progressive disclosure via `skills_list()` and `skill_view()` (`tools/skills_tool.py:305`, `:634`), `SKILL.md` discovery across roots (`agent/skill_utils.py:413`), editing/creation (`tools/skill_manager_tool.py`), security scanning (`tools/skills_guard.py`), and usage/curation sidecars.
- Persistence: one profile → one `state.db` through a single façade (`persistence_assembly.py:204`). SQLite DDL in `persistence/sqlite/_schema_ddl.py:116`. FTS search, lineage, leases, delegation ledgers, and resumable subagents are layered on top.
- Cron: `cron/jobs.py` (`create_job` at line 1775), `cron/scheduler.py::run_job` (line 2503), auditable `executions.db` (`cron/executions.py`), and at-most-once `deliveries.db` (`cron/delivery_queue.py`).
- Subagents: `tools/delegate_tool.py::delegate_task` (line 613) builds fresh child agents, with sync/background dispatch (`delegate_tool_dispatch.py`), context isolation (`agent/delegation_context.py`), and resumable records (`tools/delegate_tool_resumable.py`).

### CLI, TUI, gateway, install

- CLI: ~70 built-in subcommands (`hermes_cli/main.py:2538`), lazy parser modules under `hermes_cli/subcommands/`, and a restricted console engine (`hermes_cli/console_engine.py`).
- TUI: React 19 + Ink TypeScript (`ui-tui/README.md`) talking JSON-RPC over stdio to `tui_gateway/entry.py`. This brings a large Node dependency tree.
- Gateway: plugin adapter registry (`gateway/platform_registry.py`) with ~27 bundled platform adapters under `plugins/platforms/` and heavy optional SDK extras in `pyproject.toml:270+`.
- Install: shell/PowerShell scripts with pinned, SHA-verified uv; install intentionally avoids pip/PyPI (`setup.py:2` blocks wheels/sdists outside Nix). Update/uninstall/doctor commands are extensive.
- Tests: pytest for Python (thousands of tests), Vitest/Playwright for JS, cargo tests for Rust; canonical runner isolates each test file (`scripts/run_tests.sh`).
- License: MIT, Copyright 2025 Nous Research (`LICENSE:1-3`). Some bundled plugins/skills carry separate MIT or Apache 2.0 notices.

## What Aether adopts and what it deliberately does not

### Adopted concepts

- Narrow core with capability at the edges.
- Phase-oriented turn loop with explicit verdicts and bounded iterations.
- Stable system-prompt prefix and frozen memory snapshot for caching discipline.
- Tool registry with JSON schemas, explicit risk metadata, and deterministic validation.
- Approval gate for destructive operations; fail closed when no reviewer exists.
- Local-first persistence with a single storage façade.
- Progressive skill disclosure (list names/descriptions, load full skill on demand).
- Durable task history and recoverable subagents.
- Transparent model catalog with cost/free-tier annotations.

### Not adopted

- Nous Portal device-code auth, anonymous guest minting, entitlement checks, and hosted inference routes.
- Gateway canonical-session RPC and 27 messaging adapters. Aether's first release is local CLI-first; gateway integrations are optional adapters behind explicit config.
- React/Ink TUI and Electron desktop stack. Aether uses a Python terminal dashboard with ANSI styling and no Node runtime requirement.
- Provider plugin override of built-ins by default. Aether requires explicit operator opt-in for any third-party provider/tool extension.
- `max_iterations=sys.maxsize` default from upstream `run_agent.py`; Aether defaults to a bounded 12 iterations.

## Compatibility and risk findings

| Finding | Upstream location | Aether response |
|---|---|---|
| Nous anonymous free tier is client-side enforced and once per OS user | `hermes_cli/welcome_trial.py:1-14`, `anon_auth.py` | No dependency. Aether defaults to local inference. |
| Provider plugins can override bundled provider profiles | `providers/__init__.py:241-265` | Explicit config opt-in; unknown providers are generic OpenAI-compatible. |
| `_DISK_TTL_SECONDS` referenced but not defined in router plugin | `plugins/model-providers/router/__init__.py:175,229` | Not copied; Aether has no equivalent path. |
| Host-derived API key inference from lookalike hostnames | `hermes_cli/runtime_provider.py:426` | Keys are only read from the env var explicitly configured for a provider. |
| `extra_headers` may contain credentials and must not be logged | `hermes_cli/config_providers.py:276` | Header values are redacted in all logs and diagnostics. |
| Custom endpoint model listings are soft-accepted | `hermes_cli/models_validate.py:358-393` | Aether reports unverified model IDs in `doctor`; never claims a model exists. |
| Upstream security docs: OS isolation is the only real boundary against adversarial model output | `SECURITY.md:58-65` | Aether repeats this in `SECURITY.md`; permissions are guardrails, not a sandbox. |
| Python 3.14-only reality vs `>=3.11` packaging claim | `pyproject.toml:15` vs `CONTRIBUTING.md:115` | Aether supports Python 3.11+ with stdlib-only core; tested on 3.14. |
| Heavy startup deps (openai, httpx, pydantic, rich, prompt_toolkit, YAML, more) | `pyproject.toml:40-80` | Aether core dependencies: Python standard library only. |

## Aether target architecture

```text
CLI / stdin                         scripts/install.sh
    |                                      |
    v                                      v
aether.cli.app  ---> aether.core.agent <-- aether.config
    |                    |     |      \
    |                    |     |       \--> aether.core.loop (turn state machine)
    |                    |     |--> aether.core.context (budget + summary)
    |                    |----------> aether.providers.registry
    |                                  |--> local: ollama, lmstudio, llama.cpp
    |                                  |--> free-tier optional: groq, cerebras, HF, Gemini
    |                                  |--> paid optional: OpenAI, Anthropic, OpenRouter
    |                                  `--> generic OpenAI-compatible endpoint
    |--> aether.tools.executor ---> aether.tools.registry ---> built-in tools
    |--> aether.memory.store (MEMORY.md / USER.md + SQLite FTS)
    |--> aether.skills.engine (SKILL.md progressive disclosure)
    |--> aether.tasks.subagents (ThreadPoolExecutor + task ledger)
    |--> aether.orchestration (roles, shared state, dependency plans, task recovery)
    |--> aether.tasks.scheduler (>=30s interval jobs)
     `--> aether.persistence.store (SQLite: sessions, messages, tasks, usage)
```

### Multi-agent orchestration flow

1. `Agent` constructs an `Orchestrator` with the parent config, store, shared spend budget, and cancellation event.
2. The orchestrator resolves role settings from `orchestrator.roles` and builds a task graph from explicit roles or objective heuristics.
3. Ready tasks run in a bounded `ThreadPoolExecutor`; `mode=sequential` forces one worker and `mode=parallel` uses `orchestrator.max_concurrency`.
4. Each child agent receives a narrowed permission policy, inherited budget limit, cancellation event, role prompt, and only its role's tools. Children cannot call `orchestrate_task` or `delegate_task`.
5. Structured child results are published to owner-protected task records in `SharedTaskState`; dependent agents receive those results as explicitly untrusted context.
6. Retries, timeouts, cancellations, artifacts, usage, and tool logs are persisted through the existing SQLite task ledger.
7. The final report consolidates summaries, sources, failures, token totals, and estimated cost.

### Data flow for one Aether turn


1. CLI renders a compact dashboard and passes user text to `Agent.run_turn`.
2. Turn context loads durable memory, skill index, and recent transcript.
3. The loop asks the active provider for a streaming response with tool schemas.
4. Text deltas are rendered immediately; tool calls are validated against the permission policy.
5. Approved tools run synchronously (parallel only for explicitly safe read-only tools) with a hard timeout.
6. Tool results are appended as role=`tool` messages and the loop continues, bounded by `max_iterations`.
7. On retryable provider errors, the loop switches to the next configured fallback and rebuilds the request.
8. Final text, usage, tool log, and state are persisted atomically in SQLite.

### Storage contract

All local state is under `AETHER_HOME` (default `~/.aether`):

```text
config.json          user configuration (no secrets)
.env                 optional API keys, mode 0600, never committed
state.db             sessions, messages, tasks, usage
memories/MEMORY.md   agent notes
memories/USER.md     user preferences
skills/              user skills (SKILL.md)
cron/jobs.json       scheduled jobs
cron/executions.jsonl local scheduler execution ledger
logs/aether.log      rotating local log
```

Secrets are read from environment variables or `.env` at runtime. They are never written to `config.json`, logs, diagnostics output, or screenshots.

## Performance targets (8 GB Apple Silicon)

- Cold start to first prompt: < 1 s with stdlib imports only.
- Resident set before model call: < 60 MB.
- No background daemons unless scheduling is explicitly enabled.
- Streaming is single-writer; no terminal output corruption.
- Tool results are capped (default 16 KiB each) before entering context.
- Context compression triggers at 75% of configured context size by default.

## Verification strategy

- `python3 -m unittest discover -s tests -v` — all tests use stdlib `unittest` and a deterministic mock provider.
- `scripts/check.sh` — compile check, secret scan, test suite, CLI smoke test.
- `aether doctor` — user-facing diagnostics (Python, home layout, provider connectivity, tool availability, config validity).
- Screenshots are generated from a real CLI run against the built-in mock provider and labelled as such.

## Phase 2 architecture refresh

The original audit above remains the Milestone 1 record at upstream commit `bb89ad1a`. Phase 2 refreshed the upstream checkout to `b98c388a880b1b6fd303c9c2821a3946651a0b4c` and compared it against Aether commit `bdbe2462dda3c4646086385d600b4e2ab23f4957`.

The detailed 14-area comparison is in [PHASE2_FEATURE_COMPARISON.md](PHASE2_FEATURE_COMPARISON.md). The implementation order is in [PHASE2_ROADMAP.md](PHASE2_ROADMAP.md). M2.1 addressed durable tool-call replay and context role repair; M2.2 addressed tool timeout, URL, redaction, and path-scope hardening; M2.3 made scheduler ticks execute real local prompts with claims and an execution ledger. Provider cost enforcement added cached-token pricing, billability gating, shared budgets, and honest cost reporting. Phase 3 added the dependency-aware orchestrator described above.
