import unittest

from aether.core import Agent, ContextManager

from tests.base import TempHomeTest


class CoreTests(TempHomeTest):
    def test_context_compression(self):
        config = self.config(context_tokens=1024, compression_threshold=0.1)
        manager = ContextManager(config)
        messages = [{"role": "system", "content": "system"}]
        for index in range(12):
            role = "user" if index % 2 == 0 else "assistant"
            messages.append({"role": role, "content": f"message {index} " + "x" * 300})
        fitted, report = manager.fit(messages)
        self.assertGreater(report["removed"], 0)
        self.assertEqual(fitted[0]["role"], "system")
        self.assertTrue(any("Earlier conversation summary" in str(item.get("content")) for item in fitted))

    def test_agent_tool_turn_persists_and_writes_file(self):
        script = [
            {
                "content": "Writing the file now.",
                "tool_calls": [{"name": "write_file", "arguments": {"path": "created.txt", "content": "created by Aether"}}],
            },
            {"content": "Done."},
        ]
        config = self.config(providers={"mock": {"script": script}})
        agent = Agent(config, home=self.home, enable_subagents=False)
        deltas = []
        result = agent.run_turn("Create a file", on_delta=lambda text, kind="content": deltas.append(text))
        self.assertEqual(result.text, "Done.")
        self.assertEqual(result.exit_reason, "complete")
        self.assertEqual(len(result.tool_log), 1)
        self.assertTrue(result.tool_log[0]["ok"])
        self.assertEqual((self.workspace / "created.txt").read_text(encoding="utf-8"), "created by Aether")
        self.assertTrue("".join(deltas))
        self.assertGreaterEqual(len(agent.store.get_messages(agent.session_id)), 4)

    def test_agent_plan_and_status(self):
        agent = Agent(self.config(), home=self.home, enable_subagents=False)
        agent.set_plan("1. inspect\n2. verify")
        status = agent.status_summary()
        self.assertEqual(status["provider"], "mock")
        self.assertEqual(status["model"], "mock-standard")
        self.assertEqual(agent.plan, "1. inspect\n2. verify")


if __name__ == "__main__":
    unittest.main()
