import unittest

from aether.errors import ToolError
from aether.providers.base import ToolCall
from aether.tools import PermissionPolicy, ToolExecutor, default_registry
from aether.tools.repository import patch_apply, patch_preview, repo_index, test_run
from tests.base import TempHomeTest


class RepositoryToolTests(TempHomeTest):
    def context(self, config=None):
        return {"workspace": self.workspace, "config": config or self.config()}

    def test_index_respects_gitignore_and_generated_directories(self):
        (self.workspace / ".gitignore").write_text("ignored.txt\ncache/\n", encoding="utf-8")
        (self.workspace / "keep.py").write_text("def hello():\n    return 'world'\n", encoding="utf-8")
        (self.workspace / "ignored.txt").write_text("not indexed\n", encoding="utf-8")
        cache = self.workspace / "cache"
        cache.mkdir()
        (cache / "hidden.py").write_text("not indexed\n", encoding="utf-8")
        pycache = self.workspace / "__pycache__"
        pycache.mkdir()
        (pycache / "compiled.pyc").write_bytes(bytes([0]) + b"binary")
        result = repo_index({}, self.context())
        paths = [item["path"] for item in result["files"]]
        self.assertIn("keep.py", paths)
        self.assertNotIn("ignored.txt", paths)
        self.assertNotIn("cache/hidden.py", paths)
        self.assertNotIn("__pycache__/compiled.pyc", paths)

    def test_index_respects_nested_gitignore_scope_and_negation(self):
        source = self.workspace / "src"
        nested = source / "nested"
        nested.mkdir(parents=True)
        (source / ".gitignore").write_text(
            "private.py\nlogs/\ngenerated/output.txt\n",
            encoding="utf-8",
        )
        (nested / ".gitignore").write_text("!private.py\n", encoding="utf-8")

        (self.workspace / "private.py").write_text("root is visible\n", encoding="utf-8")
        (source / "private.py").write_text("ignored in src\n", encoding="utf-8")
        (source / "keep.py").write_text("visible\n", encoding="utf-8")
        (nested / "private.py").write_text("re-included in nested scope\n", encoding="utf-8")
        (nested / "keep.py").write_text("also visible\n", encoding="utf-8")

        logs = nested / "logs"
        logs.mkdir()
        (logs / "hidden.txt").write_text("ignored by inherited directory rule\n", encoding="utf-8")
        generated = source / "generated"
        generated.mkdir()
        (generated / "output.txt").write_text("ignored by scoped slash rule\n", encoding="utf-8")
        (generated / "other.txt").write_text("visible\n", encoding="utf-8")

        result = repo_index({}, self.context())
        paths = {item["path"] for item in result["files"]}
        self.assertIn("private.py", paths)
        self.assertIn("src/keep.py", paths)
        self.assertIn("src/nested/private.py", paths)
        self.assertIn("src/nested/keep.py", paths)
        self.assertIn("src/generated/other.txt", paths)
        self.assertNotIn("src/private.py", paths)
        self.assertNotIn("src/nested/logs/hidden.txt", paths)
        self.assertNotIn("src/generated/output.txt", paths)


    def test_index_search_returns_filename_and_line_matches(self):
        (self.workspace / "agent.py").write_text("alpha\nunique_symbol()\nomega\n", encoding="utf-8")
        result = repo_index({"action": "search", "query": "unique_symbol"}, self.context())
        self.assertEqual(result["match_count"], 1)
        self.assertEqual(result["matches"][0]["path"], "agent.py")
        self.assertEqual(result["matches"][0]["snippets"][0]["line"], 2)

    def test_index_rejects_workspace_escape(self):
        outside = self.root / "outside"
        outside.mkdir()
        with self.assertRaises(ToolError):
            repo_index({"root": str(outside)}, self.context())

    def test_index_skips_symlinks(self):
        target = self.workspace / "target.py"
        target.write_text("visible only through target\n", encoding="utf-8")
        link = self.workspace / "linked.py"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")
        result = repo_index({}, self.context())
        paths = [item["path"] for item in result["files"]]
        self.assertIn("target.py", paths)
        self.assertNotIn("linked.py", paths)

    def test_patch_preview_validates_without_writing(self):
        target = self.workspace / "sample.py"
        target.write_text("value = 1\nprint(value)\n", encoding="utf-8")
        patch = "--- a/sample.py\n+++ b/sample.py\n@@ -1,2 +1,2 @@\n-value = 1\n+value = 2\n print(value)\n"
        result = patch_preview({"patch": patch}, self.context())
        self.assertTrue(result["valid"])
        self.assertFalse(result["writes_performed"])
        self.assertEqual(target.read_text(encoding="utf-8"), "value = 1\nprint(value)\n")

    def test_patch_apply_updates_existing_file(self):
        target = self.workspace / "sample.py"
        target.write_text("value = 1\nprint(value)\n", encoding="utf-8")
        patch = "--- a/sample.py\n+++ b/sample.py\n@@ -1,2 +1,2 @@\n-value = 1\n+value = 42\n print(value)\n"
        result = patch_apply({"patch": patch}, self.context())
        self.assertTrue(result["applied"])
        self.assertEqual(target.read_text(encoding="utf-8"), "value = 42\nprint(value)\n")

    def test_patch_all_files_are_preflighted_before_any_write(self):
        first, second = self.workspace / "first.py", self.workspace / "second.py"
        first.write_text("a = 1\n", encoding="utf-8")
        second.write_text("b = 2\n", encoding="utf-8")
        patch = (
            "--- a/first.py\n+++ b/first.py\n@@ -1 +1 @@\n-a = 1\n+a = 3\n"
            "--- a/second.py\n+++ b/second.py\n@@ -1 +1 @@\n-b = WRONG\n+b = 4\n"
        )
        with self.assertRaises(ToolError):
            patch_apply({"patch": patch}, self.context())
        self.assertEqual(first.read_text(encoding="utf-8"), "a = 1\n")
        self.assertEqual(second.read_text(encoding="utf-8"), "b = 2\n")

    def test_patch_refuses_traversal_and_symlink_targets(self):
        outside = self.root / "outside.py"
        outside.write_text("safe = True\n", encoding="utf-8")
        traversal = "--- a/../outside.py\n+++ b/../outside.py\n@@ -1 +1 @@\n-safe = True\n+safe = False\n"
        with self.assertRaises(ToolError):
            patch_preview({"patch": traversal}, self.context())
        inside = self.workspace / "linked.py"
        try:
            inside.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")
        linked = "--- a/linked.py\n+++ b/linked.py\n@@ -1 +1 @@\n-safe = True\n+safe = False\n"
        with self.assertRaises(ToolError):
            patch_apply({"patch": linked}, self.context())
        self.assertEqual(outside.read_text(encoding="utf-8"), "safe = True\n")

    def test_patch_refuses_new_files_and_renames(self):
        with self.assertRaises(ToolError):
            patch_preview({"patch": "--- /dev/null\n+++ b/new.py\n@@ -0,0 +1 @@\n+value = 1\n"}, self.context())
        with self.assertRaises(ToolError):
            patch_preview({"patch": "--- a/old.py\n+++ b/new.py\n@@ -1 +1 @@\n-a\n+b\n"}, self.context())

    def test_test_run_uses_fixed_argv_and_module_allowlist(self):
        test_dir = self.workspace / "tests"
        test_dir.mkdir()
        (test_dir / "__init__.py").write_text("", encoding="utf-8")
        (test_dir / "test_sample.py").write_text(
            "import unittest\nclass Sample(unittest.TestCase):\n def test_ok(self): self.assertEqual(2, 2)\n",
            encoding="utf-8",
        )
        result = test_run({"mode": "module", "module": "test_sample"}, self.context())
        self.assertEqual(result["exit_code"], 0)
        self.assertFalse(result["timed_out"])
        with self.assertRaises(ToolError):
            test_run({"mode": "module", "module": "../../outside"}, self.context())


    def test_patch_parser_accepts_removed_line_that_looks_like_file_header(self):
        target = self.workspace / "sample.py"
        target.write_text("-- legacy\nvalue = 1\n", encoding="utf-8")
        patch = (
            "--- a/sample.py\n+++ b/sample.py\n@@ -1,2 +1,2 @@\n"
            "--- legacy\n+++ current\n value = 1\n"
        )
        patch_apply({"patch": patch}, self.context())
        self.assertEqual(target.read_text(encoding="utf-8"), "++ current\nvalue = 1\n")

    def test_patch_apply_requires_explicit_tool_approval(self):
        target = self.workspace / "sample.py"
        target.write_text("value = 1\n", encoding="utf-8")
        patch = "--- a/sample.py\n+++ b/sample.py\n@@ -1 +1 @@\n-value = 1\n+value = 2\n"
        config = self.config()
        config.set("tool_permissions.require_approval", ["patch_apply"])
        context = self.context(config)
        policy = PermissionPolicy(config, workspace=self.workspace)
        executor = ToolExecutor(default_registry(), policy, context)
        _, execution = executor.execute_call(ToolCall("patch-approval", "patch_apply", {"patch": patch}))
        self.assertFalse(execution.ok)
        self.assertIn("Approval required", execution.error)
        self.assertEqual(target.read_text(encoding="utf-8"), "value = 1\n")

    def test_test_run_refuses_an_empty_suite(self):
        (self.workspace / "tests").mkdir()
        with self.assertRaises(ToolError):
            test_run({"mode": "suite"}, self.context())

    def test_test_run_compile_mode(self):
        (self.workspace / "aether").mkdir()
        (self.workspace / "tests").mkdir()
        result = test_run({"mode": "compile"}, self.context())
        self.assertEqual(result["exit_code"], 0)


if __name__ == "__main__":
    unittest.main()
