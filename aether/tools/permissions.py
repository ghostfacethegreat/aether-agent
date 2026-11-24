import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from aether.errors import ApprovalRequired, PermissionDenied
from aether.home import aether_home
from aether.utils import parse_bool

DESTRUCTIVE_PATTERNS = [
    r"\brm\s+(-[a-z]*r[a-z]*f|-[a-z]*f[a-z]*r)\b",
    r"\brm\s+-rf\b",
    r"\bsudo\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bchmod\s+-R\s+777\b",
    r"\bgit\s+push\s+.*--force",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-fdx\b",
    r"\bcurl[^\n|]*\|\s*(ba)?sh\b",
    r"\bshutdown\b",
    r"\bkillall\b",
    r"\blaunchctl\s+(bootout|disable)\b",
]

_SENSITIVE = (".env", ".ssh", "id_rsa", "credentials", "private_key", ".aws/credentials", ".netrc")


@dataclass
class PermissionDecision:
    allowed: bool
    reason: str = ""
    needs_approval: bool = False
    rule_key: str = ""
    risk: str = "low"

    def __bool__(self):
        return self.allowed


def _key(parts) -> str:
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _args_key(tool: str, args: dict) -> str:
    canonical = json.dumps({"tool": tool, "args": args or {}}, sort_keys=True, separators=(",", ":"), default=str)
    return _key([canonical])


def _path_values(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


class PermissionPolicy:
    def __init__(self, config, store=None, workspace=None, approve_callback=None):
        self.config = config
        self.store = store
        self.workspace = Path(workspace or Path.cwd()).resolve()
        self.approve_callback = approve_callback
        self.session_approvals: set[str] = set()
        self.mode = str(config.get("tool_permissions.mode", "standard") or "standard")

    def _roots(self) -> list[Path]:
        roots = [self.workspace, aether_home()]
        for raw in self.config.get("tool_permissions.allowed_roots", []) or []:
            try:
                roots.append(Path(raw).expanduser().resolve())
            except OSError:
                continue
        return roots

    def _is_sensitive(self, path: Path) -> bool:
        lowered = str(path).lower()
        return any(marker in lowered for marker in _SENSITIVE)

    @staticmethod
    def is_destructive(command: str) -> bool:
        text = str(command or "")
        return any(re.search(pattern, text, re.I) for pattern in DESTRUCTIVE_PATTERNS)

    def _single_path_decision(self, tool: str, raw: str, args: dict | None = None) -> PermissionDecision:
        try:
            path = Path(str(raw)).expanduser()
            path = path if path.is_absolute() else (self.workspace / path)
            path = path.resolve()
        except OSError:
            return PermissionDecision(False, "Path could not be resolved", False, _args_key(tool, args or {"path": raw}), "write")
        roots = self._roots()
        inside = any(path == root or root in path.parents for root in roots)
        risk = "write" if tool in ("write_file", "edit_file") else "read"
        if self._is_sensitive(path):
            return PermissionDecision(True, "Sensitive path requires approval", True, _args_key(tool, args or {"path": str(path)}), "sensitive")
        if not inside:
            if self.mode == "strict":
                return PermissionDecision(False, f"Path outside allowed roots: {path}", False, _args_key(tool, args or {"path": str(path)}), risk)
            return PermissionDecision(True, f"Path outside workspace: {path}", True, _args_key(tool, args or {"path": str(path)}), risk)
        return PermissionDecision(True)

    def _path_decision(self, tool: str, args: dict) -> PermissionDecision:
        raw_values = []
        for key in ("path", "file", "cwd"):
            raw_values.extend(_path_values(args.get(key)))
        raw_values.extend(_path_values(args.get("paths")))
        if not raw_values:
            return PermissionDecision(True)
        for raw in raw_values:
            decision = self._single_path_decision(tool, raw, args)
            if not decision.allowed or decision.needs_approval:
                return decision
        return PermissionDecision(True)

    def check(self, tool: str, args: dict, risk: str = "low") -> PermissionDecision:
        denied = set(self.config.get("tool_permissions.deny_tools", []) or [])
        allowed_raw = self.config.get("tool_permissions.allow_tools", None)
        allowed = None if allowed_raw is None else set(allowed_raw or [])
        if tool in denied:
            return PermissionDecision(False, f"Tool '{tool}' is denied by configuration", False, _args_key(tool, args), risk)
        if allowed is not None and tool not in allowed:
            return PermissionDecision(False, f"Tool '{tool}' is not in the configured allow list", False, _args_key(tool, args), risk)

        key = _args_key(tool, args)
        if risk == "destructive" or (tool == "terminal" and self.is_destructive(args.get("command", ""))):
            if self.mode == "strict" and not parse_bool(self.config.get("tool_permissions.allow_destructive"), False):
                return PermissionDecision(False, "Destructive operation denied by strict mode", False, key, "destructive")
            return PermissionDecision(True, "Destructive operation requires approval", True, key, "destructive")

        required = set(self.config.get("tool_permissions.require_approval", []) or [])
        if tool in required:
            return PermissionDecision(True, f"Tool '{tool}' requires approval", True, key, risk)

        path_decision = self._path_decision(tool, args)
        if not path_decision.allowed or path_decision.needs_approval:
            return path_decision

        if risk in ("execute", "network") and self.mode == "strict":
            return PermissionDecision(True, f"Tool '{tool}' requires approval in strict mode", True, key, risk)
        return PermissionDecision(True, risk=risk)

    def _cached(self, rule_key: str) -> str | None:
        if rule_key in self.session_approvals:
            return "once"
        if self.store and self.config.get("tool_permissions.approval_cache") == "always":
            return self.store.get_approval(rule_key)
        return None

    def authorize(self, tool: str, args: dict, risk: str = "low") -> None:
        decision = self.check(tool, args, risk)
        if not decision.allowed:
            raise PermissionDenied(f"Blocked {tool}: {decision.reason}")
        if not decision.needs_approval:
            return
        cached = self._cached(decision.rule_key)
        if cached in ("once", "session", "always"):
            return
        if self.approve_callback is None:
            raise ApprovalRequired(
                f"Approval required for {tool}: {decision.reason}. No interactive approver is available; the action was not executed."
            )
        subject = f"Aether wants to use {tool}"
        answer = str(self.approve_callback(subject, decision.reason, decision.rule_key)).strip().lower()
        if answer not in ("once", "session", "always", "y", "yes", "a", "s"):
            raise PermissionDenied(f"User denied {tool}: {decision.reason}")
        if answer in ("session", "always", "s", "a"):
            self.session_approvals.add(decision.rule_key)
        if answer in ("always", "a") and self.store and self.config.get("tool_permissions.approval_cache") == "always":
            self.store.set_approval(decision.rule_key, "always")

    def grant_session(self, rule_key: str) -> None:
        self.session_approvals.add(rule_key)
