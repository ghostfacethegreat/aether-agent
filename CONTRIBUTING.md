# Contributing to AETHER

Thanks for considering a contribution. AETHER is an independent, local-first agent project, and the most useful contributions make it more reliable, understandable, secure, and easier for someone else to use.

## Before you start

1. Read the [README](README.md), [known limitations](docs/KNOWN_LIMITATIONS.md), and [architecture guide](docs/ARCHITECTURE.md).
2. Search [open issues](https://github.com/ghostfacethegreat/aether-agent/issues) for related work.
3. For a substantial change, comment on an existing issue or open a discussion issue before writing a large patch. Agree on scope and acceptance criteria first.
4. For a first contribution, browse issues labelled [good first issue](https://github.com/ghostfacethegreat/aether-agent/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) or [help wanted](https://github.com/ghostfacethegreat/aether-agent/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22).

Please do not start a large parity, persistence, provider, or permission refactor without coordinating with the maintainer. Some workstreams share core files and SQLite schemas.

## Development setup

AETHER targets Python 3.10+ and uses the Python standard library at runtime.

```bash
git clone https://github.com/ghostfacethegreat/aether-agent.git
cd aether-agent
git checkout feat/aether-parity-foundation
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[dev]'
```

Use the mock provider for tests and examples. It does not make network requests or require a paid model account:

```bash
aether --provider mock run "Say hello"
```

## Verification before a pull request

Run the checks relevant to your change. For runtime or tooling changes, run the full set:

```bash
python3 -m compileall -q aether tests
python3 -m unittest discover -s tests -v
bash scripts/check.sh
bash scripts/test_install.sh
git diff --check
```

GitHub Actions checks Linux on Python 3.10–3.14 and macOS 15 ARM64 on Python 3.12 and 3.14. Both platforms run the deterministic project checks and clean-checkout install test. CI must not require paid API keys, live model calls, or external services. Live provider tests must be opt-in and clearly separated from deterministic tests. The macOS CI job is a hosted compatibility check, not a substitute for testing on every supported macOS version or on a contributor's own hardware.

In your PR, include the exact commands run and their outcomes. Do not say tests pass unless you ran them on the commit being submitted. If a platform-specific check was not run, say so.

## Project design principles

- **Local-first:** ordinary CLI use must not require a hosted service or paid account.
- **Provider-agnostic:** provider-specific behavior belongs behind the existing provider interfaces.
- **Lightweight runtime:** prefer the standard library; justify any new mandatory dependency.
- **Explicit permissions:** never weaken approvals, allowed roots, forced-deny rules, URL policy, or parent/child permission inheritance to make a demo pass.
- **Bounded cost and execution:** preserve timeout, budget, cancellation, and retry guarantees.
- **Evidence over claims:** model output is not proof that a task succeeded. Verification needs real tool/test evidence.
- **Backward-compatible state:** treat SQLite migrations, Markdown memory, and user data as compatibility-sensitive.
- **Honest documentation:** distinguish implemented, partial, planned, and unverified behavior.

## Code map

- `aether/core/`: agent loop, context, state, and planning.
- `aether/providers/`: provider catalog and transports.
- `aether/routing/`: task classification and model selection.
- `aether/tools/`: tool definitions, permissions, and execution.
- `aether/coding/`: repository indexing and patch workflow.
- `aether/memory/` and `aether/learning/`: persistent memory and evidence-based skill learning.
- `aether/orchestration/`: specialist agents, plans, dependency execution, and recovery.
- `aether/persistence/`: SQLite state and migrations.
- `aether/cli/`: command parsing, terminal UI, and user-facing output.
- `tests/`: deterministic unit and integration coverage.
- `docs/` and `benchmarks/`: design records, limitations, release checks, and evaluation protocol.

## Pull request expectations

A good PR should:

1. Solve one coherent problem and link the relevant issue.
2. Include focused tests for new behavior and regression tests for bugs.
3. Update user-facing docs when commands, configuration, behavior, or limitations change.
4. Explain compatibility, security, privacy, and provider-cost implications.
5. Include verification commands and real results.
6. Keep unrelated formatting, generated files, secrets, and local state out of the diff.

Use short, imperative commit subjects such as `routing: explain rejected model candidates` or `tests: cover scheduler cancellation`.

## Security and responsible disclosure

Never commit API keys, access tokens, cookies, `.env` files, real session logs, local databases, or private user data. Redact secrets from diagnostic output before sharing it.

Do not report a vulnerability in a public issue. Follow [SECURITY.md](SECURITY.md) for private reporting guidance.

## Community expectations

Be respectful and constructive. Explain technical disagreements with evidence, review work on its merits, and make space for first-time contributors. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
