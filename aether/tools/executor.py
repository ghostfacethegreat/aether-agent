import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from aether.errors import AetherError, ToolError
from aether.utils import redact, truncate

from .registry import ToolRegistry


@dataclass
class ToolExecution:
    name: str
    arguments: dict
    duration: float
    ok: bool
    result: str = ""
    error: str = ""

    def as_dict(self):
        return {
            "name": self.name,
            "arguments": self.arguments,
            "duration": round(self.duration, 3),
            "ok": self.ok,
            "result": truncate(redact(self.result), 2000),
            "error": truncate(redact(self.error), 1000),
        }


class ToolExecutor:
    def __init__(self, registry: ToolRegistry, policy, context=None, on_execute=None, parallel=True):
        self.registry = registry
        self.policy = policy
        self.context = context or {}
        self.on_execute = on_execute
        self.parallel = parallel

    def set_context(self, context: dict) -> None:
        self.context = context

    def _execute_tool(self, tool, name: str, args: dict):
        config = self.context.get("config") or {}
        timeout = tool.timeout if tool.timeout is not None else config.get("tools.timeout", 30)
        if not timeout:
            return self.registry.execute(name, args, self.context)
        box = {}

        def target():
            try:
                box["result"] = self.registry.execute(name, args, self.context)
            except BaseException as exc:
                box["error"] = exc

        worker = threading.Thread(target=target, daemon=True)
        worker.start()
        worker.join(float(timeout))
        if worker.is_alive():
            raise ToolError(f"Tool '{name}' timed out after {float(timeout):g}s")
        if "error" in box:
            raise box["error"]
        return box.get("result", "")

    def _run(self, name: str, args: dict) -> tuple[str, ToolExecution]:
        started = time.monotonic()
        try:
            if not isinstance(args, dict):
                raise ToolError("Tool arguments must be a JSON object")
            tool = self.registry.get(name)
            self.policy.authorize(name, args, tool.risk)
            result = redact(self._execute_tool(tool, name, args))
            execution = ToolExecution(name, args, time.monotonic() - started, True, result=result)
        except AetherError as exc:
            execution = ToolExecution(name, args, time.monotonic() - started, False, error=redact(str(exc)))
        if self.on_execute:
            self.on_execute(execution)
        if execution.ok:
            return execution.result, execution
        return (
            json.dumps(
                {"ok": False, "error": execution.error, "hint": "Fix the arguments or ask the user before retrying."},
                ensure_ascii=False,
            ),
            execution,
        )

    def execute_call(self, call) -> tuple[dict, ToolExecution]:
        name = getattr(call, "name", "")
        args = getattr(call, "arguments", {}) or {}
        raw = getattr(call, "raw_arguments", "") or ""
        if not args and raw.strip():
            try:
                args = json.loads(raw)
            except ValueError:
                args = {}
        result, execution = self._run(name, args)
        message = {
            "role": "tool",
            "tool_call_id": getattr(call, "id", "") or "",
            "name": name,
            "content": result,
        }
        return message, execution

    def execute_batch(self, calls) -> list[tuple[dict, ToolExecution]]:
        results = [None] * len(calls)
        safe_indices = []
        for index, call in enumerate(calls):
            name = getattr(call, "name", "")
            try:
                tool = self.registry.get(name)
            except ToolError:
                continue
            if tool.parallel_safe:
                safe_indices.append(index)
        if self.parallel and len(safe_indices) > 1:
            with ThreadPoolExecutor(max_workers=min(4, len(safe_indices))) as pool:
                futures = {pool.submit(self.execute_call, calls[index]): index for index in safe_indices}
                for future in as_completed(futures):
                    results[futures[future]] = future.result()
        for index, call in enumerate(calls):
            if results[index] is None:
                results[index] = self.execute_call(call)
        return results
