# Phase E Implementation Plan

This plan turns the audit in [PHASE_E_ARCHITECTURE.md](PHASE_E_ARCHITECTURE.md) into ordered, verifiable work. Phase E is additive and preserves the pre-Phase-E baseline of 153 passing tests, startup performance, and all provider/cost/security controls. Phase E is implemented on this feature branch and locally verified; it has not been released.

## Acceptance contract

Phase E is complete only when deterministic tests demonstrate:

1. A simple question selects an appropriate lightweight configured model.
2. A difficult programming request selects a configured coding-capable model.
3. A research task selects a configured model with tool-calling and structured-output suitability.
4. An unavailable preferred model triggers a valid fallback.
5. Fallback to a billable provider is rejected without confirmation.
6. Shared parent/child budgets remain intact and monotonic.
7. Context-length errors are recovered without losing the current objective, tool-call IDs, or tool results.
8. Every routing decision includes an explanation.
9. Verified historical performance changes recommendations; unverified claims do not.
10. Existing security and cost regression tests still pass.

## Step 1 — capability facts

Create `aether/routing/capabilities.py`.

Each `ModelCapabilities` record stores:

- provider and model identifier
- model version when known
- local/hosted status
- context window as a fact
- input/output/cached-token prices as facts
- tool calling, structured output, streaming, coding, reasoning, research, context handling, vision
- estimated memory requirements when known
- concurrency limitation when known
- provider-specific restrictions
- evidence level: `verified`, `provider-reported`, `inferred`, or `unknown`
- source and freshness

Rules:

- Never invent context windows, model versions, prices, or benchmarks.
- Catalog prices and provider restrictions are `provider-reported`.
- Transport support in Aether code is `verified` for provider-level transport, but model-level capability remains `inferred` or `unknown`.
- User metadata may promote a fact to `verified` or `provider-reported` only when the user supplies the evidence label and source.
- Unknown pricing must not become zero.

## Step 2 — task requirements

Create `aether/routing/classifier.py`.

`classify_task()` returns category, complexity, context estimate, tool requirements, accuracy requirement, expected tokens, required capabilities, and user overrides. Classification uses one deterministic pass over text and existing plan/signals; it never calls a model for every message.

Categories: general conversation, simple question, complex reasoning, software development, debugging, code review, research, data analysis, documentation, summarization, planning, tool-heavy automation, long-context, and multi-agent orchestration.

Users can override via `routing.category_keywords`, `routing.overrides`, task text passed to `aether models routing|explain`, and explicit `TaskRequirements` in the API.

## Step 3 — router and explanations

Create `aether/routing/router.py`.

`ModelRouter.route()` scores only models the user actually configured: active provider/model, configured fallbacks, role pins, and user metadata entries. Scoring considers:

- required capabilities
- context window and safety margin
- latency estimate
- token cost and billability
- provider health/cooldown
- local hardware conservatism
- verified model-performance history
- role-specific requirements
- stability bonus for the active model

`RoutingDecision` records selected provider/model, score, reasons, considered candidates, and rejections. No suitable configured model produces an explicit limitation decision instead of silent fallback.

## Step 4 — verified model performance

Add an additive `model_performance` SQLite table and store methods:

- save outcome with task category, provider, model, success/failure, test/tool errors, tokens, actual cost, duration, recovery attempts, and evidence sources
- query by category/provider/model
- reset all or filtered history
- mark an outcome verified from Phase D user feedback or deterministic evidence with `mark_model_performance_verified()`

Only outcomes with accepted evidence sources affect learned routing. One failure is a small signal; confidence grows with sample size. No model is permanently blacklisted.

## Step 5 — context intelligence

Extend `ContextManager.fit()` with optional provider/model context limits from the capability registry and `routing.context_safety_margin`. Preserve essential system instructions, the active objective, recent messages, tool-call IDs, and matching tool results.

Handle `ContextOverflow` as a recoverable event: compress with a tighter target, retry the same provider once, record the recovery, and never remove security/approval instructions.

## Step 6 — agent and role integration

- Add routing fields to `TurnState` and `TurnResult`.
- Emit `routing_decision`, `routing_fallback`, and `context_recovered` status events.
- Preserve explicit `--provider`/`--model` and `Agent(provider_name=..., model=...)` overrides as explicit authority via `TaskRequirements.explicit_provider`/`explicit_model`; there is no `routing.manual` setting.
- Extend role metadata with planner, architect, tester, security auditor, data analyst, and documentation writer.
- Support fixed model, auto selection, preferred model with fallbacks, role capability requirements, context tokens, and spend share within the parent budget.
- Reviewer routing can avoid models already used by implementation roles when another configured model is available.

## Step 7 — CLI and diagnostics

Add:

```text
aether models list
aether models inspect PROVIDER [MODEL]
aether models capabilities PROVIDER [MODEL]
aether models routing "TASK TEXT"
aether models explain "TASK TEXT"
aether models performance
aether models health
aether models benchmark [--samples N] [--confirm-billable]
```

Add slash commands:

```text
/models
/models routing "TASK TEXT"
/models explain "TASK TEXT"
/models performance
/models health
```

Diagnostics never call a model or poll providers. `models benchmark` is an offline, deterministic routing simulation that prints JSON to stdout; it makes no model, network, or billable calls and writes no files. `--confirm-billable` is acknowledgement only.

## Step 8 — deterministic benchmarks and tests

Create `benchmarks/model_routing/runner.py` and `tests/test_model_routing.py`.

Benchmark modes: fixed-model baseline, capability routing, cost-aware routing, and learned routing. Runner fixtures are ten deterministic task texts with declared category and context sizes; they measure fixture eligibility only. Behavioral scenarios such as unsupported capability, outage, rate-limit cooldown, paid block, context overflow, unavailability, learned evidence, explanations, and nested budget accounting are covered by `tests/test_model_routing.py`, not by model calls in the runner.

No benchmark may claim real model quality or task-quality parity. Results are decision-level simulations with mock providers and explicit assumptions, printed to stdout with no result artifact written. The runner has no `__main__`, `argparse`, `--output`, or file writes; its scenarios are distinct from the behavioral tests in `tests/test_model_routing.py`.

## Step 9 — verification and checkpoint

Recorded and verified locally:

| Command | Result |
|---|---|
| `python3 -W ignore::ResourceWarning -m unittest tests.test_model_routing -q` | 26 tests pass, including HTTP 400 context-length detection/recovery and orchestrator role preferred/fallback entries |
| `python3 -W ignore::ResourceWarning -m unittest discover -s tests -q` | 179 tests pass |
| `bash scripts/check.sh && bash scripts/test_install.sh` | all checks passed; 3 cold starts, median wall time `0.114s`, peak child RSS `34.4 MiB`; local git-remote install test passed |
| `python3 scripts/benchmark.py` | 3 cold starts, median wall time `0.112s`, peak child RSS `34.9 MiB` |
| `git diff --check` | passed |

`ResourceWarning` notices for unclosed SQLite connections are non-failing. No lint/typecheck command is configured, so no lint/typecheck result is claimed. Startup timing and peak memory are local measurements, not task-quality results. Implementation is committed separately from documentation. Do not push, merge, tag, or release without confirmation.

See [MODEL_ROUTING.md](MODEL_ROUTING.md) and [PHASE_E_BENCHMARKS.md](PHASE_E_BENCHMARKS.md).
