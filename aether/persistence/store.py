import json
import sqlite3
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
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
    rule_key TEXT PRIMARY KEY,
    decision TEXT NOT NULL,
    created_at TEXT NOT NULL
);
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
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fts = False
        self.init()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path), timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def init(self) -> None:
        with self.connect() as db:
            db.executescript(SCHEMA)
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
                    """
                )
                self._fts = True
            except sqlite3.Error:
                self._fts = False

    def create_session(self, title="", provider="", model="", cwd="", session_id=None) -> str:
        session_id = session_id or make_id("session")
        now = utc_now()
        with self.connect() as db:
            db.execute(
                "INSERT INTO sessions(id,title,provider,model,cwd,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (session_id, title, provider, model, cwd, now, now),
            )
        return session_id

    def touch_session(self, session_id: str, title: str | None = None, message_count: int | None = None) -> None:
        with self.connect() as db:
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
        with self.connect() as db:
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
        with self.connect() as db:
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
        with self.connect() as db:
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
        with self.connect() as db:
            rows = db.execute("SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def get_session(self, session_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        return dict(row) if row else None

    def delete_session(self, session_id: str) -> bool:
        with self.connect() as db:
            cursor = db.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        return cursor.rowcount > 0

    def search_messages(self, query: str, limit=20, session_id=None) -> list[dict]:
        if not query.strip():
            return []
        with self.connect() as db:
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

    def create_task(self, title="", session_id="", parent_id="", metadata=None) -> str:
        task_id = make_id("task")
        now = utc_now()
        with self.connect() as db:
            db.execute(
                "INSERT INTO tasks(id,session_id,parent_id,title,status,metadata,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (task_id, session_id, parent_id, title, "pending", json.dumps(metadata or {}, ensure_ascii=False), now, now),
            )
        return task_id

    def update_task(self, task_id: str, status: str, result="", metadata=None) -> None:
        with self.connect() as db:
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

    def list_tasks(self, limit=50, status=None) -> list[dict]:
        sql = "SELECT * FROM tasks"
        params = []
        if status:
            sql += " WHERE status=?"
            params.append(status)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as db:
            rows = db.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def get_task(self, task_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(row) if row else None

    def record_usage(self, session_id, provider, model, prompt_tokens=0, completion_tokens=0, estimated_cost=0.0) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT INTO usage(session_id,provider,model,prompt_tokens,completion_tokens,estimated_cost,created_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (session_id, provider, model, int(prompt_tokens), int(completion_tokens), float(estimated_cost), utc_now()),
            )

    def session_usage(self, session_id: str) -> dict:
        with self.connect() as db:
            row = db.execute(
                "SELECT COALESCE(SUM(prompt_tokens),0) p, COALESCE(SUM(completion_tokens),0) c, "
                "COALESCE(SUM(estimated_cost),0) cost FROM usage WHERE session_id=?",
                (session_id,),
            ).fetchone()
        return {"prompt_tokens": row["p"], "completion_tokens": row["c"], "estimated_cost": row["cost"]}

    def get_approval(self, rule_key: str) -> str | None:
        with self.connect() as db:
            row = db.execute("SELECT decision FROM approvals WHERE rule_key=?", (rule_key,)).fetchone()
        return row["decision"] if row else None

    def set_approval(self, rule_key: str, decision: str) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT INTO approvals(rule_key,decision,created_at) VALUES(?,?,?) "
                "ON CONFLICT(rule_key) DO UPDATE SET decision=excluded.decision, created_at=excluded.created_at",
                (rule_key, decision, utc_now()),
            )

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
