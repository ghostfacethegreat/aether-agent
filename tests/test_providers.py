import json
import unittest

from aether.errors import ConfigError, ProviderError
from aether.providers import ProviderManager, build_provider
from aether.providers.catalog import PROVIDERS, provider_spec, rough_cost

from tests.base import TempHomeTest


class ProviderTests(TempHomeTest):
    def test_catalog_has_honest_cost_classes(self):
        self.assertEqual(PROVIDERS["ollama"].kind, "local")
        self.assertEqual(PROVIDERS["groq"].kind, "free-tier")
        self.assertEqual(PROVIDERS["openai"].kind, "paid")
        self.assertIn("free", PROVIDERS["openrouter"].cost.lower())

    def test_rough_cost_uses_model_specific_prices(self):
        usage = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}
        self.assertEqual(rough_cost("openai", "gpt-4o-mini", usage), 0.75)
        self.assertIsNone(rough_cost("openai", "gpt-4o", usage))
        self.assertEqual(rough_cost("anthropic", "claude-3-5-haiku-latest", usage), 4.8)
        self.assertIsNone(rough_cost("groq", "llama-3.3-70b-versatile", usage))
        self.assertEqual(
            rough_cost("openrouter", "meta-llama/llama-3.3-70b-instruct:free", usage),
            0.0,
        )
        self.assertEqual(
            rough_cost(
                "openai",
                "gpt-4o-mini",
                {
                    "prompt_tokens": 1_000_000,
                    "completion_tokens": 0,
                    "prompt_tokens_details": {"cached_tokens": 500_000},
                },
            ),
            0.1125,
        )
        self.assertEqual(
            rough_cost(
                "anthropic",
                "claude-3-5-haiku-latest",
                {
                    "input_tokens": 1_000_000,
                    "cache_read_input_tokens": 500_000,
                    "cache_creation_input_tokens": 200_000,
                    "output_tokens": 0,
                },
            ),
            1.04,
        )

    def test_extra_headers_are_applied_without_logging_values(self):
        config = self.config(
            providers={
                "openai": {
                    "api_key": "test-key",
                    "extra_headers": {
                        "X-Trace": "trace-secret-value",
                        "Authorization": "Bearer attacker-key",
                        "X-Api-Key": "attacker-key",
                    },
                }
            }
        )
        provider = build_provider(config, "openai")
        headers = provider._headers()
        self.assertEqual(headers["X-Trace"], "trace-secret-value")
        self.assertEqual(headers["Authorization"], "Bearer test-key")
        self.assertNotIn("X-Api-Key", headers)
        described = json.dumps(provider.describe())
        self.assertIn("X-Trace", described)
        self.assertNotIn("trace-secret-value", described)

    def test_malformed_or_protected_extra_headers_are_dropped(self):
        config = self.config(
            providers={
                "openai": {
                    "api_key": "test-key",
                    "extra_headers": {
                        "X-Trace": "safe",
                        "X-Injected": "ok\r\n X-Injected: evil",
                        "Bad\r\nName": "evil",
                        "content-length": "0",
                        "X_Api_Key": "attacker-key",
                        " authorization ": "Bearer attacker-key",
                    },
                }
            }
        )
        provider = build_provider(config, "openai")
        headers = provider._headers()
        self.assertEqual(headers["X-Trace"], "safe")
        self.assertNotIn("X-Injected", headers)
        self.assertNotIn("Bad\r\nName", headers)
        self.assertNotIn("content-length", headers)
        self.assertNotIn("X_Api_Key", headers)
        self.assertNotIn(" authorization ", headers)
        described = json.dumps(provider.describe())
        self.assertNotIn("\r", described)
        self.assertNotIn("\n", described)
        self.assertNotIn("attacker-key", described)

    def test_payload_forwards_top_p(self):
        provider = build_provider(self.config(providers={"openai": {"api_key": "test-key"}}), "openai")
        payload = provider._payload(
            [{"role": "user", "content": "Hello"}],
            None,
            False,
            {"top_p": 0.7},
        )
        self.assertEqual(payload["top_p"], 0.7)

    def test_build_mock_provider(self):
        provider = build_provider(self.config(), "mock")
        self.assertEqual(provider.name, "mock")
        self.assertEqual(provider.model, "mock-standard")
        self.assertIn("no network", provider.describe()["cost"].lower())

    def test_custom_provider_requires_base_url(self):
        with self.assertRaises(ConfigError):
            build_provider(self.config(), "custom")

    def test_mock_streaming_and_usage(self):
        provider = build_provider(self.config(), "mock")
        deltas = []
        response = provider.chat(
            [{"role": "user", "content": "Hello"}],
            stream=True,
            on_delta=lambda text, kind="content": deltas.append(text),
        )
        self.assertTrue(deltas)
        self.assertEqual("".join(deltas), response.content)
        self.assertGreater(response.usage["prompt_tokens"], 0)

    def test_mock_scripted_failure(self):
        config = self.config(providers={"mock": {"script": [{"error": "boom"}]}})
        provider = build_provider(config, "mock")
        with self.assertRaises(ProviderError):
            provider.chat([{"role": "user", "content": "Hello"}])

    def test_openai_sse_parser_accumulates_tool_arguments(self):
        provider = build_provider(self.config(providers={"openai": {"api_key": "test-key"}}), "openai")

        class FakeStream:
            def __init__(self, lines):
                self.lines = lines

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def __iter__(self):
                return iter(self.lines)

        def chunk(payload):
            return ("data: " + json.dumps(payload) + "\n\n").encode()

        lines = [
            chunk({"choices": [{"delta": {"content": "Working"}, "finish_reason": None}]}),
            chunk(
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": "call_1",
                                        "function": {"name": "read_file", "arguments": '{"path": "'},
                                    }
                                ]
                            },
                            "finish_reason": None,
                        }
                    ]
                }
            ),
            chunk({"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "a.txt\"}"}}]}, "finish_reason": "tool_calls"}]}),
            chunk({"usage": {"prompt_tokens": 12, "completion_tokens": 7}}),
            b"data: [DONE]\n\n",
        ]
        deltas = []
        response = provider._read_stream(FakeStream(lines), lambda text, kind="content": deltas.append(text))
        self.assertEqual(response.content, "Working")
        self.assertEqual(deltas, ["Working"])
        self.assertEqual(len(response.tool_calls), 1)
        self.assertEqual(response.tool_calls[0].name, "read_file")
        self.assertEqual(response.tool_calls[0].arguments, {"path": "a.txt"})
        self.assertEqual(response.usage["prompt_tokens"], 12)

    def test_manager_fallback_and_cooldown(self):
        config = self.config(fallback_providers=["lmstudio"])
        manager = ProviderManager(config)
        candidates = manager.candidates()
        self.assertEqual([item.name for item in candidates], ["mock", "lmstudio"])
        manager.mark_failed("lmstudio", 30)
        self.assertEqual([item.name for item in manager.candidates()], ["mock"])
        self.assertFalse(hasattr(manager, "clear_failure"))
        provider = manager.activate("mock", "mock-tools")
        self.assertEqual(provider.model, "mock-tools")
        self.assertEqual(config.get("model"), "mock-tools")


    def test_anthropic_replays_nested_tool_calls(self):
        provider = build_provider(self.config(providers={"anthropic": {"api_key": "test-key"}}), "anthropic")
        system, converted = provider._convert_messages(
            [
                {"role": "system", "content": "system"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "read_file", "arguments": '{"path":"a.txt"}'},
                        }
                    ],
                },
                {"role": "tool", "tool_call_id": "call_1", "name": "read_file", "content": "file body"},
            ]
        )
        self.assertEqual(system, "system")
        self.assertEqual(converted[0]["content"][0]["type"], "tool_use")
        self.assertEqual(converted[0]["content"][0]["name"], "read_file")
        self.assertEqual(converted[0]["content"][0]["input"], {"path": "a.txt"})
        self.assertEqual(converted[1]["content"][0]["tool_use_id"], "call_1")


if __name__ == "__main__":
    unittest.main()
