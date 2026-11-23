import unittest

from aether.persistence import Store

from tests.base import TempHomeTest


class StoreTests(TempHomeTest):
    def setUp(self):
        super().setUp()
        self.store = Store(self.home / "state.db")

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

    def test_export_import_session(self):
        session = self.store.create_session(title="export me")
        self.store.append_message(session, "user", "hello")
        payload = self.store.export_session(session)
        clone = self.store.import_session(payload)
        self.assertEqual(clone, session)
        self.assertEqual(len(self.store.get_messages(clone)), 2)


if __name__ == "__main__":
    unittest.main()
