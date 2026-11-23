# Release Checks

These are actual locally recorded checks. They are not a claim that a public release exists.

## Environment

- Date: 2026-11-23
- macOS, Python 3.14.2, git 2.37.1
- Aether version 0.1.0 alpha

## Checks performed

- `python3 -m compileall -q aether tests` — passed.
- `python3 -m unittest discover -s tests -v` — 38 tests passed.
- `python3 -c "import tomllib; tomllib.load(open('pyproject.toml','rb'))"` — passed.
- `python3 -c "from aether.cli.app import main"` — passed.
- `AETHER_HOME=<temp> python3 -m aether --provider mock run "Say hello"` — passed, no network.
- `AETHER_HOME=<temp> python3 -m aether providers` — passed.
- `AETHER_HOME=<temp> python3 -m aether doctor` — passed.
- `scripts/check.sh` — passed; includes compile, unit tests, doctor, mock CLI smoke, secret scan, and benchmark.
- `scripts/benchmark.py` — 3 cold starts, median wall time 0.081s, peak child RSS 29.6 MiB.
- `scripts/test_install.sh` — passed by committing the working tree to a temporary git repo, cloning it locally, installing from the clone, running the installed CLI with the mock provider, and verifying uninstall removes the wrapper.
- `aether status` with `--provider mock` — passed; displays `mock (local)` and `mock-standard`.
- Screenshots in `docs/screenshots/` were captured from real local CLI runs with `NO_COLOR=1`; label says mock provider and no network.
- Local Markdown links checked: no broken local targets.

## Tooling not available locally

- `ruff`, `mypy`, and `pyright` were not installed; no lint/typecheck claim is made.
- No third-party runtime dependencies are declared.

## Not yet verified

- Live hosted provider calls were not made.
- Real provider SSE streams were not exercised; the OpenAI-compatible SSE accumulator has an unit test with synthetic chunks.
- No hosted installer URL has been tested.
- No public GitHub release or pushed repository is recorded in this document.

## Secrets

- No `.env` file was created in the repository.
- No API keys were committed.
- `scripts/check.sh` scans source files for common API-key patterns.
