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
