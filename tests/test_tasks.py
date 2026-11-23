import unittest
from types import SimpleNamespace

from aether.errors import SchedulerError
from aether.tasks import Scheduler, SubagentManager, parse_schedule

from tests.base import TempHomeTest


class FakeAgent:
    def run_turn(self, prompt):
        return SimpleNamespace(text=f"handled: {prompt.splitlines()[0]}", exit_reason="complete")


class TaskTests(TempHomeTest):
    def test_parse_schedule(self):
        now = parse_schedule("every 30m")
        self.assertIsNotNone(now)
        iso = parse_schedule("2030-01-01T00:00:00Z")
        self.assertEqual(iso.year, 2030)
        with self.assertRaises(SchedulerError):
            parse_schedule("not a schedule")

    def test_scheduler_round_trip_and_tick(self):
        config = self.config(scheduler={"enabled": True, "tick_seconds": 5})
        ran = []
        scheduler = Scheduler(config, self.home, runner=lambda prompt: ran.append(prompt) or "ok")
        job = scheduler.add_job("check status", "2020-01-01T00:00:00Z", name="status")
        self.assertEqual(len(scheduler.list_jobs()), 1)
        summary = scheduler.tick()
        self.assertEqual(summary["due"], 1)
        self.assertEqual(summary["executed"], 1)
        self.assertEqual(summary["skipped"], 0)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(ran, ["check status"])
        self.assertTrue(summary["outcomes"][0]["run_id"])
        self.assertEqual(len(scheduler.execution_history()), 1)
        self.assertTrue(scheduler.remove_job(job["id"]))
        self.assertEqual(scheduler.list_jobs(), [])

    def test_scheduler_without_runner_reports_skip(self):
        config = self.config(scheduler={"enabled": True})
        scheduler = Scheduler(config, self.home)
        scheduler.add_job("check status", "2020-01-01T00:00:00Z")
        summary = scheduler.tick()
        self.assertEqual(summary["due"], 1)
        self.assertEqual(summary["skipped"], 1)
        self.assertEqual(summary["executed"], 0)
        self.assertIn("no runner", summary["outcomes"][0]["reason"])
        stored = scheduler.list_jobs()[0]
        self.assertIsNone(stored["last_run"])
        self.assertEqual(stored["last_status"], "skipped")
        self.assertEqual(len(scheduler.due_jobs()), 1)

    def test_scheduler_claim_survives_restart(self):
        config = self.config(scheduler={"enabled": True})
        first = Scheduler(config, self.home, runner=lambda prompt: "done")
        first.add_job("check status", "2020-01-01T00:00:00Z")
        self.assertEqual(first.tick()["executed"], 1)
        second = Scheduler(config, self.home)
        self.assertEqual(second.due_jobs(), [])
        self.assertEqual(len(second.execution_history()), 1)

    def test_scheduler_records_failed_execution(self):
        config = self.config(scheduler={"enabled": True})

        def fail(prompt):
            raise RuntimeError("boom")

        scheduler = Scheduler(config, self.home, runner=fail)
        scheduler.add_job("check status", "2020-01-01T00:00:00Z")
        summary = scheduler.tick()
        self.assertEqual(summary["failed"], 1)
        self.assertIn("boom", summary["outcomes"][0]["error"])
        self.assertEqual(scheduler.list_jobs()[0]["last_status"], "failed")
        self.assertEqual(scheduler.execution_history()[0]["status"], "failed")

    def test_scheduler_pause_resume_and_update(self):
        config = self.config(scheduler={"enabled": True})
        scheduler = Scheduler(config, self.home, runner=lambda prompt: "ok")
        job = scheduler.add_job("check status", "2030-01-01T00:00:00Z")
        self.assertIsNotNone(scheduler.set_enabled(job["id"], False))
        self.assertEqual(scheduler.due_jobs(), [])
        self.assertIsNotNone(scheduler.set_enabled(job["id"], True))
        updated = scheduler.update_job(job["id"], prompt="new prompt", schedule="2020-01-01T00:00:00Z")
        self.assertEqual(updated["prompt"], "new prompt")
        self.assertEqual(len(scheduler.due_jobs()), 1)

    def test_scheduler_thread_start_and_stop(self):
        config = self.config(scheduler={"enabled": True, "tick_seconds": 5})
        scheduler = Scheduler(config, self.home, runner=lambda prompt: "ok")
        scheduler.start()
        self.assertIsNotNone(scheduler._thread)
        scheduler.stop()
        self.assertIsNone(scheduler._thread)

    def test_subagents_run_parallel_results(self):
        manager = SubagentManager(lambda parent, task: FakeAgent(), max_workers=2)
        results = manager.run(
            [{"goal": "task one"}, {"goal": "task two"}],
            {"session_id": "s1"},
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["result"], "handled: task one")
        self.assertTrue(all(item["ok"] for item in results))


if __name__ == "__main__":
    unittest.main()
