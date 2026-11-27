import json
import os
import re
import secrets
import shlex
import tempfile
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

_SECRET_KEY = re.compile(r"(api[_-]?key|token|secret|password|authorization|cookie)", re.I)
_CHECK_MODULE = re.compile(r"^test_[A-Za-z0-9_]{1,100}$")
_PYTHON = re.compile(r"^python(?:\d(?:\.\d+)?)?(?:\.exe)?$", re.I)
_confirm_paid_override: ContextVar[str | None] = ContextVar("aether_confirm_paid_override", default=None)


@contextmanager
def confirm_paid_override(value):
    token = _confirm_paid_override.set(str(value))
    try:
        yield
    finally:
        _confirm_paid_override.reset(token)


def paid_confirmation_value() -> str | None:
    value = _confirm_paid_override.get()
    return os.environ.get("AETHER_CONFIRM_PAID") if value is None else value


def recognized_check_command(command, trusted_python=None) -> tuple[str, ...]:
    if isinstance(command, (list, tuple)):
        parts = [str(item) for item in command]
    else:
        try:
            parts = shlex.split(str(command or ""))
        except ValueError:
            return ()
    if not parts:
        return ()
    if trusted_python is not None:
        try:
            python_token = Path(parts[0]).resolve() == Path(trusted_python).resolve()
        except (OSError, ValueError):
            python_token = False
    else:
        python_token = bool(_PYTHON.fullmatch(parts[0]))
    if python_token:
        if parts[1:6] == ["-m", "unittest", "discover", "-s", "tests"] and all(part in ("-v", "-q") for part in parts[6:]):
            return ("tests",)
        if len(parts) == 4 and parts[1:3] == ["-m", "unittest"]:
            module = parts[3]
            if module.startswith("tests.") and _CHECK_MODULE.fullmatch(module.split(".", 1)[1]):
                return ("tests",)
        if parts[1:] == ["-m", "compileall", "-q", "aether", "tests"]:
            return ("verification",)
    if parts == ["bash", "scripts/check.sh"]:
        return ("check",)
    if parts == ["aether", "doctor"]:
        return ("verification",)
    return ()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def estimate_tokens(text) -> int:
    if not text:
        return 0
    if isinstance(text, (list, dict)):
        text = json.dumps(text, ensure_ascii=False)
    return max(1, int(len(str(text)) / 4) + 1)


def message_tokens(messages) -> int:
    return sum(estimate_tokens(message.get("content", "")) + 4 for message in messages)


def redact(value) -> str:
    text = str(value)
    for name, secret in os.environ.items():
        if _SECRET_KEY.search(name) and len(secret) >= 8:
            text = text.replace(secret, "[REDACTED]")
    patterns = (
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        r"sk-[A-Za-z0-9_-]{12,}",
        r"Bearer\s+[A-Za-z0-9._\-]+",
        r"gh[pousr]_[A-Za-z0-9]{20,}",
        r"github_pat_[A-Za-z0-9_]{20,}",
        r"AKIA[0-9A-Z]{16}",
        r"AIza[0-9A-Za-z_\-]{30,}",
        r"xox[baprs]-[A-Za-z0-9-]{10,}",
        r"\b([A-Za-z_][A-Za-z0-9_]*(?:api[_-]?key|token|secret|password|authorization|cookie)[A-Za-z0-9_]*)\s*([:=])\s*([\"']?)([^\s\"',}\]]{6,})\3",
    )
    for pattern in patterns:
        text = re.sub(pattern, "[REDACTED]" if "PRIVATE KEY" not in pattern else "[REDACTED]", text, flags=re.I | re.S)
    return text


def _redact_value(value):
    if isinstance(value, dict):
        return redact_mapping(value)
    if isinstance(value, (list, tuple)):
        return [_redact_value(item) for item in value]
    return redact(value)


def redact_mapping(mapping) -> dict:
    result = {}
    for key, value in mapping.items():
        if _SECRET_KEY.search(str(key)):
            result[key] = "[REDACTED]"
        else:
            result[key] = _redact_value(value)
    return result


def atomic_write(path: Path, text: str, mode: int | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        if mode is not None:
            os.chmod(path, mode)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def atomic_json_write(path: Path, data, mode: int | None = None) -> None:
    atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n", mode=mode)


def read_json(path: Path, default=None):
    try:
        with Path(path).open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default


def truncate(text, limit=16000) -> str:
    text = str(text)
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [truncated {len(text) - limit} chars]"


def make_id(prefix="id") -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


def parse_bool(value, default=False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
