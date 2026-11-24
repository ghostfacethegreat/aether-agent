# Hermes Comparison for Aether 0.2+

This document compares Aether with Hermes Agent for the intelligence-first `0.2+` program. It is source-evidenced and intentionally conservative: it records observed capabilities and research backing, not marketing claims or measured superiority.

## Scope and evidence

| Item | Value |
|---|---|
| Aether audit commit | `558bd58ec1f15ccf9cf76260d3ab7bfe675e76ce` |
| Hermes pinned baseline | `b98c388a880b1b6fd303c9c2821a3946651a0b4c` |
| Hermes current `main` checked for Phase A | `fe9a4b58ec137d3e00719c10e2385876fa03b97c` |
| Hermes source | <https://github.com/NousResearch/hermes-agent> |
| Hermes docs | <https://hermes-agent.nousresearch.com/docs/> |
| Method | static source and documentation review |
| Runtime benchmark | not run; no result data exists in this checkpoint |

Phase A evidence is summarized in [INTELLIGENCE_AUDIT.md](INTELLIGENCE_AUDIT.md). Fair comparison rules are in [benchmarks/README.md](../benchmarks/README.md). Implementation order is in [INTELLIGENCE_ROADMAP.md](INTELLIGENCE_ROADMAP.md).

## Headline assessment

Hermes currently has a much richer self-improvement and orchestration story. Its current README describes a closed learning loop, agent-created skills, skills that improve during use, persistent memory nudges, FTS5 session search, user modeling, cron automations, parallel subagents, RPC scripts, and multiple terminal backends. Its docs and source include tool search, skill curation with rollback, delegation output schemas, provider routing, and many eval directories.

Aether currently has a smaller but coherent local-first core: stdlib-only runtime, bounded turns, provider fallback, cost controls, permissions, tools, Markdown memory, `SKILL.md` skills, SQLite sessions, subagents, scheduler, and a persisted orchestrator with strict child rules. Aether's advantage is simplicity, startup cost, and local control; its weakness is that most intelligence work is still prompt-driven rather than an explicit planning, memory, learning, and verification system.

Neither project can be declared better on task quality from this document. That requires identical-model, identical-task benchmark runs.

## Capability comparison

| Area | Hermes evidence | Aether at `558bd58` | Assessment |
|---|---|---|---|
| Closed learning loop | Current README lines 19 and 26 describe autonomous skill creation, self-improvement during use, memory nudges, session search, and user modeling. Source includes `agent/review_signals.py`, `agent/curator.py`, `tools/skill_manager_tool.py`, `tools/skill_manager_scan.py`, and `tools/skill_usage.py`. | Skills are discovered and counted; no experience record, quality review, or evidence-based promotion. | Hermes leads. Aether Phase D should adopt the pattern locally with stricter evidence and rollback. |
| Persistent memory | Docs describe bounded `MEMORY.md` and `USER.md`, frozen session-start snapshots, and session boundaries for recall. Current README cites FTS5 session search and Honcho dialectic user modeling. | Two Markdown files and SQLite FTS message search. No layered memory, provenance, confidence, or consolidation. | Hermes leads on continuity. Aether Phase C should add layers without breaking existing files. |
| Skill quality and curation | `website/docs/user-guide/features/curator.md` documents active/stale/archived states, optional LLM consolidation, backups, audit ledger, pin/lock, restore, and rollback. | Basic skill validation, view/use counts, built-in labels, and child mutation denial. | Hermes leads. Aether Phase D should implement a small curator with rollback and evidence rules. |
| Progressive context | Tool-search docs describe deferring MCP/plugin schemas behind `tool_search`, `tool_describe`, and `tool_call` while preserving guardrails. Skills use progressive disclosure. | Skills use progressive disclosure; all enabled tool schemas are presented directly to the model. | Hermes leads on schema scale. Aether Phase H should consider local schema deferral for larger toolsets. |
| Coding workflow | Docs include LSP, code execution, browser, codebase navigability eval, and broad terminal capabilities. | File, terminal, git, Python tools and developer/debugger roles; no repository index, patch workflow, or TDD loop. | Hermes leads. Aether Phase F should build a small local index and patch/test workflow. |
| Research | Current README calls out research-ready batch trajectory generation; docs include web search, browser, document extraction, X search, and context files. | Web fetch/search and session search tools; no source comparison, citations, contradictions, or confidence pipeline. | Hermes leads in tooling. Aether Phase G should focus on evidence quality, not feature count. |
| Delegation and parallel agents | Current README describes isolated parallel subagents and RPC scripts. Delegation docs describe output schemas, bounded correction turns, background children, and approval routing. | Four roles, dependency plans, shared budget, cancellation, timeouts, persistence, and untrusted result boundaries. No output contracts or automatic team selection. | Hermes leads. Aether Phase I should preserve its stronger child restrictions while adding contracts and verifier roles. |
| Scheduled automations | Docs and README describe built-in cron with delivery to platforms. | In-process scheduler with local execution ledger; no daemon or delivery targets. | Hermes leads. Aether should improve durability before adding delivery surfaces. |
| Provider routing | Docs include provider routing and fallback providers; current README advertises many providers with no code changes. | 12 provider specs, ordered fallback, cooldowns, rough cost, paid confirmation, budgets, and cancellations. | Aether is competitive on controls, weaker on capability-aware routing. Phase E should add a capability registry. |
| Cost and permissions | Hermes has extensive provider and credential systems. | Explicit paid confirmation, shared locked budgets, reservations, monotonic caps, strict roots, approvals, redaction, and child restrictions. | Aether has strong local cost/permission guardrails. Keep them while adding routing. |
| Terminal interface | Hermes has a real TUI with a larger Node/React/Ink stack and many plugins. | Python CLI with ASCII artwork and colored rendering. | Out of scope for parity. Aether's visual identity is frozen by user decision. |
| Runtime footprint | Hermes has extensive optional integrations and plugin infrastructure. | Python stdlib only at runtime; no required cloud service; cold start around 0.08 s and peak child RSS around 29-31 MiB in local benchmark runs. | Aether advantage for lightweight local use. Do not regress it. |
| Evals | Current checkout contains eval directories such as `evals/tool_search`, `evals/delegation_grouping`, `evals/delegation_group_schema`, `evals/session_search_schema`, `evals/reasoning_replay`, `evals/compaction`, `evals/codebase_navigability`, and `evals/postmortem`. | 109 local unit tests and startup benchmark; no task-success harness. | Hermes leads. Aether Phase K should create reproducible task artifacts and stored results. |
| Licensing and independence | MIT, Nous Research; upstream notices apply. | MIT, independent implementation with notices in `docs/UPSTREAM_LICENSE.md`. | No issue; do not copy upstream code. |

## What Aether should learn from Hermes

1. A closed loop is more than a prompt: experience, review, promotion, versioning, and rollback must be connected.
2. Memory becomes more useful when old sessions can be searched at natural boundaries and recalled with provenance.
3. Skills need maintenance; uncurated skills accumulate duplicates and stale instructions.
4. Delegation improves when child outputs have schemas and bounded correction turns.
5. Tool schemas can be deferred when the catalog grows.
6. Evals should be part of the repository, not an afterthought.
7. Provider flexibility is valuable, but cost and credential control must remain explicit.

## What Aether should not copy

- Nous Portal, welcome tiers, entitlements, or hosted free-tier assumptions
- cloud execution backends, gateway adapters, and messaging delivery as core requirements
- plugin marketplaces and remote skill installation as default behavior
- large Node/React/Ink desktop and TUI dependencies
- claims of unlimited free models or restricted-model bypasses
- any claim that model reasoning is private, perfect, or always correct
- visual themes, fonts, or animations; these are explicitly frozen in Aether 0.2+

## Comparison method for future results

When a runtime comparison is eventually run, both systems must receive the same model or equally declared model setup, the same task text, input files, tool availability, workspace, time limit, spend limit, and scoring rubric. Record provider, model ID, settings, tool versions, temperature when available, prompt text, start/end time, token usage, cost, and complete evidence artifacts.

Do not compare Aether with a paid Hermes route against a free Aether route and call the result a model-neutral comparison. Do not compare local Aether with hosted Hermes and ignore latency or provider differences. Do not publish only favorable tasks.

Until such runs exist and are stored under `benchmarks/results/`, this document must not be summarized as "Aether beats Hermes" or "Hermes is better at everything." The accurate statement is narrower: Hermes has more implemented self-improvement and orchestration machinery today, while Aether has a smaller, stricter local core and an explicit plan to close the measured gaps.
