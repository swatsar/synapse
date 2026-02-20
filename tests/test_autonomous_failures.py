"""Tests for autonomous failure handling.

Phase 11 - Continuous Self-Improvement & Adaptive Governance.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from synapse.skills.self_improvement.engine import (
    SelfImprovementEngine,
    ImprovementPlan
)


pytestmark = pytest.mark.unit


@pytest.fixture
def failure_engine():
    """Create engine with failure handling."""
    mock_telemetry = MagicMock()
    mock_telemetry.get_system_metrics = MagicMock(return_value={
        "failure_rate": 0.15
    })
    mock_telemetry.get_skill_metrics = MagicMock(return_value={
        "success_rate": 0.65,
        "avg_latency_ms": 350
    })
    
    mock_resource = MagicMock()
    mock_resource.check_limits = MagicMock(return_value=True)
    mock_resource.get_available = MagicMock(return_value={"cpu": 80, "memory": 2048})
    
    mock_policy = MagicMock()
    mock_policy.check_permission = MagicMock(return_value=True)
    mock_policy.requires_approval = MagicMock(return_value=False)
    
    mock_registry = MagicMock()
    mock_registry.get_skill = MagicMock(return_value=MagicMock(
        name="failing_skill",
        risk_level=1,
        success_rate=0.65
    ))
    mock_registry.register = AsyncMock(side_effect=Exception("Registration failed"))
    
    mock_rollback = MagicMock()
    mock_rollback.create_checkpoint = AsyncMock(return_value="cp-fail-123")
    mock_rollback.execute_rollback = AsyncMock(return_value=MagicMock(success=True))
    
    engine = SelfImprovementEngine(
        telemetry=mock_telemetry,
        resource_manager=mock_resource,
        policy_engine=mock_policy,
        skill_registry=mock_registry,
        rollback_manager=mock_rollback
    )
    
    return engine


@pytest.mark.asyncio
async def test_failed_improvement_triggers_rollback(failure_engine):
    """Failed improvement triggers automatic rollback."""
    plan = ImprovementPlan(
        target="skill:failing_skill",
        improvement_type="performance",
        risk_level=1,
        seed=42
    )
    
    result = await failure_engine.improve(plan)
    
    assert result.success is False
    assert result.rollback_executed is True


@pytest.mark.asyncio
async def test_rollback_restores_state(failure_engine):
    """Rollback restores previous state."""
    checkpoint_id = await failure_engine.rollback_manager.create_checkpoint(
        agent_id="test",
        session_id="test_session"
    )
    
    plan = ImprovementPlan(
        target="skill:failing_skill",
        improvement_type="performance",
        risk_level=1,
        seed=42,
        checkpoint_id=checkpoint_id
    )
    
    result = await failure_engine.improve(plan)
    
    assert result.rollback_executed is True
    assert result.restored_checkpoint_id == checkpoint_id


@pytest.mark.asyncio
async def test_cluster_wide_rollback(failure_engine):
    """Rollback propagates cluster-wide."""
    mock_cluster = MagicMock()
    mock_cluster.rollback_all = AsyncMock(return_value={
        "nodes_rolled_back": 3,
        "success": True
    })
    
    failure_engine.cluster_manager = mock_cluster
    
    plan = ImprovementPlan(
        target="skill:failing_skill",
        improvement_type="performance",
        risk_level=1,
        seed=42,
        cluster_wide=True
    )
    
    result = await failure_engine.improve(plan)
    
    assert result.cluster_rollback is True
    assert result.nodes_affected == 3


@pytest.mark.asyncio
async def test_failure_audit_logged(failure_engine):
    """Failures are audit logged."""
    audit_log = []
    failure_engine.audit_logger = MagicMock(record=lambda e: audit_log.append(e))
    
    plan = ImprovementPlan(
        target="skill:failing_skill",
        improvement_type="performance",
        risk_level=1,
        seed=42
    )
    
    await failure_engine.improve(plan)
    
    assert any("rollback" in str(e).lower() or "fail" in str(e).lower() for e in audit_log)


@pytest.mark.asyncio
async def test_high_risk_failure_routes_to_approval(failure_engine):
    """High-risk failures still route through approval."""
    failure_engine.policy_engine.requires_approval = MagicMock(return_value=True)
    
    plan = ImprovementPlan(
        target="system",
        improvement_type="policy",
        risk_level=4,
        seed=42
    )
    
    result = await failure_engine.improve(plan)
    
    assert result.approval_required is True
    assert result.status == "pending_approval"


@pytest.mark.asyncio
async def test_deterministic_failure_handling(failure_engine):
    """Failure handling is deterministic."""
    plan1 = ImprovementPlan(
        target="skill:failing_skill",
        improvement_type="performance",
        risk_level=1,
        seed=42
    )
    
    plan2 = ImprovementPlan(
        target="skill:failing_skill",
        improvement_type="performance",
        risk_level=1,
        seed=42
    )
    
    result1 = await failure_engine.improve(plan1)
    result2 = await failure_engine.improve(plan2)
    
    assert result1.improvement_id == result2.improvement_id
    assert result1.rollback_executed == result2.rollback_executed
