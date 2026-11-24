# Aether 0.2+ Additive Architecture

This document maps the current Aether implementation and identifies safe extension points for the intelligence-first `Aether 0.2+` program. It is intentionally additive: the working 0.1.0 core remains the source of truth, and new reasoning, memory, learning, routing, coding, research, coordination, and verification capabilities are layered onto it without replacing working behavior.

Terminal appearance is frozen. Preserve the existing ASCII artwork and colored rendering, fix functional visual regressions only, and do not add themes, a theme selector, font tooling, animations, or a renderer rewrite without a demonstrated functional or performance bug.

The original design audit remains in [ARCHITECTURE.md](ARCHITECTURE.md). The verified capability inventory is in [AETHER_02_BASELINE.md](AETHER_02_BASELINE.md). Current evidence and gaps are in [INTELLIGENCE_AUDIT.md](INTELLIGENCE_AUDIT.md), implementation order in [INTELLIGENCE_ROADMAP.md](INTELLIGENCE_ROADMAP.md), and the source-evidenced Hermes comparison in [HERMES_COMPARISON.md](HERMES_COMPARISON.md).

## Current runtime map

```text
CLI (aether.cli.app)
  |
  +-- config / home / environment
  +-- renderer (aether.cli.render)                 [appearance frozen]
  +-- Agent (aether.core.agent)
        |
        +-- ContextManager (aether.core.context)
        +-- ProviderManager (aether.providers)
        |     +-- catalog / cost pricing
        |     +-- mock, OpenAI-compatible, Anthropic transports
         +-- Turn loop (aether.core.loop)
         |     +-- cost preflight / shared budget
         |     +-- cancellation / fallbacks / iteration bound
         +-- LearningEngine (aether.learning)
         |     +-- experience records / evidence rules
         |     +-- proposals / validation / versions / rollback
         +-- Tool registry + executor + permissions

        |     +-- file, terminal, git, Python, web, memory, skills, tasks
        +-- MemoryStore (Markdown)
        +-- SkillEngine (SKILL.md)
         +-- Store (SQLite: sessions, messages, tasks, usage, approvals, plans, memory layers, learning records)

        +-- SubagentManager
        +-- Orchestrator
              +-- roles
              +-- SharedTaskState
              +-- dependency plan / workers / retries / timeouts
              +-- persisted runs and task snapshots
        +-- Scheduler
```

## Source map and intelligence extension points

| Area | Files | Current role | 0.2+ extension approach |
|---|---|---|---|
| CLI parsing and dispatch | [../aether/cli/app.py](../aether/cli/app.py) | argument parser, command handlers, slash commands, streaming callbacks, scheduler wiring | Add status/report commands only where needed for plans, learning history, and benchmarks; keep existing command names and semantics. |
| Terminal rendering | [../aether/cli/render.py](../aether/cli/render.py) | ANSI colors, banner, dashboard, tables, tool lines, status lines, spinner | Freeze appearance; sanitize untrusted text and fix functional output issues only. |
| Core wiring | [../aether/core/agent.py](../aether/core/agent.py) | constructs and connects all subsystems; builds children | Keep constructor compatibility; add optional planner, state, verifier, memory, and learning hooks. |
| Turn loop | [../aether/core/loop.py](../aether/core/loop.py) | bounded provider/tool loop, cost/cancellation/usage | Move toward a phase-oriented state machine with checkpoints, plan revision, and verification events; preserve cost and cancellation behavior. |
| Context | [../aether/core/context.py](../aether/core/context.py) | prompt assembly and context fitting | Add bounded retrieval by task need, source labels, and progressive tool/file selection. |
| Providers | [../aether/providers/](../aether/providers/) | catalog, registry, transports, cost functions | Add a task capability registry and advisory routing while retaining provider names, fallback APIs, and cost controls. |
| Tools | [../aether/tools/](../aether/tools/) | registry, executor, permissions, built-ins | Add capability descriptions, optional schema deferral, preflight, result verification, error classification, and usage analytics without weakening approvals. |
| Memory | [../aether/memory/store.py](../aether/memory/store.py) | Markdown memory files and prompt context | Add layered memory and retrieval as additive methods/options; preserve `MEMORY.md` and `USER.md`. |
| Skills | [../aether/skills/engine.py](../aether/skills/engine.py) | `SKILL.md` discovery, validation, usage tracking, explicit install | Evidence rules, proposals, versions, rollback, and audit history are now additive; preserve existing skill files and child-write isolation. |
| Learning | [../aether/learning/](../aether/learning/) | new in Phase D | Keep verified evidence separate from model claims, validate before install, require explicit approval, and keep learning context labeled as data. |
| Persistence | [../aether/persistence/store.py](../aether/persistence/store.py) | SQLite schema and data access | Additive tables now cover plans, memory layers, experiences, proposals, versions, metrics, and learning events; never destructively rewrite existing state. |
| Orchestration | [../aether/orchestration/](../aether/orchestration/) | roles, task graph, shared state, run persistence | Expand the role catalog, add team selection and conflict handling, and integrate the independent verifier. |
| Subagents | [../aether/tasks/subagents.py](../aether/tasks/subagents.py) | parallel isolated children | Preserve delegation behavior; add output contracts and explicit delegation rationale while enforcing resource limits. |
| Scheduler | [../aether/tasks/scheduler.py](../aether/tasks/scheduler.py) | in-process due jobs and ledger | Preserve strict paid-provider and no-orchestration restrictions; add durable goal/resume support separately. |
| Config | [../aether/config.py](../aether/config.py) | typed dotted defaults and validation | Add 0.2+ settings with safe defaults; keep old configs valid. |
| Tests | [../tests/](../tests/) | stdlib `unittest` suite with mock provider | Add deterministic tests per milestone; keep the existing suite green. |
| Benchmarks | [../benchmarks/README.md](../benchmarks/README.md) | benchmark protocol and scaffolding | Implement deterministic runner, task fixtures, score calculations, and immutable result artifacts. |

## Turn lifecycle

Current lifecycle:

1. `main()` parses global options and the optional subcommand.
2. `prepare()` loads environment, config, provider/model overrides, logging, and home.
3. `cmd_chat()` or `cmd_run()` constructs an `Agent`.
4. `Agent.run_turn()` builds the system prompt from config, memory, skills, and plan.
5. `run_turn_loop()` fits context, calls providers, checks paid/cost rules, executes tools, and accumulates usage.
6. Stream deltas, tool lines, and status events reach the CLI callbacks.
7. `Agent` appends new messages and usage to SQLite when persistence is enabled.
8. `TurnResult` carries text, usage, tool log, exit reason, and messages to the caller.

Target lifecycle:

```text
objective -> complexity signal -> plan -> execute step -> observe
     ^             |                 |             |
     |             v                 v             v
   memory      capability       tool/retrieval   verifier
   recall      routing          result check     evidence
     ^             |                 |             |
     +-------------+---- revise -----+-------------+
                          |
                          v
                    response + learning record
```

Do not expose hidden chain-of-thought. Plans, state transitions, checks, and evidence are inspectable artifacts, not private reasoning transcripts.

## Orchestration lifecycle

1. `Orchestrator.run()` creates an `OrchestrationRun` and `SharedTaskState`.
2. The planner classifies complexity and builds a dependency graph from explicit roles or objective evidence.
3. Team selection chooses specialist roles with an inspectable rationale; explicit roles always override.
4. Ready tasks run in a bounded `ThreadPoolExecutor`.
5. `_orchestration_child()` produces a child `Agent` with narrowed tools, strict permissions, shared budget, and linked cancellation.
6. `SharedTaskState.publish()` stores owner-protected structured results and aggregates usage/tool logs.
7. The verifier checks requirements, artifacts, tests, and evidence before the objective can complete.
8. Conflict handling and bounded revision loops repair failed or contradictory results.
9. `_persist_run()` writes run/task metadata, usage rows, plans, states, and evidence to SQLite.
10. `_consolidate()` builds the final human-readable report from verified results.

Any live graph projection must be derived from real `SharedTaskState.snapshot()` plus persisted task rows. It must not invent progress. Appearance changes to the graph are out of scope.

## Security and reliability invariants

These are non-negotiable extension constraints:

- Child agents cannot call `orchestrate_task`, `delegate_task`, or `browser`.
- Child skill mutation remains blocked.
- Forced approval tools remain approval-gated: `terminal`, `write_file`, `edit_file`, `python`, `git`, `browser`, `scheduler`.
- Role merges are monotone: users may add restrictions, not remove forced ones.
- Dependency results, repository files, tool output, web pages, plans, and other agents' reports remain untrusted data.
- Untrusted content cannot write trusted memory, persistent instructions, or approved skills without the existing user-controlled paths and approvals.
- Learning evidence is data, not instruction; model claims and successful tool calls are not completion proof.
- Skill approval and rollback require explicit confirmation by default; auto-approval is opt-in and does not grant tools or spending authority.
- Spend budgets use locked monotonic caps; children cannot raise limits.
- Paid providers require explicit confirmation where configured; scheduled runs remain paid-blocked by default.
- Explicit `tool_permissions.allow_tools: null` means unrestricted; explicit `[]` means no tools.
- Retry must not repeat work after tools have already executed.
- Approval `once` must not be cached as a reusable rule.
- ANSI output must never emit untrusted cursor movement, OSC sequences, terminal titles, or arbitrary escapes.
- Benchmarks must not publish results without protocol, environment, prompt, tool, budget, and evidence metadata.

## Intelligence extension plan

### 1. Planning and execution state

Add a planning layer that produces an inspectable plan with objective, constraints, tasks, dependencies, required tools, expected results, verification criteria, risk, and alternatives. Add an execution-state machine with resumable checkpoints. Preserve the existing bounded loop as the low-level execution substrate.

### 2. Layered memory

Add working, episodic, semantic, procedural, and user-model layers. Keep Markdown memory as a compatible export/import surface. Retrieval must be bounded, labelled, and driven by task need. Provenance, confidence, contradiction handling, consolidation, expiration, and user deletion are required.

### 3. Learning loop

Record experience from real outcomes. Promote repeated successful procedures into candidate skills only with evidence from deterministic checks, observations, or explicit user confirmation. Preserve prior skill versions, support rollback, require approval for persistent instruction changes, and expose a searchable learning history.

Phase D implements this pipeline in `aether/learning/` with additive SQLite tables, bounded labeled context, deterministic validation, explicit install/rollback, and child isolation. [PHASE_D_LEARNING.md](PHASE_D_LEARNING.md) records the evidence rules, commands, verification, and remaining limitations.

### 4. Capability-aware routing

Add a model capability registry and task-based selection advice. Keep local and cost-free priority, fallbacks, cooldowns, paid confirmations, shared budgets, and monotonic caps unchanged. Never infer secret keys from hostnames or log credentials.

### 5. Coding and research workflows

Add repository indexing, progressive retrieval, patch-based edits, TDD hooks, regression detection, and diff review for coding. Add query planning, source comparison, citation extraction, contradiction detection, and confidence reporting for research. All external content remains untrusted.

### 6. Tool intelligence

Add capability metadata and optional schema deferral for larger tool catalogs. Add preflight validation, safe retry classification, result verification, and usage analytics. Existing permission, timeout, redaction, and cancellation behavior is mandatory.

### 7. Specialist orchestration and verification

Expand roles to at least 18 meaningful specialists. Add evidence-based team selection, explicit rationales, output contracts, conflict handling, an independent verifier, and bounded repair loops. Spawn children only when independent work benefits the objective.

### 8. Persistence and event projection

Derive state from plans, task/run records, tool logs, and verification evidence. Add additive schema only with existence checks and migrations. Preserve existing databases, keep orchestration persistence atomic, and do not store rendered visual payloads in state.

### 9. Benchmarks

Implement the protocol in [../benchmarks/README.md](../benchmarks/README.md). Store tasks and immutable results under `benchmarks/`. Run comparisons only under declared, equivalent conditions.

## Compatibility checklist

Before each 0.2+ milestone is called complete:

- existing commands still parse and behave as documented
- `python3 -m unittest discover -s tests -q` passes
- `bash scripts/check.sh` passes
- no third-party runtime dependency is introduced
- no secret, token, or generated key is committed or logged
- mocked/offline paths do not require network access
- existing ASCII artwork and colored rendering still render
- docs are updated in the same milestone
- the milestone is committed as a working checkpoint
