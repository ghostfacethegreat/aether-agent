---
name: aether-integrations
description: Build optional and secure AETHER integrations for browser automation, MCP, messaging, voice, media, and external tools.
---

Work only on optional integration adapters. Inspect the current tool registry, provider interface, config patterns, and permission policy before implementing.

Priority:
1. A safe browser adapter with isolated profiles, URL validation, redirect/DNS protections, explicit action approvals, and deterministic fake-browser tests.
2. MCP client support with user-configured servers, lazy tool discovery, schema validation, timeouts, and per-server permission boundaries.
3. Messaging adapters as optional extras with user/session isolation, webhook signature validation, and explicit account configuration.
4. Local-first voice input/output and media adapters; hosted providers remain optional and billable calls must be visible.

Do not bundle credentials, bypass login controls, start public unauthenticated servers, or make local CLI operation depend on cloud services. Keep integrations behind explicit configuration.
