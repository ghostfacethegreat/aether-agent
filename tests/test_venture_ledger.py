import unittest

from aether.persistence import Store
from aether.ventures import VentureLedger

from tests.base import TempHomeTest


class VentureLedgerTests(TempHomeTest):
    def setUp(self):
        super().setUp()
        self.store = Store(self.home / "state.db")
        self.ledger = VentureLedger(self.store)

    def test_create_list_update_and_audit_events(self):
        lead = self.ledger.create(
            "lead",
            "Example bakery",
            status="qualified",
            details={"source_url": "https://example.com", "fit_notes": "Needs short clips"},
        )
        self.assertEqual(lead["kind"], "lead")
        self.assertEqual(lead["details"]["fit_notes"], "Needs short clips")
        self.assertEqual(self.ledger.list(kind="lead")[0]["id"], lead["id"])

        updated = self.ledger.update(lead["id"], status="contacted", name="Example bakery lead")
        self.assertEqual(updated["status"], "contacted")
        self.assertEqual(updated["name"], "Example bakery lead")
        events = self.ledger.events(lead["id"])
        self.assertEqual([item["action"] for item in events], ["updated", "created"])

    def test_money_summary_separates_pipeline_booked_invoiced_received_and_expenses(self):
        self.ledger.create("quote", "Draft quote", status="sent", amount_cents=25_000)
        self.ledger.create("quote", "Accepted quote", status="accepted", amount_cents=40_000)
        self.ledger.create("invoice", "Invoice 001", status="invoiced", amount_cents=40_000)
        self.ledger.create("receipt", "Cash receipt 001", status="paid", amount_cents=40_000)
        self.ledger.create("receipt", "Pending payment note", status="open", amount_cents=9_000)
        self.ledger.create("expense", "Storage expense", status="paid", amount_cents=2_000)

        brief = self.ledger.brief()
        self.assertEqual(brief["pipeline_cents"], 25_000)
        self.assertEqual(brief["booked_cents"], 40_000)
        self.assertEqual(brief["invoiced_cents"], 40_000)
        self.assertEqual(brief["received_cents"], 40_000)
        self.assertEqual(brief["expense_cents"], 2_000)

    def test_rejects_credential_and_identity_fields(self):
        for key in ("bank_account", "password", "api_key", "passport_number", "ssn"):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    self.ledger.create("client", "Do not store secrets", details={key: "private"})

    def test_rejects_invalid_amount_and_unknown_kind(self):
        with self.assertRaises(ValueError):
            self.ledger.create("lead", "Bad amount", amount_cents=-1)
        with self.assertRaises(ValueError):
            self.ledger.create("employee", "Unknown kind")
        with self.assertRaises(ValueError):
            self.ledger.create("receipt", "Mixed currency", currency="EUR", amount_cents=100)

    def test_records_persist_after_store_reopen(self):
        record = self.ledger.create("project", "Five clip pilot", status="active")
        reopened = VentureLedger(Store(self.home / "state.db"))
        self.assertEqual(reopened.get(record["id"])["name"], "Five clip pilot")


if __name__ == "__main__":
    unittest.main()
