import json
import unittest

from aether.errors import ConfigError, ProviderError
from aether.providers import ProviderManager, build_provider
from aether.providers.catalog import PROVIDERS, provider_spec

from tests.base import TempHomeTest


class ProviderTests(TempHomeTest):
    def test_catalog_has_honest_cost_classes(self):
        self.assertEqual(PROVIDERS["ollama"].kind, "local")
        self.assertEqual(PROVIDERS["groq"].kind, "free-tier")
        self.assertEqual(PROVIDERS["openai"].kind, "paid")
        self.assertIn("free", PROVIDERS["openrouter"].cost.lower())

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
        provider = manager.activate("mock", "mock-tools")
        self.assertEqual(provider.model, "mock-tools")
        self.assertEqual(config.get("model"), "mock-tools")


if __name__ == "__main__":
    unittest.main()
