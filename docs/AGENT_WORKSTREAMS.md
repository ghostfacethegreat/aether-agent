# Parallel agent workstreams

AETHER's custom agent profiles are stored in `.github/agents/`. They provide scoped instructions for independent coding streams; they do not start themselves. Launch each profile through GitHub Copilot's Agents interface or assign an issue to the Copilot coding agent, using `feat/aether-parity-foundation` as the base branch.

| Stream | Profile | Scope |
|---|---|---|
| Orchestration | `aether-orchestration` | task graphs, contracts, verifier, background execution and resume |
| Context and memory | `aether-context-memory` | project context, layered recall, context snapshots and fitting |
| Integrations | `aether-integrations` | browser, MCP, messaging, voice and media adapters |
| Quality | `aether-quality` | CI, test harness, benchmarks and security regressions |

Assign one file/domain owner per stream before parallel work. Require each stream to submit a PR against the parity foundation branch. Avoid independent edits to the same core files. The integration pass must review each diff, run the full suite, and resolve conflicts before merge.

## Current foundation

This branch adds bounded project-context loading, dependency-aware specialist planning, an evidence-gated verifier, structured role contracts, CI, and scoped agent profiles. Browser/MCP/messaging/voice/desktop adapters, advanced sandbox backends, repository indexing/TDD, and task-quality parity remain separate workstreams.
