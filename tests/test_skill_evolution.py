"""Tests for Skill Evolution Lifecycle."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


@pytest.fixture
def mock_policy_engine():
    """Mock policy engine."""
    engine = MagicMock()
    engine.check_permission = AsyncMock(return_value=True)
    engine.validate_evolution = AsyncMock(return_value={"allowed": True})
    return engine


@pytest.fixture
def mock_capability_manager():
    """Mock capability manager."""
    manager = MagicMock()
    manager.check = AsyncMock(return_value=True)
    manager.request_capability = AsyncMock(return_value=True)
    return manager


@pytest.fixture
def mock_checkpoint_manager():
    """Mock checkpoint manager."""
    manager = MagicMock()
    manager.create_checkpoint = MagicMock(return_value=MagicMock(id="cp_123"))
    manager.restore = MagicMock()
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
async def test_skill_marked_for_evolution_when_performance_low(
    mock_policy_engine, mock_capability_manager, mock_audit_logger
):
    """Test skill is marked for evolution when performance below threshold."""
    from synapse.skills.evolution.engine import SkillEvolutionEngine
    
    engine = SkillEvolutionEngine(
        policy_engine=mock_policy_engine,
        capability_manager=mock_capability_manager,
        audit_logger=mock_audit_logger
    )
    
    # Skill with low performance
    skill_metrics = {"success_rate": 0.5, "latency_ms": 500}
    
    result = engine.should_evolve(skill_metrics)
    assert result == True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_skill_not_marked_for_evolution_when_performance_good(
    mock_policy_engine, mock_capability_manager, mock_audit_logger
):
    """Test skill is NOT marked for evolution when performance is good."""
    from synapse.skills.evolution.engine import SkillEvolutionEngine
    
    engine = SkillEvolutionEngine(
        policy_engine=mock_policy_engine,
        capability_manager=mock_capability_manager,
        audit_logger=mock_audit_logger
    )
    
    # Skill with good performance
    skill_metrics = {"success_rate": 0.95, "latency_ms": 100}
    
    result = engine.should_evolve(skill_metrics)
    assert result == False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_evolution_pipeline_deterministic(
    mock_policy_engine, mock_capability_manager, mock_audit_logger
):
    """Test evolution pipeline produces deterministic results."""
    from synapse.skills.evolution.engine import SkillEvolutionEngine
    
    engine = SkillEvolutionEngine(
        policy_engine=mock_policy_engine,
        capability_manager=mock_capability_manager,
        audit_logger=mock_audit_logger
    )
    
    skill_spec = {"name": "test_skill", "version": "1.0"}
    
    # Run twice with same input
    result1 = engine.plan_evolution(skill_spec, seed=42)
    result2 = engine.plan_evolution(skill_spec, seed=42)
    
    assert result1 == result2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_evolution_requires_capability_check(
    mock_policy_engine, mock_capability_manager, mock_audit_logger
):
    """Test evolution requires capability check."""
    from synapse.skills.evolution.engine import SkillEvolutionEngine
    
    engine = SkillEvolutionEngine(
        policy_engine=mock_policy_engine,
        capability_manager=mock_capability_manager,
        audit_logger=mock_audit_logger
    )
    
    await engine.evolve_skill({"name": "test_skill"})
    
    mock_capability_manager.check.assert_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_evolution_audit_logged(
    mock_policy_engine, mock_capability_manager, mock_audit_logger
):
    """Test evolution is audit logged."""
    from synapse.skills.evolution.engine import SkillEvolutionEngine
    
    engine = SkillEvolutionEngine(
        policy_engine=mock_policy_engine,
        capability_manager=mock_capability_manager,
        audit_logger=mock_audit_logger
    )
    
    await engine.evolve_skill({"name": "test_skill"})
    
    mock_audit_logger.record.assert_called()


@pytest.mark.unit
def test_protocol_version_present(mock_policy_engine, mock_capability_manager, mock_audit_logger):
    """Test protocol_version is present in evolution engine."""
    from synapse.skills.evolution.engine import SkillEvolutionEngine
    
    engine = SkillEvolutionEngine(
        policy_engine=mock_policy_engine,
        capability_manager=mock_capability_manager,
        audit_logger=mock_audit_logger
    )
    
    assert engine.protocol_version == "1.0"
