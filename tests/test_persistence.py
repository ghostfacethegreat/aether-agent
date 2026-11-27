import os
import sqlite3
import stat
import unittest

from aether.home import aether_home
from aether.persistence import Store

from tests.base import TempHomeTest


class StoreTests(TempHomeTest):
    def setUp(self):
        super().setUp()
        self.store = Store(self.home / "state.db")

    def test_state_database_is_private(self):
        mode = stat.S_IMODE(os.stat(self.home / "state.db").st_mode)
        self.assertEqual(mode, 0o600)

    def test_home_directories_are_private(self):
        home = aether_home()
        for path in [home, *(home / name for name in ("memories", "skills", "logs", "cron"))]:
            with self.subTest(path=path):
                self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o700)

    def test_session_messages_and_search(self):
        session = self.store.create_session(title="first", provider="mock", model="mock-standard")
        self.store.append_messages(
            session,
            [
                {"role": "user", "content": "remember pineapples"},
                {"role": "assistant", "content": "I will remember pineapples."},
            ],
        )
        rows = self.store.get_messages(session)
        self.assertEqual([row["role"] for row in rows], ["user", "assistant"])
        results = self.store.search_messages("pineapples")
        self.assertTrue(results)
        self.assertEqual(results[0]["session_id"], session)
        self.assertEqual(self.store.list_sessions()[0]["message_count"], 2)

    def test_tool_call_fields_round_trip(self):
        session = self.store.create_session(provider="mock", model="mock-standard")
        self.store.append_messages(
            session,
            [
                {
                    "role": "assistant",
                    "content": "",
                    "metadata": {"source": "test"},
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "read_file", "arguments": '{"path":"a.txt"}'},
                        }
                    ],
                },
                {"role": "tool", "tool_call_id": "call_1", "name": "read_file", "content": "file body"},
            ],
        )
        rows = self.store.get_messages(session)
        self.assertEqual(rows[0]["tool_calls"][0]["id"], "call_1")
        self.assertEqual(rows[0]["metadata"], {"source": "test"})
        self.assertEqual(rows[1]["tool_call_id"], "call_1")
        self.assertEqual(rows[1]["name"], "read_file")

    def test_tasks_usage_and_approvals(self):
        task = self.store.create_task("check build", session_id="s1")
        self.store.update_task(task, "completed", "passed")
        self.assertEqual(self.store.get_task(task)["status"], "completed")
        self.store.record_usage("s1", "mock", "mock-standard", 10, 4, 0.0)
        usage = self.store.session_usage("s1")
        self.assertEqual(usage["prompt_tokens"], 10)
        self.store.set_approval("rule", "always")
        self.assertEqual(self.store.get_approval("rule"), "always")

    def test_usage_cost_state_survives_restart(self):
        session = self.store.create_session(provider="openai", model="gpt-4o-mini")
        self.store.record_usage(
            session,
            "openai",
            "gpt-4o-mini",
            1_000_000,
            500_000,
            0.45,
            cost_known=True,
            priced_calls=1,
            unpriced_calls=0,
        )

        reopened = Store(self.home / "state.db")
        usage = reopened.session_usage(session)

        self.assertEqual(usage["estimated_cost"], 0.45)
        self.assertTrue(usage["cost_known"])
        self.assertEqual(usage["priced_calls"], 1)
        self.assertEqual(usage["unpriced_calls"], 0)

    def test_legacy_usage_table_migrates_without_loss(self):
        path = self.home / "legacy.db"
        connection = sqlite3.connect(path)
        connection.execute(
            "CREATE TABLE usage (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, "
            "provider TEXT NOT NULL, model TEXT NOT NULL, prompt_tokens INTEGER NOT NULL DEFAULT 0, "
            "completion_tokens INTEGER NOT NULL DEFAULT 0, estimated_cost REAL NOT NULL DEFAULT 0, "
            "created_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO usage(session_id,provider,model,prompt_tokens,completion_tokens,estimated_cost,created_at) "
            "VALUES('legacy','mock','mock-standard',10,4,0,'now')"
        )
        connection.commit()
        connection.close()

        store = Store(path)
        usage = store.session_usage("legacy")

        self.assertEqual(usage["prompt_tokens"], 10)
        self.assertFalse(usage["cost_known"])
        self.assertEqual(usage["unpriced_calls"], 0)

    def test_export_import_session(self):
        session = self.store.create_session(title="export me")
        self.store.append_message(session, "user", "hello")
        payload = self.store.export_session(session)
        clone = self.store.import_session(payload)
        self.assertEqual(clone, session)
        self.assertEqual(len(self.store.get_messages(clone)), 2)


if __name__ == "__main__":
    unittest.main()
