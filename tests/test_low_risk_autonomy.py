"""Tests for low-risk autonomous evolution.

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
def autonomy_engine():
    """Create autonomy engine with all dependencies."""
    mock_telemetry = MagicMock()
    mock_telemetry.get_skill_metrics = MagicMock(return_value={
        "success_rate": 0.65,
        "avg_latency_ms": 350
    })
    
    mock_resource = MagicMock()
    mock_resource.check_limits = MagicMock(return_value=True)
    mock_resource.get_available = MagicMock(return_value={
        "cpu": 80, "memory": 2048
    })
    
    mock_registry = MagicMock()
    mock_registry.get_skill = MagicMock(return_value=MagicMock(
        name="low_risk_skill",
        risk_level=1,
        success_rate=0.65
    ))
    mock_registry.register = AsyncMock(return_value=True)
    
    # Mock rollback manager
    mock_rollback = MagicMock()
    mock_rollback.create_checkpoint = AsyncMock(return_value="cp-123")
    mock_rollback.execute_rollback = AsyncMock(return_value=MagicMock(success=True))
    
    return AutonomousOptimizationEngine(
        telemetry=mock_telemetry,
        resource_manager=mock_resource,
        skill_registry=mock_registry,
        rollback_manager=mock_rollback
    )


@pytest.mark.asyncio
async def test_low_risk_skill_auto_optimizes(autonomy_engine):
    """Low-risk skill optimizes without human approval."""
    plan = OptimizationPlan(
        skill_name="low_risk_skill",
        optimization_type="performance",
        risk_level=1,
        seed=42
    )
    
    result = await autonomy_engine.optimize(plan)
    
    assert result.success is True
    assert result.approval_required is False
    assert result.status == "completed"


@pytest.mark.asyncio
async def test_low_risk_skill_registers_automatically(autonomy_engine):
    """Optimized low-risk skill registers automatically."""
    plan = OptimizationPlan(
        skill_name="low_risk_skill",
        optimization_type="performance",
        risk_level=1,
        seed=42
    )
    
    result = await autonomy_engine.optimize(plan)
    
    assert result.registered is True
    assert result.new_skill_id is not None


@pytest.mark.asyncio
async def test_low_risk_skill_performance_improves(autonomy_engine):
    """Optimization improves skill performance metrics."""
    plan = OptimizationPlan(
        skill_name="low_risk_skill",
        optimization_type="performance",
        risk_level=1,
        seed=42
    )
    
    result = await autonomy_engine.optimize(plan)
    
    assert result.improvement is not None
    assert result.improvement["success_rate"] > 0


@pytest.mark.asyncio
async def test_low_risk_skill_telemetry_recorded(autonomy_engine):
    """Optimization events are recorded in telemetry."""
    telemetry_events = []
    
    def mock_record(event, data):
        telemetry_events.append({"event": event, "data": data})
    
    autonomy_engine.telemetry.record = mock_record
    
    plan = OptimizationPlan(
        skill_name="low_risk_skill",
        optimization_type="performance",
        risk_level=1,
        seed=42
    )
    
    await autonomy_engine.optimize(plan)
    
    assert len(telemetry_events) > 0
    assert any(e["event"] == "optimization_completed" for e in telemetry_events)


@pytest.mark.asyncio
async def test_low_risk_skill_deterministic_evolution(autonomy_engine):
    """Same seed produces same evolution result."""
    plan1 = OptimizationPlan(
        skill_name="low_risk_skill",
        optimization_type="performance",
        risk_level=1,
        seed=42
    )
    
    plan2 = OptimizationPlan(
        skill_name="low_risk_skill",
        optimization_type="performance",
        risk_level=1,
        seed=42
    )
    
    result1 = await autonomy_engine.optimize(plan1)
    result2 = await autonomy_engine.optimize(plan2)
    
    assert result1.optimization_id == result2.optimization_id
    assert result1.new_skill_id == result2.new_skill_id


@pytest.mark.asyncio
async def test_low_risk_skill_rollback_on_failure(autonomy_engine):
    """Failed optimization triggers rollback."""
    # Make optimization fail
    autonomy_engine.skill_registry.register = AsyncMock(return_value=False)
    
    plan = OptimizationPlan(
        skill_name="low_risk_skill",
        optimization_type="performance",
        risk_level=1,
        seed=42
    )
    
    result = await autonomy_engine.optimize(plan)
    
    assert result.success is False
    assert result.rollback_executed is True
