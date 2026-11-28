import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

from aether.cli.app import main
from aether.persistence import Store
from aether.ventures import VentureLedger

from tests.base import TempHomeTest


class VentureCliTests(TempHomeTest):
    def run_cli(self, argv):
        output = io.StringIO()
        errors = io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = main(argv)
        return code, output.getvalue(), errors.getvalue()

    def test_add_list_and_brief_are_offline(self):
        code, output, _ = self.run_cli([
            "venture", "add", "lead", "Local gym", "--status", "qualified",
            "--details-json", '{"source_url":"https://example.com","fit_notes":"Needs clips"}',
        ])
        self.assertEqual(code, 0)
        self.assertIn("saved lead", output)

        code, output, _ = self.run_cli([
            "venture", "add", "quote", "Five clip pilot",
            "--status", "sent", "--amount-cents", "15000",
        ])
        self.assertEqual(code, 0)
        self.assertIn("saved quote", output)

        code, output, _ = self.run_cli(["venture", "list", "--kind", "lead"])
        self.assertEqual(code, 0)
        self.assertIn("Local gym", output)

        code, output, _ = self.run_cli(["venture", "brief"])
        self.assertEqual(code, 0)
        self.assertIn("Open leads", output)
        self.assertIn("$150.00", output)
        self.assertIn("not verified bank balances", output)

    def test_cli_rejects_sensitive_fields_and_invalid_json(self):
        code, _, errors = self.run_cli([
            "venture", "add", "client", "Unsafe record",
            "--details-json", '{"bank_account":"do-not-store"}',
        ])
        self.assertEqual(code, 1)
        self.assertIn("not allowed", errors)

        code, _, errors = self.run_cli([
            "venture", "add", "lead", "Bad json", "--details-json", "not-json",
        ])
        self.assertEqual(code, 1)
        self.assertIn("valid JSON", errors)

    def test_cli_updates_status_and_records_audit_event(self):
        code, output, _ = self.run_cli(["venture", "add", "project", "Clip pilot"])
        self.assertEqual(code, 0)
        record_id = VentureLedger(Store(self.home / "state.db")).list(kind="project")[0]["id"]
        code, output, _ = self.run_cli(["venture", "update", record_id, "--status", "active"])
        self.assertEqual(code, 0)
        code, output, _ = self.run_cli(["venture", "events", record_id])
        self.assertEqual(code, 0)
        self.assertIn("created", output)
        self.assertIn("updated", output)


if __name__ == "__main__":
    unittest.main()
