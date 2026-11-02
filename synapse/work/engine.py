"""Durable WorkEngine: one state owner, atomic task leases, budgets and approvals."""
from __future__ import annotations
import asyncio, uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
import aiosqlite
from synapse.work.models import Approval, ApprovalDecision, Budget, CostRecord, Lease, Project, Run, Task, WorkStatus
PROTOCOL_VERSION="1.0"
class WorkEngine:
    """SQLite-backed control-plane work ledger; scheduler remains elsewhere."""
    def __init__(self, db_path: str|Path=':memory:'):
        self.db_path=str(db_path); self._db=None; self._lock=asyncio.Lock()
    async def _conn(self):
        async with self._lock:
            if self._db is None:
                self._db=await aiosqlite.connect(self.db_path); self._db.row_factory=aiosqlite.Row
                await self._db.executescript('''CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, project_id TEXT, title TEXT, description TEXT, status TEXT, priority INTEGER, exclusive INTEGER, budget_id TEXT, version INTEGER, lease_owner TEXT, lease_token TEXT, lease_expires TEXT, created_at TEXT); CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, task_id TEXT, status TEXT, revision INTEGER, created_at TEXT); CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY, task_id TEXT, action TEXT, decision TEXT, scope TEXT, decided_by TEXT); CREATE TABLE IF NOT EXISTS budgets(id TEXT PRIMARY KEY, scope_id TEXT, limit_usd REAL, spent_usd REAL, version INTEGER); CREATE TABLE IF NOT EXISTS costs(id TEXT PRIMARY KEY, run_id TEXT, provider_id TEXT, model_id TEXT, input_tokens INTEGER, output_tokens INTEGER, cost_usd REAL, recorded_at TEXT);'''); await self._db.commit()
            return self._db
    async def close(self):
        if self._db: await self._db.close(); self._db=None
    async def create_task(self, task:Task)->Task:
        db=await self._conn(); await db.execute('INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(task.id,task.project_id,task.title,task.description,task.status.value,task.priority,int(task.exclusive),task.budget_id,task.version,None,None,None,task.created_at)); await db.commit(); return task
    async def create_run(self, run:Run)->Run:
        db=await self._conn(); await db.execute('INSERT INTO runs VALUES(?,?,?,?,?)',(run.id,run.task_id,run.status.value,run.revision,run.created_at)); await db.commit(); return run
    async def checkout(self, task_id:str, owner_id:str, lease_seconds:int=60)->Lease|None:
        db=await self._conn(); token=str(uuid.uuid4()); expiry=(datetime.now(UTC)+timedelta(seconds=lease_seconds)).isoformat()
        await db.execute('BEGIN IMMEDIATE'); cur=await db.execute('UPDATE tasks SET status=?,lease_owner=?,lease_token=?,lease_expires=?,version=version+1 WHERE id=? AND status IN (?,?) AND (lease_expires IS NULL OR lease_expires < ?)',(WorkStatus.LEASED.value,owner_id,token,expiry,task_id,WorkStatus.QUEUED.value,WorkStatus.LEASED.value,datetime.now(UTC).isoformat()));
        if cur.rowcount != 1: await db.rollback(); return None
        await db.commit(); row=await (await db.execute('SELECT version FROM tasks WHERE id=?',(task_id,))).fetchone(); return Lease(task_id,owner_id,token,expiry,row['version'])
    async def heartbeat(self, lease:Lease, lease_seconds:int=60)->bool:
        db=await self._conn(); expiry=(datetime.now(UTC)+timedelta(seconds=lease_seconds)).isoformat(); cur=await db.execute('UPDATE tasks SET lease_expires=?,version=version+1 WHERE id=? AND lease_owner=? AND lease_token=? AND lease_expires >= ?',(expiry,lease.task_id,lease.owner_id,lease.token,datetime.now(UTC).isoformat())); await db.commit(); return cur.rowcount==1
    async def release(self, lease:Lease, status:WorkStatus=WorkStatus.QUEUED)->bool:
        db=await self._conn(); cur=await db.execute('UPDATE tasks SET status=?,lease_owner=NULL,lease_token=NULL,lease_expires=NULL,version=version+1 WHERE id=? AND lease_owner=? AND lease_token=?',(status.value,lease.task_id,lease.owner_id,lease.token)); await db.commit(); return cur.rowcount==1
    async def create_approval(self, approval:Approval)->Approval:
        db=await self._conn(); await db.execute('INSERT INTO approvals VALUES(?,?,?,?,?,?)',(approval.id,approval.task_id,approval.action,approval.decision.value,approval.scope,approval.decided_by)); await db.commit(); return approval
    async def decide_approval(self, approval_id:str, decision:ApprovalDecision, decided_by:str)->bool:
        db=await self._conn(); cur=await db.execute('UPDATE approvals SET decision=?,decided_by=? WHERE id=? AND decision=?',(decision.value,decided_by,approval_id,ApprovalDecision.PENDING.value)); await db.commit(); return cur.rowcount==1
    async def create_budget(self,budget:Budget)->Budget:
        db=await self._conn(); await db.execute('INSERT INTO budgets VALUES(?,?,?,?,?)',(budget.id,budget.scope_id,budget.limit_usd,budget.spent_usd,budget.version)); await db.commit(); return budget
    async def record_cost(self,cost:CostRecord)->bool:
        db=await self._conn(); await db.execute('INSERT INTO costs VALUES(?,?,?,?,?,?,?,?)',(cost.id,cost.run_id,cost.provider_id,cost.model_id,cost.input_tokens,cost.output_tokens,cost.cost_usd,cost.recorded_at)); await db.commit(); return True
