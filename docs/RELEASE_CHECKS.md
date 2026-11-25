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

## Phase B adaptive planning checkpoint

- Branch: `feat/aether-020-intelligence-foundation`; base commit `d077948e085cb17038b2da245d31e6bf86491120`.
- Phase B checkpoint commit: `9aef0fb873f6e54bc78f7b587e3fe8709dc07c55`.
- Added deterministic planning, plan/checkpoint persistence, plan tool/CLI/slash commands, and turn-loop/agent integration.
- `python3 -W ignore::ResourceWarning -m unittest tests.test_planning tests.test_core tests.test_persistence tests.test_cli` — 48 focused tests passed.
- `python3 -m unittest discover -s tests -v` — 121 tests passed in `0.632s` in a recorded verbose run.
- The first focused run failed `test_revision_records_invalidating_evidence` because repair tasks were not selected first; `ExecutionPlan.next_task()` was fixed to prioritize `repair_` tasks before dependencies-aware selection.
- `python3 -m compileall -q aether tests && python3 -m unittest discover -s tests -v && bash scripts/check.sh && bash scripts/test_install.sh && git diff --check` — all commands passed.
- `bash scripts/check.sh` during Phase B verification — `all checks passed`; a recorded local startup benchmark had 3 cold starts, median wall time `0.095s`, peak child RSS `32.1 MiB`.
- `AETHER_HOME=<temp> python3 -m aether --provider mock run "Say hello"` followed by `aether plan list` and `aether plan status` — passed; created one completed simple plan and displayed its status.
- Full verbose test output emitted `ResourceWarning` notices for unclosed SQLite connections; no test or check failed.
- No lint/typecheck claim: no configured lint/typecheck command was found or run.
- No task-quality benchmark was run; no Hermes parity or superiority claim is made.

## Phase C layered memory checkpoint

- Branch: `feat/aether-020-intelligence-foundation`; base commit `d7e9c9ebf6b6cf65e80df8236e280eabb42c7087`.
- Phase C checkpoint commit: `833cad8f4bbdea74241c4d18f3719c77755ad7c1`.
- Added layered memory storage, bounded labeled retrieval, Markdown migration, provenance, correction, contradiction handling, consolidation, expiration, export/import, CLI/tool/slash exposure, and child write isolation.
- `python3 -W ignore::ResourceWarning -m unittest tests.test_memory_layers -v` — 11 focused tests passed.
- The first focused run failed `test_working_memory_is_session_scoped_and_expires` because already-expired active rows were excluded before pruning; `LayeredMemory.prune_expired()` now uses `include_expired=True`.
- The first focused run also failed `test_consolidation_merges_duplicates` on an ambiguous confidence/timestamp tie; the test now uses distinct confidence values to verify highest-confidence retention.
- `python3 -W ignore::ResourceWarning -m unittest discover -s tests -v` — 132 tests passed in `1.007s`.
- `bash scripts/check.sh && bash scripts/test_install.sh && git diff --check` — all commands passed.
- `bash scripts/check.sh` during Phase C verification — `all checks passed`; first run: 132 tests in `0.975s`, 3 cold starts, median wall time `0.110s`, peak child RSS `33.6 MiB`; final documentation run: 132 tests in `0.948s`, median wall time `0.095s`, peak child RSS `32.4 MiB`.
- `aether memory layer add|recall|counts` was covered by deterministic CLI tests using the mock provider and temporary home.
- Full verbose test output emitted `ResourceWarning` notices for unclosed SQLite connections; no test or check failed.
- No lint/typecheck claim: no configured lint/typecheck command was found or run.
- No task-quality benchmark was run; no Hermes parity or superiority claim is made.

## Phase D evidence-based learning checkpoint

- Branch: `feat/aether-020-intelligence-foundation`; base commit `537b983`.
- Phase D implementation checkpoint: `0dc4118af627cb2c5de4daac0a8ed4e3512705cf`.
- Added sanitized experience records, explicit feedback, evidence rules, discovery, deterministic validation, approval/rejection, version history, metrics, rollback, learning events, and bounded labeled prompt context.
- Added `aether skills discover|proposals|validate|approve|reject|history|versions|rollback|result`, `aether learning pending|metrics|feedback`, `/skills` learning actions, and `/feedback`.
- `python3 -W ignore::ResourceWarning -m unittest tests.test_learning -v` — 21 focused tests passed in `0.554s`.
- The first focused run exposed five issues: test config helper shadowing, unseeded proposal helpers, missing plan-ID inference, premature `usage` access in `Agent.run_turn()`, and un-dotted approved skill version headers. All were fixed before the recorded focused pass.
- `python3 -W ignore::ResourceWarning -m unittest discover -s tests -v` — 153 tests passed in `1.849s`.
- `bash scripts/check.sh && bash scripts/test_install.sh` — all checks passed; 3 cold starts, median wall time `0.109s`, peak child RSS `34.1 MiB`; local git-remote install test passed.
- `git diff --check` — passed before the implementation commit.
- Full verbose test output emitted `ResourceWarning` notices for unclosed SQLite connections; no test or check failed.
- No lint/typecheck claim: no configured lint/typecheck command was found or run.
- No task-quality benchmark was run; no Hermes parity or superiority claim is made.

## Phase E capability-aware routing checkpoint

- Phase E is implemented on this feature branch; implementation is committed separately from documentation. Version remains `0.1.0`; no `0.2.x` release or tag exists.
- Added evidence-aware capability registry, deterministic classifier, scored router with `capability`, `cost`, and `fixed` strategies, explicit model authority, provider health cooldowns, context-fit/overflow recovery, verified model performance, role metadata, and offline model diagnostics.
- Added focused coverage for HTTP 400 context-length detection/recovery and orchestrator role preferred/fallback entries.
- `python3 -W ignore::ResourceWarning -m unittest tests.test_model_routing -q` — 26 focused tests passed.
- `python3 -W ignore::ResourceWarning -m unittest discover -s tests -q` — 179 tests passed.
- `bash scripts/check.sh && bash scripts/test_install.sh` — all checks passed; 3 cold starts, median wall time `0.114s`, peak child RSS `34.4 MiB`; local git-remote install test passed.
- `python3 scripts/benchmark.py` — 3 cold starts, median wall time `0.112s`, peak child RSS `34.9 MiB`.
- `git diff --check` — passed.
- `ResourceWarning` notices for unclosed SQLite connections are non-failing.
- No lint/typecheck claim: no configured lint/typecheck command was found or run.
- No model/network/billable calls were made by the routing diagnostics or the deterministic benchmark; no benchmark result artifact was written.
- The startup timing and memory figures are local startup measurements, not task-quality results. No task-quality benchmark was run; no Hermes parity or superiority claim is made.

## Phase F persistent incremental index checkpoint

- Branch: `feat/aether-parity-foundation`; integration base `8f15419c4810f8e87c0992dc43ad2521754f4027`; PR #8 remains open and draft.
- Changed implementation files: `aether/coding/__init__.py`, `aether/coding/symbols.py`, `aether/coding/index.py`, `aether/tools/repository.py`, `aether/tools/builtins.py`, `aether/config.py`.
- Changed test file: `tests/test_repository_index_persistence.py`.
- Changed documentation: `docs/ARCHITECTURE.md`, `docs/CONFIGURATION.md`, `docs/DEVELOPMENT_STATUS.md`, `docs/FEATURE_MATRIX.md`, `docs/INTELLIGENCE_ROADMAP.md`, `docs/KNOWN_LIMITATIONS.md`, `docs/RELEASE_CHECKS.md`, and `docs/WORKSTATION_ACCEPTANCE_GATE.md`.
- Added a separate `repo_index.db` cache under `AETHER_HOME` with mode `0600`, additive schema creation, a `ctime_ns` migration, bounded file/symbol counts, cancellation checks, and a single-process refresh lock. `state.db` is unchanged.
- `python3 -m unittest tests.test_repository_tools tests.test_repository_index_persistence -v` — 28 focused tests passed in `0.178s`.
- `python3 -m compileall -q aether tests` — passed with no output.
- `python3 -m unittest discover -s tests -v` — 233 tests passed in `2.494s`.
- `bash scripts/check.sh` — all checks passed; its in-script suite ran 233 tests in `2.462s`; 3 cold starts, median wall time `0.120s`, peak child RSS `34.8 MiB`.
- An earlier implementation-only pass of the same five commands used `2.485s`, `2.478s`, `0.123s`, and `35.7 MiB` for the same four measurements. A final check-only rerun after the release-record edit ran 233 tests in `2.631s` with median wall time `0.128s` and peak child RSS `35.6 MiB`; all checks passed.
- `bash scripts/test_install.sh` — `0.1.0`; local git-remote install test passed.
- `git diff --check` — passed.
- Failures found and fixed before the passing run: a `str`/`Path` query bug, absent mtime/ctime invalidation, per-sync instead of per-root symbol budgeting, unsafe cached rows being filtered after SQL `LIMIT`, parallel-safe cache writes, and cancellation races during commit.
- An independent reviewer inspected the diff twice; the second pass confirmed the resolved items and noted only the accepted single-process cache scope, conservative query oversampling, and the internal-cache classification of home-directory writes.
- `ResourceWarning` notices for pre-existing unclosed SQLite connections remain non-failing in verbose output; the new index closes its own connections explicitly.
- No lint/typecheck command is configured, so none is claimed. No model/network/billable calls were made. No task-quality benchmark was run; no Hermes parity or superiority claim is made.

## Verification evidence hardening checkpoint

- Changed implementation file: `aether/core/agent.py`.
- Changed test file: `tests/test_model_routing.py`.
- Changed documentation: `README.md`, `docs/DEVELOPMENT_STATUS.md`, `docs/KNOWN_LIMITATIONS.md`, `docs/RELEASE_CHECKS.md`, and `docs/WORKSTATION_ACCEPTANCE_GATE.md`.
- `Agent._verification_from_state()` no longer treats arbitrary tool text containing `unittest`, `pytest`, `compileall`, `scripts/check.sh`, or `aether doctor` as evidence. It accepts only successful `test_run` results with a recognized deterministic command, or strictly parsed `terminal` commands for `python -m unittest`, `python -m compileall -q aether tests`, `bash scripts/check.sh`, and `aether doctor`. `python` tool snippets are never accepted as verification evidence.
- Focused verification: `python3 -m unittest tests.test_model_routing -v` — 28 tests passed in `0.292s`.
- Full verification: `python3 -m unittest discover -s tests -v` — 235 tests passed in `2.459s`.
- `python3 -m compileall -q aether tests` — passed with no output.
- `bash scripts/check.sh` — all checks passed; its in-script suite ran 235 tests in `2.461s`; 3 cold starts, median wall time `0.132s`, peak child RSS `34.8 MiB`.
- `bash scripts/test_install.sh` — `0.1.0`; local git-remote install test passed.
- `git diff --check` — passed.
- Failure found and fixed: the first strict command parser used the wrong token slice for `python -m unittest discover`, so two verification tests failed; the slice was corrected and the focused suite passed.
- Five read-only specialist audits were run before the change. Their reports were treated as data; the implementation and tests were reconciled and verified locally.
- Remaining critical work: default approval for memory/skill/scheduler writes, forced child approval for `patch_apply`, scheduled-run cancellation and tool restrictions, persistent-index corruption recovery, symbol-version/budget invalidation, and the end-to-end mock-provider coding loop.
- No lint/typecheck command is configured, so none is claimed. No model/network/billable calls were made. No Hermes parity or task-quality claim is made.

## Secrets

- No `.env` file was created in the repository.
- No API keys were committed.
- `scripts/check.sh` scans source files for common API-key patterns.
