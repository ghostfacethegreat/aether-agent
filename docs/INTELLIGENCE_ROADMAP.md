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
| C | Layered memory | working, episodic, semantic, procedural, and user layers | pending |
| D | Learning loop and skill quality | experience records, skill review, versions, rollback, curator | pending |
| E | Model capability routing | task-aware provider/model selection with existing cost controls | pending |
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

## Phase E — model capability routing

**Likely files:** `aether/providers/capabilities.py`, `aether/providers/catalog.py`, `aether/providers/registry.py`, tests.

**Behavior:**

- registry records coding, reasoning, research, tool calling, structured output, context size, latency, cost, and reliability metadata
- route tasks using requirement signals, configured credentials, and existing fallback order
- keep local and cost-free priority for default operation
- preserve paid confirmation, shared budgets, reservations, and monotonic caps
- validate responses and apply capability-aware retry policies

**Verification:** routing tests with fabricated credentials, no-secret assertions, local-first tests, paid-gating tests, fallback and cooldown tests, response-validation tests.

**Exit state:** routing improves task fit without changing provider contracts or weakening cost controls.

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
