import unittest
from unittest.mock import patch

from aether.core import Agent, ContextManager, TurnState, new_spend_budget, run_turn_loop
from aether.errors import ProviderError
from aether.persistence import Store
from aether.providers.base import ModelResponse

from tests.base import TempHomeTest


class _ContextStub:
    def fit(self, messages):
        return messages, {}


class _ManagerStub:
    def __init__(self):
        self.failed = []

    def mark_failed(self, name, seconds=60):
        self.failed.append(name)


class _PaidProviderStub:
    name = "openai"
    model = "gpt-4o-mini"
    kind = "paid"

    def __init__(self, response=None, name="openai", model="gpt-4o-mini"):
        self.name = name
        self.model = model
        self.calls = 0
        self.response = response or ModelResponse(
            content="ok",
            usage={"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000},
        )

    def chat(self, messages, tools=None, stream=False, on_delta=None, options=None):
        self.calls += 1
        return self.response


class CoreTests(TempHomeTest):
    def _turn_state(self, provider, config):
        return TurnState(
            messages=[{"role": "user", "content": "Hello"}],
            system_prompt="system",
            tools=[],
            provider_candidates=[provider],
            provider_manager=_ManagerStub(),
            context_manager=_ContextStub(),
            executor=None,
            config=config,
        )

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

    def test_context_repair_handles_orphan_tool_results(self):
        config = self.config(context_tokens=8192)
        manager = ContextManager(config)
        messages = [
            {"role": "system", "content": "system"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_kept",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "orphan", "content": "stale result"},
        ]
        fitted, report = manager.fit(messages)
        tool_ids = [item.get("tool_call_id") for item in fitted if item.get("role") == "tool"]
        self.assertIn("call_kept", tool_ids)
        self.assertNotIn("orphan", tool_ids)
        self.assertGreaterEqual(report["repaired"], 2)

    def test_agent_resume_preserves_tool_call_history(self):
        script = [
            {
                "content": "Reading now.",
                "tool_calls": [{"id": "call_resume", "name": "read_file", "arguments": {"path": "notes.txt"}}],
            },
            {"content": "Done."},
        ]
        config = self.config(providers={"mock": {"script": script}})
        agent = Agent(config, home=self.home, enable_subagents=False)
        (self.workspace / "notes.txt").write_text("note body", encoding="utf-8")
        first = agent.run_turn("Read notes.txt")
        self.assertEqual(first.exit_reason, "complete")

        resumed = Agent(
            self.config(),
            home=self.home,
            session_id=first.session_id,
            enable_subagents=False,
        )
        assistant_calls = [item for item in resumed.history if item.get("tool_calls")]
        tool_results = [item for item in resumed.history if item.get("role") == "tool"]
        self.assertEqual(assistant_calls[0]["tool_calls"][0]["id"], "call_resume")
        self.assertEqual(tool_results[0]["tool_call_id"], "call_resume")

        second = resumed.run_turn("Continue")
        self.assertEqual(second.text, "Aether mock provider is active. No network request was made.\nUse /provider ollama (or another configured provider) for real inference.")

    def test_agent_tool_turn_persists_and_writes_file(self):
        script = [
            {
                "content": "Writing the file now.",
                "tool_calls": [{"name": "write_file", "arguments": {"path": "created.txt", "content": "created by Aether"}}],
            },
            {"content": "Done."},
        ]
        config = self.config(providers={"mock": {"script": script}})
        agent = Agent(config, home=self.home, enable_subagents=False, approve_callback=lambda *args: "once")
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

    def test_paid_provider_requires_confirmation(self):
        provider = _PaidProviderStub()
        state = self._turn_state(provider, self.config())

        result = run_turn_loop(state)

        self.assertEqual(result.exit_reason, "provider_error")
        self.assertIn("not confirmed", result.error)
        self.assertEqual(provider.calls, 0)

    def test_cost_limit_blocks_expensive_call(self):
        provider = _PaidProviderStub()
        config = self.config(
            max_tokens=1_000_000,
            costs={"confirm_paid": False, "max_estimated_usd_per_turn": 0.5},
        )
        state = self._turn_state(provider, config)

        result = run_turn_loop(state)

        self.assertEqual(result.exit_reason, "provider_error")
        self.assertIn("exceeds costs.max_estimated_usd_per_turn", result.error)
        self.assertEqual(provider.calls, 0)

    def test_usage_tracks_estimated_cost_without_clearing_cooldown(self):
        provider = _PaidProviderStub()
        config = self.config(costs={"confirm_paid": False, "max_estimated_usd_per_turn": 10.0})
        state = self._turn_state(provider, config)
        state.provider_manager.mark_failed("openai", 30)

        result = run_turn_loop(state)

        self.assertEqual(result.exit_reason, "complete")
        self.assertEqual(result.final_text, "ok")
        self.assertEqual(provider.calls, 1)
        self.assertEqual(state.provider_manager.failed, ["openai"])
        self.assertEqual(state.usage["estimated_cost"], 0.75)
        self.assertTrue(state.usage["cost_known"])

    def test_free_tier_billable_provider_requires_confirmation(self):
        class FreeTierStub(_PaidProviderStub):
            name = "groq"
            model = "llama-3.3-70b-versatile"
            kind = "free-tier"

        provider = FreeTierStub()
        state = self._turn_state(provider, self.config())

        result = run_turn_loop(state)

        self.assertEqual(result.exit_reason, "provider_error")
        self.assertIn("not confirmed", result.error)
        self.assertEqual(provider.calls, 0)

    def test_unpriced_model_fails_closed_when_cap_is_configured(self):
        class UnpricedStub(_PaidProviderStub):
            model = "gpt-4o"

        provider = UnpricedStub(model="gpt-4o")
        config = self.config(costs={"confirm_paid": False, "max_estimated_usd_per_turn": 1.0})
        state = self._turn_state(provider, config)

        result = run_turn_loop(state)

        self.assertEqual(result.exit_reason, "provider_error")
        self.assertIn("unpriced model", result.error)
        self.assertEqual(provider.calls, 0)

    def test_invalid_confirm_paid_fails_closed(self):
        provider = _PaidProviderStub()
        config = self.config(costs={"confirm_paid": "enabled"})
        state = self._turn_state(provider, config)

        result = run_turn_loop(state)

        self.assertEqual(result.exit_reason, "provider_error")
        self.assertIn("not confirmed", result.error)
        self.assertEqual(provider.calls, 0)

    def test_confirm_paid_environment_override_is_run_scoped(self):
        provider = _PaidProviderStub()
        config = self.config()
        state = self._turn_state(provider, config)

        with patch.dict("os.environ", {"AETHER_CONFIRM_PAID": "1"}):
            result = run_turn_loop(state)

        self.assertEqual(result.exit_reason, "complete")
        self.assertEqual(provider.calls, 1)
        self.assertEqual(config.get("costs.confirm_paid"), True)

    def test_shared_budget_does_not_double_count_persisted_turn_usage(self):
        config = self.config(
            provider="openai",
            model="gpt-4o-mini",
            costs={"confirm_paid": False},
        )
        agent = Agent(config, home=self.home, enable_subagents=False)
        provider = _PaidProviderStub()

        with patch.object(agent.provider_manager, "candidates", lambda: [provider]):
            first = agent.run_turn("first")
            second = agent.run_turn("second")

        self.assertEqual(first.usage["estimated_cost"], 0.75)
        self.assertEqual(second.usage["estimated_cost"], 0.75)
        usage = Store(self.home / "state.db").session_usage(first.session_id)
        self.assertEqual(usage["estimated_cost"], 1.5)
        self.assertEqual(usage["prompt_tokens"], 2_000_000)
        self.assertEqual(agent.spend_budget["spent"], 1.5)

    def test_cached_anthropic_tokens_are_counted_and_priced(self):
        config = self.config(
            provider="anthropic",
            model="claude-3-5-haiku-latest",
            costs={"confirm_paid": False},
        )
        provider = _PaidProviderStub(
            ModelResponse(
                content="ok",
                usage={
                    "input_tokens": 1_000_000,
                    "cache_read_input_tokens": 500_000,
                    "cache_creation_input_tokens": 200_000,
                    "output_tokens": 0,
                },
            ),
            name="anthropic",
            model="claude-3-5-haiku-latest",
        )
        state = self._turn_state(provider, config)
        state.config = config

        run_turn_loop(state)

        self.assertEqual(state.exit_reason, "complete")
        self.assertEqual(state.usage["prompt_tokens"], 1_700_000)
        self.assertEqual(state.usage["estimated_cost"], 1.04)

    def test_retry_attempts_are_reserved_against_cap(self):
        provider = _PaidProviderStub()
        config = self.config(
            max_tokens=1_000_000,
            retry_attempts=2,
            costs={"confirm_paid": False, "max_estimated_usd_per_turn": 1.0},
        )
        state = self._turn_state(provider, config)

        result = run_turn_loop(state)

        self.assertEqual(result.exit_reason, "provider_error")
        self.assertIn("worst-case cost", result.error)
        self.assertEqual(provider.calls, 0)

    def test_spend_budget_is_shared_across_turns(self):
        budget = new_spend_budget(0.8)
        config = self.config(
            max_tokens=1_000_000,
            retry_attempts=0,
            costs={"confirm_paid": False, "max_estimated_usd_per_turn": 0.8},
        )
        first = self._turn_state(_PaidProviderStub(), config)
        second = self._turn_state(_PaidProviderStub(), config)
        first.spend_budget = second.spend_budget = budget

        first_result = run_turn_loop(first)
        second_result = run_turn_loop(second)

        self.assertEqual(first_result.exit_reason, "complete")
        self.assertEqual(second_result.exit_reason, "provider_error")
        self.assertIn("exceeds", second_result.error)
        self.assertLessEqual(second.usage["estimated_cost"], 0.8)

    def test_fallback_usage_is_attributed_to_responder(self):
        class FailingPaid(_PaidProviderStub):
            def chat(self, messages, tools=None, stream=False, on_delta=None, options=None):
                self.calls += 1
                raise ProviderError("down", provider=self.name)

        class LocalStub(_PaidProviderStub):
            name = "mock"
            model = "mock-standard"
            kind = "local"

        paid = FailingPaid()
        local = LocalStub(name="mock", model="mock-standard")
        state = self._turn_state(paid, self.config(costs={"confirm_paid": False}))
        state.provider_candidates = [paid, local]

        result = run_turn_loop(state)

        self.assertEqual(result.exit_reason, "complete")
        self.assertEqual(state.usage["provider"], "mock")
        self.assertEqual(state.usage["model"], "mock-standard")
    def test_false_paid_environment_does_not_confirm(self):
        provider = _PaidProviderStub()
        state = self._turn_state(provider, self.config())

        with patch.dict("os.environ", {"AETHER_CONFIRM_PAID": "false"}):
            result = run_turn_loop(state)

        self.assertEqual(result.exit_reason, "provider_error")
        self.assertIn("not confirmed", result.error)
        self.assertEqual(provider.calls, 0)

    def test_turn_usage_is_local_to_each_turn(self):
        config = self.config(costs={"confirm_paid": False})
        budget = new_spend_budget()
        provider = _PaidProviderStub()
        provider.response = ModelResponse(content="ok", usage={"prompt_tokens": 10, "completion_tokens": 5})

        first = self._turn_state(provider, config)
        first.spend_budget = budget
        self.assertEqual(run_turn_loop(first).exit_reason, "complete")

        second = self._turn_state(provider, config)
        second.spend_budget = budget
        self.assertEqual(run_turn_loop(second).exit_reason, "complete")

        self.assertEqual(first.usage["prompt_tokens"], 10)
        self.assertEqual(second.usage["prompt_tokens"], 10)
        with budget["lock"]:
            self.assertEqual(budget["usage"]["prompt_tokens"], 20)


if __name__ == "__main__":
    unittest.main()
