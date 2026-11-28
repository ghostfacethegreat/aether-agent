from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from aether.errors import ToolError
from aether.utils import utc_now

_SCHEMA_VERSION = 1
_SCHEMA = """
CREATE TABLE IF NOT EXISTS repo_index_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS repo_index_roots (
    root TEXT PRIMARY KEY,
    signature TEXT NOT NULL,
    files INTEGER NOT NULL DEFAULT 0,
    bytes INTEGER NOT NULL DEFAULT 0,
    symbols INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS repo_index_files (
    root TEXT NOT NULL,
    path TEXT NOT NULL,
    size INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    ctime_ns INTEGER NOT NULL DEFAULT 0,
    content_hash TEXT NOT NULL,
    lines INTEGER NOT NULL DEFAULT 0,
    extension TEXT NOT NULL DEFAULT '',
    PRIMARY KEY(root, path),
    FOREIGN KEY(root) REFERENCES repo_index_roots(root) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS repo_index_symbols (
    root TEXT NOT NULL,
    path TEXT NOT NULL,
    name TEXT NOT NULL,
    name_fold TEXT NOT NULL,
    kind TEXT NOT NULL,
    line INTEGER NOT NULL,
    PRIMARY KEY(root, path, name, line),
    FOREIGN KEY(root, path) REFERENCES repo_index_files(root, path) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_repo_index_files_root ON repo_index_files(root);
CREATE INDEX IF NOT EXISTS idx_repo_index_symbols_name ON repo_index_symbols(root, name_fold);
CREATE INDEX IF NOT EXISTS idx_repo_index_symbols_path ON repo_index_symbols(root, path);
"""


def safe_relative(value):
    text = str(value or "")
    if not text or text.startswith("/") or "\\" in text or "\x00" in text:
        return None
    parts = text.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None
    return text


def _escape_like(value):
    return str(value).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class PersistentRepositoryIndex:
    def __init__(self, home):
        self.path = Path(home).expanduser() / "repo_index.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db:
            with db:
                db.executescript(_SCHEMA)
                columns = {row["name"] for row in db.execute("PRAGMA table_info(repo_index_files)")}
                if "ctime_ns" not in columns:
                    db.execute(
                        "ALTER TABLE repo_index_files ADD COLUMN ctime_ns INTEGER NOT NULL DEFAULT 0"
                    )
                db.execute(
                    "INSERT OR REPLACE INTO repo_index_meta(key, value) VALUES('schema_version', ?)",
                    (str(_SCHEMA_VERSION),),
                )
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def snapshot(self, root, signature):
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT signature FROM repo_index_roots WHERE root=?", (root,)
            ).fetchone()
            if not row or row["signature"] != signature:
                return {}, None
            files = {
                item["path"]: dict(item)
                for item in db.execute(
                    "SELECT path, size, mtime_ns, ctime_ns, content_hash, lines, extension "
                    "FROM repo_index_files WHERE root=?", (root,)
                )
            }
            return files, set()

    def sync(self, root, signature, records, changed, max_symbols, cancel_event=None):
        def cancelled():
            return cancel_event is not None and bool(getattr(cancel_event, "is_set", lambda: False)())

        if cancelled():
            raise ToolError("repo_index cancelled")
        now = utc_now()
        records = [record for record in records if safe_relative(record["path"]) is not None]
        current_paths = {record["path"] for record in records}
        existing, symbols_written, symbols_truncated = [], 0, False
        with closing(self.connect()) as db:
            with db:
                db.execute(
                    "INSERT INTO repo_index_roots(root, signature, files, bytes, symbols, updated_at) "
                    "VALUES(?,?,?,?,0,?) ON CONFLICT(root) DO UPDATE SET "
                    "signature=excluded.signature, files=excluded.files, bytes=excluded.bytes, updated_at=excluded.updated_at",
                    (root, signature, len(records), sum(item["size"] for item in records), now),
                )
                existing = [
                    row["path"] for row in db.execute(
                        "SELECT path FROM repo_index_files WHERE root=?", (root,)
                    )
                ]
                for path in existing:
                    if path not in current_paths:
                        db.execute(
                            "DELETE FROM repo_index_files WHERE root=? AND path=?", (root, path)
                        )
                for record in records:
                    if cancelled():
                        raise ToolError("repo_index cancelled")
                    db.execute(
                        "INSERT INTO repo_index_files(root, path, size, mtime_ns, ctime_ns, content_hash, lines, extension) "
                        "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(root, path) DO UPDATE SET "
                        "size=excluded.size, mtime_ns=excluded.mtime_ns, ctime_ns=excluded.ctime_ns, "
                        "content_hash=excluded.content_hash, lines=excluded.lines, extension=excluded.extension",
                        (
                            root, record["path"], record["size"], record["mtime_ns"],
                            record.get("ctime_ns", 0), record["content_hash"], record["lines"],
                            record["extension"],
                        ),
                    )
                for path in changed:
                    db.execute(
                        "DELETE FROM repo_index_symbols WHERE root=? AND path=?", (root, path)
                    )
                retained = db.execute(
                    "SELECT COUNT(*) AS count FROM repo_index_symbols WHERE root=?", (root,)
                ).fetchone()["count"]
                budget = max(0, max_symbols - retained)
                for record in records:
                    if record["path"] not in changed:
                        continue
                    for symbol in record["symbols"]:
                        if cancelled():
                            raise ToolError("repo_index cancelled")
                        if symbols_written >= budget:
                            symbols_truncated = True
                            break
                        name = str(symbol["name"])
                        db.execute(
                            "INSERT OR REPLACE INTO repo_index_symbols(root, path, name, name_fold, kind, line) "
                            "VALUES(?,?,?,?,?,?)",
                            (root, record["path"], name, name.casefold(), str(symbol["kind"]), int(symbol["line"])),
                        )
                        symbols_written += 1
                    if symbols_truncated:
                        break
                if cancelled():
                    raise ToolError("repo_index cancelled")
                total_symbols = db.execute(
                    "SELECT COUNT(*) AS count FROM repo_index_symbols WHERE root=?", (root,)
                ).fetchone()["count"]
                db.execute(
                    "UPDATE repo_index_roots SET files=?, bytes=?, symbols=?, updated_at=? WHERE root=?",
                    (len(records), sum(item["size"] for item in records), total_symbols, now, root),
                )
        return {
            "files_refreshed": len([path for path in changed if path in current_paths]),
            "files_removed": len([path for path in existing if path not in current_paths]),
            "symbols_written": symbols_written,
            "symbols_retained": retained,
            "symbols_truncated": symbols_truncated,
        }

    def query_symbols(self, root, query, limit):
        needle = _escape_like(query.casefold())
        scan_limit = min(max(limit * 4, 200), 20000)
        with closing(self.connect()) as db:
            rows = db.execute(
                "SELECT name, kind, path, line FROM repo_index_symbols "
                "WHERE root=? AND name_fold LIKE ? ESCAPE '\\' "
                "ORDER BY path, line, name LIMIT ?",
                (root, f"%{needle}%", scan_limit),
            ).fetchall()
        results, skipped, truncated = [], 0, len(rows) >= scan_limit
        for row in rows:
            relative = safe_relative(row["path"])
            if relative is None:
                skipped += 1
                continue
            candidate = Path(root) / relative
            try:
                if candidate.is_symlink() or not candidate.is_file():
                    skipped += 1
                    continue
            except OSError:
                skipped += 1
                continue
            if len(results) >= limit:
                truncated = True
                break
            results.append({
                "name": row["name"],
                "kind": row["kind"],
                "path": relative,
                "line": row["line"],
            })
        if skipped and len(results) >= limit:
            truncated = True
        return results, truncated
