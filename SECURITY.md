# Security

## Reporting

Do not open a public issue for a suspected credential leak or a reproducible remote exploit. Use the repository's private security reporting channel if available; otherwise contact the maintainers directly.

## Threat model

Aether runs on your machine with your permissions. It is a tool runtime, not a sandbox. Prompts, files, web pages, and tool output can contain adversarial instructions. Aether treats all such content as data, but the model can still make mistakes.

The 0.2+ intelligence work expands the trust boundary. Plans, memories, learned procedures, skill versions, research notes, routing explanations, delegated reports, and benchmark fixtures are data, not trusted instructions. Untrusted content must not be able to write trusted memory, change persistent instructions, mutate approved skills, approve its own actions, raise budgets, select a different model, or mark work complete without evidence. Learning may only promote a procedure from observed tests, tool results, or explicit user confirmation. Hidden reasoning is not evidence.

## Protections in 0.1.0

- Secret redaction in logs, CLI error output, and model-facing tool results.
- Config and `.env` files are excluded from git by `.gitignore`.
- Destructive shell pattern detection, including `rm -rf`, `sudo`, `mkfs`, forced git pushes, and pipe-to-shell.
- Approval prompts for configured risky tools. Forced approval is enforced at the `PermissionPolicy` layer; action-aware mutators require fresh approval. Approval keys bind exact args, workspace/home, mode, roots, policy version 2; `session`/`always` are treated as `once` for fresh actions.
- Strict mode denies destructive operations and paths outside allowed roots.
- Sensitive path markers such as `.env`, `.ssh`, credentials, and private keys require approval.
- Memory and skills are local Markdown files with no remote sync. Memory/skills prompt context is explicitly data-only; prompt-injection labels mark untrusted content.
- Built-in skills are filtered for a small set of injection-like patterns.
- Web fetch rejects non-HTTP(S) URLs, embedded credentials, private-network targets, and unsafe redirects.
- Tool execution enforces per-tool wall-clock timeouts.
- Terminal working directories, git paths, and other explicit path arguments are checked against allowed roots.
- Scheduled runs are read-only and use context-local paid confirmation, not process env mutation.
- Streamed model output is sanitized for terminal control sequences.
- `state.db` is created with mode `0600` and home dirs with mode `0700`.

## Limitations

- Python and shell tools can execute arbitrary code with user privileges.
- Web fetch validates hostnames and resolved addresses before connecting, but DNS rebinding and all web-content injection are outside its guarantees.
- Browser automation is only as safe as the command template you configure.
- Approval caching can persist decisions in the local database for non-fresh actions; fresh-action approvals are not reused.
- Free-tier provider limits and model IDs can change without notice.
- Aether does not bypass model-provider restrictions or terms of service.
- Layered memory, automated learning, and Phase E model routing are implemented on this feature branch and locally verified, but not released; their controls must continue to be tested before release.
- Routing selects only among configured candidates, respects explicit `--provider`/`--model` or constructor overrides, cannot grant tools or raise budgets, and never calls a model in its diagnostic commands.
- Routing capability and price facts are evidence-labeled; unknown pricing is not free, and health is local failure state, not live polling.
- The `aether models benchmark` command is an offline deterministic routing simulation: no model, network, or billable calls, no file writes. `--confirm-billable` is acknowledgement only.
- No task-quality benchmark results exist; the routing simulation and startup/memory numbers do not support security, Hermes parity, or superiority conclusions.
- Cancellation is covered by deterministic unit tests in the 274-test suite, not by a live long-running cancellation demonstration.
- No third-party security audit has been performed. No lint/typecheck command is configured, so no lint/typecheck result is claimed.

## Safe unattended use

Use strict mode with an explicit tool allow-list, a non-sensitive workspace, a local provider, and no write/execute tools:

```bash
aether config set tool_permissions.mode strict
aether config set tool_permissions.allow_tools '["list_directory", "read_file", "session_search", "web_fetch", "web_search", "todo"]'
aether --provider ollama --model llama3.2:3b run "Review the README"
```
