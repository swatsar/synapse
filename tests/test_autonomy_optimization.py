"""Tests for autonomous optimization lifecycle.

Phase 10 - Production Autonomy & Self-Optimization.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from synapse.skills.autonomy.engine import (
    AutonomousOptimizationEngine,
    OptimizationPlan,
    OptimizationResult
)


pytestmark = pytest.mark.unit


@pytest.fixture
def mock_telemetry():
    """Mock telemetry engine."""
    telemetry = MagicMock()
    telemetry.get_skill_metrics = MagicMock(return_value={
        "success_rate": 0.65,
        "avg_latency_ms": 350,
        "resource_usage": {"cpu": 45, "memory": 512}
    })
    return telemetry


@pytest.fixture
def mock_resource_manager():
    """Mock resource manager."""
    manager = MagicMock()
    manager.check_limits = MagicMock(return_value=True)
    manager.get_available = MagicMock(return_value={
        "cpu": 80,
        "memory": 2048,
        "disk": 10240,
        "network": 1024
    })
    return manager


@pytest.fixture
def mock_skill_registry():
    """Mock skill registry."""
    registry = MagicMock()
    registry.get_skill = MagicMock(return_value=MagicMock(
        name="test_skill",
        risk_level=1,
        success_rate=0.65,
        avg_latency_ms=350
    ))
    registry.register = AsyncMock(return_value=True)
    return registry


@pytest.mark.asyncio
async def test_low_risk_skill_optimizes_autonomously(mock_telemetry, mock_resource_manager, mock_skill_registry):
    """Low-risk skills can optimize without human approval."""
    engine = AutonomousOptimizationEngine(
        telemetry=mock_telemetry,
        resource_manager=mock_resource_manager,
        skill_registry=mock_skill_registry
    )
    
    plan = OptimizationPlan(
        skill_name="test_skill",
        optimization_type="performance",
        risk_level=1,
        seed=42
    )
    
    result = await engine.optimize(plan)
    
    assert result.success is True
    assert result.approval_required is False
    assert result.protocol_version == "1.0"


@pytest.mark.asyncio
async def test_high_risk_skill_requires_approval(mock_telemetry, mock_resource_manager, mock_skill_registry):
    """High-risk skills require human approval."""
    engine = AutonomousOptimizationEngine(
        telemetry=mock_telemetry,
        resource_manager=mock_resource_manager,
        skill_registry=mock_skill_registry
    )
    
    plan = OptimizationPlan(
        skill_name="high_risk_skill",
        optimization_type="performance",
        risk_level=4,
        seed=42
    )
    
    result = await engine.optimize(plan)
    
    assert result.approval_required is True
    assert result.status == "pending_approval"


@pytest.mark.asyncio
async def test_optimization_respects_resource_limits(mock_telemetry, mock_resource_manager, mock_skill_registry):
    """Optimization respects resource limits."""
    # Set resource manager to reject - no available resources
    mock_resource_manager.get_available = MagicMock(return_value={})
    
    engine = AutonomousOptimizationEngine(
        telemetry=mock_telemetry,
        resource_manager=mock_resource_manager,
        skill_registry=mock_skill_registry
    )
    
    plan = OptimizationPlan(
        skill_name="test_skill",
        optimization_type="performance",
        risk_level=1,
        seed=42
    )
    
    result = await engine.optimize(plan)
    
    assert result.success is False
    assert "resource" in result.error.lower()


@pytest.mark.asyncio
async def test_optimization_deterministic_output(mock_telemetry, mock_resource_manager, mock_skill_registry):
    """Same seed produces same optimization result."""
    engine = AutonomousOptimizationEngine(
        telemetry=mock_telemetry,
        resource_manager=mock_resource_manager,
        skill_registry=mock_skill_registry
    )
    
    plan1 = OptimizationPlan(
        skill_name="test_skill",
        optimization_type="performance",
        risk_level=1,
        seed=42
    )
    
    plan2 = OptimizationPlan(
        skill_name="test_skill",
        optimization_type="performance",
        risk_level=1,
        seed=42
    )
    
    result1 = await engine.optimize(plan1)
    result2 = await engine.optimize(plan2)
    
    assert result1.optimization_id == result2.optimization_id


@pytest.mark.asyncio
async def test_optimization_audit_logged(mock_telemetry, mock_resource_manager, mock_skill_registry):
    """Optimization events are audit logged."""
    audit_log = []
    
    def mock_audit(event):
        audit_log.append(event)
    
    engine = AutonomousOptimizationEngine(
        telemetry=mock_telemetry,
        resource_manager=mock_resource_manager,
        skill_registry=mock_skill_registry,
        audit_logger=MagicMock(record=mock_audit)
    )
    
    plan = OptimizationPlan(
        skill_name="test_skill",
        optimization_type="performance",
        risk_level=1,
        seed=42
    )
    
    await engine.optimize(plan)
    
    assert len(audit_log) > 0
    assert audit_log[0]["event"] == "optimization_started"


def test_protocol_version_present():
    """All models have protocol_version."""
    plan = OptimizationPlan(
        skill_name="test",
        optimization_type="performance",
        risk_level=1,
        seed=42
    )
    result = OptimizationResult(
        success=True,
        optimization_id="test-id"
    )
    
    assert plan.protocol_version == "1.0"
    assert result.protocol_version == "1.0"
