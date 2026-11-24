# Aether Intelligence Audit

This document is the Phase A source of truth for the intelligence-first `Aether 0.2+` work. It records what Aether can do today, where its reasoning and learning systems are thin, and which capabilities are worth adopting from Hermes Agent without copying upstream code or infrastructure.

Phase A is a documentation and benchmark-contract checkpoint. It does not claim that any new runtime behavior was implemented in that phase. This audit remains the Phase A source of truth at the commits below; later phases have closed some gaps, including Phase E capability-aware routing, which is implemented on this feature branch and locally verified (26 focused / 179 total tests) but not released.

## Scope and evidence

| Item | Value |
|---|---|
| Aether audit commit | `558bd58ec1f15ccf9cf76260d3ab7bfe675e76ce` |
| Aether baseline commit | `01ee003795787cc392f033edffbb98fcb3dd8b35` |
| Hermes pinned comparison commit | `b98c388a880b1b6fd303c9c2821a3946651a0b4c` |
| Hermes current `main` checked in Phase A | `fe9a4b58ec137d3e00719c10e2385876fa03b97c` |
| Method | static source review, documentation review, and local test/benchmark record review |
| Runtime comparison | not run; no benchmark results exist yet |
| External source | <https://github.com/NousResearch/hermes-agent> |
| Documentation source | <https://hermes-agent.nousresearch.com/docs/> |

The previous Hermes comparison remains useful history, but the current `main` commit and newer feature docs expand the learning loop, tool discovery, delegation contracts, profiles, and evaluation surface. This audit distinguishes observed facts from design choices and from proposed Aether work.

No Hermes code was copied into Aether. Aether is independently implemented and remains MIT-licensed with the upstream notices in [UPSTREAM_LICENSE.md](UPSTREAM_LICENSE.md).

## Executive summary

Aether already has a reliable local-first core: bounded turns, provider fallback, tools with permissions, SQLite persistence, Markdown memory, `SKILL.md` skills, an in-process scheduler, subagents, and a dependency-aware orchestrator with shared budgets, cancellation, approvals, and recovery. Those are strong foundations.

The main weakness is not terminal appearance. It is that Aether still mostly reacts one turn at a time. It has no explicit adaptive planner, no execution-state machine with recoverable plan checkpoints, no layered memory model, no evidence-based learning loop, no capability-aware model routing, no repository-indexed coding workflow, no research evidence pipeline, and no task-success benchmark suite.

Hermes is ahead in several intelligence-related areas: an advertised closed learning loop, agent-created and self-improving skills, curated memory, session search, user modeling, cron automations, parallel delegation with output schemas, tool search, and a visible eval suite. Aether should adopt the useful patterns in its own small, stdlib-first design, not the upstream's hosted services, large UI stack, plugin marketplaces, or provider lock-in.

No conclusion here says that Aether is better or worse than Hermes overall. That requires the benchmark harness in [benchmarks/README.md](../benchmarks/README.md) and actual results under the same conditions.

## Capability gap register

| Area | Aether at `558bd58` | Observed gap | Priority |
|---|---|---|---|
| Adaptive planning | `todo` tool and orchestrator dependency plans exist | No general plan object with objective, constraints, dependencies, risk, alternatives, tools, expected results, and verification criteria | High |
| Execution state | `TurnState` and a bounded `run_turn_loop()` drive each turn | No durable per-objective state machine, phase transitions, checkpoints, or recovery planner | High |
| Verification | Exit reasons, retries, cancellation, and fallbacks exist | No independent verifier of files, tests, evidence, requirements, or completion claims | High |
| Layered memory | `MEMORY.md`, `USER.md`, and FTS-backed session search | No working, episodic, semantic, procedural, and user-model layers with provenance, confidence, consolidation, or expiration | High |
| Learning loop | Skills can be created and viewed; usage counts exist | No outcome-based experience records, skill discovery, quality review, version history, rollback, or learning log | High |
| Skill quality | Injection-pattern rejection and built-in/user labels | No skill curation lifecycle, evidence requirements, archive/restore, or per-mutation audit ledger | High |
| Model routing | Catalog, ordered fallback, cost labels, and paid gating | No capability registry at `558bd58`; Phase E has since added evidence-aware facts, deterministic classification, and scored routing over configured candidates (not task-quality proof) | High |
| Coding workflow | File, terminal, git, Python, and orchestration tools | No repository index, symbol/dependency lookup, progressive file retrieval, patch workflow, TDD loop, regression detection, or diff review | High |
| Research workflow | `web_fetch`, `web_search`, and `session_search` tools | No query planning, source comparison, citation extraction, contradiction detection, fact checking, or confidence separation | High |
| Tool intelligence | JSON schemas, permissions, approvals, timeouts, and redaction | No capability search/schema deferral, preflight checks, result verification, or usage analytics | Medium |
| specialist orchestration | Four roles: `researcher`, `developer`, `debugger`, `reviewer` | No 18-role catalog, evidence-based team selection, independent verifier, conflict arbiter, or richer role output contracts | High |
| Long-running work | In-process scheduler and persisted orchestration runs | No durable goal journal, event-driven resume, progress checkpoints, or long-task supervisor beyond a single run | Medium |
| Benchmarks | Startup benchmark in `scripts/benchmark.py`; 109 unit tests | No comparable task-success benchmark harness, result schema, scoring, or stored runs; Phase E added a deterministic routing simulation with stdout JSON only | High |
| CI | No GitHub Actions workflow | Repeatable local checks exist, but no public CI gate | Medium |
| Visual identity | Existing ASCII artwork and colored terminal rendering | Frozen by user decision; only functional visual regressions should be fixed | Not a goal |

## Detailed findings

### 1. Planning and execution control

Current Aether:

- [aether/core/loop.py](../aether/core/loop.py) defines `TurnState` and `run_turn_loop()` around provider/tool iteration, cancellation, cost checks, and exit reasons.
- [aether/core/agent.py](../aether/core/agent.py) wires the loop to providers, memory, skills, tools, orchestration, and persistence.
- [aether/orchestration/orchestrator.py](../aether/orchestration/orchestrator.py) can build dependency plans for explicit roles and persists runs through [aether/orchestration/state.py](../aether/orchestration/state.py).
- The `todo` tool can store a simple task list for the model.

What is missing:

- One general planner that works for chat, coding, research, orchestration, and scheduled work.
- Complexity classification with distinct fast, plan/execute/verify, research/delegate/test/review, and high-risk approval paths.
- Explicit plan revision when evidence changes.
- Durable checkpoints that allow a stopped objective to resume without repeating completed or non-idempotent work.
- A final verifier that distinguishes requested, changed, tested, observed, and claimed results.

Design constraint: do not ask the model to expose hidden chain-of-thought. Use explicit, inspectable plans and evidence records. A confident answer is not proof of correctness.

### 2. Memory

Current Aether:

- [aether/memory/store.py](../aether/memory/store.py) manages bounded `MEMORY.md` and `USER.md` sections with add, list, search, delete, replace, import/export, and prompt context.
- SQLite message history supports FTS5 with a substring fallback through [aether/persistence/store.py](../aether/persistence/store.py).
- `session_search` exposes some history to the model.

What is missing:

- Working memory as a first-class, per-objective record rather than only the current message list and turn state.
- Episodic memory with session/task provenance and outcomes.
- Semantic memory with stable facts, confidence, source, and contradiction handling.
- Procedural memory for reusable, verified procedures.
- A user model separate from arbitrary notes.
- Consolidation, duplicate detection, correction, expiration, import/export for all layers, and user-controlled deletion.
- Retrieval by task need instead of always injecting a bounded flat block.

Hermes evidence: its current memory docs describe bounded `MEMORY.md`/`USER.md`, frozen session-start snapshots, and session boundaries that make recall useful after `/new`. That is a useful pattern, but Aether should go further by adding explicit layers, provenance, and evidence-based promotion rather than copying the file format or prompt text.

### 3. Learning loop and skills

Current Aether:

- [aether/skills/engine.py](../aether/skills/engine.py) discovers `SKILL.md` files, parses frontmatter, injects progressive context, and records view/use counts.
- Built-in skills are labelled and child agents cannot mutate skills.
- Basic injection-pattern validation exists.

What is missing:

- Experience records that capture objective, plan, tools, tests, user feedback, failures, and final outcome.
- Evidence rules: success must come from tests, observations, or explicit user confirmation, not from the model saying it succeeded.
- Discovery of repeated successful procedures and promotion into candidate skills.
- Skill quality scoring, review, version history, previous-version preservation, and rollback.
- A curator that can mark stale skills, archive, restore, and consolidate only with an audit trail.
- A searchable learning history with approval for changes to persistent instructions.

Hermes evidence: its current README and docs describe autonomous skill creation, skills that self-improve during use, review signals, a curator with deterministic staleness transitions and optional LLM consolidation, tar snapshots, a JSONL mutation ledger, and reversible rollback. The pattern is valuable; Aether should implement a smaller version with stricter local approval and provenance.

### 4. Provider and model routing

Current Aether:

- [aether/providers/catalog.py](../aether/providers/catalog.py) has 12 provider specs, rough cost annotations, and billability checks.
- [aether/providers/registry.py](../aether/providers/registry.py) handles activation, ordered fallback, cooldowns, and candidacy.
- Paid provider confirmation, shared budgets, reservations, and monotonic caps are enforced.

What was missing at the audit checkpoint:

- A task-facing capability registry for coding, reasoning, research, tool calling, structured output, context capacity, latency, cost, and reliability. Phase E added this as evidence-aware facts in `aether/routing/capabilities.py`.
- Routing based on task requirements and configured credentials, not only a fixed primary/fallback list. Phase E added a deterministic classifier and scored router over configured candidates.
- Explicit preservation of local and cost-free priority. Phase E supports `cost` and `capability` strategies plus `prefer_local`.
- Context-length management that chooses or compresses before an oversized request fails. Phase E fits context using capability windows and recovers from overflow with capped, still-matched tool-result restoration.

Routing remains advisory and does not validate model answers or prove task quality. Do not claim unlimited free inference. Free tiers and model IDs can change without notice.

### 5. Coding workflow

Current Aether:

- Tools cover directory listing, file reads/writes/edits, terminal, git, and Python execution.
- Permissions, approvals, strict roots, destructive-pattern checks, timeouts, redaction, and process-group cleanup exist.
- The `developer` and `debugger` roles can be used through orchestration.

What is missing:

- Repository indexing and symbol/dependency lookup before file selection.
- Progressive retrieval so the model does not dump entire repositories into context.
- Patch-based edits with clear before/after review.
- Test-first and regression-check workflows tied to a plan.
- Automatic diff review and change summaries.
- Checkpoints before risky edits and recovery after failed tests.

### 6. Research and evidence workflow

Current Aether:

- `web_fetch`, `web_search`, and `session_search` tools exist.
- Fetching blocks private targets, embedded credentials, and unsafe redirects; output is treated as untrusted data.

What is missing:

- A research plan with query decomposition and source selection.
- Multi-source comparison, citation extraction, and source-quality notes.
- Contradiction detection and explicit unknowns.
- Separation of verified fact, inference, and unverified claim.
- Confidence reporting that does not masquerade as certainty.
- Reuse of the verifier and memory layers after research completes.

### 7. Tool layer

Current Aether:

- [aether/tools/registry.py](../aether/tools/registry.py), [aether/tools/executor.py](../aether/tools/executor.py), and [aether/tools/permissions.py](../aether/tools/permissions.py) provide schemas, dispatch, timeouts, approvals, redaction, and cancellation-aware execution.

What is missing:

- Capability descriptions that let a planner choose tools without loading every schema into every prompt.
- Preflight checks for required arguments, external side effects, and idempotency.
- Verification of tool results before they become claimed facts.
- Error categorization and safe retry classification.
- Per-tool usage analytics that feed planning and learning.

Hermes evidence: its current tool-search docs describe deferring MCP/plugin schemas behind `tool_search`, `tool_describe`, and `tool_call` bridge tools while preserving approvals and guardrails. Aether should consider local schema deferral for a much smaller toolset, not copy the hosted connector gateway.

### 8. Orchestration and coordination

Current Aether:

- Four default roles, dependency plans, bounded parallel/sequential execution, shared spend budgets, cancellation propagation, retries, timeouts, persisted runs, and untrusted dependency boundaries.

What is missing:

- At least 18 meaningful specialist roles with distinct prompts, output contracts, tool policies, approvals, and budgets.
- Evidence-based team selection with inspectable rationale.
- Independent verifier, conflict arbiter, release manager, and other engineering-lifecycle roles.
- Strict inheritance of budgets, permissions, approvals, cancellation, timeouts, and recursion/resource limits.
- No unnecessary child spawning; delegation must be justified by independence or parallelism.

### 9. Long-running tasks

Current Aether:

- The scheduler can run due prompts in-process and records executions locally.
- Orchestrator runs can be persisted and resumed.
- Cancellation and child task recovery exist.

What is missing:

- A durable goal/objective record that outlives one chat turn or one orchestration run.
- Event-driven resume from checkpoints, tool results, approvals, or failures.
- Progress summaries derived from actual state.
- Never inventing progress and never silently exceeding cost or time limits.

### 10. Benchmarks and release evidence

Current Aether:

- 109 unit tests and local smoke/doctor checks exist.
- `scripts/benchmark.py` measures cold start time and memory only.
- `scripts/check.sh` runs tests, CLI smoke checks, secret scanning, startup benchmark, and Markdown link checks.

What is missing:

- A task-success benchmark with fixed tasks, fixtures, prompts, tools, budgets, and scoring.
- Comparisons under the same model, prompt, tools, workspace, and budget.
- Stored result artifacts with no fabricated numbers.
- CI that repeatedly verifies the suite.

## Hermes adoption decisions

Adopt or adapt:

- closed learning loop with evidence and rollback
- layered retrieval and session recall
- skill curation, quality review, and audit ledger
- tool schema deferral/search
- delegation output contracts and bounded correction turns
- eval tasks for delegation, session search, tool search, reasoning replay, and codebase navigability
- transparent provider routing and fallback controls

Do not copy:

- Nous Portal authentication, welcome tiers, or entitlement checks
- hosted free-tier claims or unlimited-model assumptions
- messaging gateway adapters and cloud execution backends as core dependencies
- React/Ink TUI, Electron desktop, or large Node dependency trees
- plugin marketplaces and remote skill installation as a default path
- any claim that model reasoning is hidden, perfect, or always correct

## Exit criteria for Phase A

Phase A is complete only when:

1. this audit, [INTELLIGENCE_ROADMAP.md](INTELLIGENCE_ROADMAP.md), [HERMES_COMPARISON.md](HERMES_COMPARISON.md), and the benchmark scaffolding are committed;
2. stale visual-first 0.2 documents are explicitly superseded or marked historical;
3. full local checks pass;
4. no runtime behavior, themes, font system, animations, or visual redesign are introduced in this phase.

See [INTELLIGENCE_ROADMAP.md](INTELLIGENCE_ROADMAP.md) for the implementation sequence and [HERMES_COMPARISON.md](HERMES_COMPARISON.md) for the source-evidenced comparison.
