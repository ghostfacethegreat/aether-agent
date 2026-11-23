import io
import json
import unittest
from contextlib import redirect_stdout

from aether.cli.app import main
from aether.config import load_config

from tests.base import TempHomeTest


class CliTests(TempHomeTest):
    def run_cli(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(argv)
        return code, buffer.getvalue()

    def test_version_command(self):
        code, output = self.run_cli(["version"])
        self.assertEqual(code, 0)
        self.assertIn("0.1.0", output)

    def test_providers_command(self):
        code, output = self.run_cli(["providers"])
        self.assertEqual(code, 0)
        self.assertIn("ollama", output)
        self.assertIn("paid", output)

    def test_config_set_and_get(self):
        code, _ = self.run_cli(["config", "set", "personality", "Be brief."])
        self.assertEqual(code, 0)
        config = load_config(self.home / "config.json")
        self.assertEqual(config.get("personality"), "Be brief.")
        code, output = self.run_cli(["config", "get", "personality"])
        self.assertEqual(code, 0)
        self.assertIn("Be brief.", output)

    def test_memory_cli(self):
        code, _ = self.run_cli(["memory", "add", "likes tea", "--category", "preferences"])
        self.assertEqual(code, 0)
        code, output = self.run_cli(["memory", "list"])
        self.assertEqual(code, 0)
        self.assertIn("likes tea", output)

    def test_run_with_mock(self):
        code, output = self.run_cli(["--provider", "mock", "run", "Say hello"])
        self.assertEqual(code, 0)
        self.assertIn("mock provider is active", output)
        self.assertIn("mock/mock-standard", output)

    def test_status_with_mock(self):
        code, output = self.run_cli(["--provider", "mock", "status"])
        self.assertEqual(code, 0)
        self.assertIn("mock (local)", output)
        self.assertIn("mock-standard", output)

    def test_schedule_tick_reports_summary(self):
        code, output = self.run_cli(["--provider", "mock", "schedule", "tick"])
        self.assertEqual(code, 0)
        self.assertIn("Due", output)
        self.assertIn("Executed", output)
        self.assertIn("Skipped", output)
        self.assertIn("Failed", output)


if __name__ == "__main__":
    unittest.main()
