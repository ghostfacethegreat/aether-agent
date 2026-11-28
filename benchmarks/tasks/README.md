# Benchmark Tasks

This directory will hold versioned task specs for the benchmark protocol in [../README.md](../README.md). Phase A defines the authoring rules only; no task result exists yet.

## File naming

Use lowercase stable IDs:

```text
<category>-<short-name>.json
```

Examples:

```text
coding-seeded-regression.json
memory-cross-session-recall.json
research-contradictory-sources.json
multi-agent-dependent-review.json
```

## Required fields

Every task spec should include:

```json
{
  "id": "coding-seeded-regression",
  "category": "coding",
  "objective": "Exact task text given to the agent.",
  "fixture": "tasks/fixtures/coding-seeded-regression/",
  "setup": [],
  "allowed_tools": [],
  "limits": {
    "time_seconds": 300,
    "max_tokens": 20000,
    "max_spend": 0,
    "max_tool_calls": 50
  },
  "memory_state": "empty",
  "skills_state": "empty",
  "checks": [],
  "rubric": [],
  "expected_artifacts": [],
  "provenance": "Why this task is included."
}
```

## Authoring rules

- A task must test an outcome, not a preferred implementation style.
- Deterministic checks are preferred; any subjective rubric item must be explicit.
- Include failure cases, not only happy paths.
- Do not include secrets, paid tokens, or private data in fixtures.
- Keep fixtures small enough for repeated local runs.
- State whether network access is allowed.
- Version a task by changing its `id`; do not silently rewrite an old task after results exist.
- Store generated fixtures with the task or reference a deterministic generator.

## Required coverage

The task set should cover every category in [../README.md](../README.md): reasoning, coding, debugging, research, long-context retrieval, persistent memory, tool calling, multi-step execution, error recovery, self-improvement, multi-agent work, and cost/efficiency.

For fair comparisons, each task must be runnable against both Aether and Hermes with the same prompt, fixture, tool policy, and limits. If a capability is unavailable in one agent, record that as a task-level compatibility result rather than quietly changing the task.
