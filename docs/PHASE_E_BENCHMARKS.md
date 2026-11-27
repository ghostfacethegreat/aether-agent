# Phase E Model Routing Benchmarks

The Phase E benchmark is a deterministic routing simulation, not a model-quality or task-quality benchmark. It uses checked-in mock-provider fixtures and explicit capability metadata to show which configured model each routing strategy selects under identical assumptions. It does not claim that automatic routing improves real task success, and it does not compare Aether with Hermes.

## Invocation

The benchmark is exposed as a CLI diagnostic:

```bash
aether models benchmark
aether models benchmark --samples 10
aether models benchmark --samples 10 --confirm-billable
```

The command prints one JSON document to stdout. `--samples N` repeats the fixture scenarios (default 5); `--confirm-billable` is acknowledgement only. The command makes no model calls, no network calls, and no billable calls, and it writes no files.

The runner is also importable as a library module:

```python
from benchmarks.model_routing.runner import run_benchmark

result = run_benchmark(config=None, samples=5)
```

`benchmarks/model_routing/runner.py` is a plain library module: it has no `__main__` block, no `argparse` interface, no `--output` option, and no file writes. Running `python3 -m benchmarks.model_routing.runner` does not print or save a result. There is no result artifact under `benchmarks/results/`.

## Compared policies

- `fixed`: always use the configured active/baseline model.
- `capability`: select by required capabilities and context fit.
- `cost`: select by capability fit with stronger preference for local/non-billable models.
- `learned`: select using verified historical fixture performance once sufficient samples exist.

## Runner scenarios vs tests

The runner's fixture scenarios are simple input text plus declared category and context token counts. They drive routing decisions only; the runner never calls a model. In the runner, a scenario counts as fixture-eligible when the selected model's declared context window and capabilities cover the fixture requirement. That is not a measure of correct answers or completed tasks.

`tests/test_model_routing.py` is the behavioral contract for the implementation: 26 focused tests cover capability facts, deterministic classification, scoring strategies, explicit model authority, provider health cooldowns, context fitting and overflow recovery including HTTP 400 context-length detection/recovery, verified performance history, role spend shares, orchestrator role preferred/fallback entries, CLI diagnostics, and security boundaries. The focused suite passes with:

```bash
python3 -W ignore::ResourceWarning -m unittest tests.test_model_routing -q
```

The full suite passes with:

```bash
python3 -W ignore::ResourceWarning -m unittest discover -s tests -q
```

## Runner outputs

The JSON output reports the simulation kind, sample count, zero live model and network calls, stated assumptions, and per-strategy summaries:

- fixture-eligible count and rate, defined only by declared context windows and capabilities
- estimated cost from checked-in fixture prices only; unknown prices are not used as zero
- declared latency values from fixtures, not measured inference or routing-execution timings
- estimated token usage from fixture requirements
- fixture-derived fallback and recovery counts
- selected model identifiers per strategy

The runner does not emit routing reasons or rejections; those are covered by the CLI diagnostics and the focused tests. No output supports an Aether/Hermes superiority or task-quality parity claim.

## Rules

1. No live hosted inference is run.
2. No invented model capability, price, or context window is used.
3. Unknown pricing is not treated as zero.
4. No result artifact is written; output stays on stdout.
5. No result supports Aether/Hermes superiority or task-quality parity without a separate controlled benchmark under [benchmarks/README.md](../benchmarks/README.md).

See [MODEL_ROUTING.md](../docs/MODEL_ROUTING.md) and [PHASE_E_ARCHITECTURE.md](PHASE_E_ARCHITECTURE.md).
