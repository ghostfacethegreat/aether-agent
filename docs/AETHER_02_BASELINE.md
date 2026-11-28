# Aether 0.2+ Baseline

This document is the Phase 0 source of truth for the additive `Aether 0.2+` upgrade. It records the repository state, verified capabilities, measured performance, and constraints that must be preserved by every later milestone.

The project priority has changed: 0.2+ is an **intelligence-first** program. Terminal appearance is frozen. Preserve the existing ASCII artwork and colored rendering, fix functional visual regressions only, and do not add themes, a theme selector, font tooling, animations, or a renderer rewrite without a demonstrated functional or performance bug. Current planning lives in [INTELLIGENCE_AUDIT.md](INTELLIGENCE_AUDIT.md), [INTELLIGENCE_ROADMAP.md](INTELLIGENCE_ROADMAP.md), and [HERMES_COMPARISON.md](HERMES_COMPARISON.md). Older visual milestone text is retained below only as historical audit evidence and is superseded by the intelligence roadmap.

## Repository state

| Item | Verified value |
|---|---|
| Repository | `ghostfacethegreat/aether-agent` |
| Working branch | `feat/aether-02-neon-agent-platform` |
| Baseline commit | `01ee003795787cc392f033edffbb98fcb3dd8b35` |
| Baseline commit subject | `Merge pull request #1 from ghostfacethegreat/feat/multi-agent-orchestration` |
| Phase A docs commit | `558bd58ec1f15ccf9cf76260d3ab7bfe675e76ce` |
| Tracking branch | `origin/main` |
| Local `main` | `e2ee662`, behind `origin/main` |
| Prior feature branch | `feat/multi-agent-orchestration` at `3df0698` |
| Worktree at audit start | clean |
| Python | `3.14.2` |
| Package version | `0.1.0` in [../pyproject.toml](../pyproject.toml) and [../aether/__init__.py](../aether/__init__.py) |
| Requires Python | `>=3.10` |
| Runtime dependencies | none declared (`dependencies = []`) |
| Dev dependencies | none declared (`dev = []`) |
| Console entry point | `aether = aether.cli.app:main` |
| GitHub Actions | none; the repository has no `.github/workflows` directory |

The 0.2+ work starts from the merged state of PR #1, including the multi-agent orchestration implementation and the security hardening commit `3df0698`.

## Verification record

Commands run on the baseline commit:

| Command | Result |
|---|---|
| `git status --short --branch` | clean branch tracking `origin/main` |
| `python3 -m unittest discover -s tests -q` | `Ran 109 tests in 0.564s`, `OK` |
| `bash scripts/check.sh` | 109 tests passed; doctor and mock CLI smoke passed; secret scan passed; local Markdown links passed; `all checks passed` |
| `scripts/benchmark.py` via `scripts/check.sh` | 3 cold starts, median wall time `0.083s`, peak child RSS `29.5 MiB` |
| `bash scripts/test_install.sh` | completed successfully in a temporary local clone |

There are no configured lint/typecheck commands in the repository. Existing documentation notes that `ruff`, `mypy`, and `pyright` were not installed; no lint/typecheck pass is claimed here.

Historical details remain in [RELEASE_CHECKS.md](RELEASE_CHECKS.md), but some counts in that file are intentionally historical and do not match the current 109-test baseline.

## Current capabilities

### CLI and interaction

The current CLI is implemented in [../aether/cli/app.py](../aether/cli/app.py) and [../aether/cli/render.py](../aether/cli/render.py).

Top-level commands:

- `setup`, `providers`, `status`, `doctor`, `config`
- `sessions`, `memory`, `skills`, `tasks`
- `agents`, `schedule`, `run`, `version`, `update`
- interactive chat when no subcommand is supplied

Interactive slash commands:

- `/help`, `/quit`, `/exit`, `/new`, `/clear`
- `/status`, `/provider`, `/model`, `/plan`, `/tools`
- `/memory`, `/skills`, `/sessions`, `/resume`, `/history`
- `/tasks`, `/agents`, `/schedule`, `/cost`, `/doctor`, `/export`

Current behavior includes streaming deltas, provider/model switching in chat, a compact status dashboard, tool execution lines, a braille spinner before the first token, `readline` slash completion, session export, cost summary, doctor diagnostics, and scheduled-job management.

### Providers and cost controls

The provider catalog in [../aether/providers/catalog.py](../aether/providers/catalog.py) contains 12 provider specs:

- local: `mock`, `ollama`, `lmstudio`, `llamacpp`
- free-tier optional: `groq`, `cerebras`, `huggingface`, `gemini`
- mixed: `openrouter`
- paid optional: `openai`, `anthropic`
- configurable: `custom`

Transport implementations cover mock, OpenAI-compatible endpoints, and Anthropic. The system has:

- ordered fallback providers with retryable classification and cooldowns
- rough token pricing and cached-token pricing where known
- paid-provider confirmation via config or `AETHER_CONFIRM_PAID`
- strict boolean parsing for confirmation and scheduler settings
- shared spend budget with reservations, monotonic cap tightening, and locked accounting
- per-session usage persisted to SQLite

### Core turn loop

[../aether/core/loop.py](../aether/core/loop.py) implements bounded turn iterations with:

- context fitting/compression
- provider fallback
- tool-call execution batches
- cancellation checks
- provider error handling
- cost preflight and worst-case reservations
- local per-turn usage plus shared aggregate usage
- explicit exit reasons such as `complete`, `provider_error`, `cost_limit`, `cancelled`, and `max_iterations`

[../aether/core/agent.py](../aether/core/agent.py) wires config, home, store, memory, skills, provider manager, tool registry, permissions, executor, subagents, orchestrator, session history, and child-agent construction.

### Tools and permissions

The built-in registry contains 17 tools:

- read-only: `list_directory`, `read_file`, `web_fetch`, `web_search`, `session_search`, `todo`
- write/edit: `write_file`, `edit_file`, `memory`, `skill`, `scheduler`
- execute/network: `terminal`, `git`, `python`, `browser`
- delegation: `delegate_task`, `orchestrate_task`

Tool metadata includes risk, parallel-safety, timeouts, and JSON parameter schemas. [../aether/tools/permissions.py](../aether/tools/permissions.py) enforces allow/deny lists, approval requirements, strict-mode path roots, sensitive-path approval, destructive-pattern checks, and canonical approval rule keys. Subprocess tools use process-group cleanup and cancellation propagation.

### Memory, skills, and persistence

Memory is two editable Markdown files, `MEMORY.md` and `USER.md`, managed by [../aether/memory/store.py](../aether/memory/store.py). It supports add, list, search, delete, replace, clear, export/import, and bounded prompt context.

Skills are `SKILL.md` files managed by [../aether/skills/engine.py](../aether/skills/engine.py). The engine supports discovery, frontmatter parsing, progressive disclosure, create/edit, view counting, basic injection-pattern rejection, and built-in/user source labels.

SQLite state in `state.db` contains:

- `sessions`
- `messages`
- `tasks`
- `usage`
- `approvals`
- optional FTS5 message search with substring fallback

The persistence layer supports sessions, messages with tool metadata, task records, usage rows, approvals, import/export, orchestration run snapshots, and atomic orchestration persistence.

### Multi-agent orchestration

[../aether/orchestration/roles.py](../aether/orchestration/roles.py) defines four default roles:

- `researcher`
- `developer`
- `debugger`
- `reviewer`

Each role has provider/model overrides, a system prompt, tool allow/deny lists, approval requirements, and a max-iteration budget. Role resolution applies forced deny tools, forced approval tools, and read-only skill restrictions.

[../aether/orchestration/orchestrator.py](../aether/orchestration/orchestrator.py) builds dependency plans, runs ready tasks in bounded parallel or sequential mode, shares the parent spend budget, enforces paid-provider rules, propagates parent/task cancellation, handles retries and timeouts, publishes structured results, and persists/recovers runs through SQLite.

[../aether/orchestration/state.py](../aether/orchestration/state.py) owns `OrchestrationRun`, `OrchestrationTask`, and `SharedTaskState`. Dependency results are delimited as `[untrusted_data]`; task records are owner-protected; usage and tool logs are aggregated; snapshots expose data suitable for a live agent graph.

### Scheduling

The scheduler executes due prompts in-process, claims jobs before running them, records a local execution ledger, and supports list/add/remove/update/pause/resume/tick. It is disabled by default and blocks billable providers unless explicitly allowed. It is not a daemon and has no delivery targets.

## Current visual baseline

The renderer currently uses basic ANSI SGR colors in [../aether/cli/render.py](../aether/cli/render.py): reset, bold, dim, red, green, yellow, blue, magenta, and cyan. It defines `NO_COLOR` from `NO_COLOR` or non-TTY stdout, paints status lines/dashboards/tables/tool lines, and runs a braille spinner only on a TTY when color is enabled.

The current palette is not the required purple-neon identity. It includes cyan, green, yellow, red, and magenta, and the banner is a simple cyan box. There is no font registry, ASCII art generator, animated title, `/font` command, `aether fonts` command, dynamic agent graph renderer, or `TERM=dumb` handling.

This section is a historical observation from the original visual-first plan. Those items are **not** current requirements. Preserve the existing ASCII artwork and colored rendering; do not add the listed visual systems.

## Historical visual gap inventory

The original 0.2.0 audit listed these visual gaps. They are superseded by [INTELLIGENCE_ROADMAP.md](INTELLIGENCE_ROADMAP.md) and retained only to explain the baseline from which the priority changed:

1. Version remains `0.1.0` alpha in package metadata and runtime version.
2. No purple-neon palette using the formerly required colors.
3. No local ASCII font system; `aether fonts`, `aether font random`, `aether font set block`, and `aether font preview` do not exist.
4. No slash commands for `/font`, `/font random`, `/font set <name>`, or `/font list`.
5. No ASCII art engine, AI art generation path with offline fallback, or animated title sequence.
6. No 12-font registry or font distinctness system.
7. No `TERM=dumb` handling, truecolor/256/16 color-tier fallback beyond basic SGR, or escape-injection sanitizer.
8. No single coordinated terminal output owner; current streaming, spinner, tool lines, and command output are separate writes.
9. Only four orchestration roles; >=18 meaningful specialist roles are required by the intelligence roadmap, not by a visual redesign.
10. No evidence-based automatic team selection from task content.
11. No dynamic agent graph UI; current agent status is tabular.
12. No bounded memory retrieval or strengthened skill validation/versioning beyond the current baseline.
13. No GitHub Actions CI workflow.
14. Existing docs and release notes describe older milestones and test counts.
15. Existing screenshots capture the old terminal style; no new visual redesign is planned.

## Preservation requirements

Every 0.2+ milestone must remain additive. Do not remove, silently replace, or regress:

- AI conversation, streaming, fallback providers, and tool calling
- local Ollama/LM Studio/llama.cpp support
- hosted provider support, including free-tier and paid-provider flows
- terminal, Python, file, git, web, memory, skill, task, and scheduler tools
- SQLite sessions, messages, task ledger, approvals, usage, and resumability
- Markdown memory and `SKILL.md` skills
- scheduled jobs and local execution ledger
- multi-agent orchestration, shared budgets, cancellation, approvals, recovery, and untrusted-data boundaries
- install, uninstall, doctor, update, and local install test scripts
- strict no-secret policy and honest cost reporting
- stdlib-only runtime and no required network dependency for local startup
- existing ASCII artwork and colored rendering

## Definition of a completed milestone

For each milestone, record:

1. files changed
2. observable behavior added or changed
3. focused tests actually run
4. failures found and how they were fixed
5. documentation updates
6. a working checkpoint commit

Do not claim success from static inspection alone. Run the relevant tests and full checks before reporting completion.

See [AETHER_02_ARCHITECTURE.md](AETHER_02_ARCHITECTURE.md) for intelligence extension points, [AETHER_02_ROADMAP.md](AETHER_02_ROADMAP.md) for the historical milestone index and current phase map, and [INTELLIGENCE_ROADMAP.md](INTELLIGENCE_ROADMAP.md) for active work.
