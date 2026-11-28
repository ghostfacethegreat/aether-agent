# Project context files

AETHER reads selected workspace-root guidance files at the start of each user turn. This is a prompt-context feature, not code execution.

Supported defaults: `AGENTS.md`, `AETHER.md`, `.aether.md`, `CLAUDE.md`, `SOUL.md`, `.cursorrules`, and `.hermes.md`.

Security properties:
- Reads only direct children of the resolved workspace root.
- Does not recurse, search parent directories, follow symlinks, or use the network.
- Skips binary, oversized, unreadable, and invalid UTF-8 files.
- Enforces maximum file count, bytes per file, and aggregate characters.
- Injects the text as lower-priority context, never as a replacement for system policy or current user intent.

Project-context files can still contain prompt injection. The model is instructed to treat them as repository guidance and ignore requests to bypass approvals, reveal credentials, change permissions, or override the user. This is a prompt-level defense, not an OS sandbox.
