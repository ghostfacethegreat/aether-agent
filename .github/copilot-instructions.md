# Copilot instructions for AETHER

Read `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/KNOWN_LIMITATIONS.md`, and the relevant phase documents before editing.

Preserve the lightweight Python core and local-first, provider-agnostic model. Ordinary local operation must not require a paid API key. Use the mock provider for tests. Keep approval, permission, secret-redaction, parent/child budget, cancellation, and prompt-injection boundaries intact.

For orchestration changes, add deterministic tests for dependency order, cancellation, timeouts, retries, resume, and permission inheritance. Never mark a task verified from a model claim; require concrete tool evidence. For integrations, keep each provider optional and isolate credentials. Do not make local CLI startup depend on a cloud service.

Do not merge, tag, release, or change the package version. Report exact tests run, failures, and remaining limitations.
