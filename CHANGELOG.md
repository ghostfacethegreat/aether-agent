# Changelog

## Unreleased

### Added
- Add a bounded local repository index/search tool with root .gitignore handling and generated/vendor, symlink, binary, and size exclusions.
- Add unified-diff preview and approval-gated patch application with full preflight, path protections, existing-file-only policy, and rollback attempt on filesystem errors.
- Add fixed-argument repository test runner for unittest suite/module, compileall, and scripts/check.sh; include successful test_run evidence in independent verification.

### Changed
- Developer, debugger, tester, and verifier roles can use the repository coding workflow; patch writes and test execution require approval.


### Added
- Load bounded repository-root project context from AGENTS.md and compatible instruction files with symlink, traversal, binary, encoding, and size protections.
- Add structured specialist-output contracts and an independent-verification gate based on the verifier's own successful test/check tool evidence.
- Expand automatic dependency-aware orchestration across planner, researcher, architect, developer, debugger, tester, security auditor, verifier, reviewer, analyst, and documentation roles.
- Add a Python 3.10–3.14 GitHub Actions matrix and scoped Copilot custom-agent workstream profiles.

### Changed
- Implementation, debugging, and documentation workflows include a separate verifier; unverified work remains partial instead of being reported as fully verified.



### Added
- Load bounded repository-root project context from AGENTS.md and compatible instruction files with symlink, traversal, binary, encoding, and size protections.
- Add structured specialist-output contracts and an independent-verification gate based on the verifier's own successful test/check tool evidence.
- Expand automatic dependency-aware orchestration across planner, researcher, architect, developer, debugger, tester, security auditor, verifier, reviewer, analyst, and documentation roles.
- Add a Python 3.10–3.14 GitHub Actions matrix and scoped Copilot custom-agent workstream profiles.

### Changed
- Implementation, debugging, and documentation workflows include a separate verifier; unverified work remains partial instead of being reported as fully verified.



### Changed
- Refresh the interactive CLI with an acid-blue 3D-style masthead, framed session overview, labeled streamed responses, and a clearer prompt.
- Add configurable terminal themes and ASCII/NO_COLOR fallbacks without adding runtime dependencies.
- Document the TAAG/TheDraw inspiration and font redistribution limitation.


## Phase E capability-aware model routing

- Added an evidence-aware capability registry with capability, context-window, pricing, source, and freshness facts; unknown facts and prices remain unknown.
- Added a deterministic task classifier and a scored router with `capability`, `cost`, and `fixed` strategies, explicit provider/model authority, provider health cooldowns, and inspectable explanations.
- Integrated routing with context fitting and overflow recovery that preserves the objective, restores only still-matched tool results, caps restored tool text, and retries the same provider once; configured fallbacks remain in the runtime chain.
- Added verified model-performance history with `mark_model_performance_verified()`, role metadata, and per-turn child role spend shares that do not mutate the shared budget limit.
- Added `aether models list|inspect|capabilities|routing|explain|performance|health|benchmark` and `/models` diagnostics that never call models; there is no `routing.manual` setting.
- Added an offline deterministic routing benchmark that prints JSON without model, network, or billable calls or file writes; `--confirm-billable` is acknowledgement only. It is not a task-quality or Hermes-comparison result.
- Verified locally with 26 focused routing tests, including HTTP 400 context-length detection/recovery and orchestrator role preferred/fallback entries, and 179 total tests. `bash scripts/check.sh && bash scripts/test_install.sh` passed with 3 cold starts, median wall time `0.114s`, peak child RSS `34.4 MiB`, and a local git-remote install test pass. `python3 scripts/benchmark.py` recorded 3 cold starts, median wall time `0.112s`, and peak child RSS `34.9 MiB`. `git diff --check` passed. `ResourceWarning` notices for unclosed SQLite connections are non-failing; no lint/typecheck command is configured.
- Documented the behavior in `docs/MODEL_ROUTING.md`, `docs/PHASE_E_BENCHMARKS.md`, `docs/PHASE_E_ARCHITECTURE.md`, and `docs/RELEASE_CHECKS.md`. Package version remains `0.1.0`.

## Phase D evidence-based learning

- Added sanitized experience records from real turns, with explicit feedback and deterministic evidence rules that do not treat model claims or successful tool calls as completion proof.
- Added evidence-based skill discovery, proposal storage, deterministic validation, explicit approval/rejection, skill installation, version history, rollback, metrics, and learning events.
- Added additive SQLite tables for experiences, proposals, versions, metrics, and learning events without rewriting existing state.
- Added bounded, labeled learning context to prompts and disabled persistent learning writes in child agents.
- Added `aether skills discover|proposals|validate|approve|reject|history|versions|rollback|result`, `aether learning pending|metrics|feedback`, `/skills` learning actions, and `/feedback`.
- Added deterministic tests for evidence rules, discovery, validation, security checks, approval, persistence, improvement, rollback, agent turns, child isolation, CLI, and slash commands; all local checks pass.
- Documented the learning contract in `docs/PHASE_D_LEARNING.md`.

## Phase C layered memory

- Added additive SQLite-backed working, episodic, semantic, procedural, and user memory layers.
- Added bounded, labeled recall with provenance, confidence, and source labels.
- Added semantic correction and contradiction handling, duplicate consolidation, expiration, deletion controls, export/import, and idempotent Markdown migration.
- Recorded active objectives and turn outcomes from real agent turns while keeping existing `MEMORY.md` and `USER.md` valid.
- Added `aether memory layer ...`, `/memory layer ...`, and `memory` tool layer actions with child write isolation.
- Added deterministic recall, provenance, migration, retention, isolation, persistence, and CLI tests; all local checks pass.

## Phase B adaptive planning and execution state

- Added deterministic request classification for simple, moderate, complex, and high-risk work, with inspectable routes and risk notes.
- Added plan records with objective, constraints, risk assessment, alternatives, task dependencies, required tools, expected results, verification criteria, revision history, and resume context.
- Added an execution state machine and SQLite-backed plan/checkpoint persistence.
- Wired plan state into turns so tool results update task status and checkpoint status is emitted.
- Added `plan_tool`, `aether plan list|show|status|checkpoints|resume`, and `/plan status|checkpoints|resume <id>|text`.
- Added resume behavior that skips completed and non-idempotent work and records repairs when evidence invalidates a plan.
- Added deterministic planner, persistence, and agent integration tests; all local checks pass.

## Phase A intelligence audit (documentation checkpoint)

- Changed the 0.2+ priority from visual work to intelligence-first work: planning, memory, learning, model routing, coding, research, tool selection, orchestration, verification, recovery, and measured task success.
- Froze terminal appearance: existing ASCII artwork and colored rendering are preserved; themes, font tooling, animations, and visual redesigns are out of scope unless fixing a functional regression.
- Added [INTELLIGENCE_AUDIT.md](docs/INTELLIGENCE_AUDIT.md), [INTELLIGENCE_ROADMAP.md](docs/INTELLIGENCE_ROADMAP.md), and [HERMES_COMPARISON.md](docs/HERMES_COMPARISON.md) with source-evidenced gaps, adoption decisions, and phases A-L.
- Added benchmark protocol scaffolding under [benchmarks/README.md](benchmarks/README.md) with no result claims.
- Superseded the visual-first 0.2 plans in the baseline, architecture, and roadmap documents while retaining them as historical provenance.
- Refreshed the Hermes comparison evidence to current `main` at `fe9a4b58ec137d3e00719c10e2385876fa03b97c`; no runtime behavior changed and no parity or superiority claim is made.

## Phase 4 security and reliability audit

- Linked parent cancellation into orchestrated runs, propagated task cancellation into child turns and tool execution, and made timeout/cancel paths stop child work between provider/tool operations.
- Made retries skip attempts that already executed tools, tightened per-turn usage attribution, persisted orchestration child usage, and enforced cost caps with locked monotonic limits.
- Hardened approval caching so `once` applies to one action, scoped approvals to canonical argument keys, and made nested agents inherit mandatory deny/approval rules.
- Restricted child skill mutations, delimited untrusted dependency data, parsed paid-provider confirmations strictly, and disabled orchestration inside scheduled runs.
- Made stored-run cancellation update child task rows, persisted orchestration runs atomically, removed the fixed task lookup limit, and prevented duplicate subagent resume records.
- Added regression coverage for all audit fixes.

## Phase 3 multi-agent orchestration

- Added a central `Orchestrator` with role-based plans, dependency ordering, sequential/parallel execution, retries, cancellation, timeouts, and persistent run/task recovery.
- Added specialized `researcher`, `developer`, `debugger`, and `reviewer` roles with structured result parsing and owner-protected shared task state.
- Added shared spend budgets, nested budget tightening, paid-child gating, strict child permissions, and child denials for orchestration/delegation tools.
- Added the `orchestrate_task` tool and `aether agents` / `/agents` commands for listing roles, running tasks, viewing status, cancelling tasks, and resuming stored runs.
- Added mock-provider regression tests for orchestration lifecycle, concurrency, isolation, communication, budgets, cancellation, timeouts, permissions, recovery, and failure handling.

## Phase 2 audit (documentation checkpoint)

- Refreshed the Hermes Agent comparison baseline to commit `b98c388a880b1b6fd303c9c2821a3946651a0b4c`.
- Added a source-evidenced comparison of all 14 requested capability areas against Aether commit `bdbe2462dda3c4646086385d600b4e2ab23f4957`.
- Added a ranked gap register and staged milestone plan with separate commit boundaries.
- Corrected feature-matrix entries that overstated tool replay reliability, subagent durability, session recovery, and skill curation completeness.
- Published the repository at <https://github.com/ghostfacethegreat/aether-agent>; no hosted installer URL was published.

## Phase 2 Milestone 2.1

- Preserved tool-call names, IDs, and arguments across SQLite persistence and session resume.
- Added context repair for orphaned tool results and missing tool-result placeholders after compression.
- Fixed Anthropic replay conversion for nested OpenAI-style tool call fields.
- Added regression tests for store round trip, resume history, context repair, and Anthropic tool-call replay.

## Phase 2 Milestone 2.2

- Enforced per-tool timeouts in the executor with tool-specific ceilings for terminal, Python, git, browser, and network work.
- Rejected private, loopback, link-local, and credential-bearing URL targets, including redirects.
- Redacted secrets from model-facing tool results as well as tool logs.
- Extended path-root validation to terminal `cwd`, git `paths`, and other explicit path arguments.
- Added regression tests for timeout denial, private URL/redirect rejection, secret redaction, and path escapes.

## Phase 2 Milestone 2.3

- Made scheduled ticks run due prompts through a real local runner and report due, executed, skipped, and failed outcomes.
- Added job claiming before execution, one-shot disabling, and a local execution ledger at `cron/executions.jsonl`.
- Added scheduler update, pause, resume, and cancel controls to the CLI and slash commands.
- Blocked scheduled execution with paid or custom providers unless `scheduler.allow_paid` is enabled.
- Added regression tests for execution, skips, failures, restart no-refire, thread start/stop, and CLI summary output.

## 0.1.0 (unreleased alpha)

- Audited public Hermes Agent architecture and provider/security patterns.
- Added provider-agnostic core with OpenAI-compatible, Anthropic, and mock transports.
- Added SQLite session/task/usage persistence.
- Added Markdown-backed memory and `SKILL.md` skills.
- Added tool registry, permission policy, approvals, and tool executor.
- Added context budgeting, prompt assembly, phase-oriented turn loop, and provider fallback.
- Added subagents and in-process scheduler.
- Added CLI with interactive chat, slash commands, setup, providers, config, doctor, sessions, memory, skills, tasks, schedule, run, update, and version commands.
- Added standard-library-only packaging and tests.
