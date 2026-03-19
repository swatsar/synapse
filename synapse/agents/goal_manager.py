"""Goal Management System.

Protocol Version: 1.0
Specification: 3.1

Adapted from AutoGPT hierarchical goal patterns (AUTOGPT_INTEGRATION.md §2).
Synapse additions: capability validation, checkpoint integration,
audit logging, protocol versioning.
"""
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from synapse.observability.logger import audit

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger(__name__)


class GoalPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class GoalStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Goal:
    """A single agent goal with hierarchy support.

    Adapted from AutoGPT Goal model (AUTOGPT_INTEGRATION.md §2.1).
    Adds: required_capabilities, protocol_version.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    priority: GoalPriority = GoalPriority.MEDIUM
    status: GoalStatus = GoalStatus.PENDING
    parent_goal_id: Optional[str] = None
    sub_goals: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    result: Optional[str] = None
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "priority": self.priority.value,
            "status": self.status.value,
            "parent_goal_id": self.parent_goal_id,
            "sub_goals": self.sub_goals,
            "required_capabilities": self.required_capabilities,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "protocol_version": self.protocol_version,
        }


class GoalManager:
    """Hierarchical goal management for autonomous agents.

    Adapted from AutoGPT goal management (AUTOGPT_INTEGRATION.md §2.1).
    Adds: capability validation, checkpoint on state change, audit logging.
    """

    PROTOCOL_VERSION: str = PROTOCOL_VERSION

    def __init__(
        self,
        memory_store: Any = None,
        security_manager: Any = None,
        checkpoint_manager: Any = None,
    ):
        self.memory = memory_store
        self.security = security_manager
        self.checkpoint = checkpoint_manager
        self._goals: Dict[str, Goal] = {}
        self._active_goal_id: Optional[str] = None
        audit(event="goal_manager_initialized", protocol_version=PROTOCOL_VERSION)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create_goal(
        self,
        description: str,
        priority: GoalPriority = GoalPriority.MEDIUM,
        required_capabilities: Optional[List[str]] = None,
        parent_goal_id: Optional[str] = None,
    ) -> Goal:
        """Create a new goal with optional capability validation."""
        caps = required_capabilities or []

        # Validate capabilities
        if caps and self.security:
            try:
                valid = await self.security.validate_capabilities(caps)
                if not valid:
                    audit(event="goal_create_denied", caps=caps, protocol_version=PROTOCOL_VERSION)
                    raise PermissionError(f"Missing capabilities: {caps}")
            except Exception as e:
                if "validate_capabilities" in str(type(e).__name__):
                    pass  # Security manager doesn't have this method yet
                else:
                    raise

        goal = Goal(
            description=description,
            priority=priority,
            required_capabilities=caps,
            parent_goal_id=parent_goal_id,
        )
        self._goals[goal.id] = goal

        # Attach to parent
        if parent_goal_id and parent_goal_id in self._goals:
            self._goals[parent_goal_id].sub_goals.append(goal.id)

        # Checkpoint
        await self._checkpoint(f"goal_created:{goal.id}")

        audit(
            event="goal_created",
            goal_id=goal.id,
            priority=priority.value,
            has_parent=bool(parent_goal_id),
            protocol_version=PROTOCOL_VERSION,
        )
        return goal

    async def update_status(self, goal_id: str, status: GoalStatus, result: str = "") -> Goal:
        """Update goal status with audit trail."""
        if goal_id not in self._goals:
            raise KeyError(f"Goal not found: {goal_id}")
        goal = self._goals[goal_id]
        old_status = goal.status
        goal.status = status
        goal.updated_at = datetime.now(timezone.utc).isoformat()
        if status == GoalStatus.COMPLETED:
            goal.completed_at = goal.updated_at
            goal.result = result
            # Update active goal pointer
            if self._active_goal_id == goal_id:
                self._active_goal_id = None

        await self._checkpoint(f"goal_status:{goal_id}:{status.value}")
        audit(
            event="goal_status_updated",
            goal_id=goal_id,
            old_status=old_status.value,
            new_status=status.value,
            protocol_version=PROTOCOL_VERSION,
        )
        return goal

    async def set_active_goal(self, goal_id: str) -> None:
        """Set a goal as currently active."""
        if goal_id not in self._goals:
            raise KeyError(f"Goal not found: {goal_id}")
        self._active_goal_id = goal_id
        await self.update_status(goal_id, GoalStatus.IN_PROGRESS)

    async def decompose_goal(self, goal_id: str, sub_descriptions: List[str]) -> List[Goal]:
        """Decompose a goal into sub-goals."""
        if goal_id not in self._goals:
            raise KeyError(f"Goal not found: {goal_id}")
        parent = self._goals[goal_id]
        sub_goals = []
        for desc in sub_descriptions:
            sg = await self.create_goal(
                description=desc,
                priority=parent.priority,
                parent_goal_id=goal_id,
                required_capabilities=parent.required_capabilities,
            )
            sub_goals.append(sg)
        audit(event="goal_decomposed", goal_id=goal_id, sub_count=len(sub_goals), protocol_version=PROTOCOL_VERSION)
        return sub_goals

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_active_goal(self) -> Optional[Goal]:
        if self._active_goal_id:
            return self._goals.get(self._active_goal_id)
        # Return highest-priority pending goal
        pending = [g for g in self._goals.values() if g.status == GoalStatus.PENDING]
        if not pending:
            return None
        priority_order = {GoalPriority.CRITICAL: 0, GoalPriority.HIGH: 1, GoalPriority.MEDIUM: 2, GoalPriority.LOW: 3}
        return min(pending, key=lambda g: priority_order.get(g.priority, 99))

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        return self._goals.get(goal_id)

    def list_goals(self, status: Optional[GoalStatus] = None) -> List[Goal]:
        goals = list(self._goals.values())
        if status:
            goals = [g for g in goals if g.status == status]
        return sorted(goals, key=lambda g: g.created_at)

    def get_goal_tree(self) -> List[Dict[str, Any]]:
        """Return goal hierarchy as a tree."""
        roots = [g for g in self._goals.values() if not g.parent_goal_id]
        return [self._build_tree(g) for g in roots]

    def _build_tree(self, goal: Goal) -> Dict[str, Any]:
        node = goal.to_dict()
        node["children"] = [self._build_tree(self._goals[sid]) for sid in goal.sub_goals if sid in self._goals]
        return node

    def get_stats(self) -> Dict[str, Any]:
        statuses = {s.value: 0 for s in GoalStatus}
        for g in self._goals.values():
            statuses[g.status.value] = statuses.get(g.status.value, 0) + 1
        return {"total": len(self._goals), "by_status": statuses, "protocol_version": PROTOCOL_VERSION}

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    async def _checkpoint(self, label: str) -> None:
        if self.checkpoint:
            try:
                self.checkpoint.create_checkpoint(
                    state={"goals": {gid: g.to_dict() for gid, g in self._goals.items()}, "label": label},
                    agent_id="goal_manager",
                )
            except Exception as e:
                logger.debug("Checkpoint failed in GoalManager: %s", e)
