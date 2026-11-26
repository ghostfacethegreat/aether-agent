import json
import re
from typing import Any, List

from aether.persistence import Store
from aether.utils import make_id, utc_now

KINDS = (
    "lead",
    "offer",
    "client",
    "quote",
    "project",
    "deliverable",
    "invoice",
    "receipt",
    "expense",
)
STATUSES = (
    "open",
    "qualified",
    "contacted",
    "draft",
    "sent",
    "proposed",
    "accepted",
    "active",
    "blocked",
    "delivered",
    "invoiced",
    "paid",
    "overdue",
    "rejected",
    "cancelled",
    "void",
    "archived",
)
_FORBIDDEN_KEY = re.compile(
    r"(?:password|passwd|secret|token|api[_-]?key|authorization|cookie|"
    r"bank|routing|account[_-]?number|card|cvv|cvc|ssn|social[_-]?security|"
    r"passport|drivers?[_-]?license|identity[_-]?document|recovery[_-]?code)",
    re.I,
)
_NAME_LIMIT = 160
_MAX_DETAILS_BYTES = 16_000
_MAX_AMOUNT_CENTS = 100_000_000_000


def _validate_details(value: Any, depth: int = 0) -> Any:
    if depth > 5:
        raise ValueError("details may not be nested more than five levels")
    if isinstance(value, dict):
        clean = {}
        for raw_key, item in value.items():
            key = str(raw_key).strip()
            if not key or len(key) > 64:
                raise ValueError("detail keys must be 1–64 characters")
            if _FORBIDDEN_KEY.search(key):
                raise ValueError(f"detail field '{key}' is not allowed; do not store credentials or identity data")
            clean[key] = _validate_details(item, depth + 1)
        return clean
    if isinstance(value, list):
        if len(value) > 100:
            raise ValueError("detail lists may contain at most 100 items")
        return [_validate_details(item, depth + 1) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if len(value) > 4_000:
            raise ValueError("individual detail values may not exceed 4,000 characters")
        return value
    raise ValueError("details must contain only JSON-compatible values")


def _json_details(value: Any) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("details must be a JSON object")
    clean = _validate_details(value)
    encoded = json.dumps(clean, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > _MAX_DETAILS_BYTES:
        raise ValueError("details may not exceed 16 KB")
    return clean


def _validate_amount(value: int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("amount_cents must be a whole number of cents")
    if value < 0 or value > _MAX_AMOUNT_CENTS:
        raise ValueError("amount_cents must be between 0 and 100,000,000,000")
    return value


class VentureLedger:
    """Small local business ledger backed by AETHER's existing SQLite database.

    The ledger records business activity only. It never sends messages, accepts
    contracts, connects financial accounts, or initiates payments.
    """

    def __init__(self, store: Store):
        self.store = store
        with self.store.connection() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS venture_records (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    amount_cents INTEGER,
                    currency TEXT NOT NULL DEFAULT 'USD',
                    details_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_venture_records_kind_status
                    ON venture_records(kind, status, updated_at);
                CREATE TABLE IF NOT EXISTS venture_events (
                    id TEXT PRIMARY KEY,
                    record_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(record_id) REFERENCES venture_records(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_venture_events_record
                    ON venture_events(record_id, created_at);
                """
            )

    @staticmethod
    def _decode(row) -> dict | None:
        if row is None:
            return None
        item = dict(row)
        try:
            item["details"] = json.loads(item.pop("details_json") or "{}")
        except (TypeError, ValueError):
            item["details"] = {}
        return item

    def _event(self, db, record_id: str, action: str, payload: dict) -> None:
        db.execute(
            "INSERT INTO venture_events(id,record_id,action,payload_json,created_at) VALUES(?,?,?,?,?)",
            (
                make_id("venture-event"),
                record_id,
                action,
                json.dumps(payload, ensure_ascii=False),
                utc_now(),
            ),
        )

    def create(
        self,
        kind: str,
        name: str,
        status: str = "open",
        amount_cents: int | None = None,
        currency: str = "USD",
        details: dict | None = None,
    ) -> dict:
        kind = str(kind or "").strip().lower()
        name = str(name or "").strip()
        status = str(status or "").strip().lower()
        currency = str(currency or "USD").strip().upper()
        if kind not in KINDS:
            raise ValueError(f"kind must be one of: {', '.join(KINDS)}")
        if not name or len(name) > _NAME_LIMIT:
            raise ValueError(f"name must be 1–{_NAME_LIMIT} characters")
        if status not in STATUSES:
            raise ValueError(f"status must be one of: {', '.join(STATUSES)}")
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise ValueError("currency must be a three-letter ISO-style code such as USD")
        if currency != "USD":
            raise ValueError("the VentureOps MVP currently supports USD records only")
        amount_cents = _validate_amount(amount_cents)
        details = _json_details(details)
        record_id = make_id("venture")
        now = utc_now()
        record = {
            "id": record_id,
            "kind": kind,
            "name": name,
            "status": status,
            "amount_cents": amount_cents,
            "currency": currency,
            "details": details,
            "created_at": now,
            "updated_at": now,
        }
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO venture_records(id,kind,name,status,amount_cents,currency,details_json,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    record_id,
                    kind,
                    name,
                    status,
                    amount_cents,
                    currency,
                    json.dumps(details, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            self._event(db, record_id, "created", {"kind": kind, "status": status})
        return record

    def get(self, record_id: str) -> dict | None:
        with self.store.connection() as db:
            row = db.execute("SELECT * FROM venture_records WHERE id=?", (str(record_id),)).fetchone()
        return self._decode(row)

    def list(self, kind: str | None = None, status: str | None = None, limit: int = 100) -> list[dict]:
        if kind and kind not in KINDS:
            raise ValueError(f"kind must be one of: {', '.join(KINDS)}")
        if status and status not in STATUSES:
            raise ValueError(f"status must be one of: {', '.join(STATUSES)}")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        sql = "SELECT * FROM venture_records WHERE 1=1"
        params: list[Any] = []
        if kind:
            sql += " AND kind=?"
            params.append(kind)
        if status:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self.store.connection() as db:
            rows = db.execute(sql, params).fetchall()
        return [self._decode(row) for row in rows]

    def update(
        self,
        record_id: str,
        status: str | None = None,
        name: str | None = None,
        amount_cents: int | None = None,
        set_amount: bool = False,
        details: dict | None = None,
    ) -> dict | None:
        current = self.get(record_id)
        if current is None:
            return None
        next_status = current["status"] if status is None else str(status).strip().lower()
        next_name = current["name"] if name is None else str(name).strip()
        next_amount = current["amount_cents"] if not set_amount else _validate_amount(amount_cents)
        next_details = current["details"] if details is None else _json_details(details)
        if next_status not in STATUSES:
            raise ValueError(f"status must be one of: {', '.join(STATUSES)}")
        if not next_name or len(next_name) > _NAME_LIMIT:
            raise ValueError(f"name must be 1–{_NAME_LIMIT} characters")
        now = utc_now()
        changes = {
            "status": next_status,
            "name": next_name,
            "amount_cents": next_amount,
            "details": next_details,
        }
        with self.store.connection() as db:
            db.execute(
                "UPDATE venture_records SET status=?,name=?,amount_cents=?,details_json=?,updated_at=? WHERE id=?",
                (
                    next_status,
                    next_name,
                    next_amount,
                    json.dumps(next_details, ensure_ascii=False),
                    now,
                    str(record_id),
                ),
            )
            self._event(db, str(record_id), "updated", changes)
        return self.get(record_id)

    def events(self, record_id: str, limit: int = 100) -> List[dict]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT * FROM venture_events WHERE record_id=? ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (str(record_id), limit),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["payload"] = json.loads(item.pop("payload_json") or "{}")
            except (TypeError, ValueError):
                item["payload"] = {}
            result.append(item)
        return result

    def brief(self) -> dict:
        records = self.list(limit=500)
        def total(kind: str, statuses: set[str] | None = None) -> int:
            return sum(
                int(item["amount_cents"] or 0)
                for item in records
                if item["kind"] == kind and (statuses is None or item["status"] in statuses)
            )
        return {
            "record_count": len(records),
            "open_leads": sum(1 for item in records if item["kind"] == "lead" and item["status"] not in {"archived", "rejected", "cancelled"}),
            "active_projects": sum(1 for item in records if item["kind"] == "project" and item["status"] in {"open", "active", "blocked"}),
            "pipeline_cents": total("quote", {"draft", "sent", "proposed"}),
            "booked_cents": total("quote", {"accepted"}),
            "invoiced_cents": total("invoice", {"invoiced", "sent", "overdue", "paid"}),
            "received_cents": total("receipt", {"paid"}),
            "expense_cents": total("expense", {"paid"}),
        }
