"""Tests for Rollback Safety for Evolved Skills."""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_checkpoint_manager():
    """Mock checkpoint manager."""
    manager = MagicMock()
    manager.create_checkpoint = MagicMock(return_value=MagicMock(id="cp_123"))
    manager.restore = MagicMock(return_value={"success": True})
    return manager


@pytest.fixture
def mock_rollback_manager():
    """Mock rollback manager."""
    manager = MagicMock()
    manager.execute_rollback = AsyncMock(return_value={"success": True})
    return manager


@pytest.fixture
def mock_audit_logger():
    """Mock audit logger."""
    logger = MagicMock()
    logger.record = MagicMock()
    return logger


@pytest.mark.unit
@pytest.mark.asyncio
async def test_failed_evolution_triggers_rollback(mock_checkpoint_manager, mock_rollback_manager, mock_audit_logger):
    """Test failed skill evolution triggers rollback."""
    from synapse.skills.evolution.engine import SkillEvolutionEngine
    
    engine = SkillEvolutionEngine(
        checkpoint_manager=mock_checkpoint_manager,
        rollback_manager=mock_rollback_manager,
        audit_logger=mock_audit_logger
    )
    
    # Simulate failed evolution
    result = await engine.handle_evolution_failure(
        skill_name="test_skill",
        error="Execution failed",
        checkpoint_id="cp_123"
    )
    
    mock_rollback_manager.execute_rollback.assert_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cluster_state_restored_deterministically(mock_checkpoint_manager, mock_rollback_manager, mock_audit_logger):
    """Test cluster state is restored deterministically after rollback."""
    from synapse.skills.evolution.engine import SkillEvolutionEngine
    
    engine = SkillEvolutionEngine(
        checkpoint_manager=mock_checkpoint_manager,
        rollback_manager=mock_rollback_manager,
        audit_logger=mock_audit_logger
    )
    
    # Restore cluster state
    result = await engine.restore_cluster_state("cp_123")
    
    assert result["success"] == True
    mock_checkpoint_manager.restore.assert_called_with("cp_123")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_capability_checks_passed_after_rollback(mock_checkpoint_manager, mock_rollback_manager, mock_audit_logger):
    """Test capability checks pass after rollback."""
    from synapse.skills.evolution.engine import SkillEvolutionEngine
    
    mock_capability_manager = MagicMock()
    mock_capability_manager.check = AsyncMock(return_value=True)
    
    engine = SkillEvolutionEngine(
        checkpoint_manager=mock_checkpoint_manager,
        rollback_manager=mock_rollback_manager,
        audit_logger=mock_audit_logger,
        capability_manager=mock_capability_manager
    )
    
    await engine.restore_cluster_state("cp_123")
    
    # Verify capabilities are checked after restore
    result = await engine.verify_capabilities(["fs:read", "fs:write"])
    assert result == True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rollback_audit_logged(mock_checkpoint_manager, mock_rollback_manager, mock_audit_logger):
    """Test rollback operations are audit logged."""
    from synapse.skills.evolution.engine import SkillEvolutionEngine
    
    engine = SkillEvolutionEngine(
        checkpoint_manager=mock_checkpoint_manager,
        rollback_manager=mock_rollback_manager,
        audit_logger=mock_audit_logger
    )
    
    await engine.handle_evolution_failure("test_skill", "error", "cp_123")
    
    mock_audit_logger.record.assert_called()


@pytest.mark.unit
def test_protocol_version_in_rollback(mock_checkpoint_manager, mock_rollback_manager, mock_audit_logger):
    """Test protocol_version in rollback operations."""
    from synapse.skills.evolution.engine import SkillEvolutionEngine
    
    engine = SkillEvolutionEngine(
        checkpoint_manager=mock_checkpoint_manager,
        rollback_manager=mock_rollback_manager,
        audit_logger=mock_audit_logger
    )
    
    assert engine.protocol_version == "1.0"
