# Aether Task Benchmarks

This directory defines the fair-comparison protocol for the intelligence-first `Aether 0.2+` program. No benchmark results are claimed in this checkpoint. The harness and task fixtures are Phase K work in [INTELLIGENCE_ROADMAP.md](../docs/INTELLIGENCE_ROADMAP.md).

The purpose is to measure whether an agent actually completes work under controlled conditions, not to compare branding, animations, hidden reasoning, or unsupported claims.

## Truth rules

- No fabricated results, scores, transcripts, citations, or screenshots.
- Store every run in `results/` with enough evidence to reproduce or audit it.
- Compare under the same conditions. Document any difference that cannot be removed.
- A mock-provider run is a harness test, not a model-quality result.
- A paid-provider run requires the same confirmation and cost controls as normal Aether use.
- Do not publish a comparison as model-neutral if one agent uses a different model, endpoint, toolset, token budget, time limit, or workspace.
- Report failures and regressions with the same detail as successes.

## Controlled inputs

For every compared run, record and hold constant where technically possible:

| Variable | Requirement |
|---|---|
| Model | Same provider and exact model/version; otherwise mark comparison as provider-dependent |
| Model settings | Same temperature, top-p, max tokens, reasoning effort, and system overrides where exposed |
| Prompt | Exact task text, including formatting and constraints |
| Workspace | Fresh copy of the same fixture files with the same paths and permissions |
| Tools | Same tool names, schemas, documenters, timeouts, and approval modes |
| Memory | Fresh empty home unless the task specifically tests memory |
| Skills | Same installed skills and versions, or none |
| Budget | Same token, time, tool-call, and spend limits |
| Environment | Same OS/Python/hardware class; record measured versions |
| Network | Same allowed/blocked network state; record whether external research is allowed |
| Randomness | Fixed seed where the system exposes one; otherwise repeat trials and record variance |
| Trials | At least three trials for small tasks; more for nondeterministic tasks |

## Categories

Task specs in `tasks/` should cover:

1. reasoning — multi-step logic, constraint satisfaction, and decision quality
2. coding — implement a small feature in a fixture repository
3. debugging — locate and repair a seeded failure
4. research — answer from controlled local source documents with citations
5. long-context retrieval — find and combine facts from a large fixture
6. persistent memory — recall facts across simulated sessions
7. tool calling — select and invoke tools with correct arguments
8. multi-step execution — complete a dependency chain without losing state
9. error recovery — recover from a failed tool, provider error, or invalid result
10. self-improvement — reuse a learned procedure without accepting unverified claims
11. multi-agent — coordinate independent subtasks and verify the combined result
12. cost and efficiency — complete the task within a declared budget

## Scoring

Each task spec should define deterministic checks where possible and rubric checks where necessary. Report raw metrics alongside normalized scores.

Recommended metrics:

- task success: all required checks passed
- correctness: unit/integration checks, exact answers, or fact checks passed
- completeness: required artifacts, files, and constraints present
- evidence quality: citations, source traceability, and contradiction handling
- safety: approvals honored, secrets protected, denied tools not used
- tool quality: correct tool selection, invalid calls, failed calls, safe retries
- recovery: errors detected, explained, and repaired without repeating non-idempotent work
- memory: correct recall, no stale/conflicting promotion, deletions honored
- cost: tokens, estimated/real cost, tool calls, wall-clock time
- stability: variance across trials and crashes/timeouts

Keep scoring transparent. Do not reduce a run to a single number without publishing the component metrics and the rubric.

## Task spec format

Each task should be a JSON or Markdown file under `tasks/` with:

- `id` — stable identifier
- `category` — one of the listed categories
- `objective` — exact text given to the agent
- `fixture` — input files or generator reference
- `setup` — commands/config needed to prepare the workspace
- `allowed_tools` — tool names available to the agent
- `limits` — time, token, spend, and tool-call limits
- `memory_state` — empty or seeded state
- `skills_state` — empty or seeded skills
- `checks` — deterministic validators
- `rubric` — human/model-review criteria where deterministic checks are insufficient
- `expected_artifacts` — files, answers, or citations required
- `provenance` — where the task came from and why it is included

## Running a benchmark

Phase K should add a runner that executes:

```bash
python3 -m benchmarks.runner --task <task-id> --agent aether --config <config>
python3 -m benchmarks.runner --task <task-id> --agent hermes --config <config>
python3 -m benchmarks.runner --compare <run-a> <run-b> --output benchmarks/results/<study-id>.json
```

These commands are the intended interface, not implemented behavior in Phase A.

## Result storage

Use `results/README.md` for the result schema and naming rules. Every study should include the task spec hash, raw run records, environment metadata, scoring output, and a short interpretation section that states limitations.

## Current state

- `tasks/` contains the task-authoring guide only in this checkpoint.
- `results/` contains no result data in this checkpoint.
- The only currently measured local performance numbers are startup/memory numbers in [docs/RELEASE_CHECKS.md](../docs/RELEASE_CHECKS.md); they are not task-quality benchmarks.
