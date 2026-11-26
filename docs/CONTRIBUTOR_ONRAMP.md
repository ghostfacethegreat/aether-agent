# Contributor on-ramp

Welcome. You do not need to understand the entire agent runtime to make a useful contribution.

## A quick path in

1. Read the [README](../README.md) and [known limitations](KNOWN_LIMITATIONS.md).
2. Set up the project using [CONTRIBUTING.md](../CONTRIBUTING.md).
3. Choose a small issue labelled [good first issue](https://github.com/ghostfacethegreat/aether-agent/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) or [help wanted](https://github.com/ghostfacethegreat/aether-agent/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22).
4. Comment with your intended approach so work is not duplicated.
5. Submit a focused PR with tests or documentation evidence.

## Where help is useful

| Area | Starting point | Useful contributions |
| --- | --- | --- |
| First contribution: provider docs | [Issue #14](https://github.com/ghostfacethegreat/aether-agent/issues/14) | Local model setup checks, endpoint debugging, safe diagnostics, and log redaction |
| Coding workflow | [Issue #4](https://github.com/ghostfacethegreat/aether-agent/issues/4) | Search and patch edge cases, test fixtures, platform checks, and verification UX |
| Benchmarks | [Issue #6](https://github.com/ghostfacethegreat/aether-agent/issues/6) | Deterministic task fixtures, scoring guidance, reproducibility, and result review |
| Skill learning | [Issue #7](https://github.com/ghostfacethegreat/aether-agent/issues/7) | Lifecycle tests, rollback cases, and clearer review diagnostics |
| Research and evidence | [Issue #10](https://github.com/ghostfacethegreat/aether-agent/issues/10) | Source metadata fixtures, citation edge cases, and conflict/staleness tests |
| Tool discovery | [Issue #11](https://github.com/ghostfacethegreat/aether-agent/issues/11) | Schema-validation fixtures, discovery ranking tests, and permission-boundary cases |
| Release engineering | [Issue #12](https://github.com/ghostfacethegreat/aether-agent/issues/12) | Install/upgrade/rollback test plans, platform validation, and documentation |

The issues above vary in size. Start with #14 for a documentation-only first contribution; read the acceptance criteria and coordinate before changing shared core or persistence code.

## What makes a contribution valuable

- A regression test that captures a real bug.
- A small docs correction that removes ambiguity from a first-run task.
- A reproducible failure case with sanitized logs.
- A performance or compatibility result with its environment and command recorded.
- A carefully scoped change that preserves permissions, costs, cancellation, and local-first behavior.

AETHER values evidence over feature count. A small tested improvement is better than a broad unverified feature.
