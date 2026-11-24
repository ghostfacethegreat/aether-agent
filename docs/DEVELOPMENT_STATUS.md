# Development Status

This is the resume log for the intelligence-first `Aether 0.2+` program. It records verified state only. Do not mark a phase complete from static inspection alone.

## Current checkpoint

| Item | Verified value |
|---|---|
| Date | 2026-11-24 |
| Active branch | `feat/aether-020-intelligence-foundation` |
| Base checkpoint | `d077948e085cb17038b2da245d31e6bf86491120` |
| Prior checkpoint | `558bd58ec1f15ccf9cf76260d3ab7bfe675e76ce` |
| Upstream baseline | `01ee003795787cc392f033edffbb98fcb3dd8b35` |
| Remote | `https://github.com/ghostfacethegreat/aether-agent.git` |
| Tags | none |
| Worktree at branch creation | clean |
| Pushed commits from this program | none |
| Phase B verification | 121 tests passed; see [RELEASE_CHECKS.md](RELEASE_CHECKS.md) |
| Phase B checkpoint | `9aef0fb873f6e54bc78f7b587e3fe8709dc07c55` |
| Phase C verification | 132 tests passed; see [RELEASE_CHECKS.md](RELEASE_CHECKS.md) |
| Phase C checkpoint | `833cad8f4bbdea74241c4d18f3719c77755ad7c1` |
| Phase D verification | 153 tests passed; see [RELEASE_CHECKS.md](RELEASE_CHECKS.md) |
| Phase D implementation checkpoint | `0dc4118af627cb2c5de4daac0a8ed4e3512705cf` |
| Phase E focused verification | 26 tests passed in `tests.test_model_routing`; see [RELEASE_CHECKS.md](RELEASE_CHECKS.md) |
| Phase E full verification | 179 tests passed; see [RELEASE_CHECKS.md](RELEASE_CHECKS.md) |
| Phase E status | implemented on this feature branch; implementation is committed separately from documentation; not released |

The unpushed commits from this program are deliberately preserved. Do not reset, discard, force-push, push, merge, tag, or release until the release gates in [RELEASE_ROADMAP.md](RELEASE_ROADMAP.md) pass.

## Completed work

### Phase 0 — repository baseline

- Verified repository state, history, remote, test suite, install test, startup performance, and preservation constraints.
- Froze the existing ASCII artwork and colored renderer.
- Added the baseline documentation in [AETHER_02_BASELINE.md](AETHER_02_BASELINE.md) and [AETHER_02_ARCHITECTURE.md](AETHER_02_ARCHITECTURE.md).

### Phase A — intelligence audit and benchmark contract

- Completed and committed as `d077948 docs: add intelligence-first audit and roadmap`.
- Added [INTELLIGENCE_AUDIT.md](INTELLIGENCE_AUDIT.md), [INTELLIGENCE_ROADMAP.md](INTELLIGENCE_ROADMAP.md), [HERMES_COMPARISON.md](HERMES_COMPARISON.md), and benchmark scaffolding under [../benchmarks/README.md](../benchmarks/README.md).
- Superseded visual-first plans while retaining them as historical evidence.
- No runtime behavior changed.

### Verification at the Phase A checkpoint

| Command | Result |
|---|---|
| `python3 -m unittest discover -s tests -v` | 109 tests passed in `0.595s` |
| `bash scripts/check.sh` | passed; 109 tests, doctor, mock CLI smoke, secret scan, Markdown links, benchmark |
| `bash scripts/test_install.sh` | passed |
| `git diff --check` | passed |

The startup benchmark recorded 3 cold starts, about `0.08s` median wall time, and about `30 MiB` peak child RSS. These are startup measurements, not task-quality results.

### Phase B — adaptive planning and execution state

- Added deterministic request classification and inspectable plans with objective, constraints, risk assessment, alternatives, task dependencies, tools, expected results, verification criteria, and revision history.
- Wired plan state into turns and SQLite persistence; plans and checkpoints survive process restarts, and resume skips completed or non-idempotent work.
- Added `plan_tool`, `aether plan list|show|status|checkpoints|resume`, and `/plan status|checkpoints|resume <id>|text`.
- Preserved the visual freeze, provider contracts, permissions, approvals, budgets, orchestration, and existing Markdown memory.

| Command | Result |
|---|---|
| `python3 -W ignore::ResourceWarning -m unittest tests.test_planning tests.test_core tests.test_persistence tests.test_cli` | 48 focused tests passed |
| `python3 -m unittest discover -s tests -v` | 121 tests passed in `0.632s` in a recorded verbose run |
| `python3 -m compileall -q aether tests && python3 -m unittest discover -s tests -v && bash scripts/check.sh && bash scripts/test_install.sh && git diff --check` | all commands passed |
| CLI `plan list` and `plan status` smoke | passed; completed simple plan displayed correctly |

Failure found: `test_revision_records_invalidating_evidence` initially failed because repair tasks were not selected first. `ExecutionPlan.next_task()` now prioritizes `repair_` tasks before dependency-aware selection.

The full verbose test output emitted `ResourceWarning` notices for unclosed SQLite connections; no test or check failed. The startup benchmark recorded 3 cold starts, `0.095s` median wall time, and `32.1 MiB` peak child RSS. These are startup measurements, not task-quality results.

### Phase C — layered memory

- Added additive SQLite-backed working, episodic, semantic, procedural, and user memory layers while keeping `MEMORY.md` and `USER.md` valid and editable.
- Added bounded, labeled context retrieval with provenance, confidence, session-scoped working memory, duplicate consolidation, correction, contradiction handling, expiration, export/import, and idempotent Markdown migration.
- Wrote active objectives and turn episodes from real agent turns, exposed layered memory through `aether memory layer ...`, `/memory layer ...`, and the `memory` tool, and blocked child agents from persistent layered-memory writes.

| Command | Result |
|---|---|
| `python3 -W ignore::ResourceWarning -m unittest tests.test_memory_layers -v` | 11 focused tests passed |
| `python3 -W ignore::ResourceWarning -m unittest discover -s tests -v` | 132 tests passed in `1.007s` |
| `bash scripts/check.sh && bash scripts/test_install.sh && git diff --check` | all commands passed |

Failures found: `test_working_memory_is_session_scoped_and_expires` exposed that already-expired active rows were filtered out before pruning; `LayeredMemory.prune_expired()` now includes expired rows. `test_consolidation_merges_duplicates` exposed an ambiguous tie when confidence and timestamp matched; the test now uses distinct confidence values to verify highest-confidence retention.

Startup benchmarks recorded 3 cold starts, `0.110s` median wall time, and `33.6 MiB` peak child RSS during the implementation run, then `0.095s` and `32.4 MiB` during the final documentation run. These are startup measurements, not task-quality results.

### Phase D — evidence-based learning

- Added `aether/learning/` with sanitized experience records, explicit feedback, evidence-based discovery, deterministic validation, proposal approval/rejection, versioning, rollback, metrics, history, and bounded labeled prompt context.
- Added additive SQLite storage for experiences, proposals, versions, metrics, and learning events while preserving existing tables and rows.
- Wired learning into agent turns, layered memory episodes, context assembly, CLI/slash commands, and status output. Child agents remain isolated from persistent learning writes.
- Kept persistent skill changes explicitly authorized by default; `learning.allow_auto_approve` is opt-in and does not alter tool permissions, approvals, or budgets.
- Added `docs/PHASE_D_LEARNING.md` with the evidence rules, interfaces, security rules, verification record, and limitations.

| Command | Result |
|---|---|
| `python3 -W ignore::ResourceWarning -m unittest tests.test_learning -v` | 21 focused tests passed in `0.554s` |
| `python3 -W ignore::ResourceWarning -m unittest discover -s tests -v` | 153 tests passed in `1.849s` |
| `bash scripts/check.sh && bash scripts/test_install.sh` | all checks passed; local git-remote install test passed |
| `git diff --check` | passed before the implementation commit |

Failures found: the learning test setup shadowed the config helper; proposal helpers did not seed verified experiences; plan IDs were not inferred from plan payloads; `Agent.run_turn()` referenced `usage` before assignment; approved skills wrote an un-dotted version string. These were fixed before the full verification run.

The combined check/install run recorded 3 cold starts, `0.109s` median wall time, and `34.1 MiB` peak child RSS. These are startup measurements, not task-quality results.

### Phase E — capability-aware model routing

- Added an evidence-aware capability registry, a deterministic task classifier, and a scored router with `capability`, `cost`, and `fixed` strategies, explicit model authority, provider health cooldowns, and human-readable explanations.
- Integrated routing into context fitting and overflow recovery: only still-matched tool results are restored and restored text is capped; configured fallbacks remain in the runtime chain.
- Added verified model-performance history via `mark_model_performance_verified()`, role metadata, per-turn child role spend shares that do not mutate the shared budget limit, and model diagnostics that never call models.
- Added `aether models list|inspect|capabilities|routing|explain|performance|health|benchmark` and `/models` slash commands. The benchmark is an offline deterministic routing simulation that prints JSON, makes no model/network/billable calls, and writes no files; `--confirm-billable` is acknowledgement only.
- Added focused coverage for HTTP 400 context-length detection/recovery and orchestrator role preferred/fallback entries.
- Implementation files: `aether/routing/{capabilities,classifier,router}.py`, `aether/core/{context,loop,agent}.py`, `aether/persistence/store.py`, `aether/learning/engine.py`, `aether/providers/registry.py`, `aether/config.py`, `aether/orchestration/{roles,orchestrator}.py`, `aether/cli/app.py`, `benchmarks/model_routing/runner.py`, and `tests/test_model_routing.py`.

| Command | Result |
|---|---|
| `python3 -W ignore::ResourceWarning -m unittest tests.test_model_routing -q` | 26 focused tests passed |
| `python3 -W ignore::ResourceWarning -m unittest discover -s tests -q` | 179 tests passed |
| `bash scripts/check.sh && bash scripts/test_install.sh` | all checks passed; 3 cold starts, median wall time `0.114s`, peak child RSS `34.4 MiB`; local git-remote install test passed |
| `python3 scripts/benchmark.py` | 3 cold starts, median wall time `0.112s`, peak child RSS `34.9 MiB` |
| `git diff --check` | passed |

`ResourceWarning` notices for unclosed SQLite connections are non-failing. No lint/typecheck command is configured, so none is claimed. These timing and memory figures are local startup measurements, not task-quality results. No task-quality benchmark result was recorded, and no Hermes parity or superiority claim is made. See [MODEL_ROUTING.md](MODEL_ROUTING.md), [PHASE_E_BENCHMARKS.md](PHASE_E_BENCHMARKS.md), and [RELEASE_CHECKS.md](RELEASE_CHECKS.md).

## Active work

Phase F — coding workflow — is next. Phase E is implemented on this feature branch; implementation is committed separately from documentation; not pushed, merged, tagged, or released.

## Per-phase record

Record these items before marking any phase complete:

1. files changed
2. observable behavior added or changed
3. focused tests actually run
4. failures found and how they were fixed
5. documentation updates
6. benchmark impact, if any
7. working checkpoint commit hash
8. publication status: never claim push, PR, merge, tag, or release without confirmation

## Publication status

- Push: not attempted.
- Pull request: not created.
- CI: no GitHub Actions workflow exists yet.
- Merge: not attempted.
- Tag: none created.
- Release: none published.

No task-quality benchmark results exist. No Hermes parity or superiority claim is permitted.
