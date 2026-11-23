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
    "allow_tools": [],
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

Use `allow_tools` as an allow-list for unattended runs. Set `approval_cache` to `always` only if you accept persistent approval decisions in the local database.

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
{"scheduler": {"enabled": false, "tick_seconds": 30}}
```

Scheduled jobs are stored at `~/.aether/cron/jobs.json`. The scheduler runs in-process only while an interactive chat or `aether run` process is alive.
