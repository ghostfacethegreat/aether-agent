# Security

## Reporting

Do not open a public issue for a suspected credential leak or a reproducible remote exploit. Use the repository's private security reporting channel if available; otherwise contact the maintainers directly.

## Threat model

Aether runs on your machine with your permissions. It is a tool runtime, not a sandbox. Prompts, files, web pages, and tool output can contain adversarial instructions. Aether treats all such content as data, but the model can still make mistakes.

## Protections in 0.1.0

- Secret redaction in logs and CLI error output.
- Config and `.env` files are excluded from git by `.gitignore`.
- Destructive shell pattern detection, including `rm -rf`, `sudo`, `mkfs`, forced git pushes, and pipe-to-shell.
- Approval prompts for configured risky tools.
- Strict mode denies destructive operations and paths outside allowed roots.
- Sensitive path markers such as `.env`, `.ssh`, credentials, and private keys require approval.
- Memory and skills are local Markdown files with no remote sync.
- Built-in skills are filtered for a small set of injection-like patterns.
- Web fetch rejects non-HTTP(S) URLs and embedded credentials.

## Limitations

- Python and shell tools can execute arbitrary code with user privileges.
- Web fetch has no private-network block; avoid pointing it at internal services.
- Browser automation is only as safe as the command template you configure.
- Approval caching can persist decisions in the local database.
- Free-tier provider limits and model IDs can change without notice.
- Aether does not bypass model-provider restrictions or terms of service.

## Safe unattended use

Use strict mode with an explicit tool allow-list, a non-sensitive workspace, a local provider, and no write/execute tools:

```bash
aether config set tool_permissions.mode strict
aether config set tool_permissions.allow_tools '["list_directory", "read_file", "session_search", "web_fetch", "web_search", "todo"]'
aether --provider ollama --model llama3.2:3b run "Review the README"
```
