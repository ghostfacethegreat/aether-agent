# Aether

Aether is a local-first, provider-agnostic AI agent. It runs as a single CLI, stores sessions in SQLite, keeps editable memory in Markdown, and supports reusable `SKILL.md` skills. It is an independent project; it is not affiliated with Nous Research.

Aether works with no paid account: the defaults target local Ollama, and a built-in mock provider is available for tests and demos. Free-tier hosted providers are supported but clearly labelled with their own costs and limits. Aether cannot remove model-provider restrictions; only the provider can change those.

## Status

Version `0.1.0` is an alpha release. A working core, screenshots, installer scripts, and source publication are complete. The project priority for `0.2+` is intelligence first: planning, memory, learning, routing, coding, research, coordination, verification, recovery, and measured task success. Adaptive planning, risk/alternatives records, resumable execution checkpoints, and additive layered memory are implemented and locally verified on a feature branch; `0.2.0` has not been released. See the [development status](docs/DEVELOPMENT_STATUS.md), [release roadmap](docs/RELEASE_ROADMAP.md), [known limitations](docs/KNOWN_LIMITATIONS.md), [intelligence audit](docs/INTELLIGENCE_AUDIT.md), [intelligence roadmap](docs/INTELLIGENCE_ROADMAP.md), and [source-evidenced Hermes comparison](docs/HERMES_COMPARISON.md). No Hermes parity or superiority is claimed. Do not treat free-tier limits or model IDs as permanent; verify them with the provider.

Terminal appearance is frozen. The existing ASCII artwork and colored rendering are preserved; only functional visual regressions will be fixed. Do not expect a theme selector, font system, animated title, or visual redesign in `0.2+`.

Benchmark protocol and result rules are in [benchmarks/README.md](benchmarks/README.md). No task-quality benchmark results exist yet.

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

Type `/help` inside the chat for slash commands. Useful ones include `/status`, `/provider`, `/model`, `/plan`, `/tools`, `/memory`, `/skills`, `/sessions`, `/resume`, `/history`, `/tasks`, `/agents`, `/schedule`, `/cost`, and `/doctor`.

## Screenshots

Real terminal captures from a local mock-provider run; no network request or paid account was used:

- [Status dashboard](docs/screenshots/01-status.txt)
- [Mock run](docs/screenshots/02-mock-run.txt)
- [Provider catalog](docs/screenshots/03-providers.txt)
- [Doctor diagnostics](docs/screenshots/04-doctor.txt)

Branding assets are in `assets/logo.svg` and `assets/banner.svg`; they are preserved as part of the visual freeze, not a roadmap for redesign.

## Providers

```bash
aether providers
aether --provider groq --model llama-3.3-70b-versatile run "Hello"
aether --provider mock --model mock-tools run "Use a tool"
```

Provider catalog entries include `mock`, `ollama`, `lmstudio`, `llamacpp`, `groq`, `cerebras`, `huggingface`, `gemini`, `openrouter`, `openai`, `anthropic`, and `custom`. Paid providers are marked as paid. Free-tier providers are marked with their own limits. See `docs/PROVIDERS.md`.

API keys are read from environment variables or `~/.aether/.env`. Never commit keys or publish `.env` files.

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

Built-in tools cover file reads/writes, terminal and git commands, Python execution, web fetch/search, memory, skills, task delegation, multi-agent orchestration, plans, session search, and scheduling. Write/execute/network actions can require approval; destructive shell patterns are detected and can be rejected in strict mode.

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
- Browser automation is disabled unless you configure a local command template.
- Scheduled prompts can spend money if you select a paid provider. Check `aether providers` and your provider dashboard.

## Tests

```bash
python3 -m compileall -q aether tests
python3 -m unittest discover -s tests -v
bash scripts/check.sh
bash scripts/test_install.sh
```

`scripts/check.sh` includes tests, doctor and mock CLI smoke checks, secret scanning, the local startup benchmark, and Markdown link checks. It does not measure task quality; see [benchmarks/README.md](benchmarks/README.md) for that protocol.

## Attribution

Aether's architecture was informed by static audits of the public Hermes Agent repository, initially at commit `bb89ad1a`, refreshed for Phase 2 at `b98c388a880b1b6fd303c9c2821a3946651a0b4c`, and refreshed again for Phase A against current `main` at `fe9a4b58ec137d3e00719c10e2385876fa03b97c`. Hermes Agent is MIT-licensed; see `NOTICE` and `docs/UPSTREAM_LICENSE.md`. Aether is independently implemented and branded.

## License

MIT. See `LICENSE`.
