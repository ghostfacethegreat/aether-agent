from concurrent.futures import ThreadPoolExecutor, as_completed

from aether.utils import redact


class SubagentManager:
    def __init__(self, agent_factory, store=None, max_workers=3):
        self.agent_factory = agent_factory
        self.store = store
        self.max_workers = max(1, int(max_workers))

    def _run_one(self, task, parent_context):
        goal = str(task.get("goal") or "").strip()
        if not goal:
            return {"ok": False, "error": "Task goal is required", "goal": goal}
        task_id = ""
        if self.store:
            task_id = self.store.create_task(
                title=goal[:120],
                session_id=parent_context.get("session_id", ""),
                parent_id=parent_context.get("parent_id", ""),
                metadata={"role": task.get("role", "worker"), "context": redact(str(task.get("context") or ""))[:2000]},
            )
        try:
            child = self.agent_factory(parent_context, task)
            prompt = goal
            if task.get("context"):
                prompt += "\n\nContext:\n" + str(task["context"])
            result = child.run_turn(prompt)
            text = result.text
            if self.store:
                self.store.update_task(task_id, "completed", text)
            return {
                "ok": True,
                "task_id": task_id,
                "role": task.get("role", "worker"),
                "goal": goal,
                "result": text,
            }
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            if self.store:
                self.store.update_task(task_id, "failed", message)
            return {"ok": False, "task_id": task_id, "goal": goal, "error": redact(message)}

    def run(self, tasks, parent_context):
        if not tasks:
            return []
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(tasks))) as pool:
            futures = [pool.submit(self._run_one, task, parent_context) for task in tasks]
            results = [future.result() for future in as_completed(futures)]
        order = {str(task.get("goal") or ""): index for index, task in enumerate(tasks)}
        return sorted(results, key=lambda item: order.get(str(item.get("goal") or ""), 999))

    def resume(self, task_id, parent_context):
        task = self.store.get_task(task_id) if self.store else None
        if not task:
            return {"ok": False, "error": f"Task '{task_id}' not found"}
        metadata = task.get("metadata")
        if isinstance(metadata, str):
            import json

            try:
                metadata = json.loads(metadata)
            except ValueError:
                metadata = {}
        return self._run_one({"goal": task.get("result") or task.get("title") or "", "context": (metadata or {}).get("context", "")}, parent_context)
