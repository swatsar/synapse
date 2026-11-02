"""Tests for production rollback safety.

Phase 10 - Production Autonomy & Self-Optimization.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from synapse.skills.autonomy.engine import (
    AutonomousOptimizationEngine,
    OptimizationPlan
)


pytestmark = pytest.mark.unit


@pytest.fixture
def rollback_manager():
    """Create mock rollback manager."""
    manager = MagicMock()
    manager.create_checkpoint = AsyncMock(return_value="cp-test-123")
    manager.execute_rollback = AsyncMock(return_value=MagicMock(success=True))
    return manager


@pytest.fixture
def production_engine(rollback_manager):
    """Create production autonomy engine with rollback."""
    mock_telemetry = MagicMock()
    mock_telemetry.get_skill_metrics = MagicMock(return_value={
        "success_rate": 0.65,
        "avg_latency_ms": 350
    })
    
    mock_resource = MagicMock()
    mock_resource.check_limits = MagicMock(return_value=True)
    mock_resource.get_available = MagicMock(return_value={"cpu": 80, "memory": 2048})
    
    mock_registry = MagicMock()
    mock_registry.get_skill = MagicMock(return_value=MagicMock(
        name="production_skill",
        risk_level=2,
        success_rate=0.65
    ))
    mock_registry.register = AsyncMock(side_effect=Exception("Registration failed"))
    
    return AutonomousOptimizationEngine(
        telemetry=mock_telemetry,
        resource_manager=mock_resource,
        skill_registry=mock_registry,
        rollback_manager=rollback_manager
    )


@pytest.mark.asyncio
async def test_failed_optimization_triggers_rollback(production_engine):
    """Failed optimization triggers automatic rollback."""
    plan = OptimizationPlan(
        skill_name="production_skill",
        optimization_type="performance",
        risk_level=2,
        seed=42
    )
    
    result = await production_engine.optimize(plan)
    
    assert result.success is False
    assert result.rollback_executed is True


@pytest.mark.asyncio
async def test_rollback_restores_previous_state(production_engine, rollback_manager):
    """Rollback restores previous skill state."""
    # Create checkpoint before optimization
    checkpoint_id = await rollback_manager.create_checkpoint(
        agent_id="production",
        session_id="test_session"
    )
    
    plan = OptimizationPlan(
        skill_name="production_skill",
        optimization_type="performance",
        risk_level=2,
        seed=42,
        checkpoint_id=checkpoint_id
    )
    
    result = await production_engine.optimize(plan)
    
    assert result.rollback_executed is True
    assert result.restored_checkpoint_id == checkpoint_id


@pytest.mark.asyncio
async def test_cluster_wide_rollback(production_engine):
    """Rollback propagates across cluster."""
    mock_cluster_manager = MagicMock()
    mock_cluster_manager.rollback_all = AsyncMock(return_value={
        "nodes_rolled_back": 3,
        "success": True
    })
    
    production_engine.cluster_manager = mock_cluster_manager
    
    plan = OptimizationPlan(
        skill_name="production_skill",
        optimization_type="performance",
        risk_level=2,
        seed=42,
        cluster_wide=True
    )
    
    result = await production_engine.optimize(plan)
    
    assert result.cluster_rollback is True
    assert result.nodes_affected == 3


@pytest.mark.asyncio
async def test_rollback_audit_logged(production_engine):
    """Rollback events are audit logged."""
    audit_log = []
    
    def mock_audit(event):
        audit_log.append(event)
    
    production_engine.audit_logger = MagicMock(record=mock_audit)
    
    plan = OptimizationPlan(
        skill_name="production_skill",
        optimization_type="performance",
        risk_level=2,
        seed=42
    )
    
    await production_engine.optimize(plan)
    
    assert any("rollback" in str(e).lower() for e in audit_log)


@pytest.mark.asyncio
async def test_high_risk_still_requires_approval(production_engine):
    """High-risk optimizations still require human approval."""
    plan = OptimizationPlan(
        skill_name="high_risk_skill",
        optimization_type="performance",
        risk_level=4,
        seed=42
    )
    
    result = await production_engine.optimize(plan)
    
    assert result.approval_required is True
    assert result.status == "pending_approval"


def test_optimization_plan_protocol_version():
    """OptimizationPlan has protocol_version."""
    plan = OptimizationPlan(
        skill_name="test",
        optimization_type="performance",
        risk_level=1,
        seed=42
    )
    
    assert plan.protocol_version == "1.0"
