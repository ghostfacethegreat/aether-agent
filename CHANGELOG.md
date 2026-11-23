# Changelog

## Phase 2 audit (documentation checkpoint)

- Refreshed the Hermes Agent comparison baseline to commit `b98c388a880b1b6fd303c9c2821a3946651a0b4c`.
- Added a source-evidenced comparison of all 14 requested capability areas against Aether commit `bdbe2462dda3c4646086385d600b4e2ab23f4957`.
- Added a ranked gap register and staged milestone plan with separate commit boundaries.
- Corrected feature-matrix entries that overstated tool replay reliability, subagent durability, session recovery, and skill curation completeness.
- Published the repository at <https://github.com/ghostfacethegreat/aether-agent>; no hosted installer URL was published.

## Phase 2 Milestone 2.1

- Preserved tool-call names, IDs, and arguments across SQLite persistence and session resume.
- Added context repair for orphaned tool results and missing tool-result placeholders after compression.
- Fixed Anthropic replay conversion for nested OpenAI-style tool call fields.
- Added regression tests for store round trip, resume history, context repair, and Anthropic tool-call replay.

## 0.1.0 (unreleased alpha)

- Audited public Hermes Agent architecture and provider/security patterns.
- Added provider-agnostic core with OpenAI-compatible, Anthropic, and mock transports.
- Added SQLite session/task/usage persistence.
- Added Markdown-backed memory and `SKILL.md` skills.
- Added tool registry, permission policy, approvals, and tool executor.
- Added context budgeting, prompt assembly, phase-oriented turn loop, and provider fallback.
- Added subagents and in-process scheduler.
- Added CLI with interactive chat, slash commands, setup, providers, config, doctor, sessions, memory, skills, tasks, schedule, run, update, and version commands.
- Added standard-library-only packaging and tests.
