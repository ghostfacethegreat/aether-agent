# Benchmark Results

This directory will hold raw and summarized task-quality benchmark evidence. No results are stored here. The Phase E routing runner prints JSON to stdout and intentionally writes no result artifact; its deterministic fixture eligibility is not task-quality evidence.

## Naming

Use one study directory per comparison:

```text
results/<date>-<study-id>/
  study.json
  runs/
    <agent>-<trial>.json
  artifacts/
  summary.md
```

Use UTC dates in `YYYY-MM-DD` form and immutable study IDs. Do not overwrite an existing study after publishing it; create a new study ID and reference the old one.

## Study schema

`study.json` should include:

- `study_id`
- `created_at`
- `task_id` and task spec hash
- `protocol_version`
- `agents` and exact versions/SHAs
- exact provider, model, endpoint, and settings for each agent
- workspace and environment metadata
- tool availability and approval mode
- network state
- budgets and limits
- trial count and seeds
- scoring rubric version
- paths to raw run files

## Run schema

Each run file should include:

- `run_id`, `trial`, `agent`, and agent SHA
- exact prompt and task spec hash
- start/end timestamps
- exit reason and crash/timeout status
- token usage and real/estimated cost
- tool calls, arguments, results summaries, failures, and approvals
- produced files and their hashes
- verification checks and scores
- raw transcript or a content hash plus storage path
- notes about deviations from the protocol

## Interpretation

`summary.md` must state:

- which conditions were identical
- which conditions could not be equalized
- raw metric table
- observed failures
- whether the result supports any claim
- what the result does not prove

A benchmark result does not prove general superiority, hidden reasoning quality, safety, or future performance. Keep claims limited to the tested tasks and conditions.
