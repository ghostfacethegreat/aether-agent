import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_NAMES = ("aether-lead", "architect", "implementer", "qa", "reviewer", "income-scout", "payment-pathfinder", "coding-triager", "proposal-writer", "offer-strategist", "rights-reviewer", "bookkeeper", "customer-success")
BUSINESS_READ_ONLY = ("income-scout", "payment-pathfinder", "coding-triager", "proposal-writer", "offer-strategist", "rights-reviewer", "bookkeeper", "customer-success")


class OpenCodeAgentConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / "opencode.json").read_text(encoding="utf-8"))

    def test_config_selects_the_team_lead_and_defines_all_agent_profiles(self):
        self.assertEqual(self.config["default_agent"], "aether-lead")
        agents = self.config["agents"]
        self.assertEqual(set(agents), set(AGENT_NAMES))
        self.assertEqual(agents["aether-lead"]["mode"], "primary")
        for name in AGENT_NAMES[1:]:
            self.assertEqual(agents[name]["mode"], "subagent")

    def test_each_agent_has_a_markdown_system_prompt_without_legacy_frontmatter(self):
        for name in AGENT_NAMES:
            with self.subTest(agent=name):
                prompt = (ROOT / ".opencode" / "agents" / f"{name}.md").read_text(encoding="utf-8")
                self.assertTrue(prompt.strip())
                self.assertFalse(prompt.startswith("---\n"))

    def test_read_only_roles_cannot_edit(self):
        agents = self.config["agents"]
        for name in ("aether-lead", "qa"):
            with self.subTest(agent=name):
                rules = agents[name]["permissions"]
                self.assertIn(
                    {"action": "edit", "resource": "*", "effect": "deny"},
                    rules,
                )
        for name in ("architect", "reviewer", *BUSINESS_READ_ONLY):
            with self.subTest(agent=name):
                rules = agents[name]["permissions"]
                self.assertIn(
                    {"action": "*", "resource": "*", "effect": "deny"},
                    rules,
                )
                self.assertIn(
                    {"action": "read", "resource": "*", "effect": "allow"},
                    rules,
                )

    def test_lead_delegates_only_to_named_specialists(self):
        rules = self.config["agents"]["aether-lead"]["permissions"]
        self.assertIn(
            {"action": "subagent", "resource": "*", "effect": "deny"},
            rules,
        )
        for name in AGENT_NAMES[1:]:
            self.assertIn(
                {"action": "subagent", "resource": name, "effect": "allow"},
                rules,
            )

    def test_implementer_cannot_push_tag_or_merge(self):
        rules = self.config["agents"]["implementer"]["permissions"]
        for command in ("git push *", "git tag *", "gh pr merge *"):
            with self.subTest(command=command):
                self.assertIn(
                    {"action": "shell", "resource": command, "effect": "deny"},
                    rules,
                )


if __name__ == "__main__":
    unittest.main()
