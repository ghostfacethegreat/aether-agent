import unittest
from pathlib import Path

from aether.errors import ApprovalRequired, PermissionDenied, ToolError
from aether.providers.base import ToolCall
from aether.tools import PermissionPolicy, ToolExecutor, default_registry

from tests.base import TempHomeTest


class ToolTests(TempHomeTest):
    def setUp(self):
        super().setUp()
        (self.workspace / "note.txt").write_text("hello\n", encoding="utf-8")
        self.registry = default_registry()

    def context(self):
        return {
            "workspace": self.workspace,
            "config": self.config(),
            "home": self.home,
        }

    def test_registry_requires_arguments(self):
        with self.assertRaises(ToolError):
            self.registry.execute("read_file", {}, self.context())

    def test_executor_success(self):
        policy = PermissionPolicy(self.config(), workspace=self.workspace)
        executor = ToolExecutor(self.registry, policy, self.context())
        message, execution = executor.execute_call(ToolCall("c1", "read_file", {"path": "note.txt"}))
        self.assertTrue(execution.ok)
        self.assertIn("hello", message["content"])
        self.assertEqual(message["tool_call_id"], "c1")

    def test_executor_reports_unknown_tool(self):
        policy = PermissionPolicy(self.config(), workspace=self.workspace)
        executor = ToolExecutor(self.registry, policy, self.context())
        _, execution = executor.execute_call(ToolCall("c2", "not_a_tool", {}))
        self.assertFalse(execution.ok)
        self.assertIn("Unknown tool", execution.error)

    def test_approval_required_without_callback(self):
        config = self.config(tool_permissions={"require_approval": ["read_file"]})
        policy = PermissionPolicy(config, workspace=self.workspace)
        executor = ToolExecutor(self.registry, policy, self.context())
        _, execution = executor.execute_call(ToolCall("c3", "read_file", {"path": "note.txt"}))
        self.assertFalse(execution.ok)
        self.assertIn("Approval required", execution.error)

    def test_destructive_command_denied_in_strict_mode(self):
        config = self.config(tool_permissions={"mode": "strict", "require_approval": [], "allow_destructive": False})
        policy = PermissionPolicy(config, workspace=self.workspace)
        executor = ToolExecutor(self.registry, policy, self.context())
        _, execution = executor.execute_call(ToolCall("c4", "terminal", {"command": "rm -rf /tmp/aether-test"}))
        self.assertFalse(execution.ok)
        self.assertIsInstance(execution.error, str)
        self.assertIn("Destructive", execution.error)

    def test_approval_callback_can_grant(self):
        config = self.config(tool_permissions={"require_approval": ["read_file"]})
        policy = PermissionPolicy(config, workspace=self.workspace, approve_callback=lambda *args: "once")
        executor = ToolExecutor(self.registry, policy, self.context())
        _, execution = executor.execute_call(ToolCall("c5", "read_file", {"path": "note.txt"}))
        self.assertTrue(execution.ok)

    def test_parallel_execution(self):
        policy = PermissionPolicy(self.config(), workspace=self.workspace)
        executor = ToolExecutor(self.registry, policy, self.context(), parallel=True)
        calls = [ToolCall("a", "read_file", {"path": "note.txt"}), ToolCall("b", "read_file", {"path": "note.txt"})]
        results = executor.execute_batch(calls)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(execution.ok for _, execution in results))


if __name__ == "__main__":
    unittest.main()
