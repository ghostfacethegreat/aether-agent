import json
import unittest

from aether.core import Agent

from tests.base import TempHomeTest


class CodingWorkflowTests(TempHomeTest):
    @staticmethod
    def _payload(record):
        payload = record["result"]
        if isinstance(payload, str):
            try:
                return json.loads(payload)
            except ValueError:
                return {"text": payload}
        return payload

    def _write_fixture(self):
        source = self.workspace / "src" / "demo.py"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
        tests = self.workspace / "tests"
        tests.mkdir(parents=True, exist_ok=True)
        (tests / "__init__.py").write_text("", encoding="utf-8")
        (tests / "test_demo.py").write_text(
            "import unittest\n"
            "from pathlib import Path\n\n\n"
            "class DemoTests(unittest.TestCase):\n"
            "    def test_add_uses_plus(self):\n"
            "        source = Path(__file__).resolve().parents[1] / 'src' / 'demo.py'\n"
            "        self.assertIn('return a + b', source.read_text(encoding='utf-8'))\n",
            encoding="utf-8",
        )
        patch = (
            "--- a/src/demo.py\n"
            "+++ b/src/demo.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def add(a, b):\n"
            "-    return a - b\n"
            "+    return a + b\n"
        )
        return source, patch

    def test_mock_provider_coding_loop_is_really_executed(self):
        source, patch = self._write_fixture()
        script = [
            {
                "content": "I will inspect the repository for the add implementation.",
                "tool_calls": [
                    {"id": "inspect", "name": "repo_index", "arguments": {"action": "search", "query": "def add"}}
                ],
            },
            {
                "content": "The index identifies src/demo.py; I will record the plan.",
                "tool_calls": [
                    {"id": "plan", "name": "todo", "arguments": {"plan": "inspect; preview; reproduce; patch; retest; verify"}}
                ],
            },
            {
                "content": "I will preview the smallest possible patch.",
                "tool_calls": [{"id": "preview", "name": "patch_preview", "arguments": {"patch": patch}}],
            },
            {
                "content": "I will run the focused test before changing code.",
                "tool_calls": [{"id": "failing", "name": "test_run", "arguments": {"mode": "module", "module": "test_demo"}}],
            },
            {
                "content": "The test failed because add uses subtraction; I will apply the reviewed patch.",
                "tool_calls": [{"id": "apply", "name": "patch_apply", "arguments": {"patch": patch}}],
            },
            {
                "content": "I will rerun the focused test after the patch.",
                "tool_calls": [{"id": "passing", "name": "test_run", "arguments": {"mode": "module", "module": "test_demo"}}],
            },
            {"content": "The focused test passes from observed tool output."},
        ]
        config = self.config(max_iterations=10, providers={"mock": {"script": script}})
        approvals = []

        def approve(subject, reason, rule_key, details=None):
            approvals.append({"subject": subject, "reason": reason, "details": details or {}})
            return "once"

        agent = Agent(config, home=self.home, persist=False, approve_callback=approve, enable_subagents=False)
        result = agent.run_turn("Fix the add function and verify it")

        self.assertEqual(result.exit_reason, "complete")
        self.assertIn("return a + b", source.read_text(encoding="utf-8"))
        tools = [record["name"] for record in result.tool_log]
        self.assertEqual(tools, ["repo_index", "todo", "patch_preview", "test_run", "patch_apply", "test_run"])
        self.assertTrue(all(record.get("ok") for record in result.tool_log))
        payloads = [self._payload(record) for record in result.tool_log]
        self.assertGreaterEqual(payloads[0]["match_count"], 1)
        self.assertTrue(any(item["path"] == "src/demo.py" for item in payloads[0]["matches"]))
        self.assertTrue(payloads[2]["valid"])
        self.assertFalse(payloads[2]["writes_performed"])
        approval_subjects = [item["subject"] for item in approvals]
        self.assertTrue(any("test_run" in subject for subject in approval_subjects))
        self.assertTrue(any("patch_apply" in subject for subject in approval_subjects))
        self.assertTrue(any(item["details"].get("fresh") for item in approvals))
        self.assertTrue(
            result.verification["verified"],
            (result.verification, [(item["name"], item.get("ok"), str(item.get("result"))[:2000]) for item in result.tool_log]),
        )
        statuses = {task["id"]: task["status"] for task in result.execution_plan["tasks"]}
        self.assertEqual(statuses["research"], "completed")
        self.assertEqual(statuses["execute"], "completed")
        self.assertEqual(statuses["test"], "completed")
        self.assertEqual(statuses["delegate"], "skipped")
        self.assertEqual(statuses["review"], "skipped")

        def recorded_exit_code(record):
            return self._payload(record)["exit_code"]

        runs = [item for item in result.tool_log if item["name"] == "test_run"]
        self.assertEqual(recorded_exit_code(runs[0]), 1)
        self.assertEqual(recorded_exit_code(runs[-1]), 0)

        verify_script = [
            {
                "content": "Independent verification of the patched test.",
                "tool_calls": [{"id": "verify", "name": "test_run", "arguments": {"mode": "module", "module": "test_demo"}}],
            },
            {"content": "Independent verification passed."},
        ]
        verify_config = self.config(
            max_iterations=4,
            providers={"mock": {"script": verify_script}},
            tool_permissions={
                "allow_tools": ["read_file", "test_run"],
                "deny_tools": ["write_file", "edit_file", "patch_apply", "memory", "skill", "scheduler"],
                "require_approval": ["test_run"],
            },
        )
        verifier = Agent(verify_config, home=self.home, persist=False, approve_callback=lambda *args: "once", enable_subagents=False)
        verified = verifier.run_turn("Independently verify the patch")

        self.assertEqual(verified.exit_reason, "complete")
        self.assertNotEqual(verified.session_id, result.session_id)
        self.assertTrue(verified.verification["verified"])


if __name__ == "__main__":
    unittest.main()
