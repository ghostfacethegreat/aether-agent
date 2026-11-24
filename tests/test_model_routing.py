import io
import json
import os
import threading
import unittest
import urllib.error
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from aether.cli.app import SLASH_COMMANDS, main
from aether.config import Config
from aether.core.agent import Agent
from aether.core.loop import TurnState, _recover_context, run_turn_loop
from aether.core.context import ContextManager
from aether.errors import ContextOverflow, ProviderError
from aether.orchestration.roles import FORCED_APPROVAL_TOOLS, ROLE_NAMES, resolved_roles
from aether.persistence import Store
from aether.providers.base import ModelResponse
from aether.providers.catalog import provider_spec
from aether.providers.openai_compatible import OpenAICompatibleProvider
from aether.providers.registry import ProviderManager
from aether.routing import CapabilityRegistry, ModelRouter, RoutingDecision, classify_task
from aether.utils import message_tokens

from benchmarks.model_routing import run_benchmark

from tests.base import TempHomeTest


class _OverflowOnceProvider:
    name = "mock"
    model = "mock-standard"
    kind = "local"

    def __init__(self):
        self.calls = 0

    def chat(self, messages, tools=None, stream=False, on_delta=None, options=None):
        self.calls += 1
        if self.calls == 1:
            raise ContextOverflow("prompt is too long")
        return ModelResponse(content="done", usage={"prompt_tokens": 10, "completion_tokens": 2})


class _FakeHTTPResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


class _ProviderErrorStub:
    name = "mock"
    model = "mock-standard"
    kind = "local"

    def chat(self, messages, tools=None, stream=False, on_delta=None, options=None):
        raise ProviderError("temporary outage", retryable=False)


class _CompressingContext:
    def fit(self, messages, provider=None, model=None, force=False):
        kept = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "request"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "call_keep", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}
                ],
            },
            {"role": "tool", "tool_call_id": "call_keep", "name": "read_file", "content": ""},
            {"role": "user", "content": "continue"},
        ]
        return kept, {
            "changed": True,
            "removed": 2,
            "repaired": 1,
            "tokens": message_tokens(kept),
            "limit": 512,
            "limit_source": "test stub",
            "forced": bool(force),
        }


class ModelRoutingTests(TempHomeTest):
    def _cli(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(argv)
        return code or 0, buffer.getvalue()

    def test_capability_facts_do_not_invent_unknown_values(self):
        caps = CapabilityRegistry(self.config()).for_model("mock", "mock-standard")
        self.assertIsNone(caps.context_window)
        self.assertEqual(caps.fact("context_window").evidence, "unknown")
        self.assertTrue(caps.fact("tool_calling").value)
        self.assertEqual(caps.fact("tool_calling").evidence, "verified")
        self.assertTrue(caps.fact("credentials_configured").value)

    def test_user_metadata_overrides_with_explicit_evidence(self):
        config = self.config(
            models={
                "metadata": {
                    "mock/custom": {
                        "context_window": 123456,
                        "capabilities": {"reasoning": True},
                        "evidence": {"context_window": "verified", "reasoning": "verified"},
                        "source": "user config",
                        "freshness": "2026-11-24",
                    }
                }
            },
            model="custom",
            routing={"strict_capabilities": True},
        )
        registry = CapabilityRegistry(config)
        caps = registry.for_model("mock", "custom")
        self.assertEqual(caps.context_window, 123456)
        self.assertEqual(caps.fact("context_window").evidence, "verified")
        self.assertEqual(caps.fact("context_window").source, "user config")
        self.assertTrue(caps.has("reasoning"))
        requirement = classify_task("Explain caching", config)
        requirement.required_capabilities = ["reasoning"]
        requirement.context_tokens = 512
        decision = ModelRouter(config, registry=registry).route(requirement)
        self.assertTrue(decision.eligible)
        self.assertEqual(decision.key, "mock/custom")

    def test_classifier_extracts_requirements_and_user_overrides(self):
        config = self.config(
            routing={
                "overrides": {
                    "software_development": {"provider": "mock", "capabilities": ["coding", "reasoning"]}
                }
            }
        )
        requirement = classify_task("Build a Python function and run tests", config)
        self.assertEqual(requirement.category, "software_development")
        self.assertIn("coding", requirement.required_capabilities)
        self.assertEqual(requirement.explicit_provider, "mock")

    def test_router_selects_configured_model_and_explains(self):
        config = self.config(provider="mock", model="mock-standard")
        registry = CapabilityRegistry(config)
        router = ModelRouter(config, registry=registry)
        requirement = classify_task("What is a Python list?", config)
        decision = router.route(requirement)
        self.assertEqual(decision.key, "mock/mock-standard")
        self.assertTrue(decision.eligible)
        self.assertIn("selected mock/mock-standard", ModelRouter.explain(decision))

    def test_router_strategy_fixed_keeps_active_model(self):
        config = self.config(
            models={
                "metadata": {
                    "mock/better": {
                        "context_window": 32768,
                        "capabilities": {"reasoning": True},
                        "evidence": {"context_window": "verified", "reasoning": "verified"},
                    }
                }
            },
            routing={"strategy": "fixed"},
        )
        router = ModelRouter(config)
        requirement = classify_task("Explain caching", config)
        requirement.required_capabilities = ["reasoning"]
        requirement.context_tokens = 512
        decision = router.route(requirement)
        self.assertEqual(decision.key, "mock/mock-standard")

    def test_router_strategy_cost_prefers_cheaper_model(self):
        config = self.config(
            model="expensive",
            models={
                "metadata": {
                    "mock/cheap": {
                        "context_window": 8192,
                        "pricing": [0.0, 0.0],
                        "evidence": {"context_window": "verified", "pricing": "verified"},
                    },
                    "mock/expensive": {
                        "context_window": 8192,
                        "pricing": [10.0, 10.0],
                        "evidence": {"context_window": "verified", "pricing": "verified"},
                    },
                }
            },
            routing={"strategy": "cost", "prefer_local": False},
        )
        router = ModelRouter(config)
        requirement = classify_task("Explain caching", config)
        requirement.context_tokens = 512
        decision = router.route(requirement)
        self.assertEqual(decision.key, "mock/cheap")

    def test_role_context_requirement_cannot_be_lowered(self):
        config = self.config(
            model="small",
            models={
                "metadata": {
                    "mock/small": {"context_window": 8500, "evidence": {"context_window": "verified"}}
                }
            },
            routing={
                "context_safety_margin": 0.01,
                "roles": {"planner": {"context_tokens": 8192}},
            },
        )
        router = ModelRouter(config)
        requirement = classify_task("Summarize this long transcript", config)
        requirement.category = "summarization"
        requirement.context_tokens = 9000
        decision = router.route(requirement, role="planner")
        self.assertFalse(decision.eligible)
        self.assertTrue(any("context window" in item for item in decision.rejections))

    def test_router_reports_limitation_for_explicit_unavailable_model(self):
        config = self.config()
        router = ModelRouter(config)
        requirement = classify_task("What is Python?", config)
        requirement.explicit_provider = "missing"
        decision = router.route(requirement)
        self.assertFalse(decision.eligible)
        self.assertEqual(decision.provider, "")
        self.assertIn("no suitable configured model", ModelRouter.explain(decision))

    def test_paid_provider_requires_confirmation_for_routing(self):
        config = self.config(provider="openai", model="gpt-4o-mini", costs={"confirm_paid": True})
        router = ModelRouter(config)
        requirement = classify_task("Explain caching", config)
        with patch.dict(os.environ, {}, clear=True):
            decision = router.route(requirement)
        self.assertFalse(decision.eligible)
        self.assertTrue(any("not authorized" in item for item in decision.rejections))

    def test_unknown_price_is_not_treated_as_zero(self):
        config = self.config(
            provider="custom",
            model="unknown-model",
            providers={"custom": {"base_url": "http://127.0.0.1:1/v1"}},
            costs={"confirm_paid": False},
        )
        router = ModelRouter(config)
        requirement = classify_task("Explain caching", config)
        decision = router.route(requirement)
        self.assertTrue(any("not treated as zero" in item for item in decision.reasons))

    def test_verified_learning_requires_samples_and_can_be_reset(self):
        store = Store(self.home / "state.db")
        config = self.config()
        router = ModelRouter(config, store=store)
        for index in range(3):
            store.save_model_performance(
                {
                    "id": f"perf-{index}",
                    "category": "debugging",
                    "provider": "mock",
                    "model": "mock-standard",
                    "success": 1,
                    "verified": 0,
                    "sources": [],
                }
            )
            store.mark_model_performance_verified(f"none-{index}", "verified")
        score, reasons = router._learned_score("debugging", "mock", "mock-standard")
        self.assertEqual(score, 0.0)
        self.assertEqual(reasons, ["unverified model history was ignored"])
        for index in range(3):
            store.mark_model_performance_verified(f"experience-{index}", "verified")
            store.save_model_performance(
                {
                    "id": f"verified-{index}",
                    "category": "debugging",
                    "provider": "mock",
                    "model": "mock-standard",
                    "success": 0,
                    "verified": 1,
                    "sources": ["tests"],
                    "experience_id": f"experience-{index}",
                }
            )
        score, reasons = router._learned_score("debugging", "mock", "mock-standard")
        self.assertLess(score, 0.0)
        self.assertTrue(any("verified history" in item for item in reasons))
        self.assertEqual(store.reset_model_performance(category="debugging"), 6)

    def test_record_performance_accepts_verified_status_from_real_turns(self):
        store = Store(self.home / "state.db")
        router = ModelRouter(self.config(), store=store)
        requirement = classify_task("Explain caching", self.config())
        decision = RoutingDecision(provider="mock", model="mock-standard", eligible=True)
        item = router.record_performance(
            requirement,
            decision,
            True,
            usage={"prompt_tokens": 10, "completion_tokens": 2},
            verification={"status": "verified", "sources": ["tests"]},
        )
        self.assertEqual(item["verified"], 1)
        rows = store.list_model_performance(provider="mock", model="mock-standard")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["verified"], 1)

    def test_verification_requires_successful_exit_code(self):
        agent = Agent(self.config(), home=self.home, persist=False, enable_subagents=False)
        failing = SimpleNamespace(
            tool_log=[
                {
                    "name": "python",
                    "arguments": {"code": "pytest -q"},
                    "ok": True,
                    "result": '{"exit_code": 1, "output": "1 failed"}',
                }
            ],
            final_text="all tests passed",
        )
        verification = agent._verification_from_state(failing)
        self.assertEqual(verification["status"], "unverified")
        self.assertFalse(verification["verified"])
        self.assertEqual(verification["sources"], [])
        passing = SimpleNamespace(
            tool_log=[
                {
                    "name": "terminal",
                    "arguments": {"command": "python3 -m unittest discover -s tests -q"},
                    "ok": True,
                    "result": '{"exit_code": 0, "output": "OK"}',
                }
            ],
            final_text="all tests passed",
        )
        verification = agent._verification_from_state(passing)
        self.assertEqual(verification["status"], "verified")
        self.assertTrue(verification["verified"])
        self.assertIn("tests", verification["sources"])

    def test_context_budget_uses_capability_window_with_safety_margin(self):
        config = self.config(
            context_tokens=8192,
            models={"metadata": {"mock/small": {"context_window": 1000, "evidence": {"context_window": "verified"}}}},
        )
        manager = ContextManager(config)
        budget = manager.budget([{"role": "user", "content": "hello"}], provider="mock", model="small")
        self.assertEqual(budget["limit"], 900)
        self.assertIn("capability fact", budget["source"])

    def test_context_overflow_recovery_preserves_tool_result_id(self):
        config = self.config(context_tokens=1024, compression_threshold=0.2)
        provider = _OverflowOnceProvider()
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "old request"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "call_keep", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}
                ],
            },
            {"role": "tool", "tool_call_id": "call_keep", "name": "read_file", "content": "important result"},
            {"role": "assistant", "content": "interim"},
            {"role": "user", "content": "continue"},
        ]
        statuses = []
        state = TurnState(
            messages=messages,
            system_prompt="system",
            tools=[],
            provider_candidates=[provider],
            provider_manager=ProviderManager(config),
            context_manager=ContextManager(config),
            executor=None,
            config=config,
            routing_decision={"provider": "mock", "model": "mock-standard"},
            on_status=lambda item: statuses.append(item),
        )
        result = run_turn_loop(state)
        self.assertEqual(result.exit_reason, "complete")
        self.assertEqual(len(result.context_recovery), 1)
        self.assertTrue(any(item.get("kind") == "context_recovered" for item in statuses))
        self.assertTrue(any(item.get("tool_call_id") == "call_keep" and item.get("content") == "important result" for item in result.messages))

    def test_context_recovery_skips_orphan_tool_results_and_caps_content(self):
        config = self.config(context_tokens=512)
        provider = _OverflowOnceProvider()
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "request"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "call_drop", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}
                ],
            },
            {"role": "tool", "tool_call_id": "call_drop", "name": "read_file", "content": "dropped data"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "call_keep", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}
                ],
            },
            {"role": "tool", "tool_call_id": "call_keep", "name": "read_file", "content": "x" * 4000},
            {"role": "user", "content": "continue"},
        ]
        state = TurnState(
            messages=messages,
            system_prompt="system",
            tools=[],
            provider_candidates=[provider],
            provider_manager=ProviderManager(config),
            context_manager=_CompressingContext(),
            executor=None,
            config=config,
        )
        recovery = _recover_context(state, provider, "prompt is too long")
        self.assertFalse(any(item.get("tool_call_id") == "call_drop" for item in state.messages))
        tool = next(item for item in state.messages if item.get("tool_call_id") == "call_keep")
        self.assertLess(len(tool["content"]), 4000)
        self.assertEqual(recovery["tokens_after"], message_tokens(state.messages))
        self.assertLessEqual(recovery["tokens_after"], 512)
        self.assertGreaterEqual(recovery["restored_tool_results"], 1)

    def test_http_context_length_error_triggers_recovery(self):
        config = self.config(
            streaming=False,
            costs={"confirm_paid": False},
            context_tokens=1024,
            compression_threshold=0.2,
        )
        provider = OpenAICompatibleProvider(
            config,
            "gpt-4o-mini",
            provider_spec("openai"),
            "https://example.invalid/v1",
            "test-key",
        )
        error = urllib.error.HTTPError(
            "https://example.invalid/v1/chat/completions",
            400,
            "Bad Request",
            {},
            io.BytesIO(b'{"error":{"message":"maximum context length is 10 tokens"}}'),
        )
        payload = {
            "choices": [{"message": {"content": "done"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2},
        }
        success = _FakeHTTPResponse(json.dumps(payload).encode("utf-8"))
        statuses = []
        state = TurnState(
            messages=[
                {"role": "system", "content": "system"},
                {"role": "user", "content": "old request"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"id": "call_keep", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}
                    ],
                },
                {"role": "tool", "tool_call_id": "call_keep", "name": "read_file", "content": "important result"},
                {"role": "user", "content": "continue"},
            ],
            system_prompt="system",
            tools=[],
            provider_candidates=[provider],
            provider_manager=ProviderManager(config),
            context_manager=ContextManager(config),
            executor=None,
            config=config,
            on_status=lambda item: statuses.append(item),
        )
        with patch("aether.providers.openai_compatible.urllib.request.urlopen", side_effect=[error, success]):
            result = run_turn_loop(state)
        self.assertEqual(result.exit_reason, "complete")
        self.assertTrue(any(item.get("kind") == "context_recovered" for item in statuses))
        self.assertTrue(any(item.get("tool_call_id") == "call_keep" for item in result.messages))

    def test_provider_failure_emits_routing_fallback_status(self):
        config = self.config()
        fallback = _OverflowOnceProvider()
        fallback.name = "ollama"
        fallback.model = "llama3.2:3b"
        statuses = []
        state = TurnState(
            messages=[{"role": "user", "content": "hello"}],
            system_prompt="",
            tools=[],
            provider_candidates=[_ProviderErrorStub(), fallback],
            provider_manager=ProviderManager(config),
            context_manager=ContextManager(config),
            executor=None,
            config=config,
            on_status=lambda item: statuses.append(item),
        )
        result = run_turn_loop(state)
        self.assertEqual(result.exit_reason, "complete")
        fallback_event = next(item for item in statuses if item.get("kind") == "routing_fallback")
        self.assertEqual(fallback_event["from"], "mock")
        self.assertEqual(fallback_event["to"], "ollama")

    def test_provider_health_is_local_state_only(self):
        manager = ProviderManager(self.config())
        manager.mark_failed("mock", 60, "rate limit")
        health = manager.health()
        self.assertEqual(health["mock"]["status"], "cooling")
        self.assertEqual(health["mock"]["reason"], "rate limit")
        self.assertGreater(health["mock"]["retry_after_seconds"], 0)

    def test_role_catalog_includes_phase_e_roles_with_approval_constraints(self):
        names = set(ROLE_NAMES)
        expected = {"planner", "architect", "tester", "security_auditor", "data_analyst", "documentation_writer"}
        self.assertTrue(expected.issubset(names))
        roles = resolved_roles(self.config())
        self.assertEqual(roles["planner"]["role"], "planner")
        self.assertTrue(set(roles["tester"]["require_approval"]) & FORCED_APPROVAL_TOOLS)
        self.assertTrue(set(roles["documentation_writer"]["require_approval"]) & FORCED_APPROVAL_TOOLS)

    def test_orchestrator_role_preferred_and_fallbacks_are_configured_entries(self):
        config = self.config(
            orchestrator={
                "roles": {
                    "planner": {
                        "preferred": "mock/special",
                        "fallbacks": ["mock/backup"],
                    }
                }
            }
        )
        entries = CapabilityRegistry(config).configured_entries(role="planner")
        self.assertIn(("mock", "special"), entries)
        self.assertIn(("mock", "backup"), entries)

    def test_diagnostics_do_not_call_a_model(self):
        self.assertIn("/models", SLASH_COMMANDS)
        with patch("aether.core.Agent.run_turn", side_effect=AssertionError("model called")):
            code, output = self._cli(["--provider", "mock", "models", "list"])
            self.assertEqual(code, 0)
            self.assertIn("mock-standard", output)
            code, output = self._cli(["--provider", "mock", "models", "health"])
            self.assertEqual(code, 0)
            self.assertIn("does not poll", output)
            code, output = self._cli(["--provider", "mock", "models", "routing", "Build a Python function"])
            self.assertEqual(code, 0)
            payload = json.loads(output)
            self.assertEqual(payload["provider"], "mock")

    def test_child_role_share_does_not_shrink_parent_budget(self):
        agent = Agent(
            self.config(costs={"confirm_paid": False, "max_estimated_usd_per_turn": 1.0}),
            home=self.home,
            persist=False,
            enable_subagents=False,
            enable_orchestrator=False,
        )
        child = agent._orchestration_child(
            {"role": "tester", "provider": "mock", "model": "mock-standard", "spend_share": 0.2, "allowed_tools": []},
            {},
            {},
            threading.Event(),
        )
        self.assertIsNotNone(child.turn_limit)
        self.assertLessEqual(child.turn_limit, 0.2)
        result = child.run_turn("hello")
        self.assertEqual(result.exit_reason, "complete")
        self.assertEqual(agent.spend_budget["limit"], 1.0)

    def test_configured_fallbacks_remain_in_runtime_candidates(self):
        config = self.config(fallback_providers=["ollama"], routing={"max_candidates": 1})
        agent = Agent(config, home=self.home, persist=False, enable_subagents=False)
        captured = []
        original = agent.provider_manager.candidates_for

        def capture(entries):
            captured.append(list(entries))
            return original(entries)

        with patch.object(agent.provider_manager, "candidates_for", side_effect=capture):
            result = agent.run_turn("hello")
        self.assertEqual(result.exit_reason, "complete")
        self.assertTrue(captured)
        self.assertTrue(any(entry[0] == "ollama" for entry in captured[0]))

    def test_routing_status_events_are_timestamped_and_redacted(self):
        statuses = []
        agent = Agent(self.config(), home=self.home, persist=False, enable_subagents=False)
        agent.run_turn("sensitive task text", on_status=lambda item: statuses.append(item))
        decision_event = next(item for item in statuses if item.get("kind") == "routing_decision")
        self.assertIn("T", decision_event["at"])
        self.assertNotIn("text", decision_event["decision"]["requirements"])
        limited = Agent(self.config(), home=self.home, persist=False, enable_subagents=False)
        limited_statuses = []
        limitation = RoutingDecision(eligible=False, reasons=["none"], requirements={"text": "sensitive task text"})
        with patch.object(limited.model_router, "route", return_value=limitation):
            result = limited.run_turn("sensitive task text", on_status=lambda item: limited_statuses.append(item))
        self.assertEqual(result.exit_reason, "routing_error")
        limitation_event = next(item for item in limited_statuses if item.get("kind") == "routing_limitation")
        self.assertIn("T", limitation_event["at"])
        self.assertNotIn("text", limitation_event["requirements"])

    def test_benchmark_is_deterministic_and_offline(self):
        first = run_benchmark(self.config(), samples=2)
        second = run_benchmark(self.config(), samples=2)
        self.assertEqual(first, second)
        self.assertEqual(first["live_model_calls"], 0)
        self.assertEqual(first["network_calls"], 0)
        self.assertIn("success_rate", first["results"]["capability"]["summary"])
        self.assertIn("cost_per_success_usd", first["results"]["cost"]["summary"])
        self.assertGreater(
            first["results"]["capability"]["summary"]["success_rate"],
            first["results"]["fixed"]["summary"]["success_rate"],
        )
        self.assertNotIn("none", first["results"]["capability"]["selected_models"])
        self.assertIn("mock/bench-long", first["results"]["capability"]["selected_models"])


if __name__ == "__main__":
    unittest.main()
