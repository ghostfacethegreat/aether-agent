# Known Limitations

This document records what Aether does not yet prove or does not yet do. It is intentionally conservative: an unimplemented, untested, or unverified capability is not described as working.

## Release state

- Version `0.1.0` is the current published alpha baseline.
- No `0.2.0` release, tag, merge, or publication has been completed; the package version remains `0.1.0`.
- Phases B–F have implementation baselines on `feat/aether-parity-foundation`; the latest verified CI checkpoint passed the Python 3.10–3.14 matrix, including unit/check and clean-install gates. The branch is in a draft PR and has not been merged or released.
- There are no release tags in the repository at this checkpoint.
- GitHub Actions CI is configured for Python 3.10–3.14. A green run applies only to its recorded commit; later commits require a fresh run.
- Push, PR, merge, tag, and release status must be confirmed before being claimed.

## Intelligence gaps

- Adaptive planning is implemented with deterministic classification and inspectable plans; it does not generate plans with a model. Verification status is derived only from successful `test_run` evidence or strictly recognized check commands; arbitrary text containing test keywords is treated as unverified.
- Plan checkpoints are durable in SQLite and resume avoids completed or non-idempotent tasks, but they are local single-process state with no cross-process locking or event-driven resume. Bounded project-context files are loaded from the workspace root without recursion, symlink following, or network access.
- High-risk plans record an approval requirement; planning does not yet add a separate approval gate beyond existing tool permissions.
- Planner tool selection is a coarse keyword-to-tool map, not capability search or verified tool-result interpretation.
- Planning-specific cancellation and cost-limit scenarios are not separately tested; general core cancellation and cost tests still pass.
- Layered memory is additive SQLite storage for working, episodic, semantic, procedural, and user records; retrieval uses deterministic lexical scoring, not embeddings or learned ranking.
- Layered memory itself does not generate new facts from tool output or perform model-driven consolidation; Phase D learning records experience and proposes skills from verified evidence.
- Layered user-model writes are explicit CLI/tool actions; feedback is scoped to explicit user commands, not arbitrary file, web, or child-agent text.
- Layered memory has no cross-process locking, distributed sync, or encrypted storage.
- Learning discovery groups verified experiences deterministically by tool set and objective keywords; it does not use a model to author new skills.
- Skill validation checks structure, known tools, permissions, secrets, injection patterns, examples, and improvement regressions; it is not a sandboxed execution harness or an independent verifier.
- Rollback restores stored skill content but does not undo external side effects from earlier skill use.
- Skill metrics are local counters, not task-quality benchmark results.
- Learning history is local SQLite state with CLI inspection; there is no event-driven or cross-process learning loop.
- Model routing is advisory over configured candidates (active model, configured fallbacks, role pins, and matching `models.metadata` entries); it cannot enable an unconfigured model or provider.
- Routing classification is deterministic keyword/signal based, not model-driven or learned from free text alone.
- Capability and pricing facts depend on provider reports and user-configured metadata; unknown facts stay unknown and are never treated as verified or free.
- Provider health comes from local failure records and cooldowns; routing diagnostics do not poll providers or verify availability live.
- Explicit `--provider`/`--model` or `Agent(provider_name=..., model=...)` selections are authoritative; there is no `routing.manual` override switch.
- Role spend shares apply per turn to a child's portion of the shared budget; they do not raise the shared limit.
- Verified performance recommendations require `mark_model_performance_verified()` evidence; bare success text is not verified.
- Coding workflow baseline: `repo_index` performs bounded filename/source search, Python/JavaScript/TypeScript/Lua/Go/Rust lexical declaration search, and root plus nested `.gitignore` handling (common scoped patterns and negations are tested). It also maintains an opt-out persistent incremental index in `repo_index.db` under `AETHER_HOME`, with bounded file and symbol counts and size/mtime/ctime/hash invalidation. `patch_preview` validates existing-file unified diffs; `patch_apply` performs preflighted, approval-gated edits; and `test_run` runs a fixed set of repository checks. This is not yet a language server, call graph, IDE integration, automatic patch generation, multi-turn TDD controller, or independent semantic diff review. The index has no cross-process locking guarantee, and full Git pathspec/escape compatibility is not claimed. Patch application intentionally refuses file creation/deletion, renames, and binary files.
- Research work does not yet produce structured evidence, citation, contradiction, and confidence reports.
- Tool schemas are not deferred behind capability search.
- The default role registry now includes eleven specialist roles and automatic dependency-aware team planning. It remains a bounded role library, not Hermes-scale dynamic agent spawning.
- An independent verifier is used in implementation, debugging, and documentation workflows. It recognizes only successful test/check commands recorded in its own terminal tool log; it is not a formal proof of correctness or a long-running goal supervisor.

## Benchmark and comparison gaps

- No task-quality benchmark harness exists yet; the Phase E runner is a deterministic routing simulation over fixed fixtures, not task-result evidence. The repository test runner and CI validate engineering regressions, not comparative model task success.
- No benchmark result artifacts exist under `benchmarks/results/`; the routing runner prints JSON to stdout and has no `--output` or file writes.
- The startup benchmark measures cold start time and memory, not task success. Routing-simulation fixture eligibility is not model quality or task-quality parity.
- No live Aether/Hermes comparison was run.
- No Hermes parity, equivalence, or superiority claim is supported at this checkpoint.
- Free-tier model IDs, limits, and costs can change without notice and must be verified with each provider.

## Runtime and platform gaps

- Aether is a CLI application; no desktop application exists yet.
- No Tauri, React, TypeScript, Vite, or FastAPI application tree exists yet.
- No `apps/website/` tree exists yet.
- No Telegram or Discord adapter exists.
- No voice input or output pipeline exists.
- Browser automation is disabled unless the user configures a local command template.
- Scheduled jobs run in-process and are not a daemon or service.
- No cross-process concurrency guarantees are claimed for the scheduler.
- No OS-level sandbox is provided; tool subprocesses inherit the user environment.
- Full verbose test output emitted `ResourceWarning` notices for unclosed SQLite connections; no test or check failed.

## Provider and network gaps

- Live hosted provider calls were not part of the Phase A verification.
- Real hosted SSE streams are covered only by synthetic tests for the accumulator.
- Live Ollama inference was not recorded in the Phase A verification.
- Network update against the public remote was not recorded in the Phase A verification.
- No hosted installer URL is published or tested; only local install tests were run.

## Security and verification gaps

- Aether is not a security sandbox.
- Web, file, tool, and agent output is data, not trusted instruction.
- Untrusted content must never modify persistent instructions or skills.
- Approval, permission, strict-root, and redaction controls must be re-tested after every feature that touches tools or child agents.
- No third-party security audit has been performed.
- Secret scanning is local and pattern-based, not a proof that no secret exists.

## Tooling gaps

- No configured lint or typecheck command exists in the repository.
- `ruff`, `mypy`, and `pyright` were not installed or claimed in the Phase A verification.
- Some historical test counts in [RELEASE_CHECKS.md](RELEASE_CHECKS.md) are intentionally historical and do not match the current suite.

Update this file when a limitation is fixed and verified. Do not remove a limitation because code appears to exist; remove it only after tests and recorded checks support the change.
