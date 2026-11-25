import unittest

from aether.core import Agent
from aether.core.planning import (
    ExecutionPlan,
    ExecutionStateMachine,
    build_plan,
    classify_request,
    is_resume_request,
)
from aether.core.state import ExecutionCheckpoint, make_checkpoint, restore_plan
from aether.persistence import Store

from tests.base import TempHomeTest


class PlanningTests(unittest.TestCase):
    def test_classify_request_by_complexity(self):
        self.assertEqual(classify_request("Hello")["complexity"], "simple")
        self.assertEqual(classify_request("Write a short note")["complexity"], "moderate")
        self.assertEqual(classify_request("Refactor this repository and run tests")["complexity"], "complex")
        high = classify_request("Delete all records and push to production")
        self.assertEqual(high["complexity"], "high-risk")
        self.assertTrue(high["signals"])

    def test_build_plan_contains_inspectable_fields(self):
        plan = build_plan("Research this repository and run tests", "session_1")
        self.assertEqual(plan.complexity, "complex")
        self.assertEqual(plan.route, ["research", "delegate", "execute", "test", "review"])
        self.assertTrue(plan.constraints)
        self.assertTrue(plan.alternatives)
        self.assertIn("elevated", plan.risk)
        self.assertEqual(plan.get_task("test").dependencies, ["execute"])
        self.assertEqual(plan.get_task("test").verification, "command output is present and interpreted honestly")
        rendered = plan.render()
        self.assertIn("Objective: Research this repository and run tests", rendered)
        self.assertIn("Risk: elevated", rendered)
        self.assertIn("Alternatives:", rendered)
        self.assertIn("[pending] test", rendered)

    def test_state_machine_rejects_invalid_transition(self):
        plan = build_plan("Hello", "session_1")
        with self.assertRaises(Exception):
            ExecutionStateMachine.transition(plan, "completed", "invalid")
        self.assertTrue(ExecutionStateMachine.transition(plan, "running", "accepted"))
        self.assertTrue(ExecutionStateMachine.transition(plan, "paused", "waiting"))

    def test_resume_context_skips_completed_work(self):
        plan = build_plan("Create a file and verify it", "session_1")
        plan.start()
        plan.mark_task("understand", "completed", "objective is clear")
        plan.mark_task("execute", "completed", "write_file succeeded")
        context = plan.resume_context()
        self.assertIn("understand: Clarify the objective", context)
        self.assertIn("execute: Perform the requested work", context)
        self.assertIn("Next step: verify", context)
        self.assertIn("Do not repeat completed non-idempotent work", context)

    def test_revision_records_invalidating_evidence(self):
        plan = build_plan("Run a check", "session_1")
        plan.start()
        task = plan.revise("tool_failure", "test command exited non-zero")
        self.assertEqual(plan.revision, 2)
        self.assertEqual(task.id, "repair_2")
        self.assertEqual(plan.history[-1]["signal"], "tool_failure")
        self.assertEqual(plan.next_task().id, "repair_2")

    def test_resume_request_detection(self):
        self.assertTrue(is_resume_request("resume"))
        self.assertTrue(is_resume_request("Please continue."))
        self.assertFalse(is_resume_request("Continue the migration plan"))

    def test_checkpoint_round_trip(self):
        plan = build_plan("Create a file and verify it", "session_1")
        plan.start()
        plan.mark_task("execute", "completed", "write_file succeeded")
        checkpoint = make_checkpoint(plan, "after write", 1)
        restored = restore_plan(ExecutionCheckpoint.from_dict(checkpoint.to_dict()))
        self.assertEqual(restored.id, plan.id)
        self.assertEqual(restored.status, "running")
        self.assertEqual(restored.get_task("execute").status, "completed")

    def test_plan_serialization_preserves_risk_and_alternatives(self):
        plan = build_plan("Publish the release", "session_1")
        restored = ExecutionPlan.from_dict(plan.to_dict())
        self.assertEqual(restored.risk, plan.risk)
        self.assertEqual(restored.alternatives, plan.alternatives)
        self.assertTrue(restored.approval_required)


class ExecutionPlanStoreTests(TempHomeTest):
    def setUp(self):
        super().setUp()
        self.store = Store(self.home / "state.db")

    def test_plan_and_checkpoint_persist(self):
        plan = build_plan("Create a file and verify it", "session_1")
        plan.start()
        plan.mark_task("execute", "completed", "write_file succeeded")
        self.store.save_execution_plan(plan)
        checkpoint = make_checkpoint(plan, "after write", 1)
        self.store.save_execution_checkpoint(checkpoint)

        stored = self.store.get_execution_plan(plan.id)
        self.assertEqual(stored["objective"], plan.objective)
        self.assertEqual(stored["plan"]["tasks"][1]["status"], "completed")
        self.assertEqual(len(self.store.list_execution_checkpoints(plan.id)), 1)
        latest = self.store.get_latest_execution_checkpoint(plan.id)
        self.assertEqual(latest["note"], "after write")
        self.assertEqual(latest["payload"]["id"], plan.id)

    def test_list_plans_filters_by_session_and_status(self):
        first = build_plan("Hello", "session_1")
        first.start()
        first.complete()
        second = build_plan("Write a note", "session_1")
        second.start()
        third = build_plan("Hello", "session_2")
        third.start()
        for plan in (first, second, third):
            self.store.save_execution_plan(plan)

        rows = self.store.list_execution_plans(session_id="session_1")
        self.assertEqual(len(rows), 2)
        running = self.store.list_execution_plans(session_id="session_1", status="running")
        self.assertEqual([row["id"] for row in running], [second.id])


class PlanningIntegrationTests(TempHomeTest):
    def test_agent_persists_plan_for_simple_turn(self):
        agent = Agent(self.config(), home=self.home, enable_subagents=False)
        result = agent.run_turn("Say hello")

        self.assertEqual(result.exit_reason, "complete")
        self.assertIsNotNone(result.execution_plan)
        self.assertEqual(result.execution_plan["status"], "completed")
        self.assertEqual(result.execution_plan["tasks"][0]["status"], "completed")
        store = Store(self.home / "state.db")
        rows = store.list_execution_plans(session_id=result.session_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], result.execution_plan["id"])
        self.assertGreaterEqual(len(store.list_execution_checkpoints(result.execution_plan["id"])), 2)

    def test_agent_resumes_paused_plan_without_repeating_completed_tool(self):
        script = [
            {
                "content": "Writing the file now.",
                "tool_calls": [
                    {
                        "id": "call_planned_write",
                        "name": "write_file",
                        "arguments": {"path": "planned.txt", "content": "written once"},
                    }
                ],
            }
        ]
        config = self.config(max_iterations=1, providers={"mock": {"script": script}})
        agent = Agent(config, home=self.home, enable_subagents=False, approve_callback=lambda *args: "once")
        first = agent.run_turn("Create a file")

        self.assertEqual(first.exit_reason, "max_iterations")
        self.assertEqual(first.execution_plan["status"], "paused")
        execute = next(item for item in first.execution_plan["tasks"] if item["id"] == "execute")
        self.assertEqual(execute["status"], "completed")

        resumed = Agent(
            self.config(),
            home=self.home,
            session_id=first.session_id,
            enable_subagents=False,
            approve_callback=lambda *args: "once",
        )
        second = resumed.run_turn("resume")

        self.assertEqual(second.execution_plan["id"], first.execution_plan["id"])
        self.assertEqual(second.execution_plan["status"], "completed")
        self.assertEqual(second.execution_plan["revision"], first.execution_plan["revision"])
        self.assertEqual((self.workspace / "planned.txt").read_text(encoding="utf-8"), "written once")
