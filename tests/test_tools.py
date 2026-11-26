import os
import time
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from aether.errors import ApprovalRequired, PermissionDenied, ToolError
from aether.providers.base import ToolCall
from aether.tools import PermissionPolicy, Tool, ToolExecutor, ToolRegistry, default_registry
from aether.tools.builtins import _SafeRedirectHandler, _fetch_url

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

    def test_executor_enforces_tool_timeout(self):
        config = self.config(tools={"timeout": 0.05})
        policy = PermissionPolicy(config, workspace=self.workspace)
        registry = ToolRegistry()
        registry.register(Tool("slow", "Slow tool", {"type": "object"}, lambda args, context: time.sleep(2), "low"))
        context = self.context()
        context["config"] = config
        executor = ToolExecutor(registry, policy, context)
        _, execution = executor.execute_call(ToolCall("t1", "slow", {}))
        self.assertFalse(execution.ok)
        self.assertIn("timed out", execution.error)

    def test_executor_redacts_model_facing_result(self):
        with patch.dict(os.environ, {"AETHER_TEST_SERVICE_API_KEY": "abcdefgh123456"}):
            policy = PermissionPolicy(self.config(), workspace=self.workspace)
            registry = ToolRegistry()
            registry.register(
                Tool(
                    "leak",
                    "Leaks a secret",
                    {"type": "object"},
                    lambda args, context: "api_key=abcdefgh123456 token sk-abcdefghijklmnop",
                    "low",
                )
            )
            executor = ToolExecutor(registry, policy, self.context())
            message, execution = executor.execute_call(ToolCall("t2", "leak", {}))
            self.assertTrue(execution.ok)
            self.assertNotIn("abcdefgh123456", message["content"])
            self.assertNotIn("sk-abcdefghijklmnop", message["content"])
            self.assertIn("[REDACTED]", message["content"])

    def test_web_fetch_rejects_private_url(self):
        with self.assertRaises(ToolError):
            _fetch_url("http://127.0.0.1:8080")

    def test_redirects_to_private_url_are_blocked(self):
        handler = _SafeRedirectHandler()
        request = urllib.request.Request("https://example.com")
        with self.assertRaises(ToolError):
            handler.redirect_request(request, None, 302, "Found", {}, "http://127.0.0.1/")

    def test_strict_mode_checks_terminal_cwd_and_git_paths(self):
        config = self.config(tool_permissions={"mode": "strict", "require_approval": []})
        policy = PermissionPolicy(config, workspace=self.workspace)
        terminal = policy.check("terminal", {"command": "pwd", "cwd": str(self.root / "outside")}, "execute")
        self.assertFalse(terminal.allowed)
        git_add = policy.check("git", {"subcommand": "add", "paths": ["../../outside.txt"]}, "execute")
        self.assertFalse(git_add.allowed)
    def test_once_approval_is_not_cached(self):
        config = self.config(tool_permissions={"require_approval": ["read_file"]})
        answers = iter(["once", "no"])
        policy = PermissionPolicy(config, workspace=self.workspace, approve_callback=lambda *args: next(answers))
        executor = ToolExecutor(self.registry, policy, self.context())

        first, _ = executor.execute_call(ToolCall("once1", "read_file", {"path": "note.txt"}))
        second, execution = executor.execute_call(ToolCall("once2", "read_file", {"path": "note.txt"}))

        self.assertNotIn('"ok": false', first["content"])
        self.assertFalse(execution.ok)
        self.assertIn("denied", execution.error)
        self.assertIn('"ok": false', second["content"])

    def test_session_approval_is_scoped_to_exact_arguments(self):
        (self.workspace / "other.txt").write_text("other\n", encoding="utf-8")
        config = self.config(tool_permissions={"require_approval": ["read_file"]})
        answers = iter(["session", "no"])
        policy = PermissionPolicy(config, workspace=self.workspace, approve_callback=lambda *args: next(answers))
        executor = ToolExecutor(self.registry, policy, self.context())

        executor.execute_call(ToolCall("scope1", "read_file", {"path": "note.txt"}))
        _, execution = executor.execute_call(ToolCall("scope2", "read_file", {"path": "other.txt"}))

        self.assertFalse(execution.ok)
        self.assertIn("denied", execution.error)

    def test_persistent_mutations_require_approval_even_when_config_omits_tool_list(self):
        config = self.config(tool_permissions={"require_approval": []})
        policy = PermissionPolicy(config, workspace=self.workspace)
        cases = [
            ("patch_apply", {"patch": "diff"}),
            ("memory", {"action": "add", "text": "remember this"}),
            ("memory", {"action": "replace", "text": "updated"}),
            ("memory", {"action": "delete"}),
            ("memory", {"action": "import", "data": {}}),
            ("memory", {"action": "layer", "layer_action": "add", "content": "fact"}),
            ("memory", {"action": "layer", "layer_action": "correct", "content": "fact"}),
            ("memory", {"action": "layer", "layer_action": "delete", "item_id": "x"}),
            ("memory", {"action": "layer", "layer_action": "clear"}),
            ("memory", {"action": "layer", "layer_action": "consolidate"}),
            ("memory", {"action": "layer", "layer_action": "prune"}),
            ("memory", {"action": "layer", "layer_action": "migrate"}),
            ("memory", {"action": "layer", "layer_action": "import", "data": {}}),
            ("skill", {"action": "create", "name": "sample"}),
            ("skill", {"action": "edit", "name": "sample"}),
            ("scheduler", {"action": "add", "prompt": "run"}),
            ("scheduler", {"action": "remove", "id": "job"}),
        ]
        for name, arguments in cases:
            with self.subTest(tool=name, arguments=arguments):
                decision = policy.check(name, arguments, risk="write")
                self.assertTrue(decision.allowed)
                self.assertTrue(decision.needs_approval)
                self.assertIn("persistent", decision.reason)

    def test_persistent_mutation_approval_does_not_block_read_actions(self):
        config = self.config(tool_permissions={"require_approval": []})
        policy = PermissionPolicy(config, workspace=self.workspace)
        cases = [
            ("memory", {"action": "list"}),
            ("memory", {"action": "layer", "layer_action": "recall"}),
            ("skill", {"action": "view", "name": "sample"}),
            ("skill", {"action": "list"}),
            ("scheduler", {"action": "list"}),
            ("patch_preview", {"patch": "diff"}),
        ]
        for name, arguments in cases:
            with self.subTest(tool=name, arguments=arguments):
                decision = policy.check(name, arguments, risk="read")
                self.assertTrue(decision.allowed)
                self.assertFalse(decision.needs_approval)


if __name__ == "__main__":
    unittest.main()
