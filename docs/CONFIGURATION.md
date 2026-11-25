# Configuration

Aether stores config at `~/.aether/config.json`. Override the location with `AETHER_HOME` or `--config`.

## Common settings

```json
{
  "provider": "ollama",
  "model": "llama3.2:3b",
  "fallback_providers": [],
  "temperature": 0.2,
  "max_tokens": 2048,
  "max_iterations": 12,
  "context_tokens": 8192,
  "compression_threshold": 0.75,
  "personality": "You are Aether, a precise, pragmatic engineering assistant. Be concise and verify claims.",
  "streaming": true,
  "request_timeout": 60,
  "retry_attempts": 2
}
```

Use `aether config get <dotted.key>`, `aether config set <dotted.key> <json-or-string>`, and `aether config list`.

## Model routing

Routing is additive and reads only configured candidates: the active provider/model, configured fallbacks, role pins, and `models.metadata` entries that match configured providers. The recognized keys are exactly:

```json
{
  "routing": {
    "enabled": true,
    "explain": true,
    "strategy": "capability",
    "prefer_local": true,
    "strict_capabilities": false,
    "context_safety_margin": 0.1,
    "max_candidates": 5,
    "learned_min_samples": 3,
    "learned_weight": 12.0,
    "role": "",
    "avoid_models": [],
    "default_role_spend_share": 0.25,
    "category_keywords": {},
    "overrides": {},
    "roles": {}
  },
  "models": {
    "metadata": {
      "ollama/qwen2.5-coder:7b": {
        "context_window": 32768,
        "capabilities": {"coding": true, "tool_calling": true},
        "evidence": {"context_window": "provider-reported", "coding": "provider-reported"},
        "source": "user config",
        "freshness": "2026-11-24"
      }
    }
  }
}
```

`strategy` is `capability`, `cost`, or `fixed`. `strict_capabilities=true` rejects models with unknown required capabilities instead of penalizing them; the default rejects known-false capabilities and insufficient verified context windows. `learned_min_samples` and `learned_weight` control verified performance history. `default_role_spend_share` applies to child roles per turn and does not raise the shared budget limit. `avoid_models`, `category_keywords`, `overrides`, and `roles` refine selection; role metadata is described in [PROVIDERS.md](PROVIDERS.md) and user-facing behavior in [MODEL_ROUTING.md](MODEL_ROUTING.md).

There is no `routing.manual` key. CLI `--provider`/`--model` and `Agent(provider_name=..., model=...)` are authoritative as `TaskRequirements.explicit_provider`/`explicit_model`. Inspect decisions without model calls:

```bash
aether models list
aether models inspect PROVIDER [MODEL]
aether models capabilities PROVIDER [MODEL]
aether models routing "TASK TEXT"
aether models explain "TASK TEXT"
aether models performance
aether models health
aether models benchmark [--samples N] [--confirm-billable]
```

`aether models benchmark` is an offline deterministic routing simulation that prints JSON, writes no files, and makes no model/network/billable calls; `--confirm-billable` is acknowledgement only.

## Terminal presentation

The terminal renderer is configurable through the `terminal` object:

```json
{
  "terminal": {
    "theme": "acid-blue",
    "unicode": true,
    "show_banner": true,
    "show_dashboard": true,
    "show_response_labels": true
  }
}
```

Themes are `acid-blue`, `classic`, and `mono`. Set `unicode` to `false` for ASCII-only output. The `show_*` settings independently control the startup masthead, session overview, and response labels. The environment variables `NO_COLOR=1` and `AETHER_ASCII=1` provide terminal-level overrides.

## Tool permissions

```json
{
  "tool_permissions": {
    "mode": "standard",
    "allow_tools": null,
    "deny_tools": [],
    "allowed_roots": [],
    "require_approval": ["terminal", "write_file", "edit_file", "python", "git", "browser"],
    "allow_destructive": false,
    "approval_cache": "session"
  }
}
```

Modes:

- `standard`: prompt for configured risky tools; destructive patterns still prompt.
- `strict`: deny destructive operations; require approval for execute/network tools; paths outside allowed roots are denied.
- `local-dev`: intended for trusted local workspaces only.

Use `allow_tools` as an allow-list for unattended runs. `null` means unrestricted; an explicit `[]` denies every tool, including nested agents. Set `approval_cache` to `always` only if you accept persistent approval decisions in the local database. Approval choices are scoped to the exact tool arguments; `once` is not cached, and `session` is cached only for that exact action.

## Memory and skills

```json
{
  "memory": {"enabled": true, "char_limit": 4000, "inject_user_profile": true},
  "skills": {"enabled": true, "max_prompt_chars": 3000}
}
```

Memory files are edited directly at `~/.aether/memories/MEMORY.md` and `USER.md`. Skills are Markdown files at `~/.aether/skills/<name>/SKILL.md`.

## Integrations

```json
{
  "integrations": {
    "web_search": {"provider": "duckduckgo", "api_key_env": "", "base_url": ""},
    "web_fetch": {"max_bytes": 262144},
    "browser": {"command": "", "enabled": false}
  }
}
```

Browser automation is disabled by default. If enabled, the command template receives `{url}` and `{action}` shell-quoted.

## Scheduler

```json
{"scheduler": {"enabled": false, "tick_seconds": 30, "allow_paid": false}}
```

Scheduled jobs are stored at `~/.aether/cron/jobs.json`, and execution outcomes are appended to `~/.aether/cron/executions.jsonl`. The scheduler runs in-process only while an interactive chat or `aether run` process is alive. Manual `aether schedule tick` uses a real local runner and reports due, executed, skipped, and failed jobs. Paid or custom providers are refused for scheduled execution unless `allow_paid` is set to `true`.

## Multi-agent orchestration

```json
{
  "orchestrator": {
    "enabled": true,
    "mode": "parallel",
    "max_concurrency": 3,
    "max_children": 8,
    "max_depth": 2,
    "task_timeout_seconds": 120,
    "retries": 1,
    "allow_paid": false,
    "roles": {
      "researcher": {
        "provider": "",
        "model": "",
        "system_prompt": "",
        "allowed_tools": ["list_directory", "read_file", "web_fetch", "web_search"],
        "deny_tools": [],
        "require_approval": [],
        "max_iterations": 5
      }
    }
  }
}
```

`mode` is `parallel` or `sequential`. Empty `provider` and `model` values inherit the parent agent's active provider and model. Each child inherits the parent's spend budget and cannot raise its limit. Child permissions are the intersection of parent and role allow-lists, plus parent/role deny-lists. Paid providers are blocked for children unless `allow_paid=true`, `AETHER_CONFIRM_PAID` is set, or `costs.confirm_paid=false`.
