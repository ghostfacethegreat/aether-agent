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

- [ ] Package skeleton with stdlib-only dependencies and Python 3.11+ support.
- [ ] Config load/save with defaults under `AETHER_HOME`.
- [ ] Message types, turn state, bounded loop, tool-call normalization.
- [ ] Built-in `mock` provider for tests/demos.
- [ ] CLI dashboard, streaming output, slash commands, colored logs.
- [ ] SQLite session persistence for messages.
- [ ] Tests: agent loop, CLI parsing, persistence.

**Verification:** `python3 -m unittest discover -s tests -v`; CLI smoke test with mock provider.

## Milestone 3 — Model providers and free/local inference

**Goal:** genuinely usable model choice without a mandatory paid account.

- [ ] Provider catalog with cost/auth metadata.
- [ ] OpenAI-compatible transport with streaming, retries, and error classification.
- [ ] Local profiles: Ollama, LM Studio, llama.cpp.
- [ ] Optional free-tier profiles: Groq, Cerebras, Hugging Face Router, Gemini, OpenRouter free models.
- [ ] Optional paid profiles: OpenAI, Anthropic native, custom endpoint.
- [ ] Runtime model/provider switching and ordered fallback.
- [ ] Provider limit/cost display in `/providers` and `aether doctor`.
- [ ] Tests: request/response normalization, SSE parsing, fallback, switching.

## Milestone 4 — Memory, skills, and persistent context

**Goal:** local-first learning and recall.

- [ ] `MEMORY.md` / `USER.md` store with char budgets and frozen prompt snapshot.
- [ ] SQLite FTS conversation search with substring fallback.
- [ ] Memory tool actions: add, replace, delete, search, list, export, import.
- [ ] Skill parser, discovery roots, progressive disclosure, usage tracking.
- [ ] Built-in skills: `code-review`, `debug`, `web-research`.
- [ ] Context budget manager with summarization/truncation.
- [ ] Tests: memory CRUD/search/import/export, skill discovery/create/edit, context compression.

## Milestone 5 — Tools, coding agent, and subagents

**Goal:** reliable execution with explicit permissions.

- [ ] Tool registry with JSON schemas, risk metadata, output caps.
- [ ] File tools, terminal tool, git tool, Python runner.
- [ ] Web fetch/search with URL validation and optional keyed backends.
- [ ] Configurable browser command provider (disabled by default).
- [ ] Task ledger and parallel subagents with isolated context and reduced toolsets.
- [ ] Scheduler with local `cron/jobs.json`.
- [ ] Tests: tool validation/execution, permissions, subagent aggregation, scheduler tick.

## Milestone 6 — Customization, permissions, integrations

**Goal:** user-controlled behavior without disabling security indiscriminately.

- [ ] Personality/system prompt config.
- [ ] Tool allow/deny lists and path roots.
- [ ] Approval callback with session/always/deny choices.
- [ ] `local-dev` mode that relaxes non-destructive checks only.
- [ ] Integration config validation and secret redaction in logs.
- [ ] Tests: permission matrix, approval persistence, redaction, config validation.

## Milestone 7 — Testing, performance, bug fixing

**Goal:** release-quality reliability on 8 GB Apple Silicon.

- [ ] Expand regression suite across loop, providers, memory, skills, permissions, tools, CLI.
- [ ] Benchmark cold start and RSS with `scripts/benchmark.py`.
- [ ] Run `scripts/check.sh` (compile, tests, secret scan, CLI smoke).
- [ ] Fix all discovered issues before release.
- [ ] Record actual results in `docs/RELEASE_CHECKS.md`.

## Milestone 8 — Installer, documentation, branding, GitHub publication

**Goal:** professional, honest public release.

- [ ] One-command macOS installer, uninstaller, update, and diagnostics.
- [ ] Locally test installer against a local git remote.
- [ ] Branding assets (SVG logo/banner), README, provider/config guides, SECURITY, CONTRIBUTING, CHANGELOG.
- [ ] Generate screenshots from a real mock-provider CLI run; label the provider clearly.
- [ ] Full release checks: tests, secrets, license attribution, README links, repo contents.
- [ ] Create `aether-agent` GitHub repo under the authenticated account if available.
- [ ] Push source. Do not publish a hosted `curl | bash` command unless the hosted installer was verified.

## Checkpoint protocol

For each milestone, the following will be recorded in the final response:

1. Features completed.
2. Files created or modified.
3. Tests actually performed.
4. Remaining bugs.
5. Next milestone.

Every checkpoint must be a commit with a concise message. No commit will contain secrets, `.env` files, fabricated results, or unverified claims.
