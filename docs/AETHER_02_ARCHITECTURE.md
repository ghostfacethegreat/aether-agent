# Aether 0.2.0 Additive Architecture

This document maps the current Aether implementation and identifies the safe extension points for the `Aether v0.2.0` upgrade. It is intentionally additive: the working 0.1.0 core remains the source of truth, and 0.2.0 capabilities should be layered onto it without replacing working behavior.

## Current runtime map

```text
CLI (aether.cli.app)
  |
  +-- config / home / environment
  +-- renderer (aether.cli.render)
  +-- Agent (aether.core.agent)
        |
        +-- ContextManager (aether.core.context)
        +-- ProviderManager (aether.providers)
        |     +-- catalog / cost pricing
        |     +-- mock, OpenAI-compatible, Anthropic transports
        +-- Turn loop (aether.core.loop)
        |     +-- cost preflight / shared budget
        |     +-- cancellation / fallbacks / iteration bound
        +-- Tool registry + executor + permissions
        |     +-- file, terminal, git, Python, web, memory, skills, tasks
        +-- MemoryStore (Markdown)
        +-- SkillEngine (SKILL.md)
        +-- Store (SQLite: sessions, messages, tasks, usage, approvals)
        +-- SubagentManager
        +-- Orchestrator
              +-- roles
              +-- SharedTaskState
              +-- dependency plan / workers / retries / timeouts
              +-- persisted runs and task snapshots
        +-- Scheduler
```

The original design audit is preserved in [ARCHITECTURE.md](ARCHITECTURE.md). The current capability inventory is in [AETHER_02_BASELINE.md](AETHER_02_BASELINE.md).

## Source map

| Area | Files | Current role | 0.2.0 extension approach |
|---|---|---|---|
| CLI parsing and dispatch | [../aether/cli/app.py](../aether/cli/app.py) | argument parser, command handlers, slash commands, streaming callbacks, scheduler wiring | Add new commands and slash handlers without changing existing command names or semantics. |
| Terminal rendering | [../aether/cli/render.py](../aether/cli/render.py) | ANSI colors, banner, dashboard, tables, tool lines, status lines, spinner | Introduce a theme/ANSI/font/art layer and route existing render functions through it. |
| Core wiring | [../aether/core/agent.py](../aether/core/agent.py) | constructs and connects all subsystems; builds children | Keep constructor compatibility; add optional hooks/context for visual events and team selection. |
| Turn loop | [../aether/core/loop.py](../aether/core/loop.py) | bounded provider/tool loop, cost/cancellation/usage | Emit structured status events for the single-writer renderer; do not add raw stdout writes here. |
| Context | [../aether/core/context.py](../aether/core/context.py) | prompt assembly and context fitting | Preserve prompt shape while adding optional bounded retrieval context. |
| Providers | [../aether/providers/](../aether/providers/) | catalog, registry, transports, cost functions | Add provider intelligence as selection/pricing metadata and helper functions; retain existing provider names and APIs. |
| Tools | [../aether/tools/](../aether/tools/) | registry, executor, permissions, built-ins | Add metadata/events as needed; preserve allow/deny, approval, timeout, and cancellation behavior. |
| Memory | [../aether/memory/store.py](../aether/memory/store.py) | Markdown memory files and prompt context | Add bounded retrieval as an additive method/option; preserve file format. |
| Skills | [../aether/skills/engine.py](../aether/skills/engine.py) | `SKILL.md` discovery, validation, usage tracking | Add stronger validation/version handling without invalidating existing skills. |
| Orchestration | [../aether/orchestration/](../aether/orchestration/) | roles, task graph, shared state, run persistence | Expand roles and add team selection; expose real state snapshots to the renderer. |
| Subagents | [../aether/tasks/subagents.py](../aether/tasks/subagents.py) | parallel isolated children | Preserve delegation behavior; integrate with team selection only through explicit plans. |
| Scheduler | [../aether/tasks/scheduler.py](../aether/tasks/scheduler.py) | in-process due jobs and ledger | Preserve strict paid-provider and no-orchestration restrictions. |
| Persistence | [../aether/persistence/store.py](../aether/persistence/store.py) | SQLite schema and data access | Add additive columns/tables only with migration checks; never destructively rewrite existing state. |
| Config | [../aether/config.py](../aether/config.py) | typed dotted defaults and validation | Add 0.2.0 settings with safe defaults; keep old configs valid. |
| Tests | [../tests/](../tests/) | stdlib `unittest` suite with mock provider | Add deterministic tests per milestone; keep the existing suite green. |

## Turn lifecycle

1. `main()` parses global options and the optional subcommand.
2. `prepare()` loads environment, config, provider/model overrides, logging, and home.
3. `cmd_chat()` or `cmd_run()` constructs an `Agent`.
4. `Agent.run_turn()` builds the system prompt from config, memory, skills, and plan.
5. `run_turn_loop()` fits context, calls providers, checks paid/cost rules, executes tools, and accumulates usage.
6. Stream deltas, tool lines, and status events reach the CLI callbacks.
7. `Agent` appends new messages and usage to SQLite when persistence is enabled.
8. `TurnResult` carries text, usage, tool log, exit reason, and messages to the caller.

For 0.2.0, terminal output should move toward one coordinated renderer. The renderer may receive status events from the loop, orchestrator, and tools, but only one writer should own the terminal at a time. This avoids interleaved spinner, stream, table, and graph output.

## Orchestration lifecycle

1. `Orchestrator.run()` creates an `OrchestrationRun` and `SharedTaskState`.
2. `_plan_tasks()` builds a dependency graph from explicit roles or objective hints.
3. Ready tasks run in a bounded `ThreadPoolExecutor`.
4. `_orchestration_child()` produces a child `Agent` with narrowed tools, strict permissions, shared budget, and linked cancellation.
5. `SharedTaskState.publish()` stores owner-protected structured results and aggregates usage/tool logs.
6. `_persist_run()` writes run/task metadata and usage rows to SQLite.
7. `_consolidate()` builds the final human-readable report.
8. `status()` and `list_runs()` expose active and stored runs.

The live agent graph required by 0.2.0 should be a projection of `SharedTaskState.snapshot()` plus persisted task rows. It must not invent progress from animation alone.

## Security and reliability invariants

These are non-negotiable extension constraints:

- Child agents cannot call `orchestrate_task`, `delegate_task`, or `browser`.
- Child skill mutation is blocked.
- Forced approval tools remain approval-gated: `terminal`, `write_file`, `edit_file`, `python`, `git`, `browser`, `scheduler`.
- Role merges are monotone: users may add restrictions, not remove forced ones.
- Dependency results, repository files, tool output, and other agents' reports remain untrusted data.
- Spend budgets use locked monotonic caps; children cannot raise limits.
- Paid providers require explicit confirmation where configured; scheduled runs remain paid-blocked by default.
- Explicit `tool_permissions.allow_tools: null` means unrestricted; explicit `[]` means no tools.
- Retry must not repeat work after tools have already executed.
- Approval `once` must not be cached as a reusable rule.
- ANSI output must never emit untrusted cursor movement, OSC sequences, terminal titles, or arbitrary escapes.

## 0.2.0 extension plan

### 1. Purple-neon identity and safe ANSI engine

Add a dedicated visual layer (for example `aether/ui/` or focused modules under `aether/cli/`) that owns:

- required palette constants
- semantic roles such as primary, accent, success, warning, error, muted, panel, and background
- ANSI SGR generation with truecolor, 256-color, 16-color, and no-color tiers
- `NO_COLOR`, `TERM=dumb`, non-TTY, and stream capability detection
- sanitization of user/model/tool text before any escape sequence is emitted
- one renderer instance/fence for terminal writes

Keep [../aether/cli/render.py](../aether/cli/render.py) as the compatibility façade so existing callers and tests do not need to change all at once.

### 2. Fonts and ASCII art

Introduce an offline font registry and renderer:

- at least 12 genuinely different ASCII font designs
- local data only; no runtime download from Patorjk or any other site
- deterministic commands for list, random, set, preview, and reset behavior
- random selection that avoids immediately repeating the previous font
- compatibility with non-TTY and no-color output
- an AI art path with a deterministic offline fallback when no model/provider is available

Persist the selected font in config under a new defaulted key. Existing config files must remain valid.

### 3. CLI command surface

Extend `SLASH_COMMANDS`, `_print_help()`, `_agent_command()`, and `build_parser()` with the new 0.2.0 commands:

- `aether fonts`
- `aether font random`
- `aether font set <name>`
- `aether font preview [name]`
- `/font`, `/font random`, `/font set <name>`, `/font list`
- `/agents` and `/team` views that visualize real state
- `/art` for ASCII/AI art rendering

Do not remove current commands; aliases and legacy forms should continue to work where practical.

### 4. Interactive dashboard and title animation

Build dashboard components that consume existing status data:

- provider/model/session/context/cost from `Agent.status_summary()`
- role and task state from `Orchestrator.status()` and stored runs
- tool activity from executor/tool-log events
- animated title sequence that is suppressed or simplified for non-TTY, `NO_COLOR`, and `TERM=dumb`

Animation must be cosmetic only. It must not imply activity that is not occurring.

### 5. Specialist roles and team selection

Expand `DEFAULT_ROLES` in [../aether/orchestration/roles.py](../aether/orchestration/roles.py) to at least 18 meaningful roles. Each role must have:

- a distinct purpose and prompt
- structured output contract
- allowed/denied tools
- approval requirements
- max-iteration budget
- forced-rule compatibility

Add a separate team-selection module or helper that chooses roles from objective signals. `_plan_tasks()` can call it only when explicit roles are absent. Preserve the existing objective heuristic as a fallback or test fixture.

### 6. Provider, memory, and skill intelligence

Add advisory intelligence without changing provider APIs:

- rank/suggest providers from capability, cost, locality, and configured keys
- keep local/mock providers deterministic for tests
- bounded memory retrieval with explicit limits and source labels
- skill validation/versioning that accepts existing `SKILL.md` files
- no secret values in suggestions, logs, diagnostics, or screenshots

### 7. Persistence and event projection

Prefer deriving visualization state from existing task/run records. If new storage is required:

- add additive columns/tables or metadata fields
- extend `Store.init()` with existence checks and migrations
- preserve existing databases
- keep orchestration persistence atomic
- avoid storing rendered ANSI or large art payloads in state

### 8. Tests and CI

Add deterministic tests for:

- palette/color tiers and sanitization
- font registry count and distinctness
- random font behavior
- CLI command parsing and slash dispatch
- non-TTY, `NO_COLOR`, and `TERM=dumb` rendering
- dashboard/graph projection from mock orchestration state
- role catalog size, contracts, and forced-rule enforcement
- team selection from representative objectives
- provider suggestions and bounded memory behavior
- backward compatibility of config and existing SQLite state

Add GitHub Actions once the test commands are stable. CI should run at minimum compileall, the full unittest suite, the CLI smoke checks from `scripts/check.sh`, and the link/secret checks.

## Compatibility checklist

Before each 0.2.0 milestone is called complete:

- existing commands still parse and behave as documented
- `python3 -m unittest discover -s tests -q` passes
- `bash scripts/check.sh` passes
- no third-party runtime dependency is introduced
- no secret, token, or generated key is committed or logged
- mocked/offline paths do not require network access
- docs are updated in the same milestone
- the milestone is committed as a working checkpoint
