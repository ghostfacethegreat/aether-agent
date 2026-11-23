# Aether Implementation Plan

This plan is intentionally milestone-based. Each milestone ends with a working checkpoint, real tests, and documentation updates. Status is updated as work lands.

## Milestone 1 — Source audit and architecture map

**Goal:** understand upstream before writing Aether code.

- [x] Clone upstream at pinned commit.
- [x] Map entry points, core loop, provider/transport layer, tool runtime, memory, skills, persistence, cron, subagents, CLI/TUI, gateway, install, tests, license.
- [x] Identify subscription/API-key dependencies and security risks.
- [x] Write `docs/ARCHITECTURE.md`, `docs/FEATURE_MATRIX.md`, `docs/IMPLEMENTATION_PLAN.md`.
- [x] Create repository, license, NOTICE, and baseline `.gitignore`.

**Exit criteria:** architecture docs exist and are grounded in inspected files. No Aether runtime code written yet.

## Milestone 2 — Minimal working Aether agent and CLI

**Goal:** a real turn loop with a deterministic provider and a usable terminal interface.

- [x] Package skeleton with stdlib-only dependencies and Python 3.10+ support.
- [x] Config load/save with defaults under `AETHER_HOME`.
- [x] Message types, turn state, bounded loop, tool-call normalization.
- [x] Built-in `mock` provider for tests/demos.
- [x] CLI dashboard, streaming output, slash commands, colored logs.
- [x] SQLite session persistence for messages.
- [x] Tests: agent loop, CLI parsing, persistence.

**Verification:** `python3 -m unittest discover -s tests -v`; CLI smoke test with mock provider.

## Milestone 3 — Model providers and free/local inference

**Goal:** genuinely usable model choice without a mandatory paid account.

- [x] Provider catalog with cost/auth metadata.
- [x] OpenAI-compatible transport with streaming, retries, and error classification.
- [x] Local profiles: Ollama, LM Studio, llama.cpp.
- [x] Optional free-tier profiles: Groq, Cerebras, Hugging Face Router, Gemini, OpenRouter free models.
- [x] Optional paid profiles: OpenAI, Anthropic native, custom endpoint.
- [x] Runtime model/provider switching and ordered fallback.
- [x] Provider limit/cost display in `aether providers` and `aether doctor`.
- [x] Tests: request/response normalization, synthetic SSE parsing, fallback, switching.

## Milestone 4 — Memory, skills, and persistent context

**Goal:** local-first learning and recall.

- [x] `MEMORY.md` / `USER.md` store with char budgets and frozen prompt snapshot.
- [x] SQLite FTS conversation search with substring fallback.
- [x] Memory tool actions: add, replace, delete, search, list, export, import.
- [x] Skill parser, discovery roots, progressive disclosure, usage tracking.
- [x] Built-in skills: `code-review`, `debug`, `web-research`.
- [x] Context budget manager with summarization/truncation.
- [x] Tests: memory CRUD/search/import/export, skill discovery/create/edit, context compression.

## Milestone 5 — Tools, coding agent, and subagents

**Goal:** reliable execution with explicit permissions.

- [x] Tool registry with JSON schemas, risk metadata, output caps.
- [x] File tools, terminal tool, git tool, Python runner.
- [x] Web fetch/search with URL validation and optional keyed backends.
- [x] Configurable browser command provider (disabled by default).
- [x] Task ledger and parallel subagents with isolated context and reduced toolsets.
- [x] Scheduler with local `cron/jobs.json`.
- [x] Tests: tool validation/execution, permissions, subagent aggregation, scheduler tick.

## Milestone 6 — Customization, permissions, integrations

**Goal:** user-controlled behavior without disabling security indiscriminately.

- [x] Personality/system prompt config.
- [x] Tool allow/deny lists and path roots.
- [x] Approval callback with session/always/deny choices.
- [x] `local-dev` mode that relaxes non-destructive checks only.
- [x] Integration config validation and secret redaction in logs.
- [x] Tests: permission matrix, redaction, config validation.

## Milestone 7 — Testing, performance, bug fixing

**Goal:** release-quality reliability on 8 GB Apple Silicon.

- [x] Expand regression suite across loop, providers, memory, skills, permissions, tools, CLI.
- [x] Benchmark cold start and RSS with `scripts/benchmark.py`.
- [x] Run `scripts/check.sh` (compile, tests, secret scan, CLI smoke, benchmark).
- [x] Fix all discovered issues before release.
- [x] Record actual results in `docs/RELEASE_CHECKS.md`.

## Milestone 8 — Installer, documentation, branding, GitHub publication

**Goal:** professional, honest public release.

- [x] One-command macOS installer, uninstaller, update, and diagnostics.
- [x] Locally test installer against a local git remote.
- [x] Branding assets (SVG logo/banner), README, provider/config guides, SECURITY, CONTRIBUTING, CHANGELOG.
- [x] Generate screenshots from a real mock-provider CLI run; label the provider clearly.
- [x] Full local release checks: tests, secrets, license attribution, README links, repo contents.
- [x] Create `aether-agent` GitHub repo under the authenticated account if available.
- [x] Push source. Do not publish a hosted `curl | bash` command unless the hosted installer was verified.

## Checkpoint protocol

For each milestone, the following will be recorded in the final response:

1. Features completed.
2. Files created or modified.
3. Tests actually performed.
4. Remaining bugs.
5. Next milestone.

Every checkpoint must be a commit with a concise message. No commit will contain secrets, `.env` files, fabricated results, or unverified claims.

**Current checkpoint:** Phase 1 is committed and pushed to <https://github.com/ghostfacethegreat/aether-agent>. Phase 2 begins with [PHASE2_FEATURE_COMPARISON.md](PHASE2_FEATURE_COMPARISON.md) and [PHASE2_ROADMAP.md](PHASE2_ROADMAP.md); no Hermes parity is claimed until each capability is implemented and verified.
