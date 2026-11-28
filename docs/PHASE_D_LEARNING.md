# Phase D — Evidence-Based Learning

Phase D adds a local evidence pipeline that turns repeated, verified outcomes into reviewable skill proposals. It is additive: existing `SKILL.md` skills, Markdown memory, SQLite state, tools, permissions, approvals, and the frozen terminal appearance remain valid.

The core rule is simple: an agent's own completion claim is not evidence. Only deterministic checks, checks runner results, explicit user feedback, or equivalent recorded verification can promote an experience into a candidate skill.

## Checkpoint

| Item | Value |
|---|---|
| Implementation commit | `0dc4118af627cb2c5de4daac0a8ed4e3512705cf` |
| Branch | `feat/aether-020-intelligence-foundation` |
| Base checkpoint | `537b983` |
| Version | `0.1.0` alpha; no release or tag created |
| Publication | no push, pull request, merge, tag, or release |

## Implemented behavior

- Records sanitized experience facts: objective, classification, plan ID, agents, models, tool names/results timings, errors, solution summary, verification metadata, feedback, status, session, and confidence.
- Omits raw tool arguments and tool results from learning records; text is redacted and truncated.
- Separates verified outcomes from model claims. A successful tool call or a model saying "done" does not make an experience verified.
- Supports explicit user feedback with `verified`, `failed`, or `neutral` verdicts; user verification can override deterministic evidence.
- Discovers candidate skills only from repeated verified experiences grouped by tool set and objective keywords.
- Writes proposals to SQLite with evidence IDs, fingerprints, source labels, and status.
- Validates proposals for skill structure, known tools, required permissions, secret exposure, prompt-injection patterns, deterministic examples, and improvement regressions.
- Approves and installs only explicitly authorized proposals; rollback also requires explicit authorization unless `learning.allow_auto_approve` is deliberately enabled.
- Stores immutable skill versions, active version status, skill metrics, and learning events.
- Can improve an existing skill by appending corrective procedures derived from execution history, but the improvement remains a proposal until approved.
- Adds bounded, explicitly labeled learning context to prompts. The context is marked as data and must not be followed as instructions.
- Isolates child agents: persistent learning writes are disabled in child agents.

## Storage

Phase D adds these SQLite tables:

- `learning_experiences`
- `learning_proposals`
- `learning_versions`
- `learning_metrics`
- `learning_events`

Existing tables and rows are preserved. The schema is additive and initialized with existence checks.

## Interfaces

Skill learning commands:

```bash
aether skills discover --query "parser tests" --limit 5
aether skills proposals --status proposed --skill parser-tests-terminal-python
aether skills validate <proposal-or-skill>
aether skills approve <proposal> --yes
aether skills reject <proposal> --reason "duplicate"
aether skills history <skill> --query "parser" --limit 20
aether skills versions <skill>
aether skills rollback <skill> <version> --yes
aether skills result <skill> --success --verified --duration-ms 120
```

Learning inspection commands:

```bash
aether learning pending
aether learning metrics <skill>
aether learning feedback verified "The regression check passed" --session <session-id>
```

Interactive commands:

```text
/skills discover [query]
/skills proposals
/skills validate <skill>
/skills history [skill] [query]
/skills versions <skill>
/feedback <verified|failed|neutral> <text>
```

## Configuration

New dotted settings use conservative defaults:

```text
learning.enabled=true
learning.experience_retention=500
learning.min_experiences=2
learning.min_confidence=0.7
learning.require_approval=true
learning.allow_auto_approve=false
learning.max_context_chars=6000
learning.regression_limit=5
```

`learning.require_approval` and `learning.allow_auto_approve` do not grant tools, permissions, or spending authority. Existing tool approval and permission rules still apply.

## Security rules

- Model claims, tool success, web pages, files, and child-agent output remain untrusted data.
- Learning records never store raw tool arguments or raw tool results.
- Secret-like values are redacted before storage or prompt injection.
- Prompt-injection phrases and secret-like strings in proposed skills cause validation failure.
- Proposals cannot self-approve; child agents cannot persist learning records or skills.
- Persistent instruction changes are limited to explicit CLI/tool actions with confirmation by default.
- Rollback restores stored skill content; it does not undo external side effects caused by earlier skill use.

## Verification

Focused deterministic verification:

```text
python3 -W ignore::ResourceWarning -m unittest tests.test_learning -v
Ran 21 tests in 0.554s
OK
```

Full local verification:

```text
python3 -W ignore::ResourceWarning -m unittest discover -s tests -v
Ran 153 tests in 1.849s
OK

bash scripts/check.sh && bash scripts/test_install.sh
all checks passed
local git-remote install test passed

git diff --check
passed
```

Startup benchmark from the combined check/install run: 3 cold starts, `0.109s` median wall time, and `34.1 MiB` peak child RSS. These are startup measurements, not task-quality results. No Aether/Hermes comparison or superiority claim was produced.

## Failures found and fixed

- The learning test setup shadowed the inherited config helper with a `Config` instance; tests now store it as `self.cfg`.
- Proposal test helpers did not seed verified experience; `first_proposal()` now creates two deterministic verified experiences when none exist.
- `record_experience()` did not infer a plan ID from the supplied plan payload; it now uses `plan.id` when no explicit plan ID is given.
- `Agent.run_turn()` referenced a local `usage` value before it was assigned while recording learning experience; it now reads usage from the turn state.
- Approved skills wrote `version: 1` instead of the existing `version: 1.0` convention; approval now writes a dotted version string.

## Current limitations

- Discovery groups verified experiences deterministically; it does not use a model to author new skills.
- Validation runs structural and security checks plus deterministic example records; it is not a sandboxed execution harness.
- There is no independent verifier that executes a proposed skill in an isolated environment.
- Learning context is bounded lexical evidence, not learned ranking or embeddings.
- Skill metrics are local counters, not a task-quality benchmark.
- There is no event-driven or cross-process learning loop.
- No task-quality benchmark harness or result artifact exists for learning performance.

See [INTELLIGENCE_ROADMAP.md](INTELLIGENCE_ROADMAP.md), [RELEASE_CHECKS.md](RELEASE_CHECKS.md), and [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) for phase status and honest gaps.
