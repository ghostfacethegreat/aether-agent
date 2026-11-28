# AETHER Next-Generation Roadmap

**Project identity:** AETHER  
**Repository:** `ghostfacethegreat/aether-agent`  
**Product direction:** one local-first AI operations and development environment.

This roadmap is the operating plan for consolidating the existing AETHER runtime, model-routing and coding work, the OpenCode specialist team, and VentureOps into one coherent product. It separates what exists from what must still be engineered.

## Product contract

AETHER should be useful on a personal Mac without requiring a paid API, hosted database, or cloud control plane for core local operations. Hosted models and optional integrations remain user-configured. Costs, permissions, and external actions must be visible.

AETHER is an assistant and workflow system, not an unsupervised legal employee, payment processor, security sandbox, or guarantee of income.

## Consolidation status

| Component | Status | Evidence / note |
| --- | --- | --- |
| Local-first agent foundation | Implemented on the integration branch; awaiting review/merge | PR #8 workstream and its exact-head CI evidence. |
| Model capability routing | Implemented on the integration branch; awaiting review/merge | Inspectable routing metadata and tests. |
| Coding workflow | Implemented on the integration branch; awaiting review/merge | Bounded repository index, symbol lookup, diff preview, approval-gated edits and test runner. |
| 13 OpenCode specialist profiles | Implemented as configuration; not background processes | `.opencode/agents/` and `opencode.json`. Requires the owner to start OpenCode. |
| VentureOps local ledger | Initial CLI and SQLite recordkeeping implemented | Uses AETHER's existing `state.db`; no bank feed or payment processing. |
| Safe ANSI artwork loader | Implemented as an optional CLI feature | Bounded UTF-8 artwork, SGR allow-list, stripped cursor/OSC controls, and fallback. |
| Durable background worker service | **Not implemented** | [Issue #5](https://github.com/ghostfacethegreat/aether-agent/issues/5). |
| Isolated Docker execution backend | Planned; must remain optional | No Docker daemon required for core CI or local CLI. |
| Persistent agent dashboard / service | Planned | Must reflect real persisted runs, not simulated worker status. |

## Milestone 0 — Consolidate one AETHER

- Bring the foundation, model-routing, coding workflow, VentureOps ledger, agent profiles, CI, documentation, and safe CLI artwork into the AETHER repository.
- Preserve the unified project identity and remove the obsolete claim that this repository is a legacy predecessor.
- Keep the public default branch stable until the consolidated branch passes checks and review.
- Keep all changes reviewable in a dedicated integration branch and pull request.

**Exit criteria:** one integrated branch, no lost AETHER feature work, a truthful README, passing Linux/macOS CI, and a reviewable diff against `main`.

## Milestone 1 — Durable background execution

**Highest-priority engineering milestone.**

Build the missing bridge between invoked agent profiles and a dependable local workforce.

Requirements:
1. Define an execution-backend interface with local subprocess mode as the no-setup default.
2. Persist run IDs, parent/child relationships, status transitions, structured events, start/end timestamps, bounded retries, and result references.
3. Support queued, running, completed, failed, needs-attention, and cancelled states.
4. Resume interrupted runs safely after AETHER restarts without blindly repeating actions of unknown outcome.
5. Enforce parent/child permission intersections, workspace allow-lists, monotonic spend budgets, timeouts, and cancellation.
6. Bound concurrency and resource usage.
7. Keep worker output as untrusted data; verify completion with recorded tool/test evidence rather than model claims.

Acceptance tests:
- Restart during a queued task and during a running task.
- Recover interrupted runs without duplicate external side effects.
- Cancel parent and child tasks, including races.
- Handle backend unavailable, timeout, partial failure, and unknown step outcomes.
- Reject workspace traversal and unauthorized mount access.
- Verify a child cannot expand permissions, budget, or workspace scope.
- Run all core tests and CI without Docker.

## Milestone 2 — Optional execution isolation

Implement Docker as an opt-in backend only after the execution contract is stable.

- Explicit read-only defaults and workspace mounts.
- No inherited host credentials by default.
- CPU, memory, disk, process, and wall-clock limits.
- Network disabled by default; explicitly scoped egress if needed.
- Clear host/local fallback behavior when Docker is unavailable.
- CI and basic local usage remain Docker-free.

## Milestone 3 — Make the workforce operational

- Define a lead-agent work contract with objective, deliverable, allowed paths/tools, cost ceiling, deadline, and verification criteria.
- Dispatch independent read-only research and review tasks in parallel.
- Route coding tasks to the implementer with scoped edit permissions.
- Require QA and a separate reviewer for code changes.
- Add resumable work queues and a daily owner brief from persisted run records.
- Distinguish configured profiles, invoked agents, active processes, and completed runs in every UI and CLI status view.

## Milestone 4 — Strengthen VentureOps

- Add export/import and tested deletion workflows for owner records.
- Add source provenance and date-checked lead research records.
- Add scoped workspaces for offers, client work, and deliverables.
- Add draft-only proposal and customer-success workflows.
- Add rights/quality gates for media and customer deliverables.
- Keep receipts separate from estimates, quotes, invoices, and pipeline values.
- No automatic outreach, publishing, payment, transfers, purchases, or account changes.

## Milestone 5 — Evaluation and release hardening

- Add fixed task fixtures and mock-provider quality tests.
- Add opt-in live-model evaluation with model, provider, token, latency, and cost metadata.
- Store reproducible raw results and regression baselines.
- Test prompt injection, secret redaction, permissions, cancellation, retries, and restart recovery.
- Run clean-checkout install tests on supported Python and macOS versions.
- Do not claim agent quality, safety, or provider parity from CI alone.

## Working rules

- One focused issue/branch per milestone.
- Inspect the current source and tests before editing.
- Add regression tests with every behavioral change.
- Run focused tests, full tests, install checks, and `git diff --check`.
- Use the mock provider in ordinary CI; live model tests are opt-in.
- Never use a paid model or service without owner approval.
- No merges, release tags, or releases until the exact head is reviewed and verified.
- Do not report a configured profile as a running process or a task as complete without recorded execution evidence.
