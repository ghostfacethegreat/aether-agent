import unittest
from pathlib import Path

from aether.config import Config, load_config, load_environment
from aether.utils import redact, redact_mapping

from tests.base import TempHomeTest


class ConfigTests(TempHomeTest):
    def test_defaults_and_dotted_access(self):
        config = Config()
        self.assertEqual(config.get("provider"), "ollama")
        self.assertEqual(config.get("tool_permissions.mode"), "standard")
        config.set("providers.custom.base_url", "http://127.0.0.1:9000/v1")
        self.assertEqual(config.get("providers.custom.base_url"), "http://127.0.0.1:9000/v1")

    def test_save_and_reload(self):
        config = self.config(temperature=0.7)
        config.path = self.home / "config.json"
        config.save()
        loaded = load_config(config.path)
        self.assertEqual(loaded.get("provider"), "mock")
        self.assertEqual(loaded.get("temperature"), 0.7)

    def test_validation_warns_on_bad_values(self):
        config = self.config(provider="unknown", max_iterations=-1)
        warnings = config.validate()
        self.assertTrue(any("Unknown provider" in item for item in warnings))
        self.assertTrue(any("max_iterations" in item for item in warnings))

    def test_validation_warns_on_missing_cost_cap_for_billable_provider(self):
        config = self.config(provider="openai", model="gpt-4o-mini")
        warnings = config.validate()
        self.assertTrue(any("cost cap" in item for item in warnings))

    def test_environment_file_does_not_override_existing(self):
        path = self.home / ".env"
        path.write_text("GROQ_API_KEY=from-file\nMOCK_ONLY=abc\n", encoding="utf-8")
        import os

        os.environ["GROQ_API_KEY"] = "existing"
        self.addCleanup(os.environ.pop, "GROQ_API_KEY", None)
        self.addCleanup(os.environ.pop, "MOCK_ONLY", None)
        load_environment(path)
        self.assertEqual(os.environ["GROQ_API_KEY"], "existing")
        self.assertEqual(os.environ["MOCK_ONLY"], "abc")

    def test_secret_redaction(self):
        self.assertEqual(redact("key sk-abcdefghijklmnop"), "key [REDACTED]")
        redacted = redact_mapping({"api_key": "secret", "nested": {"token": "abc"}})
        self.assertEqual(redacted["api_key"], "[REDACTED]")
        self.assertEqual(redacted["nested"]["token"], "[REDACTED]")


if __name__ == "__main__":
    unittest.main()
