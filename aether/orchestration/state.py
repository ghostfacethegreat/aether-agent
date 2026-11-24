import json
import threading
from dataclasses import dataclass, field

from aether.errors import OrchestratorError
from aether.utils import make_id, redact, truncate, utc_now


def parse_structured_result(text) -> dict:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    payload = None
    try:
        payload = json.loads(raw)
    except ValueError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                payload = json.loads(raw[start : end + 1])
            except ValueError:
                payload = None
    if isinstance(payload, dict):
        return payload
    return {"summary": raw}


def _json_load(value, default):
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except ValueError:
            return default
        if isinstance(parsed, type(default)):
            return parsed
    return default


@dataclass
class OrchestrationTask:
    id: str
    role: str
    goal: str
    context: str = ""
    dependencies: list[str] = field(default_factory=list)
    status: str = "pending"
    attempts: int = 0
    result: dict | None = None
    error: str = ""
    retryable: bool = False
    usage: dict = field(default_factory=dict)
    tool_log: list = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "goal": self.goal,
            "context": self.context,
            "dependencies": list(self.dependencies),
            "status": self.status,
            "attempts": self.attempts,
            "result": self.result,
            "error": self.error,
            "retryable": self.retryable,
            "usage": dict(self.usage),
            "tool_log": list(self.tool_log),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OrchestrationTask":
        return cls(
            id=str(data.get("id") or make_id("task")),
            role=str(data.get("role") or "worker"),
            goal=str(data.get("goal") or ""),
            context=str(data.get("context") or ""),
            dependencies=[str(item) for item in (_json_load(data.get("dependencies"), []) or [])],
            status=str(data.get("status") or "pending"),
            attempts=int(data.get("attempts") or 0),
            result=_json_load(data.get("result"), {}) or None,
            error=str(data.get("error") or ""),
            retryable=bool(data.get("retryable")),
            usage=_json_load(data.get("usage"), {}),
            tool_log=_json_load(data.get("tool_log"), []),
            started_at=str(data.get("started_at") or ""),
            finished_at=str(data.get("finished_at") or ""),
        )


@dataclass
class OrchestrationRun:
    id: str
    objective: str
    mode: str
    root_task_id: str = ""
    status: str = "pending"
    final_report: str = ""
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    tasks: dict[str, OrchestrationTask] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "objective": self.objective,
            "mode": self.mode,
            "root_task_id": self.root_task_id,
            "status": self.status,
            "final_report": self.final_report,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tasks": {key: value.to_dict() for key, value in self.tasks.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OrchestrationRun":
        tasks = _json_load(data.get("tasks"), {})
        return cls(
            id=str(data.get("id") or make_id("run")),
            objective=str(data.get("objective") or ""),
            mode=str(data.get("mode") or "parallel"),
            root_task_id=str(data.get("root_task_id") or ""),
            status=str(data.get("status") or "pending"),
            final_report=str(data.get("final_report") or ""),
            created_at=str(data.get("created_at") or utc_now()),
            updated_at=str(data.get("updated_at") or utc_now()),
            tasks={key: OrchestrationTask.from_dict(value) for key, value in tasks.items() if isinstance(value, dict)},
        )


class SharedTaskState:
    def __init__(self, run_id: str, objective: str):
        self.run_id = run_id
        self.objective = objective
        self.tasks: dict[str, OrchestrationTask] = {}
        self.artifacts: dict[str, dict] = {}
        self.working_memory: dict[str, dict] = {}
        self.messages: list[dict] = []
        self.lock = threading.RLock()

    def add_task(self, task: OrchestrationTask) -> None:
        with self.lock:
            self.tasks[task.id] = task

    def get(self, task_id: str) -> OrchestrationTask | None:
        with self.lock:
            return self.tasks.get(task_id)

    def dependencies_met(self, task: OrchestrationTask) -> bool:
        with self.lock:
            return all(self.tasks.get(item) and self.tasks[item].status == "completed" for item in task.dependencies)

    def dependency_context(self, task: OrchestrationTask) -> str:
        chunks = []
        with self.lock:
            for dependency_id in task.dependencies:
                dependency = self.tasks.get(dependency_id)
                if not dependency or not dependency.result:
                    continue
                output = dependency.result.get("output") or dependency.result.get("summary") or ""
                if not isinstance(output, str):
                    output = json.dumps(output, ensure_ascii=False)
                chunks.append(f"[{dependency.role}] {truncate(output, 4000)}")
        return "\n\n".join(chunks)

    def mark_running(self, task_id: str) -> None:
        with self.lock:
            task = self.tasks[task_id]
            task.status = "running"
            task.attempts += 1
            task.started_at = task.started_at or utc_now()
            task.error = ""
            task.retryable = False

    def mark_waiting(self, task_id: str, error: str, retryable: bool) -> None:
        with self.lock:
            task = self.tasks[task_id]
            task.status = "retrying"
            task.error = truncate(redact(error), 2000)
            task.retryable = bool(retryable)
            task.finished_at = utc_now()

    def mark_failed(self, task_id: str, error: str, retryable: bool = False) -> None:
        with self.lock:
            task = self.tasks[task_id]
            task.status = "failed"
            task.error = truncate(redact(error), 2000)
            task.retryable = bool(retryable)
            task.finished_at = utc_now()

    def mark_cancelled(self, task_id: str) -> None:
        with self.lock:
            task = self.tasks[task_id]
            if task.status not in ("completed", "failed"):
                task.status = "cancelled"
                task.error = "cancelled"
                task.finished_at = utc_now()

    def mark_timed_out(self, task_id: str) -> None:
        with self.lock:
            task = self.tasks[task_id]
            if task.status not in ("completed", "failed", "cancelled"):
                task.status = "timed_out"
                task.error = "task timed out after configured limit"
                task.finished_at = utc_now()

    def publish(self, task_id: str, owner_role: str, payload: dict) -> dict:
        with self.lock:
            task = self.tasks[task_id]
            if task.status == "cancelled":
                raise OrchestratorError("Cancelled tasks cannot publish results")
            if task.result and task.result.get("owner") != owner_role:
                raise OrchestratorError(f"Task {task_id} is owned by {task.result.get('owner')}; {owner_role} cannot overwrite it")
            revision = int((task.result or {}).get("revision", 0)) + 1
            result = {
                "owner": owner_role,
                "role": owner_role,
                "revision": revision,
                "ok": bool(payload.get("ok")),
                "output": payload.get("output") or {},
                "summary": str(payload.get("summary") or "")[:4000],
                "usage": dict(payload.get("usage") or {}),
                "tool_log": list(payload.get("tool_log") or []),
                "error": truncate(redact(str(payload.get("error") or "")), 2000),
                "exit_reason": str(payload.get("exit_reason") or ""),
                "attempts": task.attempts,
            }
            task.result = result
            task.usage = dict(result["usage"])
            task.tool_log = list(result["tool_log"])
            task.error = result["error"]
            task.status = "completed" if result["ok"] else "failed"
            task.finished_at = utc_now()
            self.artifacts[task_id] = result
            self.working_memory.setdefault(owner_role, {}).update({"last_task": task_id, "last_result": result})
            self.messages.append({"from": owner_role, "task_id": task_id, "kind": "result", "content": result["summary"]})
            return result

    def snapshot(self) -> list[dict]:
        with self.lock:
            rows = []
            for task in self.tasks.values():
                usage = task.usage or {}
                rows.append(
                    {
                        "id": task.id,
                        "role": task.role,
                        "goal": task.goal,
                        "status": task.status,
                        "attempts": task.attempts,
                        "model": usage.get("model", ""),
                        "tokens": int(usage.get("prompt_tokens", 0)) + int(usage.get("completion_tokens", 0)),
                        "cost": f"${float(usage.get('estimated_cost', 0.0)):.6f}",
                        "error": task.error,
                        "dependencies": list(task.dependencies),
                    }
                )
            return rows
