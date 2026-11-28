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
| `0.2.0` | intelligence foundation | CLI Preview verification slice: 274 local tests OK, workstation gate PASS, integration base CI green (#90); PR #8 open draft; G/H/K/L pending and I/J partial; no `0.2.x` release or tag |
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
| E | model capability routing | implemented on this feature branch; included in the current 274-test local suite; not released |
| F | coding workflow | tested baseline implemented and included in the current 274-test local suite; autonomous TDD/LSP/diff review incomplete |
| G | research and evidence | pending — [issue #10](https://github.com/ghostfacethegreat/aether-agent/issues/10) |
| H | tool intelligence | pending — [issue #11](https://github.com/ghostfacethegreat/aether-agent/issues/11) |
| I | specialist orchestration | partial: specialist roles, dependency-aware teams, contracts, verifier baseline; isolated durable execution tracked in [issue #5](https://github.com/ghostfacethegreat/aether-agent/issues/5) |
| J | verification and recovery | partial: evidence-gated verifier and resumable checkpoints; long-running supervision/repair loops incomplete; see [issues #4](https://github.com/ghostfacethegreat/aether-agent/issues/4) and [#5](https://github.com/ghostfacethegreat/aether-agent/issues/5) |
| K | benchmark harness | pending — [issue #6](https://github.com/ghostfacethegreat/aether-agent/issues/6) |
| L | release hardening | pending — [issue #12](https://github.com/ghostfacethegreat/aether-agent/issues/12) |

Release gates:

- focused deterministic tests for every phase
- full local checks pass after every phase
- install/uninstall smoke test pass
- public docs describe implemented behavior only
- no benchmark or superiority claim without stored evidence
- no secrets, API keys, or `.env` files committed
- working checkpoint commit created
- only then push, open PR, verify CI, merge, tag, and publish accurate notes

Current verification for the CLI Preview slice: `python3 -m compileall -q aether tests` OK; `python3 -m unittest discover -s tests -v` 274 tests OK; `bash scripts/check.sh` 274 tests OK (3 cold starts, median wall time 0.119s, peak child RSS 33.0 MiB, all checks passed); `bash scripts/test_install.sh` OK; `git diff --check` OK. Focused verification before the full suite ran 182 tests across tools, model routing, orchestration, tasks, planning, core, persistence, render, and repository tools; deterministic CLI tests also cover doctor, provider/model switching, and plan status. `tests.test_coding_workflow` adds a real end-to-end mock-provider coding workflow with a second scripted verification agent; the orchestrator verifier evidence gate has separate deterministic coverage in `tests.test_orchestration`. Final pushed CLI Preview candidate `939208dc0622e9bfc661ece1eb3f4faf83f2b6db` passed exact-head push CI run [#91](https://github.com/ghostfacethegreat/aether-agent/actions/runs/45893216507) and PR CI run [#92](https://github.com/ghostfacethegreat/aether-agent/actions/runs/45893225173); both runs succeeded across Python 3.10–3.14, including project checks and clean-checkout install/uninstall. The Python 3.14 push-job log records 274 tests. This verifies the preview slice, not the full Phase G–L or 1.0 scope. SQLite connections are now closed; no lint/typecheck command is configured. The package version remains `0.1.0` until an explicit release is confirmed.

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

**Phase F coding workflow now has a tested baseline:** bounded persistent repository indexing/search, lexical symbol retrieval, unified-diff preview/application, and an approval-gated fixed-command test runner. Final CLI Preview candidate `939208dc0622e9bfc661ece1eb3f4faf83f2b6db` passed exact-head CI push run [#91](https://github.com/ghostfacethegreat/aether-agent/actions/runs/45893216507) and PR run [#92](https://github.com/ghostfacethegreat/aether-agent/actions/runs/45893225173) across Python 3.10–3.14; the Python 3.14 push-job log records 274 tests and clean-checkout installation. The local macOS workstation acceptance gate is also recorded as passed. Bounded repair loops are a roadmap item, not implemented. This is not a full IDE-grade TDD controller; the macOS workstation gate passed for the CLI Preview checklist, but task-quality and live-provider gates remain open.

Remaining tracks, in priority order:

1. **Research and evidence (Phase G):** source metadata, claim-level citations, contradiction/staleness detection, confidence rationale, and traceable reports ([issue #10](https://github.com/ghostfacethegreat/aether-agent/issues/10)).
2. **Tool intelligence (Phase H):** capability catalog, query-based discovery, staged schema loading, strict argument validation, permission-aware selection, and tool-health recovery ([issue #11](https://github.com/ghostfacethegreat/aether-agent/issues/11)).
1. **Browser and MCP:** local browser runtime with isolated profiles; secure URL/navigation controls; MCP stdio/HTTP servers, schema validation, and lazy tool discovery ([issue #2](https://github.com/ghostfacethegreat/aether-agent/issues/2)).
2. **Messaging and voice/media:** optional channel adapters, webhook authentication, user/session isolation, local-first speech input/output, and media tools ([issue #3](https://github.com/ghostfacethegreat/aether-agent/issues/3)).
3. **Execution backends:** optional Docker isolation first, then SSH/remote backends; durable background runs with cancellation, restart recovery, and bounded concurrency ([issue #5](https://github.com/ghostfacethegreat/aether-agent/issues/5)).
4. **Learning and curation:** model-assisted but reviewable skill drafting, duplicate/stale-skill detection, lifecycle states, isolated validation, and rollback ([issue #7](https://github.com/ghostfacethegreat/aether-agent/issues/7)).
5. **Evaluation:** reproducible task-quality fixtures, recorded tool traces, token/cost/time accounting, opt-in same-model Hermes comparisons, and regression gates ([issue #6](https://github.com/ghostfacethegreat/aether-agent/issues/6)).
6. **Coding completion:** persistent/incremental repository index, symbol navigation/LSP, create/delete patches, multi-turn TDD orchestration, and semantic diff review ([issue #4](https://github.com/ghostfacethegreat/aether-agent/issues/4)).

Do not mark a track complete from agent-profile files, issue creation, or design docs. Completion requires implementation, tests, clean-install checks, security review, and reproducible evidence artifacts. Hosted integrations and live model evaluations remain opt-in; no paid provider is required for default local operation.
