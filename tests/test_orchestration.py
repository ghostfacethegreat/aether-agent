import os
import threading
import time
import unittest
from concurrent.futures import Future
from unittest.mock import patch

from aether.config import Config
from aether.core import Agent, TurnResult
from aether.core.loop import TurnState, _cost_limit, new_spend_budget
from aether.errors import OrchestratorError, ProviderError
from aether.orchestration import OrchestrationRun, OrchestrationTask, SharedTaskState
from aether.orchestration.roles import resolved_roles
from aether.orchestration.orchestrator import ActiveRun, Orchestrator

from tests.base import TempHomeTest


class OrchestrationTests(TempHomeTest):
    def _success(self, text='{"summary":"ok"}', tokens=10):
        return TurnResult(
            text=text,
            session_id="child",
            provider="mock",
            model="mock-standard",
            usage={"prompt_tokens": tokens, "completion_tokens": tokens, "estimated_cost": 0.0},
            exit_reason="complete",
        )

    def test_sequential_dependency_execution(self):
        events = []
        lock = threading.Lock()
        roles = [{"role": "researcher"}, {"role": "reviewer", "depends_on": ["researcher"]}]

        def run_turn(agent, user_input, *args, **kwargs):
            role = "reviewer" if "(reviewer)" in user_input else "researcher"
            with lock:
                events.append(role)
            return self._success()

        agent = Agent(self.config(), home=self.home)
        with patch.object(Agent, "run_turn", run_turn):
            run = agent.orchestrator.run("Compare notes", roles=roles)
        self.assertEqual(run.status, "completed")
        self.assertEqual(events, ["researcher", "reviewer"])

    def test_parallel_execution(self):
        barrier = threading.Barrier(2)

        def run_turn(agent, user_input, *args, **kwargs):
            try:
                barrier.wait(timeout=2)
            except threading.BrokenBarrierError:
                return self._success(text='{"summary":"barrier failed"}')
            return self._success()

        agent = Agent(self.config(), home=self.home)
        with patch.object(Agent, "run_turn", run_turn):
            run = agent.orchestrator.run("Compare notes in parallel", roles=["researcher", "reviewer"])
        self.assertEqual(run.status, "completed")
        results = [task.result["summary"] for task in run.tasks.values()]
        self.assertNotIn("barrier failed", results)

    def test_shared_budget_across_children(self):
        agent = Agent(self.config(), home=self.home)
        run = agent.orchestrator.run("Explain local caching")
        self.assertEqual(run.status, "completed")
        tasks_usage = sum(int(task.usage.get("prompt_tokens", 0)) for task in run.tasks.values())
        with agent.spend_budget["lock"]:
            shared_usage = agent.spend_budget["usage"]["prompt_tokens"]
        self.assertGreaterEqual(shared_usage, tasks_usage)
        self.assertGreaterEqual(shared_usage, 20)

    def test_nested_budget_limit_cannot_be_increased(self):
        config = self.config(costs={"max_estimated_usd_per_turn": 100.0})
        budget = new_spend_budget(0.01)
        state = TurnState(
            messages=[],
            system_prompt="",
            tools=[],
            provider_candidates=[],
            provider_manager=None,
            context_manager=None,
            executor=None,
            config=config,
            spend_budget=budget,
        )
        self.assertEqual(_cost_limit(state), 0.01)
        self.assertEqual(budget["limit"], 0.01)

    def test_paid_roles_are_gated(self):
        config = self.config(
            costs={"confirm_paid": True},
            orchestrator={"allow_paid": False, "roles": {"researcher": {"provider": "openai", "model": "gpt-4o-mini"}}},
        )
        agent = Agent(config, home=self.home)
        with patch.dict(os.environ, {"AETHER_CONFIRM_PAID": ""}):
            run = agent.orchestrator.run("Research paid provider output", roles=["researcher"])
        task = next(iter(run.tasks.values()))
        self.assertEqual(run.status, "partial")
        self.assertEqual(task.status, "failed")
        self.assertIn("billable provider", task.error)

    def test_cancellation_marks_active_run(self):
        agent = Agent(self.config(), home=self.home)
        orchestrator = agent.orchestrator
        started = threading.Event()
        release = threading.Event()
        result = {}

        def execute_plan(active, mode):
            result["run_id"] = active.run.id
            started.set()
            release.wait(timeout=2)

        orchestrator._execute_plan = execute_plan
        thread = threading.Thread(target=lambda: result.update(run=orchestrator.run("Cancel this")))
        thread.start()
        self.assertTrue(started.wait(timeout=2))
        self.assertTrue(orchestrator.cancel(result["run_id"]))
        release.set()
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result["run"].status, "cancelled")
        self.assertTrue(all(task.status == "cancelled" for task in result["run"].tasks.values()))

    def test_cancel_event_propagates_to_child_turn(self):
        agent = Agent(self.config(), home=self.home)
        cancel_event = threading.Event()
        task = OrchestrationTask(id="task_cancel", role="researcher", goal="Research")
        role_settings = resolved_roles(agent.config)["researcher"]
        child = agent._orchestration_child(role_settings, task.to_dict(), {}, cancel_event)
        cancel_event.set()
        result = child.run_turn("Research")
        self.assertEqual(result.exit_reason, "cancelled")

    def test_timeout_marks_task_timed_out(self):
        agent = Agent(self.config(), home=self.home)
        orchestrator = agent.orchestrator
        state = SharedTaskState("run_timeout", "Objective")
        task = OrchestrationTask(id="task_timeout", role="researcher", goal="Research", status="running")
        state.add_task(task)
        run = OrchestrationRun(id="run_timeout", objective="Objective", mode="parallel", status="running")
        run.tasks = state.tasks
        active = ActiveRun(run=run, state=state, cancel_event=threading.Event())
        future = Future()
        active.futures[future] = task.id
        active.started[task.id] = time.monotonic() - 100
        with patch.object(orchestrator, "_int_setting", return_value=1):
            orchestrator._enforce_timeouts(active)
        self.assertEqual(task.status, "timed_out")
        self.assertTrue(future.cancelled())

    def test_permissions_are_narrowed_for_children(self):
        config = self.config(
            tool_permissions={
                "mode": "standard",
                "allow_tools": ["read_file", "list_directory"],
                "deny_tools": ["web_search"],
                "require_approval": [],
            }
        )
        agent = Agent(config, home=self.home)
        role = {
            "allowed_tools": ["read_file", "web_search", "terminal"],
            "deny_tools": ["terminal"],
            "system_prompt": "Focused worker",
            "max_iterations": 2,
        }
        task = OrchestrationTask(id="task_permissions", role="researcher", goal="Research")
        child = agent._orchestration_child(role, task.to_dict(), {}, threading.Event())
        self.assertEqual(child.config.get("tool_permissions.mode"), "strict")
        self.assertFalse(child.policy.check("web_search", {}, risk="network").allowed)
        self.assertFalse(child.policy.check("terminal", {}, risk="execute").allowed)
        self.assertTrue(child.policy.check("read_file", {}, risk="low").allowed)
        self.assertIn("orchestrate_task", child.config.get("tool_permissions.deny_tools", []))

    def test_concurrent_task_isolation_and_communication(self):
        state = SharedTaskState("run_shared", "Objective")
        first = OrchestrationTask(id="task_first", role="researcher", goal="Research")
        second = OrchestrationTask(id="task_second", role="reviewer", goal="Review", dependencies=[first.id])
        state.add_task(first)
        state.add_task(second)
        state.publish(first.id, "researcher", {"ok": True, "summary": "research finding", "output": {"evidence": "local cache"}})
        state.publish(second.id, "reviewer", {"ok": True, "summary": "review complete"})
        with self.assertRaises(OrchestratorError):
            state.publish(first.id, "reviewer", {"ok": True, "summary": "overwrite"})
        self.assertEqual(state.get(first.id).result["owner"], "researcher")
        self.assertIn("[researcher]", state.dependency_context(second))
        self.assertIn("local cache", state.dependency_context(second))
        self.assertEqual(len(state.messages), 2)

    def test_persistent_run_recovery(self):
        agent = Agent(self.config(), home=self.home)
        run = agent.orchestrator.run("Explain local caching")
        loaded = agent.orchestrator.load(run.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.objective, run.objective)
        self.assertEqual(len(loaded.tasks), 2)
        self.assertTrue(loaded.root_task_id)

    def test_persisted_run_can_be_cancelled(self):
        agent = Agent(self.config(), home=self.home)
        run = agent.orchestrator.run("Explain local caching")
        detached = Orchestrator(None, agent.config, store=agent.store)
        self.assertTrue(detached.cancel(run.id))
        loaded = detached.load(run.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.status, "cancelled")

    def test_retryable_failure_is_retried(self):
        calls = []

        def run_turn(agent, user_input, *args, **kwargs):
            calls.append(user_input)
            if len(calls) == 1:
                raise ProviderError("temporary", provider="mock", retryable=True)
            return self._success()

        agent = Agent(self.config(orchestrator={"retries": 1}), home=self.home)
        with patch.object(Agent, "run_turn", run_turn):
            run = agent.orchestrator.run("Research recovery", roles=["researcher"])
        self.assertEqual(run.status, "completed")
        task = next(iter(run.tasks.values()))
        self.assertEqual(task.attempts, 2)
        self.assertEqual(task.status, "completed")

    def test_non_retryable_failure_is_reported(self):
        config = self.config(
            providers={"mock": {"script": [{"error": "permanent", "retryable": False}]}},
            orchestrator={"retries": 0},
        )
        agent = Agent(config, home=self.home)
        run = agent.orchestrator.run("Research failure", roles=["researcher"])
        self.assertEqual(run.status, "partial")
        task = next(iter(run.tasks.values()))
        self.assertEqual(task.status, "failed")
        self.assertIn("failures: 1", run.final_report)

    def test_invalid_orchestrator_config_is_reported(self):
        config = Config(
            {
                "orchestrator": {
                    "mode": "chaos",
                    "max_children": -1,
                    "roles": [],
                }
            }
        )
        warnings = config.validate()
        self.assertTrue(any("orchestrator.mode" in warning for warning in warnings))
        self.assertTrue(any("orchestrator.max_children" in warning for warning in warnings))
        self.assertTrue(any("orchestrator.roles" in warning for warning in warnings))


if __name__ == "__main__":
    unittest.main()
