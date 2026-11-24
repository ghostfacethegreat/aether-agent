# Known Limitations

This document records what Aether does not yet prove or does not yet do. It is intentionally conservative: an unimplemented, untested, or unverified capability is not described as working.

## Release state

- Version `0.1.0` is the current published alpha baseline.
- No `0.2.0` release, tag, merge, or publication has been completed.
- There are no release tags in the repository at this checkpoint.
- There is no GitHub Actions CI workflow yet.
- Push, PR, merge, tag, and release status must be confirmed before being claimed.

## Intelligence gaps

- Adaptive planning is implemented with deterministic classification and inspectable plans; it does not generate plans with a model or verify completion independently yet.
- Plan checkpoints are durable in SQLite and resume avoids completed or non-idempotent tasks, but they are local single-process state with no cross-process locking or event-driven resume.
- High-risk plans record an approval requirement; planning does not yet add a separate approval gate beyond existing tool permissions.
- Planner tool selection is a coarse keyword-to-tool map, not capability search or verified tool-result interpretation.
- Planning-specific cancellation and cost-limit scenarios are not separately tested; general core cancellation and cost tests still pass.
- Layered memory is additive SQLite storage for working, episodic, semantic, procedural, and user records; retrieval uses deterministic lexical scoring, not embeddings or learned ranking.
- Layered memory does not generate new facts from tool output, promote procedures into skills, or perform model-driven consolidation; that evidence pipeline belongs to the learning phase.
- Layered user-model writes are explicit CLI/tool actions; approval policy for learned user-model changes is not implemented.
- Layered memory has no cross-process locking, distributed sync, or encrypted storage.
- The learning loop does not yet record verified experience or version/rollback skill changes from evidence.
- Model routing uses configured order and fallback, not a task-facing capability registry.
- Coding work does not yet build a repository index or produce verified diff reviews.
- Research work does not yet produce structured evidence, citation, contradiction, and confidence reports.
- Tool schemas are not deferred behind capability search.
- Specialist orchestration has four roles, not the planned 18.
- Independent completion verification and long-running goal supervision are not implemented.

## Benchmark and comparison gaps

- No task-quality benchmark harness exists yet.
- No benchmark result artifacts exist under `benchmarks/results/`.
- The startup benchmark measures cold start time and memory, not task success.
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
