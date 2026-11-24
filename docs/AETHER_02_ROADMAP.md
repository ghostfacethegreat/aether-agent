# Aether 0.2.0 Roadmap

This roadmap tracks the additive upgrade from the verified `0.1.0` baseline at commit `01ee003` to `Aether v0.2.0`. Baseline facts are in [AETHER_02_BASELINE.md](AETHER_02_BASELINE.md); extension points are in [AETHER_02_ARCHITECTURE.md](AETHER_02_ARCHITECTURE.md).

## Milestone contract

Every milestone must end with:

1. a concise report of changed files
2. observable behavior added or changed
3. focused tests actually run
4. fixes for any failures found
5. documentation updates
6. a working checkpoint commit

Do not mark a milestone complete based only on code inspection. Do not fabricate screenshots, benchmark results, CI results, or provider behavior.

## Phase 0 — baseline and design

**Goal:** establish a verified source of truth before behavior changes.

**Scope:**

- fetch and base work on `origin/main`
- create `feat/aether-02-neon-agent-platform`
- verify version, packaging, dependencies, tests, checks, benchmarks, CLI surface, providers, tools, memory, skills, orchestration, scheduler, and CI state
- add the three 0.2.0 planning documents
- commit the documentation-only checkpoint

**Verification:**

- `git status --short --branch`
- `python3 -m unittest discover -s tests -q`
- `bash scripts/check.sh`
- `bash scripts/test_install.sh`
- `git diff --check`

**Exit state:** baseline docs committed; no runtime behavior changed in this phase.

## Phase 1 — visual identity foundation

**Goal:** introduce the required purple-neon palette and a safe ANSI engine.

**Likely files:** new visual modules under `aether/ui/` or `aether/cli/`, `aether/cli/render.py`, config defaults, renderer tests, docs.

**Behavior:**

- primary, secondary, and background palette use the exact required hex colors
- semantic color roles replace ad hoc color choices
- truecolor, 256-color, 16-color, `NO_COLOR`, `TERM=dumb`, and non-TTY paths are explicit
- untrusted text is sanitized before escape sequences are added
- existing banner/dashboard/table/tool output remains functional

**Verification:** focused renderer tests plus full checks.

## Phase 2 — ASCII font registry

**Goal:** ship at least 12 genuinely different offline ASCII fonts.

**Likely files:** new font data/modules, config defaults, CLI help/docs, font tests.

**Behavior:**

- every font is local and deterministic
- fonts are visibly different, not renamed copies
- random selection avoids the immediately previous font
- selected font persists safely and old config remains valid

**Verification:** font count/distinctness tests, random-selection tests, config compatibility tests.

## Phase 3 — ASCII art and animated title

**Goal:** render Aether branding with local fonts and a smooth title sequence.

**Likely files:** art renderer, title animation module, renderer façade, fallback assets, tests, docs.

**Behavior:**

- generated ASCII art uses the selected font and palette
- title animation is smooth on a TTY
- non-TTY/no-color/dumb terminals get a stable static title
- AI art generation has a deterministic offline fallback
- no network request is required for startup or local art

**Verification:** animation/frame tests with fake clocks or writers, fallback tests, non-TTY tests.

## Phase 4 — new CLI command surface

**Goal:** expose font/art controls through CLI and slash commands.

**Required commands:**

- `aether fonts`
- `aether font random`
- `aether font set block`
- `aether font preview`
- `/font`
- `/font random`
- `/font set glitch`
- `/font list`

**Behavior:**

- aliases work without breaking current commands
- help output documents the new commands
- invalid font names fail clearly
- completion includes the new slash commands

**Verification:** parser/dispatch tests for every command and invalid input.

## Phase 5 — interactive dashboard

**Goal:** modernize the live dashboard using real state.

**Behavior:**

- provider, model, session, context, cost, memory, skills, tools, and workspace remain visible
- purple-neon panels and semantic indicators replace the old basic banner
- status values come from `Agent.status_summary()` and store data
- output remains readable in reduced-color and no-color terminals

**Verification:** dashboard snapshot tests using deterministic mock state.

## Phase 6 — dynamic agent graph

**Goal:** visualize real orchestration state.

**Required commands/flows:**

- `aether agents` views should work with stored and active runs
- `/agents` should show live role/task state
- `/team` should show selected roles, dependencies, and rationale

**Behavior:**

- graph nodes and edges derive from `SharedTaskState.snapshot()` and persisted task rows
- statuses reflect actual `pending`, `running`, `retrying`, `completed`, `failed`, `cancelled`, and `timed_out` states
- animation never invents progress
- cancellation and stored-run recovery update the graph correctly

**Verification:** mock orchestration runs drive graph projection tests; no live paid provider required.

## Phase 7 — specialist role catalog

**Goal:** expand from four default roles to at least 18 meaningful specialists.

**Behavior:**

- each role has a distinct prompt, output contract, tool policy, approval requirements, and iteration budget
- forced deny/approval rules remain monotone
- read-only skill rules remain where appropriate
- existing `researcher`, `developer`, `debugger`, and `reviewer` behavior remains available
- custom role overrides still work

**Verification:** role catalog tests, forced-rule tests, prompt/output-contract tests, backward compatibility tests.

## Phase 8 — intelligent team selection

**Goal:** choose role teams from objective evidence.

**Behavior:**

- selection uses task signals such as research, implementation, review, security, data, docs, testing, and operations
- team choices are inspectable through `/team`
- explicit roles always override automatic selection
- existing objective heuristic remains a safe fallback
- selected teams respect `orchestrator.max_children` and tool/security rules

**Verification:** representative objective-to-team tests, explicit-role override tests, cap tests.

## Phase 9 — provider intelligence

**Goal:** add advisory provider/model selection without changing provider contracts.

**Behavior:**

- suggestions consider locality, configured credentials, cost annotations, and capability notes
- paid providers are clearly labelled and confirmation rules remain unchanged
- mock/local providers stay deterministic for tests
- no provider key is printed, logged, or inferred from lookalike hostnames

**Verification:** provider suggestion tests with fabricated config keys; secret-redaction tests.

## Phase 10 — memory and skill intelligence

**Goal:** improve context quality without breaking existing files.

**Behavior:**

- bounded memory retrieval selects relevant entries with explicit limits
- existing `MEMORY.md` and `USER.md` formats remain valid
- skills gain stronger validation/version handling
- built-in skills remain read-only
- child agents still cannot mutate skills

**Verification:** retrieval relevance/limit tests, skill compatibility tests, validation tests, child restriction tests.

## Phase 11 — terminal integration and single-writer output

**Goal:** unify visual output so animations, streams, tool lines, and graphs never corrupt each other.

**Behavior:**

- one renderer owns terminal writes for interactive sessions
- streaming deltas, status events, graph updates, and prompts serialize safely
- spinner/title/graph animation stops cleanly on completion, error, and cancellation
- non-interactive `run` output remains script-friendly

**Verification:** fake-writer concurrency tests, cancellation tests, TTY/non-TTY behavior tests.

## Phase 12 — tests and CI

**Goal:** make 0.2.0 repeatably verifiable.

**Behavior:**

- all new modules have deterministic stdlib `unittest` coverage
- `bash scripts/check.sh` includes any required new static checks
- GitHub Actions runs compile, full tests, smoke/doctor checks, secret scan, and Markdown link check
- CI does not require paid providers or network model calls

**Verification:** local full checks plus real CI results. Wait for CI and fix failures before release.

## Phase 13 — documentation and assets

**Goal:** update the public project surface to match shipped behavior.

**Required updates:**

- `README.md` with 0.2.0 identity, commands, screenshots, and safety notes
- `CHANGELOG.md` with an accurate `0.2.0` section
- `docs/PROVIDERS.md`, `docs/CONFIGURATION.md`, `docs/FEATURE_MATRIX.md`, `docs/RELEASE_CHECKS.md`
- new/updated ASCII screenshots generated from real local runs
- `assets/logo.svg` and `assets/banner.svg` aligned with the purple-neon palette
- no fabricated terminal captures or benchmark numbers

**Verification:** link checks, smoke checks, screenshot provenance notes, full checks.

## Phase 14 — release candidate hardening

**Goal:** freeze behavior and verify release quality.

**Behavior:**

- version becomes `0.2.0` in package metadata and runtime
- fresh install/uninstall works from a local clone
- full tests, checks, benchmark, and install script pass
- CI passes on the release branch
- no secrets, tokens, `.env` files, or generated credentials are committed
- release notes describe only implemented behavior

**Verification:**

- `python3 -m unittest discover -s tests -q`
- `bash scripts/check.sh`
- `bash scripts/test_install.sh`
- real CI run
- `git diff --check`

## Phase 15 — release

**Goal:** publish `v0.2.0`.

**Required actions:**

- open PR against `main`
- wait for real CI results and fix failures
- merge only after checks pass
- tag `v0.2.0`
- publish a GitHub release with accurate notes, screenshots, and installation instructions
- if permissions or CI prevent completion, report the exact state and remaining commands

**Exit state:** `AETHER v0.2.0` released without claiming `v1.0.0` or any unimplemented parity.
