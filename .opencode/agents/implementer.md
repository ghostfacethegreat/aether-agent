---
description: Implements one approved AETHER work package with scoped edits and local verification.
mode: subagent
steps: 24
permissions:
  - action: edit
    resource: "*"
    effect: ask
  - action: edit
    resource: "aether/**"
    effect: allow
  - action: edit
    resource: "tests/**"
    effect: allow
  - action: edit
    resource: "docs/**"
    effect: allow
  - action: edit
    resource: "README.md"
    effect: allow
  - action: shell
    resource: "*"
    effect: ask
  - action: shell
    resource: "git status *"
    effect: allow
  - action: shell
    resource: "git diff *"
    effect: allow
  - action: shell
    resource: "python3 -m compileall *"
    effect: allow
  - action: shell
    resource: "python3 -m unittest *"
    effect: allow
  - action: shell
    resource: "bash scripts/check.sh"
    effect: allow
  - action: shell
    resource: "git push *"
    effect: deny
  - action: shell
    resource: "git tag *"
    effect: deny
  - action: shell
    resource: "gh pr merge *"
    effect: deny
---

Implement only the specific task and files assigned by the lead. Read the existing implementation and adjacent tests first. Preserve current public interfaces, SQLite compatibility, explicit approval boundaries, budgets, cancellation, and cross-platform behavior. Add focused regression tests. Do not silently broaden scope or reformat unrelated code. Run allowed checks and report exact results, including failures. Do not commit, push, merge, tag, publish, or modify repository settings.
