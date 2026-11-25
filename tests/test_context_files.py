import tempfile
import unittest
from pathlib import Path

from aether.config import Config
from aether.context_files import load_project_context


class ProjectContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = Config()

    def tearDown(self):
        self.temp.cleanup()

    def test_loads_supported_root_context_files_in_priority_order(self):
        (self.root / "AGENTS.md").write_text("Repository rules", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("Additional guidance", encoding="utf-8")
        result = load_project_context(self.root, self.config)
        self.assertLess(result.index("AGENTS.md"), result.index("CLAUDE.md"))
        self.assertIn("Repository rules", result)
        self.assertIn("Additional guidance", result)

    def test_disabled_context_files_return_empty(self):
        (self.root / "AGENTS.md").write_text("Do not load", encoding="utf-8")
        self.config.set("context_files.enabled", False)
        self.assertEqual(load_project_context(self.root, self.config), "")

    def test_nested_files_are_not_loaded(self):
        nested = self.root / "nested"
        nested.mkdir()
        (nested / "AGENTS.md").write_text("Nested rules", encoding="utf-8")
        self.assertEqual(load_project_context(self.root, self.config), "")

    def test_symlinks_are_not_loaded(self):
        target = self.root / "target.md"
        target.write_text("Outside guidance", encoding="utf-8")
        link = self.root / "AGENTS.md"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")
        self.assertEqual(load_project_context(self.root, self.config), "")

    def test_oversized_binary_and_invalid_utf8_are_skipped(self):
        self.config.set("context_files.max_file_bytes", 32)
        (self.root / "AGENTS.md").write_text("A" * 100, encoding="utf-8")
        (self.root / "AETHER.md").write_bytes(b"\\x00binary")
        (self.root / ".aether.md").write_bytes(b"\\xffbad utf8")
        self.assertEqual(load_project_context(self.root, self.config), "")

    def test_file_and_total_character_limits_are_enforced(self):
        (self.root / "AGENTS.md").write_text("A" * 40, encoding="utf-8")
        (self.root / "AETHER.md").write_text("B" * 40, encoding="utf-8")
        self.config.set("context_files.max_file_bytes", 100)
        self.config.set("context_files.max_total_chars", 60)
        result = load_project_context(self.root, self.config)
        self.assertLessEqual(len(result), 60)
        self.assertIn("AGENTS.md", result)
        self.assertNotIn("AETHER.md", result)

    def test_custom_filename_list_is_honored(self):
        (self.root / "CUSTOM.md").write_text("Custom rules", encoding="utf-8")
        self.config.set("context_files.filenames", ["CUSTOM.md", "../secret.md"])
        result = load_project_context(self.root, self.config)
        self.assertIn("Custom rules", result)
        self.assertNotIn("secret.md", result)


if __name__ == "__main__":
    unittest.main()
