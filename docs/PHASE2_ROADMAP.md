# Phase 2 Roadmap

This roadmap turns [PHASE2_FEATURE_COMPARISON.md](PHASE2_FEATURE_COMPARISON.md) into staged work. It is a plan, not a completion report. Each milestone must end with a working checkpoint, tests that exercise behavior, honest validation notes, documentation updates, and its own Git commit.

## Ranking method

Scores are relative and deliberately practical:

- **User value**: how much the gap improves normal local use.
- **Complexity**: implementation and review effort in the current stdlib-only core.
- **Memory/CPU**: expected runtime cost on an 8 GB Apple Silicon machine.
- **Free feasibility**: whether it can work without paid accounts or mandatory external services.
- **Reliability impact**: whether the gap can cause incorrect, misleading, or unsafe behavior today.

`P0` means fix before expanding surface area. `P1` means high-value core improvement. `P2` means useful but larger optional surface. `P3` means deferred or deliberately different.

## Ranked gap register

| Rank | Gap | User value | Complexity | Memory/CPU | Free feasibility | Reliability impact | Priority |
|---:|---|---|---|---|---|---|---|
| 1 | Preserve tool calls on resume and repair context role alternation | High | Low | Low | High | High: malformed replay can fail strict providers or misinterpret history | P0 |
| 2 | Fix Anthropic multi-turn tool-call replay conversion | High | Low | Low | High | High: likely broken tool continuation on one supported transport | P0 |
| 3 | Enforce tool timeout metadata, tighten web URL safety, restrict redirects/private networks, and redact model-facing tool output | High | Medium | Low | High | High: prevents hangs, SSRF-like access, and secret leakage | P0 |
| 4 | Make scheduler execution honest: run due prompts, start background scheduling, record executions, and report manual ticks accurately | High | Medium | Low | High | High: current "ran N jobs" can be false | P0 |
| 5 | Implement cost estimates and enforce configured per-turn cost/paid confirmation limits | High | Medium | Low | High | High: current cost fields are always `0.0` and limits are inert | P0 |
| 6 | Harden path/tool scope checks for terminal `cwd`, git paths, child workdirs, and redirects | High | Medium | Low | High | High: permission checks currently miss several write/execute paths | P0 |
| 7 | Add local skill usage lifecycle, deterministic curation, rollback, and approval-aware skill mutation | High | Medium | Low | High | Medium: self-improvement can become unsafe or stale without controls | P1 |
| 8 | Add web result caching, truncation spill, backend abstraction, and keyless fallback controls | Medium-High | Medium | Low | High | Medium: improves reliability and lowers third-party dependence | P1 |
| 9 | Improve installer relocatability, update validation, doctor resolution, and CI coverage | High | Medium | Low | High | High for public adoption: wrapper currently points at a source checkout | P1 |
| 10 | Add durable subagent records, resume through CLI, output schemas, result redaction, and task-ledger integration | Medium-High | High | Low-Medium | High | Medium | P1 |
| 11 | Add provider, memory, and MCP extension interfaces with explicit opt-in | Medium | High | Low-Medium | High | Medium | P2 |
| 12 | Add a minimal local webhook/relay gateway adapter before broader messaging platforms | Medium | High | Medium | Medium: platform credentials may be optional but accounts are often required | Medium | P2 |
| 13 | Add optional local CDP browser automation with URL policy and no cloud requirement | Medium | High | Medium | Medium | Medium | P2 |
| 14 | Add optional local STT/TTS module with explicit dependency install | Medium for CLI users | High | Medium-High: models/audio deps | High in principle, heavy in practice | Low-Medium | P3 |
| 15 | Add TUI/desktop surfaces | Low for lean-core goal | High | High | High | Low | P3 / N/A for current design |

## Staged implementation plan

### Milestone 2.0 — Source audit and roadmap

**Status:** completed by this documentation checkpoint.

**Scope**
- Refresh upstream to `b98c388a880b1b6fd303c9c2821a3946651a0b4c`.
- Compare all 14 required areas using Aether commit `bdbe2462dda3c4646086385d600b4e2ab23f4957`.
- Classify each capability and cite source evidence.
- Rank gaps by user value, complexity, memory/CPU, free feasibility, and reliability.

**Commit:** `docs: phase 2 feature gap audit`

---

### Milestone 2.1 — Replay and context correctness

**Status:** implemented; regression tests added and local checks passed.

**Goal:** make multi-turn tool conversations survive persistence, resume, compression, and Anthropic transport conversion.

**Changes**
- Persist assistant `tool_calls` and tool `tool_call_id` fields in SQLite messages.
- Hydrate those fields when loading sessions for `/resume` and `--session`.
- Add a context repair pass that removes orphaned tool results or restores missing pairs after compression.
- Fix Anthropic replay conversion to read nested `function.name` / `function.arguments` emitted by the loop.
- Add regression tests that run a mock tool turn, persist it, reload it, and ask a second provider turn with tool history.

**Exit criteria**
- A resumed session with prior tool calls builds valid OpenAI-compatible and Anthropic-compatible message lists.
- Compressed histories do not contain orphaned `role=tool` messages.
- `scripts/check.sh` passes.

**Commit:** `fix: preserve tool-call replay and repair context alternation`

---

### Milestone 2.2 — Tool execution and URL safety

**Status:** implemented; regression tests added and local checks passed.

**Goal:** close the highest-risk execution gaps without adding dependencies.

**Changes**
- Make `ToolExecutor` enforce `Tool.timeout` for all tools, not only subprocess handlers.
- Reject redirects to non-http(s), private, loopback, link-local, or credential-bearing URLs unless explicitly configured for local development.
- Preserve embedded-credential denial and add redirect-chain validation for `web_fetch`.
- Redact secrets in model-facing tool results, not only tool logs.
- Route terminal `cwd`, git `paths`, and delegated work directories through path-root validation.
- Add tests for timeout denial, redirect rejection, secret redaction, and path escapes.

**Exit criteria**
- Dangerous or oversized tool work terminates predictably.
- Fetching a private-network URL cannot succeed through redirects.
- Path and approval tests cover terminal, git, and delegated contexts.

**Commit:** `fix: harden tool execution and URL safety`

---

### Milestone 2.3 — Scheduler truth and durable local execution

**Goal:** make scheduled jobs actually run and report only what happened.

**Changes**
- Start the background scheduler in interactive chat when explicitly enabled.
- Give manual `schedule tick` a real runner and change output to distinguish due, executed, skipped, and failed jobs.
- Add a local executions table or file ledger with run IDs and outcomes.
- Add at-most-once admission for recurring jobs.
- Add job update, pause, resume, and cancel controls.
- Keep delivery local by default; do not imply messaging delivery exists.

**Exit criteria**
- A due mock-provider job executes, records an outcome, and is not re-fired after a simulated restart.
- Manual tick no longer claims execution when no runner exists.
- Scheduler thread start/stop is tested.

**Commit:** `feat: make scheduler execute due jobs`

---

### Milestone 2.4 — Provider cost and limit enforcement

**Goal:** make cost and limit controls real rather than decorative.

**Changes**
- Implement `rough_cost()` from catalog price metadata where available.
- Record real estimates in usage rows and CLI `/cost`.
- Enforce `costs.max_estimated_usd_per_turn` and `confirm_paid` before paid-provider calls.
- Send configured `top_p`; safely apply configured `extra_headers` without logging secret values.
- Clear provider cooldown after a successful call to the same provider.
- Add tests for estimate calculation, paid confirmation denial, header application/redaction, and cooldown reset.

**Exit criteria**
- Paid calls cannot silently exceed configured local limits.
- Cost output is no longer always `0.0` when pricing metadata is available.
- No secret or header value appears in logs or diagnostics.

**Commit:** `feat: enforce cost transparency and provider limits`

---

### Milestone 2.5 — Local skill curation and safer self-improvement

**Goal:** add conservative self-improvement without a cloud hub or mandatory model calls.

**Changes**
- Extend skill usage state with lifecycle metadata: active, stale, archived.
- Add deterministic archive/cleanup rules with no deletion by default.
- Add content-addressed backups and single-edit rollback.
- Require explicit approval for skill mutation beyond benign create/edit paths.
- Add opt-in prompt review that uses the already configured provider and is disabled by default.
- Expand skill safety scanning beyond hardcoded substrings where feasible without dependencies.

**Exit criteria**
- Stale skills can be archived and restored.
- Skill mutations write audit records.
- No background LLM call occurs unless explicitly enabled.

**Commit:** `feat: add local skill curation and rollback`

---

### Milestone 2.6 — Web research hardening

**Goal:** make keyless web research more reliable and explicit about backend behavior.

**Changes**
- Add a small backend abstraction around DuckDuckGo, Brave, and Serper without making APIs mandatory.
- Add TTL disk cache and in-process single-flight for identical searches.
- Add head/tail extract spill with paging hints.
- Add explicit config switches for keyless fallback and URL policy.
- Add tests with recorded/static fixtures only; do not require live web access in CI.

**Exit criteria**
- Repeated identical searches do not issue duplicate requests in-process.
- Oversized extracts are bounded and recoverable.
- Offline tests cover backend selection and failure handling.

**Commit:** `feat: harden web research backends`

---

### Milestone 2.7 — Installation, update, and portability hardening

**Goal:** make public installation less dependent on a mutable source checkout.

**Changes**
- Make installer wrapper independent of source-tree movement where possible, or fail with an actionable relocation message.
- Add a network update test path that runs only when explicitly requested.
- Fix `doctor --live` to resolve configured provider settings rather than catalog defaults.
- Add CI config for compile/tests/markdown links/secret scan on Linux and macOS.
- Keep Windows, Docker, and Nix as documented deferred surfaces unless actually added and tested.

**Exit criteria**
- Moving or reinstalling a source checkout does not silently break the CLI.
- `doctor --live` checks the active configured endpoint/model.
- CI config is syntactically valid and mirrors `scripts/check.sh`.

**Commit:** `feat: harden installation and update paths`

---

### Milestone 2.8 — Optional extension surfaces

**Goal:** expand only after the core gaps are closed.

**Candidates**
- Provider/memory plugin interfaces behind explicit opt-in.
- MCP client support with hosted/stdio policy differences.
- Durable subagents with steer/stop and output schemas.
- Minimal local webhook/relay gateway adapter.
- Optional CDP browser automation.
- Optional local STT/TTS with separately installed dependencies.

**Exit criteria**
- Each candidate gets its own audit update, design note, tests, and commit.
- No optional surface becomes a mandatory dependency.
- No parity claim is added to public docs without source evidence and verification.

**Commit pattern:** one commit per candidate, e.g. `feat: add opt-in MCP tools`, `feat: add local webhook gateway`.

## Validation matrix

Validation must exercise behavior, not just imports. Results should be recorded in `docs/RELEASE_CHECKS.md` after each milestone.

| Area | Required validation | Baseline at audit |
|---|---|---|
| Conversation persistence | Scripted mock-provider tool turn, exit, resume, second turn; assert tool history and token usage survive | M2.1 regression passed: tool calls and tool result IDs now survive reload; token usage was already covered |
| Provider switching | Switch provider/model in chat and one-shot mode; assert active provider and model reset correctly | Synthetic/unit coverage passed; live provider switch not recorded |
| Local inference | If Ollama is installed and serving, run one real local prompt; if unavailable, report "not validated" | Not validated; no live Ollama run recorded |
| Tool execution | Safe parallel tools, unknown tool, denied approval, destructive strict-denial, timeout | M2.2 executor-level timeout regression passed; safe/approval/denial tests still pass |
| Memory retrieval | Add, search, export, import, and inject into prompt under char budget | Engine tests passed; CLI commands not unit-tested |
| Skills | Create, view, edit, list, usage tracking; model-driven skill tool turn | Engine tests passed; model-driven turn not tested |
| Subagents | Delegate two tasks with mock provider through real `Agent`; assert results, ledger, and reduced tools | Fake-agent test passed; real-agent end-to-end absent |
| Error recovery | Provider failover, cooldown, malformed tool arguments, context compression with tool calls | Provider failover passed; M2.1 context repair and Anthropic nested replay regressions passed |
| Permissions | Deny, once, session, always, strict destructive denial, path root escape, terminal cwd, git paths | M2.2 strict-mode regressions cover terminal cwd and git paths; core permission tests still pass |
| Installation | Local git-remote install, mock run, uninstall; separate explicit network update test | Local install passed; network update not tested |
| Web | Static-fixture search/fetch; redirect/private URL denial; oversized extract behavior | M2.2 private URL and safe-redirect regressions passed; live fetch remains unvalidated |
| Scheduler | Add job, enable background scheduler, execute due mock job, simulate restart, no duplicate fire | CRUD/tick tests passed; execution honesty and durability incomplete |

## Public-development protocol

- Keep `main` deployable; develop larger candidates on branches and merge after tests.
- Use one commit per completed milestone; do not combine unrelated milestones.
- Update the comparison, feature matrix, architecture notes, README, and changelog in the same commit when behavior or status changes.
- Never publish API keys, `.env` files, guessed benchmark numbers, fabricated screenshots, or live-provider claims that were not actually run.
- Do not publish a hosted installer URL until that exact URL and installer have been tested.
- State unavailable local services and failed validations explicitly.
