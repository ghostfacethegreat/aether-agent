# Phase E Architecture Audit

Phase E adds capability-aware model routing without replacing Aether's provider architecture. This document records the audited baseline, compatibility requirements, and extension points. The audit checkpoint itself changed no runtime behavior; the implementation described by the extension design is now implemented on this feature branch and locally verified, but not released.

## Implementation status

Phase E is implemented on this feature branch; implementation is committed separately from documentation. Local verification: 26 focused tests pass with `python3 -W ignore::ResourceWarning -m unittest tests.test_model_routing -q`, and 179 tests pass with `python3 -W ignore::ResourceWarning -m unittest discover -s tests -q`. `bash scripts/check.sh && bash scripts/test_install.sh` passed with 3 cold starts, median wall time `0.114s`, peak child RSS `34.4 MiB`, and a local git-remote install test pass. `python3 scripts/benchmark.py` recorded 3 cold starts, median wall time `0.112s`, and peak child RSS `34.9 MiB`. `git diff --check` passed. `ResourceWarning` notices for unclosed SQLite connections are non-failing; no lint/typecheck command is configured, so none is claimed. Version remains `0.1.0`; no `0.2.x` release or tag exists.

Implementation files: [../aether/routing/capabilities.py](../aether/routing/capabilities.py), [../aether/routing/classifier.py](../aether/routing/classifier.py), [../aether/routing/router.py](../aether/routing/router.py), [../aether/core/context.py](../aether/core/context.py), [../aether/core/loop.py](../aether/core/loop.py), [../aether/core/agent.py](../aether/core/agent.py), [../aether/persistence/store.py](../aether/persistence/store.py), [../aether/learning/engine.py](../aether/learning/engine.py), [../aether/providers/registry.py](../aether/providers/registry.py), [../aether/config.py](../aether/config.py), [../aether/orchestration/roles.py](../aether/orchestration/roles.py), [../aether/orchestration/orchestrator.py](../aether/orchestration/orchestrator.py), [../aether/cli/app.py](../aether/cli/app.py), [../benchmarks/model_routing/runner.py](../benchmarks/model_routing/runner.py), and [../tests/test_model_routing.py](../tests/test_model_routing.py).

## Baseline

| Item | Value |
|---|---|
| Branch | `feat/aether-020-intelligence-foundation` |
| Implementation checkpoint | `0dc4118af627cb2c5de4daac0a8ed4e3512705cf` |
| Documentation checkpoint | `42dcf4fd9b5f461ba52263b8a2f1f8b6f0117d2b` |
| Tests before Phase E | 153 passing |
| Startup median | `0.108s` |
| Peak RSS | `34.1 MiB` |
| Version | `0.1.0` alpha |
| Publication | no push, pull request, merge, tag, or release |

The startup benchmark measures cold start time and memory only. It is not a task-quality result. No Aether/Hermes parity or superiority claim is permitted.

## Existing model infrastructure

### Provider catalog and construction

- `aether/providers/catalog.py` defines frozen `ProviderSpec` records for `mock`, `ollama`, `lmstudio`, `llamacpp`, `groq`, `cerebras`, `huggingface`, `gemini`, `openrouter`, `openai`, `anthropic`, and `custom`.
- `ProviderSpec` already carries provider kind, base URL, API key environment variable, API mode, default model, cost notes, limits, sample models, base/model prices, cached-token prices, docs, and pricing notes.
- `rough_cost()` understands OpenAI prompt/completion and cached-token usage plus Anthropic input/output/cache usage. Unknown model prices return `None`; this must remain fail-closed.
- `provider_is_billable()` treats unknown providers as billable and local specs without prices as non-billable. Free-tier hosted specs are conservatively billable unless explicitly priced otherwise.
- `aether/providers/registry.py::build_provider()` resolves base URL, credentials, model, and transport. Unknown provider names become custom OpenAI-compatible providers and still require a base URL.
- `ProviderManager` owns the active provider, model, configured fallback list, cooldowns, candidates, and active-provider description.

### Provider contracts

- `aether/providers/base.py` defines `ToolCall`, `ModelResponse`, and `BaseProvider.chat()`.
- OpenAI-compatible and Anthropic transports implement streaming, tool calls, usage normalization, retries for rate limits and transient server errors, authentication errors, redacted error reporting, and provider descriptions that expose only credential presence.
- `MockProvider` supports scripted responses, scripted failures, streaming, and deterministic tool usage tests.
- Provider errors are already classified in `aether/errors.py`: `ProviderError`, `AuthenticationError`, `RateLimitError`, and `ContextOverflow`.

### Agent loop, budget, and usage

- `aether/core/loop.py::TurnState` carries messages, tools, provider candidates, provider manager, context manager, executor, config, usage, shared spend budget, cancellation, and status callbacks.
- `_preflight_cost()` performs billable-provider confirmation checks, estimates worst-case cost including retries, reserves the estimate, and refuses unpriced models when a cost cap is configured.
- `_cost_limit()` takes `min(configured, inherited)` and monotonically lowers the shared budget under a lock. Children cannot raise it.
- `_call_provider()` iterates candidates, emits status events, marks failures with temporary or longer cooldowns, releases reservations, and aggregates errors.
- `_accumulate_usage()` records prompt/completion tokens, cached-token pricing through `rough_cost()`, shared usage, actual cost, and `cost_known`.
- `aether/persistence/store.py` has an additive `usage` table and methods for per-session usage history.

### Context and planning

- `aether/core/context.py::ContextManager` assembles system prompts, truncates oversized tool results, removes middle messages, summarizes removed messages, and repairs tool-call/tool-result pairing.
- Token estimates use the honest heuristic in `aether/utils.py`; there is no provider-specific tokenizer dependency.
- `aether/core/planning.py::classify_request()` already classifies complexity and route shape for prompt/planning purposes. It is not used for model selection.
- `ContextManager.rough_cost()` is a stub returning `0.0` and must not be used as a real pricing source.

### Configuration, CLI, roles, and orchestration

- `aether/config.py` uses typed dotted defaults, deep merge, safe JSON writes, and additive validation warnings. Existing configs remain valid when new keys are added.
- `aether/cli/app.py` exposes stable top-level commands and slash commands. `--confirm-paid` is process-scoped and never persisted.
- `aether/orchestration/roles.py::DEFAULT_ROLES` currently defines `researcher`, `developer`, `debugger`, and `reviewer`; roles may pin `provider` and `model`.
- `resolved_roles()` forces deny/approval sets after user overrides; forced child protections cannot be weakened.
- `aether/core/agent.py::_orchestration_child()` and `_child_agent()` pass the same shared spend budget to children.
- `Orchestrator._authorize_paid()` blocks billable child roles unless explicitly allowed by existing controls.

### Memory and learning

- `aether/memory/layers.py` provides working, episodic, semantic, procedural, and user memory with provenance, confidence, bounded recall, and episodes.
- `aether/learning/engine.py` records sanitized experience, explicit feedback, evidence rules, skill proposals, validation, versions, rollback, and learning context.
- `aether/persistence/store.py` contains additive `usage`, `memory_items`, `learning_experiences`, `learning_proposals`, `learning_versions`, `learning_metrics`, and `learning_events` tables.
- Phase D's `_verify_flags()` treats model claims and bare success status as unverified. Phase E model-performance evidence must follow the same rule.

### Benchmarks and docs

- At the audit checkpoint, `benchmarks/` contained protocol documentation only. Phase E has since added a deterministic routing runner under `benchmarks/model_routing/`; it prints JSON to stdout and writes no result artifact.
- `scripts/check.sh` runs compile, unit tests, doctor, mock CLI smoke, secret scan, local Markdown link check, and startup benchmark.
- Phase E documentation targets are listed in [INTELLIGENCE_ROADMAP.md](INTELLIGENCE_ROADMAP.md), [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md), [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md), [RELEASE_CHECKS.md](RELEASE_CHECKS.md), [README.md](../README.md), [CHANGELOG.md](../CHANGELOG.md), [PROVIDERS.md](PROVIDERS.md), and [CONFIGURATION.md](CONFIGURATION.md).

## Gaps found at the audit checkpoint

These gaps describe the baseline before Phase E implementation, not the current implementation on this feature branch.

- No model capability registry exists.
- No task-to-capability requirements exist for routing.
- No transparent scoring system or model-selection explanation exists.
- No verified model-performance history exists; `usable` usage rows are per request, not per successful task.
- No health status view exists beyond provider cooldown internals.
- No CLI or slash commands exist for models, capabilities, routing explanations, performance, or health.
- No deterministic model-routing benchmark harness exists. Phase E added an offline routing-simulation runner, not a task-quality harness.
- No role capability requirements, per-role context settings, or per-role spend shares exist.
- `ContextOverflow` is defined but not handled as a recoverable context event.
- `extra_body` can currently override payload fields such as model and tools; routing must not make this bypass invisible.

## Compatibility requirements

Phase E must preserve:

1. Existing provider names, transports, tool-call contract, `ModelResponse`, and usage shapes.
2. `ProviderManager` active provider, fallback order, cooldowns, and status events.
3. Paid-provider confirmation semantics, including the inverted meaning of `costs.confirm_paid`.
4. Preflight reservations, monotonic shared caps, post-call cost checks, and cached-token pricing.
5. Mock-provider deterministic tests and offline diagnostics.
6. SQLite additive schema migrations and existing tables.
7. Child permission narrowing, forced deny/approval sets, cancellation, and no retries after tool side effects.
8. Frozen terminal appearance and existing CLI command grammar.
9. No secret logging, no secret commits, and no assumed free-tier behavior.
10. 153 existing passing tests before adding Phase E tests.

## Extension design

Phase E is additive:

- `aether/routing/capabilities.py`: structured capability facts with evidence levels and freshness.
- `aether/routing/classifier.py`: deterministic task requirements without an extra model call.
- `aether/routing/router.py`: transparent scoring, explanations, learned performance, health-aware fallback.
- Additive config under `routing.*` and `models.metadata`.
- Additive SQLite table for verified model performance.
- Additive `TurnState.routing` and `TurnResult.routing` fields.
- New CLI/slash commands only; no existing command semantics changed.
- New deterministic benchmark harness under `benchmarks/model_routing/`.

The full workflow is in [PHASE_E_IMPLEMENTATION_PLAN.md](PHASE_E_IMPLEMENTATION_PLAN.md), user-facing behavior in [MODEL_ROUTING.md](MODEL_ROUTING.md), and benchmark protocol in [PHASE_E_BENCHMARKS.md](PHASE_E_BENCHMARKS.md).
