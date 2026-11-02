"""Durable local storage for conversations, task outcomes and progress events.

The UI store is deliberately separate from the agent's semantic memory. It uses
only the Python standard library and one short-lived SQLite connection per
operation, so requests and uvicorn worker threads never share a connection.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "1.0"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class WorkspaceStore:
    def __init__(self, path: str | Path):
        self.path = str(Path(path).expanduser().resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    archived INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                    parent_task_id TEXT, approval_id TEXT,
                    task TEXT NOT NULL, payload_json TEXT NOT NULL,
                    status TEXT NOT NULL, success INTEGER, error TEXT,
                    result_json TEXT, created_at TEXT NOT NULL,
                    started_at TEXT, completed_at TEXT, duration_ms INTEGER,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );
                CREATE INDEX IF NOT EXISTS tasks_session ON tasks(session_id, created_at);
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                    role TEXT NOT NULL, content TEXT NOT NULL, task_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );
                CREATE TABLE IF NOT EXISTS task_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
                    task_id TEXT NOT NULL, event TEXT NOT NULL, data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS events_session ON task_events(session_id, id);
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY, task_id TEXT, action TEXT NOT NULL,
                    risk_level INTEGER NOT NULL, details_json TEXT NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL,
                    decided_at TEXT, execution_task_id TEXT
                );
            """)
            db.execute(
                "UPDATE tasks SET status='failed', success=0, error=?, completed_at=? "
                "WHERE status IN ('queued', 'running')",
                ("Execution interrupted by application restart", utc_now()),
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @staticmethod
    def _task(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["payload"] = json.loads(item.pop("payload_json"))
        result = item.pop("result_json")
        item["result"] = json.loads(result) if result else None
        item["success"] = None if item["success"] is None else bool(item["success"])
        return item

    @staticmethod
    def _approval(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["details"] = json.loads(item.pop("details_json"))
        return item

    def create_session(self, title: str = "Новая задача") -> dict[str, Any]:
        now, session_id = utc_now(), new_id("session")
        with self._connect() as db:
            db.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, 0)",
                (session_id, title, now, now),
            )
        return self.get_session(session_id)

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
            if row is None or row["archived"]:
                return None
            result = dict(row)
            result["task_count"] = db.execute(
                "SELECT COUNT(*) FROM tasks WHERE session_id=?", (session_id,),
            ).fetchone()[0]
            return result

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("""
                SELECT s.*, COUNT(t.id) AS task_count,
                    (SELECT status FROM tasks WHERE session_id=s.id ORDER BY created_at DESC LIMIT 1)
                    AS last_status
                FROM sessions s LEFT JOIN tasks t ON t.session_id=s.id
                WHERE s.archived=0 GROUP BY s.id ORDER BY s.updated_at DESC
            """).fetchall()
            return [dict(row) for row in rows]

    def update_session(self, session_id: str, title: str) -> dict[str, Any] | None:
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE sessions SET title=?, updated_at=? WHERE id=? AND archived=0",
                (title, utc_now(), session_id),
            )
            if not cursor.rowcount:
                return None
        return self.get_session(session_id)

    def archive_session(self, session_id: str) -> bool:
        with self._connect() as db:
            return bool(db.execute(
                "UPDATE sessions SET archived=1, updated_at=? WHERE id=?", (utc_now(), session_id),
            ).rowcount)

    def create_task(
        self, session_id: str, task: str, payload: dict[str, Any], *,
        task_id: str | None = None, parent_task_id: str | None = None,
        approval_id: str | None = None,
    ) -> dict[str, Any]:
        task_id, now = task_id or new_id("task"), utc_now()
        with self._connect() as db:
            db.execute("""
                INSERT INTO tasks(id, session_id, parent_task_id, approval_id, task,
                    payload_json, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'queued', ?)
            """, (task_id, session_id, parent_task_id, approval_id, task,
                  json.dumps(payload, ensure_ascii=False), now))
            db.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            return self._task(row) if row else None

    def list_all_tasks(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM tasks ORDER BY created_at").fetchall()
            return [self._task(row) for row in rows]

    def list_tasks(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM tasks WHERE session_id=? ORDER BY created_at", (session_id,),
            ).fetchall()
            return [self._task(row) for row in rows]

    def update_task(self, task_id: str, **fields: Any) -> dict[str, Any]:
        allowed = {"status", "success", "error", "started_at", "completed_at", "duration_ms", "approval_id"}
        values = []
        for key, value in fields.items():
            if key == "result":
                key, value = "result_json", json.dumps(value, ensure_ascii=False)
            elif key not in allowed:
                raise ValueError(f"Unsupported task field: {key}")
            else:
                value = int(value) if key == "success" and value is not None else value
            values.extend((key, value))
        assignments = ", ".join(f"{values[i]}=?" for i in range(0, len(values), 2))
        parameters = [values[i] for i in range(1, len(values), 2)]
        with self._connect() as db:
            db.execute(f"UPDATE tasks SET {assignments} WHERE id=?", (*parameters, task_id))
        return self.get_task(task_id)

    def add_message(self, session_id: str, role: str, content: str, task_id: str | None = None) -> dict:
        message_id, now = new_id("message"), utc_now()
        with self._connect() as db:
            db.execute(
                "INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?)",
                (message_id, session_id, role, content, task_id, now),
            )
            db.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))
        return {"id": message_id, "session_id": session_id, "role": role,
                "content": content, "task_id": task_id, "created_at": now}

    def list_messages(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM messages WHERE session_id=? ORDER BY created_at", (session_id,)).fetchall()
            return [dict(row) for row in rows]

    def add_event(self, session_id: str, task_id: str, event: str, data: dict[str, Any]) -> int:
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO task_events(session_id, task_id, event, data_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, task_id, event, json.dumps(data, ensure_ascii=False), utc_now()),
            )
            return int(cursor.lastrowid)

    def list_events(self, session_id: str, after: int = 0) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM task_events WHERE session_id=? AND id>? ORDER BY id LIMIT 300",
                (session_id, after),
            ).fetchall()
            return [{"id": row["id"], "task_id": row["task_id"], "event": row["event"],
                     "data": json.loads(row["data_json"]), "created_at": row["created_at"]} for row in rows]

    def create_approval(self, task: dict[str, Any], risk_level: int) -> dict[str, Any]:
        approval_id, now = new_id("approval"), utc_now()
        with self._connect() as db:
            db.execute("""
                INSERT INTO approvals(id, task_id, action, risk_level, details_json, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'pending', ?)
            """, (approval_id, task["id"], task["task"], risk_level,
                  json.dumps(task["payload"], ensure_ascii=False), now))
            db.execute("UPDATE tasks SET approval_id=? WHERE id=?", (approval_id, task["id"]))
        return self.get_approval(approval_id)

    def get_approval(self, approval_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
            return self._approval(row) if row else None

    def list_approvals(self, session_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT a.* FROM approvals a"
        parameters: tuple = ()
        if session_id:
            query += " JOIN tasks t ON t.id=a.task_id WHERE t.session_id=?"
            parameters = (session_id,)
        query += " ORDER BY a.created_at DESC"
        with self._connect() as db:
            return [self._approval(row) for row in db.execute(query, parameters).fetchall()]

    def decide_approval(self, approval_id: str, status: str, execution_task_id: str | None = None) -> bool:
        with self._connect() as db:
            return bool(db.execute(
                "UPDATE approvals SET status=?, decided_at=?, execution_task_id=? WHERE id=? AND status='pending'",
                (status, utc_now(), execution_task_id, approval_id),
            ).rowcount)

    def link_approval_execution(self, approval_id: str, execution_task_id: str) -> bool:
        """Record the actual retry after the one-time approval has been claimed."""
        with self._connect() as db:
            return bool(db.execute(
                "UPDATE approvals SET execution_task_id=? WHERE id=? AND status='approved' "
                "AND execution_task_id IS NULL",
                (execution_task_id, approval_id),
            ).rowcount)

    def close(self) -> None:
        """Connections are operation-scoped; retained for lifecycle symmetry."""


def default_workspace_store() -> WorkspaceStore:
    configured = os.getenv("SYNAPSE_UI_DB_PATH")
    if configured:
        path = Path(configured)
    else:
        db_path = os.getenv("SYNAPSE_DB_PATH")
        path = Path(db_path).with_name("workspace.sqlite3") if db_path else Path.home() / ".synapse" / "workspace.sqlite3"
    return WorkspaceStore(path)
