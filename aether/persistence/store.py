import json
import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from aether.utils import make_id, utc_now

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    provider TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    cwd TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    message_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL DEFAULT '',
    parent_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    result TEXT NOT NULL DEFAULT '',
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost REAL NOT NULL DEFAULT 0,
    cost_known INTEGER NOT NULL DEFAULT 0,
    priced_calls INTEGER NOT NULL DEFAULT 0,
    unpriced_calls INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
    rule_key TEXT PRIMARY KEY,
    decision TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS execution_plans (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL DEFAULT '',
    objective TEXT NOT NULL DEFAULT '',
    complexity TEXT NOT NULL DEFAULT '',
    route TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    plan_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_execution_plans_session ON execution_plans(session_id, updated_at);
CREATE TABLE IF NOT EXISTS execution_checkpoints (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    phase TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(plan_id) REFERENCES execution_plans(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_execution_checkpoints_plan ON execution_checkpoints(plan_id, sequence);
CREATE TABLE IF NOT EXISTS memory_items (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL DEFAULT '',
    layer TEXT NOT NULL,
    subject TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    provenance TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.5,
    status TEXT NOT NULL DEFAULT 'active',
    metadata TEXT NOT NULL DEFAULT '{}',
    supersedes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_memory_items_layer ON memory_items(layer, status, updated_at);
CREATE INDEX IF NOT EXISTS idx_memory_items_session ON memory_items(session_id, layer, status);
CREATE TABLE IF NOT EXISTS learning_experiences (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL DEFAULT '',
    objective TEXT NOT NULL DEFAULT '',
    classification TEXT NOT NULL DEFAULT '{}',
    plan_id TEXT NOT NULL DEFAULT '',
    plan TEXT NOT NULL DEFAULT '{}',
    agents TEXT NOT NULL DEFAULT '[]',
    models TEXT NOT NULL DEFAULT '[]',
    tools TEXT NOT NULL DEFAULT '[]',
    errors TEXT NOT NULL DEFAULT '[]',
    solution TEXT NOT NULL DEFAULT '',
    verification TEXT NOT NULL DEFAULT '{}',
    feedback TEXT NOT NULL DEFAULT '{}',
    outcome TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    provenance TEXT NOT NULL DEFAULT 'agent-turn',
    confidence REAL NOT NULL DEFAULT 0.5,
    verified INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_learning_experiences_session ON learning_experiences(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_learning_experiences_verified ON learning_experiences(verified, created_at);
CREATE TABLE IF NOT EXISTS learning_proposals (
    id TEXT PRIMARY KEY,
    skill_name TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'create',
    status TEXT NOT NULL DEFAULT 'proposed',
    content TEXT NOT NULL,
    meta TEXT NOT NULL DEFAULT '{}',
    evidence TEXT NOT NULL DEFAULT '[]',
    validation TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    decided_at TEXT NOT NULL DEFAULT '',
    decided_by TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_learning_proposals_skill ON learning_proposals(skill_name, status, created_at);
CREATE TABLE IF NOT EXISTS learning_versions (
    id TEXT PRIMARY KEY,
    skill_name TEXT NOT NULL,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'candidate',
    proposal_id TEXT NOT NULL DEFAULT '',
    score REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(skill_name, version)
);
CREATE INDEX IF NOT EXISTS idx_learning_versions_skill ON learning_versions(skill_name, version);
CREATE TABLE IF NOT EXISTS learning_metrics (
    skill_name TEXT PRIMARY KEY,
    active_version INTEGER NOT NULL DEFAULT 0,
    execution_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    verification_count INTEGER NOT NULL DEFAULT 0,
    total_duration_ms REAL NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost REAL NOT NULL DEFAULT 0,
    last_success_at TEXT NOT NULL DEFAULT '',
    last_modified_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS learning_events (
    id TEXT PRIMARY KEY,
    skill_name TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL DEFAULT '',
    payload TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_learning_events_skill ON learning_events(skill_name, created_at);
CREATE TABLE IF NOT EXISTS model_performance (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL DEFAULT '',
    provider TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    success INTEGER NOT NULL DEFAULT 0,
    verified INTEGER NOT NULL DEFAULT 0,
    sources TEXT NOT NULL DEFAULT '[]',
    tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost REAL NOT NULL DEFAULT 0,
    cost_known INTEGER NOT NULL DEFAULT 0,
    duration_ms REAL NOT NULL DEFAULT 0,
    recovery_attempts INTEGER NOT NULL DEFAULT 0,
    experience_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_model_performance_route ON model_performance(category, provider, model, created_at);
CREATE INDEX IF NOT EXISTS idx_model_performance_experience ON model_performance(experience_id);
"""

MESSAGE_FIELDS = ("name", "tool_call_id", "tool_calls")


def _encode_message_metadata(message: dict) -> str:
    metadata = dict(message.get("metadata") or {})
    fields = {}
    for key in MESSAGE_FIELDS:
        value = message.get(key)
        if value in (None, "", []):
            continue
        fields[key] = value
    if fields:
        metadata["__message_fields"] = fields
    return json.dumps(metadata, ensure_ascii=False)


def _decode_message_metadata(raw: str) -> tuple[dict, dict]:
    try:
        metadata = json.loads(raw or "{}")
    except ValueError:
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    fields = metadata.pop("__message_fields", None)
    return metadata, fields if isinstance(fields, dict) else {}


class Store:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(self.path, os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(descriptor)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass
        self._fts = False
        self.init()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path), timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def connection(self):
        db = self.connect()
        try:
            with db:
                yield db
        finally:
            db.close()

    def init(self) -> None:
        with self.connection() as db:
            db.executescript(SCHEMA)
            columns = {row["name"] for row in db.execute("PRAGMA table_info(usage)")}
            for name, definition in (
                ("cost_known", "INTEGER NOT NULL DEFAULT 0"),
                ("priced_calls", "INTEGER NOT NULL DEFAULT 0"),
                ("unpriced_calls", "INTEGER NOT NULL DEFAULT 0"),
            ):
                if name not in columns:
                    db.execute(f"ALTER TABLE usage ADD COLUMN {name} {definition}")
            try:
                db.executescript(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts
                    USING fts5(content, content_rowid='id', tokenize='unicode61');
                    CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
                        INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
                    END;
                    CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
                        DELETE FROM messages_fts WHERE rowid = old.id;
                    END;
                    CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
                        DELETE FROM messages_fts WHERE rowid = old.id;
                        INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
                    END;
                    CREATE VIRTUAL TABLE IF NOT EXISTS memory_items_fts
                    USING fts5(content, subject, content_rowid='rowid', tokenize='unicode61');
                    CREATE TRIGGER IF NOT EXISTS memory_items_ai AFTER INSERT ON memory_items BEGIN
                        INSERT INTO memory_items_fts(rowid, content, subject) VALUES (new.rowid, new.content, new.subject);
                    END;
                    CREATE TRIGGER IF NOT EXISTS memory_items_ad AFTER DELETE ON memory_items BEGIN
                        DELETE FROM memory_items_fts WHERE rowid = old.rowid;
                    END;
                    CREATE TRIGGER IF NOT EXISTS memory_items_au AFTER UPDATE ON memory_items BEGIN
                        DELETE FROM memory_items_fts WHERE rowid = old.rowid;
                        INSERT INTO memory_items_fts(rowid, content, subject) VALUES (new.rowid, new.content, new.subject);
                    END;
                    """
                )
                self._fts = True
            except sqlite3.Error:
                self._fts = False

    def create_session(self, title="", provider="", model="", cwd="", session_id=None) -> str:
        session_id = session_id or make_id("session")
        now = utc_now()
        with self.connection() as db:
            db.execute(
                "INSERT INTO sessions(id,title,provider,model,cwd,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (session_id, title, provider, model, cwd, now, now),
            )
        return session_id

    def touch_session(self, session_id: str, title: str | None = None, message_count: int | None = None) -> None:
        with self.connection() as db:
            if title is not None:
                db.execute("UPDATE sessions SET title=?, updated_at=? WHERE id=?", (title, utc_now(), session_id))
            elif message_count is not None:
                db.execute(
                    "UPDATE sessions SET message_count=?, updated_at=? WHERE id=?",
                    (message_count, utc_now(), session_id),
                )
            else:
                db.execute("UPDATE sessions SET updated_at=? WHERE id=?", (utc_now(), session_id))

    def append_message(self, session_id: str, role: str, content: str, metadata=None) -> int:
        metadata = metadata or {}
        now = utc_now()
        with self.connection() as db:
            cursor = db.execute(
                "INSERT INTO messages(session_id,role,content,metadata,created_at) VALUES(?,?,?,?,?)",
                (session_id, role, str(content or ""), _encode_message_metadata({"metadata": metadata}), now),
            )
            db.execute(
                "UPDATE sessions SET message_count=message_count+1, updated_at=? WHERE id=?",
                (now, session_id),
            )
            return int(cursor.lastrowid or 0)

    def append_messages(self, session_id: str, messages: list[dict]) -> None:
        with self.connection() as db:
            now = utc_now()
            for message in messages:
                db.execute(
                    "INSERT INTO messages(session_id,role,content,metadata,created_at) VALUES(?,?,?,?,?)",
                    (
                        session_id,
                        message.get("role", "user"),
                        str(message.get("content") or ""),
                        _encode_message_metadata(message),
                        now,
                    ),
                )
            db.execute(
                "UPDATE sessions SET message_count=message_count+?, updated_at=? WHERE id=?",
                (len(messages), now, session_id),
            )

    def get_messages(self, session_id: str, limit: int | None = None) -> list[dict]:
        query = "SELECT role,content,metadata,created_at FROM messages WHERE session_id=?"
        params = [session_id]
        if limit:
            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
        else:
            query += " ORDER BY id ASC"
        with self.connection() as db:
            rows = db.execute(query, params).fetchall()
        result = []
        for row in reversed(rows) if limit else rows:
            item = dict(row)
            metadata, fields = _decode_message_metadata(item.get("metadata") or "{}")
            item.update(fields)
            item["metadata"] = metadata
            result.append(item)
        return result

    def list_sessions(self, limit=20) -> list[dict]:
        with self.connection() as db:
            rows = db.execute("SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def get_session(self, session_id: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        return dict(row) if row else None

    def delete_session(self, session_id: str) -> bool:
        with self.connection() as db:
            cursor = db.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        return cursor.rowcount > 0

    def search_messages(self, query: str, limit=20, session_id=None) -> list[dict]:
        if not query.strip():
            return []
        with self.connection() as db:
            if self._fts:
                try:
                    rows = db.execute(
                        "SELECT session_id,role,content,created_at FROM messages_fts "
                        "JOIN messages ON messages.id=messages_fts.rowid "
                        "WHERE messages_fts MATCH ? ORDER BY messages.id DESC LIMIT ?",
                        (query, limit),
                    ).fetchall()
                except sqlite3.OperationalError:
                    rows = []
            else:
                rows = []
            if not rows:
                like = f"%{query}%"
                sql = "SELECT session_id,role,content,created_at FROM messages WHERE content LIKE ?"
                params = [like]
                if session_id:
                    sql += " AND session_id=?"
                    params.append(session_id)
                sql += " ORDER BY id DESC LIMIT ?"
                params.append(limit)
                rows = db.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def create_task(self, title="", session_id="", parent_id="", metadata=None, task_id=None) -> str:
        task_id = task_id or make_id("task")
        now = utc_now()
        with self.connection() as db:
            db.execute(
                "INSERT INTO tasks(id,session_id,parent_id,title,status,metadata,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (task_id, session_id, parent_id, title, "pending", json.dumps(metadata or {}, ensure_ascii=False), now, now),
            )
        return task_id

    def update_task(self, task_id: str, status: str, result="", metadata=None) -> None:
        with self.connection() as db:
            if metadata is None:
                db.execute(
                    "UPDATE tasks SET status=?,result=?,updated_at=? WHERE id=?",
                    (status, str(result or ""), utc_now(), task_id),
                )
            else:
                db.execute(
                    "UPDATE tasks SET status=?,result=?,metadata=?,updated_at=? WHERE id=?",
                    (status, str(result or ""), json.dumps(metadata, ensure_ascii=False), utc_now(), task_id),
                )

    def find_tasks_by_run_id(self, run_id: str) -> list[dict]:
        wanted = str(run_id)
        with self.connection() as db:
            rows = db.execute("SELECT * FROM tasks ORDER BY updated_at DESC").fetchall()
        result = []
        for row in rows:
            metadata = row["metadata"]
            try:
                parsed = json.loads(metadata or "{}")
            except (TypeError, ValueError):
                continue
            if isinstance(parsed, dict) and str(parsed.get("run_id") or "") == wanted:
                result.append(dict(row))
        return result

    def persist_orchestration(self, creates=None, updates=None, usages=None) -> None:
        now = utc_now()
        with self.connection() as db:
            for item in creates or []:
                db.execute(
                    "INSERT OR IGNORE INTO tasks(id,session_id,parent_id,title,status,metadata,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (
                        item["id"],
                        item.get("session_id", ""),
                        item.get("parent_id", ""),
                        item.get("title", ""),
                        item.get("status", "pending"),
                        json.dumps(item.get("metadata") or {}, ensure_ascii=False),
                        now,
                        now,
                    ),
                )
            for item in updates or []:
                db.execute(
                    "UPDATE tasks SET status=?,result=?,metadata=?,updated_at=? WHERE id=?",
                    (
                        item.get("status", "pending"),
                        str(item.get("result") or ""),
                        json.dumps(item.get("metadata") or {}, ensure_ascii=False),
                        now,
                        item["id"],
                    ),
                )
            for item in usages or []:
                db.execute(
                    "INSERT INTO usage(session_id,provider,model,prompt_tokens,completion_tokens,estimated_cost,"
                    "cost_known,priced_calls,unpriced_calls,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        item.get("session_id", ""),
                        item.get("provider", ""),
                        item.get("model", ""),
                        int(item.get("prompt_tokens", 0)),
                        int(item.get("completion_tokens", 0)),
                        float(item.get("estimated_cost", 0.0)),
                        int(bool(item.get("cost_known"))),
                        int(item.get("priced_calls", 0)),
                        int(item.get("unpriced_calls", 0)),
                        now,
                    ),
                )

    def list_tasks(self, limit=50, status=None) -> list[dict]:
        sql = "SELECT * FROM tasks"
        params = []
        if status:
            sql += " WHERE status=?"
            params.append(status)
        sql += " ORDER BY updated_at DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self.connection() as db:
            rows = db.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def get_task(self, task_id: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(row) if row else None

    def record_usage(
        self,
        session_id,
        provider,
        model,
        prompt_tokens=0,
        completion_tokens=0,
        estimated_cost=0.0,
        cost_known=False,
        priced_calls=0,
        unpriced_calls=0,
    ) -> None:
        with self.connection() as db:
            db.execute(
                "INSERT INTO usage(session_id,provider,model,prompt_tokens,completion_tokens,estimated_cost,"
                "cost_known,priced_calls,unpriced_calls,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    session_id,
                    provider,
                    model,
                    int(prompt_tokens),
                    int(completion_tokens),
                    float(estimated_cost),
                    int(bool(cost_known)),
                    int(priced_calls),
                    int(unpriced_calls),
                    utc_now(),
                ),
            )

    def session_usage(self, session_id: str) -> dict:
        with self.connection() as db:
            row = db.execute(
                "SELECT COALESCE(SUM(prompt_tokens),0) p, COALESCE(SUM(completion_tokens),0) c, "
                "COALESCE(SUM(estimated_cost),0) cost, COALESCE(SUM(cost_known),0) known_rows, "
                "COALESCE(SUM(priced_calls),0) priced_calls, COALESCE(SUM(unpriced_calls),0) unpriced_calls "
                "FROM usage WHERE session_id=?",
                (session_id,),
            ).fetchone()
        return {
            "prompt_tokens": row["p"],
            "completion_tokens": row["c"],
            "estimated_cost": row["cost"],
            "cost_known": bool(row["known_rows"] and not row["unpriced_calls"]),
            "priced_calls": row["priced_calls"],
            "unpriced_calls": row["unpriced_calls"],
        }

    def get_approval(self, rule_key: str) -> str | None:
        with self.connection() as db:
            row = db.execute("SELECT decision FROM approvals WHERE rule_key=?", (rule_key,)).fetchone()
        return row["decision"] if row else None

    def set_approval(self, rule_key: str, decision: str) -> None:
        with self.connection() as db:
            db.execute(
                "INSERT INTO approvals(rule_key,decision,created_at) VALUES(?,?,?) "
                "ON CONFLICT(rule_key) DO UPDATE SET decision=excluded.decision, created_at=excluded.created_at",
                (rule_key, decision, utc_now()),
            )

    @staticmethod
    def _execution_payload(value) -> dict:
        if hasattr(value, "to_dict"):
            return value.to_dict()
        if isinstance(value, dict):
            return dict(value)
        return {}

    @staticmethod
    def _decode_execution_row(row) -> dict | None:
        if not row:
            return None
        item = dict(row)
        try:
            item["plan"] = json.loads(item.get("plan_json") or "{}")
        except (TypeError, ValueError):
            item["plan"] = {}
        return item

    def save_execution_plan(self, plan) -> None:
        payload = self._execution_payload(plan)
        now = utc_now()
        with self.connection() as db:
            db.execute(
                "INSERT INTO execution_plans(id,session_id,objective,complexity,route,status,plan_json,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                "session_id=excluded.session_id, objective=excluded.objective, complexity=excluded.complexity, "
                "route=excluded.route, status=excluded.status, plan_json=excluded.plan_json, updated_at=excluded.updated_at",
                (
                    str(payload.get("id") or ""),
                    str(payload.get("session_id") or ""),
                    str(payload.get("objective") or ""),
                    str(payload.get("complexity") or ""),
                    str(payload.get("route") or ""),
                    str(payload.get("status") or ""),
                    json.dumps(payload, ensure_ascii=False),
                    str(payload.get("created_at") or now),
                    now,
                ),
            )

    def get_execution_plan(self, plan_id: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM execution_plans WHERE id=?", (plan_id,)).fetchone()
        return self._decode_execution_row(row)

    def list_execution_plans(self, session_id: str | None = None, status: str | None = None, limit: int | None = 20) -> list[dict]:
        sql = "SELECT * FROM execution_plans WHERE 1=1"
        params = []
        if session_id:
            sql += " AND session_id=?"
            params.append(session_id)
        if status:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY updated_at DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self.connection() as db:
            rows = db.execute(sql, params).fetchall()
        return [self._decode_execution_row(row) for row in rows]

    def save_execution_checkpoint(self, checkpoint) -> None:
        payload = self._execution_payload(checkpoint)
        with self.connection() as db:
            db.execute(
                "INSERT OR REPLACE INTO execution_checkpoints(id,plan_id,sequence,phase,note,payload,created_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    str(payload.get("id") or ""),
                    str(payload.get("plan_id") or ""),
                    int(payload.get("sequence") or 0),
                    str(payload.get("phase") or ""),
                    str(payload.get("note") or ""),
                    json.dumps(payload.get("payload") or {}, ensure_ascii=False),
                    str(payload.get("created_at") or utc_now()),
                ),
            )

    @staticmethod
    def _decode_checkpoint_row(row) -> dict | None:
        if not row:
            return None
        item = dict(row)
        try:
            item["payload"] = json.loads(item.get("payload") or "{}")
        except (TypeError, ValueError):
            item["payload"] = {}
        return item

    def list_execution_checkpoints(self, plan_id: str, limit: int | None = 50) -> list[dict]:
        sql = "SELECT * FROM execution_checkpoints WHERE plan_id=? ORDER BY sequence ASC, created_at ASC"
        params = [plan_id]
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self.connection() as db:
            rows = db.execute(sql, params).fetchall()
        return [self._decode_checkpoint_row(row) for row in rows]

    def get_latest_execution_checkpoint(self, plan_id: str) -> dict | None:
        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM execution_checkpoints WHERE plan_id=? ORDER BY sequence DESC, created_at DESC LIMIT 1",
                (plan_id,),
            ).fetchone()
        return self._decode_checkpoint_row(row)

    @staticmethod
    def _encode_memory_metadata(metadata) -> str:
        return json.dumps(metadata if isinstance(metadata, dict) else {}, ensure_ascii=False)

    @staticmethod
    def _decode_memory_row(row) -> dict | None:
        if not row:
            return None
        item = dict(row)
        try:
            metadata = json.loads(item.get("metadata") or "{}")
        except (TypeError, ValueError):
            metadata = {}
        item["metadata"] = metadata if isinstance(metadata, dict) else {}
        return item

    @staticmethod
    def _fts_query(query: str) -> str:
        tokens = re.findall(r"\w+", str(query or ""), re.UNICODE)[:12]
        return " OR ".join('"' + token.replace('"', '""') + '"' for token in tokens)

    def save_memory_item(self, item) -> None:
        now = utc_now()
        with self.connection() as db:
            db.execute(
                "INSERT INTO memory_items(id,session_id,layer,subject,content,provenance,confidence,status,"
                "metadata,supersedes,created_at,updated_at,expires_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET session_id=excluded.session_id, layer=excluded.layer, "
                "subject=excluded.subject, content=excluded.content, provenance=excluded.provenance, "
                "confidence=excluded.confidence, status=excluded.status, metadata=excluded.metadata, "
                "supersedes=excluded.supersedes, updated_at=excluded.updated_at, expires_at=excluded.expires_at",
                (
                    str(item.get("id") or ""),
                    str(item.get("session_id") or ""),
                    str(item.get("layer") or "semantic"),
                    str(item.get("subject") or ""),
                    str(item.get("content") or ""),
                    str(item.get("provenance") or ""),
                    float(item.get("confidence", 0.5)),
                    str(item.get("status") or "active"),
                    self._encode_memory_metadata(item.get("metadata")),
                    str(item.get("supersedes") or ""),
                    str(item.get("created_at") or now),
                    str(item.get("updated_at") or now),
                    str(item.get("expires_at") or ""),
                ),
            )

    def get_memory_item(self, item_id: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM memory_items WHERE id=?", (item_id,)).fetchone()
        return self._decode_memory_row(row)

    def list_memory_items(
        self,
        layer: str | None = None,
        session_id: str | None = None,
        status: str | None = "active",
        include_expired: bool = False,
        limit: int | None = None,
    ) -> list[dict]:
        sql = "SELECT * FROM memory_items WHERE 1=1"
        params = []
        if status:
            sql += " AND status=?"
            params.append(status)
        if layer:
            sql += " AND layer=?"
            params.append(layer)
        if session_id is not None:
            sql += " AND session_id=?"
            params.append(session_id)
        if not include_expired:
            sql += " AND (expires_at='' OR expires_at>?)"
            params.append(utc_now())
        sql += " ORDER BY updated_at DESC, created_at DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self.connection() as db:
            rows = db.execute(sql, params).fetchall()
        return [self._decode_memory_row(row) for row in rows]

    def delete_memory_item(self, item_id: str) -> bool:
        with self.connection() as db:
            cursor = db.execute("DELETE FROM memory_items WHERE id=?", (item_id,))
        return cursor.rowcount > 0

    def search_memory_items(
        self,
        query: str,
        layer: str | None = None,
        session_id: str | None = None,
        status: str | None = "active",
        limit: int = 50,
    ) -> list[dict]:
        text = str(query or "").strip()
        if not text:
            return []
        filters = ""
        params = []
        if status:
            filters += " AND memory_items.status=?"
            params.append(status)
        if layer:
            filters += " AND memory_items.layer=?"
            params.append(layer)
        if session_id is not None:
            filters += " AND memory_items.session_id=?"
            params.append(session_id)
        rows = []
        if self._fts:
            match = self._fts_query(text)
            if match:
                try:
                    with self.connection() as db:
                        rows = db.execute(
                            "SELECT memory_items.* FROM memory_items_fts "
                            "JOIN memory_items ON memory_items.rowid=memory_items_fts.rowid "
                            "WHERE memory_items_fts MATCH ?" + filters + " ORDER BY memory_items.updated_at DESC LIMIT ?",
                            [match, *params, limit],
                        ).fetchall()
                except sqlite3.OperationalError:
                    rows = []
        if not rows:
            like = f"%{text}%"
            sql = "SELECT * FROM memory_items WHERE (content LIKE ? OR subject LIKE ?)" + filters.replace(
                "memory_items.", ""
            )
            with self.connection() as db:
                rows = db.execute(sql, [like, like, *params, limit]).fetchall()
        return [self._decode_memory_row(row) for row in rows]

    @staticmethod
    def _encode_learning_json(value) -> str:
        payload = value if isinstance(value, (dict, list)) else []
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _decode_learning_json(raw, default):
        try:
            value = json.loads(raw or "")
        except (TypeError, ValueError):
            return default
        if isinstance(value, type(default)):
            return value
        return default

    def _decode_experience_row(self, row) -> dict | None:
        if not row:
            return None
        item = dict(row)
        for key, default in (
            ("classification", {}),
            ("plan", {}),
            ("agents", []),
            ("models", []),
            ("tools", []),
            ("errors", []),
            ("verification", {}),
            ("feedback", {}),
        ):
            item[key] = self._decode_learning_json(item.get(key), default)
        item["verified"] = bool(item.get("verified"))
        return item

    def save_experience(self, item) -> None:
        now = utc_now()
        with self.connection() as db:
            db.execute(
                "INSERT INTO learning_experiences(id,session_id,objective,classification,plan_id,plan,agents,models,"
                "tools,errors,solution,verification,feedback,outcome,status,provenance,confidence,verified,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET session_id=excluded.session_id, objective=excluded.objective, "
                "classification=excluded.classification, plan_id=excluded.plan_id, plan=excluded.plan, "
                "agents=excluded.agents, models=excluded.models, tools=excluded.tools, errors=excluded.errors, "
                "solution=excluded.solution, verification=excluded.verification, feedback=excluded.feedback, "
                "outcome=excluded.outcome, status=excluded.status, provenance=excluded.provenance, "
                "confidence=excluded.confidence, verified=excluded.verified",
                (
                    str(item.get("id") or ""),
                    str(item.get("session_id") or ""),
                    str(item.get("objective") or ""),
                    self._encode_learning_json(item.get("classification") or {}),
                    str(item.get("plan_id") or ""),
                    self._encode_learning_json(item.get("plan") or {}),
                    self._encode_learning_json(item.get("agents") or []),
                    self._encode_learning_json(item.get("models") or []),
                    self._encode_learning_json(item.get("tools") or []),
                    self._encode_learning_json(item.get("errors") or []),
                    str(item.get("solution") or ""),
                    self._encode_learning_json(item.get("verification") or {}),
                    self._encode_learning_json(item.get("feedback") or {}),
                    str(item.get("outcome") or ""),
                    str(item.get("status") or ""),
                    str(item.get("provenance") or "agent-turn"),
                    float(item.get("confidence", 0.5)),
                    int(bool(item.get("verified"))),
                    str(item.get("created_at") or now),
                ),
            )

    def get_experience(self, experience_id: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM learning_experiences WHERE id=?", (experience_id,)).fetchone()
        return self._decode_experience_row(row)

    def list_experiences(
        self,
        session_id: str | None = None,
        verified_only: bool = False,
        query: str = "",
        limit: int | None = 50,
    ) -> list[dict]:
        sql = "SELECT * FROM learning_experiences WHERE 1=1"
        params = []
        if session_id is not None:
            sql += " AND session_id=?"
            params.append(session_id)
        if verified_only:
            sql += " AND verified=1"
        if query:
            like = f"%{str(query)}%"
            sql += " AND (objective LIKE ? OR solution LIKE ? OR outcome LIKE ? OR plan_id LIKE ?)"
            params.extend([like, like, like, like])
        sql += " ORDER BY created_at DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self.connection() as db:
            rows = db.execute(sql, params).fetchall()
        return [self._decode_experience_row(row) for row in rows]

    def _decode_learning_proposal_row(self, row) -> dict | None:
        if not row:
            return None
        item = dict(row)
        item["meta"] = self._decode_learning_json(item.get("meta"), {})
        item["evidence"] = self._decode_learning_json(item.get("evidence"), [])
        item["validation"] = self._decode_learning_json(item.get("validation"), {})
        return item

    def save_learning_proposal(self, item) -> None:
        now = utc_now()
        with self.connection() as db:
            db.execute(
                "INSERT INTO learning_proposals(id,skill_name,kind,status,content,meta,evidence,validation,"
                "created_at,decided_at,decided_by) VALUES(?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET skill_name=excluded.skill_name, kind=excluded.kind, "
                "status=excluded.status, content=excluded.content, meta=excluded.meta, evidence=excluded.evidence, "
                "validation=excluded.validation, decided_at=excluded.decided_at, decided_by=excluded.decided_by",
                (
                    str(item.get("id") or ""),
                    str(item.get("skill_name") or ""),
                    str(item.get("kind") or "create"),
                    str(item.get("status") or "proposed"),
                    str(item.get("content") or ""),
                    self._encode_learning_json(item.get("meta") or {}),
                    self._encode_learning_json(item.get("evidence") or []),
                    self._encode_learning_json(item.get("validation") or {}),
                    str(item.get("created_at") or now),
                    str(item.get("decided_at") or ""),
                    str(item.get("decided_by") or ""),
                ),
            )

    def get_learning_proposal(self, proposal_id: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM learning_proposals WHERE id=?", (proposal_id,)).fetchone()
        return self._decode_learning_proposal_row(row)

    def list_learning_proposals(self, skill_name: str | None = None, status: str | None = None, limit: int | None = 50) -> list[dict]:
        sql = "SELECT * FROM learning_proposals WHERE 1=1"
        params = []
        if skill_name:
            sql += " AND skill_name=?"
            params.append(skill_name)
        if status:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY created_at DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self.connection() as db:
            rows = db.execute(sql, params).fetchall()
        return [self._decode_learning_proposal_row(row) for row in rows]

    def save_skill_version(self, item) -> None:
        now = utc_now()
        with self.connection() as db:
            db.execute(
                "INSERT INTO learning_versions(id,skill_name,version,content,status,proposal_id,score,created_at) "
                "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(skill_name,version) DO UPDATE SET content=excluded.content, "
                "status=excluded.status, proposal_id=excluded.proposal_id, score=excluded.score",
                (
                    str(item.get("id") or ""),
                    str(item.get("skill_name") or ""),
                    int(item.get("version") or 1),
                    str(item.get("content") or ""),
                    str(item.get("status") or "candidate"),
                    str(item.get("proposal_id") or ""),
                    float(item.get("score") or 0.0),
                    str(item.get("created_at") or now),
                ),
            )

    def get_skill_version(self, skill_name: str, version: int) -> dict | None:
        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM learning_versions WHERE skill_name=? AND version=?",
                (skill_name, int(version)),
            ).fetchone()
        return dict(row) if row else None

    def list_skill_versions(self, skill_name: str) -> list[dict]:
        with self.connection() as db:
            rows = db.execute(
                "SELECT * FROM learning_versions WHERE skill_name=? ORDER BY version DESC",
                (skill_name,),
            ).fetchall()
        return [dict(row) for row in rows]

    def latest_skill_version(self, skill_name: str) -> dict | None:
        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM learning_versions WHERE skill_name=? ORDER BY version DESC LIMIT 1",
                (skill_name,),
            ).fetchone()
        return dict(row) if row else None

    def set_skill_version_status(self, skill_name: str, version: int, status: str) -> None:
        with self.connection() as db:
            db.execute(
                "UPDATE learning_versions SET status=? WHERE skill_name=? AND version=?",
                (status, skill_name, int(version)),
            )

    def save_skill_metrics(self, item) -> None:
        now = utc_now()
        with self.connection() as db:
            db.execute(
                "INSERT INTO learning_metrics(skill_name,active_version,execution_count,success_count,"
                "verification_count,total_duration_ms,total_tokens,estimated_cost,last_success_at,last_modified_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(skill_name) DO UPDATE SET "
                "active_version=excluded.active_version, execution_count=excluded.execution_count, "
                "success_count=excluded.success_count, verification_count=excluded.verification_count, "
                "total_duration_ms=excluded.total_duration_ms, total_tokens=excluded.total_tokens, "
                "estimated_cost=excluded.estimated_cost, last_success_at=excluded.last_success_at, "
                "last_modified_at=excluded.last_modified_at",
                (
                    str(item.get("skill_name") or ""),
                    int(item.get("active_version") or 0),
                    int(item.get("execution_count") or 0),
                    int(item.get("success_count") or 0),
                    int(item.get("verification_count") or 0),
                    float(item.get("total_duration_ms") or 0.0),
                    int(item.get("total_tokens") or 0),
                    float(item.get("estimated_cost") or 0.0),
                    str(item.get("last_success_at") or ""),
                    str(item.get("last_modified_at") or now),
                ),
            )

    def get_skill_metrics(self, skill_name: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM learning_metrics WHERE skill_name=?", (skill_name,)).fetchone()
        return dict(row) if row else None

    def list_skill_metrics(self) -> list[dict]:
        with self.connection() as db:
            rows = db.execute("SELECT * FROM learning_metrics ORDER BY skill_name").fetchall()
        return [dict(row) for row in rows]

    def record_learning_event(self, item) -> None:
        with self.connection() as db:
            db.execute(
                "INSERT INTO learning_events(id,skill_name,event_type,payload,created_at) VALUES(?,?,?,?,?)",
                (
                    str(item.get("id") or ""),
                    str(item.get("skill_name") or ""),
                    str(item.get("event_type") or ""),
                    self._encode_learning_json(item.get("payload") or {}),
                    str(item.get("created_at") or utc_now()),
                ),
            )

    def list_learning_events(self, skill_name: str | None = None, event_type: str | None = None, limit: int | None = 50) -> list[dict]:
        sql = "SELECT * FROM learning_events WHERE 1=1"
        params = []
        if skill_name:
            sql += " AND skill_name=?"
            params.append(skill_name)
        if event_type:
            sql += " AND event_type=?"
            params.append(event_type)
        sql += " ORDER BY created_at DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self.connection() as db:
            rows = db.execute(sql, params).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = self._decode_learning_json(item.get("payload"), {})
            result.append(item)
        return result

    def save_model_performance(self, item: dict) -> None:
        with self.connection() as db:
            db.execute(
                "INSERT INTO model_performance(id,category,provider,model,success,verified,sources,tokens,estimated_cost,"
                "cost_known,duration_ms,recovery_attempts,experience_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    str(item.get("id") or make_id("model-perf")),
                    str(item.get("category") or ""),
                    str(item.get("provider") or ""),
                    str(item.get("model") or ""),
                    int(bool(item.get("success"))),
                    int(bool(item.get("verified"))),
                    self._encode_learning_json(item.get("sources") or []),
                    int(item.get("tokens") or 0),
                    float(item.get("cost") or 0.0),
                    int(bool(item.get("cost_known"))),
                    float(item.get("duration_ms") or 0.0),
                    int(item.get("recovery_attempts") or 0),
                    str(item.get("experience_id") or ""),
                    str(item.get("created_at") or utc_now()),
                ),
            )

    def list_model_performance(
        self,
        category: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        verified_only: bool = False,
        limit: int | None = 50,
    ) -> list[dict]:
        sql = "SELECT * FROM model_performance WHERE 1=1"
        params = []
        if category:
            sql += " AND category=?"
            params.append(category)
        if provider:
            sql += " AND provider=?"
            params.append(provider)
        if model:
            sql += " AND model=?"
            params.append(model)
        if verified_only:
            sql += " AND verified=1"
        sql += " ORDER BY created_at DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self.connection() as db:
            rows = db.execute(sql, params).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["sources"] = self._decode_learning_json(item.get("sources"), [])
            result.append(item)
        return result

    def reset_model_performance(self, category: str | None = None, provider: str | None = None, model: str | None = None) -> int:
        sql = "DELETE FROM model_performance WHERE 1=1"
        params = []
        if category:
            sql += " AND category=?"
            params.append(category)
        if provider:
            sql += " AND provider=?"
            params.append(provider)
        if model:
            sql += " AND model=?"
            params.append(model)
        with self.connection() as db:
            cursor = db.execute(sql, params)
        return int(cursor.rowcount or 0)

    def mark_model_performance_verified(self, experience_id: str, verdict: str) -> int:
        if not experience_id or str(verdict).lower() != "verified":
            return 0
        with self.connection() as db:
            rows = db.execute("SELECT id,sources FROM model_performance WHERE experience_id=?", (experience_id,)).fetchall()
            for row in rows:
                sources = self._decode_learning_json(row["sources"], [])
                if "user" not in sources:
                    sources.append("user")
                db.execute(
                    "UPDATE model_performance SET verified=1,sources=? WHERE id=?",
                    (self._encode_learning_json(sources), row["id"]),
                )
            return len(rows)

    def export_session(self, session_id: str) -> dict:
        session = self.get_session(session_id)
        if not session:
            return {}
        return {"session": session, "messages": self.get_messages(session_id)}

    def import_session(self, payload: dict) -> str:
        session = payload.get("session") or {}
        session_id = str(session.get("id") or make_id("session"))
        if not self.get_session(session_id):
            self.create_session(
                title=session.get("title", ""),
                provider=session.get("provider", ""),
                model=session.get("model", ""),
                cwd=session.get("cwd", ""),
                session_id=session_id,
            )
        self.append_messages(session_id, payload.get("messages") or [])
        return session_id
