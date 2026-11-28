import unittest

from aether.orchestration.contracts import validate_role_output


class RoleContractTests(unittest.TestCase):
    def test_verifier_requires_structured_fields(self):
        self.assertTrue(validate_role_output("verifier", {"summary": "done", "verdict": "pass"}))
        self.assertEqual(
            validate_role_output(
                "verifier",
                {"summary": "done", "checks": ["bash scripts/check.sh"], "failures": [], "verdict": "pass"},
            ),
            [],
        )

    def test_verdict_enums_are_checked(self):
        errors = validate_role_output(
            "tester",
            {"summary": "done", "checks": [], "failures": [], "verdict": "probably"},
        )
        self.assertTrue(any("verdict must be one of" in item for item in errors))

    def test_unknown_roles_are_not_forced_into_a_contract(self):
        self.assertEqual(validate_role_output("custom_role", {"summary": "ok"}), [])


if __name__ == "__main__":
    unittest.main()
