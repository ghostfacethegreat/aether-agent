import threading
from dataclasses import dataclass, field
from pathlib import Path

from aether.config import Config
from aether.core.context import ContextManager
from aether.core.loop import TurnState, new_spend_budget, run_turn_loop
from aether.home import aether_home, state_db_path, workspace_root
from aether.memory import MemoryStore
from aether.orchestration import Orchestrator
from aether.persistence import Store
from aether.providers import ProviderManager
from aether.providers.catalog import provider_spec
from aether.skills import SkillEngine
from aether.tasks import SubagentManager
from aether.tools import PermissionPolicy, ToolExecutor, default_registry
from aether.utils import make_id, truncate

CHILD_TOOLS = ["list_directory", "read_file", "web_fetch", "web_search", "session_search", "skill", "todo"]


@dataclass
class TurnResult:
    text: str
    session_id: str
    provider: str
    model: str
    usage: dict = field(default_factory=dict)
    tool_log: list = field(default_factory=list)
    exit_reason: str = "complete"
    error: str = ""
    messages: list = field(default_factory=list)


class Agent:
    def __init__(
        self,
        config: Config | None = None,
        home: Path | str | None = None,
        provider_name: str | None = None,
        model: str | None = None,
        store: Store | None = None,
        session_id: str | None = None,
        allowed_tools: list[str] | None = None,
        approve_callback=None,
        persist=True,
        enable_subagents=True,
        scheduler=None,
        spend_budget: dict | None = None,
        cancel_event: threading.Event | None = None,
        enable_orchestrator=True,
    ):
        self.home = Path(home or aether_home())
        self.config = config or Config()
        raw_limit = self.config.get("costs.max_estimated_usd_per_turn")
        try:
            budget_limit = None if raw_limit is None else float(raw_limit)
        except (TypeError, ValueError):
            budget_limit = None
        self.spend_budget = spend_budget if spend_budget is not None else new_spend_budget(budget_limit)
        if provider_name:
            self.config.set("provider", provider_name)
        if model:
            self.config.set("model", model)
        self.store = store or Store(state_db_path() if home is None else self.home / "state.db")
        self.persist = persist
        self.workspace = workspace_root()
        self.memory = MemoryStore(self.home, self.config.get("memory.char_limit", 4000))
        self.skills = SkillEngine(self.home, enabled=bool(self.config.get("skills.enabled", True)))
        self.context_manager = ContextManager(self.config)
        self.provider_manager = ProviderManager(self.config)
        self.registry = default_registry(int(self.config.get("tools.max_result_chars", 16000)))
        if allowed_tools is not None:
            self.registry.tools = {name: tool for name, tool in self.registry.tools.items() if name in allowed_tools}
        self.policy = PermissionPolicy(
            self.config,
            store=self.store,
            workspace=self.workspace,
            approve_callback=approve_callback,
        )
        self.executor = ToolExecutor(self.registry, self.policy, parallel=bool(self.config.get("tools.parallel_safe", True)))
        self.scheduler = scheduler
        self.approve_callback = approve_callback
        self.cancel_event = cancel_event or threading.Event()
        self.enable_subagents = enable_subagents
        self.subagents = SubagentManager(self._child_agent, self.store, max_workers=3) if enable_subagents else None
        self.orchestrator = (
            Orchestrator(self, config, store=self.store, cancel_event=self.cancel_event)
            if enable_subagents and enable_orchestrator and bool(self.config.get("orchestrator.enabled", True))
            else None
        )
        self.plan = ""
        self.current_state: TurnState | None = None
        self.session_id = session_id or (self.store.create_session(provider=self.provider_manager.active_name, model=self.provider_manager.model) if persist else make_id("session"))
        self.history = self._load_history()
        self._refresh_executor_context()

    def _load_history(self) -> list[dict]:
        if not self.persist or not self.store.get_session(self.session_id):
            return []
        rows = self.store.get_messages(self.session_id, limit=80)
        result = []
        for row in rows:
            item = {"role": row["role"], "content": row["content"]}
            for key in ("name", "tool_call_id", "tool_calls"):
                if row.get(key):
                    item[key] = row[key]
            if row.get("metadata"):
                item["metadata"] = row["metadata"]
            result.append(item)
        return result

    def _refresh_executor_context(self) -> None:
        self.executor.set_context(
            {
                "config": self.config,
                "store": self.store if self.persist else None,
                "home": self.home,
                "workspace": self.workspace,
                "memory": self.memory,
                "skills": self.skills,
                "policy": self.policy,
                "provider_manager": self.provider_manager,
                "scheduler": self.scheduler,
                "subagents": self.subagents,
                "orchestrator": self.orchestrator,
                "cancel_event": self.cancel_event,
                "session_id": self.session_id,
                "set_plan": self.set_plan,
            }
        )

    def _child_agent(self, parent_context, task):
        child_config = Config(self.config.as_dict())
        child_config.set("provider", self.provider_manager.active_name)
        child_config.set("model", self.provider_manager.model)
        child_config.set("max_iterations", min(4, int(self.config.get("max_iterations", 12))))
        child_config.set("tool_permissions.mode", "strict")
        child_config.set("tool_permissions.allow_tools", CHILD_TOOLS)
        child_config.set("tool_permissions.require_approval", [])
        child = Agent(
            child_config,
            home=self.home,
            store=self.store,
            allowed_tools=CHILD_TOOLS,
            persist=False,
            enable_subagents=False,
            spend_budget=self.spend_budget,
            cancel_event=self.cancel_event,
            approve_callback=self.approve_callback,
        )
        child.policy.workspace = self.workspace
        return child

    def _orchestration_child(self, role_spec: dict, task: dict, parent_context: dict, cancel_event: threading.Event):
        child_config = Config(self.config.as_dict())
        provider = str(role_spec.get("provider") or self.provider_manager.active_name)
        model = str(role_spec.get("model") or self.provider_manager.model)
        child_config.set("provider", provider)
        child_config.set("model", model)
        child_config.set("personality", role_spec.get("system_prompt", ""))
        child_config.set("system_prompt", "")
        child_config.set("max_iterations", int(role_spec.get("max_iterations", 4)))
        parent_allowed = set(self.config.get("tool_permissions.allow_tools", []) or [])
        role_allowed = set(role_spec.get("allowed_tools", CHILD_TOOLS) or [])
        allowed = sorted(role_allowed & parent_allowed) if parent_allowed else sorted(role_allowed)
        allowed = [name for name in allowed if name not in ("orchestrate_task", "delegate_task")]
        denied = set(self.config.get("tool_permissions.deny_tools", []) or [])
        denied.update(role_spec.get("deny_tools", []) or [])
        denied.update(("orchestrate_task", "delegate_task"))
        required = set(self.config.get("tool_permissions.require_approval", []) or [])
        required.update(role_spec.get("require_approval", []) or [])
        child_config.set("tool_permissions.mode", "strict")
        child_config.set("tool_permissions.allow_tools", allowed)
        child_config.set("tool_permissions.deny_tools", sorted(denied))
        child_config.set("tool_permissions.require_approval", sorted(required))
        child_config.set("tool_permissions.allowed_roots", self.config.get("tool_permissions.allowed_roots", []) or [])
        child_config.set("tool_permissions.allow_destructive", False)
        child = Agent(
            child_config,
            home=self.home,
            store=self.store,
            allowed_tools=allowed,
            approve_callback=self.approve_callback,
            persist=False,
            enable_subagents=False,
            enable_orchestrator=False,
            spend_budget=self.spend_budget,
            cancel_event=cancel_event,
        )
        child.policy.workspace = self.workspace
        return child

    def set_plan(self, text: str) -> None:
        self.plan = str(text or "").strip()
        if self.current_state:
            self.current_state.plan = self.plan

    def switch_provider(self, name: str, model: str | None = None):
        if model is None and name != self.provider_manager.active_name:
            spec = provider_spec(name)
            if spec:
                model = spec.default_model
        provider = self.provider_manager.activate(name, model)
        self.config.set("provider", name)
        self.config.set("model", provider.model)
        if self.persist:
            self.store.touch_session(self.session_id)
        return provider

    def switch_model(self, model: str):
        return self.provider_manager.set_model(model)

    def clear_history(self) -> None:
        self.history = []
        self.plan = ""
        if self.persist:
            session = self.store.get_session(self.session_id)
            if session:
                self.store.delete_session(self.session_id)
            self.session_id = self.store.create_session(
                provider=self.provider_manager.active_name,
                model=self.provider_manager.model,
                cwd=str(self.workspace),
            )

    def run_turn(self, user_input: str, on_delta=None, on_status=None) -> TurnResult:
        text = str(user_input or "").strip()
        if not text:
            raise ValueError("User input cannot be empty")
        self._refresh_executor_context()
        if self.cancel_event.is_set():
            return TurnResult(text="Stopped: task was cancelled.", session_id=self.session_id, provider="", model="", exit_reason="cancelled")
        system_prompt = self.context_manager.system_prompt(
            memory_context=self.memory.context() if self.config.get("memory.enabled", True) else "",
            skills_context=self.skills.context(int(self.config.get("skills.max_prompt_chars", 3000))),
            plan=self.plan,
        )
        messages = [{"role": "system", "content": system_prompt}] + [dict(item) for item in self.history]
        user_message = {"role": "user", "content": text}
        messages.append(user_message)
        with self.spend_budget["lock"]:
            start_usage = dict(self.spend_budget["usage"])
        state = TurnState(
            messages=messages,
            system_prompt=system_prompt,
            tools=self.registry.definitions(),
            provider_candidates=self.provider_manager.candidates(),
            provider_manager=self.provider_manager,
            context_manager=self.context_manager,
            executor=self.executor,
            config=self.config,
            session_id=self.session_id,
            max_iterations=int(self.config.get("max_iterations", 12)),
            on_delta=on_delta,
            on_status=on_status,
            new_messages=[user_message],
            plan=self.plan,
            spend_budget=self.spend_budget,
            cancel_event=self.cancel_event,
        )
        self.current_state = state
        run_turn_loop(state)
        with self.spend_budget["lock"]:
            end_usage = dict(self.spend_budget["usage"])
        for key in ("prompt_tokens", "completion_tokens", "estimated_cost", "priced_calls", "unpriced_calls"):
            state.usage[key] = end_usage.get(key, 0) - start_usage.get(key, 0)
        state.usage["cost_known"] = state.usage["priced_calls"] > 0 and state.usage["unpriced_calls"] == 0
        self.plan = state.plan
        self.history = [item for item in state.messages if item.get("role") != "system"][-80:]
        usage = state.usage
        if self.persist and self.store.get_session(self.session_id):
            self.store.append_messages(self.session_id, state.new_messages)
            if len(self.history) == 1:
                self.store.touch_session(self.session_id, title=truncate(text, 60))
            provider_name = str(usage.get("provider") or self.provider_manager.active_name)
            provider_model = str(usage.get("model") or self.provider_manager.model)
            self.store.record_usage(
                self.session_id,
                provider_name,
                provider_model,
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
                usage.get("estimated_cost", 0.0),
                cost_known=bool(usage.get("cost_known")),
                priced_calls=int(usage.get("priced_calls", 0)),
                unpriced_calls=int(usage.get("unpriced_calls", 0)),
            )
        return TurnResult(
            text=state.final_text,
            session_id=self.session_id,
            provider=str(usage.get("provider") or self.provider_manager.active_name),
            model=str(usage.get("model") or self.provider_manager.model),
            usage=state.usage,
            tool_log=state.tool_log,
            exit_reason=state.exit_reason,
            error=str(state.error or ""),
            messages=state.messages,
        )

    def status_summary(self) -> dict:
        active = self.provider_manager.describe_active()
        return {
            "session": self.session_id,
            "provider": active.get("name"),
            "model": active.get("model"),
            "kind": active.get("kind"),
            "cost": active.get("cost"),
            "limits": active.get("limits"),
            "messages": len(self.history),
            "tools": len(self.registry.tools),
            "skills": len(self.skills.list_skills()),
            "memories": len(self.memory.list()) + len(self.memory.list(True)),
            "workspace": str(self.workspace),
            "home": str(self.home),
        }
