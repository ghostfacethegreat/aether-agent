# AETHER

<p align="center">
  <img src="assets/banner.svg" alt="AETHER — local-first AI agent" width="100%" />
</p>

<p align="center">
  <strong>A local-first AI agent for developers who want control, visibility, and room to extend.</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT license"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/Python-3.10%2B-3776AB.svg" alt="Python 3.10 and later"></a>
  <a href="docs/DEVELOPMENT_STATUS.md"><img src="https://img.shields.io/badge/status-alpha-orange.svg" alt="Alpha"></a>
</p>

AETHER is an independent, provider-agnostic agent that runs from your terminal. It connects local or hosted language models to persistent memory, reusable skills, guarded tools, project-aware coding workflows, and specialist agents.

The design goal is straightforward: **an agent you can inspect, configure, and improve**—not a black box that quietly assumes permission. AETHER keeps its runtime lightweight, its state local by default, and its boundaries visible.

[Try the CLI](#quick-start) · [Explore the architecture](docs/ARCHITECTURE.md) · [See the roadmap](docs/RELEASE_ROADMAP.md) · [Contribute](CONTRIBUTING.md) · [Report a bug](https://github.com/ghostfacethegreat/aether-agent/issues/new/choose)

## Why AETHER is worth evaluating

| Design priority | What it means in practice |
| --- | --- |
| **Bring your own model** | Use local Ollama, LM Studio, or llama.cpp endpoints, or configure hosted providers. Provider choice and billable usage remain visible. |
| **Keep your state** | Sessions and task records live in local SQLite; memory and skills remain inspectable and editable. |
| **Delegate with boundaries** | Specialist agents can work from dependency plans, share bounded budgets, inherit permissions, and be cancelled or resumed. |
| **Make coding work reviewable** | Search a repository, inspect a patch before applying it, require approval for writes, and run a bounded test command. |
| **Verify instead of guessing** | A separate verifier needs successful test/check evidence; a model saying “done” is not sufficient. |
| **Stay lightweight** | Python 3.10+ and no third-party runtime dependencies. External providers and optional integrations are not required for the mock demo. |

AETHER is designed for developers who value local-first workflows, provider flexibility, readable state, and explicit approval boundaries. It is an independent project—not an official Hermes Agent build or fork.

## Quick start

The current CLI Preview candidate is on the `feat/aether-parity-foundation` branch and is still under review in [PR #8](https://github.com/ghostfacethegreat/aether-agent/pull/8). The repository's default branch remains the earlier `0.1.0` alpha baseline until that work is merged.

```bash
git clone https://github.com/ghostfacethegreat/aether-agent.git
cd aether-agent
git checkout feat/aether-parity-foundation
python3 -m pip install -e .
```

Try the built-in mock provider first. It runs in-process and does not need an API key or network access:

```bash
aether --provider mock run "Say hello"
```

For a real local model, install and start [Ollama](https://ollama.com/), then run:

```bash
ollama pull llama3.2:3b
aether --provider ollama --model llama3.2:3b run "Explain this repository"
```

Start the interactive terminal:

```bash
aether
```

The mock provider is for deterministic testing and demos; it is not a language model. See [provider configuration](docs/PROVIDERS.md) and [the configuration guide](docs/CONFIGURATION.md) for the full setup.

## What is in the current candidate

- **Agent runtime:** provider abstraction, context budgeting, streaming, session history, plans, checkpoints, and recovery paths.
- **Memory and skills:** editable Markdown memory, layered SQLite-backed recall, reusable `SKILL.md` procedures, evidence-labelled learning proposals, review, versioning, and rollback.
- **Model routing:** inspectable provider/model selection using configured candidates, capability metadata, cost class, context limits, and local provider health.
- **Specialist teams:** dependency-aware planning, researcher/developer/debugger/tester/security/verifier/reviewer roles, bounded parallel execution, cancellation, and persisted run state.
- **Repository workflow:** bounded, ignore-aware indexing; lexical declaration search across Python, JavaScript/TypeScript, Lua, Go, and Rust; patch preview; approval-gated edits to existing UTF-8 files; and a bounded test runner.
- **Safety controls:** explicit tool permissions, approval prompts, path checks, URL restrictions, secret redaction, timeouts, and parent/child permission and budget boundaries.

These are documented capabilities of the preview candidate, not a claim that every workflow is complete or appropriate for unattended use. See [known limitations](docs/KNOWN_LIMITATIONS.md) before evaluating it on important work.

## Project status and evidence

> **Stage: Alpha / CLI Preview candidate.** PR #8 is still draft and unmerged. No tagged release or binary installer is being advertised.

The latest documentation, contributor-onboarding, and launch-plan head is [commit 4447b4b](https://github.com/ghostfacethegreat/aether-agent/commit/4447b4b872f4a184853d5219f215091a6e2b5bb9); both exact-head [push CI #116](https://github.com/ghostfacethegreat/aether-agent/actions/runs/45895191550) and [PR CI #117](https://github.com/ghostfacethegreat/aether-agent/actions/runs/45895195225) passed on that SHA.

**What this evidence does and does not show:**

- Unit and install checks provide regression and packaging evidence; they do not measure general task quality.
- AETHER does not yet publish a reproducible head-to-head benchmark against Hermes or other agent frameworks.
- No Hermes feature-parity, superiority, or “drop-in replacement” claim is made.
- No independent third-party security audit has been completed.
- AETHER is not a security sandbox. Shell and Python tools can execute with the permissions of the local user.

Read the [development status](docs/DEVELOPMENT_STATUS.md), [workstation acceptance gate](docs/WORKSTATION_ACCEPTANCE_GATE.md), [known limitations](docs/KNOWN_LIMITATIONS.md), [Hermes comparison](docs/HERMES_COMPARISON.md), and [benchmark protocol](benchmarks/README.md) for the evidence and remaining gaps.

## Documentation

| Start here | What you will find |
| --- | --- |
| [Architecture](docs/ARCHITECTURE.md) | Runtime, components, data flow, and design boundaries |
| [Providers](docs/PROVIDERS.md) | Local, hosted, mock, and custom provider setup |
| [Configuration](docs/CONFIGURATION.md) | Model settings, permissions, memory, scheduling, and orchestration |
| [Model routing](docs/MODEL_ROUTING.md) | Candidate selection, capability evidence, diagnostics, and limitations |
| [Agent workstreams](docs/AGENT_WORKSTREAMS.md) | Scoped development areas and parallel-agent guidance |
| [Launch plan](docs/LAUNCH_PLAN.md) | Positioning, demo checklist, channel strategy, and contributor growth |
| [Release roadmap](docs/RELEASE_ROADMAP.md) | Milestones and release gates |
| [Known limitations](docs/KNOWN_LIMITATIONS.md) | Current gaps, safety assumptions, and unverified behavior |
| [Benchmarks](benchmarks/README.md) | How task-quality comparisons will be run and reported |
| [CLI presentation](docs/CLI_PRESENTATION.md) | Terminal themes, ASCII fallback, and customization |

## Join the project

AETHER needs contributors who care about dependable agent workflows—not just more feature flags.

- **New to the codebase?** Start with [Contributing](CONTRIBUTING.md) and the [contributor on-ramp](docs/CONTRIBUTOR_ONRAMP.md).
- **Want a small first task?** Browse issues labelled [good first issue](https://github.com/ghostfacethegreat/aether-agent/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) or [help wanted](https://github.com/ghostfacethegreat/aether-agent/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22).
- **Found a defect?** Use the [bug report form](https://github.com/ghostfacethegreat/aether-agent/issues/new?template=bug_report.yml).
- **Have an idea?** Use the [feature request form](https://github.com/ghostfacethegreat/aether-agent/issues/new?template=feature_request.yml); discuss substantial changes before investing in a large implementation.
- **Found a security issue?** Follow [SECURITY.md](SECURITY.md); do not publish exploit details in a public issue.

Useful open work includes the coding workflow (#4), reproducible quality benchmarks (#6), evidence-grounded research (#10), tool discovery and validation (#11), and release hardening (#12). Check each issue for scope and acceptance criteria before starting.

## Safety and privacy

AETHER's permission system is a guardrail, not a sandbox. Review tool requests before approving them, use strict mode for unattended or unfamiliar workspaces, and do not run untrusted prompts with write/execute permissions in sensitive directories. Local memory, session state, and credentials should be treated as private user data.

## License and attribution

AETHER is released under the [MIT License](LICENSE). It is independently implemented and branded. Its architecture was informed by static review of the public [Hermes Agent](https://github.com/NousResearch/hermes-agent) project; AETHER is not affiliated with Nous Research. See [NOTICE](NOTICE) and [the upstream license record](docs/UPSTREAM_LICENSE.md).
