"""Fixed tests for checkpoint manager."""
import pytest
from unittest.mock import MagicMock

PROTOCOL_VERSION: str = "1.0"

# Test synapse/core/checkpoint.py - FIXED
def test_checkpoint_manager_create():
    """Test checkpoint manager create_checkpoint."""
    from synapse.core.checkpoint import CheckpointManager
    manager = CheckpointManager()
    # Correct signature: create_checkpoint(state, agent_id, session_id)
    checkpoint = manager.create_checkpoint(
        state={"test": "data"},
        agent_id="test_agent",
        session_id="test_session"
    )
    assert checkpoint is not None
    assert checkpoint.checkpoint_id is not None
    assert checkpoint.agent_id == "test_agent"
    assert checkpoint.session_id == "test_session"

def test_checkpoint_manager_get():
    """Test checkpoint manager get_checkpoint."""
    from synapse.core.checkpoint import CheckpointManager
    manager = CheckpointManager()
    # Create checkpoint first
    checkpoint = manager.create_checkpoint(
        state={"test": "data"},
        agent_id="test_agent",
        session_id="test_session"
    )
    # Get the checkpoint
    retrieved = manager.get_checkpoint(checkpoint.checkpoint_id)
    assert retrieved is not None
    assert retrieved.checkpoint_id == checkpoint.checkpoint_id

def test_checkpoint_manager_restore():
    """Test checkpoint manager restore."""
    from synapse.core.checkpoint import CheckpointManager
    manager = CheckpointManager()
    # Create checkpoint first
    checkpoint = manager.create_checkpoint(
        state={"test": "data", "nested": {"key": "value"}},
        agent_id="test_agent",
        session_id="test_session"
    )
    # Restore the state
    state = manager.restore(checkpoint.checkpoint_id)
    assert state is not None
    assert state["test"] == "data"
    assert state["nested"]["key"] == "value"

def test_checkpoint_manager_restore_nonexistent():
    """Test checkpoint manager restore with nonexistent ID."""
    from synapse.core.checkpoint import CheckpointManager
    manager = CheckpointManager()
    # Try to restore nonexistent checkpoint
    state = manager.restore("nonexistent-id")
    assert state is None

def test_checkpoint_manager_with_audit():
    """Test checkpoint manager with audit logger."""
    from synapse.core.checkpoint import CheckpointManager
    mock_audit = MagicMock()
    mock_audit.record = MagicMock()
    
    manager = CheckpointManager(audit=mock_audit)
    checkpoint = manager.create_checkpoint(
        state={"test": "data"},
        agent_id="test_agent",
        session_id="test_session"
    )
    
    # Verify audit was called
    assert mock_audit.record.called
