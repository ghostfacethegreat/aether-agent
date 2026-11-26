# AETHER Workstation Acceptance Gate

This document defines when AETHER is ready to become the primary day-to-day agent on a user's computer. A green unit-test matrix is necessary, but it is not sufficient. Every capability below must be demonstrated on the target workstation with recorded evidence before AETHER is described as a Hermes replacement.

## Release rule

AETHER is **not a full replacement** while any critical workflow is missing, unsafe, or unverified. Keep the existing agent installed and usable until the parallel-run and rollback checks pass. AETHER may be adopted in stages, but the full-replacement claim requires every critical gate in this document.

The minimum project hardware target is an 8 GB Apple Silicon Mac. Release verification must also record the actual macOS version, chip, RAM, Python version, active provider/model, and whether each model call is local, free-tier, or billable.

## Critical workflow matrix

| Workflow | Required end-to-end demonstration | Pass condition |
|---|---|---|
| School and learning | Read supplied notes/PDF/text; explain a topic at the requested level; produce a study guide, flashcards, worked examples, and a study plan; answer a research question with source links and dates. | No fabricated citations or unsupported facts; explanations are understandable; the agent distinguishes teaching/help from doing assessed work dishonestly; all generated files are saved where requested. |
| Coding projects | Open an existing repository; understand project instructions; find relevant code; plan a change; create, edit, and delete files only with the configured approval; run focused tests; diagnose a failing test; repair it; review the final diff independently. | The resulting application behaves as specified; tests actually ran and their exit codes are recorded; no out-of-workspace writes; no false verified/completed status; the final diff and remaining risks are shown. |
| Research and web use | Turn a broad question into queries; gather several independent sources; extract claims; cite each claim; detect disagreement and stale information; summarize confidence and unknowns. | Links resolve; citations support the statements; conflicting evidence and publication dates are visible; page instructions are treated as untrusted data; no invented browsing or source claims. |
| Browser and computer tasks | Use an isolated browser profile; navigate and inspect pages; fill forms and download files only within allowed roots; request approval before sending, publishing, purchasing, deleting, or changing account/security settings. | Private-network/redirect protections work; credentials and cookies are isolated from normal browsing; approvals cannot be bypassed by web content or child agents; every external side effect is auditable. |
| Personal organization | Persist goals and preferences; build a task plan; schedule and list reminders; resume a long task after CLI restart; cancel it; recover from a failed step without repeating a completed non-idempotent action. | State survives restart; due times and time zones are explicit; cancellation is reliable; retries are bounded; no duplicate side effects occur. |
| Communication and voice | Use the supported messaging adapter with isolated user/session identities; receive text; produce a reply draft; optionally transcribe speech and speak a response. | The user can disable each adapter; session identity is enforced; webhook signatures/replay protections and rate limits are tested; sending or uploading still requires configured approval. |
| Business and content operations | Run a repeatable workflow that researches a topic, organizes source material, drafts copy/content, prepares a schedule, and packages assets for review. | Deliverables are saved and traceable; the agent reports incomplete steps honestly; publishing, account changes, and spending require explicit approval; no platform policy or rights bypass is attempted. |
| General file and data work | Find, summarize, transform, and organize user-authorized files; produce useful outputs such as Markdown, CSV, and supported office formats where adapters exist. | File boundaries are enforced; binary/large files are handled safely; originals are preserved unless overwrite is approved; output files are validated and discoverable. |

## Engineering gates

### 1. Installation and workstation stability

- A clean install succeeds from a fresh checkout on the supported macOS target.
- The installer, upgrade path, configuration, uninstall, and recovery instructions work without deleting user projects or existing memory.
- AETHER starts, exits, and restarts cleanly; a multi-hour session does not leak unbounded processes or memory.
- Local-only operation works with no paid API key and makes no hidden network or billable calls.
- A provider outage, rate limit, invalid model ID, missing optional integration, and offline state produce actionable errors.
- The existing Hermes installation and its user data remain untouched until the user deliberately switches over.

### 2. Task-quality evidence

- Maintain a fixed fixture suite covering each critical workflow above.
- Record exact prompt, fixture/workspace revision, model/provider, configuration, tool trace, timestamps, elapsed time, token usage/cost when available, exit status, evaluator rubric, score, and failure notes.
- Run deterministic mock-provider tests in CI. Live model and AETHER-versus-Hermes comparisons are opt-in and use the same model, instructions, workspace, tools, permissions, and budgets.
- Store raw results, including failures. Do not publish only successful runs.
- Require at least 90% of scored non-safety task criteria to pass across the representative suite, and require 100% pass on critical security, approval, privacy, and verification criteria. A human review must confirm the high-impact school, research, coding, and business outputs.
- A benchmark score is not a substitute for the user's own acceptance of their real workflows.

### 3. Security and control

- All tool permissions, approvals, secret redaction, strict workspace boundaries, child-agent permission intersections, shared budgets, and cancellation protections have regression tests.
- Prompt injection from web pages, files, emails, project instructions, memories, skills, and agent reports cannot grant permissions or override the current user request.
- No model claim, successful file write, or child-agent report can mark a task verified. Verification must be grounded in the required independent tool evidence and task-specific checks.
- Irreversible and external side effects are explicit, previewed, and approval-gated.
- AETHER is not described as an OS sandbox unless an OS-level isolation backend is installed, configured, and tested.

### 4. Parallel-run and cutover

- Run AETHER alongside the existing assistant for at least one representative week of normal use.
- Compare outcomes on the same set of real, non-sensitive tasks; record failures and manual interventions.
- Confirm memory export/import, project workspace selection, configuration backup, and rollback to the previous assistant.
- Do not remove the previous assistant until the user has confirmed that the required workflows pass and the fallback is available.

## Evidence record template

For each run, record:

- Date/time and machine details:
- AETHER commit/version:
- Provider/model and billing mode:
- Workflow/category and exact task:
- Workspace/fixture revision:
- Tools used and approval decisions:
- Test/check commands, exit codes, and outputs:
- Result against each acceptance criterion:
- Failure, manual intervention, or recovery required:
- Cost/tokens/elapsed time (or explicitly unavailable):
- Human reviewer decision:

## CLI Preview workstation gate — PASS (2026-11-26)

This records the actual Mac gate for the CLI Preview verification slice, not a full-replacement claim. PR #8 is open and draft on `feat/aether-parity-foundation`; there is no merge, tag, release, version/default-branch change, or published binary.

| Item | Recorded value |
|---|---|
| macOS | 15.0.1, build 24A348 |
| Chip | Apple M1, arm64 |
| RAM | 8589934598 bytes (~8 GB) |
| Python | 3.14.2 |
| Active provider/model | `mock` / `mock-standard` |
| Local suite | 274 tests OK; `scripts/check.sh`, `scripts/test_install.sh`, and `git diff --check` OK |

Checklist — PASS:

- [x] fresh install
- [x] `aether --version`
- [x] `doctor`
- [x] mock conversation
- [x] provider/model switch
- [x] memory add/search across separate processes
- [x] plan status/resume
- [x] approval prompt (fresh once)
- [x] `repo_index` search
- [x] `patch_preview`
- [x] approval-gated `patch_apply`
- [x] `test_run`
- [x] direct `unittest`
- [x] Aether home directory mode `0700`
- [x] `state.db` mode `0600`
- [x] uninstall removes the wrapper; Aether state and project data preserved

Cancellation is covered by deterministic unit tests in the 274-test suite, not by a live long-running cancellation demonstration.

### Scope of this PASS

- The coding workflow is a guarded foundation with persistent incremental retrieval, not a complete autonomous TDD system.
- `repo_index` handles common root and nested `.gitignore` patterns, with regression coverage for scope and ordered negation.
- `repo_index action="symbols"` provides bounded lexical declaration search for Python, JavaScript/TypeScript, Lua, Go, and Rust, with an incrementally refreshed cache and size/mtime/ctime/hash invalidation.
- Research does not yet provide a full source/citation/contradiction/confidence report.
- Browser automation/MCP, messaging/voice, isolated durable background execution, full task-quality benchmarks, and advanced skill curation remain open workstreams.
- No same-model task-quality comparison has established Hermes parity, and no comparative benchmark was run.
- AETHER remains a CLI product; a desktop application is not part of the current implemented baseline.

### Gates still open

- No live hosted or paid provider checks.
- No task-quality benchmark or Hermes parity/superiority claim.
- No browser, voice, or desktop artifact.
- No signed macOS release.
- No external security review.
- No live long-running cancellation demonstration.
- No merge, tag, or release.
- Engineering gates 2 and 4 above (task-quality evidence, parallel-run and cutover) remain open, gate 3 has not had an external security review, and the full-replacement claim in the release rule is not made.

Integration base `fcee9db806fff2788198988fea07703b6a5f0cd1` passed GitHub Actions run #90 (run IDs `45737098740` / `45737090789`) with 238 tests on Python 3.10–3.14, `scripts/check.sh`, and clean-checkout install/uninstall. That is Linux CI evidence for the base only; later local changes are not yet CI-verified, fresh CI is required for the exact final pushed SHA, and Actions is authoritative.

This status section must be refreshed from the actual branch, CI, release metadata, and workstation runs before any replacement claim.
