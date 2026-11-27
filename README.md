<div align="center">

<img src="assets/banner.svg" alt="AETHER — local-first AI agent" width="100%" />

# AETHER

### A local-first AI agent built around visible state, provider choice, and deliberate control.

<p>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-22c55e?style=flat-square" alt="MIT license"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/Python-3.10%2B-3776ab?style=flat-square&logo=python&logoColor=white" alt="Python 3.10 or newer"></a>
  <a href="docs/DEVELOPMENT_STATUS.md"><img src="https://img.shields.io/badge/status-alpha-f59e0b?style=flat-square" alt="Alpha status"></a>
  <a href="https://github.com/ghostfacethegreat/aether-agent/actions/workflows/ci.yml"><img src="https://github.com/ghostfacethegreat/aether-agent/actions/workflows/ci.yml/badge.svg?branch=feat%2Faether-parity-foundation" alt="AETHER CI"></a>
</p>

[Quick start](#-quick-start) · [Architecture](#-how-it-fits-together) · [Capabilities](#-what-aether-does) · [Documentation](#-documentation) · [Contributing](#-build-with-us)

</div>

---

**AETHER connects the models you choose to persistent memory, reusable skills, specialist agents, and reviewable tools.** It runs as a Python CLI, keeps its working state local by default, and makes consequential actions visible before they happen.

It is an independent project inspired by public agent research. It is not an official Hermes Agent build, fork, or affiliated project.

## ✦ The AETHER approach

| Local-first by default | Provider-agnostic | Control you can inspect |
| --- | --- | --- |
| SQLite sessions and task records, plus editable Markdown memory and skills. | Local inference or supported hosted APIs, with provider choice and cost class visible. | Approval-gated writes, bounded tools, explicit permissions, and verification evidence. |

AETHER is intentionally lightweight: **Python 3.10+ with no third-party runtime dependencies**. The built-in mock provider makes it possible to run deterministic demos and tests without an API key or network request. It is a test/demo provider, not a language model.

## 🚀 Quick start

The current CLI Preview candidate is available on `feat/aether-parity-foundation` and is under review in [draft PR #8](https://github.com/ghostfacethegreat/aether-agent/pull/8). The default branch remains the earlier `0.1.0` alpha baseline until that work is reviewed and merged.

```bash
git clone https://github.com/ghostfacethegreat/aether-agent.git
cd aether-agent
git checkout feat/aether-parity-foundation
python3 -m pip install -e .
```

### First run: no key, no network

```bash
aether --provider mock run "Say hello"
```

Example output from a real local terminal capture:

```text
Aether mock provider is active. No network request was made.
Use /provider ollama (or another configured provider) for real inference.
```

### Run a local model

Install and start [Ollama](https://ollama.com/), then:

```bash
ollama pull llama3.2:3b
aether --provider ollama --model llama3.2:3b run "Explain this repository"
```

Launch the interactive terminal with:

```bash
aether
```

Inside chat, type `/help` to discover commands. The mock provider is useful for smoke tests; use a configured local or hosted model for real inference.

## 🧭 What AETHER does

| Capability | What is included |
| --- | --- |
| **Agent runtime** | Provider adapters, context budgeting, streaming, session history, plans, checkpoints, and recovery paths. |
| **Memory and skills** | Editable Markdown memory, SQLite-backed recall layers, reusable `SKILL.md` procedures, evidence-labelled learning proposals, review, versioning, and rollback. |
| **Model routing** | Inspectable provider/model selection using configured candidates, capability metadata, cost class, context limits, and local health records. |
| **Specialist teams** | Dependency-aware planning, bounded parallel execution, structured results, persisted run state, cancellation, and resume. |
| **Coding workflow** | Bounded repository indexing and symbol search, patch preview, approval-gated edits to existing UTF-8 files, and a bounded test runner. |
| **Safety boundaries** | Tool permissions, approval prompts, path checks, URL restrictions, secret redaction, timeouts, and parent/child budget boundaries. |

### How it fits together

<p align="center">
  <img src="assets/architecture.svg" alt="AETHER architecture: CLI, agent runtime, planning and context, permission gate, approved tools, local state, and model providers." width="100%" />
</p>

### A look inside the terminal

The repository includes real text captures from local runs. These examples use the mock provider unless the capture explicitly says otherwise.

- [Status dashboard](docs/screenshots/01-status.txt)
- [Mock-provider run](docs/screenshots/02-mock-run.txt)
- [Provider catalog](docs/screenshots/03-providers.txt)
- [Doctor diagnostics](docs/screenshots/04-doctor.txt)

## 🔌 Model providers

The provider catalog includes local options such as `ollama`, `lmstudio`, and `llamacpp`, plus hosted adapters including `groq`, `cerebras`, `huggingface`, `gemini`, `openrouter`, `openai`, `anthropic`, and `custom`.

```bash
aether providers
aether --provider mock --model mock-tools run "Use a tool"
```

Provider pricing, model IDs, availability, and free-tier quotas can change. AETHER does not bypass provider restrictions or make hosted inference free. Check the provider's current terms and dashboard before using a hosted service. See [provider setup](docs/PROVIDERS.md).

## 🛡️ Control, privacy, and limitations

- **You stay in the loop.** Write, execute, and network actions can require approval. Strict mode and explicit tool allow-lists are recommended for unfamiliar or unattended workspaces.
- **Local state is inspectable.** Sessions and task records live in local SQLite; memory and skills are editable local files.
- **Hosted means hosted.** When you select a hosted provider, request content is sent to that provider and is subject to its terms and privacy policy.
- **Not a sandbox.** Tool subprocesses inherit the permissions of the local user. Approval prompts are guardrails, not an OS-level isolation boundary.
- **No parity promises.** AETHER is alpha. It does not claim Hermes feature parity, equivalent task quality, or superiority over other agent frameworks.

Read [known limitations](docs/KNOWN_LIMITATIONS.md) and [SECURITY.md](SECURITY.md) before using AETHER with sensitive workspaces or untrusted prompts.

## 📚 Documentation

| Guide | Purpose |
| --- | --- |
| [Architecture](docs/ARCHITECTURE.md) | Runtime components, data flow, and design boundaries |
| [Providers](docs/PROVIDERS.md) | Local, hosted, mock, and custom provider setup |
| [Configuration](docs/CONFIGURATION.md) | Models, permissions, memory, scheduling, and orchestration |
| [Model routing](docs/MODEL_ROUTING.md) | Candidate selection, capability evidence, diagnostics, and limitations |
| [Agent workstreams](docs/AGENT_WORKSTREAMS.md) | Scoped development areas and parallel-agent guidance |
| [Known limitations](docs/KNOWN_LIMITATIONS.md) | Current gaps, safety assumptions, and unverified behavior |
| [Development status](docs/DEVELOPMENT_STATUS.md) | Evidence log, verification state, and release boundaries |
| [Release roadmap](docs/RELEASE_ROADMAP.md) | Milestones and release gates |
| [Benchmarks](benchmarks/README.md) | Reproducible evaluation approach and reporting rules |
| [CLI presentation](docs/CLI_PRESENTATION.md) | Terminal themes, ASCII fallback, and customization |
| [Launch plan](docs/LAUNCH_PLAN.md) | Project positioning, demo checklist, and contributor growth |

## 🤝 Build with us

AETHER is open source and welcomes focused contributions in Python/CLI engineering, local-model integrations, evaluation, reliability, security review, and documentation.

- **New here?** Start with the [contributor on-ramp](docs/CONTRIBUTOR_ONRAMP.md).
- **Want to collaborate?** Introduce yourself in the [contributor call](https://github.com/ghostfacethegreat/aether-agent/issues/15).
- **Need a starter task?** See [issue #14](https://github.com/ghostfacethegreat/aether-agent/issues/14).
- **Found a bug or have an idea?** Use the [issue chooser](https://github.com/ghostfacethegreat/aether-agent/issues/new/choose).
- **Found a security issue?** Follow the private reporting guidance in [SECURITY.md](SECURITY.md).

This is an open-source volunteer project, not a paid job posting. There is no minimum contribution commitment; a small, tested improvement is welcome.

## 📜 Project status, license, and attribution

- **Stage:** alpha / CLI Preview candidate.
- **Review:** PR #8 is open, draft, and unmerged.
- **Release:** package version remains `0.1.0`; no tagged release or binary installer is advertised.
- **Evidence:** CI and local test results are recorded in [Development Status](docs/DEVELOPMENT_STATUS.md). Passing tests show engineering checks, not general task quality or model superiority.

AETHER is distributed under the [MIT License](LICENSE). Its architecture was informed by static review of the public [Hermes Agent](https://github.com/NousResearch/hermes-agent) repository; AETHER is independently implemented and branded. See [NOTICE](NOTICE) and [the upstream license record](docs/UPSTREAM_LICENSE.md).

---

<div align="center">

**AETHER** · Build deliberately. Keep control.

<sub>Local-first · Provider-agnostic · Evidence over hype</sub>

</div>
