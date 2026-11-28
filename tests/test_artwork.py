import tempfile
import unittest
from pathlib import Path

from aether.cli.artwork import load_ansi_art, sanitize_ansi_art


class ArtworkTests(unittest.TestCase):
    def test_sanitizer_keeps_sgr_and_removes_cursor_and_osc_sequences(self):
        source = "\x1b[34mJUNIPER\x1b[0m\x1b[2J\x1b]0;owned-title\x07"
        result = sanitize_ansi_art(source, allow_color=True)
        self.assertIn("\x1b[34m", result)
        self.assertIn("JUNIPER", result)
        self.assertNotIn("\x1b[2J", result)
        self.assertNotIn("\x1b]", result)
        self.assertTrue(result.endswith("\x1b[0m"))

    def test_color_is_removed_when_disabled(self):
        result = sanitize_ansi_art("\x1b[31mred\x1b[0m", allow_color=False)
        self.assertEqual(result, "red")

    def test_width_and_line_limits_are_enforced(self):
        result = sanitize_ansi_art(
            "123456789\nsecond\nthird",
            max_width=5,
            max_lines=2,
        )
        self.assertEqual(result, "12345\nsecon")

    def test_unicode_fallback_rejects_non_ascii_art(self):
        self.assertEqual(sanitize_ansi_art("AETHER █", allow_unicode=False), "")

    def test_loader_rejects_wrong_extension_and_large_file(self):
        with tempfile.TemporaryDirectory() as temp:
            wrong = Path(temp) / "banner.sh"
            wrong.write_text("echo unsafe", encoding="utf-8")
            large = Path(temp) / "large.ansi"
            large.write_text("x" * (32 * 1024 + 1), encoding="utf-8")
            self.assertIsNone(load_ansi_art(wrong))
            self.assertIsNone(load_ansi_art(large))

    def test_loader_reads_sanitized_utf8_art(self):
        with tempfile.TemporaryDirectory() as temp:
            art = Path(temp) / "juniper.ansi"
            art.write_text("\x1b[94mJUNIPER\x1b[0m\x1b[2J", encoding="utf-8")
            result = load_ansi_art(art, allow_color=True)
            self.assertIn("JUNIPER", result)
            self.assertNotIn("\x1b[2J", result)

    def test_missing_art_falls_back(self):
        self.assertIsNone(load_ansi_art("/definitely/not/a/real/banner.ansi"))


if __name__ == "__main__":
    unittest.main()
