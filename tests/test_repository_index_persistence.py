import os
import sqlite3
import unittest
from contextlib import closing
from threading import Event
from unittest.mock import patch

from aether.coding.index import PersistentRepositoryIndex
from aether.coding.symbols import extract_symbols
from aether.errors import ToolError
from aether.tools.repository import repo_index
from tests.base import TempHomeTest


class PersistentRepositoryIndexTests(TempHomeTest):
    def context(self, config=None):
        return {"workspace": self.workspace, "home": self.home, "config": config or self.config()}

    def test_persistent_symbols_survive_calls_and_refresh_only_changed_files(self):
        source = self.workspace / "parser.py"
        source.write_text("def parse_alpha():\n    return 1\n", encoding="utf-8")

        first = repo_index({"action": "symbols", "query": "parse"}, self.context())
        self.assertTrue(first["persistent"])
        self.assertEqual(first["refresh"]["files_refreshed"], 1)
        self.assertIn("parse_alpha", {item["name"] for item in first["symbols"]})

        with patch("aether.tools.repository.extract_symbols", wraps=extract_symbols) as extractor:
            second = repo_index({"action": "symbols", "query": "parse"}, self.context())
            self.assertEqual(extractor.call_count, 0)
        self.assertEqual(second["refresh"]["files_refreshed"], 0)
        self.assertIn("parse_alpha", {item["name"] for item in second["symbols"]})

        source.write_text("def parse_alpha():\n    return 1\ndef parse_beta():\n    return 2\n", encoding="utf-8")
        stats = source.stat()
        os.utime(source, ns=(stats.st_atime_ns, stats.st_mtime_ns + 1_000_000))
        with patch("aether.tools.repository.extract_symbols", wraps=extract_symbols) as extractor:
            third = repo_index({"action": "symbols", "query": "parse"}, self.context())
            self.assertEqual(extractor.call_count, 1)
        names = {item["name"] for item in third["symbols"]}
        self.assertTrue({"parse_alpha", "parse_beta"}.issubset(names))

        source.unlink()
        fourth = repo_index({"action": "symbols", "query": "parse"}, self.context())
        self.assertEqual(fourth["match_count"], 0)
        self.assertEqual(fourth["refresh"]["files_removed"], 1)

    def test_persistent_index_action_is_idempotent_and_bounded_by_bounds_change(self):
        (self.workspace / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
        (self.workspace / "ignored.py").write_text("def hidden_parse(): pass\n", encoding="utf-8")
        source = self.workspace / "parser.py"
        source.write_text("def visible_parse(): pass\n" + "# padding\n" * 40, encoding="utf-8")

        result = repo_index({"action": "index"}, self.context())
        self.assertTrue(result["persistent"])
        self.assertEqual(result["refresh"]["files_refreshed"], 2)
        self.assertTrue((self.home / "repo_index.db").is_file())
        symbols = repo_index({"action": "symbols", "query": "parse"}, self.context())
        names = {item["name"] for item in symbols["symbols"]}
        self.assertIn("visible_parse", names)
        self.assertNotIn("hidden_parse", names)

        config = self.config()
        config.set("repository_index.max_file_bytes", 256)
        narrowed = repo_index({"action": "symbols", "query": "parse"}, self.context(config))
        self.assertEqual(narrowed["match_count"], 0)
        self.assertEqual(narrowed["refresh"]["files_refreshed"], 1)

    def test_persistent_index_discards_unsafe_stored_paths(self):
        repo_index({"action": "index"}, self.context())
        root = str(self.workspace.resolve())
        with closing(sqlite3.connect(self.home / "repo_index.db")) as db:
            with db:
                db.execute(
                    "INSERT OR REPLACE INTO repo_index_files(root, path, size, mtime_ns, ctime_ns, content_hash, lines, extension) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (root, "../outside.py", 20, 1, 1, "stale", 1, ".py"),
                )
                db.execute(
                    "INSERT OR REPLACE INTO repo_index_symbols(root, path, name, name_fold, kind, line) "
                    "VALUES(?,?,?,?,?,?)",
                    (root, "../outside.py", "escape_parse", "escape_parse", "function", 1),
                )
        result = repo_index({"action": "symbols", "query": "escape_parse"}, self.context())
        self.assertEqual(result["match_count"], 0)
        with closing(sqlite3.connect(self.home / "repo_index.db")) as db:
            count = db.execute(
                "SELECT COUNT(*) FROM repo_index_files WHERE path=?", ("../outside.py",)
            ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_on_demand_symbols_remain_available_when_persistence_is_disabled(self):
        (self.workspace / "parser.py").write_text("def plain_parse(): pass\n", encoding="utf-8")
        config = self.config()
        config.set("repository_index.persistent", False)
        result = repo_index({"action": "symbols", "query": "parse"}, self.context(config))
        self.assertFalse(result["persistent"])
        self.assertIn("plain_parse", {item["name"] for item in result["symbols"]})
        self.assertFalse((self.home / "repo_index.db").exists())

    def test_same_size_rewrite_with_restored_mtime_is_detected(self):
        source = self.workspace / "parser.py"
        original = "def parse_one(): pass\n"
        source.write_text(original, encoding="utf-8")
        repo_index({"action": "index"}, self.context())
        stats = source.stat()
        source.write_text("def parse_two(): pass\n", encoding="utf-8")
        os.utime(source, ns=(stats.st_atime_ns, stats.st_mtime_ns))

        result = repo_index({"action": "symbols", "query": "parse"}, self.context())
        names = {item["name"] for item in result["symbols"]}
        self.assertIn("parse_two", names)
        self.assertNotIn("parse_one", names)

    def test_symbol_budget_is_enforced_across_refreshes(self):
        (self.workspace / "first.py").write_text("def alpha_symbol(): pass\n", encoding="utf-8")
        config = self.config()
        config.set("repository_index.max_index_symbols", 1)
        first = repo_index({"action": "index"}, self.context(config))
        self.assertEqual(first["refresh"]["symbols_written"], 1)

        (self.workspace / "second.py").write_text("def beta_symbol(): pass\n", encoding="utf-8")
        second = repo_index({"action": "index"}, self.context(config))
        self.assertEqual(second["refresh"]["symbols_written"], 0)
        self.assertEqual(second["refresh"]["symbols_retained"], 1)
        self.assertTrue(second["refresh"]["symbols_truncated"])

    def test_query_filters_unsafe_rows_before_applying_limit(self):
        (self.workspace / "parser.py").write_text("def valid_parse(): pass\n", encoding="utf-8")
        repo_index({"action": "index"}, self.context())
        root = str(self.workspace.resolve())
        with closing(sqlite3.connect(self.home / "repo_index.db")) as db:
            with db:
                db.execute(
                    "INSERT INTO repo_index_files(root, path, size, mtime_ns, ctime_ns, content_hash, lines, extension) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (root, "../outside.py", 20, 1, 1, "stale", 1, ".py"),
                )
                db.execute(
                    "INSERT INTO repo_index_symbols(root, path, name, name_fold, kind, line) "
                    "VALUES(?,?,?,?,?,?)",
                    (root, "../outside.py", "fake_parse", "fake_parse", "function", 1),
                )
        config = self.config()
        config.set("repository_index.max_results", 1)
        symbols, truncated = PersistentRepositoryIndex(self.home).query_symbols(root, "parse", 1)
        self.assertEqual([item["name"] for item in symbols], ["valid_parse"])
        self.assertTrue(truncated)

    def test_cancelled_refresh_does_not_commit_index(self):
        (self.workspace / "parser.py").write_text("def parse_alpha(): pass\n", encoding="utf-8")
        context = self.context()
        context["cancel_event"] = Event()
        context["cancel_event"].set()
        with self.assertRaises(ToolError):
            repo_index({"action": "index"}, context)
        with closing(sqlite3.connect(self.home / "repo_index.db")) as db:
            count = db.execute("SELECT COUNT(*) FROM repo_index_roots").fetchone()[0]
        self.assertEqual(count, 0)

    def test_index_action_requires_persistence(self):
        config = self.config()
        config.set("repository_index.persistent", False)
        with self.assertRaises(ToolError):
            repo_index({"action": "index"}, self.context(config))

    def test_sync_cancellation_rolls_back_index_writes(self):
        class TriggeredEvent:
            def __init__(self, trigger):
                self.calls = 0
                self.trigger = trigger

            def is_set(self):
                self.calls += 1
                return self.calls >= self.trigger

        (self.workspace / "parser.py").write_text("def parse_alpha(): pass\n", encoding="utf-8")
        repo_index({"action": "index"}, self.context())
        root = str(self.workspace.resolve())
        records = [{
            "path": "added.py", "size": 20, "mtime_ns": 1, "ctime_ns": 1,
            "content_hash": "stale", "lines": 1, "extension": ".py", "symbols": [],
        }]
        index = PersistentRepositoryIndex(self.home)
        with self.assertRaises(ToolError):
            index.sync(root, "cancelled-signature", records, {"added.py"}, 10, cancel_event=TriggeredEvent(2))
        with closing(sqlite3.connect(self.home / "repo_index.db")) as db:
            count = db.execute(
                "SELECT COUNT(*) FROM repo_index_files WHERE root=? AND path=?", (root, "added.py")
            ).fetchone()[0]
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
