"""Durable control-plane records and explicit task/run lifecycle contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
import uuid

PROTOCOL_VERSION = "1.0"


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class WorkStatus(str, Enum):
    QUEUED = "queued"
    LEASED = "leased"
    RUNNING = "running"
    WAITING = "waiting"
    WAITING_APPROVAL = "waiting_for_approval"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    REJECTED = "rejected"
    CANCELLING = "cancelling"


TERMINAL_STATUSES = frozenset({
    WorkStatus.COMPLETED,
    WorkStatus.FAILED,
    WorkStatus.CANCELLED,
    WorkStatus.TIMED_OUT,
    WorkStatus.REJECTED,
})

# State transitions are intentionally explicit. Any missing edge is rejected.
ALLOWED_TRANSITIONS: dict[WorkStatus, frozenset[WorkStatus]] = {
    WorkStatus.QUEUED: frozenset({WorkStatus.LEASED, WorkStatus.REJECTED, WorkStatus.CANCELLED}),
    WorkStatus.LEASED: frozenset({WorkStatus.RUNNING, WorkStatus.QUEUED, WorkStatus.CANCELLED, WorkStatus.TIMED_OUT}),
    WorkStatus.RUNNING: frozenset({WorkStatus.WAITING, WorkStatus.WAITING_APPROVAL, WorkStatus.COMPLETED, WorkStatus.FAILED, WorkStatus.CANCELLING, WorkStatus.TIMED_OUT}),
    WorkStatus.WAITING: frozenset({WorkStatus.RUNNING, WorkStatus.CANCELLED, WorkStatus.TIMED_OUT}),
    WorkStatus.WAITING_APPROVAL: frozenset({WorkStatus.RUNNING, WorkStatus.REJECTED, WorkStatus.CANCELLED}),
    WorkStatus.PAUSED: frozenset({WorkStatus.QUEUED, WorkStatus.CANCELLED}),
    WorkStatus.CANCELLING: frozenset({WorkStatus.CANCELLED, WorkStatus.FAILED, WorkStatus.TIMED_OUT}),
    WorkStatus.COMPLETED: frozenset(),
    WorkStatus.FAILED: frozenset(),
    WorkStatus.CANCELLED: frozenset(),
    WorkStatus.TIMED_OUT: frozenset(),
    WorkStatus.REJECTED: frozenset(),
}


def can_transition(current: WorkStatus, target: WorkStatus) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())


class InvalidTransition(ValueError):
    """Raised when a task/run lifecycle edge is not explicitly allowed."""


class ApprovalDecision(str, Enum):
    PENDING = "pending"
    ALLOW_ONCE = "allow_once"
    ALLOW_RUN = "allow_run"
    ALLOW_TASK = "allow_task"
    ALLOW_WORKSPACE = "allow_workspace"
    DENY = "deny"


@dataclass(frozen=True)
class Goal:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    tenant_id: str | None = None
    status: str = "active"
    created_at: str = field(default_factory=now_iso)


@dataclass(frozen=True)
class Project:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    goal_id: str | None = None
    name: str = ""
    workspace_id: str | None = None
    status: str = "active"


@dataclass(frozen=True)
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str | None = None
    title: str = ""
    description: str = ""
    status: WorkStatus = WorkStatus.QUEUED
    priority: int = 0
    exclusive: bool = True
    budget_id: str | None = None
    version: int = 0
    created_at: str = field(default_factory=now_iso)


@dataclass(frozen=True)
class Run:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    status: WorkStatus = WorkStatus.QUEUED
    revision: int = 0
    created_at: str = field(default_factory=now_iso)


@dataclass(frozen=True)
class Lease:
    task_id: str
    owner_id: str
    token: str
    expires_at: str
    version: int


@dataclass(frozen=True)
class Approval:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    action: str = ""
    decision: ApprovalDecision = ApprovalDecision.PENDING
    scope: str = "run"
    decided_by: str | None = None


@dataclass(frozen=True)
class Budget:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    scope_id: str = ""
    limit_usd: float = 0.0
    spent_usd: float = 0.0
    version: int = 0


@dataclass(frozen=True)
class CostRecord:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = ""
    provider_id: str = ""
    model_id: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    recorded_at: str = field(default_factory=now_iso)
