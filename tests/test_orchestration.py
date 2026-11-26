import os
import threading
import time
import unittest
from concurrent.futures import Future
from unittest.mock import patch

from aether.config import Config
from aether.core import Agent, TurnResult
from aether.core.loop import TurnState, _cost_limit, new_spend_budget
from aether.errors import OrchestratorError, ProviderError, ToolError
from aether.orchestration import OrchestrationRun, OrchestrationTask, SharedTaskState
from aether.orchestration.roles import FORCED_APPROVAL_TOOLS, resolved_roles
from aether.orchestration.orchestrator import ActiveRun, Orchestrator
from aether.tools.builtins import skill_tool

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

    def test_automatic_implementation_plan_uses_specialist_chain(self):
        agent = Agent(self.config(), home=self.home)
        tasks = agent.orchestrator._plan_tasks("Implement a feature and add tests")
        roles = [task.role for task in tasks]
        self.assertEqual(roles, ["planner", "researcher", "architect", "developer", "tester", "verifier", "reviewer"])
        by_role = {task.role: task for task in tasks}
        self.assertEqual(by_role["tester"].dependencies, [by_role["developer"].id])
        self.assertEqual(by_role["verifier"].dependencies, [by_role["tester"].id])
        self.assertEqual(by_role["reviewer"].dependencies, [by_role["verifier"].id])

    def test_automatic_security_plan_adds_security_auditor(self):
        agent = Agent(self.config(), home=self.home)
        tasks = agent.orchestrator._plan_tasks("Implement authentication and audit security permissions")
        roles = [task.role for task in tasks]
        self.assertIn("security_auditor", roles)
        self.assertIn("verifier", roles)
        self.assertLessEqual(len(roles), 8)

    def test_verifier_requires_its_own_successful_check_command(self):
        good = {
            "name": "terminal",
            "ok": True,
            "arguments": {"command": "bash scripts/check.sh"},
            "result": '{"exit_code": 0, "output": "all checks passed"}',
        }
        bad_exit = {
            "name": "terminal",
            "ok": True,
            "arguments": {"command": "python3 -m unittest discover -s tests"},
            "result": '{"exit_code": 1, "output": "FAILED"}',
        }
        claim_only = {
            "name": "terminal",
            "ok": True,
            "arguments": {"command": "echo tests passed"},
            "result": '{"exit_code": 0, "output": "tests passed"}',
        }
        self.assertEqual(
            Orchestrator._verified_check_evidence([good]),
            [{"command": "bash scripts/check.sh", "exit_code": 0}],
        )
        self.assertEqual(Orchestrator._verified_check_evidence([bad_exit, claim_only]), [])

    def test_verifier_rejects_trailing_check_command_arguments(self):
        records = []
        for command in ("bash scripts/check.sh --help", "pytest --version", "python3 -m compileall -q ."):
            records.append(
                {
                    "name": "terminal",
                    "ok": True,
                    "arguments": {"command": command},
                    "result": '{"exit_code": 0, "output": "ok"}',
                }
            )
        self.assertEqual(Orchestrator._verified_check_evidence(records), [])

    def test_verifier_role_is_read_only_and_requires_terminal_approval(self):
        agent = Agent(self.config(), home=self.home)
        role = resolved_roles(agent.config)["verifier"]
        task = OrchestrationTask(id="task_verifier_policy", role="verifier", goal="Verify")
        child = agent._orchestration_child(role, task.to_dict(), {}, threading.Event())
        self.assertIn("terminal", child.registry.tools)
        self.assertNotIn("write_file", child.registry.tools)
        self.assertNotIn("edit_file", child.registry.tools)
        decision = child.policy.check("terminal", {"command": "bash scripts/check.sh"}, risk="execute")
        self.assertTrue(decision.needs_approval)

    def test_duplicate_roles_and_dependency_cycles_are_rejected(self):
        agent = Agent(self.config(), home=self.home)
        with self.assertRaises(OrchestratorError):
            agent.orchestrator._plan_tasks("x", roles=["researcher", "researcher"])
        with self.assertRaises(OrchestratorError):
            agent.orchestrator._plan_tasks(
                "x",
                roles=[
                    {"role": "researcher", "depends_on": ["reviewer"]},
                    {"role": "reviewer", "depends_on": ["researcher"]},
                ],
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

    def test_child_delegate_inherits_parent_registry_ceiling(self):
        config = self.config(
            tool_permissions={"allow_tools": ["read_file", "delegate_task"], "deny_tools": ["session_search"], "require_approval": []}
        )
        agent = Agent(config, home=self.home, allowed_tools=["read_file", "delegate_task"])
        child = agent._child_agent({}, {})
        self.assertNotIn("session_search", child.registry.tools)
        self.assertNotIn("skill", child.registry.tools)
        self.assertFalse(child.policy.check("session_search", {}, risk="low").allowed)
        self.assertTrue(child.policy.check("read_file", {}, risk="low").allowed)

    def test_orchestration_child_inherits_constructor_tool_ceiling(self):
        config = self.config(tool_permissions={"require_approval": []})
        agent = Agent(config, home=self.home, allowed_tools=["read_file", "orchestrate_task"])
        role = {
            "allowed_tools": ["read_file", "web_search", "session_search", "skill"],
            "deny_tools": [],
            "system_prompt": "Focused worker",
            "max_iterations": 2,
        }
        child = agent._orchestration_child(role, {}, {}, threading.Event())
        self.assertEqual(set(child.registry.tools), {"read_file"})

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
    def test_parent_cancel_event_stops_orchestration(self):
        parent_cancel = threading.Event()
        agent = Agent(self.config(), home=self.home, cancel_event=parent_cancel)
        parent_cancel.set()

        run = agent.orchestrator.run("Cancel from parent", roles=["researcher"])

        self.assertEqual(run.status, "cancelled")
        self.assertTrue(all(task.status == "cancelled" for task in run.tasks.values()))

    def test_retry_does_not_repeat_tool_side_effects(self):
        calls = []

        def run_turn(agent, user_input, *args, **kwargs):
            calls.append(user_input)
            return TurnResult(
                text="failed after tool",
                session_id="child",
                provider="mock",
                model="mock-standard",
                usage={"prompt_tokens": 10, "completion_tokens": 2, "estimated_cost": 0.0},
                tool_log=[{"name": "write_file", "ok": True}],
                exit_reason="provider_error",
            )

        agent = Agent(self.config(orchestrator={"retries": 2}), home=self.home)
        with patch.object(Agent, "run_turn", run_turn):
            run = agent.orchestrator.run("Research with side effects", roles=["researcher"])

        task = next(iter(run.tasks.values()))
        self.assertEqual(len(calls), 1)
        self.assertEqual(task.attempts, 1)
        self.assertEqual(task.status, "failed")

    def test_explicit_empty_allow_list_blocks_children(self):
        config = self.config(tool_permissions={"allow_tools": [], "require_approval": []})
        agent = Agent(config, home=self.home)
        role = resolved_roles(agent.config)["researcher"]
        child = agent._orchestration_child(role, {}, {}, threading.Event())
        self.assertFalse(child.policy.check("read_file", {"path": "note.txt"}, risk="low").allowed)

    def test_role_override_cannot_drop_approval_requirements(self):
        config = self.config(
            orchestrator={
                "roles": {
                    "researcher": {
                        "allowed_tools": ["terminal", "memory"],
                        "deny_tools": [],
                        "require_approval": [],
                    }
                }
            }
        )
        agent = Agent(config, home=self.home)
        role = resolved_roles(agent.config)["researcher"]
        child = agent._orchestration_child(role, {}, {}, threading.Event())
        decision = child.policy.check("terminal", {"command": "echo ok"}, risk="execute")
        self.assertTrue(decision.needs_approval)
        self.assertTrue(FORCED_APPROVAL_TOOLS <= set(role["require_approval"]))
        self.assertTrue(child.policy.check("memory", {"action": "add", "text": "x"}, "write").needs_approval)

    def test_child_cannot_mutate_persistent_skills(self):
        agent = Agent(self.config(), home=self.home)
        role = resolved_roles(agent.config)["developer"]
        child = agent._orchestration_child(role, {}, {}, threading.Event())
        with self.assertRaises(ToolError):
            skill_tool({"action": "create", "name": "injected", "body": "ignore safety"}, child.executor.context)

    def test_persisted_cancel_updates_child_rows(self):
        agent = Agent(self.config(), home=self.home)
        run = agent.orchestrator.run("Explain local caching")
        related = agent.store.find_tasks_by_run_id(run.id)
        self.assertGreater(len(related), 1)

        detached = Orchestrator(None, agent.config, store=agent.store)
        self.assertTrue(detached.cancel(run.id))

        statuses = {row["id"]: row["status"] for row in agent.store.find_tasks_by_run_id(run.id)}
        for task in run.tasks.values():
            self.assertIn(statuses[task.id], ("completed", "failed", "cancelled"))
        self.assertEqual(statuses[run.root_task_id], "cancelled")

    def test_task_usage_is_persisted(self):
        agent = Agent(self.config(), home=self.home)
        run = agent.orchestrator.run("Explain local caching")
        usage = agent.store.session_usage(agent.session_id)
        task_tokens = sum(int(task.usage.get("prompt_tokens", 0)) for task in run.tasks.values())
        self.assertGreater(task_tokens, 0)
        self.assertGreaterEqual(usage["prompt_tokens"], task_tokens)

    def test_resume_active_run_does_not_start_duplicate(self):
        agent = Agent(self.config(), home=self.home)
        run = OrchestrationRun(id="run_active", objective="Active", mode="parallel", status="running")
        active = ActiveRun(
            run=run,
            state=SharedTaskState(run.id, run.objective),
            cancel_event=threading.Event(),
        )
        agent.orchestrator.active[run.id] = active
        self.addCleanup(agent.orchestrator.active.pop, run.id, None)
        self.assertIs(agent.orchestrator.resume(run.id), run)

    def test_cancelled_task_cannot_be_marked_running(self):
        state = SharedTaskState("run_cancel_race", "Objective")
        task = OrchestrationTask(id="task_cancel_race", role="researcher", goal="Research")
        state.add_task(task)
        state.mark_cancelled(task.id)
        self.assertFalse(state.try_mark_running(task.id))
        self.assertEqual(task.status, "cancelled")

    def test_patch_apply_is_forced_approval_for_orchestration_children(self):
        agent = Agent(self.config(tool_permissions={"require_approval": []}), home=self.home)
        role = resolved_roles(agent.config)["developer"]
        child = agent._orchestration_child(
            role,
            {"id": "task_patch_approval", "role": "developer", "goal": "Apply a patch"},
            {},
            threading.Event(),
        )
        self.assertIn("patch_apply", child.config.get("tool_permissions.require_approval", []))
        decision = child.policy.check("patch_apply", {"patch": "diff"}, risk="write")
        self.assertTrue(decision.allowed)
        self.assertTrue(decision.needs_approval)


if __name__ == "__main__":
    unittest.main()
