import json
import os
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field

from aether.errors import ApprovalRequired, ConfigError, OrchestratorError, PermissionDenied, ProviderError
from aether.providers.catalog import provider_is_billable
from aether.utils import make_id, parse_bool, redact, recognized_check_command, truncate, utc_now

from .roles import UNTRUSTED_DATA_NOTICE, resolved_roles
from .contracts import validate_role_output
from .state import OrchestrationRun, OrchestrationTask, SharedTaskState, parse_structured_result


class _LinkedCancelEvent:
    def __init__(self, parent=None):
        self._event = threading.Event()
        self._parent = parent

    def is_set(self) -> bool:
        return self._event.is_set() or bool(self._parent is not None and self._parent.is_set())

    def set(self) -> None:
        self._event.set()

    def clear(self) -> None:
        self._event.clear()

    def wait(self, timeout=None) -> bool:
        if self.is_set():
            return True
        return self._event.wait(timeout)


@dataclass
class ActiveRun:
    run: OrchestrationRun
    state: SharedTaskState
    cancel_event: _LinkedCancelEvent
    task_events: dict[str, threading.Event] = field(default_factory=dict)
    futures: dict = field(default_factory=dict)
    started: dict[str, float] = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock)


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
            or parse_bool(os.environ.get("AETHER_CONFIRM_PAID"), False)
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
        if roles is not None:
            if not roles:
                raise OrchestratorError("At least one orchestration role is required")
            for item in roles:
                if isinstance(item, dict):
                    name = str(item.get("role") or item.get("name") or "").strip().lower()
                    deps = [str(value).strip().lower() for value in (item.get("depends_on") or [])]
                else:
                    name = str(item).strip().lower()
                    deps = []
                if not name:
                    raise OrchestratorError("Every orchestration task needs a role")
                if name in role_names:
                    raise OrchestratorError(f"Duplicate orchestration role '{name}'")
                role_names.append(name)
                dependencies[name] = deps
        else:
            lowered = objective.lower()
            security_work = any(token in lowered for token in (
                "security", "vulnerability", "permission", "secret", "authentication",
                "authorization", "sandbox", "prompt injection",
            ))
            debugging_work = any(token in lowered for token in (
                "debug", "bug", "traceback", "stack trace", "regression", "crash",
                "failing test", "tests fail", "broken",
            ))
            implementation = any(token in lowered for token in (
                "implement", "build", "write code", "fix", "refactor", "patch",
                "code", "repository", "repo", "develop", "feature", "application",
            ))
            documentation = not implementation and any(token in lowered for token in (
                "documentation", "document", "docs", "readme", "user guide", "write a guide",
            ))

            if debugging_work:
                role_names = ["researcher", "debugger", "tester", "verifier", "reviewer"]
                dependencies = {
                    "researcher": [],
                    "debugger": ["researcher"],
                    "tester": ["debugger"],
                    "verifier": ["tester"],
                    "reviewer": ["verifier"],
                }
            elif implementation:
                role_names = ["planner", "researcher", "architect", "developer", "tester"]
                dependencies = {
                    "planner": [],
                    "researcher": ["planner"],
                    "architect": ["researcher"],
                    "developer": ["architect"],
                    "tester": ["developer"],
                }
                if security_work:
                    role_names.append("security_auditor")
                    dependencies["security_auditor"] = ["researcher", "developer"]
                role_names.extend(["verifier", "reviewer"])
                dependencies["verifier"] = (
                    ["tester", "security_auditor"] if security_work else ["tester"]
                )
                dependencies["reviewer"] = ["verifier"]
            elif documentation:
                role_names = ["planner", "researcher", "documentation_writer", "tester", "verifier", "reviewer"]
                dependencies = {
                    "planner": [],
                    "researcher": ["planner"],
                    "documentation_writer": ["researcher"],
                    "tester": ["documentation_writer"],
                    "verifier": ["tester"],
                    "reviewer": ["verifier"],
                }
            else:
                # Keep simple questions inexpensive; verification is for work products.
                role_names = ["researcher", "reviewer"]
                dependencies = {"researcher": [], "reviewer": ["researcher"]}

        max_children = self._int_setting("max_children", 8)
        if len(role_names) > max_children:
            raise OrchestratorError(f"Plan has {len(role_names)} tasks; orchestrator.max_children={max_children}")

        ids: dict[str, str] = {name: make_id("task") for name in role_names}
        goals = {
            "planner": f"Plan the work, dependencies, risks, and acceptance checks for: {objective}",
            "researcher": f"Research constraints and gather concrete evidence for: {objective}",
            "architect": f"Design a backward-compatible implementation and identify affected files: {objective}",
            "developer": f"Implement the requested work with focused changes and tests: {objective}",
            "debugger": f"Reproduce and diagnose the failure, then make the smallest safe fix: {objective}",
            "tester": f"Run focused tests and report exact commands, exit codes, and failures for: {objective}",
            "security_auditor": f"Audit the work for security, permission, prompt-injection, and secret risks: {objective}",
            "verifier": f"Independently verify the work by running repository checks; do not rely on other agents' claims: {objective}",
            "reviewer": f"Independently review correctness, regressions, security, and maintainability: {objective}",
            "documentation_writer": f"Update user and developer documentation to match implemented behavior: {objective}",
            "data_analyst": f"Analyze relevant data and distinguish measurements from assumptions: {objective}",
        }
        for name in role_names:
            if name not in available:
                raise OrchestratorError(f"Unknown agent role '{name}'")

        for name in role_names:
            missing = [dependency for dependency in dependencies.get(name, []) if dependency not in ids]
            if missing:
                raise OrchestratorError(f"Role '{name}' depends on unknown roles: {', '.join(missing)}")

        visiting = set()
        visited = set()

        def visit(name):
            if name in visiting:
                raise OrchestratorError(f"Orchestration dependency cycle contains '{name}'")
            if name in visited:
                return
            visiting.add(name)
            for dependency in dependencies.get(name, []):
                visit(dependency)
            visiting.remove(name)
            visited.add(name)

        for name in role_names:
            visit(name)

        tasks = []
        for name in role_names:
            tasks.append(
                OrchestrationTask(
                    id=ids[name],
                    role=name,
                    goal=goals.get(name, f"Complete the assigned objective: {objective}"),
                    context=f"Role: {name}\nObjective: {objective}",
                    dependencies=[ids[item] for item in dependencies.get(name, [])],
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
        with self.lock:
            run = active.run
            session_id = str(getattr(self.parent, "session_id", "") or "")
            creates = []
            updates = []
            usages = []
            if not run.root_task_id:
                run.root_task_id = make_id("task")
                creates.append(
                    {
                        "id": run.root_task_id,
                        "session_id": session_id,
                        "title": run.objective[:120],
                        "metadata": {"kind": "orchestrator_run", "run_id": run.id, "run": run.to_dict()},
                    }
                )
            with active.state.lock:
                tasks = list(active.state.tasks.values())
                run.tasks = active.state.tasks
            for task in tasks:
                metadata = {
                    "kind": "orchestrator_task",
                    "run_id": run.id,
                    "role": task.role,
                    "dependencies": task.dependencies,
                    "attempts": task.attempts,
                    "task": task.to_dict(),
                }
                if self.store.get_task(task.id) is None:
                    creates.append(
                        {
                            "id": task.id,
                            "session_id": session_id,
                            "parent_id": run.root_task_id,
                            "title": task.goal[:120],
                            "metadata": metadata,
                        }
                    )
                updates.append(
                    {
                        "id": task.id,
                        "status": task.status,
                        "result": json.dumps(task.result or {"error": task.error}, ensure_ascii=False),
                        "metadata": metadata,
                    }
                )
                if task.usage and not task.usage_persisted:
                    usages.append({"session_id": session_id, **task.usage})
                    task.usage_persisted = True
            updates.append(
                {
                    "id": run.root_task_id,
                    "status": run.status,
                    "result": run.final_report,
                    "metadata": {"kind": "orchestrator_run", "run_id": run.id, "run": run.to_dict()},
                }
            )
            self.store.persist_orchestration(creates, updates, usages)

    @staticmethod
    def _supported_check_command(command: str) -> bool:
        return bool(recognized_check_command(command))

    @classmethod
    def _verified_check_evidence(cls, tool_log: list[dict]) -> list[dict]:
        evidence = []
        for record in tool_log or []:
            if not isinstance(record, dict) or not record.get("ok"):
                continue
            tool_name = record.get("name")
            arguments = record.get("arguments") if isinstance(record.get("arguments"), dict) else {}
            command = str(arguments.get("command") or "").strip()
            if tool_name == "terminal":
                if not cls._supported_check_command(command):
                    continue
            elif tool_name == "test_run":
                mode = str(arguments.get("mode") or "").strip().lower()
                if mode not in ("suite", "module", "compile", "check"):
                    continue
                module = str(arguments.get("module") or "").strip()
                command = f"test_run {mode}" + (f" {module}" if mode == "module" else "")
            else:
                continue
            result = record.get("result")
            payload = result if isinstance(result, dict) else {}
            if isinstance(result, str):
                try:
                    parsed = json.loads(result)
                    if isinstance(parsed, dict):
                        payload = parsed
                except ValueError:
                    continue
            try:
                exit_code = int(payload.get("exit_code"))
            except (TypeError, ValueError):
                continue
            if exit_code == 0 and not payload.get("timed_out"):
                evidence.append({"command": truncate(command, 240), "exit_code": 0})
        return evidence

    def _execute_task(self, active: ActiveRun, task: OrchestrationTask, task_event: threading.Event) -> dict:
        if task_event.is_set() or active.cancel_event.is_set():
            return {"ok": False, "output": {}, "summary": "cancelled", "error": "cancelled", "exit_reason": "cancelled", "retryable": False}
        state = active.state
        if not state.try_mark_running(task.id):
            return {"ok": False, "output": {}, "summary": "cancelled", "error": "task is no longer runnable", "exit_reason": "cancelled", "retryable": False}
        self._persist_run(active)
        role_settings = dict(resolved_roles(self.config).get(task.role, {}))
        role_settings.setdefault("role", task.role)
        tool_log = []
        try:
            self._authorize_paid(role_settings)
            child = self.parent._orchestration_child(role_settings, task.to_dict(), {"session_id": str(getattr(self.parent, "session_id", "") or "")}, task_event)
            child.executor.on_execute = lambda execution: tool_log.append(execution.as_dict())
            result = child.run_turn(self._prompt(active, task, role_settings))
            output = parse_structured_result(result.text)
            combined_log = list(tool_log) + list(getattr(result, "tool_log", []) or [])
            contract_errors = (
                validate_role_output(task.role, output)
                if task.role == "verifier" or bool(self._setting("strict_output_contracts", False))
                else []
            )
            task_ok = result.exit_reason in ("complete", "max_iterations") and not task_event.is_set()
            error = result.error
            if task.role == "verifier":
                evidence = self._verified_check_evidence(combined_log)
                requested_verdict = str(output.get("verdict") or "").strip().lower()
                checks = output.get("checks")
                verified = bool(
                    task_ok
                    and not contract_errors
                    and requested_verdict == "pass"
                    and isinstance(checks, list)
                    and checks
                    and evidence
                )
                output["aether_verification"] = {
                    "verified": verified,
                    "commands": evidence,
                    "reason": (
                        "A successful recognized test/check command was observed in this verifier's own tool log."
                        if verified
                        else "Independent test/check evidence and a valid pass contract were not both observed."
                    ),
                }
                if not verified:
                    task_ok = False
                    output["verdict"] = "partial" if requested_verdict != "fail" else "fail"
                    error = "Independent verification was not established: run a recognized check command and report its observed result."
            elif contract_errors:
                task_ok = False
                error = "Structured role output violated its contract: " + "; ".join(contract_errors)
            return {
                "ok": task_ok,
                "output": output,
                "summary": str(output.get("summary") or result.text),
                "usage": dict(result.usage),
                "tool_log": combined_log,
                "error": error,
                "exit_reason": result.exit_reason,
                "retryable": result.exit_reason == "provider_error" and not combined_log,
            }
        except Exception as exc:
            return {
                "ok": False,
                "output": {},
                "summary": "",
                "error": redact(f"{type(exc).__name__}: {exc}"),
                "exit_reason": "error",
                "tool_log": tool_log,
                "retryable": self._retryable_error(exc) and not tool_log,
            }

    def _complete_task(self, active: ActiveRun, task_id: str, payload: dict) -> bool:
        task = active.state.get(task_id)
        if task is None or task.status in ("cancelled", "timed_out"):
            return False
        active.state.add_attempt(task_id, payload)
        retries = self._int_setting("retries", 1)
        if not payload.get("ok"):
            if (
                payload.get("retryable")
                and not payload.get("tool_log")
                and task.attempts <= retries
                and not active.cancel_event.is_set()
            ):
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
        with active.lock:
            active.task_events[task.id] = event
        future = executor.submit(self._execute_task, active, task, event)
        with active.lock:
            active.futures[future] = task.id
            active.started[task.id] = time.monotonic()

    def _enforce_timeouts(self, active: ActiveRun) -> None:
        timeout = self._int_setting("task_timeout_seconds", 120)
        if not timeout:
            return
        now = time.monotonic()
        with active.lock:
            running = set(active.futures.values())
            expired = [
                task_id
                for task_id, started in active.started.items()
                if now - started > timeout and task_id in running
            ]
            events = {task_id: active.task_events.get(task_id) for task_id in expired}
            futures = list(active.futures.items())
        for task_id in expired:
            active.state.mark_timed_out(task_id)
            event = events.get(task_id)
            if event:
                event.set()
            for future, pending_id in futures:
                if pending_id == task_id:
                    future.cancel()
        if expired:
            self._persist_run(active)

    def _abort_running(self, active: ActiveRun) -> None:
        with active.lock:
            futures = list(active.futures.items())
            events = list(active.task_events.values())
        for event in events:
            event.set()
        for future, _ in futures:
            future.cancel()

    def _execute_plan(self, active: ActiveRun, mode: str) -> None:
        max_workers = 1 if mode == "sequential" else max(1, self._int_setting("max_concurrency", 3))
        pending = [task for task in active.state.tasks.values() if task.status in ("pending", "retrying")]
        executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="aether-orchestrator")
        try:
            while pending or active.futures:
                if active.cancel_event.is_set():
                    self._abort_running(active)
                    for task in pending:
                        active.state.mark_cancelled(task.id)
                    if pending:
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
                    with active.lock:
                        slots = len(active.futures) < max_workers
                    if slots:
                        ready.append(task)
                for task in ready:
                    self._submit(active, task, executor)
                    pending.remove(task)
                with active.lock:
                    futures = list(active.futures)
                if not futures:
                    if pending:
                        for task in pending:
                            active.state.mark_failed(task.id, "task could not satisfy dependencies", False)
                        self._persist_run(active)
                    break
                done, _ = wait(futures, timeout=0.2, return_when=FIRST_COMPLETED)
                for future in done:
                    with active.lock:
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
            self._abort_running(active)
            executor.shutdown(wait=False, cancel_futures=True)
            with active.lock:
                pending_futures = list(active.futures)
            if pending_futures:
                wait(pending_futures, timeout=2)
            with active.lock:
                active.futures.clear()
                active.started.clear()

    def _consolidate(self, run: OrchestrationRun, state: SharedTaskState) -> str:
        lines = ["# Aether multi-agent report", "", f"Objective: {run.objective}", ""]
        verifier_tasks = [task for task in run.tasks.values() if task.role == "verifier"]
        verified_commands = []
        for task in verifier_tasks:
            output = (task.result or {}).get("output") or {}
            verification = output.get("aether_verification") if isinstance(output, dict) else {}
            if isinstance(verification, dict) and verification.get("verified"):
                verified_commands.extend(verification.get("commands") or [])
        if verifier_tasks and verified_commands:
            lines.append("Independent verification: VERIFIED")
            lines.extend(f"- {item.get('command')} (exit {item.get('exit_code')})" for item in verified_commands)
        elif verifier_tasks:
            lines.append("Independent verification: NOT VERIFIED")
        else:
            lines.append("Independent verification: NOT REQUESTED")
        lines.append("")

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
        active = ActiveRun(run=run, state=state, cancel_event=_LinkedCancelEvent(self.parent_cancel))
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
        except BaseException:
            state.finalize_unfinished("failed", "orchestration interrupted")
            run.status = "partial"
            run.final_report = self._consolidate(run, state)
            run.updated_at = utc_now()
            self._persist_run(active)
            raise
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
            for row in self.store.list_tasks(limit=None):
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
        for row in self.store.list_tasks(limit=None):
            metadata = self._parse_metadata(row)
            if metadata.get("kind") == "orchestrator_run" and metadata.get("run_id") == run_id:
                data = metadata.get("run") if isinstance(metadata.get("run"), dict) else {}
                data.setdefault("id", run_id)
                data.setdefault("root_task_id", row["id"])
                run = OrchestrationRun.from_dict(data)
                if row["status"] != "running":
                    run.status = row["status"]
                for task_row in self.store.find_tasks_by_run_id(run_id):
                    task_metadata = self._parse_metadata(task_row)
                    if task_metadata.get("kind") != "orchestrator_task":
                        continue
                    task_data = task_metadata.get("task") if isinstance(task_metadata.get("task"), dict) else {"id": task_row["id"]}
                    task_data.setdefault("id", task_row["id"])
                    task = OrchestrationTask.from_dict(task_data)
                    if task_row["status"] not in ("pending", "running", "retrying"):
                        task.status = task_row["status"]
                    run.tasks[task.id] = task
                return run
        return None

    def resume(self, run_id: str) -> OrchestrationRun | None:
        with self.lock:
            active = self.active.get(run_id)
            if active:
                return active.run
        run = self.load(run_id)
        if run is None:
            return None
        state = SharedTaskState(run.id, run.objective)
        state.tasks = run.tasks
        for task in run.tasks.values():
            if task.status in ("running", "timed_out"):
                task.status = "pending"
                task.error = ""
                task.finished_at = ""
            state.add_task(task)
        run.status = "running"
        active = ActiveRun(run=run, state=state, cancel_event=_LinkedCancelEvent(self.parent_cancel))
        with self.lock:
            self.active[run.id] = active
        try:
            self._persist_run(active)
            self._execute_plan(active, run.mode)
            statuses = {task.status for task in run.tasks.values()}
            run.status = "completed" if statuses == {"completed"} else "cancelled" if "cancelled" in statuses else "partial"
            run.final_report = self._consolidate(run, state)
            run.updated_at = utc_now()
            self._persist_run(active)
            return run
        except BaseException:
            state.finalize_unfinished("failed", "orchestration interrupted")
            run.status = "partial"
            run.final_report = self._consolidate(run, state)
            run.updated_at = utc_now()
            self._persist_run(active)
            raise
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
                with active.lock:
                    events = {key: value for key, value in active.task_events.items() if key in task_ids}
                    futures = list(active.futures.items())
                for current_id in task_ids:
                    active.state.mark_cancelled(current_id)
                    event = events.get(current_id)
                    if event:
                        event.set()
                    for future, pending_id in futures:
                        if pending_id == current_id:
                            future.cancel()
                self._persist_run(active)
        if not cancelled and self.store:
            requested_id = str(task_id)
            row = self.store.get_task(requested_id)
            if not row:
                for candidate in self.store.find_tasks_by_run_id(requested_id):
                    metadata = self._parse_metadata(candidate)
                    run_data = metadata.get("run") if isinstance(metadata.get("run"), dict) else {}
                    if str(metadata.get("run_id") or run_data.get("id") or "") == requested_id:
                        row = candidate
                        break
            if row:
                requested = str(requested_id)
                metadata = self._parse_metadata(row)
                run_id = str(metadata.get("run_id") or requested)
                related = self.store.find_tasks_by_run_id(run_id)
                root_row = next((item for item in related if self._parse_metadata(item).get("kind") == "orchestrator_run"), None)
                if root_row is None and metadata.get("kind") == "orchestrator_run":
                    root_row = row
                if root_row is None:
                    root_row = row
                root_metadata = self._parse_metadata(root_row)
                data = root_metadata.get("run") if isinstance(root_metadata.get("run"), dict) else {}
                run = OrchestrationRun.from_dict(data)
                run.id = str(root_metadata.get("run_id") or run.id or requested)
                run.root_task_id = str(root_row["id"])
                run.status = "cancelled"
                run.updated_at = utc_now()
                for task in run.tasks.values():
                    if task.status not in ("completed", "failed"):
                        task.status = "cancelled"
                        task.error = "cancelled"
                        task.finished_at = run.updated_at
                updates = [
                    {
                        "id": run.root_task_id,
                        "status": "cancelled",
                        "result": "cancelled",
                        "metadata": {"kind": "orchestrator_run", "run_id": run.id, "run": run.to_dict()},
                    }
                ]
                for task_row in related:
                    task_metadata = self._parse_metadata(task_row)
                    if task_metadata.get("kind") != "orchestrator_task":
                        continue
                    task_data = task_metadata.get("task") if isinstance(task_metadata.get("task"), dict) else {"id": task_row["id"]}
                    task_data.setdefault("id", task_row["id"])
                    task = OrchestrationTask.from_dict(task_data)
                    if task.status not in ("completed", "failed"):
                        task.status = "cancelled"
                        task.error = "cancelled"
                        task.finished_at = run.updated_at
                    task_metadata["task"] = task.to_dict()
                    task_metadata["status"] = "cancelled"
                    updates.append(
                        {
                            "id": str(task_row["id"]),
                            "status": "cancelled" if task.status == "cancelled" else task_row["status"],
                            "result": task_row["result"],
                            "metadata": task_metadata,
                        }
                    )
                self.store.persist_orchestration(updates=updates)
                cancelled = True
        return cancelled
