# Aether 0.2+ Roadmap

This roadmap tracks the additive upgrade from the verified `0.1.0` baseline at commit `01ee003` to the intelligence-first `Aether 0.2+` program. Baseline facts are in [AETHER_02_BASELINE.md](AETHER_02_BASELINE.md); extension points are in [AETHER_02_ARCHITECTURE.md](AETHER_02_ARCHITECTURE.md).

The earlier visual-first phase list is archived below for provenance. It is superseded by [INTELLIGENCE_ROADMAP.md](INTELLIGENCE_ROADMAP.md). Current work improves reasoning, memory, learning, routing, coding, research, coordination, verification, recovery, and measured task success. Terminal appearance is frozen: preserve the existing ASCII artwork and colored rendering, fix functional visual regressions only, and do not add themes, a theme selector, font tooling, animations, or a renderer rewrite without a demonstrated functional or performance bug.

## Milestone contract

Every milestone must end with:

1. a concise report of changed files
2. observable behavior added or changed
3. focused tests actually run
4. fixes for any failures found
5. documentation updates
6. benchmark impact, if any
7. a working checkpoint commit

Do not mark a milestone complete based only on code inspection. Do not fabricate screenshots, benchmark results, CI results, or provider behavior.

## Current phase map

| Phase | Name | Status |
|---|---|---|
| Phase 0 | Baseline and source-of-truth docs | complete |
| Phase A | Intelligence audit, Hermes comparison, benchmark contract | current documentation checkpoint |
| Phase B | Adaptive planning and execution state | pending |
| Phase C | Layered memory | pending |
| Phase D | Learning loop and skill quality | pending |
| Phase E | Model capability routing | pending |
| Phase F | Coding workflow | pending |
| Phase G | Research and evidence | pending |
| Phase H | Tool intelligence | pending |
| Phase I | Specialist orchestration | pending |
| Phase J | Verification and recovery | pending |
| Phase K | Benchmark harness | pending |
| Phase L | Release hardening | pending |

Full scope, likely files, behaviors, verification, and exit states for Phases B-L are in [INTELLIGENCE_ROADMAP.md](INTELLIGENCE_ROADMAP.md). Benchmark protocol details are in [benchmarks/README.md](../benchmarks/README.md).

## Phase 0 — baseline and design

**Status:** complete.

**Goal:** establish a verified source of truth before behavior changes.

**Scope:**

- fetch and base work on `origin/main`
- create `feat/aether-02-neon-agent-platform`
- verify version, packaging, dependencies, tests, checks, benchmarks, CLI surface, providers, tools, memory, skills, orchestration, scheduler, and CI state
- add the initial 0.2 planning documents
- commit the documentation-only checkpoint

**Verification completed:**

- `git status --short --branch`
- `python3 -m unittest discover -s tests -q`
- `bash scripts/check.sh`
- `bash scripts/test_install.sh`
- `git diff --check`

**Exit state:** baseline docs committed at `558bd58`; no runtime behavior changed in this phase.

## Phase A — intelligence audit and benchmark contract

**Goal:** replace guesses with source-evidenced intelligence priorities before runtime changes.

**Scope:**

- audit Aether at `558bd58ec1f15ccf9cf76260d3ab7bfe675e76ce`
- compare Hermes at pinned commit `b98c388a880b1b6fd303c9c2821a3946651a0b4c` and current `main` at `fe9a4b58ec137d3e00719c10e2385876fa03b97c`
- add the intelligence audit, roadmap, comparison, and benchmark protocol
- supersede visual-first 0.2 plans
- freeze terminal appearance and preserve existing ASCII artwork

**Verification:** full local checks and Markdown link checks; no runtime behavior changed.

**Exit state:** Phase A documentation checkpoint committed after checks pass.

## Archived visual-first milestones

The following phases were written before the user changed the priority to intelligence first. They are retained as historical provenance only and must not be executed as current roadmap items.

### Archived Phase 1 — visual identity foundation

Originally proposed a purple-neon palette and safe ANSI engine. Superseded by the visual freeze; only functional renderer bugs and untrusted-text sanitization are in scope.

### Archived Phase 2 — ASCII font registry

Originally proposed at least 12 offline ASCII fonts, font selection, and persistence. Superseded; no font system should be added.

### Archived Phase 3 — ASCII art and animated title

Originally proposed generated ASCII art and an animated title sequence. Superseded; existing ASCII artwork must be preserved, not replaced or animated.

### Archived Phase 4 — new CLI command surface

Originally proposed `aether fonts`, `aether font *`, `/font *`, and `/art` commands. Superseded; do not add font/art commands.

### Archived Phase 5 — interactive dashboard

Originally proposed a purple-neon dashboard redesign. Superseded; dashboard changes are limited to functional correctness and readability regressions.

### Archived Phase 6 — dynamic agent graph

Originally proposed a visual graph UI. Intelligence work may expose real plan/task state, but appearance changes are out of scope.

### Archived Phase 7 — specialist role catalog

Still relevant as intelligence work. Current version: Phase I in [INTELLIGENCE_ROADMAP.md](INTELLIGENCE_ROADMAP.md); expand to at least 18 meaningful roles with real work, contracts, and forced-rule enforcement.

### Archived Phase 8 — intelligent team selection

Still relevant as intelligence work. Current version: Phase I; choose roles from objective evidence, keep explicit roles authoritative, and expose inspectable rationale.

### Archived Phase 9 — provider intelligence

Still relevant as intelligence work. Current version: Phase E; add capability-aware routing without changing provider contracts or weakening cost controls.

### Archived Phase 10 — memory and skill intelligence

Still relevant as intelligence work. Current versions: Phases C and D; add layered memory, retrieval, skill evidence, versioning, and curation.

### Archived Phase 11 — terminal integration and single-writer output

Visual/animation details are superseded. Functional output correctness, sanitization, and cancellation-safe writes remain valid only when fixing a demonstrated bug.

### Archived Phase 12 — tests and CI

Still relevant. Current version: Phase L; add deterministic tests and CI after benchmark and runtime work stabilizes.

### Archived Phase 13 — documentation and assets

Still relevant for docs; visual asset redesign is superseded. Current version: Phase L; update docs to describe implemented intelligence behavior only.

### Archived Phase 14 — release candidate hardening

Still relevant. Current version: Phase L.

### Archived Phase 15 — release

Still relevant after all verification. Do not push, merge, tag, or publish until checks, reports, and benchmark claims are accurate.
