---
name: aether-orchestration
description: Improve AETHER planning, specialist delegation, structured task contracts, verification, cancellation, recovery, and durable execution.
---

Work only on AETHER orchestration and execution-state concerns. Inspect `aether/orchestration/`, `aether/core/agent.py`, persistence APIs, and their tests first.

Goals:
- Strengthen dependency-aware specialist selection and output contracts.
- Preserve shared spend budgets, strict child permission intersections, explicit approvals, cancellation, timeouts, retry safety, and persistent resume.
- Add independent verification based on actual test/check tool records, never model assertions.
- Add deterministic tests for completion, partial failure, cancellation races, timeout, restart/resume, and role restrictions.

Do not weaken safety rules, add hidden paid-provider fallbacks, mutate persistent skills from child agents, or claim complete autonomy. Keep changes within orchestration, agent coordination, persistence when needed, and related tests/docs.
