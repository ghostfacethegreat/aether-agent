# Contributing

## Development setup

```bash
python3 -m pip install -e '.[dev]'
python3 -m unittest discover -s tests -v
```

Aether targets Python 3.10+ and uses only the standard library at runtime. Avoid adding third-party dependencies unless the feature cannot be implemented safely with the standard library.

## Ground rules

- Never commit keys, `.env` files, real session logs, or private data.
- Do not report a feature as done until a test covers it.
- Keep provider cost and limit language factual; do not imply free models are unlimited.
- Do not claim Aether removes model-provider restrictions.
- Preserve the local-first default and make external services opt-in.
- Use `aether doctor`, `compileall`, and unit tests before opening a PR.

## Code layout

- `aether/core/`: agent orchestration, context fitting, loop phases.
- `aether/providers/`: provider catalog and transports.
- `aether/tools/`: tool definitions, permissions, executor.
- `aether/memory/`: Markdown-backed long-term memory.
- `aether/skills/`: SKILL.md discovery and progressive disclosure.
- `aether/tasks/`: subagents and scheduler.
- `aether/persistence/`: SQLite session/task/usage store.
- `aether/cli/`: command-line interface and rendering.

## Commit style

Use short imperative subjects, for example `providers: add fallback cooldown` or `tests: cover permission denial paths`.
