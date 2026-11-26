import re
import unittest
from unittest.mock import patch

from aether.cli import render


class RenderTests(unittest.TestCase):
    def tearDown(self):
        render.configure({})

    def test_sanitize_untrusted_removes_terminal_control_sequences(self):
        value = "safe\x1b[2J\x1b]0;title\x07\x1b[31mbad\x1b[0m\u202e\u0000 still safe"
        self.assertEqual(render.sanitize_untrusted(value), "safebad still safe")

    def test_banner_contains_product_name_and_version(self):
        render.configure({"theme": "acid-blue"})
        output = render.banner("0.1.0")
        self.assertIn("AETHER", output)
        self.assertIn("0.1.0", output)
        self.assertIn("LOCAL-FIRST AGENT", output)

    def test_banner_can_be_disabled(self):
        render.configure({"show_banner": False})
        self.assertEqual(render.banner("0.1.0"), "")

    def test_ascii_mode_avoids_unicode_art(self):
        render.configure({"unicode": False})
        output = render.banner("0.1.0")
        self.assertIn("#", output)
        self.assertNotIn("█", output)
        self.assertNotIn("░", output)
        self.assertIn("aether", render.prompt())

    def test_dashboard_contains_runtime_fields(self):
        render.configure({})
        output = render.dashboard({
            "kind": "local",
            "provider": "ollama",
            "model": "llama3.2:3b",
            "session": "abc123",
            "messages": 3,
            "tools": 5,
            "skills": 2,
            "memories": 4,
            "workspace": "/tmp/project",
            "cost": "$0.00",
            "limits": "budget ok",
        })
        for expected in ("SESSION OVERVIEW", "ollama (local)", "llama3.2:3b", "abc123", "/tmp/project"):
            self.assertIn(expected, output)

    def test_dashboard_can_be_disabled(self):
        render.configure({"show_dashboard": False})
        self.assertEqual(render.dashboard({}), "")

    def test_compact_banner_respects_narrow_terminal(self):
        with patch.object(render, "terminal_width", return_value=40):
            output = render.banner("0.1.0")
        self.assertIn("AETHER", output)
        # ANSI SGR color sequences do not occupy visible terminal columns.
        for line in output.splitlines():
            visible = re.sub(r"\x1b\[[0-9;]*m", "", line)
            self.assertLessEqual(len(visible), 40)

    def test_response_labels_can_be_disabled(self):
        render.configure({"show_response_labels": False})
        self.assertEqual(render.assistant_prefix(), "")
        self.assertEqual(render.reasoning_prefix(), "")

    def test_prompt_and_response_prefix_are_distinct(self):
        render.configure({})
        self.assertIn("aether", render.prompt())
        render.configure({"unicode": False})
        ascii_status = render.status_line({"kind": "routing_fallback", "from": "local", "to": "hosted"})
        self.assertNotIn("→", ascii_status)
        self.assertNotIn("·", ascii_status)
        self.assertIn("AETHER", render.assistant_prefix())
        self.assertIn("REASONING", render.reasoning_prefix())


if __name__ == "__main__":
    unittest.main()
