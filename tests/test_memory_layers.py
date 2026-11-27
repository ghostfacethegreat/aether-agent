import io
import unittest
from contextlib import redirect_stdout

from aether.cli.app import main
from aether.core import Agent
from aether.memory import LayeredMemory, MemoryStore
from aether.persistence import Store

from tests.base import TempHomeTest


class LayeredMemoryTests(TempHomeTest):
    def make_layered(self, session_id="session-a", config=None):
        return LayeredMemory(
            MemoryStore(self.home),
            Store(self.home / "state.db"),
            config=config or self.config(),
            persist=True,
            session_id=session_id,
        )

    def run_cli(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(argv)
        return code, buffer.getvalue()

    def test_remember_recall_and_bounded_context(self):
        memory = self.make_layered()
        memory.remember(
            "semantic",
            "Aether uses SQLite for state",
            subject="storage",
            provenance="test",
            confidence=0.8,
        )
        memory.remember(
            "procedural",
            "Run tests after edits",
            subject="release",
            provenance="verified-test",
            verified=True,
        )
        memory.remember(
            "episodic",
            "Session fixed a bug",
            subject="session:old",
            provenance="turn:old",
        )

        rows = memory.recall("SQLite")
        self.assertTrue(rows)
        self.assertEqual(rows[0]["layer"], "semantic")
        context = memory.context("SQLite", max_chars=500)
        self.assertIn("<layered-memory>", context)
        self.assertIn("source: test", context)
        self.assertLessEqual(len(context), 500)

    def test_working_memory_is_session_scoped_and_expires(self):
        memory = self.make_layered(session_id="s1")
        memory.set_working("active_objective", "fix memory", session_id="s1")
        memory.set_working("active_objective", "other task", session_id="s2")
        self.assertEqual([row["content"] for row in memory.recall(session_id="s1")], ["fix memory"])

        memory.remember(
            "working",
            "old temporary fact",
            subject="temporary",
            session_id="s1",
            expires_days=-1,
        )
        self.assertEqual(memory.prune_expired(), 1)
        self.assertNotIn(
            "old temporary fact",
            [row["content"] for row in memory.list("working", session_id="s1")],
        )

    def test_provenance_and_contradiction_resolution(self):
        memory = self.make_layered()
        left = memory.remember(
            "semantic",
            "Use Ollama locally",
            subject="default provider",
            provenance="user",
            confidence=0.8,
        )
        right = memory.remember(
            "semantic",
            "Use OpenAI only",
            subject="default provider",
            provenance="web-page",
            confidence=0.4,
        )
        self.assertEqual(len(memory.contradictions()), 1)
        self.assertTrue(memory.resolve_contradiction(left["id"], right["id"]))
        self.assertEqual(memory.contradictions(), [])
        self.assertEqual(memory.get(right["id"])["status"], "contradicted")

    def test_correction_supersedes_old_fact(self):
        memory = self.make_layered()
        old = memory.remember(
            "semantic",
            "Runtime is Python 3.11",
            subject="runtime",
            provenance="old test",
        )
        new = memory.correct(old["id"], "Runtime is Python 3.12", provenance="new test")
        self.assertEqual(memory.get(old["id"])["status"], "superseded")
        self.assertEqual(new["metadata"]["corrected_from"], old["id"])
        contents = [row["content"] for row in memory.recall("Python")]
        self.assertIn("Runtime is Python 3.12", contents)
        self.assertNotIn("Runtime is Python 3.11", contents)

    def test_markdown_migration_is_idempotent(self):
        legacy = MemoryStore(self.home)
        legacy.add("prefers tea", "preferences")
        legacy.add("uses local models", "tools", user=True)
        memory = LayeredMemory(
            legacy,
            Store(self.home / "state.db"),
            config=self.config(),
            persist=True,
        )

        counts = memory.counts()
        self.assertEqual(counts["semantic"], 1)
        self.assertEqual(counts["user"], 1)
        self.assertEqual(memory.migrate_markdown(), 0)
        self.assertTrue(any(row["content"] == "prefers tea" for row in memory.list("semantic")))
        self.assertTrue(any(row["content"] == "uses local models" for row in memory.list("user")))

    def test_consolidation_merges_duplicates(self):
        memory = self.make_layered()
        first = memory.remember(
            "semantic",
            "Uses Git for history",
            subject="tools",
            session_id="s1",
            provenance="first",
            confidence=0.9,
        )
        memory.remember(
            "semantic",
            "Uses Git for history",
            subject="tools",
            session_id="s2",
            provenance="second",
            confidence=0.7,
        )
        report = memory.consolidate()
        self.assertEqual(report["duplicates"], 1)
        active = memory.list("semantic")
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["id"], first["id"])

    def test_export_import_round_trip(self):
        memory = self.make_layered()
        memory.remember(
            "semantic",
            "Aether uses SQLite for state",
            subject="storage",
            provenance="test",
        )
        payload = memory.export_data()
        clone_home = self.root / "clone"
        clone = LayeredMemory(
            MemoryStore(clone_home),
            Store(clone_home / "state.db"),
            config=self.config(),
            persist=True,
        )
        imported = clone.import_data(payload, merge=False)
        self.assertGreaterEqual(imported, 1)
        self.assertTrue(clone.recall("SQLite"))

    def test_child_agent_layered_memory_is_isolated(self):
        agent = Agent(self.config(), home=self.home, enable_subagents=False)
        before = agent.layered_memory.counts()["total"]
        child = agent._child_agent({}, {"goal": "do work"})
        self.assertFalse(child.layered_memory.enabled)
        self.assertIsNone(child.layered_memory.remember("semantic", "child secret", subject="child"))
        self.assertEqual(agent.layered_memory.counts()["total"], before)

    def test_agent_turn_records_working_and_episode(self):
        agent = Agent(self.config(), home=self.home, enable_subagents=False)
        result = agent.run_turn("Remember the release plan")
        self.assertEqual(result.exit_reason, "complete")
        working = agent.layered_memory.list("working", session_id=agent.session_id)
        episodes = agent.layered_memory.list("episodic", session_id=agent.session_id)
        self.assertTrue(any("Remember the release plan" in row["content"] for row in working))
        self.assertTrue(episodes)
        self.assertEqual(agent.status_summary()["memory_layers"]["episodic"], len(episodes))

    def test_store_memory_items_search_and_delete(self):
        store = Store(self.home / "state.db")
        store.save_memory_item(
            {
                "id": "mem-test",
                "session_id": "s1",
                "layer": "semantic",
                "subject": "pets",
                "content": "Mika likes pineapples",
                "provenance": "test",
                "confidence": 0.8,
                "metadata": {"source": "unit"},
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        )
        self.assertTrue(store.search_memory_items("pineapples"))
        self.assertEqual(store.get_memory_item("mem-test")["metadata"], {"source": "unit"})
        self.assertTrue(store.delete_memory_item("mem-test"))
        self.assertIsNone(store.get_memory_item("mem-test"))

    def test_layered_memory_cli(self):
        code, output = self.run_cli(
            [
                "memory",
                "layer",
                "add",
                "likes tea",
                "--layer",
                "semantic",
                "--subject",
                "preferences",
                "--provenance",
                "cli-test",
            ]
        )
        self.assertEqual(code, 0)
        self.assertTrue(output.strip())
        code, output = self.run_cli(["memory", "layer", "recall", "tea"])
        self.assertEqual(code, 0)
        self.assertIn("likes tea", output)
        code, output = self.run_cli(["memory", "layer", "counts"])
        self.assertEqual(code, 0)
        self.assertIn('"semantic"', output)


if __name__ == "__main__":
    unittest.main()
