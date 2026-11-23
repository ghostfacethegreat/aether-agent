import unittest
from types import SimpleNamespace

from aether.errors import SchedulerError
from aether.tasks import Scheduler, SubagentManager, parse_schedule

from tests.base import TempHomeTest


class FakeAgent:
    def run_turn(self, prompt):
        return SimpleNamespace(text=f"handled: {prompt.splitlines()[0]}")


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
        job = scheduler.add_job("check status", "every 1h", name="status")
        self.assertEqual(len(scheduler.list_jobs()), 1)
        job["next_run"] = "2020-01-01T00:00:00+00:00"
        executed = scheduler.tick()
        self.assertEqual(len(executed), 1)
        self.assertEqual(ran, ["check status"])
        self.assertTrue(scheduler.remove_job(job["id"]))
        self.assertEqual(scheduler.list_jobs(), [])

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
