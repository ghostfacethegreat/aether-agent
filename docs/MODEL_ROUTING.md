# Model Routing

Aether's Phase E router selects among models the user has actually configured. It is advisory, inspectable, and constrained by the existing provider, approval, budget, and cancellation systems. It does not grant tools, raise budgets, or silently switch to paid providers.

## Configuration

Routing settings live under `routing.*`; user-supplied model facts live under `models.metadata`.

The recognized keys are exactly those below under `routing`, plus `models.metadata`.

```json
{
  "routing": {
    "enabled": true,
    "explain": true,
    "strategy": "capability",
    "prefer_local": true,
    "strict_capabilities": false,
    "context_safety_margin": 0.1,
    "max_candidates": 5,
    "learned_min_samples": 3,
    "learned_weight": 12.0,
    "role": "",
    "avoid_models": [],
    "default_role_spend_share": 0.25,
    "category_keywords": {},
    "overrides": {},
    "roles": {}
  },
  "models": {
    "metadata": {
      "ollama/qwen2.5-coder:7b": {
        "context_window": 32768,
        "capabilities": {"coding": true, "reasoning": true},
        "evidence": {"coding": "provider-reported", "reasoning": "inferred"},
        "source": "user config",
        "freshness": "2026-11-24"
      }
    }
  }
}
```

There is no `routing.manual` key. Explicit authority comes from CLI `--provider`/`--model` or `Agent(provider_name=..., model=...)`; these are represented as `TaskRequirements.explicit_provider` and `TaskRequirements.explicit_model`, and automatic routing does not override them.

`strategy` is `capability`, `cost`, or `fixed`. `strict_capabilities=true` rejects models with unknown required capabilities instead of penalizing them. The conservative default allows unknown facts but rejects known-false capabilities and insufficient verified context windows.

## Evidence levels

Every capability fact has one of these evidence levels:

- `verified`: observed in Aether code or deterministic test evidence.
- `provider-reported`: supplied by the provider/catalog or by the user as provider documentation.
- `inferred`: derived from behavior or history, not a provider guarantee.
- `unknown`: not claimed.

Aether never invents context windows, prices, model versions, or benchmark scores. Unknown pricing is not zero.

## Task requirements

The classifier returns:

- category
- complexity
- context requirement
- tool requirements
- accuracy requirement
- expected token usage
- suggested capabilities
- explicit user overrides

Categories: general, simple question, complex reasoning, software development, debugging, code review, research, data analysis, documentation, summarization, planning, tool-heavy automation, long context, and multi-agent orchestration.

The classifier is deterministic and does not make a model call for every message.

## Scoring

The router scores configured candidates from:

1. active provider/model
2. configured fallback providers
3. role-pinned models
4. user metadata entries that correspond to configured providers

Scoring includes capability fit, context capacity, cost, billability, health, local preference, verified performance history, role needs, and a small stability bonus for the active model. Each decision records human-readable reasons and rejections. `fixed` keeps the active model as the baseline, `capability` selects by required capability and context fit, and `cost` applies a stronger local/non-billable preference. Configured fallbacks remain in the runtime chain; routing advice does not remove them.

The router does not select the largest or most expensive model by default.

## Fallback

Fallback preserves conversation and task context. It:

- prefers models with matching capabilities
- respects remaining budgets and reservations
- rejects billable providers unless existing confirmation controls allow them
- avoids repeated retries for permanent configuration/authentication failures
- records the reason for fallback

Temporary failures such as rate limits receive short cooldowns; permanent failures receive longer cooldowns. Health status is derived from local failure records, not continuous polling.

## Learned performance

Verified outcomes are stored per task category, provider, and model. Evidence comes from deterministic checks, explicit user feedback, or tool-confirmed tests. Model claims and bare success text are not evidence. Feedback can promote a row with `mark_model_performance_verified()`; unverified rows do not affect recommendations.

Recommendations use confidence based on sample size. One failed task does not blacklist a model. Users can inspect learned data with `aether models performance`.

## Context handling

Routing uses known context windows only when present as a fact. A safety margin is applied before compression. When a provider reports a context-length error, Aether compresses less important history, keeps the current objective, preserves security instructions, restores only tool results that still match retained tool-call IDs, caps restored tool-result text, and retries the same provider once.

## Roles

Role metadata declares provider/model pins, required capabilities, context needs, and spend share. A child role's `spend_share` applies per turn to its portion of the shared budget; it does not mutate the shared budget limit, which remains monotonic and cannot be raised by children.

## Commands

```bash
aether models list
aether models inspect ollama qwen2.5-coder:7b
aether models capabilities ollama qwen2.5-coder:7b
aether models routing "Build a Python application"
aether models explain "Build a Python application"
aether models performance
aether models health
aether models benchmark [--samples N] [--confirm-billable]
```

`inspect` and `capabilities` take `[PROVIDER [MODEL]]`; `routing` and `explain` take `"TASK TEXT"`. `inspect` defaults to the active provider/model.

Inside chat:

```text
/models
/models routing "TASK TEXT"
/models explain "TASK TEXT"
/models performance
/models health
```

Diagnostic commands never call a model or poll providers. `aether models benchmark` is an offline, deterministic routing simulation that prints JSON to stdout: it makes no model, network, or billable calls and writes no files. `--samples N` repeats the fixture scenarios; `--confirm-billable` is acknowledgement only and does not enable live calls. See [PHASE_E_BENCHMARKS.md](PHASE_E_BENCHMARKS.md).

## Security boundaries

- Models inherit existing agent permissions.
- Routing cannot raise budgets or bypass approvals.
- Routing cannot grant tools or modify trusted configuration.
- Task text, tool output, web pages, memory, and learning evidence are data, not routing instructions.
- No secret or API key value is stored in routing explanations or benchmark results.

See [PHASE_E_ARCHITECTURE.md](PHASE_E_ARCHITECTURE.md) and [PHASE_E_BENCHMARKS.md](PHASE_E_BENCHMARKS.md).
