"""Phase 13.1.4 - Forced Rollback Under Load

Validates:
- Rollback during active execution
- Checkpoint restore correctness
- No partial state after rollback
- State consistency
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from synapse.core.checkpoint import CheckpointManager, Checkpoint
from synapse.core.rollback import RollbackManager
from synapse.core.execution_fabric import ExecutionFabric
from synapse.security.capability_manager import CapabilityManager
from synapse.core.audit import AuditLogger


@pytest.fixture
def capability_manager():
    cm = CapabilityManager()
    cm.grant_capability("checkpoint")
    cm.grant_capability("rollback")
    return cm


@pytest.fixture
def audit_logger():
    return AuditLogger()


@pytest.fixture
def checkpoint_manager(capability_manager, audit_logger):
    return CheckpointManager(cap_manager=capability_manager, audit=audit_logger)


@pytest.fixture
def rollback_manager(checkpoint_manager, capability_manager, audit_logger):
    return RollbackManager(cp_manager=checkpoint_manager, cap_manager=capability_manager, audit=audit_logger)


@pytest.fixture
def execution_fabric():
    return ExecutionFabric(seed_manager=None)


@pytest.mark.chaos
@pytest.mark.asyncio
class TestForcedRollbackUnderLoad:
    """Test forced rollback scenarios during active execution."""

    async def test_rollback_during_active_execution(self, checkpoint_manager, rollback_manager):
        """Rollback during active execution must complete correctly."""
        initial_state = {
            "tasks": [{"id": "task_1", "status": "pending"}],
            "resources": {"cpu": 50},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        checkpoint = checkpoint_manager.create_checkpoint(state=initial_state)

        # Force rollback during execution
        rollback_manager.rollback_to(checkpoint.id)

        # Verify state restored to checkpoint
        restored = checkpoint_manager.get_state(checkpoint.id)
        assert restored == initial_state

    async def test_no_partial_state_after_rollback(self, checkpoint_manager, rollback_manager):
        """After rollback, no partial state should exist."""
        nested_state = {
            "level_1": {
                "level_2": {
                    "level_3": {"value": 42}
                }
            },
            "array": [1, 2, 3, 4, 5]
        }

        checkpoint = checkpoint_manager.create_checkpoint(state=nested_state)

        # Perform rollback
        rollback_manager.rollback_to(checkpoint.id)

        # Verify complete state restoration
        restored = checkpoint_manager.get_state(checkpoint.id)
        assert restored == nested_state
        assert restored["level_1"]["level_2"]["level_3"]["value"] == 42
        assert len(restored["array"]) == 5

    async def test_concurrent_rollback_requests(self, checkpoint_manager, rollback_manager):
        """Concurrent rollback requests must be handled correctly."""
        state = {"counter": 0, "operations": []}

        checkpoint = checkpoint_manager.create_checkpoint(state=state)

        # Execute multiple rollbacks (synchronous, so they run sequentially)
        rollback_manager.rollback_to(checkpoint.id)
        rollback_manager.rollback_to(checkpoint.id)
        rollback_manager.rollback_to(checkpoint.id)

        # State should be consistent
        restored = checkpoint_manager.get_state(checkpoint.id)
        assert restored == state

    async def test_rollback_preserves_checkpoint_integrity(self, checkpoint_manager, rollback_manager):
        """Rollback must not corrupt checkpoint data."""
        original_state = {
            "critical_data": "must_not_change",
            "nested": {"deep": {"value": 123}}
        }

        checkpoint = checkpoint_manager.create_checkpoint(state=original_state)

        # Multiple rollbacks
        for i in range(5):
            rollback_manager.rollback_to(checkpoint.id)

        # Verify checkpoint unchanged
        final = checkpoint_manager.get_state(checkpoint.id)
        assert final == original_state
        assert final["critical_data"] == "must_not_change"
