import json
import os
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field

from aether.errors import ApprovalRequired, ConfigError, OrchestratorError, PermissionDenied, ProviderError
from aether.providers.catalog import provider_is_billable
from aether.utils import make_id, redact, truncate, utc_now

from .roles import UNTRUSTED_DATA_NOTICE, resolved_roles
from .state import OrchestrationRun, OrchestrationTask, SharedTaskState, parse_structured_result


@dataclass
class ActiveRun:
    run: OrchestrationRun
    state: SharedTaskState
    cancel_event: threading.Event
    task_events: dict[str, threading.Event] = field(default_factory=dict)
    futures: dict = field(default_factory=dict)
    started: dict[str, float] = field(default_factory=dict)


class Orchestrator:
    def __init__(self, parent, config, store=None, cancel_event=None):
        self.parent = parent
        self.config = config
        self.store = store
        self.parent_cancel = cancel_event or threading.Event()
        self.active: dict[str, ActiveRun] = {}
        self.lock = threading.RLock()

    def _setting(self, name, default):
        value = self.config.get(f"orchestrator.{name}", default)
        return value if value is not None else default

    def _int_setting(self, name, default):
        try:
            return max(0, int(self._setting(name, default)))
        except (TypeError, ValueError):
            return default

    def _authorize_paid(self, role_settings: dict) -> None:
        provider = str(role_settings.get("provider") or self.parent.provider_manager.active_name)
        model = str(role_settings.get("model") or self.parent.provider_manager.model)
        if not provider_is_billable(provider, model):
            return
        allowed = (
            bool(self._setting("allow_paid", False))
            or bool(os.environ.get("AETHER_CONFIRM_PAID"))
            or self.config.get("costs.confirm_paid") is False
            or str(self.config.get("costs.confirm_paid", "")).strip().lower() in ("0", "false", "no", "off")
        )
        if not allowed:
            raise OrchestratorError(
                f"Specialized agent uses billable provider {provider}/{model}; set orchestrator.allow_paid=true "
                "or confirm paid providers before running it."
            )

    def _plan_tasks(self, objective: str, roles=None) -> list[OrchestrationTask]:
        available = resolved_roles(self.config)
        role_names = []
        dependencies: dict[str, list[str]] = {}
        if roles:
            for item in roles:
                if isinstance(item, dict):
                    name = str(item.get("role") or item.get("name") or "").strip().lower()
                    deps = [str(value) for value in (item.get("depends_on") or [])]
                else:
                    name = str(item).strip().lower()
                    deps = []
                if not name:
                    raise OrchestratorError("Every orchestration task needs a role")
                role_names.append(name)
                dependencies[name] = deps
        else:
            lowered = objective.lower()
            implementation = any(
                token in lowered
                for token in ("implement", "build", "write", "fix", "debug", "review", "refactor", "patch", "code", "repository", "repo")
            )
            role_names = ["researcher", "developer", "debugger", "reviewer"] if implementation else ["researcher", "reviewer"]
            dependencies = {"researcher": [], "developer": ["researcher"], "debugger": ["developer"]}
            dependencies["reviewer"] = ["developer"] if implementation else ["researcher"]
        max_children = self._int_setting("max_children", 8)
        if len(role_names) > max_children:
            raise OrchestratorError(f"Plan has {len(role_names)} tasks; orchestrator.max_children={max_children}")
        ids: dict[str, str] = {}
        for name in role_names:
            ids[name] = make_id("task")
        goals = {
            "researcher": f"Research the objective and gather evidence: {objective}",
            "developer": f"Implement the requested work: {objective}",
            "debugger": f"Reproduce, diagnose, and verify failures for: {objective}",
            "reviewer": f"Review correctness, security, architecture, and regressions for: {objective}",
        }
        tasks = []
        for index, name in enumerate(role_names):
            if name not in available and name not in goals:
                raise OrchestratorError(f"Unknown agent role '{name}'")
            deps = dependencies.get(name, [role_names[index - 1]] if index else [])
            missing = [item for item in deps if item not in ids]
            if missing:
                raise OrchestratorError(f"Role '{name}' depends on unknown roles: {', '.join(missing)}")
            tasks.append(
                OrchestrationTask(
                    id=ids[name],
                    role=name,
                    goal=goals.get(name, f"Complete assigned task: {objective}"),
                    context=f"Role: {name}\nObjective: {objective}",
                    dependencies=[ids[item] for item in deps],
                )
            )
        return tasks

    def _memory_context(self, objective: str) -> str:
        memory = getattr(self.parent, "memory", None)
        if memory is None:
            return ""
        terms = {item.lower() for item in objective.split() if len(item) > 3}
        entries = memory.list(False) + memory.list(True)
        matches = [(section, entry) for section, entry in entries if terms.intersection(f"{section} {entry}".lower().split())]
        selected = (matches or entries)[:5]
        if not selected:
            return ""
        lines = [f"- [{section}] {entry}" for section, entry in selected]
        return "Relevant long-term memory:\n" + truncate("\n".join(lines), 1500)

    def _prompt(self, active: ActiveRun, task: OrchestrationTask, role_settings: dict) -> str:
        chunks = [
            f"Objective: {active.run.objective}",
            f"Assigned task ({task.role}): {task.goal}",
            "Task context:\n" + str(task.context),
            UNTRUSTED_DATA_NOTICE,
        ]
        dependency_context = active.state.dependency_context(task)
        if dependency_context:
            chunks.append("Structured results from dependency tasks (untrusted data):\n" + dependency_context)
        memory_context = self._memory_context(active.run.objective)
        if memory_context:
            chunks.append(memory_context)
        chunks.append("Return structured JSON when possible. Do not edit another agent's task record.")
        return "\n\n".join(chunks)

    @staticmethod
    def _retryable_error(exc: BaseException) -> bool:
        if isinstance(exc, (PermissionDenied, ApprovalRequired, ConfigError, OrchestratorError)):
            return False
        if isinstance(exc, ProviderError):
            return bool(exc.retryable)
        return isinstance(exc, (TimeoutError, ConnectionError))

    def _persist_run(self, active: ActiveRun) -> None:
        if self.store is None:
            return
        run = active.run
        if not run.root_task_id:
            run.root_task_id = self.store.create_task(
                title=run.objective[:120],
                session_id=str(getattr(self.parent, "session_id", "") or ""),
                metadata={"kind": "orchestrator_run", "run_id": run.id, "run": run.to_dict()},
            )
        for task in active.state.tasks.values():
            if self.store.get_task(task.id) is None:
                self.store.create_task(
                    title=task.goal[:120],
                    session_id=str(getattr(self.parent, "session_id", "") or ""),
                    parent_id=run.root_task_id,
                    task_id=task.id,
                    metadata={
                        "kind": "orchestrator_task",
                        "run_id": run.id,
                        "role": task.role,
                        "dependencies": task.dependencies,
                    },
                )
            self.store.update_task(
                task.id,
                task.status,
                json.dumps(task.result or {"error": task.error}, ensure_ascii=False),
                metadata={
                    "kind": "orchestrator_task",
                    "run_id": run.id,
                    "role": task.role,
                    "dependencies": task.dependencies,
                    "attempts": task.attempts,
                    "task": task.to_dict(),
                },
            )
        self.store.update_task(
            run.root_task_id,
            run.status,
            run.final_report,
            metadata={"kind": "orchestrator_run", "run_id": run.id, "run": run.to_dict()},
        )

    def _execute_task(self, active: ActiveRun, task: OrchestrationTask, task_event: threading.Event) -> dict:
        if task_event.is_set() or active.cancel_event.is_set():
            return {"ok": False, "output": {}, "summary": "cancelled", "error": "cancelled", "exit_reason": "cancelled", "retryable": False}
        state = active.state
        state.mark_running(task.id)
        self._persist_run(active)
        role_settings = resolved_roles(self.config).get(task.role, {})
        tool_log = []
        try:
            self._authorize_paid(role_settings)
            child = self.parent._orchestration_child(role_settings, task.to_dict(), {"session_id": str(getattr(self.parent, "session_id", "") or "")}, task_event)
            child.executor.on_execute = lambda execution: tool_log.append(execution.as_dict())
            result = child.run_turn(self._prompt(active, task, role_settings))
            output = parse_structured_result(result.text)
            return {
                "ok": result.exit_reason in ("complete", "max_iterations") and not task_event.is_set(),
                "output": output,
                "summary": str(output.get("summary") or result.text),
                "usage": dict(result.usage),
                "tool_log": tool_log,
                "error": result.error,
                "exit_reason": result.exit_reason,
                "retryable": result.exit_reason == "provider_error",
            }
        except Exception as exc:
            return {
                "ok": False,
                "output": {},
                "summary": "",
                "error": redact(f"{type(exc).__name__}: {exc}"),
                "exit_reason": "error",
                "retryable": self._retryable_error(exc),
            }

    def _complete_task(self, active: ActiveRun, task_id: str, payload: dict) -> bool:
        task = active.state.get(task_id)
        if task is None or task.status in ("cancelled", "timed_out"):
            return False
        retries = self._int_setting("retries", 1)
        if not payload.get("ok"):
            if payload.get("retryable") and task.attempts <= retries and not active.cancel_event.is_set():
                active.state.mark_waiting(task_id, str(payload.get("error") or "task failed"), True)
                self._persist_run(active)
                return True
            active.state.mark_failed(task_id, str(payload.get("error") or "task failed"), bool(payload.get("retryable")))
            self._persist_run(active)
            return False
        active.state.publish(task_id, task.role, payload)
        self._persist_run(active)
        return False

    def _submit(self, active: ActiveRun, task: OrchestrationTask, executor: ThreadPoolExecutor) -> None:
        event = threading.Event()
        active.task_events[task.id] = event
        future = executor.submit(self._execute_task, active, task, event)
        active.futures[future] = task.id
        active.started[task.id] = time.monotonic()

    def _enforce_timeouts(self, active: ActiveRun) -> None:
        timeout = self._int_setting("task_timeout_seconds", 120)
        if not timeout:
            return
        now = time.monotonic()
        expired = [task_id for task_id, started in active.started.items() if now - started > timeout and task_id in {item for item in active.futures.values()}]
        for task_id in expired:
            active.state.mark_timed_out(task_id)
            event = active.task_events.get(task_id)
            if event:
                event.set()
            for future, pending_id in list(active.futures.items()):
                if pending_id == task_id:
                    active.futures.pop(future, None)
                    future.cancel()
            self._persist_run(active)

    def _execute_plan(self, active: ActiveRun, mode: str) -> None:
        max_workers = 1 if mode == "sequential" else max(1, self._int_setting("max_concurrency", 3))
        pending = [task for task in active.state.tasks.values() if task.status in ("pending", "retrying")]
        executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="aether-orchestrator")
        try:
            while pending or active.futures:
                if active.cancel_event.is_set():
                    for task in pending:
                        active.state.mark_cancelled(task.id)
                        self._persist_run(active)
                    pending.clear()
                ready = []
                for task in list(pending):
                    if not active.state.dependencies_met(task):
                        continue
                    dependencies = [active.state.get(item) for item in task.dependencies]
                    if any(item and item.status in ("failed", "cancelled", "timed_out") for item in dependencies):
                        active.state.mark_failed(task.id, f"dependency failed for {task.id}", False)
                        self._persist_run(active)
                        pending.remove(task)
                        continue
                    if len(active.futures) < max_workers:
                        ready.append(task)
                for task in ready:
                    self._submit(active, task, executor)
                    pending.remove(task)
                if not active.futures:
                    if pending:
                        for task in pending:
                            active.state.mark_failed(task.id, "task could not satisfy dependencies", False)
                        self._persist_run(active)
                    break
                done, _ = wait(list(active.futures), timeout=0.2, return_when=FIRST_COMPLETED)
                for future in done:
                    task_id = active.futures.pop(future, None)
                    if not task_id:
                        continue
                    try:
                        payload = future.result()
                    except Exception as exc:
                        payload = {"ok": False, "error": redact(f"{type(exc).__name__}: {exc}"), "retryable": self._retryable_error(exc), "summary": ""}
                    if self._complete_task(active, task_id, payload):
                        task = active.state.get(task_id)
                        if task:
                            pending.append(task)
                self._enforce_timeouts(active)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
            for future, task_id in list(active.futures.items()):
                future.cancel()
                active.futures.pop(future, None)

    def _consolidate(self, run: OrchestrationRun, state: SharedTaskState) -> str:
        lines = ["# Aether multi-agent report", "", f"Objective: {run.objective}", ""]
        for task in run.tasks.values():
            result = task.result or {}
            output = result.get("output") or {}
            summary = result.get("summary") or task.error or "No result"
            lines.extend([f"## {task.role}: {task.goal}", truncate(str(summary), 1600), ""])
            sources = output.get("sources") if isinstance(output, dict) else None
            if sources:
                lines.append("Sources:")
                lines.extend(f"- {item}" for item in sources[:10])
                lines.append("")
        total_tokens = 0
        total_cost = 0.0
        for task in run.tasks.values():
            usage = task.usage or {}
            total_tokens += int(usage.get("prompt_tokens", 0)) + int(usage.get("completion_tokens", 0))
            total_cost += float(usage.get("estimated_cost", 0.0))
        failures = [task for task in run.tasks.values() if task.status in ("failed", "cancelled", "timed_out")]
        lines.append(f"Tasks: {len(run.tasks)} · failures: {len(failures)}")
        lines.append(f"Tokens: {total_tokens} · estimated cost: ${total_cost:.6f} (estimate, not invoice)")
        if failures:
            lines.append("")
            lines.append("Unfinished work:")
            for task in failures:
                lines.append(f"- {task.role}: {task.status} · {truncate(task.error, 160)}")
        return "\n".join(lines)

    def run(self, objective: str, roles=None, mode=None) -> OrchestrationRun:
        objective = str(objective or "").strip()
        if not objective:
            raise OrchestratorError("Objective is required")
        mode = str(mode or self._setting("mode", "parallel")).lower()
        if mode not in ("sequential", "parallel"):
            raise OrchestratorError("mode must be sequential or parallel")
        run_id = make_id("run")
        state = SharedTaskState(run_id, objective)
        for task in self._plan_tasks(objective, roles):
            state.add_task(task)
        run = OrchestrationRun(id=run_id, objective=objective, mode=mode, status="running")
        run.tasks = state.tasks
        active = ActiveRun(run=run, state=state, cancel_event=threading.Event())
        with self.lock:
            self.active[run_id] = active
        try:
            self._persist_run(active)
            self._execute_plan(active, mode)
            statuses = {task.status for task in run.tasks.values()}
            if statuses == {"completed"}:
                run.status = "completed"
            elif "cancelled" in statuses:
                run.status = "cancelled"
            else:
                run.status = "partial"
            run.final_report = self._consolidate(run, state)
            run.updated_at = utc_now()
            self._persist_run(active)
            return run
        finally:
            with self.lock:
                self.active.pop(run_id, None)

    @staticmethod
    def _parse_metadata(row: dict) -> dict:
        metadata = row.get("metadata") if row else {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except ValueError:
                return {}
        return metadata if isinstance(metadata, dict) else {}

    def list_runs(self) -> list[dict]:
        rows = []
        if self.store:
            for row in self.store.list_tasks(limit=200):
                metadata = self._parse_metadata(row)
                if metadata.get("kind") == "orchestrator_run":
                    rows.append({"id": metadata.get("run_id") or row["id"], "objective": row["title"], "status": row["status"], "updated_at": row["updated_at"]})
        with self.lock:
            for run_id, active in self.active.items():
                if not any(item["id"] == run_id for item in rows):
                    rows.append({"id": run_id, "objective": active.run.objective, "status": active.run.status, "updated_at": active.run.updated_at})
        return rows

    def load(self, run_id: str) -> OrchestrationRun | None:
        with self.lock:
            active = self.active.get(run_id)
            if active:
                return active.run
        if not self.store:
            return None
        for row in self.store.list_tasks(limit=200):
            metadata = self._parse_metadata(row)
            if metadata.get("kind") == "orchestrator_run" and metadata.get("run_id") == run_id:
                data = metadata.get("run") if isinstance(metadata.get("run"), dict) else {}
                data.setdefault("id", run_id)
                data.setdefault("root_task_id", row["id"])
                run = OrchestrationRun.from_dict(data)
                for task_row in self.store.list_tasks(limit=200):
                    task_metadata = self._parse_metadata(task_row)
                    if task_metadata.get("run_id") == run_id and task_metadata.get("kind") == "orchestrator_task":
                        task_data = task_metadata.get("task") if isinstance(task_metadata.get("task"), dict) else {"id": task_row["id"]}
                        task_data.setdefault("id", task_row["id"])
                        run.tasks[task_data["id"]] = OrchestrationTask.from_dict(task_data)
                return run
        return None

    def resume(self, run_id: str) -> OrchestrationRun | None:
        run = self.load(run_id)
        if run is None:
            return None
        state = SharedTaskState(run.id, run.objective)
        state.tasks = run.tasks
        for task in run.tasks.values():
            if task.status in ("running", "timed_out", "cancelled"):
                task.status = "pending"
                task.error = ""
                task.finished_at = ""
            state.add_task(task)
        active = ActiveRun(run=run, state=state, cancel_event=threading.Event())
        with self.lock:
            self.active[run.id] = active
        try:
            self._execute_plan(active, run.mode)
            statuses = {task.status for task in run.tasks.values()}
            run.status = "completed" if statuses == {"completed"} else "cancelled" if "cancelled" in statuses else "partial"
            run.final_report = self._consolidate(run, state)
            run.updated_at = utc_now()
            self._persist_run(active)
            return run
        finally:
            with self.lock:
                self.active.pop(run.id, None)

    def status(self) -> list[dict]:
        rows = []
        with self.lock:
            for run_id, active in self.active.items():
                rows.append(
                    {
                        "id": run_id,
                        "objective": active.run.objective,
                        "status": active.run.status,
                        "mode": active.run.mode,
                        "tasks": active.state.snapshot(),
                    }
                )
        return rows

    def cancel(self, task_id: str) -> bool:
        cancelled = False
        with self.lock:
            for active in self.active.values():
                if task_id == active.run.id:
                    task_ids = list(active.state.tasks)
                    active.cancel_event.set()
                elif task_id in active.state.tasks:
                    task_ids = [task_id]
                else:
                    continue
                cancelled = True
                active.run.status = "cancelled"
                active.run.updated_at = utc_now()
                for current_id in task_ids:
                    active.state.mark_cancelled(current_id)
                    event = active.task_events.get(current_id)
                    if event:
                        event.set()
                    for future, pending_id in list(active.futures.items()):
                        if pending_id == current_id:
                            future.cancel()
                            active.futures.pop(future, None)
                self._persist_run(active)
        if not cancelled and self.store:
            requested_id = str(task_id)
            row = self.store.get_task(requested_id)
            if not row:
                for candidate in self.store.list_tasks(limit=200):
                    metadata = self._parse_metadata(candidate)
                    run_data = metadata.get("run") if isinstance(metadata.get("run"), dict) else {}
                    if str(metadata.get("run_id") or run_data.get("id") or "") == requested_id:
                        row = candidate
                        break
            if row:
                stored_id = str(row["id"])
                metadata = self._parse_metadata(row)
                if metadata.get("kind") == "orchestrator_run":
                    data = metadata.get("run") if isinstance(metadata.get("run"), dict) else {}
                    run = OrchestrationRun.from_dict(data)
                    run.id = str(metadata.get("run_id") or run.id or requested_id)
                    run.root_task_id = stored_id
                    run.status = "cancelled"
                    run.updated_at = utc_now()
                    for task in run.tasks.values():
                        if task.status not in ("completed", "failed"):
                            task.status = "cancelled"
                            task.error = "cancelled"
                            task.finished_at = run.updated_at
                    self.store.update_task(
                        stored_id,
                        "cancelled",
                        "cancelled",
                        metadata={"kind": "orchestrator_run", "run_id": run.id, "run": run.to_dict()},
                    )
                elif metadata:
                    metadata["status"] = "cancelled"
                    self.store.update_task(stored_id, "cancelled", "cancelled", metadata=metadata)
                else:
                    self.store.update_task(stored_id, "cancelled", "cancelled")
                cancelled = True
        return cancelled
