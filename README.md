# Aether

Aether is a local-first, provider-agnostic AI agent. It runs as a single CLI, stores sessions in SQLite, keeps editable memory in Markdown, and supports reusable `SKILL.md` skills. It is an independent project; it is not affiliated with Nous Research.

Aether works with no paid account: the defaults target local Ollama, and a built-in mock provider is available for tests and demos. Free-tier hosted providers are supported but clearly labelled with their own costs and limits. Aether cannot remove model-provider restrictions; only the provider can change those.

## Status

Version `0.1.0` is an alpha release. A working core, screenshots, installer scripts, and source publication are complete. The project priority for `0.2+` is intelligence first: planning, memory, learning, routing, coding, research, coordination, verification, recovery, and measured task success. Adaptive planning, risk/alternatives records, resumable execution checkpoints, additive layered memory, an evidence-based learning loop with versioned skills, and capability-aware model routing are implemented and locally verified on a feature branch; `0.2.0` has not been released. See the [development status](docs/DEVELOPMENT_STATUS.md), [release roadmap](docs/RELEASE_ROADMAP.md), [known limitations](docs/KNOWN_LIMITATIONS.md), [intelligence audit](docs/INTELLIGENCE_AUDIT.md), [intelligence roadmap](docs/INTELLIGENCE_ROADMAP.md), [model routing](docs/MODEL_ROUTING.md), [Phase D learning](docs/PHASE_D_LEARNING.md), and [source-evidenced Hermes comparison](docs/HERMES_COMPARISON.md). No Hermes parity or superiority is claimed. Do not treat free-tier limits or model IDs as permanent; verify them with the provider.

The interactive CLI now uses an `acid-blue` presentation with a 3D block-letter masthead, framed runtime summary, distinct response labels, and a clearer prompt. It keeps the lightweight Python runtime and degrades to plain ASCII/`NO_COLOR` terminals. See [CLI presentation](docs/CLI_PRESENTATION.md) for customization and design notes. The exact ACID 3D Blue TheDraw font file is not bundled because its redistribution rights are unclear; Aether uses an original block-letter treatment rather than copying TAAG's bundled site code.

Benchmark protocol and result rules are in [benchmarks/README.md](benchmarks/README.md). No task-quality benchmark results exist yet. `aether models benchmark` is an offline deterministic routing simulation that prints JSON and makes no model, network, or billable calls; it is not task-quality evidence.

## Install

Aether requires Python 3.10+ and has no third-party runtime dependencies.

```bash
git clone https://github.com/ghostfacethegreat/aether-agent.git aether-agent
cd aether-agent
python3 -m pip install -e .
aether setup
```

For development:

```bash
python3 -m pip install -e '.[dev]'
python3 -m unittest discover -s tests -v
```

Local installer scripts are also available: `scripts/install.sh`, `scripts/uninstall.sh`, and `scripts/test_install.sh`. Set `AETHER_HOME` before installing to choose a different data directory. A hosted `curl | bash` URL is intentionally not published.

## Quick start

Try the in-process mock provider first:

```bash
aether --provider mock run "Say hello"
```

Use a local model with Ollama:

```bash
ollama pull llama3.2:3b
aether setup
aether run "Explain this repository"
```

Start interactive mode:

```bash
aether
```

Type `/help` inside the chat for slash commands. Useful ones include `/status`, `/provider`, `/model`, `/models`, `/plan`, `/tools`, `/memory`, `/skills`, `/feedback`, `/sessions`, `/resume`, `/history`, `/tasks`, `/agents`, `/schedule`, `/cost`, and `/doctor`.

## Screenshots

Real terminal captures from a local mock-provider run; no network request or paid account was used:

- [Status dashboard](docs/screenshots/01-status.txt)
- [Mock run](docs/screenshots/02-mock-run.txt)
- [Provider catalog](docs/screenshots/03-providers.txt)
- [Doctor diagnostics](docs/screenshots/04-doctor.txt)

Branding assets are in `assets/logo.svg` and `assets/banner.svg`; they are preserved as part of the visual freeze, not a roadmap for redesign.

## Terminal presentation

The interactive CLI defaults to the blue 3D-style theme. Customize it without installing a UI dependency:

```bash
aether config set terminal.theme "classic"          # acid-blue, classic, or mono
aether config set terminal.unicode false            # use ASCII-safe glyphs
aether config set terminal.show_banner false        # hide the startup masthead
aether config set terminal.show_dashboard false     # hide the session overview
aether config set terminal.show_response_labels false
```

Set `NO_COLOR=1` to disable ANSI colors or `AETHER_ASCII=1` to force ASCII characters. See [CLI presentation](docs/CLI_PRESENTATION.md).

## Providers

```bash
aether providers
aether --provider groq --model llama-3.3-70b-versatile run "Hello"
aether --provider mock --model mock-tools run "Use a tool"
```

Provider catalog entries include `mock`, `ollama`, `lmstudio`, `llamacpp`, `groq`, `cerebras`, `huggingface`, `gemini`, `openrouter`, `openai`, `anthropic`, and `custom`. Paid providers are marked as paid. Free-tier providers are marked with their own limits. See `docs/PROVIDERS.md`.

API keys are read from environment variables or `~/.aether/.env`. Never commit keys or publish `.env` files.

## Model routing

Aether can score the models you have configured using deterministic task requirements, evidence-labeled capability facts, context windows, cost, billability, provider health, and role needs. `routing.strategy` accepts `capability`, `cost`, or `fixed`. Explicit `--provider`/`--model` or `Agent(provider_name=..., model=...)` selections stay authoritative; there is no `routing.manual` setting. Diagnostics never call a model.

```bash
aether models list
aether models inspect ollama qwen2.5-coder:7b
aether models capabilities ollama qwen2.5-coder:7b
aether models routing "Build a Python application"
aether models explain "Build a Python application"
aether models performance
aether models health
aether models benchmark --samples 5
```

Inside chat, `/models list|inspect|capabilities|routing|explain|performance|health` gives the same inspectable diagnostics. `aether models benchmark [--samples N] [--confirm-billable]` is an offline, deterministic routing simulation: it prints JSON, writes no files, and makes no model, network, or billable calls. `--confirm-billable` is acknowledgement only. It does not measure task quality. See [MODEL_ROUTING.md](docs/MODEL_ROUTING.md) and [configuration](docs/CONFIGURATION.md).

## Configuration

Config is JSON at `~/.aether/config.json` by default. Use `AETHER_HOME` to relocate all state.

```bash
aether config list
aether config set personality "You are terse and skeptical."
aether config set tool_permissions.mode strict
aether config set fallback_providers '["lmstudio", "groq"]'
```

Secrets belong in `~/.aether/.env`, for example:

```text
GROQ_API_KEY=...
OPENROUTER_API_KEY=...
HF_TOKEN=...
```

See `docs/CONFIGURATION.md`.

## Memory, skills, and tools

Memory starts as two editable Markdown files: `~/.aether/memories/MEMORY.md` and `USER.md`. Aether also keeps additive SQLite-backed layers for working objectives, turn episodes, semantic facts with provenance, verified procedures, and an explicit user model. Layered recall is bounded and labeled, and child agents cannot write it persistently.

```bash
aether memory add "Prefer Python for prototypes" --category preferences
aether memory list
aether memory layer add "Uses SQLite locally" --layer semantic --subject storage --provenance manual
aether memory layer recall "SQLite"
aether memory layer counts
```

Skills are `SKILL.md` files in `~/.aether/skills/<name>/SKILL.md`, with built-in examples under `aether/skills/builtin/`. Skills are discovered on demand and summarized in the system prompt.

```bash
aether skills list
aether skills view code-review
aether skills create my-skill "A useful procedure"
```

Aether also records sanitized experience from real turns and can propose reviewable skills only from verified evidence. Model claims, successful tool calls, files, web pages, and child-agent output do not count as verification by themselves. Persistent skill changes require explicit confirmation by default.

```bash
aether skills discover --query "parser tests"
aether skills proposals
aether skills validate <skill>
aether skills approve <proposal> --yes
aether skills versions <skill>
aether skills rollback <skill> <version> --yes
aether learning pending
aether learning metrics <skill>
aether learning feedback verified "The regression check passed"
```

Inside chat, use `/skills discover`, `/skills proposals`, `/skills validate <skill>`, `/skills history`, `/skills versions <skill>`, and `/feedback <verified|failed|neutral> <text>`. See [Phase D learning](docs/PHASE_D_LEARNING.md).

Built-in tools cover file reads/writes, terminal and git commands, Python execution, web fetch/search, memory, skills, task delegation, multi-agent orchestration, plans, session search, and scheduling. Write/execute/network actions can require approval; destructive shell patterns are detected and can be rejected in strict mode.

## Project context

Aether can load bounded repository-root guidance from `AGENTS.md`, `AETHER.md`, `.aether.md`, `CLAUDE.md`, `SOUL.md`, `.cursorrules`, and `.hermes.md`. It reads only direct children of the workspace root, skips symlinks, nested paths, binary/invalid files, and applies file-count, byte, and total-character limits. This is lower-priority workspace guidance; it cannot override tool permissions, approvals, safety rules, or the current user request.

```bash
aether config set context_files.enabled false
aether config set context_files.max_total_chars 12000
aether config set context_files.filenames '["AGENTS.md", "AETHER.md"]'
```

## Specialist teams and verification

Aether's default role registry includes planner, researcher, architect, developer, debugger, tester, security auditor, independent verifier, reviewer, data analyst, and documentation writer. Automatic orchestration selects dependency-aware teams for implementation, debugging, documentation, and security work. Implementation teams include an independent verifier.

The verifier cannot modify files or approve itself. A run is marked independently verified only when the verifier's own terminal log contains an exit-code-zero run of a recognized test/check command and its structured result satisfies the verifier contract. Terminal commands still follow configured approval rules.

Set `orchestrator.strict_output_contracts=true` to validate structured outputs from all specialist roles. This is opt-in for compatibility; verifier output contracts and its tool-evidence gate are always enforced.

See [parallel agent workstreams](docs/AGENT_WORKSTREAMS.md) for scoped Copilot profiles and the next parity milestones.

## Repository coding workflow

Aether now includes a local, on-demand repository index and a guarded unified-diff workflow:

- `repo_index` summarizes files or searches filenames and source snippets, respects root `.gitignore` patterns and skips symlinks, generated/vendor directories, binary files, and oversized files.
- `patch_preview` validates a unified diff and reports affected files and hashes without writing.
- `patch_apply` applies modifications only to existing UTF-8 files after complete preflight. It rejects path escapes, symlinks, binary files, renames, and file creation/deletion. Tool execution requires explicit approval.
- `test_run` executes a bounded set of fixed test commands (unittest suite, one `test_*.py` module, compileall, or `scripts/check.sh`) without accepting an arbitrary shell command string. Test execution requires approval.

The index is rebuilt on demand; it is not a persistent symbol database or LSP. This provides a coding-agent foundation, not yet a fully autonomous IDE-grade TDD loop. See [configuration](docs/CONFIGURATION.md) and [known limitations](docs/KNOWN_LIMITATIONS.md).

## Sessions and tasks

```bash
aether sessions list
aether --session <id> run "Continue"
aether tasks list
aether schedule add "Summarize new notes" "every 1h"
```

Sessions, messages, task ledger, approvals, and usage counters are stored locally in `~/.aether/state.db`.

## Plans and checkpoints

Aether classifies requests as simple, moderate, complex, or high-risk and records an inspectable plan when work needs more than a direct reply. Plans include risk notes, alternatives, task dependencies, tools, expected results, verification criteria, and revision history. High-risk plans record an approval requirement while existing tool permissions continue to apply.

Plans and checkpoints are stored in local SQLite. Resume skips completed and non-idempotent work, and plan changes caused by failures or feedback are recorded as revisions.

```bash
aether plan list
aether plan status
aether plan show <plan-id>
aether plan checkpoints
aether plan resume <plan-id>
```

Inside chat, use `/plan status`, `/plan checkpoints`, `/plan resume <plan-id>`, or `/plan <text>`.

## Multi-agent orchestration

Aether can split an objective across specialized `researcher`, `developer`, `debugger`, and `reviewer` agents. The orchestrator builds a dependency plan, runs ready tasks in parallel by default, passes structured results between tasks, consolidates the final report, and keeps child permissions inside the parent's allow-list. Expanding the role catalog, automatic team selection, output contracts, and an independent verifier are planned intelligence work, not shipped behavior.

```bash
aether agents list
aether --provider mock agents run researcher "Explain local caching"
aether agents status
aether agents cancel <task-id>
aether agents resume <run-id>
```

Inside chat, use `/agents list`, `/agents run <role> <task>`, `/agents status`, and `/agents cancel <task-id>`. Agent runs share the parent's spend budget; nested agents cannot raise the limit. Paid providers are blocked for child agents unless `orchestrator.allow_paid=true`, `AETHER_CONFIRM_PAID` has a truthy value, or `costs.confirm_paid=false`.

## Safety notes

- Aether is not a security sandbox. Tool subprocesses inherit the user's environment.
- Do not run untrusted prompts with write/execute tools enabled in a sensitive workspace.
- Use `tool_permissions.mode=strict` and explicit `allow_tools` for unattended runs.
- Web output is data, not instructions; Aether's system prompt tells the model not to follow injected instructions from files or pages.
- Multi-agent child results are untrusted data; the orchestrator delimits them as task context and never grants children the `orchestrate_task` tool. Child agents cannot create or edit persistent skills.
- Learning records omit raw tool arguments and results, and prompt learning context is labeled as data, not instruction.
- Learned skills are proposals until explicitly approved; validation rejects secret exposure and injection patterns, and rollback needs explicit confirmation.
- Browser automation is disabled unless you configure a local command template.
- Scheduled prompts can spend money if you select a paid provider. Check `aether providers` and your provider dashboard.

## Tests

```bash
python3 -m compileall -q aether tests
python3 -m unittest discover -s tests -v
bash scripts/check.sh
bash scripts/test_install.sh
```

Phase E local verification: `python3 -W ignore::ResourceWarning -m unittest tests.test_model_routing -q` passes 26 focused tests, covering HTTP 400 context-length detection/recovery and orchestrator role preferred/fallback entries among other routing behavior, and `python3 -W ignore::ResourceWarning -m unittest discover -s tests -q` passes 179 tests. `bash scripts/check.sh && bash scripts/test_install.sh` passed with 3 cold starts, median wall time `0.114s`, peak child RSS `34.4 MiB`, and a local git-remote install test pass. `python3 scripts/benchmark.py` recorded 3 cold starts, median wall time `0.112s`, and peak child RSS `34.9 MiB`. `git diff --check` passed. `ResourceWarning` notices for unclosed SQLite connections are non-failing. No lint/typecheck command is configured, so none is claimed. These are startup measurements, not task-quality results.

`scripts/check.sh` includes tests, doctor and mock CLI smoke checks, secret scanning, the local startup benchmark, and Markdown link checks. It does not measure task quality; see [benchmarks/README.md](benchmarks/README.md) for that protocol.

## Attribution

Aether's architecture was informed by static audits of the public Hermes Agent repository, initially at commit `bb89ad1a`, refreshed for Phase 2 at `b98c388a880b1b6fd303c9c2821a3946651a0b4c`, and refreshed again for Phase A against current `main` at `fe9a4b58ec137d3e00719c10e2385876fa03b97c`. Hermes Agent is MIT-licensed; see `NOTICE` and `docs/UPSTREAM_LICENSE.md`. Aether is independently implemented and branded.

## License

MIT. See `LICENSE`.
