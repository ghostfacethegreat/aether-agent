# Release Checks

These are actual locally recorded checks. They are not a claim that a public release exists.

## Environment

- Date: 2026-11-23
- macOS, Python 3.14.2, git 2.37.1
- Aether version 0.1.0 alpha

## Checks performed

- `python3 -m compileall -q aether tests` — passed.
- `python3 -m unittest discover -s tests -v` — 38 tests passed.
- `python3 -c "import tomllib; tomllib.load(open('pyproject.toml','rb'))"` — passed.
- `python3 -c "from aether.cli.app import main"` — passed.
- `AETHER_HOME=<temp> python3 -m aether --provider mock run "Say hello"` — passed, no network.
- `AETHER_HOME=<temp> python3 -m aether providers` — passed.
- `AETHER_HOME=<temp> python3 -m aether doctor` — passed.
- `scripts/check.sh` — passed; includes compile, unit tests, doctor, mock CLI smoke, secret scan, and benchmark.
- `scripts/benchmark.py` — 3 cold starts, median wall time 0.081s, peak child RSS 29.6 MiB.
- `scripts/test_install.sh` — passed by committing the working tree to a temporary git repo, cloning it locally, installing from the clone, running the installed CLI with the mock provider, and verifying uninstall removes the wrapper.
- `aether status` with `--provider mock` — passed; displays `mock (local)` and `mock-standard`.
- Screenshots in `docs/screenshots/` were captured from real local CLI runs with `NO_COLOR=1`; label says mock provider and no network.
- Local Markdown links checked: no broken local targets.

## Tooling not available locally

- `ruff`, `mypy`, and `pyright` were not installed; no lint/typecheck claim is made.
- No third-party runtime dependencies are declared.

## Not yet verified

- Live hosted provider calls were not made.
- Real provider SSE streams were not exercised; the OpenAI-compatible SSE accumulator has an unit test with synthetic chunks.
- No hosted installer URL has been tested.
- The local install test used a temporary git remote; no hosted installer URL was tested.
- Live local inference with an Ollama server was not recorded in this document.
- Network update (`aether update` against the public remote) was not recorded in this document.

## Phase 2 audit checkpoint

- Upstream comparison baseline: `b98c388a880b1b6fd303c9c2821a3946651a0b4c`.
- Aether comparison baseline: `bdbe2462dda3c4646086385d600b4e2ab23f4957`.
- Added [PHASE2_FEATURE_COMPARISON.md](PHASE2_FEATURE_COMPARISON.md) and [PHASE2_ROADMAP.md](PHASE2_ROADMAP.md).
- This checkpoint changed documentation only; no new runtime behavior was implemented or validated.
- `scripts/check.sh` after the documentation checkpoint — passed: 38 tests, doctor, mock CLI smoke, secret scan, local Markdown links, and benchmark.
- The public repository was created and source was pushed at commit `bdbe246` before this documentation checkpoint.

## Phase 2 Milestone 2.1 checks

- `python3 -m unittest tests.test_persistence tests.test_core tests.test_providers` — 17 targeted tests passed.
- Targeted reruns emitted ResourceWarning notices for unclosed SQLite connections; no test failed, and the full check below passed.
- `scripts/check.sh` after M2.1 — passed: 42 tests, doctor, mock CLI smoke, secret scan, local Markdown links, and benchmark.
- Benchmark in that M2.1 run: 3 cold starts, median wall time 0.079s, peak child RSS 30.3 MiB.
- Validated behavior: tool-call metadata round trip, resumed tool-call history, context repair, and Anthropic nested tool-call replay.

## Phase 2 Milestone 2.2 checks

- `python3 -m unittest tests.test_tools -v` — 12 targeted tests passed.
- `scripts/check.sh` after M2.2 — passed: 47 tests, doctor, mock CLI smoke, secret scan, local Markdown links, and benchmark.
- Benchmarks in M2.2 runs: 3 cold starts each, median wall time around 0.08s and peak child RSS around 30 MiB.
- Validated behavior: executor-level timeout denial, model-facing secret redaction, private URL rejection, redirect-to-private rejection, and strict-mode path checks for terminal `cwd` and git `paths`.
- Not validated here: live web fetches, live search providers, DNS rebinding, OS-level sandboxing, or browser command templates.

## Phase 2 Milestone 2.3 checks

- `python3 -m unittest tests.test_tasks tests.test_cli -v` — 15 targeted tests passed.
- `scripts/check.sh` after M2.3 — passed: 53 tests, doctor, mock CLI smoke, secret scan, local Markdown links, and benchmark.
- Benchmarks in M2.3 runs: 3 cold starts each, median wall time around 0.08s and peak child RSS around 29 MiB.
- Validated behavior: due-prompt execution, no-runner skips, failed-run records, restart no-refire, one-shot disabling, execution ledger, scheduler thread start/stop, update/pause/resume controls, and CLI summary output.
- Not validated here: real daemon/service scheduling, cross-process concurrency, delivery targets, or live scheduled provider calls.

## Phase A intelligence audit checkpoint

- Aether audit commit: `558bd58ec1f15ccf9cf76260d3ab7bfe675e76ce`.
- Hermes pinned baseline: `b98c388a880b1b6fd303c9c2821a3946651a0b4c`.
- Hermes current `main` checked for this phase: `fe9a4b58ec137d3e00719c10e2385876fa03b97c`.
- Added [INTELLIGENCE_AUDIT.md](INTELLIGENCE_AUDIT.md), [INTELLIGENCE_ROADMAP.md](INTELLIGENCE_ROADMAP.md), [HERMES_COMPARISON.md](HERMES_COMPARISON.md), and [../benchmarks/README.md](../benchmarks/README.md) scaffolding.
- Superseded visual-first 0.2 plans in the baseline, architecture, roadmap, original architecture audit, and Phase 2 docs; terminal appearance is frozen.
- `python3 -m unittest discover -s tests -v` — 109 tests passed in `0.595s`.
- `bash scripts/check.sh` — passed; 109 tests in `0.476s`, doctor and mock CLI smoke passed, secret scan passed, local Markdown links passed, cold starts: 3, median wall time `0.088s`, peak child RSS `30.3 MiB`, `all checks passed`.
- `bash scripts/test_install.sh` — passed; local git-remote install test completed.
- `git diff --check` — passed.
- No runtime behavior changed; no task-quality benchmark was run; no Hermes parity or superiority claim is made.
- No lint/typecheck claim: no configured lint/typecheck command was found or run.

## Secrets

- No `.env` file was created in the repository.
- No API keys were committed.
- `scripts/check.sh` scans source files for common API-key patterns.
