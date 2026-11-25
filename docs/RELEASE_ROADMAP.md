# Release Roadmap

This roadmap tracks the intelligence-first path from the current `0.1.0` alpha checkpoint to a verified `1.0.0` release. It is a status document, not a claim that any release has been published.

## Rules

1. Work in order; do not skip a release milestone.
2. Each implementation phase gets deterministic tests, full local checks, documentation updates, and a working checkpoint commit.
3. Preserve the Python core, provider framework, tools, memory, skills, scheduler, orchestration, cancellation, approvals, budgets, ASCII artwork, and colored rendering.
4. Keep runtime stdlib-first and practical on an 8 GB Apple Silicon Mac.
5. Use mock providers for ordinary tests. Never fabricate benchmarks or publish unverified claims.
6. Push, pull request, CI, merge, tag, and release only after that milestone's gates pass and the result has been confirmed.
7. If a milestone cannot pass, report the failure and keep the last verified checkpoint.

## Status summary

| Version | Theme | Status |
|---|---|---|
| `0.1.0` | local-first provider-agnostic CLI alpha | published baseline |
| `0.2.0` | intelligence foundation | in development; Phases A-E complete and locally verified, no `0.2.x` release or tag |
| `0.3.0` | autonomous software development | pending |
| `0.4.0` | messaging, voice, and improved automation | pending |
| `0.5.0` | desktop and website applications | pending |
| `0.9.0` | release candidate and fair comparisons | pending |
| `1.0.0` | reliable documented platform | pending |

## `0.2.0` — intelligence foundation

Goal: make Aether understand objectives, plan, execute, remember, learn, route models, verify, and recover without weakening the existing CLI.

| Phase | Outcome | Status |
|---|---|---|
| A | intelligence audit, Hermes comparison, benchmark contract | complete |
| B | adaptive planning and execution state | complete and locally verified |
| C | layered memory | complete and locally verified |
| D | learning loop and skill quality | complete and locally verified |
| E | model capability routing | implemented on this feature branch and locally verified (26 focused / 179 total tests); not released |
| F | coding workflow | pending |
| G | research and evidence | pending |
| H | tool intelligence | pending |
| I | specialist orchestration | pending |
| J | verification and recovery | pending |
| K | benchmark harness | pending |
| L | release hardening | pending |

Release gates:

- focused deterministic tests for every phase
- full local checks pass after every phase
- install/uninstall smoke test pass
- public docs describe implemented behavior only
- no benchmark or superiority claim without stored evidence
- no secrets, API keys, or `.env` files committed
- working checkpoint commit created
- only then push, open PR, verify CI, merge, tag, and publish accurate notes

Phase E verification is `python3 -W ignore::ResourceWarning -m unittest tests.test_model_routing -q` (26 passing) and `python3 -W ignore::ResourceWarning -m unittest discover -s tests -q` (179 passing). `bash scripts/check.sh && bash scripts/test_install.sh` passed with 3 cold starts, median wall time `0.114s`, peak child RSS `34.4 MiB`, and a local git-remote install test pass. `python3 scripts/benchmark.py` recorded 3 cold starts, median wall time `0.112s`, and peak child RSS `34.9 MiB`. `git diff --check` passed. `ResourceWarning` notices for unclosed SQLite connections are non-failing; no lint/typecheck command is configured. The package version remains `0.1.0` until an explicit release is confirmed.

The active phase detail is in [INTELLIGENCE_ROADMAP.md](INTELLIGENCE_ROADMAP.md). Verified history is in [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md). Known gaps are in [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

## `0.3.0` — autonomous software development

Planned capabilities:

- repository indexing, symbol lookup, and progressive retrieval
- test-first coding workflow with focused regression checks
- multi-agent development teams with evidence-based role selection
- durable long-running task supervision and recovery
- optional bounded browser automation through local configuration
- reviewed diffs and verified completion claims

Gates: fixture-repository tests, patch and rollback tests, multi-agent contract tests, long-task resume tests, full checks, docs, checkpoint commit, push, PR, CI, merge, tag, and release notes.

## `0.4.0` — messaging, voice, and automation

Planned capabilities:

- Telegram and Discord adapters as optional bounded interfaces
- session continuity across messaging platforms with strict user isolation
- voice input/output through configurable local or explicit provider paths
- improved scheduled automation and delivery controls

Gates: adapter tests with fake clients, credential isolation tests, user/session boundary tests, voice configuration tests, approval and cost regression tests, full checks, docs, checkpoint commit, publication flow.

## `0.5.0` — desktop and website applications

Planned capabilities:

- Tauri 2 desktop shell with React, TypeScript, and Vite
- optional local FastAPI service with authentication, strict bind address, CORS controls, and request limits
- macOS packaging with verified artifacts
- `apps/website/` documentation and download site
- membership tiers, if any, enforced server-side by the repository owner; never only in the client

Gates: desktop build, local service security tests, signed or clearly documented macOS artifact status, verified download links from actual GitHub release assets, website build, entitlement server tests, full checks, docs, checkpoint commit, publication flow.

## `0.9.0` — release candidate

Planned capabilities:

- full test, security, performance, installation, and user-acceptance pass
- reproducible task benchmark results under identical conditions
- fair Aether/Hermes comparisons with exact commands, models, prompts, tools, budgets, and environment
- known issues and migration notes

Gates: benchmark result artifacts, no fabricated numbers, external review of claims, fresh-clone install test, full checks, docs, checkpoint commit, RC tag only after verification.

## `1.0.0` — reliable platform

Release only when all of the following are true:

- critical tests and security checks pass
- installers and migrations are verified
- documentation matches actual behavior
- desktop packaging and optional integrations are verified
- cost, permission, and approval systems pass regression tests
- performance and startup checks pass
- limitations are published honestly
- benchmark evidence supports every comparative claim, or no comparative claim is made
- the working checkpoint is clean and fully verified before publication


## Hermes-competitive capability tracks

**Phase F coding workflow now has a tested baseline:** bounded repository indexing/search, unified-diff preview/application, and an approval-gated fixed-command test runner. It is not a full IDE-grade TDD controller.

Remaining tracks, in priority order:

1. **Browser and MCP:** local browser runtime with isolated profiles; secure URL/navigation controls; MCP stdio/HTTP servers, schema validation, and lazy tool discovery.
2. **Messaging and voice/media:** optional channel adapters, webhook authentication, user/session isolation, local-first speech input/output, and media tools.
3. **Execution backends:** optional Docker isolation first, then SSH/remote backends; durable background runs with cancellation, restart recovery, and bounded concurrency.
4. **Learning and curation:** model-assisted but reviewable skill drafting, duplicate/stale-skill detection, lifecycle states, isolated validation, and rollback.
5. **Evaluation:** reproducible task-quality fixtures, recorded tool traces, token/cost/time accounting, opt-in same-model Hermes comparisons, and regression gates.
6. **Coding completion:** persistent/incremental repository index, symbol navigation/LSP, create/delete patches, multi-turn TDD orchestration, and semantic diff review.

Do not mark a track complete from agent-profile files, issue creation, or design docs. Completion requires implementation, tests, clean-install checks, security review, and reproducible evidence artifacts. Hosted integrations and live model evaluations remain opt-in; no paid provider is required for default local operation.
