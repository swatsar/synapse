"""SQLite-backed durable task/run control plane.

The engine owns lifecycle transitions, leases, approvals, budgets, and costs.
Every state-changing operation uses an atomic compare-and-set so a stale worker
cannot overwrite a newer owner or terminal outcome.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import aiosqlite

from synapse.work.models import (
    ALLOWED_TRANSITIONS,
    Approval,
    ApprovalDecision,
    Budget,
    CostRecord,
    InvalidTransition,
    Lease,
    Project,
    Run,
    Task,
    TERMINAL_STATUSES,
    WorkStatus,
    can_transition,
)

PROTOCOL_VERSION = "1.0"


class WorkEngine:
    """Durable local work ledger with explicit task/run state transitions."""

    def __init__(self, db_path: str | Path = ":memory:"):
        self.db_path = str(db_path)
        self._db: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def _conn(self) -> aiosqlite.Connection:
        if self._db is None:
            self._db = await aiosqlite.connect(self.db_path)
            self._db.row_factory = aiosqlite.Row
            await self._db.execute("PRAGMA foreign_keys=ON")
            await self._db.execute("PRAGMA busy_timeout=15000")
            await self._db.execute("PRAGMA journal_mode=WAL")
            await self._db.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks(
                    id TEXT PRIMARY KEY, project_id TEXT, title TEXT NOT NULL,
                    description TEXT NOT NULL, status TEXT NOT NULL,
                    priority INTEGER NOT NULL, exclusive INTEGER NOT NULL,
                    budget_id TEXT, version INTEGER NOT NULL, lease_owner TEXT,
                    lease_token TEXT, lease_expires TEXT, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs(
                    id TEXT PRIMARY KEY, task_id TEXT NOT NULL, status TEXT NOT NULL,
                    revision INTEGER NOT NULL, created_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(id)
                );
                CREATE TABLE IF NOT EXISTS work_events(
                    id INTEGER PRIMARY KEY AUTOINCREMENT, entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL, from_status TEXT, to_status TEXT NOT NULL,
                    reason TEXT, version INTEGER NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS approvals(
                    id TEXT PRIMARY KEY, task_id TEXT NOT NULL, action TEXT NOT NULL,
                    decision TEXT NOT NULL, scope TEXT NOT NULL, decided_by TEXT
                );
                CREATE TABLE IF NOT EXISTS budgets(
                    id TEXT PRIMARY KEY, scope_id TEXT NOT NULL, limit_usd REAL NOT NULL,
                    spent_usd REAL NOT NULL, version INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS costs(
                    id TEXT PRIMARY KEY, run_id TEXT NOT NULL, provider_id TEXT NOT NULL,
                    model_id TEXT NOT NULL, input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL, cost_usd REAL NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                """
            )
            await self._db.commit()
        return self._db

    async def close(self) -> None:
        async with self._lock:
            if self._db is not None:
                await self._db.close()
                self._db = None

    @staticmethod
    def _status(value: str | WorkStatus) -> WorkStatus:
        return value if isinstance(value, WorkStatus) else WorkStatus(value)

    async def create_task(self, task: Task) -> Task:
        async with self._lock:
            db = await self._conn()
            await db.execute(
                "INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (task.id, task.project_id, task.title, task.description, task.status.value,
                 task.priority, int(task.exclusive), task.budget_id, task.version,
                 None, None, None, task.created_at),
            )
            await db.commit()
        return task

    async def create_run(self, run: Run) -> Run:
        async with self._lock:
            db = await self._conn()
            await db.execute(
                "INSERT INTO runs VALUES(?,?,?,?,?)",
                (run.id, run.task_id, run.status.value, run.revision, run.created_at),
            )
            await db.commit()
        return run

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        async with self._lock:
            db = await self._conn()
            row = await (await db.execute("SELECT * FROM tasks WHERE id=?", (task_id,))).fetchone()
        return dict(row) if row else None

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        async with self._lock:
            db = await self._conn()
            row = await (await db.execute("SELECT * FROM runs WHERE id=?", (run_id,))).fetchone()
        return dict(row) if row else None

    async def transition_task(
        self,
        task_id: str,
        target: WorkStatus,
        *,
        expected_version: int | None = None,
        reason: str | None = None,
    ) -> dict[str, Any] | None:
        """Atomically transition a task, optionally requiring its current version."""
        target = self._status(target)
        async with self._lock:
            db = await self._conn()
            row = await (await db.execute(
                "SELECT status, version FROM tasks WHERE id=?", (task_id,)
            )).fetchone()
            if row is None:
                return None
            current = WorkStatus(row["status"])
            if not can_transition(current, target):
                raise InvalidTransition(f"task {task_id}: {current.value} -> {target.value}")
            predicates = "id=? AND status=?"
            args: list[Any] = [task_id, current.value]
            if expected_version is not None:
                predicates += " AND version=?"
                args.append(expected_version)
            cur = await db.execute(
                f"UPDATE tasks SET status=?, version=version+1 WHERE {predicates}",  # noqa: S608
                [target.value, *args],
            )
            if cur.rowcount != 1:
                await db.rollback()
                raise RuntimeError("stale task version; transition was not applied")
            new_version = int(row["version"]) + 1
            await db.execute(
                "INSERT INTO work_events(entity_type,entity_id,from_status,to_status,reason,version,created_at) VALUES(?,?,?,?,?,?,?)",
                ("task", task_id, current.value, target.value, reason, new_version, datetime.now(UTC).isoformat()),
            )
            await db.commit()
            result = await (await db.execute("SELECT * FROM tasks WHERE id=?", (task_id,))).fetchone()
        return dict(result)

    async def transition_run(
        self,
        run_id: str,
        target: WorkStatus,
        *,
        expected_revision: int | None = None,
        reason: str | None = None,
    ) -> dict[str, Any] | None:
        """Atomically transition a run with optimistic revision checking."""
        target = self._status(target)
        async with self._lock:
            db = await self._conn()
            row = await (await db.execute(
                "SELECT status, revision FROM runs WHERE id=?", (run_id,)
            )).fetchone()
            if row is None:
                return None
            current = WorkStatus(row["status"])
            if not can_transition(current, target):
                raise InvalidTransition(f"run {run_id}: {current.value} -> {target.value}")
            predicates = "id=? AND status=?"
            args: list[Any] = [run_id, current.value]
            if expected_revision is not None:
                predicates += " AND revision=?"
                args.append(expected_revision)
            cur = await db.execute(
                f"UPDATE runs SET status=?, revision=revision+1 WHERE {predicates}",  # noqa: S608
                [target.value, *args],
            )
            if cur.rowcount != 1:
                await db.rollback()
                raise RuntimeError("stale run revision; transition was not applied")
            revision = int(row["revision"]) + 1
            await db.execute(
                "INSERT INTO work_events(entity_type,entity_id,from_status,to_status,reason,version,created_at) VALUES(?,?,?,?,?,?,?)",
                ("run", run_id, current.value, target.value, reason, revision, datetime.now(UTC).isoformat()),
            )
            await db.commit()
            result = await (await db.execute("SELECT * FROM runs WHERE id=?", (run_id,))).fetchone()
        return dict(result)

    async def checkout(self, task_id: str, owner_id: str, lease_seconds: int = 60) -> Lease | None:
        """Claim a queued or expired lease without overwriting active ownership."""
        if lease_seconds < 0:
            lease_seconds = 0
        token = str(uuid.uuid4())
        now = datetime.now(UTC)
        expiry = (now + timedelta(seconds=lease_seconds)).isoformat()
        async with self._lock:
            db = await self._conn()
            row = await (await db.execute(
                "SELECT status, version, lease_expires FROM tasks WHERE id=?", (task_id,)
            )).fetchone()
            if row is None:
                return None
            status = WorkStatus(row["status"])
            old_expiry = row["lease_expires"]
            expired = old_expiry is None or old_expiry <= now.isoformat()
            if status not in {WorkStatus.QUEUED, WorkStatus.LEASED} or not expired:
                return None
            cur = await db.execute(
                "UPDATE tasks SET status=?, lease_owner=?, lease_token=?, lease_expires=?, version=version+1 "
                "WHERE id=? AND version=? AND (lease_expires IS NULL OR lease_expires <= ?)",
                (WorkStatus.LEASED.value, owner_id, token, expiry, task_id, row["version"], now.isoformat()),
            )
            if cur.rowcount != 1:
                await db.rollback()
                return None
            version = int(row["version"]) + 1
            await db.execute(
                "INSERT INTO work_events(entity_type,entity_id,from_status,to_status,reason,version,created_at) VALUES(?,?,?,?,?,?,?)",
                ("task", task_id, status.value, WorkStatus.LEASED.value, f"lease:{owner_id}", version, now.isoformat()),
            )
            await db.commit()
        return Lease(task_id, owner_id, token, expiry, version)

    async def heartbeat(self, lease: Lease, lease_seconds: int = 60) -> bool:
        if lease_seconds < 0:
            lease_seconds = 0
        expiry = (datetime.now(UTC) + timedelta(seconds=lease_seconds)).isoformat()
        async with self._lock:
            db = await self._conn()
            cur = await db.execute(
                "UPDATE tasks SET lease_expires=?,version=version+1 WHERE id=? AND status=? AND lease_owner=? AND lease_token=? AND lease_expires >= ?",
                (expiry, lease.task_id, WorkStatus.LEASED.value, lease.owner_id, lease.token, datetime.now(UTC).isoformat()),
            )
            await db.commit()
            return cur.rowcount == 1

    async def release(self, lease: Lease, status: WorkStatus = WorkStatus.QUEUED) -> bool:
        """Release a lease only when its owner/token still match."""
        status = self._status(status)
        async with self._lock:
            db = await self._conn()
            row = await (await db.execute(
                "SELECT status, version FROM tasks WHERE id=? AND lease_owner=? AND lease_token=?",
                (lease.task_id, lease.owner_id, lease.token),
            )).fetchone()
            if row is None:
                return False
            current = WorkStatus(row["status"])
            if not can_transition(current, status):
                raise InvalidTransition(f"task {lease.task_id}: {current.value} -> {status.value}")
            cur = await db.execute(
                "UPDATE tasks SET status=?, lease_owner=NULL, lease_token=NULL, lease_expires=NULL, version=version+1 "
                "WHERE id=? AND status=? AND lease_owner=? AND lease_token=? AND version=?",
                (status.value, lease.task_id, current.value, lease.owner_id, lease.token, row["version"]),
            )
            if cur.rowcount != 1:
                await db.rollback()
                return False
            await db.commit()
            return True

    async def recover_expired_leases(self) -> int:
        """Return expired leases to queued without touching active workers."""
        now = datetime.now(UTC).isoformat()
        async with self._lock:
            db = await self._conn()
            cur = await db.execute(
                "UPDATE tasks SET status=?, lease_owner=NULL, lease_token=NULL, lease_expires=NULL, version=version+1 "
                "WHERE status=? AND lease_expires IS NOT NULL AND lease_expires < ?",
                (WorkStatus.QUEUED.value, WorkStatus.LEASED.value, now),
            )
            await db.commit()
            return cur.rowcount

    async def create_approval(self, approval: Approval) -> Approval:
        async with self._lock:
            db = await self._conn()
            await db.execute(
                "INSERT INTO approvals VALUES(?,?,?,?,?,?)",
                (approval.id, approval.task_id, approval.action, approval.decision.value,
                 approval.scope, approval.decided_by),
            )
            await db.commit()
        return approval

    async def decide_approval(self, approval_id: str, decision: ApprovalDecision, decided_by: str) -> bool:
        async with self._lock:
            db = await self._conn()
            cur = await db.execute(
                "UPDATE approvals SET decision=?,decided_by=? WHERE id=? AND decision=?",
                (decision.value, decided_by, approval_id, ApprovalDecision.PENDING.value),
            )
            await db.commit()
            return cur.rowcount == 1

    async def create_budget(self, budget: Budget) -> Budget:
        async with self._lock:
            db = await self._conn()
            await db.execute(
                "INSERT INTO budgets VALUES(?,?,?,?,?)",
                (budget.id, budget.scope_id, budget.limit_usd, budget.spent_usd, budget.version),
            )
            await db.commit()
        return budget

    async def record_cost(self, cost: CostRecord) -> bool:
        async with self._lock:
            db = await self._conn()
            await db.execute(
                "INSERT INTO costs VALUES(?,?,?,?,?,?,?,?)",
                (cost.id, cost.run_id, cost.provider_id, cost.model_id, cost.input_tokens,
                 cost.output_tokens, cost.cost_usd, cost.recorded_at),
            )
            await db.commit()
            return True

    async def list_events(self, entity_id: str) -> list[dict[str, Any]]:
        async with self._lock:
            db = await self._conn()
            rows = await (await db.execute(
                "SELECT * FROM work_events WHERE entity_id=? ORDER BY id", (entity_id,)
            )).fetchall()
        return [dict(row) for row in rows]


__all__ = ["WorkEngine", "PROTOCOL_VERSION"]
