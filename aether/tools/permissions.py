import hashlib
import inspect
import json
import re
from dataclasses import dataclass
from pathlib import Path

from aether.errors import ApprovalRequired, PermissionDenied
from aether.home import aether_home
from aether.utils import parse_bool, redact, redact_mapping, truncate

APPROVAL_POLICY_VERSION = 2
FORCED_APPROVAL_TOOLS = {
    "terminal",
    "write_file",
    "edit_file",
    "python",
    "git",
    "browser",
    "patch_apply",
    "test_run",
    "delegate_task",
    "orchestrate_task",
}

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
_LAYER_WRITE_OPERATIONS = {"add", "correct", "delete", "clear", "consolidate", "prune", "migrate", "import"}
_MEMORY_WRITE_ACTIONS = {"add", "replace", "delete", "import"}
_SKILL_WRITE_ACTIONS = {"create", "edit", "approve", "reject", "rollback"}
_SCHEDULER_WRITE_ACTIONS = {"add", "remove", "update", "pause", "resume"}
_FRESH_APPROVAL_TOOLS = {"write_file", "edit_file", "patch_apply"}


@dataclass
class PermissionDecision:
    allowed: bool
    reason: str = ""
    needs_approval: bool = False
    rule_key: str = ""
    risk: str = "low"
    fresh: bool = False
    details: dict | None = None

    def __bool__(self):
        return self.allowed


def _key(parts) -> str:
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _args_key(tool: str, args: dict, scope: dict | None = None) -> str:
    payload = {"policy_version": APPROVAL_POLICY_VERSION, "tool": tool, "args": args or {}}
    if scope is not None:
        payload["scope"] = scope
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return _key([canonical])


def _action_label(args: dict | None) -> str:
    values = args or {}
    for key in ("action", "operation", "layer_action", "subcommand"):
        value = str(values.get(key) or "").strip().lower()
        if value:
            return value
    return ""


def _state_changing_action(tool: str, args: dict | None) -> str:
    values = args or {}
    action = str(values.get("action") or "").strip().lower()
    if tool == "memory":
        if action == "layer":
            operation = str(values.get("layer_action") or values.get("operation") or "").strip().lower()
            return operation if operation in _LAYER_WRITE_OPERATIONS else ""
        return action if action in _MEMORY_WRITE_ACTIONS else ""
    if tool == "skill":
        return action if action in _SKILL_WRITE_ACTIONS else ""
    if tool == "scheduler":
        return action if action in _SCHEDULER_WRITE_ACTIONS else ""
    if tool in ("delegate_task", "orchestrate_task"):
        return action or "run"
    return ""


def _path_values(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


class PermissionPolicy:
    def __init__(self, config, store=None, workspace=None, approve_callback=None, home=None):
        self.config = config
        self.store = store
        self.workspace = Path(workspace or Path.cwd()).resolve()
        self.home = Path(home or aether_home()).resolve()
        self.approve_callback = approve_callback
        self.session_approvals: set[str] = set()
        self.mode = str(config.get("tool_permissions.mode", "standard") or "standard")

    def _key_for(self, tool: str, args: dict | None) -> str:
        roots = []
        for raw in self.config.get("tool_permissions.allowed_roots", []) or []:
            try:
                roots.append(str(Path(raw).expanduser().resolve()))
            except OSError:
                continue
        scope = {
            "workspace": str(self.workspace),
            "home": str(self.home),
            "mode": self.mode,
            "allowed_roots": sorted(roots),
        }
        return _args_key(tool, args or {}, scope)

    def clear_session_approvals(self) -> None:
        self.session_approvals.clear()

    def _roots(self) -> list[Path]:
        roots = [self.workspace, self.home]
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
            return PermissionDecision(False, "Path could not be resolved", False, self._key_for(tool, args or {"path": raw}), "write")
        roots = self._roots()
        inside = any(path == root or root in path.parents for root in roots)
        risk = "write" if tool in ("write_file", "edit_file") else "read"
        if self._is_sensitive(path):
            return PermissionDecision(
                True,
                "Sensitive path requires approval",
                True,
                self._key_for(tool, args or {"path": str(path)}),
                "sensitive",
                fresh=True,
            )
        if not inside:
            if self.mode == "strict":
                return PermissionDecision(False, f"Path outside allowed roots: {path}", False, self._key_for(tool, args or {"path": str(path)}), risk)
            return PermissionDecision(
                True,
                f"Path outside workspace: {path}",
                True,
                self._key_for(tool, args or {"path": str(path)}),
                risk,
                fresh=True,
            )
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

    @staticmethod
    def _mutation_approval_reason(tool: str, args: dict) -> str:
        """Require human approval for persistent writes, independent of config overrides."""
        action = str(args.get("action") or "").strip().lower()
        if tool == "patch_apply":
            return "Applying a repository patch changes persistent workspace files"
        if tool == "memory":
            if action in {"add", "replace", "delete", "import"}:
                return f"Memory action '{action}' changes persistent memory"
            if action == "layer":
                operation = str(args.get("layer_action") or args.get("operation") or "list").strip().lower()
                if operation in {"add", "correct", "delete", "clear", "consolidate", "prune", "migrate", "import"}:
                    return f"Layered-memory action '{operation}' changes persistent memory"
        if tool == "skill" and action in {"create", "edit"}:
            return f"Skill action '{action}' changes persistent skills"
        if tool == "scheduler" and action in {"add", "remove"}:
            return f"Scheduler action '{action}' changes persistent scheduled jobs"
        return ""

    def check(self, tool: str, args: dict, risk: str = "low") -> PermissionDecision:
        args = args or {}
        denied = set(self.config.get("tool_permissions.deny_tools", []) or [])
        allowed_raw = self.config.get("tool_permissions.allow_tools", None)
        allowed = None if allowed_raw is None else set(allowed_raw or [])
        key = self._key_for(tool, args)
        if tool in denied:
            return PermissionDecision(False, f"Tool '{tool}' is denied by configuration", False, key, risk)
        if allowed is not None and tool not in allowed:
            return PermissionDecision(False, f"Tool '{tool}' is not in the configured allow list", False, key, risk)

        if risk == "destructive" or (tool == "terminal" and self.is_destructive(args.get("command", ""))):
            if self.mode == "strict" and not parse_bool(self.config.get("tool_permissions.allow_destructive"), False):
                return PermissionDecision(False, "Destructive operation denied by strict mode", False, key, "destructive")
            return PermissionDecision(
                True,
                "Destructive operation requires fresh approval",
                True,
                key,
                "destructive",
                fresh=True,
                details={"action": _action_label(args)},
            )

        path_decision = self._path_decision(tool, args)
        if not path_decision.allowed or path_decision.needs_approval:
            return path_decision

        mutation_reason = self._mutation_approval_reason(tool, args)
        if mutation_reason:
            return PermissionDecision(
                True,
                mutation_reason,
                True,
                key,
                "write",
                fresh=True,
                details={"action": _action_label(args)},
            )

        state_action = _state_changing_action(tool, args)
        if state_action:
            return PermissionDecision(
                True,
                f"Tool '{tool}' action '{state_action}' requires fresh approval",
                True,
                key,
                risk,
                fresh=True,
                details={"action": state_action},
            )

        if tool in _FRESH_APPROVAL_TOOLS:
            return PermissionDecision(
                True,
                f"Tool '{tool}' requires fresh approval",
                True,
                key,
                risk,
                fresh=True,
                details={"action": _action_label(args)},
            )

        required = set(self.config.get("tool_permissions.require_approval", []) or []) | FORCED_APPROVAL_TOOLS
        if tool in required:
            return PermissionDecision(True, f"Tool '{tool}' requires approval", True, key, risk, details={"action": redact(_action_label(args))})

        if risk in ("execute", "network") and self.mode == "strict":
            return PermissionDecision(True, f"Tool '{tool}' requires approval in strict mode", True, key, risk, details={"action": _action_label(args)})
        return PermissionDecision(True, risk=risk)

    def _cached(self, rule_key: str) -> str | None:
        if rule_key in self.session_approvals:
            return "once"
        if self.store and self.config.get("tool_permissions.approval_cache") == "always":
            return self.store.get_approval(rule_key)
        return None

    def _approval_details(self, tool: str, args: dict, decision: PermissionDecision, risk: str) -> dict:
        safe_args = redact_mapping(args or {})
        rendered = {}
        for name, value in safe_args.items():
            text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
            rendered[str(name)] = truncate(text, 240)
        return {
            "tool": tool,
            "action": str(redact((decision.details or {}).get("action") or _action_label(args) or "run")),
            "risk": risk,
            "reason": decision.reason,
            "rule_key": decision.rule_key,
            "fresh": decision.fresh,
            "arguments": rendered,
        }

    def _ask_approver(self, subject: str, reason: str, rule_key: str, details: dict):
        callback = self.approve_callback
        try:
            signature = inspect.signature(callback)
            signature.bind(subject, reason, rule_key, details)
        except (TypeError, ValueError):
            return callback(subject, reason, rule_key)
        return callback(subject, reason, rule_key, details)

    def authorize(self, tool: str, args: dict, risk: str = "low") -> None:
        args = args or {}
        decision = self.check(tool, args, risk)
        if not decision.allowed:
            raise PermissionDenied(f"Blocked {tool}: {decision.reason}")
        if not decision.needs_approval:
            return
        if not decision.fresh:
            cached = self._cached(decision.rule_key)
            if cached in ("once", "session", "always"):
                return
        if self.approve_callback is None:
            raise ApprovalRequired(
                f"Approval required for {tool}: {decision.reason}. No interactive approver is available; the action was not executed."
            )
        subject = f"Aether wants to use {tool}"
        details = self._approval_details(tool, args, decision, risk)
        answer = str(self._ask_approver(subject, decision.reason, decision.rule_key, details)).strip().lower()
        if answer not in ("once", "session", "always", "y", "yes", "a", "s"):
            raise PermissionDenied(f"User denied {tool}: {decision.reason}")
        if decision.fresh:
            return
        if answer in ("session", "always", "s", "a"):
            self.session_approvals.add(decision.rule_key)
        if answer in ("always", "a") and self.store and self.config.get("tool_permissions.approval_cache") == "always":
            self.store.set_approval(decision.rule_key, "always")

    def grant_session(self, rule_key: str) -> None:
        self.session_approvals.add(rule_key)
