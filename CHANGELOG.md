# Changelog

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
