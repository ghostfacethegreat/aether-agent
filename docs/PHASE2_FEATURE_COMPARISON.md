# Phase 2 Feature Comparison: Aether vs Hermes Agent

## Scope and evidence

This is the Phase 2 source-level comparison requested after Aether `0.1.0`. It is not a parity claim. It records what exists, what is absent, and what is implemented with different tradeoffs.

- Upstream baseline: <https://github.com/NousResearch/hermes-agent>
- Audited upstream commit: `b98c388a880b1b6fd303c9c2821a3946651a0b4c`
- Audited Aether commit: `bdbe2462dda3c4646086385d600b4e2ab23f4957`
- Audit date: 2026-11-23
- Method: static source review of both checkouts, plus prior local Aether test/install records. No upstream code was copied into Aether.
- Hermes paths are relative to the upstream checkout. Aether paths are relative to `aether-agent`. Line ranges are inclusive where available.
- Classification values: `Fully implemented`, `Partially implemented`, `Not implemented`, `Implemented differently`.
- Negative findings cite the closest implementation, docs, or tracked-tree boundary. They do not claim a file was exhaustively searched beyond the cited audit.

Prior release checks are recorded in [RELEASE_CHECKS.md](RELEASE_CHECKS.md). Prioritization and milestone sequencing are in [PHASE2_ROADMAP.md](PHASE2_ROADMAP.md).

## 1. Agent execution and planning

| Capability | Hermes status and evidence | Aether status | Aether evidence and limitation |
|---|---|---|---|
| Bounded iterative turn loop with tool rounds | `Fully implemented` — `agent/conversation_loop.py:1-6,1434-1471,1529-1564,1782-1805`; `agent/turn_finalizer.py:649-669` | `Fully implemented` | `aether/core/loop.py:86-130`; `aether/core/agent.py:160-215`; `tests/test_core.py:21-39`. Aether loops up to `max_iterations`, fits context, calls providers, executes tools, and persists final state. |
| System prompt assembly | `Fully implemented` — `agent/prompt_builder.py:194-222,261,1305-1324`; `agent/system_prompt.py:288-319` | `Fully implemented` | `aether/core/context.py:12-28`; `aether/core/agent.py:165-170`. Personality, custom prompt, date, plan, memory, and skills are included. |
| Plan mode / visible todos | `Fully implemented` — `agent/plan_prompt.py:1-6,11-26,60-71`; `tools/todo_tool.py:1-4,9-22` | `Partially implemented` | `aether/core/agent.py:72,127-130`; `aether/tools/builtins.py:368-377`; `aether/cli/app.py:320-324`; `tests/test_core.py:41-47`. Plan text is visible and injected, but there is no autonomous plan graph or durable standalone plan state. |
| Persistent goals / Ralph loop | `Fully implemented` — `hermes_cli/goals.py:1-7,32-51` | `Not implemented` | No goals module exists in the tracked tree; the closest bounded execution is `aether/core/loop.py:86-130` and the task ledger in `docs/ARCHITECTURE.md:139-141`. |
| Context compression and handoff | `Fully implemented` — `agent/context_compressor.py:1-2,204-239,470-528,560-602` | `Implemented differently` | `aether/core/context.py:45-78`; `tests/test_core.py:9-19`. Aether uses heuristic token estimates and middle-message summarization, not an auxiliary-model compressor, checkpoints, or refusal/quota-aware recovery. |
| Delegation and subagents | `Fully implemented` — `tools/delegate_tool.py:613-649`; `agent/subagent_lifecycle.py:1-2,24-45`; `agent/delegation_backends.py:1-13` | `Partially implemented` | `aether/tasks/subagents.py:46-53`; `aether/core/agent.py:108-125`; `tests/test_tasks.py:37-45`. Synchronous parallel delegation works with a reduced toolset; durable, steerable, resumable children are incomplete. |
| Verification-before-finish nudge | `Partially implemented` — `agent/verification_stop.py:1-3,62-70` | `Implemented differently` | `scripts/check.sh:1-46`; `aether/skills/builtin/code-review/SKILL.md:1-14`. Aether has human-run checks and prompt guidance but no runtime verification gate. |
| Session persistence and trajectory recording | `Fully implemented` — `agent/session_persistence.py:490-512` | `Partially implemented` | `aether/core/agent.py:193-215`; `aether/persistence/store.py:130-147,252-267`; `tests/test_core.py:39`. Messages are persisted, but tool-call structure is lost on reload and no trajectory export exists. |

## 2. Model providers and inference

| Capability | Hermes status and evidence | Aether status | Aether evidence and limitation |
|---|---|---|---|
| Provider registry and profiles | `Fully implemented` — `providers/base.py:141-171`; `providers/__init__.py:121-169,367-408` | `Implemented differently` | `aether/providers/catalog.py:20-181`; `aether/providers/registry.py:19-46`. Aether has a static 12-profile catalog plus generic OpenAI-compatible fallback, not a bundled/user plugin profile system. |
| Chat-completions transport | `Fully implemented` — `agent/transports/base.py:1-4,12-41`; `agent/transports/chat_completions.py:1-5` | `Fully implemented` | `aether/providers/openai_compatible.py:82-171,173-191,254-259`. Handles Bearer auth, tools, usage, `/models`, retries, and common HTTP errors. No live HTTP test is recorded. |
| Streaming / SSE normalization | `Fully implemented` — `agent/chat_completion_helpers.py:169-234,237-259` | `Fully implemented` | `aether/providers/openai_compatible.py:193-252`; `tests/test_providers.py:28-38,46-96`. Synthetic SSE parsing is tested; live provider streams are not. |
| Auth types and credential pools | `Fully implemented` — `providers/base.py:161-179`; `agent/credential_pool.py:1-9`; `agent/credential_pool_selection.py:30-75` | `Partially implemented` | `aether/config.py:64-82`; `aether/utils.py:28-51`; `docs/PROVIDERS.md:1-42`. Aether supports explicit env vars and `.env`; it has no OAuth, AWS SDK, external-process auth, or key pool. |
| Anthropic Messages transport | `Fully implemented` — `agent/transports/anthropic.py:1-8` | `Partially implemented` | `aether/providers/anthropic.py:24-215`; `aether/core/loop.py:35-43`. Native conversion and SSE parsing exist, but replay reads top-level call fields while the loop emits nested `function` fields, so multi-turn tool replay is likely broken. |
| Fallback, cooldown, and restore | `Fully implemented` — `agent/fallback_cooldown.py:1-2,11-28,61-80` | `Fully implemented` | `aether/providers/registry.py:70-90`; `aether/core/loop.py:54-73`; `tests/test_providers.py:98-107`. Active provider first, then configured fallbacks, with time-based cooldowns. |
| Model metadata, pricing, context limits | `Fully implemented` — `agent/model_metadata.py:1-5,902,1024,1126-1188` | `Partially implemented` | `aether/providers/catalog.py:20-180`; `aether/cli/app.py:398-401,458-465`; `aether/core/context.py:84-86`. Cost annotations and token counts exist; dollar estimates and account balance do not. |
| Reasoning effort and prompt caching | `Fully implemented` — `agent/reasoning_effort.py:1-10,22-37`; `agent/prompt_caching.py:1-6,25-34,37-49` | `Partially implemented` | `aether/config.py:14`; `aether/providers/openai_compatible.py:82-171`; `aether/core/context.py:12-28`. Some reasoning parameters exist; `top_p` is configured but not sent, and there are no provider cache breakpoints. |
| Auxiliary inference router | `Fully implemented` — `agent/auxiliary_client.py:1-8,2239-2311` | `Not implemented` | No auxiliary provider client exists in the tracked tree; Aether's context summarization is inline heuristic behavior in `aether/core/context.py:45-78`. |
| Local inference | `Fully implemented` — `README.md:37-61`; `agent/model_metadata.py:1126-1188` | `Implemented differently` | `aether/providers/catalog.py:23-74`; `aether/providers/registry.py:19-46`; `docs/PROVIDERS.md:26-42`. Aether targets external OpenAI-compatible Ollama/LM Studio/llama.cpp servers; it has no bundled runtime or model downloader. No live local-model run is recorded for Phase 2. |
| External service dependency model | `Implemented differently` — `README.md:19-21,37-61,125-140` | `Implemented differently` | `pyproject.toml:1-37`; `README.md:5,13-29`. Both allow local-only use; Hermes exposes more hosted optional surfaces, while Aether keeps a stdlib-only core and no mandatory paid account. |

## 3. Tool calling and execution

| Capability | Hermes status and evidence | Aether status | Aether evidence and limitation |
|---|---|---|---|
| Tool registry and schema generation | `Fully implemented` — `tools/registry.py:596-612,1016-1049`; `model_tools.py:225-236` | `Partially implemented` | `aether/tools/registry.py:8-64`; `aether/tools/builtins.py:403-599`; `tests/test_tools.py:24-26`. Aether validates names and required keys, but not full JSON Schema types or constrained values. |
| Toolsets and scoped surfaces | `Fully implemented` — `toolsets.py:1-36,335-458` | `Implemented differently` | `aether/tools/permissions.py:46-118`; `aether/core/agent.py:17,108-125`. Aether uses allow/deny lists, modes, and a narrow child tool list rather than upstream's many composable toolsets. |
| Concurrent dispatch and ordered results | `Fully implemented` — `agent/tool_executor.py:1608-1639`; `tools/tool_result_storage.py:1-6` | `Fully implemented` | `aether/tools/executor.py:32-38,84-103`; `tests/test_tools.py:67-73`. Safe tools run in a 4-worker pool; results are reordered by call index. |
| Approval and loop guardrails | `Fully implemented` — `tools/approval.py:1-11`; `agent/tool_guardrails.py:1-5,21-42` | `Fully implemented` | `aether/tools/executor.py:43-64`; `aether/tools/permissions.py:127-146`; `tests/test_tools.py:43-65`. Missing approvers fail closed; denial and destructive strict-denial are tested. |
| Terminal, file, and code execution | `Fully implemented` — `tools/terminal_tool.py:1-11`; `tools/file_tools.py:1-6`; `tools/code_execution_tool.py:1-11,39-50,948-953` | `Implemented differently` | `aether/tools/builtins.py:159-236,447-485`. Short-lived local subprocesses are used; there is no sandbox backend, persistent Python session, or remote backend. |
| File-write safety | `Fully implemented` — `tools/file_tools_write_guards.py:1-10,32-39` | `Partially implemented` | `aether/tools/permissions.py:26,55-92`; `aether/tools/builtins.py:97-157`. Sensitive markers and roots are checked, but git `paths`, terminal `cwd`, redirects, and binary/opaque content guards are incomplete. |
| MCP integration | `Fully implemented` — `tools/mcp_tool.py:1-9`; `tools/hosted_tool_policy.py:62` | `Not implemented` | No MCP module appears in the tracked tree; the closest extension point is `aether/tools/registry.py:8-64`. |
| Output caps and redaction | `Fully implemented` — `tools/tool_result_storage.py:1-6`; `tools/approval.py` guard paths | `Partially implemented` | `aether/tools/registry.py:62-64`; `aether/tools/executor.py:12-29`; `aether/core/context.py:51-55`. Tool logs are redacted, but model-facing tool results are only truncated, not redacted. |
| Tool-level timeout enforcement | `Fully implemented` — `agent/tool_guardrails.py:1-5,21-42` | `Partially implemented` | `aether/tools/registry.py:16`; `aether/tools/executor.py:32-103`; `aether/tools/builtins.py:163,203,220,293`. `Tool.timeout` exists but the executor does not enforce it; handlers use mixed fixed timeouts. |
| Hosted / provider-specific tool scoping | `Fully implemented` — `tools/hosted_tool_policy.py:1-23,29-40,42-66,83-96` | `Not implemented` | No hosted scope policy exists; Aether's closest policy is local permission mode in `aether/tools/permissions.py:46-118`. |

## 4. Persistent memory

| Capability | Hermes status and evidence | Aether status | Aether evidence and limitation |
|---|---|---|---|
| `MEMORY.md` / `USER.md` store and CRUD | `Fully implemented` — `tools/memory_tool.py:1-5,38-56,373-390`; `tools/memory_tool_store.py:1-3,21-32` | `Fully implemented` | `aether/memory/store.py:10-48,59-98`; `tests/test_memory_skills.py:11-24`. Atomic Markdown writes and add/list/search/context/delete are tested. |
| Frozen long-term profile snapshot | `Fully implemented` — `tools/memory_tool.py:38-56` | `Implemented differently` | `aether/core/context.py:12-28`; `aether/memory/store.py:122-138`. Aether rebuilds prompts from current files each turn rather than maintaining a frozen session snapshot. |
| Past-session search | `Fully implemented` — `tools/session_search_tool.py:1-9,28-39`; `persistence/conversation/search.py:1-18` | `Fully implemented` | `aether/persistence/store.py:7-54,130-167`; `aether/tools/builtins.py:337-365`; `tests/test_persistence.py:13-27`. FTS5 with substring fallback exists; there is no upstream-style DISCOVER/BROWSE protocol. |
| FTS5 availability handling | `Fully implemented` — `persistence/sqlite/_schema.py:284-293,1128-1137,1532-1541` | `Implemented differently` | `aether/persistence/store.py:7-54`. Aether creates FTS structures but does not implement upstream's runtime probes, trigger drops, or rebuild workflows. |
| LLM summarization for recall | `Implemented differently` — `tools/session_search_tool.py:8,827`; `agent/context_compressor.py:1-2` | `Not implemented` | `aether/core/context.py:45-78` summarizes only in-turn removals; there is no query-time or cross-session LLM recall. |
| Pluggable external memory providers | `Fully implemented` — `agent/memory_provider.py:1-6,21-37`; `agent/memory_manager.py:1-5,37-58` | `Not implemented` | No memory provider plugin interface exists in the tracked tree; Aether's memory storage is `aether/memory/store.py:10-48`. |
| Memory context fencing and redaction | `Fully implemented` — `agent/memory_context.py:1-6,17-41`; `agent/memory_manager.py:346-373` | `Partially implemented` | `aether/core/context.py:24-27`; `aether/skills/engine.py:11,70-71,113-115`. Aether relies on prompt guidance and a small blocklist; there is no general sanitizer or provenance fence. |
| Import/export and direct editing | `Fully implemented` — `hermes_cli/subcommands/memory.py`; `tools/memory_tool.py` | `Fully implemented` | `aether/memory/store.py:100-120`; `aether/cli/app.py:105-111,571-597`; `tests/test_memory_skills.py:19-22`. JSON round trip is tested; CLI commands are not unit-tested. |

## 5. Skills and self-improvement

| Capability | Hermes status and evidence | Aether status | Aether evidence and limitation |
|---|---|---|---|
| Skill format, discovery, progressive disclosure | `Fully implemented` — `tools/skills_tool.py:1-5,33-39`; `agent/skill_utils.py:28-36,413-430` | `Fully implemented` | `aether/skills/engine.py:9-10,26-40,43-73,96-103`; `tests/test_memory_skills.py:26-29,36,43-46`. |
| Skill list/view | `Fully implemented` — `tools/skills_tool.py:305,634,739-807` | `Fully implemented` | `aether/skills/engine.py:89-103`; `aether/tools/builtins.py:337-355`; `aether/cli/app.py:113-128,600-616`. |
| Skill create/edit/patch/delete | `Fully implemented` — `tools/skill_manager_tool.py:2-8,396-413,580-601,845-859,953` | `Fully implemented` | `aether/skills/engine.py:89-148`; `aether/tools/builtins.py:337-355`; `tests/test_memory_skills.py:30-35`. Built-ins are read-only; user skills can be changed. |
| Usage telemetry and provenance | `Fully implemented` — `tools/skill_usage.py:1-6,35-40`; `tools/skill_ledger.py:1-9,39` | `Partially implemented` | `aether/skills/engine.py:49,77-87,93,147-161`; `aether/cli/app.py:604-606`. `.usage.json` counts views/edits, but there is no JSONL audit log, content-addressed backup, or rollback. |
| Prompt guidance to create/improve skills | `Fully implemented` — `agent/prompt_builder.py:194-222,261,1305-1324`; `agent/system_prompt.py:288-319` | `Implemented differently` | `aether/core/context.py:12-28`; `aether/skills/builtin/web-research/SKILL.md:1-14`. Skill index is injected, but there is no strong prompt policy requiring skill persistence. |
| Background memory/skill review | `Fully implemented` — `agent/background_review.py:1-6,532-657,1286-1349,1460-1494`; `agent/review_signals.py:1-10,33-50` | `Not implemented` | No background review module exists in the tracked tree; the nearest human-triggered checks are `scripts/check.sh:1-46`. |
| Curator / consolidation lifecycle | `Fully implemented` — `agent/curator.py:1-7,42-46,117-159,293-315,898-925` | `Not implemented` | No curator module exists; Aether has usage counters only at `aether/skills/engine.py:49,147-161`. |
| Skills Hub / external skill sources | `Fully implemented` — `tools/skills_hub.py:1-12,28-45`; `tools/skills_hub_search.py:99-129`; `tools/skills_hub_install.py:181-215,246,305` | `Not implemented` | `docs/FEATURE_MATRIX.md:51` states no cloud hub; no hub module appears in the tracked tree. |
| Self-improvement safety scanning | `Fully implemented` — `tools/skills_guard.py`; `tools/skill_manager_tool.py` guards | `Partially implemented` | `aether/skills/engine.py:11,70-71,113-115`; `SECURITY.md:20`; `tests/test_memory_skills.py:38-41`. Aether uses a short hardcoded substring blocklist. |

## 6. Subagents and parallel execution

| Capability | Hermes status and evidence | Aether status | Aether evidence and limitation |
|---|---|---|---|
| Dedicated delegation tool | `Fully implemented` — `tools/delegate_tool.py:613-637,739,806` | `Fully implemented` | `aether/tools/builtins.py:358-365,550-571`; `aether/tasks/subagents.py:46-53`; `tests/test_tasks.py:37-45`. Synchronous single/batch delegation works with deterministic fakes. |
| Child construction and tool filtering | `Fully implemented` — `tools/delegate_tool.py:209,506`; `tools/delegate_tool_toolsets.py:14-21,38-77` | `Implemented differently` | `aether/core/agent.py:17,108-125`; `aether/tools/permissions.py:94-118`; `aether/tools/builtins.py:550-571`. Child tools are narrower but include write-capable `skill`; network tools fail closed in strict mode. |
| Parallel batch execution | `Fully implemented` — `tools/delegate_tool_dispatch.py:140-155,177` | `Fully implemented` | `aether/tasks/subagents.py:46-53`; `aether/tools/executor.py:32-38`. Aether uses a local thread pool; results are sorted back by goal. |
| Live list / steer / stop | `Fully implemented` — `tools/delegate_tool_registry.py:1,21-22,40-59,102-113,133-156` | `Not implemented` | `aether/tasks/subagents.py:16-67` exposes submit/wait/resume only; no steer/stop registry exists. |
| Durable/resumable children | `Fully implemented` — `tools/delegate_tool_resumable.py:1-12,28-44,58-74,130-157,194-233`; `tools/delegate_tool_auto_resume.py:1-25,40-60,79-107,252-258` | `Partially implemented` | `aether/tasks/subagents.py:55-67`; `aether/cli/app.py:134-136,619-626`. `resume()` exists but CLI refuses it and child history is not restored. |
| Structured child output | `Fully implemented` — `tools/delegation_output_schema.py:1-7,19-39`; `tools/delegate_tool_child_run.py:554-572` | `Not implemented` | No output-schema validation appears in `aether/tasks/subagents.py:16-67`; results are plain strings. |
| Result summarization, redaction, spill | `Fully implemented` — `tools/delegate_tool_results.py:1,54-78,164-239` | `Partially implemented` | `aether/tools/registry.py:62-64`; `aether/tools/executor.py:12-29`. Generic output truncation exists; there is no child-summary budget, secret-aware redaction, or paging spill. |
| Git worktree isolation | `Fully implemented` — `tools/delegate_tool_config.py:162-166`; `tools/delegate_tool_child_run.py:461-479` | `Not implemented` | No worktree isolation exists in `aether/tasks/subagents.py:16-67`; Aether children share the current working directory. |
| Task ledger integration | `Fully implemented` — durable records in `tools/delegate_tool_resumable.py` and persistence layers | `Partially implemented` | `aether/tasks/subagents.py:16-23,31-44`; `aether/persistence/store.py:212-245`; `tests/test_persistence.py:29-32`. Store CRUD is tested separately, but subagent-to-ledger writes are not tested end to end. |
| Standalone `send_message` tool | `Not implemented` — `tools/delegate_tool.py:746`; `tools/delegate_tool_toolsets.py:19` | `Not implemented` | No `send_message` built-in appears in `aether/tools/builtins.py:403-599`; child toolsets exclude side-effect messaging by design. |

## 7. Scheduling and automation

| Capability | Hermes status and evidence | Aether status | Aether evidence and limitation |
|---|---|---|---|
| Cron management surface | `Fully implemented` — `tools/cronjob_tools.py:1131-1199,1019-1036` | `Partially implemented` | `aether/tasks/scheduler.py:32-74`; `aether/cli/app.py:138-151,629-642`; `tests/test_tasks.py:24-35`. Add/list/remove jobs works; update/pause/resume/cancel/run are not present. |
| Schedule forms | `Fully implemented` — `tools/cronjob_tools.py:1157-1168` | `Implemented differently` | `aether/tasks/scheduler.py:11-29`; `tests/test_tasks.py:16-22`. Aether supports `every N s/m/h/d` and ISO one-shots, not cron syntax, named timezones, calendars, or catch-up policy. |
| Fresh autonomous runs | `Fully implemented` — `tools/cronjob_tools.py:1131-1135,1149-1155` | `Partially implemented` | `aether/tasks/scheduler.py:76-108` invokes an injected runner, but CLI manual ticks create no runner and interactive chat does not start the background scheduler. |
| Prompt, skills, scripts, monitors | `Fully implemented` — `tools/cronjob_tools.py:673-691,1116-1128,1178-1198`; `cron/scheduler_script.py:446-475` | `Not implemented` | `aether/tasks/scheduler.py:11-129` stores only a prompt string; no profile scripts, monitors, or skill-bound jobs exist. |
| Delivery targets and surfaces | `Fully implemented` — `tools/cronjob_tools.py:1170-1177`; `cron/scheduler_delivery.py:1-47,50-74` | `Not implemented` | `aether/tasks/scheduler.py:92-108` stores results in `jobs.json`; no delivery queue or messaging targets exist. |
| At-most-once firing and audit DB | `Fully implemented` — `cron/scheduler_tick.py:33-72`; `cron/scheduler.py:1645-1669` | `Not implemented` | `aether/tasks/scheduler.py:92-108`; `docs/ARCHITECTURE.md:73,102`. Upstream `executions.db` and delivery queue equivalents were deliberately not adopted. |
| Manual runs | `Fully implemented` — `cron/extra_fire.py:1-72`; `tools/cronjob_tools.py:1133` | `Implemented differently` | `aether/cli/app.py:629-642`; `aether/tasks/scheduler.py:92-108`. Manual ticks mark and reschedule jobs but do not execute prompts, while output says jobs ran. |
| Background scheduler | `Fully implemented` — `cron/scheduler.py:577-582,4144-4157,4294-4317` | `Partially implemented` | `aether/tasks/scheduler.py:110-129`; `aether/cli/app.py:678-695`; `docs/CONFIGURATION.md:81`. Thread code exists, but interactive chat does not start it and `aether run` stops it immediately. |

## 8. Web research and browser capabilities

| Capability | Hermes status and evidence | Aether status | Aether evidence and limitation |
|---|---|---|---|
| Web search and extract tools | `Fully implemented` — `tools/web_tools.py:302-333` | `Fully implemented` | `aether/tools/builtins.py:54-94,239-278,486-501`. Fetch/search and HTML-to-text exist; they are best-effort and untested against live sites. |
| Pluggable web backend registry | `Fully implemented` — `agent/web_search_registry.py:1-16`; `tools/web_tools.py:1-10` | `Partially implemented` | `aether/tools/builtins.py:248-270`; `aether/config.py:44-48`. DuckDuckGo, Brave, and Serper are hardcoded choices, not a plugin registry. |
| Search provider variety | `Fully implemented` — `plugins/web/tavily/provider.py:3,89-123`; `plugins/web/brave_free/provider.py:4-47`; `plugins/web/ddgs/provider.py:184`; `plugins/web/firecrawl/provider.py:4,80-97,339,388`; `plugins/web/searxng/provider.py:17`; `plugins/web/exa/provider.py:3,37-76` and others | `Partially implemented` | `aether/tools/builtins.py:248-270`; `docs/PROVIDERS.md:1-42`. Aether covers one keyless path and two optional keyed paths; all external quota limitations remain. |
| Keyless fallback | `Fully implemented` — `plugins/web/keyless_mcp.py:1-5,24-32` | `Implemented differently` | `aether/tools/builtins.py:248-278`. Aether parses DuckDuckGo HTML directly; no MCP fallback chain, no explicit disable switch. |
| Search caching and extract spill | `Fully implemented` — `tools/web_result_cache.py:1-8,24-47`; `tools/web_tools_truncate.py:1-38` | `Partially implemented` | `aether/tools/registry.py:62-64`. Generic result truncation exists; no TTL cache, single-flight, head/tail paging, or safety-before-cache-hit behavior. |
| Browser automation surface | `Implemented differently` — `tools/browser_use_cli.py:1-7,1000-1020` | `Implemented differently` | `aether/tools/builtins.py:281-301,502-512`; `aether/config.py:47`. Aether executes an operator-supplied shell template; no browser runtime or DOM API. |
| Browser sessions, CDP, cloud, vault | `Fully implemented` — `tools/browser_session.py:1-18`; `tools/browser_cdp_tool.py:368-378`; `tools/browser_vault_tool.py:430-458`; `plugins/browser/browserbase/provider.py:1-4,26,34-45,67-68` | `Not implemented` | `docs/FEATURE_MATRIX.md:39`; `docs/ARCHITECTURE.md:99-104`. No browser module appears in the tracked tree. |
| URL safety | `Fully implemented` — `tools/browser_url_policy.py:1-7,33-42` | `Partially implemented` | `aether/tools/builtins.py:54-67`; `SECURITY.md:21,26`. http/https and embedded credentials are checked; private-network/SSRF and redirect restrictions are absent. |

## 9. Messaging integrations

| Capability | Hermes status and evidence | Aether status | Aether evidence and limitation |
|---|---|---|---|
| Gateway platform model and plugin registry | `Fully implemented` — `gateway/config.py:235-259,320,325-336,420`; `gateway/platform_registry.py:187-209` | `Not implemented` | `docs/ARCHITECTURE.md:102`; `docs/FEATURE_MATRIX.md:108`. No gateway package or platform registry exists in the tracked tree. |
| Bundled chat adapters | `Fully implemented` — `plugins/platforms/telegram/adapter.py:6628`; `plugins/platforms/discord/adapter.py:7066`; `plugins/platforms/slack/adapter.py:7055`; `plugins/platforms/whatsapp/adapter.py:1726`; `plugins/platforms/matrix/adapter.py:3134` | `Not implemented` | `aether/config.py:44-48` only configures web/fetch/browser integrations; no adapter modules exist. |
| Long-tail and catalog platforms | `Fully implemented` / `Implemented differently` — `plugins/platforms/sms/adapter.py:346`; `plugins/platforms/email/adapter.py:1032`; `website/docs/user-guide/messaging/homeassistant.md:10-32`; `plugin-catalog/yuanbao.yaml:1-11` | `Not implemented` | `docs/FEATURE_MATRIX.md:108` lists messaging gateways as planned only. |
| Profile credentials and activation | `Fully implemented` — `website/docs/user-guide/messaging/index.md:17-26`; `gateway/config.py:420` | `Partially implemented` | `aether/config.py:64-82`; `aether/utils.py:28-51`. Generic `.env` loading and redaction exist; no adapter-specific scopes or enable flags exist. |
| Outbound delivery and reliability | `Fully implemented` — `gateway/platforms/base_delivery_ledger.py:3,31,39-40,48,83-108`; `gateway/outbound/send.py:512,671` | `Not implemented` | `aether/tasks/scheduler.py:92-108`; `docs/ARCHITECTURE.md:73`. No delivery ledger, redelivery, or media adaptation exists. |
| Standalone `send_message` tool | `Not implemented` — `tools/delegate_tool.py:746`; `tools/delegate_tool_toolsets.py:19` | `Not implemented` | No `send_message` built-in appears in `aether/tools/builtins.py:403-599`. |

## 10. Voice support

| Capability | Hermes status and evidence | Aether status | Aether evidence and limitation |
|---|---|---|---|
| TTS tool and providers | `Fully implemented` — `tools/tts_tool.py:123-139,464-473,633-657`; `tools/tts_tool_providers.py:1-8,28-42` | `Not implemented` | `aether/cli/render.py:1-136`; `aether/cli/app.py:215-260`. Output is ANSI/text only; no audio tools or voice provider settings exist. |
| STT providers and preprocessing | `Fully implemented` — `tools/transcription_tools.py:1-9,236-270,433-460`; `tools/transcription_common.py:15-68` | `Not implemented` | `aether/cli/app.py:32-164,422-435`; `aether/config.py:8-51`. CLI accepts text only; no audio flags, modules, or dependencies. |
| Live sessions, wake word, barge-in | `Fully implemented` — `tools/voice_mode.py:526-568,664-684,1335-1397`; `tools/wake_word.py:1-9,36-66,75-87`; `tui_gateway/methods_voice.py:238-326,574-635` | `Not implemented` | No voice module appears in the tracked tree; `docs/FEATURE_MATRIX.md` does not list voice support. |
| Streaming TTS and auto-TTS | `Fully implemented` — `gateway/streaming_tts_consumer.py:34-41,131-142,168-206`; `gateway/platforms/base.py:4377-4389` | `Not implemented` | `aether/cli/app.py:215-260` streams text deltas only. |
| Discord voice channels | `Fully implemented` — `gateway/run_voice.py:200-229`; `plugins/platforms/discord/adapter.py:658-663,3542-3569,3768-3794` | `Not implemented` | No gateway or Discord adapter exists; see `docs/ARCHITECTURE.md:102`. |
| Managed full-duplex voice | `Fully implemented` — `tools/voice_live.py:1-20`; `website/docs/user-guide/features/voice-mode.md:27-29` | `Not implemented` | `aether/providers/catalog.py:20-180` includes text chat APIs only. This upstream path is paid and should remain explicitly optional in Aether. |

## 11. CLI and user experience

| Capability | Hermes status and evidence | Aether status | Aether evidence and limitation |
|---|---|---|---|
| CLI parser, dispatch, one-shot runs | `Fully implemented` — `hermes_cli/main.py:3226-3342`; `hermes_cli/_parser.py:1-80,260-320` | `Fully implemented` | `aether/cli/app.py:32-164,645-706`; `aether/__main__.py:1-4`; `tests/test_cli.py:19-56`. |
| Interactive REPL and slash commands | `Fully implemented` — `cli.py:883`; `hermes_cli/commands.py:44-150` | `Fully implemented` | `aether/cli/app.py:25-29,272-435`. Command coverage is broad; interactive input and slash dispatch are not unit-tested. |
| Resume/continue/worktree flags | `Fully implemented` — `hermes_cli/_parser.py:280-297` | `Partially implemented` | `aether/cli/app.py:364-373`; `aether/core/agent.py:74-88`. `/resume` and `--session` exist, but tool-call structure is lost; no `--worktree` launch exists. |
| TUI launch and recovery | `Fully implemented` — `hermes_cli/main_tui_launch.py:62-119,140-215` | `Not implemented` | `docs/ARCHITECTURE.md:103`; `docs/FEATURE_MATRIX.md:80`. Aether deliberately uses an ANSI terminal UI with no Node runtime. |
| Status, setup, doctor | `Fully implemented` — `hermes_cli/status.py:1-80`; `hermes_cli/status_report.py:1-60`; `hermes_cli/setup.py:1-220`; `hermes_cli/doctor.py:1-220` | `Fully implemented` | `aether/cli/app.py:438-524`; `tests/test_cli.py:52-56`; `docs/RELEASE_CHECKS.md:19-20`. |
| Command completion | `Fully implemented` — registry-driven command metadata in `hermes_cli/commands.py:44-150` | `Partially implemented` | `aether/cli/app.py:263-269`. Uses stdlib `readline`; no test and no metadata registry. |
| Update command | `Fully implemented` — `hermes_cli/update_cmd.py:1-60,700-760` | `Partially implemented` | `aether/cli/app.py:656-675`; `docs/RELEASE_CHECKS.md:32-37`. Requires a git checkout and has no network test. |

## 12. Security and permissions

| Capability | Hermes status and evidence | Aether status | Aether evidence and limitation |
|---|---|---|---|
| Approval gate and command guards | `Fully implemented` — `tools/approval.py:1207,1372,1402,1484`; `agent/tool_guardrails.py:1-5,21-42` | `Fully implemented` | `aether/tools/executor.py:43-64`; `aether/tools/permissions.py:10-24,68-71,102-106,127-149`; `tests/test_tools.py:43-65`. |
| Persistent approval posture | `Fully implemented` — `hermes_cli/approval_mode.py:1-45`; `tools/approval_context.py:1-220` | `Partially implemented` | `aether/tools/permissions.py:120-149`; `aether/cli/app.py:191-202`. "always" can persist in-session/config, but there is no revocation command or rich approval context model. |
| Scope and path isolation | `Fully implemented` — `hermes_scope.py:1-260` | `Partially implemented` | `aether/tools/permissions.py:26,55-92`. Workspace roots are checked for some file tools, but terminal `cwd`, git paths, redirects, and child working directories are incomplete. |
| Windows ACL and process identity checks | `Fully implemented` — `hermes_dir_acl.py:1-260`; `process_identity.py:1-220` | `Not implemented` | No equivalent modules appear in the tracked tree; Aether's permissions are path/tool based in `aether/tools/permissions.py:46-118`. |
| Prompt-injection defenses | `Fully implemented` — multiple guard modules including `tools/memory_context.py`, `tools/skills_guard.py`, and `agent/tool_guardrails.py` | `Partially implemented` | `aether/core/context.py:24-27`; `aether/skills/engine.py:11,70-71,113-115`; `SECURITY.md:7-29`; `tests/test_memory_skills.py:38-41`. No general sanitizer, provenance labels, or trust-boundary enforcement. |
| Secret redaction and file hygiene | `Fully implemented` — config/provider redaction paths | `Fully implemented` | `aether/utils.py:9,28-51`; `aether/logging.py:9-40`; `aether/config.py:113-116`; `tests/test_config.py:44-48`; `scripts/check.sh:22-26`. User-created `.env` permission hardening is not enforced. |
| Dependency security audit | `Fully implemented` — `hermes_cli/security_audit.py:1-58` | `Not implemented` | Aether has no third-party runtime dependencies and no `security audit` command; the closest control is `scripts/check.sh:22-26`. |
| OS/process sandbox | `Fully implemented` — terminal backends and hosted scoping in `tools/terminal_tool.py`, `tools/hosted_tool_policy.py` | `Not implemented` | `SECURITY.md:9,23-26`; `aether/tools/builtins.py:159-236`. Aether explicitly runs shell/Python with user privileges and inherited environment. |

## 13. Installation and deployment

| Capability | Hermes status and evidence | Aether status | Aether evidence and limitation |
|---|---|---|---|
| Bootstrap installers | `Fully implemented` — `setup-hermes.sh:1-120`; `setup-hermes.ps1:1-120` | `Partially implemented` | `scripts/install.sh:1-46`; `scripts/test_install.sh:1-27`; `docs/RELEASE_CHECKS.md:22`. Local git-remote install works; no hosted URL, Windows installer, pinned artifact hash chain, or package manager integration. |
| Packaging | `Fully implemented` — `pyproject.toml:1-60,140-220,240-320` | `Fully implemented` | `pyproject.toml:1-37`; `aether/__main__.py:1-4`; `tests/test_cli.py:19-22`. Aether uses stdlib-only dependencies and console entry point. |
| Container and declarative deployment | `Fully implemented` — `Dockerfile:260-360`; `docker-compose.yml:1-76`; `flake.nix:1-53`; `nix/packages.nix:1-111` | `Not implemented` | No Dockerfile, Compose file, Nix flake, or service manager appears in the tracked tree. |
| Self-update | `Fully implemented` — `hermes_cli/update_cmd.py:1-60,700-760` | `Partially implemented` | `aether/cli/app.py:656-675`; `docs/RELEASE_CHECKS.md:32-37`. Git-based update exists but is not network-tested and requires a checkout. |
| Uninstall and first-run setup | `Fully implemented` — `hermes_cli/uninstall.py:1-80`; `hermes_cli/profiles_service_cleanup.py:1-60` | `Fully implemented` / `Partially implemented` | Setup/first-run: `aether/cli/app.py:438-455`; `aether/config.py:153-163`; `aether/home.py:4-24`. Uninstall: `scripts/uninstall.sh:1-38`, not unit-tested. |
| Diagnostics | `Fully implemented` — `hermes_cli/doctor.py:1-220` | `Fully implemented` | `aether/cli/app.py:475-524`; `docs/RELEASE_CHECKS.md:19-20`. |
| CI and platform coverage | `Fully implemented` — `.github/workflows/README.md:491-498` and workflow files | `Partially implemented` | `README.md:11-29`; `docs/FEATURE_MATRIX.md:86-88`; `docs/RELEASE_CHECKS.md:5-9`. Local macOS evidence exists; no CI matrix or Windows coverage. |
| License and attribution | `Fully implemented` — MIT | `Fully implemented` | `LICENSE:1-21`; `NOTICE:1-10`; `docs/UPSTREAM_LICENSE.md:1-21`. |

## 14. Context management and reliability

| Capability | Hermes status and evidence | Aether status | Aether evidence and limitation |
|---|---|---|---|
| Context engine abstraction | `Fully implemented` — `agent/context_engine.py:1-90,97-133,172` | `Implemented differently` | `aether/core/context.py:12-78`. Aether has one concrete budget manager, not a pluggable engine interface. |
| Compression, pruning, anti-thrash safeguards | `Fully implemented` — `agent/context_compressor.py:2035-2058,2855-2915,5021-5065` | `Partially implemented` | `aether/core/context.py:45-78`; `tests/test_core.py:9-19`. Basic threshold/truncation/summary works; no cooldown, structural backoff, ineffective breaker, or preflight hooks. |
| Filesystem checkpoint and rollback | `Fully implemented` — `agent/checkpoints/manager.py:1-60,884,1071,1242` | `Not implemented` | No checkpoint module appears in the tracked tree; file writes are atomic via `aether/utils.py:54-75`, but multi-file rollback is absent. |
| Durable session persistence | `Fully implemented` — `agent/session_persistence.py:1-80,237-275,368-459` | `Partially implemented` | `aether/persistence/store.py:94-167`; `aether/core/agent.py:74-88`; `aether/cli/app.py:364-373`. Reload loses assistant `tool_calls` and tool `tool_call_id`, so resumed tool-call structure is incomplete. |
| Retry, backoff, fallback cooldown | `Fully implemented` — `agent/retry_utils.py:1-120,121-195`; `agent/fallback_cooldown.py:1-140` | `Fully implemented` | `aether/core/loop.py:54-73,91-97`; `aether/providers/registry.py:70-90`; `tests/test_providers.py:98-107`. Aether uses simpler retryable-error classification and fixed cooldowns. |
| Role alternation / schema repair | `Fully implemented` — upstream tool round and context engine paths cited in areas 1 and 3 | `Not implemented` | `aether/core/loop.py:101-124`; `aether/core/context.py:45-78`; `docs/FEATURE_MATRIX.md:24`. Context compression can remove a tool call while leaving its result. |
| Usage accounting and cost estimation | `Fully implemented` — catalog pricing and accounting paths in `agent/model_metadata.py`, `agent/fallback_cooldown.py` | `Partially implemented` | `aether/core/agent.py:197-205`; `aether/persistence/store.py:39-48,252-267`; `aether/core/context.py:84-86`. Token counters exist; `estimated_cost` is always `0.0` and configured limits are not enforced. |
| Atomic local writes and redacted logs | `Fully implemented` — checkpoints and persistence layers | `Fully implemented` | `aether/utils.py:54-75`; `aether/logging.py:9-40`. |
| Startup watchdog and gateway hygiene | `Fully implemented` / `Partially implemented` — `hermes_startup_watchdog.py:1-120`; `gateway/run.py:250-340,1600-1665` | `Not implemented` | No watchdog or gateway hygiene module exists in the tracked tree. |
| Benchmarks and release checks | `Fully implemented` — extensive test suites and runners | `Partially implemented` | `scripts/benchmark.py:11-38`; `scripts/check.sh:1-46`; `docs/RELEASE_CHECKS.md:11-37`. Prior local checks passed; live providers, hosted installer, update network path, and local inference remain unverified. |

## Summary

Aether has a working local-first core: bounded turn loop, provider switching/fallback, tool execution with approvals, SQLite sessions, Markdown memory, `SKILL.md` skills, task delegation, scheduler baseline, and a usable CLI. The largest verified gaps are not cosmetic: tool-call replay after resume, role-alternation repair, scheduler execution honesty, provider cost enforcement, web URL safety, tool timeout enforcement, external memory/provider/MCP extension surfaces, durable subagents, messaging, voice, browser automation, containers/Nix, and service management.

This document should be updated when a capability is implemented and verified. Until then, no section should be read as a claim of Hermes parity.
