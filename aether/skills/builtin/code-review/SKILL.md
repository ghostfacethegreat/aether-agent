---
name: code-review
description: Review changed code for correctness, safety, and maintainability.
version: 1.0
---

# Code review

1. Identify the intended behavior from the request and surrounding code.
2. Read the full changed files before commenting; never review from a diff alone if files are available.
3. Report findings in priority order: correctness, security, performance, maintainability.
4. For each finding include file, line, why it matters, and a concrete fix.
5. If no issues are found, say so explicitly and list what was checked.
6. Do not make unrelated refactors unless asked.
