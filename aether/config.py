import copy
import os
from pathlib import Path

from aether.errors import ConfigError
from aether.utils import atomic_json_write, parse_bool, read_json

DEFAULTS = {
    "version": 1,
    "provider": "ollama",
    "model": "llama3.2:3b",
    "providers": {},
    "temperature": 0.2,
    "top_p": 1.0,
    "max_tokens": 2048,
    "max_iterations": 12,
    "context_tokens": 8192,
    "compression_threshold": 0.75,
    "reasoning_effort": None,
    "personality": "You are Aether, a precise, pragmatic engineering assistant. Be concise and verify claims.",
    "system_prompt": "",
    "streaming": True,
    "request_timeout": 60,
    "retry_attempts": 2,
    "fallback_providers": [],
    "tool_permissions": {
        "mode": "standard",
        "allow_tools": [],
        "deny_tools": [],
        "allowed_roots": [],
        "require_approval": ["terminal", "write_file", "edit_file", "python", "git", "browser"],
        "allow_destructive": False,
        "approval_cache": "session",
    },
    "tools": {
        "timeout": 30,
        "max_result_chars": 16000,
        "parallel_safe": True,
        "python_enabled": True,
    },
    "memory": {"enabled": True, "char_limit": 4000, "inject_user_profile": True},
    "skills": {"enabled": True, "max_prompt_chars": 3000},
    "costs": {"confirm_paid": True, "max_estimated_usd_per_turn": None},
    "integrations": {
        "web_search": {"provider": "duckduckgo", "api_key_env": "", "base_url": ""},
        "web_fetch": {"max_bytes": 262144},
        "browser": {"command": "", "enabled": False},
    },
    "scheduler": {"enabled": False, "tick_seconds": 30},
    "logging": {"level": "INFO", "file": True},
}


def _deep_merge(base, override):
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_environment(env_file: Path | None = None) -> None:
    from aether.home import env_path

    path = Path(env_file) if env_file else env_path()
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


class Config:
    def __init__(self, data=None, path: Path | None = None):
        self._data = _deep_merge(DEFAULTS, data or {})
        self.path = Path(path) if path else None

    def get(self, dotted: str, default=None):
        node = self._data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, dotted: str, value) -> None:
        parts = dotted.split(".")
        node = self._data
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value

    def update(self, data: dict) -> None:
        self._data = _deep_merge(self._data, data)

    def as_dict(self) -> dict:
        return copy.deepcopy(self._data)

    def save(self) -> None:
        if self.path is None:
            raise ConfigError("Config has no path")
        atomic_json_write(self.path, self._data, mode=0o600)

    def validate(self) -> list[str]:
        warnings = []
        if self.get("provider") not in _KNOWN_PROVIDERS:
            warnings.append(f"Unknown provider '{self.get('provider')}'. Use 'aether providers' to list valid names.")
        mode = self.get("tool_permissions.mode")
        if mode not in {"standard", "strict", "local-dev"}:
            warnings.append(f"Invalid tool_permissions.mode '{mode}'. Expected standard, strict, or local-dev.")
        for key in ("max_iterations", "context_tokens", "request_timeout", "retry_attempts"):
            value = self.get(key)
            if not isinstance(value, int) or value < 0:
                warnings.append(f"{key} must be a non-negative integer.")
        threshold = self.get("compression_threshold")
        if not isinstance(threshold, (int, float)) or not 0.1 <= threshold <= 0.95:
            warnings.append("compression_threshold must be between 0.1 and 0.95.")
        if parse_bool(self.get("costs.confirm_paid"), True) and self.get("costs.max_estimated_usd_per_turn") is None:
            pass
        return warnings


_KNOWN_PROVIDERS = {
    "mock",
    "ollama",
    "lmstudio",
    "llamacpp",
    "custom",
    "openai",
    "anthropic",
    "openrouter",
    "groq",
    "cerebras",
    "huggingface",
    "gemini",
}


def load_config(path: Path | None = None, create: bool = True) -> Config:
    from aether.home import config_path

    target = Path(path) if path else config_path()
    data = read_json(target, {})
    if not isinstance(data, dict):
        raise ConfigError(f"Config at {target} is not a JSON object")
    config = Config(data, target)
    if create and not target.exists():
        config.save()
    return config
