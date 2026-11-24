# Aether Intelligence Roadmap

This roadmap supersedes the visual-first `Aether 0.2.0` phase list with an intelligence-first `Aether 0.2+` program. The goal is to make Aether better at understanding objectives, planning, remembering, learning, coding, researching, coordinating, verifying, and recovering. Terminal appearance is frozen: preserve the existing ASCII artwork and colored rendering, fix functional visual regressions only, and do not add themes, a theme selector, font tooling, animations, or a renderer rewrite without a demonstrated functional or performance bug.

Evidence and gaps are in [INTELLIGENCE_AUDIT.md](INTELLIGENCE_AUDIT.md). The source-evidenced competitor comparison is in [HERMES_COMPARISON.md](HERMES_COMPARISON.md). Benchmark rules are in [benchmarks/README.md](../benchmarks/README.md).

## Operating principles

1. Improve the existing core; do not rewrite Aether from scratch.
2. Keep runtime stdlib-only, local-first, and practical on an 8 GB Apple Silicon Mac.
3. Treat "self-improvement" as an evidence pipeline, not a claim that the model is always right.
4. Never ask for or assume hidden chain-of-thought. Use inspectable plans, checks, and evidence.
5. Adaptive by complexity: simple requests stay fast; risky or ambiguous work gains planning, verification, and approval.
6. Delegate only when parallelism or independent expertise improves the result.
7. No provider lock-in, no unlimited-free claims, no paid spend without existing confirmation rules.
8. Keep files, tool output, web pages, and other agents' results as untrusted data.
9. Do not claim superiority over Hermes or any other agent without benchmark results produced under the same conditions.
10. Each implementation phase gets focused deterministic tests, full local checks, documentation updates, and a separate working checkpoint commit.

## Phase map

| Phase | Name | Main outcome | Status |
|---|---|---|---|
| A | Intelligence audit and benchmark contract | evidence, gap register, comparison, benchmark rules | complete at `d077948` |
| B | Adaptive planning and execution state | inspectable plans, complexity routing, recoverable checkpoints | complete and locally verified |
| C | Layered memory | working, episodic, semantic, procedural, and user layers | complete and locally verified |
| D | Learning loop and skill quality | experience records, skill review, versions, rollback, curator | complete and locally verified |
| E | Model capability routing | task-aware provider/model selection with existing cost controls | implemented on this feature branch and locally verified (26 focused / 179 total tests); not released |
| F | Coding workflow | repository indexing, progressive retrieval, patches, tests, diff review | pending |
| G | Research and evidence | query planning, sources, citations, contradictions, confidence | pending |
| H | Tool intelligence | capability search, preflight, result verification, analytics | pending |
| I | Specialist orchestration | larger role catalog, team selection, verifier, conflict handling | pending |
| J | Verification and recovery | independent completion checks, repair loops, long-running resume | pending |
| K | Benchmark harness | reproducible task runs, scoring, stored evidence, comparisons | pending |
| L | Release hardening | docs, tests, CI, versioning, release candidate checks | pending |

## Phase A — intelligence audit and benchmark contract

**Goal:** replace guesses with a source-evidenced baseline before runtime changes.

**Scope:**

- audit current Aether source, tests, docs, and performance record
- audit Hermes at pinned commit `b98c388a880b1b6fd303c9c2821a3946651a0b4c` and current `main` at `fe9a4b58ec137d3e00719c10e2385876fa03b97c`
- record gaps and adoption decisions
- define fair benchmark categories, controls, metrics, and result schema
- mark visual-first 0.2 plans as historical

**Exit state:** documentation-only checkpoint; no runtime behavior changed.

## Phase B — adaptive planning and execution state

**Likely files:** `aether/core/planning.py`, `aether/core/state.py`, `aether/core/loop.py`, `aether/core/agent.py`, `aether/tools/builtins.py`, tests.

**Behavior:**

- classify work as simple, moderate, complex, or high-risk
- produce an inspectable plan with objective, constraints, tasks, dependencies, tools, expected results, and verification criteria
- route simple requests directly; use plan/execute/verify for moderate work; research/delegate/execute/test/review for complex work; add approval for high-risk work
- maintain an execution-state machine with checkpoints and resumable status
- revise plans when tests, tool results, or user feedback invalidate assumptions

**Verification:** deterministic planner tests, state-transition tests, checkpoint resume tests, cancellation and cost-limit behavior tests, full checks.

**Exit state:** the same objective can pause and resume without repeating completed or non-idempotent work.

### Phase B result

- Implemented in `aether/core/planning.py` and `aether/core/state.py`, with persistence in `aether/persistence/store.py`, turn integration in `aether/core/loop.py`, agent wiring in `aether/core/agent.py`, tool/CLI exposure in `aether/tools/builtins.py` and `aether/cli/app.py`, and deterministic tests in `tests/test_planning.py`.
- Plans now record objective, constraints, risk assessment, alternatives, task dependencies, required tools, expected results, verification criteria, revision history, and resume context.
- Focused verification: 48 tests passed in `tests.test_planning`, `tests.test_core`, `tests.test_persistence`, and `tests.test_cli`.
- Full verification: 121 tests passed; `scripts/check.sh`, `scripts/test_install.sh`, and `git diff --check` passed.
- Failure fixed: repair tasks are now prioritized by `ExecutionPlan.next_task()` after `test_revision_records_invalidating_evidence` exposed the ordering bug.
- Startup benchmark after the code checkpoint: 3 cold starts, `0.095s` median wall time, `32.1 MiB` peak child RSS; no task-quality benchmark was run.
- Phase B checkpoint commit: `9aef0fb873f6e54bc78f7b587e3fe8709dc07c55`.
- Detailed commands and limitations are in [RELEASE_CHECKS.md](RELEASE_CHECKS.md) and [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

## Phase C — layered memory

**Likely files:** `aether/memory/store.py`, `aether/persistence/store.py`, new memory modules, tests.

**Behavior:**

- working memory for active objectives and facts
- episodic memory for sessions, tasks, outcomes, and failures
- semantic memory for stable facts with provenance, confidence, and contradiction handling
- procedural memory for verified reusable procedures
- explicit user model separate from general notes
- retrieval by task need with bounded context and source labels
- consolidation, duplicate detection, correction, expiration, export/import, and deletion controls

**Verification:** recall/relevance tests, bounded-context tests, provenance and contradiction tests, migration tests for existing `MEMORY.md` and `USER.md`, child isolation tests.

**Exit state:** existing Markdown memory remains valid, while richer memory is available through additive storage.

### Phase C result

- Checkpoint commit: `833cad8f4bbdea74241c4d18f3719c77755ad7c1`.
- Implemented in `aether/memory/layers.py`, `aether/persistence/store.py`, `aether/config.py`, `aether/core/agent.py`, `aether/cli/app.py`, `aether/tools/builtins.py`, and `tests/test_memory_layers.py`.
- Existing `MEMORY.md` and `USER.md` entries migrate idempotently into semantic and user layers with source labels; the original Markdown files remain the editable baseline.
- Turn integration records the active objective in working memory and an outcome/failure episode after each persistent turn; child agents cannot write layered memory.
- Focused verification: 11 tests passed in `tests.test_memory_layers`.
- Full verification: 132 tests passed; `scripts/check.sh`, `scripts/test_install.sh`, and `git diff --check` passed.
- Failure fixed: `LayeredMemory.prune_expired()` now includes already-expired active rows instead of relying on the default active-row filter.
- Startup benchmarks after the Phase C work: 3 cold starts, `0.110s` median wall time and `33.6 MiB` peak child RSS during implementation, then `0.095s` and `32.4 MiB` during the final documentation run; no task-quality benchmark was run.
- Detailed commands and limitations are in [RELEASE_CHECKS.md](RELEASE_CHECKS.md) and [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

## Phase D — learning loop and skill quality

**Likely files:** `aether/learning/`, `aether/skills/engine.py`, `aether/persistence/store.py`, tests.

**Behavior:**

- experience records capture objective, plan, tools used, tests, failures, feedback, and outcome
- promote repeated successful procedures into candidate skills only with evidence
- review skill quality before persistent changes
- preserve previous versions and support rollback
- record a searchable learning history
- require approval for persistent instruction or user-model changes
- never let web content or untrusted files modify trusted instructions or skills

**Verification:** evidence-rule tests, candidate-skill tests, version/rollback tests, untrusted-content tests, approval tests, learning-history search tests.

**Exit state:** skills can improve from observed outcomes without unverified self-claims becoming trusted instructions.

### Phase D result

- Implementation checkpoint: `0dc4118af627cb2c5de4daac0a8ed4e3512705cf`.
- Added `aether/learning/models.py` and `aether/learning/engine.py`, with additive SQLite tables for experiences, proposals, versions, metrics, and learning events.
- Experience records omit raw tool arguments and results, redact text, and require deterministic or explicit user evidence for verified outcomes.
- Discovery proposes skills only from repeated verified experiences; validation checks structure, tools, permissions, secrets, injection patterns, examples, and improvement regressions.
- Approval, rejection, rollback, and installation remain explicit by default. Child agents cannot persist learning records or skills.
- Added CLI commands for `skills discover|proposals|validate|approve|reject|history|versions|rollback|result` and `learning pending|metrics|feedback`, plus `/skills` learning actions and `/feedback`.
- Focused verification: 21 tests passed in `tests.test_learning`.
- Full verification: 153 tests passed; `scripts/check.sh`, `scripts/test_install.sh`, and `git diff --check` passed.
- Failures fixed: config helper shadowing in tests, missing verified seeds in proposal helpers, missing plan-ID inference, premature `usage` access in `Agent.run_turn()`, and un-dotted approved skill version headers.
- Startup benchmarks after Phase D: 3 cold starts, `0.109s` median wall time, and `34.1 MiB` peak child RSS; no task-quality benchmark was run.
- Details and limitations are in [PHASE_D_LEARNING.md](PHASE_D_LEARNING.md), [RELEASE_CHECKS.md](RELEASE_CHECKS.md), and [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

## Phase E — model capability routing

**Implemented files:** `aether/routing/{capabilities,classifier,router}.py`, `aether/core/{context,loop,agent}.py`, `aether/persistence/store.py`, `aether/learning/engine.py`, `aether/providers/registry.py`, `aether/config.py`, `aether/orchestration/{roles,orchestrator}.py`, `aether/cli/app.py`, `benchmarks/model_routing/runner.py`, and `tests/test_model_routing.py`.

**Behavior:**

- evidence-aware capability registry with context windows, capability facts, prices, source, and freshness
- deterministic task classifier producing category, complexity, context needs, tool requirements, and explicit provider/model authority
- scored router with `capability`, `cost`, and `fixed` strategies, explicit model authority, health cooldowns, and explanations
- context fitting from capability windows with overflow recovery that restores only still-matched tool results and caps restored text, including HTTP 400 context-length detection/recovery
- verified model-performance history via `mark_model_performance_verified()`, role metadata, and per-turn child role spend shares that do not mutate the shared budget limit
- offline diagnostic commands that never call models; configured fallbacks remain in the runtime chain, and orchestrator role preferred/fallback entries are recognized as configured entries

**Verification:** 26 deterministic tests in `tests.test_model_routing` and 179 tests in the full suite.

**Exit state:** routing offers inspectable task fit without changing provider contracts or weakening cost controls. No task-quality improvement is claimed.

### Phase E result

- Implemented on this feature branch; implementation is committed separately from documentation; not pushed, merged, tagged, or released.
- Focused verification: `python3 -W ignore::ResourceWarning -m unittest tests.test_model_routing -q` — 26 tests passed, including HTTP 400 context-length detection/recovery and orchestrator role preferred/fallback entries.
- Full verification: `python3 -W ignore::ResourceWarning -m unittest discover -s tests -q` — 179 tests passed.
- `bash scripts/check.sh && bash scripts/test_install.sh` — all checks passed; 3 cold starts, median wall time `0.114s`, peak child RSS `34.4 MiB`; local git-remote install test passed.
- `python3 scripts/benchmark.py` — 3 cold starts, median wall time `0.112s`, peak child RSS `34.9 MiB`.
- `git diff --check` — passed.
- `ResourceWarning` notices for unclosed SQLite connections are non-failing; no lint/typecheck command is configured, so none is claimed. Timing and memory figures are local startup measurements, not task-quality results.
- Added `aether models list|inspect|capabilities|routing|explain|performance|health|benchmark` and `/models` commands. The benchmark is an offline deterministic routing simulation that prints JSON, makes no model/network/billable calls, and writes no result artifact; `--confirm-billable` is acknowledgement only.
- Details and limitations are in [MODEL_ROUTING.md](MODEL_ROUTING.md), [PHASE_E_BENCHMARKS.md](PHASE_E_BENCHMARKS.md), and [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

## Phase F — coding workflow

**Likely files:** `aether/coding/`, `aether/tools/builtins.py`, orchestrator developer/debugger roles, tests.

**Behavior:**

- build a lightweight repository index and symbol/dependency lookup
- retrieve files progressively instead of loading whole repositories indiscriminately
- use patch-based edits with reviewable before/after changes
- connect edits to focused tests, regression checks, and diff review
- record checkpoints before risky changes
- require the verifier to inspect actual files, tests, and command output before completion

**Verification:** fixture-repository tests, index freshness tests, patch application/rollback tests, test-selection tests, diff-review tests, regression-detection tests.

**Exit state:** coding tasks produce reviewed diffs and tested claims, not just file writes.

## Phase G — research and evidence

**Likely files:** `aether/research/`, web tools, memory integration, verifier integration, tests.

**Behavior:**

- decompose research questions into queries and source types
- compare multiple sources and extract citations
- detect contradictions and missing evidence
- separate verified evidence, inference, unknown information, and conflicting sources
- report confidence without implying certainty
- treat all retrieved pages as untrusted data

**Verification:** fixture-source tests, citation extraction tests, contradiction tests, source-quality tests, injection tests, confidence-reporting tests.

**Exit state:** research answers are traceable to sources and honest about uncertainty.

## Phase H — tool intelligence

**Likely files:** `aether/tools/registry.py`, `aether/tools/executor.py`, `aether/tools/permissions.py`, tests.

**Behavior:**

- add capability descriptions and search/deferred schema discovery
- validate required arguments and side-effect expectations before execution
- classify errors and permit only safe retries
- verify tool results before promoting them to facts
- record usage analytics for planner and learning feedback
- keep approvals, strict roots, timeout ceilings, redaction, and cancellation intact

**Verification:** schema-deferral tests, preflight tests, non-idempotent retry-denial tests, error-classification tests, result-verification tests, permission regression tests.

**Exit state:** the planner can choose and validate tools without bloating every prompt or weakening safety.

## Phase I — specialist orchestration

**Likely files:** `aether/orchestration/roles.py`, `aether/orchestration/team.py`, `aether/orchestration/orchestrator.py`, `aether/orchestration/state.py`, tests.

**Behavior:**

- expand to at least 18 meaningful roles, including Planner, Architect, Frontend developer, Backend developer, Tester, Security auditor, Documentation writer, Data analyst, DevOps engineer, Performance engineer, Product analyst, Automation engineer, Release manager, and Verifier
- select teams from objective evidence while explicit roles always win
- expose team rationale through status output
- give each role a distinct prompt, output contract, tool policy, approval requirements, and budget
- add conflict resolution and independent review
- strictly inherit budget, permissions, approvals, cancellation, timeouts, and recursion/resource limits

**Verification:** role catalog tests, selection tests, explicit-override tests, contract validation tests, forced-rule tests, cap tests, conflict-resolution tests.

**Exit state:** specialist agents perform real, bounded work and the verifier can reject incomplete results.

## Phase J — verification and recovery

**Likely files:** `aether/verification/`, `aether/core/loop.py`, orchestrator integration, persistence, tests.

**Behavior:**

- verify completion against the original objective and plan
- check changed files, tests, evidence, citations, and requirement coverage
- repair failed or missing work with bounded revision loops
- support durable long-running goals with event-driven resume
- never invent progress or silently exceed spending limits
- preserve cancellation and approval semantics across all recovery paths

**Verification:** requirement-coverage tests, evidence-trace tests, repair-loop tests, long-task resume tests, cancellation and budget regression tests.

**Exit state:** completion claims require observed evidence and failed work can resume safely.

## Phase K — benchmark harness

**Likely files:** `benchmarks/`, runner modules, task fixtures, result artifacts.

**Behavior:**

- implement the controls and metrics in [benchmarks/README.md](../benchmarks/README.md)
- cover reasoning, coding, debugging, research, long-context retrieval, memory, tool calling, multi-step execution, recovery, learning, multi-agent work, and cost/efficiency
- record model, provider, prompt, tools, workspace, budget, time, result, and evidence for every run
- store results under `benchmarks/results/`; never fabricate or overwrite evidence
- compare Aether and Hermes only under identical conditions

**Verification:** runner tests with mock provider, fixture determinism tests, score calculation tests, result-schema tests, no-secret tests.

**Exit state:** reproducible runs produce inspectable result files that support or refute performance claims.

## Phase L — release hardening

**Likely files:** version files, README, changelog, security docs, CI, release checks.

**Behavior:**

- update public docs to describe implemented intelligence behavior only
- keep visual notes limited to preserving existing ASCII artwork and colored rendering
- add CI for compile, tests, smoke checks, secret scan, link check, and benchmark if deterministic
- run install/uninstall tests and full checks
- verify no secrets, tokens, `.env` files, or generated credentials are committed
- issue release notes with exact commands run and exact results observed

**Verification:** full local checks, real CI results, install test, fresh-clone smoke test, `git diff --check`.

**Exit state:** an honest release checkpoint that makes no parity or superiority claim without benchmark evidence.

## Visual freeze

The following are explicitly out of scope for `Aether 0.2+` unless a functional defect is demonstrated:

- replacing or regenerating the existing ASCII artwork
- adding a theme system or theme selector
- adding font registration, random font selection, or font preview commands
- adding animated title sequences
- rebuilding the dashboard or agent graph as a visual project
- changing branding assets for visual novelty

Renderer work is allowed only to fix a functional regression, preserve readability, sanitize untrusted text, or repair output that interferes with task execution. Such changes still require tests and must preserve the existing ASCII identity.

## Per-phase contract

Every implementation phase must record:

1. files changed
2. observable behavior added or changed
3. focused tests actually run
4. failures found and how they were fixed
5. documentation updates
6. benchmark impact, if any
7. a working checkpoint commit

Do not mark a phase complete from static inspection alone. Do not push, merge, tag, or release until verification and reporting are complete.
